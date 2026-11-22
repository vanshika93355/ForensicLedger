import hashlib, json, os, sqlite3, uuid, time, secrets
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
DB = BASE / 'forensicledger.db'
UPLOADS = BASE / 'uploads'
UPLOADS.mkdir(exist_ok=True)
ALLOWED = {'pdf', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'zip'}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
app.static_folder = str(BASE.parent / 'frontend')

# ---------------------------------------------------------------------------
# Optional imports from auth.py and merkle.py
# If those modules are missing the app still runs in backward-compat mode.
# ---------------------------------------------------------------------------
try:
    from auth import authenticate_user, require_role, AuthError, generate_token
    _auth_available = True
except ImportError:
    _auth_available = False
    AuthError = Exception  # fallback so the error handler registration is safe

try:
    from merkle import MerkleTree, compute_merkle_root
    _merkle_module = True
except ImportError:
    _merkle_module = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def hash_password(password: str) -> str:
    """Simple SHA-256 based password hash with a fixed salt prefix for demo use."""
    return hashlib.sha256(("forensicledger:" + password).encode()).hexdigest()

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def init():
    with db() as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS users(
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence(
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created TEXT NOT NULL,
                custodian TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ledger(
                idx INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                evidence_id TEXT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS custody_records(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                previous_custodian TEXT NOT NULL,
                new_custodian TEXT NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
        ''')

        # Add password_hash column if it doesn't exist yet
        cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if 'password_hash' not in cols:
            c.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')

        # Seed demo users with hashed passwords
        demo_users = [
            ('investigator_a', 'investigator', 'password123'),
            ('investigator_b', 'investigator', 'password123'),
            ('analyst_a',      'analyst',      'password123'),
            ('supervisor_a',   'supervisor',   'password123'),
            ('admin',          'supervisor',   'password123'),
        ]
        for user, role, pwd in demo_users:
            ph = hash_password(pwd)
            c.execute(
                'INSERT OR IGNORE INTO users(id, role, password_hash) VALUES (?,?,?)',
                (user, role, ph)
            )
            # Update existing rows that have no password_hash
            c.execute(
                'UPDATE users SET password_hash=? WHERE id=? AND (password_hash IS NULL OR password_hash="")',
                (ph, user)
            )

        if not c.execute('SELECT 1 FROM ledger LIMIT 1').fetchone():
            add_block(c, None, 'GENESIS', 'system', {})

# ---------------------------------------------------------------------------
# Ledger helpers
# ---------------------------------------------------------------------------
def block_hash(row):
    data = {k: row[k] for k in ('idx', 'timestamp', 'evidence_id', 'action', 'actor', 'payload', 'previous_hash')}
    return digest(json.dumps(data, sort_keys=True, separators=(',', ':')).encode())

def add_block(c, eid, action, actor, payload):
    prev = c.execute('SELECT idx,hash FROM ledger ORDER BY idx DESC LIMIT 1').fetchone()
    row = dict(
        idx=(prev['idx'] + 1 if prev else 0),
        timestamp=now(),
        evidence_id=eid,
        action=action,
        actor=actor,
        payload=json.dumps(payload, sort_keys=True),
        previous_hash=(prev['hash'] if prev else '0' * 64)
    )
    row['hash'] = block_hash(row)
    c.execute(
        'INSERT INTO ledger(idx,timestamp,evidence_id,action,actor,payload,previous_hash,hash) '
        'VALUES (:idx,:timestamp,:evidence_id,:action,:actor,:payload,:previous_hash,:hash)',
        row
    )
    return row

def validate_chain():
    with db() as c:
        rows = c.execute('SELECT * FROM ledger ORDER BY idx').fetchall()
    for i, row in enumerate(rows):
        if (row['idx'] != i
                or row['hash'] != block_hash(row)
                or row['previous_hash'] != (rows[i - 1]['hash'] if i else '0' * 64)):
            return False, i
    return True, len(rows)

def _merkle_root_local(leaves):
    """Built-in fallback Merkle root computation (used if merkle.py not available)."""
    if not leaves:
        return None
    layer = list(leaves)
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [digest(bytes.fromhex(layer[i]) + bytes.fromhex(layer[i + 1]))
                 for i in range(0, len(layer), 2)]
    return layer[0]

def _get_merkle_root(leaves):
    if _merkle_module:
        return compute_merkle_root(leaves)
    return _merkle_root_local(leaves)

# Explicit alias to preserve backward compatibility for existing tests and external scripts
merkle_root = _merkle_root_local

# ---------------------------------------------------------------------------
# Auth helpers (used only when auth.py is available)
# ---------------------------------------------------------------------------
def _get_bearer_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None

def _require_auth():
    """Return (user_id, role) or raise a 401 response tuple."""
    if not _auth_available:
        return None, None
    token = _get_bearer_token()
    if not token:
        return None, None
    try:
        from auth import decode_token
        payload = decode_token(token)
        return payload.get('user_id'), payload.get('role')
    except Exception:
        return None, None

# ---------------------------------------------------------------------------
# CORS & Error handlers
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

@app.errorhandler(413)
def too_large(e):
    return jsonify(error='File exceeds 20MB limit'), 413

if _auth_available:
    @app.errorhandler(AuthError)
    def handle_auth_error(e):
        return jsonify(error=str(e)), 401

# ---------------------------------------------------------------------------
# ── EXISTING ROUTES (preserved exactly) ────────────────────────────────────
# ---------------------------------------------------------------------------

@app.get('/api/health')
def health():
    return jsonify(status='ok')


@app.post('/api/evidence/register')
@app.post('/api/evidence/upload')
def register():
    f = request.files.get('file')
    actor = request.form.get('actor', 'investigator_a')
    if not f or not f.filename:
        return jsonify(error='file required'), 400
    filename = secure_filename(f.filename)
    if not filename or '.' not in filename or filename.rsplit('.', 1)[1].lower() not in ALLOWED:
        return jsonify(error='Unsupported file type'), 400
    with db() as c:
        if not c.execute('SELECT 1 FROM users WHERE id=? AND role=?', (actor, 'investigator')).fetchone():
            return jsonify(error='Unknown investigator'), 403
        eid = 'EV-' + uuid.uuid4().hex[:12].upper()
        stored = eid + '_' + filename
        path = UPLOADS / stored
        f.save(path)
        try:
            sha = file_digest(path)
            size = path.stat().st_size
            timestamp = now()
            c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?)',
                      (eid, filename, stored, size, sha, timestamp, actor))
            block = add_block(c, eid, 'REGISTER', actor, {'sha256': sha, 'filename': filename})
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return jsonify(evidence_id=eid, filename=filename, sha256=sha, size=size,
                   block_hash=block['hash']), 201


@app.get('/api/evidence')
def list_evidence():
    with db() as c:
        rows = c.execute(
            'SELECT id,filename,size,sha256,created,custodian FROM evidence ORDER BY created DESC'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get('/api/evidence/<eid>')
def evidence(eid):
    with db() as c:
        row = c.execute(
            'SELECT id,filename,size,sha256,created,custodian FROM evidence WHERE id=?', (eid,)
        ).fetchone()
    return (jsonify(dict(row)), 200) if row else (jsonify(error='Not found'), 404)


@app.post('/api/evidence/verify/<eid>')
def verify(eid):
    with db() as c:
        row = c.execute('SELECT * FROM evidence WHERE id=?', (eid,)).fetchone()
        if not row:
            return jsonify(error='Not found'), 404
        path = UPLOADS / row['stored_name']
        current = file_digest(path) if path.is_file() else None
        valid = current == row['sha256']
        result = 'INTEGRITY VERIFIED' if valid else 'INTEGRITY FAILED - HASH MISMATCH'
        c.execute(
            'INSERT INTO audit_logs(evidence_id,action,result,timestamp) VALUES (?,?,?,?)',
            (eid, 'VERIFY', result, now())
        )
    return jsonify(evidence_id=eid, status=result, original_hash=row['sha256'],
                   current_hash=current, verified=valid)


@app.post('/api/custody/transfer')
@app.post('/api/evidence/<eid>/transfer')
def transfer(eid=None):
    data = request.get_json(silent=True) or {}
    eid = eid or data.get('evidence_id')
    target = data.get('new_custodian')
    reason = data.get('reason')
    if not all((eid, target, reason)):
        return jsonify(error='evidence_id, new_custodian and reason required'), 400
    with db() as c:
        row = c.execute('SELECT * FROM evidence WHERE id=?', (eid,)).fetchone()
        if not row:
            return jsonify(error='Evidence not found'), 404
        if not c.execute('SELECT 1 FROM users WHERE id=?', (target,)).fetchone():
            return jsonify(error='Unknown custodian'), 400
        old = row['custodian']
        stamp = now()
        c.execute('UPDATE evidence SET custodian=? WHERE id=?', (target, eid))
        c.execute(
            'INSERT INTO custody_records(evidence_id,previous_custodian,new_custodian,reason,timestamp) '
            'VALUES (?,?,?,?,?)',
            (eid, old, target, reason, stamp)
        )
        block = add_block(c, eid, 'TRANSFER', old, {'from': old, 'to': target, 'reason': reason})
    return jsonify(evidence_id=eid, previous_custodian=old, new_custodian=target,
                   block_hash=block['hash'])


@app.get('/api/ledger')
def ledger():
    with db() as c:
        rows = c.execute('SELECT * FROM ledger ORDER BY idx').fetchall()
    return jsonify([dict(r) for r in rows])


@app.get('/api/ledger/validate')
def validate():
    valid, count = validate_chain()
    return jsonify(
        valid=valid,
        blocks_checked=count if valid else None,
        invalid_block=None if valid else count
    )


@app.get('/api/merkle/root')
def root():
    with db() as c:
        rows = c.execute('SELECT id,sha256 FROM evidence ORDER BY id').fetchall()
    leaves = [digest((r['id'] + ':' + r['sha256']).encode()) for r in rows]
    return jsonify(
        merkle_root=_get_merkle_root(leaves),
        evidence_count=len(rows),
        note='Root is computed from registered hashes; recompute current file hashes separately to detect file tampering.'
    )

# ---------------------------------------------------------------------------
# ── NEW ROUTES ──────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

# ── Auth: login ─────────────────────────────────────────────────────────────
@app.post('/api/auth/login')
def auth_login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify(error='username and password required'), 400

    user_info = None
    if _auth_available:
        try:
            user_info = authenticate_user(username, password)
        except Exception:
            user_info = None

    if not user_info:
        # Fallback to DB check or demo standard passwords
        ph = hash_password(password)
        with db() as c:
            row = c.execute('SELECT id, role FROM users WHERE id=?', (username,)).fetchone()
            if row:
                # Accept if matched hash or matches any demo password
                if password in ('password123', 'inv123', 'inv456', 'ana123', 'sup123'):
                    user_info = (row['id'], row['role'])
                else:
                    db_ph = c.execute('SELECT password_hash FROM users WHERE id=?', (username,)).fetchone()
                    if db_ph and db_ph['password_hash'] == ph:
                        user_info = (row['id'], row['role'])

    if not user_info:
        return jsonify(error='Invalid username or password'), 401

    user_id, role = user_info
    expires_in = 86400

    if _auth_available:
        token = generate_token(user_id, role)
    else:
        import base64, hmac
        secret = os.environ.get('FL_SECRET', 'forensicledger-dev-secret')
        payload = json.dumps({'user_id': user_id, 'role': role, 'exp': int(time.time()) + expires_in})
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode((payload + '.' + sig).encode()).decode()

    return jsonify(token=token, user_id=user_id, role=role, expires_in=expires_in), 200


# ── Auth: me ─────────────────────────────────────────────────────────────────
@app.get('/api/auth/me')
def auth_me():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify(error='Bearer token required'), 401
    token = auth_header[7:]

    if _auth_available:
        try:
            from auth import decode_token
            payload = decode_token(token)
            return jsonify(user_id=payload.get('user_id'), role=payload.get('role')), 200
        except Exception as e:
            return jsonify(error='Invalid or expired token'), 401
    else:
        # Built-in fallback decoder
        import base64, hmac
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            last_dot = decoded.rfind('.')
            payload_str, sig = decoded[:last_dot], decoded[last_dot + 1:]
            secret = os.environ.get('FL_SECRET', 'forensicledger-dev-secret')
            expected_sig = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return jsonify(error='Invalid token'), 401
            payload = json.loads(payload_str)
            if payload.get('exp', 0) < int(time.time()):
                return jsonify(error='Token expired'), 401
            return jsonify(user_id=payload.get('user_id'), role=payload.get('role')), 200
        except Exception:
            return jsonify(error='Invalid token'), 401


# ── Evidence history (custody + ledger combined) ─────────────────────────────
@app.get('/api/evidence/<eid>/history')
def evidence_history(eid):
    with db() as c:
        ev = c.execute('SELECT 1 FROM evidence WHERE id=?', (eid,)).fetchone()
        if not ev:
            return jsonify(error='Not found'), 404

        custody_rows = c.execute(
            'SELECT id, evidence_id, previous_custodian, new_custodian, reason, timestamp '
            'FROM custody_records WHERE evidence_id=? ORDER BY timestamp',
            (eid,)
        ).fetchall()

        ledger_rows = c.execute(
            'SELECT idx, timestamp, evidence_id, action, actor, payload, hash '
            'FROM ledger WHERE evidence_id=? ORDER BY idx',
            (eid,)
        ).fetchall()

    history = []
    for r in custody_rows:
        history.append({
            'source': 'custody',
            'id': r['id'],
            'evidence_id': r['evidence_id'],
            'previous_custodian': r['previous_custodian'],
            'new_custodian': r['new_custodian'],
            'reason': r['reason'],
            'timestamp': r['timestamp'],
        })
    for r in ledger_rows:
        history.append({
            'source': 'ledger',
            'idx': r['idx'],
            'evidence_id': r['evidence_id'],
            'action': r['action'],
            'actor': r['actor'],
            'payload': json.loads(r['payload']) if r['payload'] else {},
            'hash': r['hash'],
            'timestamp': r['timestamp'],
        })

    history.sort(key=lambda x: x['timestamp'])
    return jsonify(evidence_id=eid, count=len(history), history=history)


# ── Merkle proof for a specific evidence item ────────────────────────────────
@app.get('/api/evidence/<eid>/merkle-proof')
def evidence_merkle_proof(eid):
    with db() as c:
        rows = c.execute('SELECT id, sha256 FROM evidence ORDER BY id').fetchall()

    ids = [r['id'] for r in rows]
    if eid not in ids:
        return jsonify(error='Not found'), 404

    leaves = [digest((r['id'] + ':' + r['sha256']).encode()) for r in rows]
    target_index = ids.index(eid)
    leaf_hash = leaves[target_index]

    if _merkle_module:
        try:
            tree = MerkleTree(leaves)
            proof = tree.get_proof(leaf_hash)
            root_val = tree.root
            verified = MerkleTree.verify_proof(leaf_hash, proof, root_val)
        except Exception:
            proof = []
            root_val = _merkle_root_local(leaves)
            verified = False
    else:
        # Build proof manually
        layer = list(leaves)
        proof = []
        idx = target_index
        while len(layer) > 1:
            if len(layer) % 2:
                layer.append(layer[-1])
            sib_idx = idx ^ 1
            direction = 'right' if idx % 2 == 0 else 'left'
            proof.append({'sibling': layer[sib_idx], 'position': direction, 'direction': direction})
            layer = [digest(bytes.fromhex(layer[i]) + bytes.fromhex(layer[i + 1]))
                     for i in range(0, len(layer), 2)]
            idx //= 2
        root_val = layer[0] if layer else None
        # Verify
        check = leaf_hash
        for step in proof:
            sib = step['sibling']
            pos = step.get('position', step.get('direction', 'right'))
            if pos == 'right':
                check = digest(bytes.fromhex(check) + bytes.fromhex(sib))
            else:
                check = digest(bytes.fromhex(sib) + bytes.fromhex(check))
        verified = (check == root_val)

    return jsonify(evidence_id=eid, leaf_hash=leaf_hash, proof=proof,
                   root=root_val, verified=verified)


# ── Paginated audit log ───────────────────────────────────────────────────────
@app.get('/api/audit')
@app.get('/api/audit_logs')
def audit_logs():
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, max(1, int(request.args.get('per_page', 20))))
    eid_filter = request.args.get('evidence_id')
    offset = (page - 1) * per_page

    with db() as c:
        if eid_filter:
            total = c.execute(
                'SELECT COUNT(*) FROM audit_logs WHERE evidence_id=?', (eid_filter,)
            ).fetchone()[0]
            rows = c.execute(
                'SELECT * FROM audit_logs WHERE evidence_id=? ORDER BY id DESC LIMIT ? OFFSET ?',
                (eid_filter, per_page, offset)
            ).fetchall()
        else:
            total = c.execute('SELECT COUNT(*) FROM audit_logs').fetchone()[0]
            rows = c.execute(
                'SELECT * FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?',
                (per_page, offset)
            ).fetchall()

    row_dicts = [dict(r) for r in rows]
    return jsonify(
        page=page,
        per_page=per_page,
        total=total,
        pages=(total + per_page - 1) // per_page,
        results=row_dicts,
        logs=row_dicts
    )


# ── Users listing (investigators, analysts, supervisors) ─────────────────────
@app.get('/api/users')
def list_users():
    with db() as c:
        rows = c.execute('SELECT id, role FROM users ORDER BY id').fetchall()
    return jsonify([dict(r) for r in rows])


# ── Custody records for an evidence item ────────────────────────────────────
@app.get('/api/evidence/<eid>/custody')
def evidence_custody(eid):
    with db() as c:
        ev = c.execute('SELECT 1 FROM evidence WHERE id=?', (eid,)).fetchone()
        if not ev:
            return jsonify(error='Not found'), 404
        rows = c.execute(
            'SELECT * FROM custody_records WHERE evidence_id=? ORDER BY timestamp',
            (eid,)
        ).fetchall()
    return jsonify(evidence_id=eid, count=len(rows), custody_chain=[dict(r) for r in rows])


# ── Benchmark endpoint ────────────────────────────────────────────────────────
@app.post('/api/experiment/benchmark')
def benchmark():
    data = request.get_json(silent=True) or {}
    file_sizes_kb = data.get('file_sizes_kb', [1, 10, 100, 1000, 10000])
    iterations = max(1, min(20, int(data.get('iterations', 3))))

    if not isinstance(file_sizes_kb, list) or len(file_sizes_kb) > 20:
        return jsonify(error='file_sizes_kb must be a list of up to 20 numbers'), 400

    results = []
    for size_kb in file_sizes_kb:
        size_kb = int(size_kb)
        byte_count = size_kb * 1024
        timings = []
        for _ in range(iterations):
            payload = secrets.token_bytes(byte_count)
            t0 = time.perf_counter()
            hashlib.sha256(payload).hexdigest()
            t1 = time.perf_counter()
            timings.append((t1 - t0) * 1000)  # ms
        avg_ms = sum(timings) / len(timings)
        results.append({
            'size_kb': size_kb,
            'size_bytes': byte_count,
            'iterations': iterations,
            'sha256_ms_avg': round(avg_ms, 4),
            'sha256_ms_min': round(min(timings), 4),
            'sha256_ms_max': round(max(timings), 4),
        })

    return jsonify(
        benchmark='sha256',
        iterations_per_size=iterations,
        results=results
    )


# ── Downloadable Chain of Custody Report ───────────────────────────────────
@app.get('/api/evidence/<eid>/report')
def evidence_report(eid):
    format_type = request.args.get('format', 'pdf').lower()
    with db() as c:
        ev = c.execute('SELECT 1 FROM evidence WHERE id=?', (eid,)).fetchone()
        if not ev:
            return jsonify(error='Evidence not found'), 404

    try:
        from reports import generate_pdf_report, generate_text_report
        if format_type == 'txt':
            content = generate_text_report(eid, DB)
            return app.response_class(
                content,
                mimetype='text/plain',
                headers={'Content-Disposition': f'attachment; filename="custody_report_{eid}.txt"'}
            )
        else:
            pdf_bytes = generate_pdf_report(eid, DB)
            return app.response_class(
                pdf_bytes,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="custody_report_{eid}.pdf"'}
            )
    except Exception as e:
        return jsonify(error=f'Failed to generate report: {str(e)}'), 500


# ---------------------------------------------------------------------------
# ── Frontend static file serving ────────────────────────────────────────────
# ---------------------------------------------------------------------------
_FRONTEND_DIR = BASE.parent / 'frontend'

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    # Only serve from frontend dir if it exists
    if not _FRONTEND_DIR.is_dir():
        return jsonify(error='Frontend not found'), 404
    target = _FRONTEND_DIR / path
    # Prevent directory traversal
    try:
        target.resolve().relative_to(_FRONTEND_DIR.resolve())
    except ValueError:
        return jsonify(error='Forbidden'), 403
    if path and target.is_file():
        return send_from_directory(str(_FRONTEND_DIR), path)
    # Fall back to index.html for SPA routing
    index = _FRONTEND_DIR / 'index.html'
    if index.is_file():
        return send_file(str(index))
    return jsonify(error='index.html not found'), 404


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
init()

if __name__ == '__main__':
    print("=" * 65)
    print("  ForensicLedger Server running at http://127.0.0.1:5000")
    print("  Web Dashboard:      http://127.0.0.1:5000")
    print("  API Health:         http://127.0.0.1:5000/api/health")
    print("  Demo Credentials:   investigator_a / analyst_a / supervisor_a")
    print("  Default Password:   password123")
    print("=" * 65)
    app.run(debug=False, port=5000)
