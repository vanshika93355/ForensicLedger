"""
generate_diagrams.py
Generates high-resolution architectural, workflow, and ER diagrams for ForensicLedger:
1. ForensicLedger_Architecture_Diagram.png
2. ForensicLedger_Workflow_Diagram.png
3. ForensicLedger_Database_ER_Diagram.png
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

DOC_DIR = Path("c:/Users/justf/Downloads/ForensicLedger_AutoDemo/ForensicLedger/documentation")
DOC_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#cbd5e1'

def create_architecture_diagram():
    fig, ax = plt.subplots(figsize=(14, 10), dpi=300)
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Title
    ax.text(50, 96, "ForensicLedger System Architecture", fontsize=18, fontweight='bold', color='#f8fafc', ha='center')
    ax.text(50, 93, "Three-Tier Cryptographically Verified Evidence & Chain of Custody Management Framework", fontsize=10, color='#94a3b8', ha='center')

    # Tier 1: Presentation Tier
    p1 = patches.FancyBboxPatch((5, 74), 90, 16, boxstyle="round,pad=1", ec="#38bdf8", fc="#1e293b", lw=2)
    ax.add_patch(p1)
    ax.text(8, 87, "TIER 1: PRESENTATION & CLIENT USER INTERFACES (SPA)", fontsize=11, fontweight='bold', color='#38bdf8')
    
    # Submodules Tier 1
    sub_t1 = [
        ("Investigator Portal", "Evidence Ingestion, Transfer,\nIntegrity Verification", 10),
        ("Forensic Analyst UI", "Analytical Inspection,\nLocal Hash Audit", 40),
        ("Supervisor & Admin Panel", "Chain Auditing, User Management,\nCertified Report Export", 70)
    ]
    for title, desc, x in sub_t1:
        box = patches.FancyBboxPatch((x, 75.5), 25, 10, boxstyle="round,pad=0.5", ec="#475569", fc="#0f172a", lw=1)
        ax.add_patch(box)
        ax.text(x + 12.5, 82.5, title, fontsize=9, fontweight='bold', color='#f1f5f9', ha='center')
        ax.text(x + 12.5, 78.5, desc, fontsize=7.5, color='#94a3b8', ha='center')

    # Arrow 1 to 2
    ax.annotate("", xy=(50, 68), xytext=(50, 74), arrowprops=dict(arrowstyle="->", color="#38bdf8", lw=2))
    ax.text(52, 71, "REST API (JSON / HTTP Multipart / Bearer JWT)", fontsize=8, color='#38bdf8', va='center')

    # Tier 2: API Gateway & Security Middleware
    p2 = patches.FancyBboxPatch((5, 48), 90, 19, boxstyle="round,pad=1", ec="#a855f7", fc="#1e293b", lw=2)
    ax.add_patch(p2)
    ax.text(8, 64, "TIER 2: API GATEWAY, AUTHENTICATION & DISPATCH ENGINE", fontsize=11, fontweight='bold', color='#a855f7')

    sub_t2 = [
        ("JWT Authentication", "HMAC-SHA256 Token Signing\n24-Hour Expiration", 8),
        ("Role-Based Access Control", "Principal-of-Least-Privilege\nInvestigator / Analyst / Supervisor", 31),
        ("Streaming Ingestion Pipeline", "1 MB Chunked Read Buffer\nSanitization & Disk Vaulting", 54),
        ("Audit Logging Dispatcher", "Immutable Event Trail\nAction / Actor / Timestamp", 77)
    ]
    for title, desc, x in sub_t2:
        box = patches.FancyBboxPatch((x, 49.5), 20, 12, boxstyle="round,pad=0.5", ec="#475569", fc="#0f172a", lw=1)
        ax.add_patch(box)
        ax.text(x + 10, 58, title, fontsize=8, fontweight='bold', color='#f1f5f9', ha='center')
        ax.text(x + 10, 53, desc, fontsize=7, color='#94a3b8', ha='center')

    # Arrow 2 to 3
    ax.annotate("", xy=(30, 42), xytext=(30, 48), arrowprops=dict(arrowstyle="->", color="#a855f7", lw=2))
    ax.annotate("", xy=(70, 42), xytext=(70, 48), arrowprops=dict(arrowstyle="->", color="#a855f7", lw=2))

    # Tier 3: Core Storage & Cryptographic Engines
    p3 = patches.FancyBboxPatch((5, 8), 90, 33, boxstyle="round,pad=1", ec="#10b981", fc="#1e293b", lw=2)
    ax.add_patch(p3)
    ax.text(8, 38, "TIER 3: CRYPTOGRAPHIC ENGINES & PERSISTENT STORAGE", fontsize=11, fontweight='bold', color='#10b981')

    sub_t3 = [
        ("Off-Chain Evidence Vault", "Isolated Disk Repository\n(backend/uploads/)\nUnique ID: EV-{UUID12}\n1MB Stream SHA-256", 8, 26, 8, "#38bdf8"),
        ("Hash-Linked Blockchain", "Sequential Block Chain\nBlock Digest: H(idx||eid||prev)\nTamper-Evident History\nMonotonic Indexing", 38, 26, 8, "#a855f7"),
        ("Merkle Tree Accumulator", "Binary Tree Accumulator\nLeaves: H(eid || ':' || sha256)\nO(log N) Inclusion Proofs\nDifferential Disclosure", 68, 26, 8, "#10b981")
    ]
    for title, desc, x, w, y, color in sub_t3:
        box = patches.FancyBboxPatch((x, y), w, 27, boxstyle="round,pad=0.5", ec=color, fc="#0f172a", lw=1.2)
        ax.add_patch(box)
        ax.text(x + w/2, y + 23, title, fontsize=9, fontweight='bold', color=color, ha='center')
        ax.text(x + w/2, y + 12, desc, fontsize=7.5, color='#cbd5e1', ha='center', va='center')

    plt.tight_layout()
    out_file = DOC_DIR / "ForensicLedger_Architecture_Diagram.png"
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"Generated: {out_file}")

def create_workflow_diagram():
    fig, ax = plt.subplots(figsize=(14, 12), dpi=300)
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 97, "ForensicLedger 12-Step Evidence Lifecycle Workflow", fontsize=17, fontweight='bold', color='#f8fafc', ha='center')
    ax.text(50, 94.5, "End-to-End Cryptographic Custody, Verification, Accumulation, and Auditing Pipeline", fontsize=9.5, color='#94a3b8', ha='center')

    steps = [
        ("1. User Authentication", "JWT Bearer Token\nRole Assignment", 15, 84, "#38bdf8"),
        ("2. Evidence Ingestion", "Multipart POST\nStream Reading", 50, 84, "#38bdf8"),
        ("3. File Validation", "MIME & Extension\nSanitization", 85, 84, "#38bdf8"),
        
        ("4. SHA-256 Hashing", "1MB Chunked Stream\n256-bit Digest", 85, 68, "#a855f7"),
        ("5. Off-Chain Storage", "UUID Vault Isolation\n(backend/uploads)", 50, 68, "#a855f7"),
        ("6. Metadata Anchoring", "SQLite DB Insert\nSize, Time, Custodian", 15, 68, "#a855f7"),

        ("7. Ledger Block Chaining", "Canonical JSON\nH(B_k) = H(prev_hash)", 15, 52, "#10b981"),
        ("8. Merkle Accumulation", "Leaf: H(EID:SHA)\nBalanced Binary Tree", 50, 52, "#10b981"),
        ("9. Sub-Linear Verification", "O(log N) Proof Path\nJudicial Attestation", 85, 52, "#10b981"),

        ("10. Real-Time Verification", "Recompute Stream\nvs Database Hash", 85, 36, "#f59e0b"),
        ("11. Tamper Detection", "Avalanche Detection\nIntegrity Error Alert", 50, 36, "#ef4444"),
        ("12. Custody Transfer", "Authorized Hand-off\nNew Block Anchored", 15, 36, "#38bdf8"),

        ("13. Audit Trail Logging", "Immutable Event Trail\nAction & Actor Binding", 30, 20, "#a855f7"),
        ("14. Court Report Export", "Certified PDF / TXT\nChain of Custody Report", 70, 20, "#10b981"),
    ]

    for title, desc, x, y, col in steps:
        box = patches.FancyBboxPatch((x - 12.5, y - 5), 25, 10, boxstyle="round,pad=0.5", ec=col, fc="#1e293b", lw=1.5)
        ax.add_patch(box)
        ax.text(x, y + 2.5, title, fontsize=8, fontweight='bold', color=col, ha='center')
        ax.text(x, y - 2, desc, fontsize=7, color='#cbd5e1', ha='center')

    # Connectors
    arrows = [
        ((27.5, 84), (37.5, 84)),  # 1 -> 2
        ((62.5, 84), (72.5, 84)),  # 2 -> 3
        ((85, 79), (85, 73)),      # 3 -> 4
        ((72.5, 68), (62.5, 68)),  # 4 -> 5
        ((37.5, 68), (27.5, 68)),  # 5 -> 6
        ((15, 63), (15, 57)),      # 6 -> 7
        ((27.5, 52), (37.5, 52)),  # 7 -> 8
        ((62.5, 52), (72.5, 52)),  # 8 -> 9
        ((85, 47), (85, 41)),      # 9 -> 10
        ((72.5, 36), (62.5, 36)),  # 10 -> 11
        ((37.5, 36), (27.5, 36)),  # 11 -> 12
        ((20, 31), (25, 25)),      # 12 -> 13
        ((42.5, 20), (57.5, 20)),  # 13 -> 14
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", color="#94a3b8", lw=1.5))

    # Legend / Annotation Box
    lbox = patches.FancyBboxPatch((10, 4), 80, 8, boxstyle="round,pad=0.5", ec="#475569", fc="#0f172a", lw=1)
    ax.add_patch(lbox)
    ax.text(50, 8.5, "Legend: Cyan = Authentication & Ingestion | Purple = Hash & Vault | Green = Ledger & Merkle | Amber/Red = Verification & Tamper Detection", fontsize=7.5, color='#94a3b8', ha='center')

    plt.tight_layout()
    out_file = DOC_DIR / "ForensicLedger_Workflow_Diagram.png"
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"Generated: {out_file}")

def create_database_er_diagram():
    fig, ax = plt.subplots(figsize=(15, 11), dpi=300)
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    ax.text(50, 97, "ForensicLedger Relational Database Schema (SQLite)", fontsize=17, fontweight='bold', color='#f8fafc', ha='center')
    ax.text(50, 94.5, "Entity-Relationship & Cryptographic Hash Linkage Architecture", fontsize=9.5, color='#94a3b8', ha='center')

    # Table 1: evidence
    t1_box = patches.FancyBboxPatch((5, 55), 28, 35, boxstyle="round,pad=0.5", ec="#38bdf8", fc="#1e293b", lw=2)
    ax.add_patch(t1_box)
    ax.text(19, 87, "TABLE: evidence", fontsize=10, fontweight='bold', color='#38bdf8', ha='center')
    t1_text = (
        "id: TEXT (PK)\n"
        "filename: TEXT\n"
        "size: INTEGER\n"
        "sha256: TEXT (64-hex)\n"
        "created_at: TEXT (ISO-8601)\n"
        "custodian: TEXT\n"
        "stored_name: TEXT\n"
        "case_id: TEXT\n"
        "status: TEXT ('verified')"
    )
    ax.text(7, 83, t1_text, fontsize=8, color='#e2e8f0', va='top', family='monospace')

    # Table 2: ledger
    t2_box = patches.FancyBboxPatch((36, 50), 30, 40, boxstyle="round,pad=0.5", ec="#10b981", fc="#1e293b", lw=2)
    ax.add_patch(t2_box)
    ax.text(51, 87, "TABLE: ledger (Blockchain)", fontsize=10, fontweight='bold', color='#10b981', ha='center')
    t2_text = (
        "idx: INTEGER (PK)\n"
        "timestamp: TEXT (ISO-8601)\n"
        "evidence_id: TEXT (FK -> evidence)\n"
        "action: TEXT (GENESIS/REG/..)\n"
        "actor: TEXT\n"
        "payload: TEXT (Canonical JSON)\n"
        "hash: TEXT (Block Digest)\n"
        "previous_hash: TEXT (Link to B_k-1)"
    )
    ax.text(38, 83, t2_text, fontsize=8, color='#e2e8f0', va='top', family='monospace')

    # Table 3: custody_records
    t3_box = patches.FancyBboxPatch((70, 58), 26, 32, boxstyle="round,pad=0.5", ec="#a855f7", fc="#1e293b", lw=2)
    ax.add_patch(t3_box)
    ax.text(83, 87, "TABLE: custody_records", fontsize=10, fontweight='bold', color='#a855f7', ha='center')
    t3_text = (
        "id: INTEGER (PK)\n"
        "evidence_id: TEXT (FK)\n"
        "previous_custodian: TEXT\n"
        "new_custodian: TEXT\n"
        "reason: TEXT\n"
        "timestamp: TEXT (ISO-8601)"
    )
    ax.text(72, 83, t3_text, fontsize=8, color='#e2e8f0', va='top', family='monospace')

    # Table 4: audit_logs
    t4_box = patches.FancyBboxPatch((15, 10), 32, 34, boxstyle="round,pad=0.5", ec="#f59e0b", fc="#1e293b", lw=2)
    ax.add_patch(t4_box)
    ax.text(31, 41, "TABLE: audit_logs", fontsize=10, fontweight='bold', color='#f59e0b', ha='center')
    t4_text = (
        "id: INTEGER (PK AUTO)\n"
        "evidence_id: TEXT (FK)\n"
        "action: TEXT (REGISTER/..)\n"
        "result: TEXT ('INTEGRITY..')\n"
        "timestamp: TEXT (ISO-8601)"
    )
    ax.text(17, 37, t4_text, fontsize=8, color='#e2e8f0', va='top', family='monospace')

    # Table 5: users
    t5_box = patches.FancyBboxPatch((55, 10), 32, 34, boxstyle="round,pad=0.5", ec="#ec4899", fc="#1e293b", lw=2)
    ax.add_patch(t5_box)
    ax.text(71, 41, "TABLE: users (RBAC)", fontsize=10, fontweight='bold', color='#ec4899', ha='center')
    t5_text = (
        "id: TEXT (PK, Username)\n"
        "role: TEXT ('investigator'|..)\n"
        "password_hash: TEXT\n"
        "  (Salted HMAC-SHA256)"
    )
    ax.text(57, 37, t5_text, fontsize=8, color='#e2e8f0', va='top', family='monospace')

    # Relationships Connectors
    # 1. evidence.id -> ledger.evidence_id
    ax.annotate("", xy=(36, 75), xytext=(33, 75), arrowprops=dict(arrowstyle="<->", color="#38bdf8", lw=1.5))
    ax.text(34.5, 76.5, "1:N", fontsize=8, color="#38bdf8", ha='center')

    # 2. evidence.id -> custody_records.evidence_id
    ax.annotate("", xy=(70, 75), xytext=(66, 75), arrowprops=dict(arrowstyle="<->", color="#a855f7", lw=1.5))
    ax.text(68, 76.5, "1:N", fontsize=8, color="#a855f7", ha='center')

    # 3. evidence.id -> audit_logs.evidence_id
    ax.annotate("", xy=(25, 44), xytext=(19, 55), arrowprops=dict(arrowstyle="<->", color="#f59e0b", lw=1.5))
    ax.text(20, 48, "1:N", fontsize=8, color="#f59e0b", ha='center')

    # 4. users.id -> ledger.actor
    ax.annotate("", xy=(52, 50), xytext=(65, 44), arrowprops=dict(arrowstyle="<->", color="#ec4899", lw=1.5))
    ax.text(61, 48, "1:N", fontsize=8, color="#ec4899", ha='center')

    plt.tight_layout()
    out_file = DOC_DIR / "ForensicLedger_Database_ER_Diagram.png"
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"Generated: {out_file}")

if __name__ == "__main__":
    create_architecture_diagram()
    create_workflow_diagram()
    create_database_er_diagram()
