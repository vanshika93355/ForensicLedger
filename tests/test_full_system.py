"""
test_full_system.py — Comprehensive End-to-End System & Stress Testing Suite
Covers all functional requirements, security policies, edge cases, role-based
permissions, file integrity tampering, ledger validation, Merkle inclusion proofs,
report generation, and persistence.
"""

import io
import os
import sys
import json
import time
import pytest
from pathlib import Path

# Ensure backend directory is in python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app as service
from merkle import MerkleTree, compute_merkle_root, digest
from auth import hash_password, verify_password, generate_token, decode_token, AuthError
import reports


@pytest.fixture
def client():
    """Flask test client connected to the application."""
    service.app.config["TESTING"] = True
    with service.app.test_client() as test_client:
        yield test_client


# ===========================================================================
# 1. AUTHENTICATION & ROLE-BASED ACCESS CONTROL (RBAC)
# ===========================================================================

def test_login_all_roles(client):
    """Test successful authentication for all 3 defined roles + admin."""
    roles = [
        ("investigator_a", "password123", "investigator"),
        ("investigator_b", "password123", "investigator"),
        ("analyst_a", "password123", "analyst"),
        ("supervisor_a", "password123", "supervisor"),
        ("admin", "password123", "supervisor"),
    ]
    for username, pwd, expected_role in roles:
        res = client.post("/api/auth/login", json={"username": username, "password": pwd})
        assert res.status_code == 200, f"Login failed for {username}"
        data = res.get_json()
        assert "token" in data
        assert data["user_id"] == username
        assert data["role"] == expected_role

        # Verify JWT token payload
        claims = decode_token(data["token"])
        assert claims["user_id"] == username
        assert claims["role"] == expected_role


def test_login_invalid_credentials(client):
    """Test login failure scenarios."""
    # Wrong password
    res = client.post("/api/auth/login", json={"username": "investigator_a", "password": "wrong_password_999"})
    assert res.status_code == 401
    assert "Invalid" in res.get_json().get("error", "")

    # Non-existent user
    res = client.post("/api/auth/login", json={"username": "ghost_user", "password": "password123"})
    assert res.status_code == 401

    # Empty payload
    res = client.post("/api/auth/login", json={})
    assert res.status_code == 400

    # Missing username or password
    res = client.post("/api/auth/login", json={"username": "investigator_a"})
    assert res.status_code == 400


def test_token_verification_and_tampering(client):
    """Test token validation and rejection of corrupted/forged tokens."""
    # Generate valid token
    tok = generate_token("investigator_a", "investigator")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 200
    assert res.get_json()["user_id"] == "investigator_a"

    # Malformed token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok[:-5]}evil"})
    assert res.status_code == 401

    # Missing Bearer prefix
    res = client.get("/api/auth/me", headers={"Authorization": tok})
    assert res.status_code == 401

    # Missing header entirely
    res = client.get("/api/auth/me")
    assert res.status_code == 401


# ===========================================================================
# 2. EVIDENCE REGISTRATION & INPUT VALIDATION
# ===========================================================================

def test_evidence_registration_valid_file(client):
    """Register evidence with valid extension and verify response."""
    test_bytes = b"Digital Forensic Evidence - Hard Drive Sector 42"
    res = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(test_bytes), "sector_42.txt"), "actor": "investigator_a"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["evidence_id"].startswith("EV-")
    assert data["filename"] == "sector_42.txt"
    assert data["size"] == len(test_bytes)
    assert data["sha256"] == digest(test_bytes)
    assert "block_hash" in data


def test_evidence_registration_disallowed_extension(client):
    """Reject unapproved executable file extensions (e.g. .exe, .sh, .bat)."""
    res = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(b"binary payload"), "malware.exe"), "actor": "investigator_a"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 400
    assert "Unsupported file type" in res.get_json().get("error", "")


def test_evidence_registration_empty_file(client):
    """Reject upload when no file is provided in multipart body."""
    res = client.post("/api/evidence/register", data={"actor": "investigator_a"}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "file required" in res.get_json().get("error", "")


def test_evidence_registration_unauthorized_actor(client):
    """Reject registration when an unknown or unauthorized actor attempts upload."""
    res = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(b"data"), "evidence.txt"), "actor": "unknown_intruder"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 403
    assert "Unknown investigator" in res.get_json().get("error", "")


# ===========================================================================
# 3. EVIDENCE VERIFICATION & TAMPERING DETECTION
# ===========================================================================

def test_evidence_tampering_detection(client):
    """Register evidence, verify, tamper disk bytes directly, verify again, restore, verify."""
    original_bytes = b"Cryptographically Pristine Forensic Image 001"
    reg = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(original_bytes), "pristine.txt"), "actor": "investigator_a"},
        content_type="multipart/form-data"
    )
    eid = reg.get_json()["evidence_id"]

    # Step 1: Initial verification must be True
    v1 = client.post(f"/api/evidence/verify/{eid}")
    assert v1.status_code == 200
    assert v1.get_json()["verified"] is True
    assert v1.get_json()["status"] == "INTEGRITY VERIFIED"

    # Step 2: Locate file on disk and tamper 1 byte
    with service.db() as c:
        row = c.execute("SELECT stored_name FROM evidence WHERE id = ?", (eid,)).fetchone()
    stored_path = service.UPLOADS / row["stored_name"]
    assert stored_path.is_file()

    backup_bytes = stored_path.read_bytes()
    tampered_bytes = bytearray(backup_bytes)
    tampered_bytes[0] = (tampered_bytes[0] + 1) % 256
    stored_path.write_bytes(bytes(tampered_bytes))

    try:
        # Step 3: Verification on tampered file must fail
        v2 = client.post(f"/api/evidence/verify/{eid}")
        assert v2.status_code == 200
        assert v2.get_json()["verified"] is False
        assert "MISMATCH" in v2.get_json()["status"]
    finally:
        # Step 4: Restore original bytes
        stored_path.write_bytes(backup_bytes)

    # Step 5: Verification after restoration must succeed
    v3 = client.post(f"/api/evidence/verify/{eid}")
    assert v3.status_code == 200
    assert v3.get_json()["verified"] is True


