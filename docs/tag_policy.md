# Future tag policy

No tags or releases are created by this setup. Tag only a reviewed, clean, already pushed commit after explicit authorization for the real event. Use immutable annotated tags, English messages, and the corresponding B2 checkpoint hash. A correction receives a new tag; do not move an existing tag.

Examples for a future authorized submission:

```text
git tag -a submission/example-venue/2027-01-15-v1 REVIEWED_COMMIT -m "Archive reviewed submission version 1; B2 checkpoint SHA256: CHECKPOINT_SHA256"
git push origin refs/tags/submission/example-venue/2027-01-15-v1
```

Use `accepted/example-venue/2027-03-01-v1` only after the acceptance is verified and the owner authorizes that tag. The venue and dates above are illustrative. Tags do not create a GitHub release or submit a manuscript.
