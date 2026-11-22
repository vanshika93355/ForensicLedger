"""
run_experiments.py — ForensicLedger Performance Benchmarks
===========================================================
Runs five real (no fabricated data) experiments and saves results as
JSON, CSV, and matplotlib figures.

Usage
-----
  # standalone:
  python experiments/run_experiments.py

  # from another module:
  from experiments.run_experiments import run_all_experiments
  results = run_all_experiments()
"""

# ---------------------------------------------------------------------------
# Standard-library imports (always available)
# ---------------------------------------------------------------------------
import hashlib
import time
import os
import json
import random
import sys
import statistics
import csv
import io
import importlib.util
import tempfile
import uuid
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional: matplotlib
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend – safe everywhere
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    _MPL = True
except ImportError:
    try:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "matplotlib", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        _MPL = True
    except Exception:
        _MPL = False

# ---------------------------------------------------------------------------
# Path setup – works whether the script is run from the repo root or from
# within the experiments/ folder.
# ---------------------------------------------------------------------------
_SCRIPT_DIR  = Path(__file__).resolve().parent          # …/experiments/
_REPO_ROOT   = _SCRIPT_DIR.parent                       # …/ForensicLedger/
_BACKEND_DIR = _REPO_ROOT / "backend"
_RESULTS_DIR = _SCRIPT_DIR / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Add backend to sys.path so we can import app / merkle directly
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ===========================================================================
# HELPERS
# ===========================================================================

def _random_sha256() -> str:
    """Return a random 64-char hex string (simulates a SHA-256 hash leaf)."""
    return hashlib.sha256(random.getrandbits(256).to_bytes(32, "big")).hexdigest()


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _fmt_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms * 1000:.2f} µs"
    if ms < 1000:
        return f"{ms:.3f} ms"
    return f"{ms / 1000:.3f} s"


def _print_separator(char: str = "─", width: int = 72) -> None:
    print(char * width)


def _print_header(title: str) -> None:
    _print_separator("═")
    print(f"  {title}")
    _print_separator("═")


def _save_json(data: dict, filename: str) -> None:
    path = _RESULTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  [JSON] Saved → {path}")


def _save_csv(rows: list[dict], filename: str) -> None:
    if not rows:
        return
    path = _RESULTS_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [CSV]  Saved → {path}")


# ===========================================================================
# EXPERIMENT 1 — SHA-256 Hashing Performance
# ===========================================================================

def experiment_sha256(
    sizes_kb: list[int] | None = None,
    iterations: int = 5,
) -> dict:
    """
    Measure SHA-256 hashing time for various file sizes.

    Returns a dict with key 'sha256' mapping to a list of per-size records.
    """
    if sizes_kb is None:
        sizes_kb = [1, 10, 100, 1024, 10240, 102400]

    _print_header("Experiment 1 · SHA-256 Hashing Performance")
    print(f"  Sizes (KB): {sizes_kb}  |  Iterations per size: {iterations}\n")

    header = f"{'Size (KB)':>12}  {'Mean (ms)':>12}  {'Min (ms)':>12}  {'Max (ms)':>12}  {'StdDev (ms)':>12}"
    print(header)
    _print_separator()

    records = []
    for size_kb in sizes_kb:
        byte_count = size_kb * 1024
        timings_ms: list[float] = []
        for _ in range(iterations):
            payload = random.randbytes(byte_count)
            t0 = time.perf_counter()
            hashlib.sha256(payload).hexdigest()
            t1 = time.perf_counter()
            timings_ms.append((t1 - t0) * 1000.0)

        mean_ms  = statistics.mean(timings_ms)
        min_ms   = min(timings_ms)
        max_ms   = max(timings_ms)
        stdev_ms = statistics.stdev(timings_ms) if len(timings_ms) > 1 else 0.0

        print(
            f"  {size_kb:>10,} KB  "
            f"{mean_ms:>12.4f}  "
            f"{min_ms:>12.4f}  "
            f"{max_ms:>12.4f}  "
            f"{stdev_ms:>12.4f}"
        )
        records.append(
            {
                "size_kb":     size_kb,
                "size_bytes":  byte_count,
                "iterations":  iterations,
                "mean_ms":     round(mean_ms,  6),
                "min_ms":      round(min_ms,   6),
                "max_ms":      round(max_ms,   6),
                "stdev_ms":    round(stdev_ms, 6),
                "throughput_mb_per_s": round(
                    (byte_count / (1024 * 1024)) / (mean_ms / 1000), 3
                ) if mean_ms > 0 else 0,
            }
        )

    _print_separator()
    print()
    _save_csv(records, "benchmark_sha256.csv")
    return {"sha256": records}