def test_verify_nonexistent_evidence(client):
    """Return 404 for verifying an evidence ID that does not exist."""
    res = client.post("/api/evidence/verify/EV-DOESNOTEXIST99")
    assert res.status_code == 404


# ===========================================================================
# 4. CUSTODY TRANSFER & LIFECYCLE HISTORY
# ===========================================================================

def test_custody_transfer_flow(client):
    """Test full transfer lifecycle: registration -> transfer A->B -> transfer B->Supervisor."""
    reg = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(b"Custody flow test"), "custody_doc.pdf"), "actor": "investigator_a"},
        content_type="multipart/form-data"
    )
    eid = reg.get_json()["evidence_id"]

    # Transfer 1: investigator_a -> investigator_b
    t1 = client.post("/api/custody/transfer", json={
        "evidence_id": eid,
        "new_custodian": "investigator_b",
        "reason": "Forwarded to ballistics lab"
    })
    assert t1.status_code == 200
    assert t1.get_json()["previous_custodian"] == "investigator_a"
    assert t1.get_json()["new_custodian"] == "investigator_b"

    # Transfer 2: investigator_b -> supervisor_a
    t2 = client.post("/api/custody/transfer", json={
        "evidence_id": eid,
        "new_custodian": "supervisor_a",
        "reason": "Trial evidence presentation"
    })
    assert t2.status_code == 200
    assert t2.get_json()["previous_custodian"] == "investigator_b"
    assert t2.get_json()["new_custodian"] == "supervisor_a"

    # Verify custody history API
    h_res = client.get(f"/api/evidence/{eid}/history")
    assert h_res.status_code == 200
    hist = h_res.get_json()["history"]
    assert len(hist) >= 3  # REGISTER, TRANSFER 1, TRANSFER 2


def test_custody_transfer_invalid_inputs(client):
    """Test validation errors on transfer."""
    # Unknown target custodian
    res = client.post("/api/custody/transfer", json={
        "evidence_id": "EV-ANY",
        "new_custodian": "unknown_officer",
        "reason": "Test"
    })
    assert res.status_code in (400, 404)

    # Missing reason
    res = client.post("/api/custody/transfer", json={
        "evidence_id": "EV-ANY",
        "new_custodian": "investigator_b"
    })
    assert res.status_code == 400


# ===========================================================================
# 5. BLOCKCHAIN & MERKLE INCLUSION PROOFS
# ===========================================================================

def test_blockchain_validation_integrity(client):
    """Validate that the hash-linked blockchain confirms integrity."""
    res = client.get("/api/ledger/validate")
    assert res.status_code == 200
    data = res.get_json()
    assert data["valid"] is True
    assert data["blocks_checked"] > 0
    assert data["invalid_block"] is None


def test_merkle_inclusion_proof_verification(client):
    """Verify that Merkle inclusion proof correctly verifies against the live root."""
    reg = client.post(
        "/api/evidence/register",
        data={"file": (io.BytesIO(b"Merkle proof validation data"), "merkle_spec.txt"), "actor": "investigator_a"},
        content_type="multipart/form-data"
    )
    eid = reg.get_json()["evidence_id"]

    res = client.get(f"/api/evidence/{eid}/merkle-proof")
    assert res.status_code == 200
    pdata = res.get_json()
    assert pdata["evidence_id"] == eid
    assert pdata["verified"] is True
    assert "leaf_hash" in pdata
    assert "root" in pdata
    assert isinstance(pdata["proof"], list)


# ===========================================================================
# 6. AUDIT LOGS & REPORTS
# ===========================================================================

def test_audit_logs_recording(client):
    """Ensure verification actions generate traceable audit logs."""
    res_list = client.get("/api/evidence")
    items = res_list.get_json()
    if items:
        eid = items[0]["id"]
        client.post(f"/api/evidence/verify/{eid}")

    logs_res = client.get("/api/audit?page=1&per_page=10")
    assert logs_res.status_code == 200
    logs = logs_res.get_json()
    assert "results" in logs
    assert logs["total"] > 0


def test_court_reports_pdf_and_text(client):
    """Test generating official court reports in both PDF and Plain Text."""
    res_list = client.get("/api/evidence")
    items = res_list.get_json()
    assert len(items) > 0
    eid = items[0]["id"]

    # PDF Report
    pdf_res = client.get(f"/api/evidence/{eid}/report?format=pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.mimetype == "application/pdf"
    assert len(pdf_res.data) > 100

    # TXT Report
    txt_res = client.get(f"/api/evidence/{eid}/report?format=txt")
    assert txt_res.status_code == 200
    assert txt_res.mimetype == "text/plain"
    assert b"FORENSICLEDGER: CHAIN OF CUSTODY" in txt_res.data


# ===========================================================================
# 7. DATABASE PERSISTENCE ACROSS RE-INITIALIZATION
# ===========================================================================

def test_database_persistence_across_reloads():
    """Verify that re-initializing or reconnecting preserves all prior records and blockchain links."""
    with service.db() as c:
        count_before = c.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        blocks_before = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    # Re-call init() as happens on process restart
    service.init()

    with service.db() as c:
        count_after = c.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        blocks_after = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]

    assert count_after == count_before
    assert blocks_after == blocks_before

    # Re-validate chain
    valid, checked = service.validate_chain()
    assert valid is True
    assert checked == blocks_after
