"""Verify the initial curated snapshot. Does not run research experiments."""
from pathlib import Path
import hashlib, json
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'evidence/file_manifest.json').read_text())
for entry in manifest['files']:
    path=(root/entry['path']).resolve()
    if not path.is_relative_to(root):raise SystemExit('Unsafe manifest path')
    data=path.read_bytes()
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise SystemExit('File identity mismatch: '+entry['path'])
print('PASS: '+str(len(manifest['files']))+' curated files match their SHA256 values.')
