"""Preserve complete logs losslessly without committing terminal whitespace."""
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = []
for path in sorted(root.rglob('*.log')):
    original = path.read_bytes()
    archived = gzip.compress(original, mtime=0)
    assert gzip.decompress(archived) == original
    target = path.with_suffix(path.suffix + '.gz')
    target.write_bytes(archived)
    manifest.append(dict(path=str(target.relative_to(root)), original_bytes=len(original),
                         original_sha256=hashlib.sha256(original).hexdigest(),
                         gzip_sha256=hashlib.sha256(archived).hexdigest()))
    path.unlink()
existing = root / 'log-manifest.json'
prior = json.loads(existing.read_text()) if existing.exists() else []
combined = {row['path']: row for row in [*prior, *manifest]}
existing.write_text(json.dumps(list(combined.values()), indent=2) + '\n')
print(f'{len(manifest)} logs compressed and round-trip verified')
