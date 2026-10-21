"""Create and verify a local English research ZIP. Performs no upload."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import zipfile

root = Path(__file__).resolve().parents[1]
round1 = root / "results/round1_causal_audit_20261021"
followup = root / "results/host_adapter_cpu_20261021"
directory = root / "local_only/deliveries"
directory.mkdir(parents=True, exist_ok=True)
archive = directory / "wfa_round1_english_20261021_cecb0dc.zip"
assert not archive.exists(), "Do not overwrite a prior delivery"
payload = {}
for path in sorted(round1.iterdir()):
    if path.is_file():
        payload["round1/" + path.name] = path.read_bytes()
payload["code/recompute_round1_tables.py"] = (root / "tools/recompute_round1_tables.py").read_bytes()
payload["calculations/derived_table_recomputation.json"] = (followup / "round1_table_recomputation.json").read_bytes()
for relative in ["lib/align.cu", "utils/wfa_cpu.c"]:
    payload["source_reference/" + relative] = (followup / "source_reference" / relative).read_bytes()
payload["REPORT.txt"] = b"""Exact GPU traceback: completed first-round causal audit
English delivery, 2026-10-21. Local preparation only; no Library ID is asserted.

Outcome
The retained corrected R2 receipts give GC OFF median 28.121268417s and GC ON
24.320034711s: 13.517291075% lower completion time. All five matched round
differences are positive. OFF has the same 118 arena-capacity rescue IDs in
each repetition; ON has zero. Each job includes 10000 original ONT pairs,
9112 GPU-eligible plus 888 CPU-routed, E16384/C20971520/w32/B512. Both modes
reserve 5739913483 CUDA bytes under a 5905580032-byte reservation cap.

What this establishes
The tested GC configuration changes complete execution: more GPU work finishes,
CPU recomputation is avoided, and submission/overlap/output timing changes.
It does not isolate pure collector instruction cost or a hardware speedup.
A separate single diagnostic has a batch-1-to-2 alignment-pair envelope gap
of 5.604592640s OFF versus 0.009612288s ON. The OFF batch0 CPU helper lasts
10.814826297s while the overlapping next CUDA bracket lasts 5.228879883s.
These durations are not additive fractions of primary wall time. The device
gap is not proof that all engines were idle, and no host/device clocks are
bridged. Rescue work is imbalanced across the four static CPU assignments.

Proposed discriminating experiment
GC OFF/ON crossed with GATED/QUEUED submission, using the same bounded slots,
CPU capacity, exact output and rescue policy. Compare complete fresh requests.
Ordinary load balancing is a separate strong software qualifier. Queue speedup,
GC residual under that stronger baseline, and shared-pool novelty are UNKNOWN.

Validation and counterexample
The first raw audit completed 415 checks before source-path loss. It checked
score/reference equality, output coverage, statuses, IDs and sealed hashes;
it did not rerun native alignment or independently recheck all CIGAR bases.
The original full-CIGAR semantic validation is inherited historical evidence.
The first CPU abstract model explores 252 finite states and catches early slot
release while normal RLE still reads the buffer. It proves no CUDA race freedom,
native alignment correctness, optimal queue size or performance.

Source continuity and reproducibility
The original 59-file audit and Korean report remain unchanged. The two historical
summary groups match all ten retained per-run completion times exactly.
A supplied protected local MANIFEST matches the original SHA256, but only 1 of
112 required inputs was present in that supplied tree; 111 remain unresolved
there. The original-path absence and failed complete raw rerun after generator
edits are explicitly retained. A manifest match is not transitive restoration.
The bundle includes exact preserved source references, portable derived tables,
model code and a derived-table calculator. It does not include a full raw replay
environment. A later CPU adapter review is separate from these historical timings.

Negative results and limits
No measured asynchronous queue result, new native GPU run, native race proof,
shared-pool witness, new alignment principle, independent-corpus generalization
or architecture-wide benefit is claimed. Fixed-duration replay is conditional.
No failed or incomplete run is treated as a fast completed request.
"""
payload["REPRODUCE.txt"] = b"""Extract into a fresh directory. Use an existing Python 3 installation.

