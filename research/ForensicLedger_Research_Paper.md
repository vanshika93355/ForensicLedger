# ForensicLedger: A Cryptographically Verified Off-Chain Chain of Custody Management Framework for Digital Evidence

**[AUTHOR NAME 1]**, **[AUTHOR NAME 2]**, and **[AUTHOR NAME 3]**  
*Digital Forensics and Cyber Security Research Group, [INSTITUTION], [CITY, COUNTRY]*  
Email: [email@institution.edu]  
*IEEE Transactions / IEEE Access, November 2026 (Preprint)*

---

### Abstract
Admissibility of digital evidence requires verifiable integrity, authentic provenance, and an unbroken chain of custody (CoC). Paper records and centralized relational databases are exposed to privileged-insider modification and non-repudiation failures, while public permissionless blockchains introduce fee volatility, slow finality, and confidentiality concerns. This paper presents ForensicLedger, a lightweight chain of custody framework intended for single-laboratory deployment. It combines chunked off-chain evidence storage, a local sequential hash-linked event ledger, a binary Merkle tree accumulator for $O(\log N)$ inclusion proofs, and token-based role-based access control (RBAC). On a synthetic benchmark whose file sizes are modeled on the Govdocs1 corpus, the prototype reaches a steady-state SHA-256 streaming throughput of about 912 MB/s for files of 10 MB and larger, registers 100 items at a mean of 18.80 ms per item (53.19 items/s), and verifies a single item in a mean of 9.96 ms. A 1,000-leaf Merkle tree builds in 2.55 ms, and an inclusion proof verifies in 0.042 ms. In an in-memory comparison against a linear traversal baseline, Merkle verification was $81.10\times$ faster at $N = 1,000$, although it was slower at $N = 10$ and the advantage was not monotonic at larger $N$. A small tampering experiment (20 items, 10 single-byte mutations) detected all modifications. We also discuss the threat model and the limitations of a single-host trust boundary.

**Index Terms**—Access control, blockchains, cryptography, data integrity, digital forensics, Merkle tree.

---

## I. INTRODUCTION

DIGITAL evidence is central to criminal prosecutions, civil litigation, and corporate investigations. Under evidentiary rules such as the U.S. Federal Rules of Evidence (FRE 901/902) and guidelines such as ISO/IEC 27037:2012, admissibility depends on showing that evidence was lawfully acquired, preserved without undetected modification, and handled under a documented, tamper-evident chain of custody.

Traditional systems rely on paper custody forms or centralized relational databases (RDBMS). Paper logs can degrade, be lost, or be forged retrospectively. In a centralized database, a privileged administrator or an adversary holding root credentials can alter evidence metadata or audit logs without producing a cryptographic alarm. Blockchain-based alternatives have been proposed [1]–[3], but public networks can impose variable transaction fees and confirmation delays, and may expose evidence identifiers to unintended parties. Permissioned designs reduce some of these concerns at the cost of multi-node infrastructure.

The objective of this work is to design, implement, and empirically evaluate a lightweight framework that combines off-chain evidence storage, hash-linked ledger chaining, and Merkle tree accumulation to provide tamper-evident integrity and efficient selective verification on local infrastructure.

The contributions are:
- **Dual-layer architecture**: bulk evidence payloads are stored in an isolated local vault, while every custody event is anchored in a sequential hash-linked ledger.
- **Merkle-based selective verification**: a binary Merkle accumulator provides $O(\log N)$ inclusion proofs that allow an examiner to verify one item without access to unrelated evidence hashes.
- **Role accountability**: least-privilege RBAC enforced through HMAC-SHA256 signed JSON Web Tokens (JWT) for Investigator, Analyst, and Supervisor roles.
- **Empirical evaluation**: six reproducible experiments covering streaming hashing, registration, verification, Merkle scaling, tamper detection, and a comparison with a linear-scan baseline, together with an explicit discussion of threats and limitations.

---

## II. RELATED WORK