# ===========================================================================
# EXPERIMENT 2 — Evidence Registration Performance (Flask test client)
# ===========================================================================

def _build_flask_test_client():
    """
    Import app.py from the backend directory and return a Flask test client
    backed by an isolated temporary SQLite database so the experiments do
    not pollute the real database.
    """
    # Explicitly import the sub-module that is needed
    import importlib.util as _iutil

    # ------------------------------------------------------------------
    # Temporary directories / files for this test run
    # ------------------------------------------------------------------
    _tmp_uploads = tempfile.mkdtemp(prefix="fl_exp_uploads_")
    _tmp_db_file = os.path.join(tempfile.gettempdir(), f"fl_exp_{uuid.uuid4().hex}.db")

    # ------------------------------------------------------------------
    # Load backend/app.py under a unique module name so repeated calls
    # do not collide with any previously-cached import.
    # ------------------------------------------------------------------
    spec = _iutil.spec_from_file_location(
        f"backend_app_exp_{uuid.uuid4().hex[:8]}",
        str(_BACKEND_DIR / "app.py"),
    )
    mod = _iutil.module_from_spec(spec)

    # Insert into sys.modules so intra-module imports (merkle, auth) work
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    # Redirect DB and UPLOADS *after* exec_module so we override the
    # paths set by the top-level code in app.py, then re-run init().
    mod.DB      = Path(_tmp_db_file)
    mod.UPLOADS = Path(_tmp_uploads)
    mod.UPLOADS.mkdir(exist_ok=True)
    mod.init()

    client  = mod.app.test_client()

    def cleanup():
        shutil.rmtree(_tmp_uploads, ignore_errors=True)
        try:
            if os.path.exists(_tmp_db_file):
                os.unlink(_tmp_db_file)
        except OSError:
            pass
        sys.modules.pop(spec.name, None)

    return client, mod, cleanup


def experiment_registration(
    batch_sizes: list[int] | None = None,
) -> dict:
    """
    Measure wall-clock time for registering batches of evidence items.

    Returns a dict with key 'registration'.
    """
    if batch_sizes is None:
        batch_sizes = [1, 10, 25, 50, 100]

    _print_header("Experiment 2 · Evidence Registration Performance")

    try:
        client, mod, cleanup = _build_flask_test_client()
    except Exception as exc:
        print(f"  [WARN] Could not start Flask test client: {exc}")
        print("         Skipping Experiment 2 & 3.\n")
        return {"registration": [], "registered_ids": []}

    print(f"  Batch sizes: {batch_sizes}\n")
    header = f"{'Items':>8}  {'Total (ms)':>14}  {'Per-item (ms)':>16}"
    print(header)
    _print_separator()

    records        = []
    registered_ids = []          # kept for Experiment 3

    for n in batch_sizes:
        batch_ids: list[str] = []
        t_start = time.perf_counter()
        for i in range(n):
            fake_content = random.randbytes(random.randint(512, 4096))
            data = io.BytesIO(fake_content)
            resp = client.post(
                "/api/evidence/register",
                data={
                    "file":  (data, f"evidence_{i:04d}.txt"),
                    "actor": "investigator_a",
                },
                content_type="multipart/form-data",
            )
            if resp.status_code == 201:
                batch_ids.append(resp.get_json()["evidence_id"])
        t_end = time.perf_counter()

        total_ms    = (t_end - t_start) * 1000.0
        per_item_ms = total_ms / n if n else 0

        print(f"  {n:>8}  {total_ms:>14.2f}  {per_item_ms:>16.4f}")
        records.append(
            {
                "batch_size":    n,
                "registered":    len(batch_ids),
                "total_ms":      round(total_ms,    4),
                "per_item_ms":   round(per_item_ms, 4),
            }
        )
        registered_ids.extend(batch_ids)

    _print_separator()
    print()
    _save_csv(records, "benchmark_registration.csv")
    return {
        "registration":    records,
        "registered_ids":  registered_ids,
        "_client":         client,
        "_cleanup":        cleanup,
    }


# ===========================================================================
# EXPERIMENT 3 — Verification Performance
# ===========================================================================

