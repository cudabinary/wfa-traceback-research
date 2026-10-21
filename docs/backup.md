# Backup operation

Bucket: `cudabinary-research-archive-20261021` (private, SSE-B2/AES256).
Paper prefix: `research-archive/papers/wfa-traceback/`.
Existing key scope: `research-archive/`. No key or permission expansion is needed. Prefix separation is organizational, not access-control isolation.

The raw catalogue is an immutable compressed JSONL object. Each row links a logical source identifier and SHA256 to exact existing global object versions, pack hashes, offsets, and lengths. Raw datasets are reused by reference rather than uploaded again. Korean and path-bearing originals are archive-only; their content is not rewritten.

The first content commit includes the source manifest and initial checkout hash manifest. A B2 snapshot manifest names that content commit, the raw-catalogue object version, and a full Git bundle. An audit commit adds the verified snapshot receipt. A final external checkpoint names the audit commit and its full Git bundle. This two-step design avoids self-referential commit or manifest hashes.

For future work, finish and verify an experiment before staging it, scan the exact staged payload, make an ordinary commit, and push only this repository's main branch. With the preserved archive operator tools, create a new immutable Git bundle and checkpoint below this paper prefix. Reuse existing raw content by hash. Download the checkpoint and bundle into a new directory, verify SHA256, and verify the recovered Git history and checkout. Record the immutable object version and checkpoint hash in the next audit commit. Never overwrite an uncertain upload or repeat a create/push/upload until the real remote state has been checked.

Budget applies once to the whole existing archive and both papers: 60,000,000,000 stored bytes, USD 5/month, and USD 5 initial upload/restore. Count every object version and all prior transfers. MAIN's ledger and this task's supplementary ledger must be combined before future transfers. Stop when an allowance or charge cannot be bounded. No recurring backup job was created.