Kumar et al. [1] proposed a distributed CoC framework on a permissioned blockchain, showing that consensus can replace a trusted database administrator; the approach requires a multi-node deployment that may be heavy for a single laboratory. Badr et al. [2] combined smart contracts with off-chain IPFS storage for medical forensics, supporting the use of off-chain storage for large payloads, though IPFS retrieval latency can limit throughput. Liang et al. [3] introduced B-CoC, which addresses privacy through channel-based encryption. Brotsis et al. [4] empirically examined blockchain platforms for IoT forensics and reported scalability and latency limitations. Al-Zahrani and Al-Dhaqm [5] proposed a cloud-oriented blockchain CoC model emphasizing role-based auditability.

ForensicLedger targets the space between a single mutable database and a multi-node blockchain: it offers hash-chained tamper evidence and Merkle-based selective verification on a standalone host, with the trust trade-offs discussed in Section VI. Table I summarizes the comparison.

### TABLE I: COMPARATIVE ARCHITECTURAL FEATURE MATRIX
| Dimension | Centralized SQL | Permissioned CoC [1], [3] | ForensicLedger (this work) |
| :--- | :--- | :--- | :--- |
| **Tamper evidence** | Low (admin-mutable) | High (consortium consensus) | Moderate–high (hash-linked chain; single host) |
| **Storage model** | Database BLOB | External IPFS / data lake | Isolated off-chain vault |
| **Batch verification** | $O(N)$ table scan | Smart-contract query | $O(\log N)$ Merkle proof |
| **Transaction fees** | None | None (high server cost) | None |
| **Infrastructure** | Single-server DB | Multi-node cluster | Lightweight standalone |

---

## III. PROPOSED METHODOLOGY

### A. System Architecture and Data Flow
ForensicLedger has three coordinated tiers (Fig. 1): (1) a presentation and role-based access tier, (2) a cryptographic evidence and ledger engine, and (3) a Merkle accumulator subsystem. When a file arrives via multipart HTTP POST, the stream is passed through a 1 MB chunked buffer that computes its SHA-256 fingerprint while the file is written to an isolated vault directory. The digest, metadata, and custodian identity are then appended to the hash-linked ledger.

*(Fig. 1. ForensicLedger architecture: evidence payloads are stored off-chain, while digests and custody events are anchored in the ledger and summarized by a Merkle root.)*

### B. Threat Model
We consider the following adversaries: (i) a malicious insider or database administrator who edits evidence files or ledger records after registration; (ii) an attacker with stolen user credentials who attempts actions beyond the role’s privileges; (iii) an adversary who modifies evidence bytes in the vault; and (iv) an adversary who truncates, reorders, or rolls back ledger entries. ForensicLedger is designed to detect (iii) and in-place edits under (i) and (iv), and to restrict (ii) through role scoping. An adversary with full control of the host who can rewrite the entire ledger and recompute all hashes is outside the guarantees of the current prototype unless the latest ledger head or Merkle root is anchored externally (see Section VI).

### C. Hash-Linked Ledger
Every event produces a block $B_k$ containing an index $idx_k$, an ISO-8601 UTC timestamp $ts_k$, an evidence identifier $eid_k$, an action type $act_k \in \{\text{GENESIS}, \text{REGISTER}, \text{TRANSFER}, \text{VERIFY}, \text{ANALYZE}\}$, the actor identity $actor_k$, a JSON payload $pl_k$, and the previous block hash $prev_k$. With canonical (key-sorted) JSON serialization, the block digest is:

$$H(B_k) = \text{SHA256}(\text{Ser}(idx_k, ts_k, eid_k, act_k, actor_k, pl_k, prev_k)) \tag{1}$$

The chain is valid if:

$$prev_0 = 0^{64} \quad \text{and} \quad prev_k = H(B_{k-1}) \quad \forall k > 0 \tag{2}$$

