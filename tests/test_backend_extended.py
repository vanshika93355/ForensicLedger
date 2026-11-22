import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import app as service
from merkle import MerkleTree, compute_merkle_root, digest
from auth import hash_password, verify_password, generate_token, decode_token

def test_auth_login_success():
    client = service.app.test_client()
    res = client.post("/api/auth/login", json={"username": "investigator_a", "password": "password123"})
    assert res.status_code == 200
    data = res.get_json()
    assert "token" in data
    assert data["user_id"] == "investigator_a"
    assert data["role"] == "investigator"

def test_auth_login_fail():
    client = service.app.test_client()
    res = client.post("/api/auth/login", json={"username": "investigator_a", "password": "wrong_password"})
    assert res.status_code == 401

def test_auth_me_endpoint():
    client = service.app.test_client()
    login_res = client.post("/api/auth/login", json={"username": "supervisor_a", "password": "password123"})
    assert login_res.status_code == 200
    token = login_res.get_json()["token"]

    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.get_json()
    assert me_data["user_id"] == "supervisor_a"
    assert me_data["role"] == "supervisor"

def test_evidence_history():
    client = service.app.test_client()
    reg = client.post("/api/evidence/register", data={"file": (io.BytesIO(b"history test evidence"), "history_sample.txt")}, content_type="multipart/form-data")
    assert reg.status_code == 201
    eid = reg.get_json()["evidence_id"]

    tr = client.post("/api/custody/transfer", json={"evidence_id": eid, "new_custodian": "investigator_b", "reason": "Microscopic analysis"})
    assert tr.status_code == 200

    hist_res = client.get(f"/api/evidence/{eid}/history")
    assert hist_res.status_code == 200
    hist = hist_res.get_json()["history"]
    assert any(h.get("action") == "REGISTER" for h in hist)
    assert any(h.get("action") == "TRANSFER" or h.get("source") == "custody" for h in hist)

def test_merkle_tree_module():
    leaves = [digest(f"leaf_{i}".encode()) for i in range(5)]
    tree = MerkleTree(leaves)
    assert tree.root is not None
    assert len(tree.root) == 64

    for leaf in leaves:
        proof = tree.get_proof(leaf)
        assert len(proof) > 0
        assert MerkleTree.verify_proof(leaf, proof, tree.root) is True

    fake_leaf = digest(b"fake_data")
    assert MerkleTree.verify_proof(fake_leaf, tree.get_proof(leaves[0]), tree.root) is False

def test_evidence_merkle_proof_api():
    client = service.app.test_client()
    reg = client.post("/api/evidence/register", data={"file": (io.BytesIO(b"merkle test content"), "merkle_doc.txt")}, content_type="multipart/form-data")
    assert reg.status_code == 201
    eid = reg.get_json()["evidence_id"]

    proof_res = client.get(f"/api/evidence/{eid}/merkle-proof")
    assert proof_res.status_code == 200
    pdata = proof_res.get_json()
    assert pdata["verified"] is True
    assert "proof" in pdata
    assert "root" in pdata

def test_audit_logs_pagination():
    client = service.app.test_client()
    res = client.get("/api/audit?page=1&per_page=5")
    assert res.status_code == 200
    data = res.get_json()
    assert "page" in data
    assert "results" in data
    assert isinstance(data["results"], list)

def test_benchmark_endpoint():
    client = service.app.test_client()
    res = client.post("/api/experiment/benchmark", json={"file_sizes_kb": [1, 10], "iterations": 2})
    assert res.status_code == 200
    data = res.get_json()
    assert data["benchmark"] == "sha256"
    assert len(data["results"]) == 2

def test_report_generation():
    client = service.app.test_client()
    reg = client.post("/api/evidence/register", data={"file": (io.BytesIO(b"evidence for report"), "report_file.txt")}, content_type="multipart/form-data")
    assert reg.status_code == 201
    eid = reg.get_json()["evidence_id"]

    # Test PDF report
    pdf_res = client.get(f"/api/evidence/{eid}/report?format=pdf")
    assert pdf_res.status_code == 200
    assert len(pdf_res.data) > 0

    # Test Plain Text report
    txt_res = client.get(f"/api/evidence/{eid}/report?format=txt")
    assert txt_res.status_code == 200
    assert b"FORENSICLEDGER: CHAIN OF CUSTODY" in txt_res.data
    assert eid.encode() in txt_res.data