def experiment_verification(
    client,
    registered_ids: list[str],
) -> dict:
    """
    Measure per-item verification time for already-registered evidence.

    Returns a dict with key 'verification'.
    """
    _print_header("Experiment 3 · Verification Performance")

    if not registered_ids:
        print("  [SKIP] No registered IDs available from Experiment 2.\n")
        return {"verification": []}

    # Sample up to 50 IDs to keep the benchmark manageable
    sample = registered_ids[:50]
    print(f"  Verifying {len(sample)} items (sample from registered pool)\n")

    timings_ms: list[float] = []
    statuses:   list[bool]  = []
    records:    list[dict]  = []

    for eid in sample:
        t0   = time.perf_counter()
        resp = client.post(f"/api/evidence/verify/{eid}")
        t1   = time.perf_counter()
        ms   = (t1 - t0) * 1000.0
        verified = resp.get_json().get("verified", False) if resp.status_code == 200 else False
        timings_ms.append(ms)
        statuses.append(verified)
        records.append({"evidence_id": eid, "verify_ms": round(ms, 4), "verified": verified})

    mean_ms  = statistics.mean(timings_ms)
    min_ms   = min(timings_ms)
    max_ms   = max(timings_ms)
    stdev_ms = statistics.stdev(timings_ms) if len(timings_ms) > 1 else 0.0

    print(f"  Items verified : {len(sample)}")
    print(f"  All intact     : {all(statuses)}")
    print(f"  Mean time      : {mean_ms:.4f} ms")
    print(f"  Min  time      : {min_ms:.4f} ms")
    print(f"  Max  time      : {max_ms:.4f} ms")
    print(f"  StdDev         : {stdev_ms:.4f} ms")
    print()

    _save_csv(records, "benchmark_verification.csv")
    return {
        "verification": {
            "count":    len(sample),
            "mean_ms":  round(mean_ms,  4),
            "min_ms":   round(min_ms,   4),
            "max_ms":   round(max_ms,   4),
            "stdev_ms": round(stdev_ms, 4),
            "all_intact": all(statuses),
        },
        "verification_detail": records,
    }


# ===========================================================================
# EXPERIMENT 4 — Merkle Tree Performance
# ===========================================================================

def experiment_merkle(
    leaf_counts: list[int] | None = None,
) -> dict:
    """
    Benchmark Merkle tree construction, proof generation, and proof verification.

    Returns a dict with key 'merkle'.
    """
    if leaf_counts is None:
        leaf_counts = [1, 10, 50, 100, 500, 1000]

    _print_header("Experiment 4 · Merkle Tree Performance")

    # Try to import MerkleTree from the backend; fall back to a local impl.
    try:
        from merkle import MerkleTree
        _has_merkle = True
        print("  Using backend/merkle.py MerkleTree")
    except ImportError:
        _has_merkle = False
        print("  [WARN] merkle.py not importable – using built-in fallback")

    class _FallbackMerkle:
        """Minimal Merkle tree used only when merkle.py is unavailable."""

        def __init__(self, leaves: list[str]) -> None:
            self._leaves = list(leaves)
            self._layers: list[list[str]] = []
            if leaves:
                self._build()

        def _build(self) -> None:
            layer = list(self._leaves)
            self._layers = [layer]
            while len(layer) > 1:
                if len(layer) % 2:
                    layer = layer + [layer[-1]]
                layer = [
                    hashlib.sha256((layer[i] + layer[i + 1]).encode()).hexdigest()
                    for i in range(0, len(layer), 2)
                ]
                self._layers.append(layer)

        @property
        def root(self) -> str | None:
            return self._layers[-1][0] if self._layers else None

        def get_proof(self, leaf_hash: str) -> list[dict]:
            if not self._layers or leaf_hash not in self._layers[0]:
                return []
            proof: list[dict] = []
            idx = self._layers[0].index(leaf_hash)
            for layer in self._layers[:-1]:
                padded = layer if len(layer) % 2 == 0 else layer + [layer[-1]]
                sib_idx = idx ^ 1
                position = "right" if idx % 2 == 0 else "left"
                proof.append({"sibling": padded[sib_idx], "position": position})
                idx //= 2
            return proof

        @staticmethod
        def verify_proof(leaf: str, proof: list[dict], root: str) -> bool:
            cur = leaf
            for step in proof:
                sib = step["sibling"]
                if step["position"] == "left":
                    cur = hashlib.sha256((sib + cur).encode()).hexdigest()
                else:
                    cur = hashlib.sha256((cur + sib).encode()).hexdigest()
            return cur == root

    _Tree = MerkleTree if _has_merkle else _FallbackMerkle

    print(f"\n  Leaf counts: {leaf_counts}\n")
    header = (
        f"{'Leaves':>8}  {'Build (ms)':>12}  {'Proof Gen (ms)':>16}  "
        f"{'Proof Verify (ms)':>18}  {'Root (hex prefix)':>20}"
    )
    print(header)
    _print_separator()

    records: list[dict] = []

    for n in leaf_counts:
        leaves = [_random_sha256() for _ in range(n)]
        target = random.choice(leaves)

        # --- Build ---
        t0    = time.perf_counter()
        tree  = _Tree(leaves)
        t_build = (time.perf_counter() - t0) * 1000.0

        root_val = tree.root or ""

        # --- Proof generation ---
        t0    = time.perf_counter()
        proof = tree.get_proof(target)
        t_proof_gen = (time.perf_counter() - t0) * 1000.0

        # --- Proof verification ---
        t0 = time.perf_counter()
        ok = _Tree.verify_proof(target, proof, root_val)
        t_proof_ver = (time.perf_counter() - t0) * 1000.0

        root_prefix = root_val[:16] + "…" if root_val else "(empty)"
        print(
            f"  {n:>8}  "
            f"{t_build:>12.4f}  "
            f"{t_proof_gen:>16.4f}  "
            f"{t_proof_ver:>18.4f}  "
            f"  {root_prefix}"
        )
        records.append(
            {
                "leaf_count":       n,
                "build_ms":         round(t_build,     6),
                "proof_gen_ms":     round(t_proof_gen, 6),
                "proof_verify_ms":  round(t_proof_ver, 6),
                "proof_valid":      ok,
                "root_prefix":      root_val[:16],
            }
        )

    _print_separator()
    print()
    _save_csv(records, "benchmark_merkle.csv")
    return {"merkle": records}


