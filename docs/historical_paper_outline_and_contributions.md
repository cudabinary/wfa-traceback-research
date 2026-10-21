# Paper structure and scoped contribution sentences

1. **Problem:** full exact CIGAR needs history; private traceback reservation couples capacity, worker pool and exact CPU rescue.
2. **Observation:** cumulative generation can greatly exceed the retained ancestor closure. Reusing dead records changes feasible execution points, while collection still pays real work.
3. **Method:** separate E/C/w; guard appends; synchronize conservative root collection; bitmap/rank/staged in-place relocation and complete remapping; share baseline fixes across builds.
4. **Evaluation:** same-binary ON/OFF, lighter no-GC with an extra worker, bounded E/CPU alternatives, independent qualification, whole-job timing and separately instrumented retention/completion traces.
5. **Limits:** conditional ONT benefit; competitive/faster CPU alternatives, seen confirmation, unavailable sanitizer, measured reservations rather than residency, no selector or hardware claim.

## Contribution wording

- We realize existing active-root traceback reclamation inside private persistent GPU-worker arenas, with independent capacity guards and synchronized stable relocation of records and references for the tested exact global affine contract.
- Matched-capacity controls, including same-binary collection ON/OFF at identical allocated workspace, show how arena reuse removes exact CPU restarts and reduces whole-job completion after practical no-GC and CPU alternatives are considered.
- We provide source-specific preservation conditions, actual-helper boundary tests, measured generation/retention and allocation receipts that delimit the result and make the tested mechanism auditable.

These sentences claim concrete implementation and evidence. Reachability GC, WFA recurrence, persistent scheduling, BiWFA rescue, and capacity/concurrency tradeoffs are attributed to prior work. The manuscript does not claim discovery of those principles or universal superiority.
