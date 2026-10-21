"""Curate a completed audit without changing the historical snapshot.

Run once with --source pointing to the preserved first-round audit directory.
Personal paths and Korean prose remain in the original audit, outside Git.
No experiments, compiler, remote requests, archive transfers, or restores run.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--git", default="git")
args = parser.parse_args()
source = args.source.resolve()
root = Path(__file__).resolve().parents[1]
destination = root / "results/round1_causal_audit_20261021"
assert not destination.exists(), "Use a fresh destination; never overwrite an import"

git = lambda *a: subprocess.check_output([args.git, "-C", str(root), *a])
seed_head = git("rev-parse", "HEAD").decode().strip()
assert seed_head == "bb0a83a766d65a237dd16aab87a63ab706b4a858"
tracked = [x.decode() for x in git("ls-files", "-z").split(b"\0") if x]
assert len(tracked) == 43
seed_files = []
for path in tracked:
    data = (root / path).read_bytes()
    committed = git("show", f"HEAD:{path}")
    assert data == committed, f"Historical checkout differs from HEAD: {path}"
    seed_files.append({"path": path, "bytes": len(data), "sha256": sha(data)})

first_manifest_data = (source / "MANIFEST.json").read_bytes()
assert sha(first_manifest_data) == "369c7c2b61a62ff4a1c6ce0fe82ff512334f284ac6cce2733e0a1c477eca3afe"
first_manifest = json.loads(first_manifest_data)
original_index = {x["path"]: x for x in first_manifest["files"]}
receipts = []


def get(name):
    data = (source / name).read_bytes()
    item = original_index[name]
    assert len(data) == item["bytes"] and sha(data) == item["sha256"], name
    receipts.append({"original_audit_relative_path": name, "bytes": len(data), "sha256": sha(data)})
    return data


def load(name):
    return json.loads(get(name).decode("utf-8-sig"))


def save(name, value):
    (destination / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


primary = list(csv.DictReader(io.StringIO(get("PRIMARY_RUNS.csv").decode("utf-8-sig"))))
historical = json.loads((root / "results/results.json").read_text())
comparisons = []
for mode, choice in [(0, "g0c20w32"), (1, "g1c20w32")]:
    old = next(x for x in historical["groups"] if x["choice"] == choice)
    new = [x for x in primary if int(x["gc_mode"]) == mode]
    by_id = {x["run_id"]: x for x in new}
    assert set(by_id) == set(old["run_ids"])
    assert [float(by_id[x]["completion_s"]) for x in old["run_ids"]] == old["times_s"]
    assert statistics.median(float(x["completion_s"]) for x in new) == old["median_s"]
    assert all(int(x["reserved_bytes"]) == old["reserved_bytes"] and
               int(x["capacity_rescues"]) == old["rescues"] for x in new)
    comparisons.append({"choice": choice, "status": "EXACT_NUMERIC_MATCH", "runs": len(new),
                        "median_s": old["median_s"], "reserved_bytes": old["reserved_bytes"],
                        "capacity_rescues": old["rescues"]})

raw_identity = load("INPUT_RECEIPTS.json")
raw_by_relative = {x["relative_path"]: x for x in raw_identity["files"]}
seed_sources = json.loads((root / "evidence/source_manifest.json").read_text())
overlaps = []
prefix = "WIN_PAPER/rtx4060ti_wfa_mechanism_20261019/"
for item in seed_sources["admitted"]:
    if item["source_id"].startswith(prefix):
        relative = item["source_id"][len(prefix):]
        if relative in raw_by_relative:
            old = raw_by_relative[relative]
            assert (old["bytes"], old["sha256"]) == (item["bytes"], item["sha256"])
            overlaps.append(item["source_id"])

destination.mkdir(parents=True, exist_ok=False)
copies = {
    "PAIRED_CONTRASTS.csv": "paired_contrasts.csv",
    "DIAGNOSTIC_BATCHES.csv": "diagnostic_batches.csv",
    "DIAGNOSTIC_RESCUE_THREADS.csv": "diagnostic_rescue_threads.csv",
    "DIAGNOSTIC_SUMMARY.json": "diagnostic_summary.json",
    "FIXED_DURATION_FIFO_REPLAY.json": "fixed_duration_fifo_replay.json",
    "MINIMAL_2X2_PROTOCOL.json": "minimal_2x2_protocol.json",
    "CLAIMS_AND_FALSIFIERS.csv": "claims_and_falsifiers.csv",
    "QUEUE_OWNERSHIP_MODEL.json": "queue_ownership_model_result.json",
    "queue_ownership_model.py": "queue_ownership_model.py",
    "AUDIT_RESULTS.json": "audit_results.json",
    "SCOPE_SEPARATION.json": "scope_separation.json",
    "VALIDATION.json": "first_round_validation.json",
    "GPU_WINDOW_REQUIREMENTS.json": "gpu_window_requirements.json",
}
for old, new in copies.items():
    (destination / new).write_bytes(get(old))

for row in primary:
    row.pop("receipt_path")
    row["archive_source_id_to_resolve"] = prefix + "raw/runs/" + row["run_id"] + "/run.json"
with (destination / "primary_runs.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(primary[0]))
    writer.writeheader()
    writer.writerows(primary)

annotations = load("SOURCE_AUDIT.json")
portable_anchors = []
for key, item in annotations["anchors"].items():
    kind, member = key.split("/", 1)
    archive = "WFA-GPU_corrected.tar.gz" if kind == "corrected" else "WFA-GPU_diagnostic.tar.gz"
    portable_anchors.append({"variant": kind, "archive_source_id_to_resolve": prefix + "source/" + archive,
                             "member": member, "member_sha256": item["member_sha256"],
                             "anchors": item["anchors"]})
save("source_annotations.json", {"anchors": portable_anchors,
     "pipeline": annotations["pipeline"], "callback_terminology": annotations["callback_terminology"],
     "buffer_dependency": annotations["buffer_dependency"], "static_scheduling": annotations["static_scheduling"],
     "scope": "Source annotations from verified first-round archive snapshots; full original snapshots remain outside this curated import."})
save("required_raw_identities.json", {
    "status": "IDENTITY_INDEX_ONLY_NOT_RESTORATION_RECEIPT",
    "scope": "112 inputs consumed at the initial raw audit; source IDs must be resolved and object versions pinned before any later restore.",
    "files": [{"archive_source_id_to_resolve": prefix + x["relative_path"],
               "bytes": x["bytes"], "sha256": x["sha256"],
               "initial_original_manifest_check": x["original_manifest_check"]}
              for x in raw_identity["files"]]})
save("seed_tracked_file_hashes.json", {"commit": seed_head, "tracked_files_compared_with_HEAD": 43, "files": seed_files})

summary = {
    "status": "COMPLETED_FIRST_ROUND_CURATED_IMPORT",
    "seed_commit": seed_head,
    "seed_tracked_files_compared_byte_for_byte_with_HEAD": 43,
    "initial_curated_manifest_entries": 40,
    "seed_file_manifest_sha256": sha((root / "evidence/file_manifest.json").read_bytes()),
    "seed_source_manifest_sha256": sha((root / "evidence/source_manifest.json").read_bytes()),
    "first_round_audit_manifest_sha256": sha(first_manifest_data),
    "first_round_report": {"original_relative_name": "REPORT_KO.txt", "bytes": 9890,
                            "sha256": "ee6be839dd1d1b605b22ca1af91455b2c457fe69872ac0981885fe3ab6a4ac02",
                            "location": "Preserved original audit outside Git; Korean prose is not rewritten or imported."},
    "historical_numeric_comparisons": comparisons,
    "direct_seed_source_identity_overlap_with_112_audited_inputs": overlaps,
    "restoration_status": "The setup and this curated import do not restore or prove current availability of all 112 original raw inputs. Original-path unavailability remains the last confirmed state; no new raw-path probing or remote restore was performed.",
    "initial_raw_verification": "415 checks passed before original files became unavailable; 25 first-run outputs were preserved and checked against the initial run manifest.",
    "completed_new_analysis": ["Recomputed primary medians and five matched contrasts from original receipts", "Matched the same 118 capacity-failure IDs across all GC-OFF repeats", "Compared within-device pair envelopes and host callback durations without bridging clocks", "Measured rescue-thread imbalance and ran a conditional fixed-duration replay", "Specified the bounded 2x2 and falsifiers", "Explored 252 finite CPU ownership states and obtained the expected unsafe early-release counterexample"],
    "unestablished": ["Native asynchronous-queue speedup", "Pipeline-independent pure GC instruction benefit", "Native race freedom", "Shared-pool witness or novelty", "Independent-corpus or architecture-wide generalization"],
    "next_single_step": "Specify the actual host change and exact slot-byte formula, then review pointer ownership and synchronization against the preserved source. No GPU execution is authorized by this import.",
    "remaining_gates": ["Verify any restored raw inputs against the 112 identity entries before a full raw replay", "Exact ABI slot-memory formula and host limits", "Actual implementation/native correctness gates", "Exclusive GPU schedule and explicit build/GPU authorization", "Before future transfers, merge supplemental task-only counters with current MAIN counters exactly once and bound storage/transfer costs; actual account billing remains unverified"],
    "first_round_ZIP_exists": False, "ZIP_created_by_import": False,
    "new_GPU_runs": 0, "new_compilations": 0, "new_remote_transfers": 0,
    "archival_status": "Local curated import only. The new round has no immutable B2 object/checkpoint receipt yet; do not infer it from seed backup receipts.",
}
save("summary.json", summary)
(destination / "README.txt").write_text("""Round 1 causal audit: completed analysis and design, no native queue run

