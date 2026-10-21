"""Explore a finite host-adapter contract. No native pointers, CUDA or timings.

Unlike the first-round model, this includes D2H completion, the old overlap
position (service after the next submission), a gate before copy-out, and drain.
"""
from collections import deque
from pathlib import Path
import argparse
import json


def explore(n, slots, gated=False, mutant=None):
    # producer batch/phase, active GPU, completed GPU mask, last submitted,
    # slot leases, payload owners, FIFO jobs, CPU(batch,slot,phase), done mask
    # Producer phases: acquire/launch/gate/enqueue_copy/copy_done/publish/
    # advance/drain/end. CPU phases: rescue then normal RLE.
    initial = (0, 0, -1, 0, -1, (-1,) * slots, (-1,) * slots, (), (-1, -1, -1), 0)
    frontier = deque([initial])
    parent = {initial: None}
    transitions = terminals = waits = 0
    failures = []

    def history(state, event):
        result = [event]
        while parent[state] is not None:
            state, event = parent[state]
            result.append(event)
        return list(reversed(result))

    while frontier:
        state = frontier.popleft()
        b, phase, active, gpu_done, launched, leases, payloads, queue, cpu, done = state
        actions = []

        def add(event, **changes):
            names = ["b", "phase", "active", "gpu_done", "launched", "leases", "payloads", "queue", "cpu", "done"]
            values = list(state)
            for name, value in changes.items():
                values[names.index(name)] = value
            actions.append((event, tuple(values)))

        if active >= 0:
            add(f"GPU {active} completes", active=-1, gpu_done=gpu_done | (1 << active))
        slot = b % slots
        if phase == 0:
            if leases[slot] == -1:
                new = list(leases)
                new[slot] = b
                add(f"acquire slot {slot} for batch {b}", leases=tuple(new), phase=1)
            else:
                waits += 1
        elif phase == 1 and active == -1:
            add(f"submit GPU {b}; prior batch may enter CPU service", active=b, launched=b, phase=2)
        elif phase == 2:
            if not gated or b == 0 or done & (1 << (b - 1)):
                add(f"pass submission gate for batch {b}", phase=3)
        elif phase == 3:
            add(f"enqueue D2H for batch {b}", phase=5 if mutant == "publish_before_copy_done" else 4)
        elif phase == 4 and gpu_done & (1 << b):
            new = list(payloads)
            new[slot] = b
            add(f"D2H batch {b} completes in slot {slot}", payloads=tuple(new), phase=5)
        elif phase == 5:
            if payloads[slot] != b:
                return {"status": "COUNTEREXAMPLE", "reason": "READY published before D2H completion",
                        "witness": history(state, f"publish batch {b} with payload owner {payloads[slot]}"),
                        "states_explored": len(parent)}
            add(f"publish batch {b} to FIFO", queue=queue + ((b, slot),), phase=6)
        elif phase == 6:
            add(f"advance after batch {b}", b=b + 1 if b + 1 < n else b, phase=0 if b + 1 < n else 7)
        elif phase == 7:
            if done == (1 << n) - 1:
                add("final drain complete; outputs may close and buffers may free", phase=8)

        if cpu[0] == -1 and queue:
            job, index = queue[0]
            allowed = launched >= job + 1 or (phase == 7 and mutant != "omit_final_flush")
            if allowed:
                if leases[index] != job or payloads[index] != job:
                    return {"status": "COUNTEREXAMPLE", "reason": "stale queued slot",
                            "witness": history(state, f"CPU starts batch {job} from invalid slot {index}"),
                            "states_explored": len(parent)}
                add(f"CPU rescue starts batch {job}", cpu=(job, index, 0), queue=queue[1:])
        elif cpu[0] >= 0:
            job, index, step = cpu
            if payloads[index] != job:
                return {"status": "COUNTEREXAMPLE", "reason": "slot overwritten before normal RLE completed",
                        "witness": history(state, f"RLE batch {job} sees payload from {payloads[index]}"),
                        "states_explored": len(parent)}
            if step == 0:
                new = list(leases)
                if mutant == "release_after_rescue":
                    new[index] = -1
                add(f"rescue batch {job} ends" + ("; UNSAFE early release" if mutant == "release_after_rescue" else ""),
                    leases=tuple(new), cpu=(job, index, 1))
            else:
                new = list(leases)
                if mutant != "release_after_rescue":
                    assert new[index] == job
                    new[index] = -1
                add(f"normal RLE batch {job} ends; release slot {index}",
                    leases=tuple(new), cpu=(-1, -1, -1), done=done | (1 << job))

        if phase == 8:
            assert done == gpu_done == (1 << n) - 1 and active == -1
            assert not queue and cpu[0] == -1 and all(x == -1 for x in leases)
            terminals += 1
        elif not actions:
            failures.append(history(state, f"unfinished circular wait: producer batch={b}, phase={phase}, last_submitted={launched}, queued={queue}, leases={leases}"))
        for event, successor in actions:
            transitions += 1
            if successor not in parent:
                parent[successor] = (state, event)
                frontier.append(successor)
        assert len(parent) < 500_000, "finite-state limit exceeded"
    return {"status": "DEADLOCK" if failures else "PASS", "batches": n, "slots": slots,
            "gated": gated, "mutant": mutant, "states_explored": len(parent),
            "transitions": transitions, "terminal_states": terminals,
            "slot_wait_states": waits, "deadlock_witness": failures[0] if failures else None}


parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
normal = [explore(n, q, gated) for n, q in [(3, 2), (4, 2), (6, 4)] for gated in [False, True]]
assert all(x["status"] == "PASS" for x in normal)
one_slot = explore(2, 1)
missing_flush = explore(1, 2, mutant="omit_final_flush")
early_publish = explore(2, 2, mutant="publish_before_copy_done")
early_release = explore(3, 2, mutant="release_after_rescue")
assert one_slot["status"] == missing_flush["status"] == "DEADLOCK"
assert early_publish["status"] == early_release["status"] == "COUNTEREXAMPLE"

# Concrete index contract: seven pairs in batches of 3,3,1 over two cyclic slots.
correct, wrong_from, wrong_count = [], [], []
for batch, start in enumerate(range(0, 7, 3)):
    count = min(3, 7 - start)
    correct.extend(range(start, start + count))
    wrong_from.extend(range((batch % 2) * 3, (batch % 2) * 3 + count))
    wrong_count.extend(range(start, start + 3))
assert correct == list(range(7)) and wrong_from[-1] == 0 and wrong_count[-2:] == [7, 8]

result = {"status": "BOUNDED_ADAPTER_MODEL_PASS_WITH_EXPECTED_COUNTEREXAMPLES",
          "normal_cases": normal,
          "counterexamples": {"one_slot_deferred_dispatch": one_slot, "missing_final_flush": missing_flush,
                              "publish_before_D2H_done": early_publish, "release_before_normal_RLE": early_release},
          "index_counterexamples": {"correct_global_IDs": correct, "slot_index_as_global_from": wrong_from,
                                    "fixed_full_batch_count_on_tail": wrong_count},
          "interpretation": "For this acquire-before-submit and next-submit-deferred CPU contract, Q=1 can deadlock, Q>=2 passed only the finite cases above. This is not a universal queue-size theorem.",
          "unproved": ["C++/OpenMP/CUDA memory ordering", "real pointer and stream behavior", "ABI sizes", "allocation or cancellation faults", "alignment correctness", "native race freedom", "performance"]}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": result["status"], "normal_states": sum(x["states_explored"] for x in normal),
                  "normal_cases": len(normal), "counterexamples": len(result["counterexamples"]) + 2}, indent=2))
