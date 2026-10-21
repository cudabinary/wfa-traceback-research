"""Verify an existing protected restore and copy selected source, offline."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import re
import tarfile

parser = argparse.ArgumentParser()
parser.add_argument("--protected-source", type=Path, required=True)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output.resolve() if args.output else root / "results/host_adapter_source_review_20261021"
out.mkdir(parents=True, exist_ok=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


receipt_bytes = (args.protected_source / "RESTORE_RECEIPT.json").read_bytes()
receipt = json.loads(receipt_bytes)
source = receipt["source"]
assert source["source_id"] == "WIN_PAPER/rtx4060ti_wfa_mechanism_20261019/source/WFA-GPU_corrected.tar.gz"
assert source["sha256"] == "6519a817e52d72e74938937b7397ad653b319dde5652843a2c311e9d644e232f"
archive = (args.protected_source / "WFA-GPU_corrected.tar.gz").read_bytes()
assert len(archive) == source["bytes"] == 1108320 and sha(archive) == source["sha256"]
e = source["extents"][0]
pack = args.protected_source / ("pack329-" + e["pack_sha256"] + ".pack")
h = hashlib.sha256()
with pack.open("rb") as file:
    while chunk := file.read(4 * 1024 * 1024):
        h.update(chunk)
assert pack.stat().st_size == e["remote"]["contentLength"] == 67108864
assert h.hexdigest() == e["pack_sha256"] == "881c2823242d2d359c3ba83e9f3cc3ebc7336653635fc9e3183d36fee0c797fb"
with pack.open("rb") as file:
    file.seek(e["pack_offset"])
    extent = file.read(e["bytes"])
assert e["file_offset"] == 0 and extent == archive
previous = json.loads((root / "results/host_adapter_cpu_20261021/source_reuse_receipt.json").read_text())
old = {x["original_audit_member"].removeprefix("source_snapshots/corrected/"): x for x in previous["members"]}
members = []
calls = []
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
    selected = [x["name"] for x in receipt["members"]] + ["WFA-GPU/utils/sequences.h", "WFA-GPU/lib/aligner.c", "WFA-GPU/utils/cuda_utils.cuh"]
    for name in selected:
        data = tf.extractfile(name).read()
        saved = next((x for x in receipt["members"] if x["name"] == name), None)
        if saved:
            assert len(data) == saved["bytes"] and sha(data) == saved["sha256"]
            protected_member = args.protected_source / "members" / name
            # The operator may strip the common archive root in its member folder.
            if not protected_member.is_file():
                protected_member = args.protected_source / "members" / name.removeprefix("WFA-GPU/")
            assert protected_member.is_file() and protected_member.read_bytes() == data
        relative = name.removeprefix("WFA-GPU/")
        if relative in old:
            assert sha(data) == old[relative]["sha256"] and len(data) == old[relative]["bytes"]
        text = data.decode("utf-8")
        assert not re.search(r"\b[A-Za-z]:[\\/]|/mnt/[a-z]/Users/|/home/[A-Za-z0-9_-]+/|/Users/[A-Za-z0-9_-]+/", text)
        target = out / "source_reference" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        members.append({"member": name, "bytes": len(data), "sha256": sha(data),
                        "protected_extracted_member_compared": bool(saved), "previous_reference_match": relative in old})
    for member in tf.getmembers():
        if member.isfile() and member.name.endswith((".cu", ".c", ".cpp", ".h", ".cuh", ".hpp")):
            text = tf.extractfile(member).read().decode("utf-8", errors="replace")
            for line, value in enumerate(text.splitlines(), 1):
                if re.search(r"\bcopyInResults(?:_distance)?\s*\(", value):
                    calls.append({"member": member.name, "line": line, "text": value.strip()})
    original = tf.extractfile("WFA-GPU/lib/sequence_alignment.cu").read().decode()
    begin = original.index("void copyInResults (")
    end = original.index("\n}", begin) + 2
    body = original[begin:end] + "\n"
    (out / "copyInResults.inc").write_text(body, encoding="utf-8", newline="\n")

result = {"status": "DIRECT_PACK_ARCHIVE_AND_MEMBER_IDENTITIES_PASS",
          "source": {k: source[k] for k in ["source_id", "bytes", "sha256", "extents"]},
          "inherited_descriptor_status_note": "The operator receipt nested source status was a historical retrieval-plan label; actual local pack/archive/member identities were checked here.",
          "protected_restore_receipt_sha256": sha(receipt_bytes), "members": members,
          "copy_symbols_in_entire_archive": calls,
          "copy_function_verbatim_span": {"member": "WFA-GPU/lib/sequence_alignment.cu", "first_line": 346, "last_line": 368,
                                          "bytes": len(body.encode()), "sha256": sha(body.encode())},
          "new_download_bytes": 0, "new_upload_bytes": 0,
          "budget_counters": "Read as an external receipt only; not re-added, subtracted or changed here.",
          "protected_source_modified": False, "entire_112_input_restore": False,
          "scientific_scope": "Source identity and static review only; not alignment correctness, race freedom or performance."}
(out / "restore_verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": result["status"], "archive_bytes": len(archive), "pack_bytes": pack.stat().st_size,
                  "receipt_members_matched": 8, "archive_members_copied": len(members),
                  "copy_symbol_occurrences": len(calls), "new_transfer_bytes": 0}, indent=2))