# ===========================================================================
# EXPERIMENT 5 — Tampering Detection Accuracy
# ===========================================================================

def experiment_tampering(
    n_items:   int = 20,
    n_tamper:  int = 10,
) -> dict:
    """
    Register *n_items* evidence files; tamper *n_tamper* of them directly on
    disk; then verify all items and compute confusion-matrix metrics.

    Returns a dict with key 'tampering'.
    """
    _print_header("Experiment 5 · Tampering Detection Accuracy")
    print(f"  Items registered : {n_items}  |  Items tampered : {n_tamper}\n")

    try:
        client, mod, cleanup = _build_flask_test_client()
    except Exception as exc:
        print(f"  [WARN] Could not start Flask test client: {exc}")
        print("         Skipping Experiment 5.\n")
        return {"tampering": {}}

    # --- Register n_items ---
    registered: list[dict] = []          # [{eid, stored_name, path, tampered}]
    for i in range(n_items):
        content = random.randbytes(random.randint(256, 2048))
        data    = io.BytesIO(content)
        resp    = client.post(
            "/api/evidence/register",
            data={
                "file":  (data, f"item_{i:03d}.txt"),
                "actor": "investigator_a",
            },
            content_type="multipart/form-data",
        )
        if resp.status_code == 201:
            info = resp.get_json()
            # Locate file on disk: stored as EID_filename inside mod.UPLOADS
            stored_name = info["evidence_id"] + "_item_" + f"{i:03d}.txt"
            # Find actual stored filename by scanning the upload dir
            upload_dir = Path(mod.UPLOADS)
            matches = list(upload_dir.glob(f"{info['evidence_id']}_*"))
            disk_path = matches[0] if matches else None
            registered.append(
                {
                    "eid":        info["evidence_id"],
                    "disk_path":  disk_path,
                    "tampered":   False,
                }
            )

    if len(registered) < n_items:
        print(f"  [WARN] Only {len(registered)}/{n_items} items registered successfully.")

    # --- Tamper n_tamper items (pick at random) ---
    tamper_pool = [r for r in registered if r["disk_path"] and r["disk_path"].exists()]
    tamper_set  = random.sample(tamper_pool, min(n_tamper, len(tamper_pool)))
    for item in tamper_set:
        path: Path = item["disk_path"]
        original   = path.read_bytes()
        # Flip a random byte somewhere in the file
        pos         = random.randint(0, max(0, len(original) - 1))
        ba          = bytearray(original)
        ba[pos]     = (ba[pos] + 1) % 256
        path.write_bytes(bytes(ba))
        item["tampered"] = True

    # --- Verify all items ---
    tampered_set_eids = {r["eid"] for r in tamper_set}
    TP = TN = FP = FN = 0
    detail_records: list[dict] = []

    for item in registered:
        resp       = client.post(f"/api/evidence/verify/{item['eid']}")
        if resp.status_code != 200:
            continue
        result     = resp.get_json()
        detected   = not result.get("verified", True)   # True  → integrity failed
        ground_truth_tampered = item["tampered"]

        if detected and ground_truth_tampered:
            TP += 1; label = "TP"
        elif not detected and not ground_truth_tampered:
            TN += 1; label = "TN"
        elif detected and not ground_truth_tampered:
            FP += 1; label = "FP"
        else:
            FN += 1; label = "FN"

        detail_records.append(
            {
                "evidence_id":       item["eid"],
                "actually_tampered": ground_truth_tampered,
                "detected_tampered": detected,
                "outcome":           label,
            }
        )

    total     = TP + TN + FP + FN
    accuracy  = (TP + TN) / total if total else 0
    precision = TP / (TP + FP)   if (TP + FP) else 0
    recall    = TP / (TP + FN)   if (TP + FN) else 0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0)

    print(f"  Confusion Matrix:")
    print(f"    TP={TP}  FP={FP}")
    print(f"    FN={FN}  TN={TN}")
    print(f"  Accuracy  : {accuracy:.4f}")
    print(f"  Precision : {precision:.4f}")
    print(f"  Recall    : {recall:.4f}")
    print(f"  F1-Score  : {f1:.4f}")
    print()

    _save_csv(detail_records, "benchmark_tampering.csv")
    cleanup()

    result_dict = {
        "n_items":    n_items,
        "n_tampered": n_tamper,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "accuracy":  round(accuracy,  4),
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1_score":  round(f1,        4),
    }
    return {"tampering": result_dict}


