"""Finite abstract ownership model, not a CUDA implementation or proof.

Explore every interleaving of one serial GPU pipeline, bounded cyclic host slots,
one FIFO batch service, rescue followed by normal RLE, and final output readiness.
The deliberate early-release mutant must expose an overwritten reader.
"""
from collections import deque
from pathlib import Path
import json


def explore(n, capacity, early_release=False):
    # next_launch, GPU_active, device_result_pending, leases, payload_owners,
    # FIFO[(batch,slot)], CPU(batch,slot,stage), output_ready_bitmask
    initial = (0, -1, -1, (-1,) * capacity, (-1,) * capacity, (), (-1, -1, -1), 0)
    frontier = deque([initial])
    parent = {initial: None}
    transitions = 0
    terminals = 0
    blocked_snapshots = 0
    maximum_owned = 0
    maximum_pending = 0
    deadlocks = []

    def history(state, final):
        chain = [final]
        while parent[state] is not None:
            state, event = parent[state]
            chain.append(event)
        return list(reversed(chain))

    while frontier:
        state = frontier.popleft()
        nxt, gpu, pending, leases, payloads, queue, cpu, done = state
        maximum_owned = max(maximum_owned, sum(x >= 0 for x in leases))
        maximum_pending = max(maximum_pending, len(queue))
        candidates = []
        if gpu == -1 and pending == -1 and nxt < n:
            candidates.append((f"launch GPU batch {nxt}", (nxt + 1, nxt, pending, leases, payloads, queue, cpu, done)))
        if gpu >= 0:
            candidates.append((f"GPU batch {gpu} completed", (nxt, -1, gpu, leases, payloads, queue, cpu, done)))
        if pending >= 0:
            slot = pending % capacity
            if leases[slot] == -1:
                l2, p2 = list(leases), list(payloads)
                l2[slot] = p2[slot] = pending
                candidates.append((f"snapshot batch {pending} into slot {slot}",
                                   (nxt, gpu, -1, tuple(l2), tuple(p2), queue + ((pending, slot),), cpu, done)))
            else:
                blocked_snapshots += 1
        if cpu[0] == -1 and queue:
            batch, slot = queue[0]
            if payloads[slot] != batch or leases[slot] != batch:
                return {"status": "COUNTEREXAMPLE", "reason": "stale queued slot",
                        "history": history(state, f"consume batch {batch}, slot {slot} owned by {payloads[slot]}")}
            candidates.append((f"start rescue batch {batch} from slot {slot}",
                               (nxt, gpu, pending, leases, payloads, queue[1:], (batch, slot, 0), done)))
        if cpu[0] >= 0:
            batch, slot, stage = cpu
            if payloads[slot] != batch:
                return {"status": "COUNTEREXAMPLE", "reason": "payload overwritten while normal RLE still reads it",
                        "batches": n, "slots": capacity, "states_explored": len(parent),
                        "history": history(state, f"RLE batch {batch} reads slot {slot}, now containing batch {payloads[slot]}")}
            l2 = list(leases)
            if stage == 0:
                if early_release:
                    l2[slot] = -1
                candidates.append((f"rescue batch {batch} done" + ("; UNSAFE slot release" if early_release else ""),
                                   (nxt, gpu, pending, tuple(l2), payloads, queue, (batch, slot, 1), done)))
            else:
                assert not (done & (1 << batch)), "double output"
                if not early_release:
                    assert leases[slot] == batch
                    l2[slot] = -1
                # The mutant must not free a slot already reassigned to a later batch.
                candidates.append((f"normal RLE batch {batch} done; output ready; release slot",
                                   (nxt, gpu, pending, tuple(l2), payloads, queue, (-1, -1, -1), done | (1 << batch))))
        terminal = done == (1 << n) - 1
        if terminal:
            assert gpu == pending == -1 and not queue and cpu[0] == -1
            assert all(x == -1 for x in leases)
            terminals += 1
        elif not candidates:
            deadlocks.append(history(state, "unfinished deadlock"))
        for event, successor in candidates:
            transitions += 1
            if successor not in parent:
                parent[successor] = (state, event)
                frontier.append(successor)
        assert len(parent) < 1_000_000, "finite model state budget exceeded"
    return {"status": "PASS" if not deadlocks and terminals else "FAIL", "batches": n, "slots": capacity,
            "states_explored": len(parent), "transitions": transitions, "terminal_states": terminals,
            "unfinished_deadlocks": deadlocks, "snapshot_blocked_states": blocked_snapshots,
            "maximum_owned_slots": maximum_owned, "maximum_queued_batches": maximum_pending}


out = Path(__file__).resolve().parent
correct = [explore(n, capacity) for n, capacity in [(3, 1), (4, 2), (6, 4)]]
mutant = explore(3, 1, early_release=True)
assert all(x["status"] == "PASS" for x in correct)
assert mutant["status"] == "COUNTEREXAMPLE"
result = {
    "status": "BOUNDED_MODEL_PASS_WITH_EXPECTED_MUTANT_COUNTEREXAMPLE",
    "correct_models": correct, "unsafe_early_release": mutant,
    "scope": "Abstract serial GPU, cyclic host slots, one FIFO batch service, rescue then normal RLE; no real data, timings, CUDA calls or native worker execution.",
    "properties": ["no overwrite before last reader finishes", "bounded host slot ownership", "exactly-once output readiness", "all finite modeled interleavings drain without unfinished deadlock"],
    "unproved": ["CUDA/CPU memory-model ordering", "real pointer aliasing and metadata lifetimes", "allocation failures", "thread cancellation", "arbitrary penalties", "optimal alignment", "native race freedom", "performance"]
}
(out / "QUEUE_OWNERSHIP_MODEL.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
