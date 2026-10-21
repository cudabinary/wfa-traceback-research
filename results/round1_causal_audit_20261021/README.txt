Round 1 causal audit: completed analysis and design, no native queue run

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

Continuity update: the protected local R2 MANIFEST.json now matches the
first audit and the handoff SHA256 exactly. Only 1 of 112 required inputs
was found in that protected tree; 111 remain missing there. This does not
complete raw restoration or permit a full raw replay. See restoration_check.json.