# ===========================================================================
# EXPERIMENT 6 — Comparative Baseline (Merkle Proof vs. Linear Scan)
# ===========================================================================

def experiment_baseline(
    counts: list[int] | None = None,
    iterations: int = 25,
) -> dict:
    """
    Compare Merkle inclusion proof verification against a linear scan baseline.
    Baseline: O(N) linear traversal through blocks to confirm leaf existence.
    Merkle:   O(log N) cryptographic proof verification against root hash.
    """
    if counts is None:
        counts = [10, 50, 100, 500, 1000, 2500, 5000]

    _print_header("Experiment 6 · Merkle Proof vs Linear Scan Baseline")
    print(f"  Evidence volumes: {counts}  |  Iterations: {iterations}\n")

    try:
        from merkle import MerkleTree
    except ImportError:
        from backend.merkle import MerkleTree

    header = f"{'Evidence N':>12}  {'Linear Scan (ms)':>18}  {'Merkle Proof (ms)':>18}  {'Speedup Factor':>16}"
    print(header)
    _print_separator()

    records = []
    for n in counts:
        leaves = [_random_sha256() for _ in range(n)]
        target = random.choice(leaves)
        tree = MerkleTree(leaves)
        proof = tree.get_proof(target)
        root = tree.root

        # Benchmark Linear Blockchain Scan Baseline:
        # Verifier must walk blocks, verify each block's cryptographic hash, and check payload
        blocks = [
            {"idx": i, "payload": json.dumps({"sha256": l, "filename": f"ev_{i}.txt"}), "prev": "0"*64}
            for i, l in enumerate(leaves)
        ]
        linear_times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            found = False
            for blk in blocks:
                # Recompute block hash as required during blockchain traversal
                b_hash = hashlib.sha256((str(blk["idx"]) + blk["payload"] + blk["prev"]).encode()).hexdigest()
                if target in blk["payload"]:
                    found = True
                    break
            t1 = time.perf_counter()
            linear_times.append((t1 - t0) * 1000.0)
        linear_ms = statistics.mean(linear_times)

        # Benchmark Merkle Proof Verification:
        merkle_times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            ok = MerkleTree.verify_proof(target, proof, root)
            t1 = time.perf_counter()
            merkle_times.append((t1 - t0) * 1000.0)
        merkle_ms = statistics.mean(merkle_times)

        speedup = (linear_ms / merkle_ms) if merkle_ms > 0 else 1.0
        print(f"  {n:>12}  {linear_ms:>18.6f}  {merkle_ms:>18.6f}  {speedup:>15.2f}x")

        records.append({
            "evidence_count": n,
            "linear_scan_ms": round(linear_ms, 6),
            "merkle_proof_ms": round(merkle_ms, 6),
            "speedup_factor": round(speedup, 2)
        })

    _print_separator()
    print()
    _save_csv(records, "benchmark_baseline.csv")
    return {"baseline_comparison": records}


# ===========================================================================
# GRAPH GENERATION
# ===========================================================================

