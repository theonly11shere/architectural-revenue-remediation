"""Verify the V7.8.1 upgrade and its required commercial-architecture baseline."""
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent
manifest = json.loads((root / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
missing = [name for name in manifest['required_backend_files'] if not (root / name).is_file()]
if missing:
    raise SystemExit('Required backend files are missing:\n' + '\n'.join(missing))

mismatches = []
for name, expected in manifest['release_sha256'].items():
    path = root / name
    # Release entries are text files, hashed with LF line endings. Git may
    # check them out as CRLF on Windows; normalize only that difference.
    if not path.is_file() or hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != expected:
        mismatches.append(name)
if mismatches:
    raise SystemExit('Release files are missing or changed:\n' + '\n'.join(mismatches))

# Catch a mixed workflow baseline before importing the app or starting pytest.
from scan_execution_protocol import BUSINESS_TYPES, build_production_workflow
for business in BUSINESS_TYPES:
    plan = build_production_workflow({'business_type': business, 'business_type_confidence': .91})
    contract = plan.get('commercial_contract')
    if not isinstance(contract, dict) or contract.get('business_type') != business:
        raise SystemExit('Incompatible commercial workflow for business type: ' + business)

import main
assert main.SCANNER_ENGINE_VERSION == 'v7.8.1-universal-path-refinement'
assert main.API_VERSION == '7.8.1'
print('Runtime version and commercial workflow verified; running offline scanner/report checks.', flush=True)
raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q', *manifest['test_files'], '--disable-warnings'], cwd=root))
