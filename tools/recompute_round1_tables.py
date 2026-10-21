"""Recompute portable derived tables. This is not a replay of absent raw runs."""
from pathlib import Path
import argparse
import csv
import json
import statistics


parser = argparse.ArgumentParser()
parser.add_argument("--data", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()


def table(name):
    with (args.data / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


runs = table("primary_runs.csv")
pairs = []
for rnd in range(5):
    a = next(x for x in runs if int(x["round"]) == rnd and int(x["gc_mode"]) == 0)
    b = next(x for x in runs if int(x["round"]) == rnd and int(x["gc_mode"]) == 1)
    assert int(a["capacity_rescues"]) == 118 and int(b["capacity_rescues"]) == 0
    off, on = float(a["completion_s"]), float(b["completion_s"])
    pairs.append({"round": rnd, "off_s": off, "on_s": on, "off_minus_on_s": off - on,
                  "reduction_pct": 100 * (off - on) / off})
off = statistics.median(x["off_s"] for x in pairs)
on = statistics.median(x["on_s"] for x in pairs)
batches = table("diagnostic_batches.csv")
gaps = []
for mode in (0, 1):
    a = next(x for x in batches if int(x["gc_mode"]) == mode and int(x["batch"]) == 1)
    b = next(x for x in batches if int(x["gc_mode"]) == mode and int(x["batch"]) == 2)
    gap = float(b["device_pair_envelope_start_s"]) - float(a["device_pair_envelope_end_s"])
    assert abs(gap - float(b["gap_from_previous_pair_envelope_s"])) < 1e-12
    gaps.append({"gc_mode": mode, "batch_1_to_2_pair_envelope_gap_s": gap})
result = {"status": "PASS_DERIVED_TABLE_RECOMPUTATION_ONLY", "off_median_s": off,
          "on_median_s": on, "median_reduction_pct": 100 * (off - on) / off,
          "paired_contrasts": pairs, "same_device_domain_gaps": gaps,
          "not_reproduced": ["original raw alignment runs or per-base CIGAR checks", "raw device/host traces",
                             "per-job FIFO replay, whose original job-duration trace is absent", "native asynchronous queue performance"],
          "scope": "Checks arithmetic and consistency of preserved derived tables; not independent raw evidence."}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ["status", "off_median_s", "on_median_s", "median_reduction_pct"]}, indent=2))