def generate_graphs(all_results: dict) -> None:
    """Generate and save all benchmark figures (requires matplotlib)."""
    if not _MPL:
        print("  [SKIP] matplotlib not available – skipping graph generation.\n")
        return

    _print_header("Generating Graphs")

    # ── Figure 1: SHA-256 time vs file size (log-x line chart) ────────────
    sha_data = all_results.get("sha256", [])
    if sha_data:
        sizes  = [r["size_kb"]  for r in sha_data]
        means  = [r["mean_ms"]  for r in sha_data]
        mins   = [r["min_ms"]   for r in sha_data]
        maxs   = [r["max_ms"]   for r in sha_data]
        stdevs = [r["stdev_ms"] for r in sha_data]

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(sizes, means, "o-", linewidth=2, color="#2563EB", label="Mean")
        ax.fill_between(sizes, mins, maxs, alpha=0.2, color="#2563EB", label="Min–Max range")
        ax.errorbar(sizes, means, yerr=stdevs, fmt="none", ecolor="#1D4ED8",
                    capsize=4, alpha=0.6, label="±1 StdDev")
        ax.set_xscale("log")
        ax.set_xlabel("File Size (KB) — log scale", fontsize=12)
        ax.set_ylabel("SHA-256 Time (ms)", fontsize=12)
        ax.set_title("SHA-256 Hashing Performance vs File Size", fontsize=14, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
        ax.set_xticks(sizes)
        ax.set_xticklabels([f"{s:,}" for s in sizes], rotation=30, ha="right")
        fig.tight_layout()
        out = _RESULTS_DIR / "fig1_sha256.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  [FIG1] Saved → {out}")

    # ── Figure 2: Registration time vs evidence count (bar chart) ─────────
    reg_data = all_results.get("registration", [])
    if reg_data:
        batches  = [r["batch_size"]  for r in reg_data]
        totals   = [r["total_ms"]    for r in reg_data]
        per_item = [r["per_item_ms"] for r in reg_data]

        x       = range(len(batches))
        width   = 0.38
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax2      = ax1.twinx()

        bars1 = ax1.bar([i - width / 2 for i in x], totals,   width=width,
                        color="#10B981", alpha=0.85, label="Total time (ms)")
        bars2 = ax2.bar([i + width / 2 for i in x], per_item, width=width,
                        color="#F59E0B", alpha=0.85, label="Per-item time (ms)")

        ax1.set_xlabel("Batch Size (number of evidence items)", fontsize=12)
        ax1.set_ylabel("Total Registration Time (ms)", fontsize=12, color="#10B981")
        ax2.set_ylabel("Per-item Time (ms)",            fontsize=12, color="#F59E0B")
        ax1.set_title("Evidence Registration Performance", fontsize=14, fontweight="bold")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([str(b) for b in batches])
        ax1.tick_params(axis="y", labelcolor="#10B981")
        ax2.tick_params(axis="y", labelcolor="#F59E0B")
        ax1.legend(loc="upper left",  fontsize=10)
        ax2.legend(loc="upper right", fontsize=10)
        ax1.grid(True, axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        out = _RESULTS_DIR / "fig2_registration.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  [FIG2] Saved → {out}")

    # ── Figure 3: Merkle tree build time vs leaf count (line chart) ────────
    mkl_data = all_results.get("merkle", [])
    if mkl_data:
        leaves   = [r["leaf_count"]      for r in mkl_data]
        builds   = [r["build_ms"]        for r in mkl_data]
        proofs_g = [r["proof_gen_ms"]    for r in mkl_data]
        proofs_v = [r["proof_verify_ms"] for r in mkl_data]

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(leaves, builds,   "o-", linewidth=2, color="#8B5CF6", label="Build time")
        ax.plot(leaves, proofs_g, "s--", linewidth=2, color="#EC4899", label="Proof generation")
        ax.plot(leaves, proofs_v, "^:", linewidth=2, color="#06B6D4", label="Proof verification")
        ax.set_xlabel("Number of Leaves", fontsize=12)
        ax.set_ylabel("Time (ms)", fontsize=12)
        ax.set_title("Merkle Tree Performance vs Leaf Count", fontsize=14, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.set_xticks(leaves)
        ax.set_xticklabels([str(l) for l in leaves])
        fig.tight_layout()
        out = _RESULTS_DIR / "fig3_merkle.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  [FIG3] Saved → {out}")

    # ── Figure 4: Tampering detection confusion matrix ─────────────────────
    tamp = all_results.get("tampering", {})
    if tamp:
        TP = tamp.get("TP", 0)
        FP = tamp.get("FP", 0)
        FN = tamp.get("FN", 0)
        TN = tamp.get("TN", 0)

        matrix    = [[TP, FP], [FN, TN]]
        row_labels = ["Tampered (actual)", "Intact (actual)"]
        col_labels = ["Tampered (detected)", "Intact (detected)"]
        colors     = [["#F87171", "#FDE68A"], ["#FDE68A", "#6EE7B7"]]

        fig, ax = plt.subplots(figsize=(6, 5))
        for r in range(2):
            for c in range(2):
                val = matrix[r][c]
                ax.add_patch(plt.Rectangle((c, 1 - r), 1, 1,
                                           facecolor=colors[r][c], edgecolor="white", linewidth=2))
                label = ["TP", "FP", "FN", "TN"][r * 2 + c]
                ax.text(c + 0.5, 1.5 - r, f"{label}\n{val}",
                        ha="center", va="center", fontsize=16, fontweight="bold")

        ax.set_xlim(0, 2)
        ax.set_ylim(0, 2)
        ax.set_xticks([0.5, 1.5])
        ax.set_xticklabels(col_labels, fontsize=11)
        ax.set_yticks([0.5, 1.5])
        ax.set_yticklabels(row_labels[::-1], fontsize=11)
        ax.xaxis.set_ticks_position("top")
        ax.xaxis.set_label_position("top")
        ax.set_title(
            f"Tampering Detection · Accuracy={tamp['accuracy']:.2%}  "
            f"F1={tamp['f1_score']:.2%}",
            fontsize=12, fontweight="bold", pad=14,
        )
        fig.tight_layout()
        out = _RESULTS_DIR / "fig4_tampering.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  [FIG4] Saved → {out}")

    # ── Figure 5: Baseline Comparison (Merkle vs Linear Scan) ───────────
    base_data = all_results.get("baseline_comparison", [])
    if base_data:
        counts = [r["evidence_count"] for r in base_data]
        linear_t = [r["linear_scan_ms"] for r in base_data]
        merkle_t = [r["merkle_proof_ms"] for r in base_data]
        speedups = [r["speedup_factor"] for r in base_data]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

        # Subplot 1: Latency Comparison
        ax1.plot(counts, linear_t, "o-", color="#EF4444", linewidth=2, label="Linear Scan Baseline O(N)")
        ax1.plot(counts, merkle_t, "s-", color="#10B981", linewidth=2, label="Merkle Proof O(log N)")
        ax1.set_xlabel("Evidence Records (N)", fontsize=11)
        ax1.set_ylabel("Verification Latency (ms)", fontsize=11)
        ax1.set_title("Verification Latency: Merkle vs Baseline", fontsize=12, fontweight="bold")
        ax1.legend(fontsize=10)
        ax1.grid(True, linestyle="--", alpha=0.5)

        # Subplot 2: Speedup Factor
        ax2.bar([str(c) for c in counts], speedups, color="#0EA5E9", alpha=0.85)
        ax2.set_xlabel("Evidence Records (N)", fontsize=11)
        ax2.set_ylabel("Speedup Factor (x)", fontsize=11)
        ax2.set_title("Merkle Verification Speedup over Linear Scan", fontsize=12, fontweight="bold")
        for i, v in enumerate(speedups):
            ax2.text(i, v + (max(speedups) * 0.02), f"{v:.1f}x", ha="center", fontsize=9, fontweight="bold")
        ax2.grid(True, axis="y", linestyle="--", alpha=0.5)

        fig.tight_layout()
        out = _RESULTS_DIR / "fig5_baseline_comparison.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  [FIG5] Saved → {out}")

    print()


