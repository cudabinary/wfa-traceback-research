"""Prepare local source references and pinned retrieval requirements, offline."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json


parser = argparse.ArgumentParser()
parser.add_argument("--audit-source", type=Path, required=True)
parser.add_argument("--catalogue", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = root / "results/host_adapter_cpu_20261021"
out.mkdir(parents=True, exist_ok=True)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


original_manifest = json.loads((args.audit_source / "MANIFEST.json").read_text())
original = {x["path"]: x for x in original_manifest["files"]}
assert sha((args.audit_source / "MANIFEST.json").read_bytes()) == "369c7c2b61a62ff4a1c6ce0fe82ff512334f284ac6cce2733e0a1c477eca3afe"
reuse = []
for relative in ["lib/align.cu", "utils/wfa_cpu.c"]:
    name = "source_snapshots/corrected/" + relative
    data = (args.audit_source / name).read_bytes()
    entry = original[name]
    assert len(data) == entry["bytes"] and sha(data) == entry["sha256"]
    target = out / "source_reference" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as file:
        file.write(data)
    reuse.append({"original_audit_member": name, "copied_relative_path": target.relative_to(root).as_posix(),
                  "bytes": len(data), "sha256": sha(data),
                  "scope": "Exact preserved archive-member reference, not a complete restored source archive or native build."})
save("source_reuse_receipt.json", {"first_round_manifest_sha256": sha((args.audit_source / "MANIFEST.json").read_bytes()),
                                  "members": reuse, "original_files_changed": False})

catalogue_data = args.catalogue.read_bytes()
backup = json.loads((root / "evidence/backup_receipt.json").read_text())
assert sha(catalogue_data) == backup["raw_catalogue"]["sha256"]
catalogue = [json.loads(line) for line in gzip.decompress(catalogue_data).decode().splitlines()]
prefix = "WIN_PAPER/rtx4060ti_wfa_mechanism_20261019/"
required = [prefix + "source/WFA-GPU_corrected.tar.gz"]
optional = [prefix + "raw/runs/diag_g0c20w32/gpu.cpu_events.csv",
            prefix + "raw/runs/diag_g0c20w32/gpu.host_events.csv",
            prefix + "raw/runs/diag_g1c20w32/gpu.host_events.csv"]
chosen = []
initial_inputs = json.loads((args.audit_source / "INPUT_RECEIPTS.json").read_text())
initial = {prefix + x["relative_path"]: x for x in initial_inputs["files"]}
for source_id in required + optional:
    item = next(x for x in catalogue if x["source_id"] == source_id)
    assert (item["bytes"], item["sha256"]) == (initial[source_id]["bytes"], initial[source_id]["sha256"])
    item = dict(item)
    item["priority"] = "REQUIRED_FOR_ABI_AND_COPY_HELPER" if source_id in required else "OPTIONAL_FOR_RAW_TRACE_RECHECK_NOT_NEEDED_FOR_CPU_CONTRACT"
    item["status"] = "PINNED_NOT_DOWNLOADED_OR_RESTORED"
    chosen.append(item)


def transfer_bytes(items):
    packs = {e["remote"]["fileId"]: e for x in items for e in x["extents"]}
    return sum(e["remote"]["contentLength"] for e in packs.values())


save("minimal_retrieval_plan.json", {
    "status": "OFFLINE_PLAN_NO_TRANSFER", "catalogue_sha256": sha(catalogue_data),
    "catalogue_object_version": backup["raw_catalogue"]["remote"],
    "sources": chosen, "required_logical_bytes": sum(x["bytes"] for x in chosen if x["source_id"] in required),
    "required_fresh_full_pack_download_bytes": transfer_bytes(chosen[:1]),
    "optional_raw_trace_logical_bytes": sum(x["bytes"] for x in chosen[1:]),
    "optional_raw_trace_fresh_full_pack_download_bytes": transfer_bytes(chosen[1:]),
    "required_plus_optional_distinct_full_pack_bytes": transfer_bytes(chosen),
    "required_archive_members_to_inspect": ["WFA-GPU/lib/wfa_types.h", "WFA-GPU/lib/alignment_results.h",
        "WFA-GPU/lib/sequence_alignment.cu", "WFA-GPU/lib/sequence_alignment.cuh",
        "WFA-GPU/lib/kernels/sequence_alignment_kernel.cuh", "WFA-GPU/lib/kernels/common_alignment_kernels.cuh"],
    "reuse": "Two exact preserved source members are already reused locally. Setup restores did not retain complete downloaded packs on disk in the inspected setup subtree. A supplied matching local pack or logical archive would reduce new transfer need; verify its complete hash before reuse.",
    "restore_rule": "Pin fileId/version, verify full pack SHA256, concatenate extents by file_offset, verify full logical bytes and SHA256; inspect only required members in a separate destination.",
    "prohibited_now": "No remote restore/upload or B2 transfer is performed. No name-only version choice or full 111-input restore."})

E, B, Q = 16384, 512, 4
A, R, K = 20, 8, (2 * E) // 16
payload = B * (A + K * R)
save("host_slot_capacity.json", {
    "status": "CONDITIONAL_AUDITED_MODEL_PAYLOAD_ARITHMETIC_NOT_NEW_ABI_VERIFICATION",
    "source_model": {"path": "code/model.py", "sha256": sha((root / "code/model.py").read_bytes()),
                     "declared_alignment_result_bytes": A, "declared_backtrace_record_bytes": R,
                     "declared_result_tail_records": "floor(2*E/16)"},
    "formula": {"one_pinned_slot_payload": "B * (A + K(E)*R)", "Q_pinned_slot_payload": "Q * B * (A + K(E)*R)",
                "increment_over_one_slot": "(Q-1) * B * (A + K(E)*R)",
                "ordinary_host_metadata": "Q*sizeof(SlotControl) + queue_capacity*sizeof(Job) + engine synchronization/thread storage; sizes pending implementation ABI",
                "other_host_memory": "Global sequences, metadata and CIGAR outputs plus four BiWFA workspaces, allocator/pinned overhead and thread stacks remain counted separately."},
    "example": {"E": E, "B": B, "Q": Q, "K": K, "one_slot_payload_bytes": payload,
                "four_slot_payload_bytes": Q * payload, "extra_over_one_slot_bytes": (Q - 1) * payload},
    "pending": ["Confirm exact type definitions and macro in the pinned corrected archive", "Static assertions in any authorized native build", "Freeze descriptor ABI and allocation overhead", "Measure complete host pinned/ordinary peak; payload is not full RSS or total memory", "Verify device reservation remains equal in the new adapter"],
    "native_compilation_or_GPU_execution": False})
print(json.dumps({"reused_source_members": len(reuse), "required_archive_logical_bytes": chosen[0]["bytes"],
                  "required_fresh_pack_bytes": transfer_bytes(chosen[:1]), "four_slot_payload_bytes": Q * payload}, indent=2))
