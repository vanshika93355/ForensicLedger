# ForensicLedger: A Hash-Verified Chain of Custody Management System

**ForensicLedger** is a complete, cryptographically verified digital evidence chain-of-custody (CoC) and audit management system. It pairs streaming SHA-256 fingerprinting and off-chain storage with an immutable hash-linked private blockchain and binary Merkle tree accumulators.

---

## 1. Core Architecture & Technologies

- **Backend:** Python 3.11–3.13, Flask 3.1, SQLite / PostgreSQL-ready schema with WAL-mode journaling.
- **Cryptographic Engine:** SHA-256 digital fingerprinting (FIPS PUB 180-4), chunked 1 MB streaming hashing.
- **Private Blockchain Ledger:** Sequential hash-linked blocks:
  $$H(B_k) = \text{SHA-256}(\text{JSON}_{\text{canonical}}(idx \parallel timestamp \parallel evidence\_id \parallel action \parallel actor \parallel payload \parallel previous\_hash))$$
- **Merkle Tree Accumulator:** Full binary Merkle tree with logarithmic inclusion proof generation and verification ($O(\log N)$).
- **Authentication & RBAC:** PyJWT JSON Web Tokens (HMAC-SHA256) enforcing strict role segregation (`investigator`, `analyst`, `supervisor`).
- **Reporting Engine:** Automated PDF / Plain-Text chain-of-custody court admissibility reports (fpdf2).
- **Frontend Dashboard:** Modern, responsive single-page web interface (Tailwind CSS, Font Awesome, Vanilla JavaScript).

```
+----------------------------------------------------------------------------------+
|                            USER & CLIENT INTERFACE                              |
|  +--------------------+  +---------------------+  +---------------------------+  |
|  | Investigator View  |  | Forensic Analyst UI |  | Supervisor & Audit Panel  |  |
|  +--------------------+  +---------------------+  +---------------------------+  |
+----------------------------------------+-----------------------------------------+
                                         | REST API (JSON / Bearer JWT)
+----------------------------------------v-----------------------------------------+
|                               API & AUTH GATEWAY                                 |
|  - JWT Authentication & RBAC Middleware (PyJWT, HS256)                          |
|  - Multi-part Stream Upload Handler (SHA-256 on ingestion)                      |
|  - Court Report Dispatcher (PDF / Plain-Text Streams)                           |
+-------------------+------------------------------------+-------------------------+
                    |                                    |
+-------------------v------------------+  +--------------v-------------------------+
|     OFF-CHAIN EVIDENCE STORAGE       |  |     CRYPTOGRAPHIC LEDGER ENGINE        |
|  - Isolated File Vault (backend/uploads) |  - Sequential Hash-Linked Ledger (SQLite) |
|  - Unique Prefixed Identifiers (UUIDv4)|  - Genesis Block Anchor                   |
|  - Streaming Chunked Digesting (1MB) |  - Block Hash: H(idx|ts|eid|act|actor|p|prev)|
+-------------------+------------------+  +--------------+-------------------------+
                    |                                    |
                    +------------------+-----------------+
                                       |
+--------------------------------------v-------------------------------------------+
|                          MERKLE ACCUMULATOR MODULE                               |
|  - Binary Merkle Tree Construction: leaves = H(evidence_id : sha256)             |
|  - Logarithmic Proof Generation: get_proof(target_leaf) -> [ {sibling, pos} ]    |
|  - Independent Court Verification: verify_proof(target_leaf, proof, root)       |
+----------------------------------------------------------------------------------+
```

---

## 2. Windows 11 Quick Start Guide

### Option A: One-Click Faculty Demonstration (Automated 10-Check Audit)
Right-click `Run-Demo.ps1` and select **Run with PowerShell**, or in an elevated PowerShell terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Run-Demo.ps1
```

This script automatically:
1. Detects or initializes the virtual environment (`.venv`);
2. Installs dependencies (`pip install -r requirements.txt`);
3. Executes unit and extended integration test suites (`pytest`);
4. Launches the local Flask API service;
5. Performs the 10-step automated faculty demonstration (`scripts/run_demo.py`);
6. Performs a controlled tamper test on a demo upload and verifies detection;
7. Restores exact original bytes and validates blockchain continuity;
8. Generates `faculty_demo_report.html` and `faculty_demo_results.json`.

---

### Option B: Launch Full Interactive Web Dashboard
To launch the full web application and open the browser:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Start-ForensicLedger.ps1
```

Then open your browser to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

#### Demo Accounts Pre-Configured:
| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `investigator_a` | `password123` | `investigator` | Lead Case Investigator (evidence registration & transfers) |
| `investigator_b` | `password123` | `investigator` | Secondary Investigator |
| `analyst_a` | `password123` | `analyst` | Forensic Laboratory Analyst |
| `supervisor_a` | `password123` | `supervisor` | Case Supervisor (full audit log & ledger verification access) |
| `admin` | `password123` | `supervisor` | System Administrator |

---

### Option C: Manual Setup (CLI / VS Code)

```powershell
# 1. Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run complete test suite (11 unit & extended tests)
pytest -v tests/

# 4. Run real performance benchmarks & generate research figures
python experiments/run_experiments.py

# 5. Start API & Dashboard server
python backend/app.py
```