# ===========================================================================
# SUMMARY TABLE
# ===========================================================================

def print_summary(all_results: dict) -> None:
    """Print a formatted multi-section summary table to stdout."""
    _print_header("SUMMARY")

    # SHA-256
    sha_data = all_results.get("sha256", [])
    if sha_data:
        print("  ┌─ SHA-256 Hashing ─────────────────────────────────────────────────┐")
        print(f"  │  {'Size (KB)':>10}  {'Mean (ms)':>12}  {'Throughput (MB/s)':>18}  │")
        print(f"  │  {'─'*10}  {'─'*12}  {'─'*18}  │")
        for r in sha_data:
            print(
                f"  │  {r['size_kb']:>10,}  {r['mean_ms']:>12.4f}  "
                f"{r['throughput_mb_per_s']:>18.2f}  │"
            )
        print("  └───────────────────────────────────────────────────────────────────┘\n")

    # Registration
    reg_data = all_results.get("registration", [])
    if reg_data:
        print("  ┌─ Evidence Registration ────────────────────────────────────────────┐")
        print(f"  │  {'Batch':>8}  {'Total (ms)':>12}  {'Per-item (ms)':>16}  {'Registered':>10}  │")
        print(f"  │  {'─'*8}  {'─'*12}  {'─'*16}  {'─'*10}  │")
        for r in reg_data:
            print(
                f"  │  {r['batch_size']:>8}  {r['total_ms']:>12.2f}  "
                f"{r['per_item_ms']:>16.4f}  {r['registered']:>10}  │"
            )
        print("  └────────────────────────────────────────────────────────────────────┘\n")

    # Verification
    ver_data = all_results.get("verification", {})
    if ver_data:
        print("  ┌─ Verification Performance ────────────────────────────────────────┐")
        print(f"  │  Items sampled : {ver_data.get('count', 0):<10}  All intact : {str(ver_data.get('all_intact', '?')):<6}         │")
        print(f"  │  Mean : {ver_data.get('mean_ms',0):.4f} ms   Min : {ver_data.get('min_ms',0):.4f} ms   Max : {ver_data.get('max_ms',0):.4f} ms   │")
        print("  └───────────────────────────────────────────────────────────────────┘\n")

    # Merkle
    mkl_data = all_results.get("merkle", [])
    if mkl_data:
        print("  ┌─ Merkle Tree ─────────────────────────────────────────────────────┐")
        print(f"  │  {'Leaves':>8}  {'Build (ms)':>12}  {'Proof Gen':>12}  {'Proof Verify':>14}  │")
        print(f"  │  {'─'*8}  {'─'*12}  {'─'*12}  {'─'*14}  │")
        for r in mkl_data:
            print(
                f"  │  {r['leaf_count']:>8}  {r['build_ms']:>12.4f}  "
                f"{r['proof_gen_ms']:>12.4f}  {r['proof_verify_ms']:>14.4f}  │"
            )
        print("  └───────────────────────────────────────────────────────────────────┘\n")

    # Tampering
    tamp = all_results.get("tampering", {})
    if tamp:
        print("  ┌─ Tampering Detection ─────────────────────────────────────────────┐")
        print(f"  │  Total items : {tamp.get('n_items',0):<6}  Tampered : {tamp.get('n_tampered',0):<6}                      │")
        print(f"  │  TP={tamp.get('TP',0)}  FP={tamp.get('FP',0)}  FN={tamp.get('FN',0)}  TN={tamp.get('TN',0)}                                        │")
        print(f"  │  Accuracy={tamp.get('accuracy',0):.4f}  Precision={tamp.get('precision',0):.4f}  Recall={tamp.get('recall',0):.4f}  F1={tamp.get('f1_score',0):.4f}  │")
        print("  └───────────────────────────────────────────────────────────────────┘\n")

    # Baseline Comparison
    base_data = all_results.get("baseline_comparison", [])
    if base_data:
        print("  ┌─ Baseline Comparison (Linear Scan vs Merkle Proof) ───────────────┐")
        print(f"  │  {'Evidence (N)':>12}  {'Linear Scan':>14}  {'Merkle Proof':>14}  {'Speedup':>12}  │")
        print(f"  │  {'─'*12}  {'─'*14}  {'─'*14}  {'─'*12}  │")
        for r in base_data:
            print(
                f"  │  {r['evidence_count']:>12,}  {r['linear_scan_ms']:>11.4f} ms  "
                f"{r['merkle_proof_ms']:>11.4f} ms  {r['speedup_factor']:>10.1f}x  │"
            )
        print("  └───────────────────────────────────────────────────────────────────┘\n")


