# Verification and recovery

Run from the repository root:

```text
python tools/verify_manifest.py
```

This checks sizes and SHA256 values for the initial curated snapshot. It does not validate scientific claims, compile historical programs, rerun experiments, or treat old receipts as newly executed tests.

Typesetting sources are historical R2 sources. Direct rebuilding requires an already installed compatible TeX engine and fonts; no compiler was installed or new PDF build claimed. The preserved manuscript PDFs are the identity reference. WFA-GPU/WFA2 source archives and exact input archives must be restored through the catalogue before GPU replay. Historical harnesses depend on those headers/libraries and their recorded build flags. Do not infer that the selected C++ files alone are a complete build.

For a fresh recovery, obtain the immutable checkpoint and expected SHA256 from the coordinating verification report or a subsequent audited receipt. Use the existing restricted archive authentication outside Git. Download the checkpoint by its B2 file ID, verify its hash, then download its referenced Git bundle and verify that hash. Verify the bundle in a new empty repository, fetch its main branch, and compare the recovered HEAD and tracked file hashes. Do not restore over an original or active research directory.

For raw evidence, download and verify the referenced catalogue. Locate the desired source ID, download each exact B2 object version, verify the whole pack SHA256, concatenate the indicated extents in file-offset order, and compare the complete logical file SHA256 and size. Existing archive restore tools implement this process. Object names alone do not pin a version; use the recorded file ID.

The initial setup verifies remote manifests, both Git bundle recoveries, all tracked checkout files, and at least one historical representative file per paper reconstructed from a freshly downloaded existing global pack. It is not a complete raw-dataset restore or a different-physical-computer test.
