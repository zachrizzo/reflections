"""Pinned sources and geometry guards for a hosted compound art review."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
REPO = 'zachrizzo/reflections'
WORKFLOW = '.github/workflows/compound-street-review.yml'
STREET_ZIP = Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/HostedStreetReview/north-market-street-illustrative-review.zip')
GATE_ZIP = Path('ArtDirection/CityPCG/MedievalOpening/StrongholdKit/HostedEntranceReview/stronghold_entrance_illustrative_review.zip')
TRIANGLE_HELPER = Path('Tools/CityPCG/stronghold_entrance_review_common.py')
TRIANGLE_HELPER_LF_SHA = 'b2021aaad7a1c11e30d8a1313934b944fbf1234f765159a1a24cf7da6620cf5e'
KIT_HELPER = Path('Tools/CityPCG/stronghold_entrance_review_hosted.py')
KIT_HELPER_LF_SHA = '43b1df583384d82fd1052eee2716fd1fb77ae0c9ee5f901fca91ec5dc374ad45'
ARCHIVES = {STREET_ZIP: (35334942, '021114d3c208f9aed1f4c6d874c24e6306050244ad17426d491d9106cf2be698'),
            GATE_ZIP: (1924747, 'd4aba22ac7ae358c853ed83bc5c7534021292cee0fd35fbcee040663d46b621d')}
MEMBERS = {
    'street': (STREET_ZIP, 'north_market_street_review.glb', '36c0f99f20230e7e2404d491d499c9b26dfce49d1dbd434194a3c6fad97227e2'),
    'occupied': (GATE_ZIP, 'StrongholdEntrance_Occupied.glb', '57573db81f6524e2adb2dbbe6b316c54b03c5b037df5eaff5ab7f249766dd9e4'),
    'reclaimed': (GATE_ZIP, 'StrongholdEntrance_Reclaimed.glb', '7c1032f6d8fcd8b24022c2c7799ea978fdd6f4a295fd5df710057b99650f41a4'),
    'supplies': (GATE_ZIP, 'ReusableAssets/SupplyStack.glb', '2f0bbf60e20f2f5284e71949209e5d66cc9a18d26805f2978d39f4d61b262eef'),
    'rack': (GATE_ZIP, 'ReusableAssets/GuardRack.glb', '9a8f27b2b0e703562c8bb3d3fd1d945c97f54122ac541cca9f5c10a5e4685aa0'),
}
MEMBER_SIZES = {'street': 18499916}
GATE_TRANSLATION = (32.2, -20.5, 0.)
GATE_YAW_DEG = 90.
CORRIDOR_LOW = (-5., -1.1, .06)
CORRIDOR_HIGH = (5., 1.1, 2.4)


def gate_to_world(point):
    angle = math.radians(GATE_YAW_DEG)
    x, y, z = point
    return (GATE_TRANSLATION[0]+math.cos(angle)*x-math.sin(angle)*y,
            GATE_TRANSLATION[1]+math.sin(angle)*x+math.cos(angle)*y,
            GATE_TRANSLATION[2]+z)


def world_to_gate(point):
    angle = math.radians(GATE_YAW_DEG)
    x, y, z = (point[i]-GATE_TRANSLATION[i] for i in range(3))
    return (math.cos(angle)*x+math.sin(angle)*y,
            -math.sin(angle)*x+math.cos(angle)*y, z)


def digest(path, limit):
    h = hashlib.sha256(); size = 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(256*1024), b''):
            size += len(block)
            if size > limit:
                raise ValueError('Input exceeds size limit')
            h.update(block)
    return size, h.hexdigest()


def validate_inputs(workspace):
    for rel, expected in ARCHIVES.items():
        path = workspace/rel
        if path.is_symlink() or path.resolve(strict=True) != path or digest(path, expected[0]) != expected:
            raise ValueError('Pinned review archive missing or changed')
    for rel, expected in ((TRIANGLE_HELPER, TRIANGLE_HELPER_LF_SHA), (KIT_HELPER, KIT_HELPER_LF_SHA)):
        helper = workspace/rel
        if helper.is_symlink() or helper.resolve(strict=True) != helper:
            raise ValueError('Review helper is redirected')
        data = helper.read_bytes().replace(b'\r\n', b'\n')
        if b'\r' in data or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Review helper changed')


def check_push_shape(event, sha, parents, changed):
    before = event.get('before') if isinstance(event, dict) else None
    if (not isinstance(before, str) or not re.fullmatch('[0-9a-f]{40}', before) or before == '0'*40
            or event.get('after') != sha or event.get('ref') != 'refs/heads/main'
            or event.get('created') is not False or event.get('deleted') is not False
            or event.get('forced') is not False or parents.decode('ascii').split() != [sha, before]
            or changed != WORKFLOW.encode()+b'\0'):
        raise ValueError('Expected exactly one workflow-only main commit')


def hosted_context():
    env = os.environ
    required = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
                'GITHUB_REPOSITORY': REPO, 'GITHUB_REPOSITORY_ID': '1457160414',
                'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKFLOW_REF': f'{REPO}/{WORKFLOW}@refs/heads/main'}
    sha, run, attempt = (env.get(key, '') for key in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    if (sys.platform != 'linux' or any(env.get(key) != value for key, value in required.items())
            or not re.fullmatch('[0-9a-f]{40}', sha) or not re.fullmatch('[1-9][0-9]*', run)
            or not re.fullmatch('[1-9][0-9]*', attempt)
            or env.get('GITHUB_EVENT_NAME') not in ('push', 'workflow_dispatch')):
        raise RuntimeError('Not the designated hosted review workflow')
    workspace = Path(env['GITHUB_WORKSPACE']).resolve(strict=True)
    temp = Path(env['RUNNER_TEMP']).resolve(strict=True)
    if workspace != ROOT or temp.is_relative_to(workspace):
        raise RuntimeError('Unexpected review workspace')
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=workspace, text=True).strip() != sha:
        raise RuntimeError('Unexpected checked-out revision')
    if env['GITHUB_EVENT_NAME'] == 'push':
        event_path = Path(env['GITHUB_EVENT_PATH']).resolve(strict=True)
        if not event_path.is_relative_to(temp) or event_path.stat().st_size > 2*2**20:
            raise RuntimeError('Unexpected event path')
        event = json.loads(event_path.read_text(encoding='utf-8'))
        before = event.get('before', '')
        if not isinstance(before, str) or not re.fullmatch('[0-9a-f]{40}', before):
            raise RuntimeError('Invalid push base')
        parents = subprocess.check_output(['git', 'rev-list', '--parents', '-n', '1', sha], cwd=workspace)
        changed = subprocess.check_output(['git', 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z',
                                           before, sha], cwd=workspace)
        check_push_shape(event, sha, parents, changed)
    return workspace, temp, run, attempt


def member(archive, name):
    entries = [entry for entry in archive.infolist() if entry.filename == name]
    if len(entries) != 1:
        raise ValueError('Missing or duplicated expected member')
    item = entries[0]
    mode = (item.external_attr >> 16) & 0o170000
    if (item.is_dir() or item.flag_bits & 1 or mode not in (0, stat.S_IFREG)
            or item.compress_type not in (0, 8) or not 0 < item.file_size <= 128*2**20):
        raise ValueError('Unsupported source archive member')
    return item


def extract_inputs(workspace, temp, run, attempt):
    validate_inputs(workspace)
    stage = temp/f'compound-review-{run}-{attempt}'
    stage.mkdir(mode=0o700)
    outputs = {}
    for key, (archive_rel, name, expected_sha) in MEMBERS.items():
        path = stage/(key+'.glb')
        with zipfile.ZipFile(workspace/archive_rel) as archive:
            if len(archive.infolist()) > 128:
                raise ValueError('Unexpected source archive inventory')
            item = member(archive, name)
            if key in MEMBER_SIZES and item.file_size != MEMBER_SIZES[key]:
                raise ValueError('Source member size changed')
            size = 0; h = hashlib.sha256()
            with archive.open(item) as source, path.open('xb') as dest:
                for block in iter(lambda: source.read(256*1024), b''):
                    size += len(block)
                    if size > item.file_size:
                        raise ValueError('Source member exceeds declared size')
                    h.update(block); dest.write(block)
            if size != item.file_size or h.hexdigest() != expected_sha or digest(path, item.file_size) != (size, expected_sha):
                raise ValueError('Source member failed integrity check')
        outputs[key] = path
    return stage, outputs