# ===========================================================================
# MAIN ENTRY POINT
# ===========================================================================

def run_all_experiments() -> dict:
    """
    Run all five experiments, save artefacts, and return a results dict.

    This is the public API – call it from other modules.
    """
    random.seed(42)          # reproducible randomness within each run

    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║          ForensicLedger – Performance Benchmark Suite               ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"  Results directory : {_RESULTS_DIR}")
    print(f"  matplotlib        : {'available ✓' if _MPL else 'NOT available – graphs skipped'}")
    print()

    all_results: dict = {}

    # ── Experiment 1 ─────────────────────────────────────────────────────
    r1 = experiment_sha256()
    all_results.update(r1)

    # ── Experiments 2 & 3 (share a Flask client) ──────────────────────────
    r2 = experiment_registration()
    client   = r2.pop("_client",  None)
    cleanup2 = r2.pop("_cleanup", None)
    all_results["registration"]   = r2.get("registration", [])
    all_results["registered_ids"] = r2.get("registered_ids", [])

    if client and all_results["registered_ids"]:
        r3 = experiment_verification(client, all_results["registered_ids"])
        all_results.update(r3)
    else:
        all_results["verification"] = {}

    if cleanup2:
        try:
            cleanup2()
        except Exception:
            pass

    # ── Experiment 4 ─────────────────────────────────────────────────────
    r4 = experiment_merkle()
    all_results.update(r4)

    # ── Experiment 5 ─────────────────────────────────────────────────────
    r5 = experiment_tampering(n_items=20, n_tamper=10)
    all_results.update(r5)

    # ── Experiment 6: Baseline Comparison ────────────────────────────────
    r6 = experiment_baseline()
    all_results.update(r6)

    # ── Persist all results as JSON ───────────────────────────────────────
    # Strip non-serialisable keys before saving
    save_data = {
        k: v for k, v in all_results.items()
        if k not in ("registered_ids",)
    }
    _save_json(save_data, "results.json")

    # ── Graphs ───────────────────────────────────────────────────────────
    generate_graphs(all_results)

    # ── Summary ──────────────────────────────────────────────────────────
    print_summary(all_results)

    _print_separator("═")
    print("  All experiments complete.")
    _print_separator("═")
    print()

    return all_results


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_all_experiments()
