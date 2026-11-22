"""
reports.py — Forensic Chain of Custody Report Generator
Generates PDF and plain text reports for forensic evidence items.
"""

import io
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

def _get_evidence_data(evidence_id: str, db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ev = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if not ev:
            return None
        custody = conn.execute(
            "SELECT * FROM custody_records WHERE evidence_id = ? ORDER BY timestamp ASC",
            (evidence_id,)
        ).fetchall()
        ledger = conn.execute(
            "SELECT * FROM ledger WHERE evidence_id = ? ORDER BY idx ASC",
            (evidence_id,)
        ).fetchall()
        audit = conn.execute(
            "SELECT * FROM audit_logs WHERE evidence_id = ? ORDER BY timestamp DESC",
            (evidence_id,)
        ).fetchall()
        return {
            "evidence": dict(ev),
            "custody": [dict(c) for c in custody],
            "ledger": [dict(l) for l in ledger],
            "audit": [dict(a) for a in audit]
        }
    finally:
        conn.close()

def generate_text_report(evidence_id: str, db_path: Path) -> str:
    """Generate a clean, structured plain-text chain-of-custody report."""
    data = _get_evidence_data(evidence_id, db_path)
    if not data:
        return f"Report generation failed: Evidence ID '{evidence_id}' not found."

    ev = data["evidence"]
    lines = [
        "=" * 80,
        "FORENSICLEDGER: CHAIN OF CUSTODY & INTEGRITY VERIFICATION REPORT",
        "=" * 80,
        f"Generated At (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"Report Classification: LAW ENFORCEMENT & FORENSIC ADMISSIBILITY DRAFT",
        "-" * 80,
        "1. EVIDENCE RECORD SUMMARY",
        f"   Evidence Identifier : {ev.get('id')}",
        f"   Original Filename   : {ev.get('filename')}",
        f"   Internal Storage    : {ev.get('stored_name')}",
        f"   File Size (bytes)   : {ev.get('size'):,} bytes",
        f"   Registration Time   : {ev.get('created')}",
        f"   Initial / Current   : {ev.get('custodian')}",
        f"   Registered SHA-256  : {ev.get('sha256')}",
        "-" * 80,
        "2. CHAIN OF CUSTODY TRANSFER LOG",
    ]

    if not data["custody"]:
        lines.append("   (No custody transfers recorded. Evidence remains with initial custodian.)")
    else:
        for idx, tr in enumerate(data["custody"], 1):
            lines.append(f"   [{idx}] Timestamp : {tr.get('timestamp')}")
            lines.append(f"       From      : {tr.get('previous_custodian')}")
            lines.append(f"       To        : {tr.get('new_custodian')}")
            lines.append(f"       Reason    : {tr.get('reason')}")

    lines.extend([
        "-" * 80,
        "3. HASH-LINKED BLOCKCHAIN LEDGER ENTRIES",
    ])
    if not data["ledger"]:
        lines.append("   (No ledger blocks recorded for this evidence item.)")
    else:
        for blk in data["ledger"]:
            lines.append(f"   Block #{blk.get('idx')} | Action: {blk.get('action')} | Actor: {blk.get('actor')}")
            lines.append(f"     Timestamp: {blk.get('timestamp')}")
            lines.append(f"     Hash     : {blk.get('hash')}")
            lines.append(f"     PrevHash : {blk.get('previous_hash')}")

    lines.extend([
        "-" * 80,
        "4. AUDIT & VERIFICATION HISTORY",
    ])
    if not data["audit"]:
        lines.append("   (No verification checks run yet.)")
    else:
        for a in data["audit"]:
            lines.append(f"   [{a.get('timestamp')}] Action: {a.get('action')} | Result: {a.get('result')}")

    lines.extend([
        "=" * 80,
        "END OF REPORT — FORENSICLEDGER CRYPTOGRAPHIC ASSURANCE",
        "=" * 80,
    ])
    return "\n".join(lines)

def generate_pdf_report(evidence_id: str, db_path: Path) -> bytes:
    """Generate a formatted PDF chain-of-custody report using fpdf2."""
    data = _get_evidence_data(evidence_id, db_path)
    if not data:
        raise ValueError(f"Evidence '{evidence_id}' not found.")

    try:
        from fpdf import FPDF
    except ImportError:
        # Fall back to UTF-8 encoded text as bytes
        return generate_text_report(evidence_id, db_path).encode("utf-8")

    ev = data["evidence"]

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(15, 23, 42) # Dark navy
            self.rect(0, 0, 210, 28, 'F')
            self.set_font('Helvetica', 'B', 15)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, 'FORENSICLEDGER EVIDENCE RECORD', align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_font('Helvetica', 'I', 9)
            self.set_text_color(14, 165, 233) # Sky blue
            self.cell(0, 5, 'Cryptographic Chain of Custody & Integrity Assurance', align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(8)

        def footer(self):
            self.set_y(-18)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, f'ForensicLedger v2.0 | Evidence ID: {evidence_id} | Page {self.page_no()}/{{nb}}', align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 4, 'Tamper-Evident Off-Chain Evidence with Hash-Linked Private Blockchain & Merkle Trees', align='C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Section 1: Summary Box
    pdf.set_fill_color(240, 249, 255)
    pdf.set_draw_color(14, 165, 233)
    pdf.rect(10, 32, 190, 48, 'DF')

    pdf.set_xy(14, 34)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(2, 132, 199)
    pdf.cell(0, 7, '1. EVIDENCE IDENTIFICATION & METADATA', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(30, 41, 59)
    
    pdf.set_x(14)
    pdf.cell(45, 5, 'Evidence ID:', 0)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, str(ev.get('id')), new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', '', 9)
    pdf.set_x(14)
    pdf.cell(45, 5, 'Original Filename:', 0)
    pdf.cell(0, 5, str(ev.get('filename')), new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(14)
    pdf.cell(45, 5, 'File Size:', 0)
    pdf.cell(0, 5, f"{ev.get('size'):,} bytes", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(14)
    pdf.cell(45, 5, 'Registration Timestamp:', 0)
    pdf.cell(0, 5, str(ev.get('created')), new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(14)
    pdf.cell(45, 5, 'Current Custodian:', 0)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 5, str(ev.get('custodian')), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)

    # Section 2: SHA-256 Fingerprint
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, '2. CRYPTOGRAPHIC FINGERPRINT (SHA-256)', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Courier', 'B', 9)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_draw_color(203, 213, 225)
    pdf.cell(190, 8, f"  {ev.get('sha256')}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Section 3: Chain of Custody History
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, '3. CHAIN OF CUSTODY TRANSFER LOG', new_x="LMARGIN", new_y="NEXT")
    
    # Table Header
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(38, 6, 'Timestamp', border=1, fill=True)
    pdf.cell(30, 6, 'From', border=1, fill=True)
    pdf.cell(30, 6, 'To', border=1, fill=True)
    pdf.cell(92, 6, 'Reason', border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(30, 41, 59)
    if not data["custody"]:
        pdf.cell(190, 6, 'No custody transfers recorded. Stored under initial custodian.', border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        for row in data["custody"]:
            pdf.cell(38, 6, str(row.get('timestamp')[:19]), border=1)
            pdf.cell(30, 6, str(row.get('previous_custodian')), border=1)
            pdf.cell(30, 6, str(row.get('new_custodian')), border=1)
            pdf.cell(92, 6, str(row.get('reason'))[:55], border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Section 4: Blockchain Ledger Blocks
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, '4. IMMUTABLE BLOCKCHAIN RECORD', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(12, 6, 'Idx', border=1, fill=True)
    pdf.cell(20, 6, 'Action', border=1, fill=True)
    pdf.cell(28, 6, 'Actor', border=1, fill=True)
    pdf.cell(65, 6, 'Block Hash (SHA-256)', border=1, fill=True)
    pdf.cell(65, 6, 'Previous Block Hash', border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Courier', '', 7)
    pdf.set_text_color(30, 41, 59)
    if not data["ledger"]:
        pdf.cell(190, 6, 'No blockchain entries found.', border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        for blk in data["ledger"]:
            pdf.set_font('Helvetica', '', 8)
            pdf.cell(12, 6, str(blk.get('idx')), border=1)
            pdf.cell(20, 6, str(blk.get('action')), border=1)
            pdf.cell(28, 6, str(blk.get('actor')), border=1)
            pdf.set_font('Courier', '', 6)
            pdf.cell(65, 6, str(blk.get('hash')), border=1)
            pdf.cell(65, 6, str(blk.get('previous_hash')), border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Section 5: Verification & Audit Logs
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, '5. INTEGRITY VERIFICATION LOG', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 6, 'Timestamp', border=1, fill=True)
    pdf.cell(30, 6, 'Action', border=1, fill=True)
    pdf.cell(120, 6, 'Result', border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(30, 41, 59)
    if not data["audit"]:
        pdf.cell(190, 6, 'No integrity verifications recorded.', border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        for a in data["audit"]:
            res = a.get('result', '')
            pdf.cell(40, 6, str(a.get('timestamp')[:19]), border=1)
            pdf.cell(30, 6, str(a.get('action')), border=1)
            if 'VERIFIED' in res:
                pdf.set_text_color(5, 150, 105) # Green
            else:
                pdf.set_text_color(220, 38, 38) # Red
            pdf.cell(120, 6, res, border=1, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 41, 59)

    out = pdf.output()
    if isinstance(out, str):
        return out.encode('latin1')
    return bytes(out)