The corrected historical R2 comparison is reproduced numerically by the
retained first-round audit: GC OFF 28.121268417s, ON 24.320034711s, median
reduction 13.517291075%, capacity rescues 118 versus zero. All five matched
contrasts favor ON under those fixed conditions.

The total effect includes continued GPU computation, CPU recomputation,
submission timing and output readiness. A separate single diagnostic shows
a batch-1-to-2 alignment-pair envelope gap of about 5.605s with GC OFF versus
0.010s with ON. That gap is not an estimate of removable time or proof that
every device engine was idle. Static CPU rescue assignments are imbalanced.
The fixed-duration FIFO replay is a conditional model, not measured speedup.

The core proposed experiment is GC OFF/ON crossed with GATED/QUEUED host
submission. Keep bounded storage, CPU resources and rescue scheduling equal.
Ordinary dynamic rescue scheduling is a separate strong-baseline qualifier.
The CPU ownership model explores 252 finite states and catches a deliberately
unsafe release before normal RLE readers finish. It proves no native CUDA
race freedom, alignment correctness or performance.

The seed's two R2 groups match all ten retained per-run completion values,
reservations and rescue counts exactly. Setup identity and representative
backup restore do not establish restoration of the 112 inputs used by the
first audit. Their original-path unavailability remains the last verified
state. Full raw replay after generator edits was not completed.