#### Algorithm 1: Ledger Append and Chain Validation
```text
procedure APPEND(eid, act, actor, pl)
    prev <- H(last block) or 0^64 if empty
    B <- (idx, UTCNOW(), eid, act, actor, pl, prev)
    B.hash <- SHA256(Ser(B)); persist B
end procedure

procedure VALIDATE(chain)
    prev <- 0^64
    for each block B_k in order do
        if B_k.prev != prev or SHA256(Ser(B_k)) != B_k.hash then
            return INVALID(k)
        end if
        prev <- B_k.hash
    end for
    return VALID
end procedure
```

### D. Merkle Accumulator and Inclusion Proofs
To support selective disclosure without revealing unrelated evidence hashes, a binary Merkle tree is built over ordered leaves:

$$L_i = \text{SHA256}(eid_i \parallel \text{':'} \parallel \text{SHA256}(file_i)) \tag{3}$$

An inclusion proof for leaf $L_t$ is the list of sibling hashes along the path to the root, of length:

$$\ell = \lceil \log_2 N \rceil \tag{4}$$

An examiner recomputes the root from $L_t$ and the proof and compares it with the published root using $O(\log N)$ hash operations.

#### Algorithm 2: Merkle Inclusion Proof
```text
procedure PROVE(leaves, t)
    level <- leaves; proof <- []; i <- t
    while |level| > 1 do
        sib <- i ^ 1  // sibling index; duplicate last node if odd
        append (level[sib], i mod 2) to proof
        level <- HASHPAIRS(level); i <- floor(i / 2)
    end while
    return proof
end procedure

procedure VERIFY(L_t, proof, root)
    h <- L_t
    for (s, pos) in proof do
        h <- (pos == 0) ? SHA256(h || s) : SHA256(s || h)
    end for
    return h == root
end procedure
```

---

## IV. EXPERIMENTAL SETUP

**Dataset statement.** The evaluation workload is *synthetic*. A generator produced files at six size tiers (1 KB, 10 KB, 100 KB, 1 MB, 10 MB, 100 MB) chosen to resemble the size distribution of the Digital Corpora Govdocs1 collection. The real Govdocs1 files were not used, and the synthetic files do not reproduce its MIME structure or entropy in any validated way.

**Host environment.** All experiments ran on an AMD x86_64 host (Family 25, Model 80, 12 logical threads) under Windows 11 Enterprise (64-bit, build 10.0.26300) with an NVMe PCIe 4.0 SSD, Python 3.13.13, Flask 3.1.3, and PyJWT 2.15.1. Timings used Python’s `time.perf_counter()`. Hashing experiments used 5 iterations per size; the verification experiment used 50 records. Unless noted, tables report means, and dispersion is given only where it was recorded (min/max in Table II, standard deviation for single-item verification). Repeated trials with confidence intervals for all experiments are planned.

---

## V. RESULTS AND DISCUSSION

### A. Experiment 1: SHA-256 Streaming Throughput
Table II and Fig. 2 show hashing time and throughput from 1 KB to 100 MB. Throughput rises with size and plateaus near 900–912 MB/s from 1 MB upward. The 1 KB and 10 KB rows should not be read as steady-state rates: their per-call times are on the order of microseconds, where timer resolution, interpreter overhead, and warm-up dominate (note the 1 KB maximum of 0.6231 ms against a minimum of 0.0046 ms, and the non-monotonic 10 KB value). We therefore regard $\ge 1$ MB as the steady-state regime.

### TABLE II: SHA-256 STREAMING HASHING PERFORMANCE (5 ITERATIONS)
| Size | Mean (ms) | Min (ms) | Max (ms) | MB/s |
| :--- | :--- | :--- | :--- | :--- |
| **1 KB** | 0.1299 | 0.0046 | 0.6231 | 7.52† |
| **10 KB** | 0.0147 | 0.0122 | 0.0220 | 663.43† |
| **100 KB** | 0.1092 | 0.1069 | 0.1163 | 893.96 |
| **1 MB** | 1.1099 | 1.0921 | 1.1305 | 901.02 |
| **10 MB** | 10.9614 | 10.8839 | 11.1867 | 912.30 |
| **100 MB** | 109.6493 | 108.1664 | 112.5165 | 912.00 |

*†Timer-resolution/warm-up affected; not steady-state.*