---

## 3. Comprehensive REST API Reference

All requests accept and return `application/json` unless otherwise specified. Endpoints requiring authentication accept a standard `Authorization: Bearer <token>` header.

### Authentication & Users
| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/auth/login` | None | Authenticates credentials; returns `{token, user_id, role, expires_in}`. |
| `GET` | `/api/auth/me` | Bearer | Validates active JWT session and returns `{user_id, role}`. |
| `GET` | `/api/users` | None | Lists registered users and roles (for transfer selection). |

### Evidence Management & Custody
| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/evidence/register` | Opt. | Multipart file upload (`file`, `actor`). Computes SHA-256, writes off-chain, and anchors a `REGISTER` block. |
| `POST` | `/api/evidence/upload` | Opt. | Alias route for evidence upload. |
| `GET` | `/api/evidence` | None | Lists all registered evidence items sorted by registration time. |
| `GET` | `/api/evidence/<eid>` | None | Retrieves detailed metadata for specific evidence ID. |
| `POST` | `/api/evidence/verify/<eid>` | None | Re-hashes stored file from disk; checks against database hash; records event in audit log. |
| `POST` | `/api/custody/transfer` | Opt. | Transfers custody (`evidence_id`, `new_custodian`, `reason`); records transfer block. |
| `POST` | `/api/evidence/<eid>/transfer` | Opt. | Alias route for custody transfer. |
| `GET` | `/api/evidence/<eid>/history` | None | Returns merged custody transfers and blockchain entries for the evidence ID. |
| `GET` | `/api/evidence/<eid>/custody` | None | Returns custody transfer records for the evidence ID. |
| `GET` | `/api/evidence/<eid>/report` | None | Generates and downloads a court-ready PDF (`?format=pdf`) or plain-text (`?format=txt`) report. |

### Blockchain & Merkle Verification
| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/ledger` | None | Retrieves entire block sequence from Genesis. |
| `GET` | `/api/ledger/validate` | None | Validates chain hashes, previous hashes, and sequential indices. |
| `GET` | `/api/merkle/root` | None | Computes and returns the root of the Merkle accumulator. |
| `GET` | `/api/evidence/<eid>/merkle-proof` | None | Returns Merkle inclusion proof for the specific item with verification status. |

### Auditing & Performance
| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/audit` | None | Paginated system audit logs (`?page=1&per_page=20&evidence_id=...`). |
| `GET` | `/api/audit_logs` | None | Alias route for audit log retrieval. |
| `POST` | `/api/experiment/benchmark` | None | Live SHA-256 speed benchmark across custom payload sizes. |

---

## 4. Empirical Evaluation & Research Benchmarks

Benchmarks were performed directly on realistic file size distributions reflecting the **Digital Corpora Govdocs1** profile:

| Metric | Measured Value | Analysis |
| :--- | :---: | :--- |
| **Peak SHA-256 Throughput** | **855.96 MB/s** | Sustained streaming rate for files $\ge 1\text{ MB}$. |
| **Evidence Registration Latency** | **20.69 ms / item** | Ingests ~48 files/sec including full disk write and block anchoring. |
| **Single-Item Verification** | **13.38 ms** | Fast stream validation from storage vault. |
| **Merkle Tree Construction (1,000 leaves)** | **2.44 ms** | Linear $O(N)$ accumulation in memory. |
| **Merkle Proof Verification (1,000 leaves)** | **0.028 ms** | Logarithmic $O(\log N)$ cryptographic path reconstruction. |
| **Merkle vs. Linear Scan Speedup** | **Up to 71.0× Speedup** | Dramatic efficiency gain over sequential block traversal. |
| **Tampering Detection Sensitivity** | **100% ($F_1 = 1.000$)** | Detected every single-byte adversarial file mutation ($TP=10, FP=0, TN=10, FN=0$). |

Generated experimental graphs and data tables are located in:
- `experiments/results/fig1_sha256.png`
- `experiments/results/fig2_registration.png`
- `experiments/results/fig3_merkle.png`
- `experiments/results/fig4_tampering.png`
- `experiments/results/fig5_baseline_comparison.png`
- `experiments/results/results.json` and accompanying CSVs.

The complete academic manuscript is available in:
**`research/ForensicLedger_Research_Paper.md`**

---

## 5. Security and Integrity Guarantees

1. **Storage Integrity:** Evidence bytes are decoupled from metadata. Modifying even 1 byte of an uploaded evidence file immediately causes a SHA-256 digest mismatch upon verification.
2. **Ledger Integrity:** Every custody change or registration appends an immutable block. Altering a past block invalidates all downstream block hashes and causes `/api/ledger/validate` to pinpoint the exact corrupted index.
3. **Merkle Proofs for Court Admissibility:** Merkle inclusion proofs allow defense and prosecution experts to prove an item's registration in a master batch without disclosing hashes or metadata of other unrelated cases.
4. **Court-Ready PDF Reports:** One-click download of legally formatted chain-of-custody reports certified with exact timestamps, previous custodians, reasons, and block hashes.
