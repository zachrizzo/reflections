"""Pure checks for an isolated, review-only stronghold entrance scene."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = '.github/workflows/stronghold-entrance-review.yml'
REPO = 'zachrizzo/reflections'
KIT = Path('ArtDirection/CityPCG/MedievalOpening/StrongholdKit/Source')
SOURCE_HASHES = {
    KIT/'SM_GL1450_WatchGate.glb': '20fd9e3ee78b8d402f9f1a2573c40e89e13ad9961855611bf13514c43f700c0b',
    KIT/'SM_GL1450_StrongholdGateFrame.glb': 'fc89898bf9d9c322ffe33de3499f05d09996e1185ec22f52472141a570a6b8c2',
    KIT/'SM_GL1450_StrongholdPennantsOccupied.glb': '29169160e62034ed897abcf2ff582b3e39206f467ee10a12684d24291242d632',
    KIT/'SM_GL1450_StrongholdPennantsReclaimed.glb': '2bc517f911c4b152a4fe649bb5841b98e85f504c3d5087a307b9558499ad4475',
}
WATCH = Path('ArtDirection/MedievalLondon/MarketDressing/build_watch_gate.py')
MARKET = Path('ArtDirection/MedievalLondon/MarketDressing/build_market_dressing.py')
RECIPE = Path('ArtDirection/CityPCG/MedievalOpening/StrongholdKit/placement_recipe.json')
TEXT_HASHES = {
    WATCH: '74aa39108a9faec75156eaf24913dbd631827e385f0bd59681eafb26c04e1e24',
    MARKET: 'd78c583bb31dbd34e60e981a8b4259919a3aa30634a169352d0ab32fa7ca6271',
    RECIPE: '7bdbd64d7da38cfa551b426cb1ae56f6983dbb6e866aab7f5221fc6566b380df',
}
# Source-surface corridor only. In-game collision/navigation remain unverified.
CORRIDOR_LOW = (-1.25, -1.10, .06)
CORRIDOR_HIGH = (1.25, 1.10, 2.40)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(256*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def text_sha(path):
    data = Path(path).read_bytes().replace(b'\r\n', b'\n')
    if b'\r' in data:
        raise ValueError('Source text contains a lone carriage return')
    return hashlib.sha256(data).hexdigest()


def validate_inputs(root):
    root = Path(root).resolve(strict=True)
    for rel, digest in SOURCE_HASHES.items():
        path = root/rel
        if path.is_symlink() or path.resolve(strict=True) != path or not path.is_file() or sha(path) != digest:
            raise ValueError('Stronghold GLB differs from the pinned source')
        with path.open('rb') as stream:
            header = stream.read(12)
        if len(header) != 12 or struct.unpack('<4sII', header) != (b'glTF', 2, path.stat().st_size):
            raise ValueError('Source is not a complete GLB')
    for rel, digest in TEXT_HASHES.items():
        path = root/rel
        if path.is_symlink() or path.resolve(strict=True) != path or text_sha(path) != digest:
            raise ValueError('Stronghold source code or recipe differs from the pin')


def push_shape(event, sha, parents, paths):
    before = event.get('before') if isinstance(event, dict) else None
    if (not isinstance(before, str) or not re.fullmatch('[0-9a-f]{40}', before) or before == '0'*40
            or event.get('after') != sha or event.get('ref') != 'refs/heads/main'
            or event.get('deleted') is not False or event.get('created') is not False
            or event.get('forced') is not False or parents.decode('ascii').split() != [sha, before]
            or paths != WORKFLOW.encode()+b'\0'):
        raise ValueError('Expected one workflow-only non-merge main push')


def hosted_context():
    env = os.environ
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
                'GITHUB_REPOSITORY': REPO, 'GITHUB_REPOSITORY_ID': '1457160414',
                'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKFLOW_REF': f'{REPO}/{WORKFLOW}@refs/heads/main'}
    sha_value, run_id, attempt = (env.get(k, '') for k in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    if (sys.platform != 'linux' or any(env.get(k) != v for k, v in expected.items())
            or not re.fullmatch('[0-9a-f]{40}', sha_value) or not re.fullmatch('[1-9][0-9]*', run_id)
            or not re.fullmatch('[1-9][0-9]*', attempt)
            or env.get('GITHUB_EVENT_NAME') not in ('push', 'workflow_dispatch')):
        raise RuntimeError('Not the intended hosted main-only workflow')
    workspace = Path(env['GITHUB_WORKSPACE']).resolve(strict=True)
    temp = Path(env['RUNNER_TEMP']).resolve(strict=True)
    if workspace != ROOT or temp.is_relative_to(workspace):
        raise RuntimeError('Unexpected hosted workspace')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip()
    if head != sha_value:
        raise RuntimeError('Hosted checkout differs from workflow revision')
    if env['GITHUB_EVENT_NAME'] == 'push':
        path = Path(env['GITHUB_EVENT_PATH']).resolve(strict=True)
        if not path.is_relative_to(temp) or path.stat().st_size > 2*2**20:
            raise RuntimeError('Unexpected event path')
        event = json.loads(path.read_text(encoding='utf-8'))
        before = event.get('before', '')
        if not isinstance(before, str) or not re.fullmatch('[0-9a-f]{40}', before):
            raise RuntimeError('Invalid push base')
        parents = subprocess.check_output(['git', 'rev-list', '--parents', '-n', '1', sha_value], cwd=workspace)
        paths = subprocess.check_output(['git', 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z',
                                         before, sha_value], cwd=workspace)
        push_shape(event, sha_value, parents, paths)
    return workspace


def _sub(a, b):
    return tuple(a[i]-b[i] for i in range(3))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def triangle_intersects_box(points, low=CORRIDOR_LOW, high=CORRIDOR_HIGH):
    """Conservative separating-axis test for a triangle and a closed AABB."""
    if (len(points) != 3 or any(len(p) != 3 or any(not math.isfinite(x) for x in p) for p in points)
            or any(not math.isfinite(a) or not math.isfinite(b) or a >= b for a, b in zip(low, high))):
        raise ValueError('Non-finite or invalid triangle/box')
    center = tuple((a+b)/2 for a, b in zip(low, high))
    extent = tuple((b-a)/2 for a, b in zip(low, high))
    v = [_sub(p, center) for p in points]
    edges = [_sub(v[1], v[0]), _sub(v[2], v[1]), _sub(v[0], v[2])]
    axes = [(1.,0.,0.), (0.,1.,0.), (0.,0.,1.), _cross(edges[0], edges[1])]
    for edge in edges:
        axes.extend((_cross(edge, (1.,0.,0.)), _cross(edge, (0.,1.,0.)), _cross(edge, (0.,0.,1.))))
    for axis in axes:
        if sum(x*x for x in axis) < 1e-24:
            continue
        projected = [sum(p[i]*axis[i] for i in range(3)) for p in v]
        radius = sum(extent[i]*abs(axis[i]) for i in range(3))
        if min(projected) > radius+1e-9 or max(projected) < -radius-1e-9:
            return False
    return True