*(Fig. 2. SHA-256 streaming throughput versus file size; small-size points are warm-up affected.)*

### B. Experiments 2 and 3: Registration and Verification
Table III and Fig. 3 report registration for batches of 1 to 100 items. A single cold registration took 97.56 ms, which we attribute to first-use initialization such as file-descriptor and database-connection setup (not separately profiled). For 100 items the mean per-item latency was 18.80 ms, or 53.19 items/s. Single-item verification over 50 records had a mean latency of 9.96 ms (min 8.34, max 20.74, std. dev. 2.85 ms), and all 50 verifications succeeded.

### TABLE III: EVIDENCE REGISTRATION BATCH SCALABILITY
| Batch $N$ | Total (ms) | Per-item (ms) | Items/s |
| :--- | :--- | :--- | :--- |
| **1** | 97.56 | 97.56 | 10.25 |
| **10** | 166.43 | 16.64 | 60.08 |
| **25** | 524.23 | 20.97 | 47.69 |
| **50** | 913.24 | 18.26 | 54.75 |
| **100** | 1879.95 | 18.80 | 53.19 |

*(Fig. 3. Total registration time versus batch size. Per-item latency stabilizes near 18–21 ms for $N \ge 10$.)*

### C. Experiments 4 and 5: Merkle Performance and Tamper Detection
Table IV and Fig. 4 show that build time grows roughly linearly with the number of leaves (2.55 ms for 1,000 leaves), while proof generation and verification stay in the tens of microseconds (0.050 ms and 0.042 ms at $N = 1,000$).

### TABLE IV: MERKLE ACCUMULATOR PERFORMANCE
| Leaves $N$ | Build (ms) | Proof gen (ms) | Proof verify (ms) | Valid |
| :--- | :--- | :--- | :--- | :--- |
| **10** | 0.0798 | 0.0204 | 0.0182 | True |
| **50** | 0.1506 | 0.0155 | 0.0374 | True |
| **100** | 0.2912 | 0.0149 | 0.0195 | True |
| **500** | 1.3770 | 0.0271 | 0.0244 | True |
| **1,000** | 2.5465 | 0.0501 | 0.0418 | True |

*(Fig. 4. Merkle tree build time and proof generation/verification latency versus leaf count.)*

In the tampering test, 20 items were checked, 10 of which had a single byte modified; the system produced $TP = 10, FP = 0, FN = 0, TN = 10$. This is expected for SHA-256, since a changed byte changes the digest with overwhelming probability, but the sample is small and the test covers only content modification, not ledger-level attacks.

### D. Experiment 6: Merkle Proof versus Linear Scan
This experiment compares Merkle proof verification with a linear traversal baseline that scans in-memory ledger blocks to locate and check one item. Table V and Fig. 5 give the results. At $N = 1,000$ the linear scan took 1.9192 ms and Merkle verification 0.0237 ms, a speedup of $81.10\times$ (the ratio of the rounded values shown is about $81.0\times$; the reported figure uses unrounded timings). The Merkle verification time here (0.0237 ms) differs from Table IV (0.0418 ms) because the two were measured in separate runs with different procedures and, at these sub-0.05 ms scales, are sensitive to timer resolution and system noise; they should not be compared directly.

The results are not monotonic. At $N = 10$ the Merkle proof was *slower* than the scan ($0.51\times$), which is expected because fixed per-proof overhead outweighs the saving for tiny sets. At $N = 5,000$ the linear scan time fell to 0.1895 ms, giving only $5.96\times$. We hypothesize that caching or memory-layout effects in the in-memory baseline contributed, but we did not test this, and the drop could also reflect measurement noise or a baseline implementation detail. These single-run values should be confirmed with repeated trials and confidence intervals. Finally, verifying one Merkle proof and re-validating an entire hash chain provide different assurances: the former confirms membership of one item under a root, whereas the latter checks the integrity and order of all events.

