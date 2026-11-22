import json, time, urllib.request, urllib.error, uuid, html, sys
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5000"
SAMPLE = ROOT / "sample_data" / "sample_evidence.txt"
DB = ROOT / "backend" / "forensicledger.db"
UPLOADS = ROOT / "backend" / "uploads"

def request(path, method="GET", data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def upload_file(path):
    boundary = "----ForensicLedger" + uuid.uuid4().hex
    content = path.read_bytes()
    filename = path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return request("/api/evidence/register", "POST", body,
                   {"Content-Type": f"multipart/form-data; boundary={boundary}"})

def write_report(results):
    rows = "".join(
        f"<tr><td>{html.escape(x['step'])}</td><td class='{ 'pass' if x['passed'] else 'fail' }'>{'PASS' if x['passed'] else 'FAIL'}</td><td>{html.escape(x['detail'])}</td></tr>"
        for x in results
    )
    payload = json.dumps(results, indent=2)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>ForensicLedger Faculty Demo</title>
<style>body{{font:15px Arial,sans-serif;margin:40px;color:#18212b}}h1{{color:#126b55}}.summary{{padding:16px;background:#eef8f3;border-radius:8px;margin:20px 0}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:12px;text-align:left}}th{{background:#126b55;color:white}}.pass{{color:#087443;font-weight:bold}}.fail{{color:#b42318;font-weight:bold}}code{{overflow-wrap:anywhere}}small{{color:#555}}</style></head><body>
<h1>ForensicLedger – Faculty Demonstration Report</h1><small>Generated automatically from live API responses. Educational prototype; not a production forensic system.</small>
<div class="summary"><b>Demo result:</b> {sum(x['passed'] for x in results)} of {len(results)} checks passed<br><b>Evidence ID:</b> {html.escape(next((x['detail'].split('=')[-1] for x in results if x['step']=='Evidence registration'), 'N/A'))}</div>
<table><thead><tr><th>Demonstration step</th><th>Result</th><th>Observed output</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Raw results</h2><pre>{html.escape(payload)}</pre>
<p><b>Interpretation:</b> File integrity verification compares the current stored file bytes with the SHA-256 digest recorded at registration. Ledger validation checks the hash-linked ledger records separately. A valid ledger does not mean an altered evidence file is intact.</p>
</body></html>"""
    (ROOT / "faculty_demo_report.html").write_text(page, encoding="utf-8")
    (ROOT / "faculty_demo_results.json").write_text(payload, encoding="utf-8")

def main():
    results=[]
    health=request("/api/health")
    results.append({"step":"API health","passed":health.get("status")=="ok","detail":json.dumps(health)})
    registered=upload_file(SAMPLE)
    eid=registered["evidence_id"]
    results.append({"step":"Evidence registration","passed":bool(eid and len(registered.get("sha256",""))==64),"detail":f"Evidence ID={eid}; SHA-256={registered.get('sha256')}; block hash={registered.get('block_hash')}"})
    original=request(f"/api/evidence/verify/{eid}","POST")
    results.append({"step":"Original evidence verification","passed":original.get("verified") is True,"detail":original.get("status","No status")})
    listed=request("/api/evidence")
    results.append({"step":"SQLite evidence listing","passed":any(x.get("id")==eid for x in listed),"detail":f"{len(listed)} evidence record(s) returned; new record present={any(x.get('id')==eid for x in listed)}"})
    ledger=request("/api/ledger")
    results.append({"step":"Hash-linked ledger entry","passed":any(x.get("evidence_id")==eid and x.get("action")=="REGISTER" for x in ledger),"detail":f"{len(ledger)} ledger block(s); registration block present"})
    transfer=request("/api/custody/transfer","POST",json.dumps({"evidence_id":eid,"new_custodian":"investigator_b","reason":"Automated faculty demonstration"}).encode(),{"Content-Type":"application/json"})
    results.append({"step":"Custody transfer","passed":transfer.get("new_custodian")=="investigator_b","detail":json.dumps(transfer)})
    root=request("/api/merkle/root")
    results.append({"step":"Merkle root generation","passed":bool(root.get("merkle_root")),"detail":f"Evidence count={root.get('evidence_count')}; Merkle root={root.get('merkle_root')}"})
    # Safely modify only this demo upload, then restore exact original bytes.
    with sqlite3.connect(DB) as conn:
        row=conn.execute("SELECT stored_name FROM evidence WHERE id=?",(eid,)).fetchone()
    stored_path=UPLOADS/row[0]
    backup=stored_path.read_bytes()
    try:
        stored_path.write_bytes(backup + b"\nDEMO TAMPER TEST - NOT ORIGINAL EVIDENCE\n")
        tampered=request(f"/api/evidence/verify/{eid}","POST")
        results.append({"step":"Tampering detection","passed":tampered.get("verified") is False and "FAILED" in tampered.get("status",""),"detail":tampered.get("status","No status")})
    finally:
        stored_path.write_bytes(backup)
    restored=request(f"/api/evidence/verify/{eid}","POST")
    results.append({"step":"Original bytes restored","passed":restored.get("verified") is True,"detail":restored.get("status","No status")})
    chain=request("/api/ledger/validate")
    results.append({"step":"Ledger validation","passed":chain.get("valid") is True,"detail":json.dumps(chain)})
    write_report(results)
    print("\n=== FORENSICLEDGER DEMO RESULTS ===")
    for item in results:
        print(f"[{'PASS' if item['passed'] else 'FAIL'}] {item['step']}: {item['detail']}")
    passed=sum(x["passed"] for x in results)
    print(f"\n{passed}/{len(results)} checks passed.")
    print(f"Report: {ROOT / 'faculty_demo_report.html'}")
    if passed != len(results):
        sys.exit(1)

if __name__=="__main__":
    main()