See summary.json for provenance, negative findings, the next step and gates.
Required raw identities are portable lookup keys, not restoration receipts.
Korean prose, path-bearing receipts and exact original raw logs remain in
the preserved first-round audit. Their bytes are not rewritten to English.
No first-round ZIP was present and none was generated for this import.
No remote transfer, new checkpoint, build or GPU experiment was performed.
""", encoding="utf-8")

# Inspect exact new text payloads before any staging. This is a conservative
# portable-text check, not a claim that a generic secret scanner is complete.
prohibited = re.compile(r"\b[A-Za-z]:[\\/]|/mnt/[a-z]/Users/|/home/|/Users/|BEGIN [A-Z ]*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}")
for file in destination.iterdir():
    text = file.read_bytes().decode("utf-8-sig")
    assert not prohibited.search(text), f"Private path or credential pattern: {file.name}"
    assert not re.search(r"[\uac00-\ud7a3]", text), f"Korean prose in new Git payload: {file.name}"
for item in seed_files:
    assert sha((root / item["path"]).read_bytes()) == item["sha256"], "Seed changed during import"

save("import_receipt.json", {"original_manifest_sha256": sha(first_manifest_data),
                            "source_files_verified_during_copy": receipts,
                            "exact_original_bytes_preserved_for": copies,
                            "derived_transformations": {"primary_runs.csv": "Replace personal receipt_path with portable source lookup ID; numeric fields unchanged",
                                                        "source_annotations.json": "Replace absolute archive/snapshot paths with portable archive IDs and member hashes",
                                                        "required_raw_identities.json": "Retain bytes/SHA256 and portable candidate source IDs; omit personal machine paths"},
                            "historical_seed_unchanged": True,
                            "portable_text_payload_check": "PASS_NO_DETECTED_MACHINE_PATH_CREDENTIAL_PATTERN_OR_KOREAN_PROSE",
                            "native_experiments_run": False, "remote_transfers": False})
entries = []
for file in sorted(destination.iterdir()):
    data = file.read_bytes()
    entries.append({"path": file.relative_to(root).as_posix(), "bytes": len(data), "sha256": sha(data)})
save("file_manifest.json", {"files": entries, "scope": "Completed curated round1 import only; manifest excludes itself"})
print(json.dumps({"seed_head": seed_head, "historical_tracked_files_compared": len(seed_files),
                  "historical_numeric_groups_match": len(comparisons), "imported_files": len(entries) + 1,
                  "destination": destination.relative_to(root).as_posix(), "remote_transfers": 0}, indent=2))