### TABLE V: VERIFICATION: MERKLE PROOF VS. LINEAR SCAN
| Items $N$ | Linear (ms) | Merkle (ms) | Speedup |
| :--- | :--- | :--- | :--- |
| **10** | 0.0051 | 0.0099 | 0.51× |
| **50** | 0.0289 | 0.0151 | 1.91× |
| **100** | 0.1243 | 0.0166 | 7.49× |
| **500** | 0.8253 | 0.0206 | 40.13× |
| **1,000** | 1.9192 | 0.0237 | 81.10× |
| **2,500** | 2.8867 | 0.0499 | 57.84× |
| **5,000** | 0.1895 | 0.0318 | 5.96× |

*(Fig. 5. Observed speedup of Merkle proof verification over the linear scan baseline (single run per $N$).)*

---

## VI. LIMITATIONS

**(1) Single-host trust:** the ledger is local, so an adversary controlling the host can rewrite the entire chain and recompute hashes; the guarantees hold only if the latest ledger head or Merkle root is anchored externally (e.g., trusted timestamping or witnessed publication).  
**(2) No external timestamp authority:** timestamps come from the host clock.  
**(3) Synthetic data:** results come from generated files modeled on Govdocs1 size tiers, not from real forensic corpora.  
**(4) Small tamper test:** 20 items and one mutation type do not establish detection rates under broader attack scenarios.  
**(5) Measurement scope:** single-host, in-memory micro-benchmarks with limited repetitions; persistent-storage and multi-user concurrent performance were not evaluated.  
**(6) Key management:** JWT signing keys are held by the application and are not yet protected by an HSM or TPM.

---

## VII. CONCLUSION AND FUTURE WORK

ForensicLedger combines chunked off-chain SHA-256 fingerprinting, a hash-linked private event ledger, binary Merkle accumulation, and JWT-based RBAC in a standalone framework. In our synthetic single-host evaluation it hashed large files at about 912 MB/s, registered items at roughly 53 per second, and produced and verified Merkle proofs in well under 0.1 ms, while detecting all 10 injected single-byte modifications. The Merkle advantage over a linear scan was clear at moderate sizes but not at very small ones, and larger-scale behavior needs repeated measurement.

Future work includes:
1. Multi-site replication using the Raft consensus algorithm.
2. Integration with an RFC 3161 timestamp authority and external anchoring of ledger heads.
3. HSM/TPM 2.0 key protection.
4. Evaluation on real forensic corpora with repeated trials and confidence intervals.

*Source code: [repository URL].*

---

## REFERENCES

[1] P. Kumar, R. Kumar, G. P. Gupta, and R. Tripathi, “A distributed framework for digital evidence chain of custody using permissioned blockchain,” *IEEE Trans. Netw. Service Manag.*, vol. 18, no. 4, pp. 4771–4784, Dec. 2021, doi: 10.1109/TNSM.2021.3108871.  
[2] S. Badr, I. Gomaa, and W. M. Abd-Elhafiez, “A secure medical forensic chain of custody based on blockchain technology,” *J. King Saud Univ.—Comput. Inf. Sci.*, vol. 34, no. 10, pp. 9184–9195, Nov. 2022, doi: 10.1016/j.jksuci.2021.10.016.  
[3] H. Liang, N. Zhou, and X. Huang, “B-CoC: A blockchain-based digital evidence chain of custody framework with privacy protection,” *J. Inf. Secur. Appl.*, vol. 68, Art. no. 103248, Aug. 2022, doi: 10.1016/j.jisa.2022.103248.  
[4] S. Brotsis, N. Kolokotronis, K. Limniotis, S. Bendiab, and S. Shiaeles, “On the suitability of blockchain platforms for IoT digital forensics: An empirical study,” *IEEE Internet Things J.*, vol. 9, no. 20, pp. 20387–20401, Oct. 2022, doi: 10.1109/JIOT.2022.3175895.  
[5] M. Al-Zahrani and A. Al-Dhaqm, “A blockchain-based digital forensic chain of custody framework for cloud computing,” *IEEE Access*, vol. 10, pp. 31450–31464, Mar. 2022, doi: 10.1109/ACCESS.2022.3160408.