Recompute preserved derived arithmetic:
  python code/recompute_round1_tables.py --data round1 --output output/recomputed.json

Run the first finite CPU ownership model in this fresh extracted copy:
  python round1/queue_ownership_model.py
The latter writes round1/QUEUE_OWNERSHIP_MODEL.json. It is an abstract model,
not a native alignment, CUDA run or performance benchmark.

The first command checks median/paired arithmetic and within-device envelope
gaps from retained derived tables. It cannot recreate absent original raw events,
full input sequences, compiler state, per-base CIGAR validation or per-job FIFO
replay. Exact missing identities are in round1/required_raw_identities.json;
the supplied partial restore is documented in round1/restoration_check.json.
No download or restore is automatic. Source references are incomplete for native
builds; required type headers and copy helper were not in the preserved excerpt.

Use root MANIFEST.json and SHA256SUMS.txt for this ZIP's payload. Historical
manifests under round1 refer to their original curated source layout and are
provenance records, not this ZIP's membership list. Preserve original bytes.
"""
payload["PROVENANCE.json"] = (json.dumps({
    "base_local_commit": "cecb0dc9d5e6a7baba97e49a63309337a9bb8524",
    "original_round1_manifest_sha256": "369c7c2b61a62ff4a1c6ce0fe82ff512334f284ac6cce2733e0a1c477eca3afe",
    "original_Korean_report_bytes": 9890,
    "original_Korean_report_sha256": "ee6be839dd1d1b605b22ca1af91455b2c457fe69872ac0981885fe3ab6a4ac02",
    "source_reference_receipt": json.loads((followup / "source_reuse_receipt.json").read_text()),
    "scope": "First-round English delivery. Derived arithmetic was rechecked locally; original raw alignment was not replayed.",
    "sharing_status_at_creation": "LOCAL_ONLY_NOT_UPLOADED_NO_LIBRARY_ID",
    "excluded": ["credentials", "personal machine paths", "Korean original prose", "unrelated research", "large raw data", "native binaries"],
}, indent=2) + "\n").encode()

private = re.compile(r"\b[A-Za-z]:[\\/]|/mnt/[a-z]/Users/|/home/[A-Za-z0-9_-]+/|/Users/[A-Za-z0-9_-]+/|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
for name, data in payload.items():
    path = PurePosixPath(name)
    assert not path.is_absolute() and ".." not in path.parts and "\\" not in name
    text = data.decode("utf-8-sig")
    assert not private.search(text) and not re.search(r"[\uac00-\ud7a3]", text), name

def entry(name, data):
    return {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

payload["SHA256SUMS.txt"] = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payload.items())).encode()
payload["MANIFEST.json"] = (json.dumps({"files": [entry(n, b) for n, b in sorted(payload.items())],
    "scope": "Every ZIP entry except this self-referential manifest; external receipt hashes every entry including this manifest."}, indent=2) + "\n").encode()
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name, data in sorted(payload.items()):
        item = zipfile.ZipInfo(name, (2026, 10, 21, 0, 0, 0))
        item.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(item, data)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist())) == len(payload)
    for name, data in payload.items():
        assert z.read(name) == data
    contents = [{**entry(x.filename, z.read(x.filename)), "CRC32": f"{x.CRC:08x}"} for x in z.infolist()]
receipt = {"status": "LOCAL_ENGLISH_ZIP_CRC_CONTENTS_AND_SHA256_PASS",
           "zip_relative_path": archive.relative_to(root).as_posix(), "zip_bytes": archive.stat().st_size,
           "zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "entry_count": len(payload),
           "entries": contents, "native_GPU_runs": 0, "Library_upload": "NOT_PERFORMED",
           "Library_ID": None, "B2_transfer": "NOT_PERFORMED"}
(root / "evidence/round1_english_delivery_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: receipt[k] for k in ["status", "zip_relative_path", "zip_bytes", "zip_sha256", "entry_count"]}, indent=2))
