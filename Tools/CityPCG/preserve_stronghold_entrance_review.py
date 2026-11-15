"""Hosted preservation of one pinned illustrative stronghold source review."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

import preserve_north_market_hosted as base
import preserve_north_market_tenancy_fbx as guarded


WORKFLOW = '.github/workflows/preserve-stronghold-entrance-review.yml'
WORKFLOW_REF = f'{base.REPO}/{WORKFLOW}@refs/heads/main'
TARGET_REL = Path('ArtDirection/CityPCG/MedievalOpening/StrongholdKit/HostedEntranceReview')
TARGET = base.ROOT/TARGET_REL
ZIP_NAME = 'stronghold_entrance_illustrative_review.zip'
ZIP_REL = (TARGET_REL/ZIP_NAME).as_posix()
ITEM = {'id': 14170395738, 'run': 43734534399, 'size': 1924747,
        'sha256': 'd4aba22ac7ae358c853ed83bc5c7534021292cee0fd35fbcee040663d46b621d',
        'head_sha': '6613ca43ffe41a00515c24118c8d2de2f0b2a106',
        'name': 'stronghold-entrance-illustrative-review'}
FILES = {
    '01_gate_only.png': (536856, 'fba022b6a7c060bb0f0dfb4f1ae542dcc0a517268c4b7e7d46bf647b87756574'),
    '02_occupied_dressed.png': (540754, 'a6e105ba52fd3d655ea8b13166bf93b86f27c9f0f032d47251bc63f9b499b45c'),
    '03_reclaimed_dressed.png': (539583, '69cfc1494d344347cf84b9286b208e1311ff02ce51d277284a763126e82d0ade'),
    'build.report.json': (5571, '36d708d761b44fdcee344f17c0d026f0a517c11ffea8528bd9f9530285bf2707'),
    'verify.report.json': (4048, '753433982b8b2767e001c7bda475deab930d46335bf17243a7b284fc2f6de1ac'),
}
GLBS = {
    'ReusableAssets/PalisadeWing.glb': 'b9ecc35113c1c8fbd89b7f6e25053c130ba24de45b16b7d9f622e61a469b1ec8',
    'ReusableAssets/GuardRack.glb': '9a8f27b2b0e703562c8bb3d3fd1d945c97f54122ac541cca9f5c10a5e4685aa0',
    'ReusableAssets/SupplyStack.glb': '2f0bbf60e20f2f5284e71949209e5d66cc9a18d26805f2978d39f4d61b262eef',
    'ReusableAssets/WatchSconce.glb': 'c32868d94f965c7734ce629f0aa741aec0fd7cb9328b573d9f0ba7372775314e',
    'ReusableAssets/ClaimMarkerOccupied.glb': '321eafefc4f967c5180078f2939160ab813a40bbd79d3c6295061d38bbdc70e2',
    'ReusableAssets/ClaimMarkerReclaimed.glb': '4d7feb92261bbbee221b8df8b6ac89c7dd5b3ae7594f7b6afbcccfc3f3e9c90c',
    'StrongholdEntrance_Occupied.glb': '57573db81f6524e2adb2dbbe6b316c54b03c5b037df5eaff5ab7f249766dd9e4',
    'StrongholdEntrance_Reclaimed.glb': '7c1032f6d8fcd8b24022c2c7799ea978fdd6f4a295fd5df710057b99650f41a4',
}
CORRIDOR = [[-1.25, -1.1, .06], [1.25, 1.1, 2.4]]
SAFE_ERRORS = frozenset({'host-context', 'run-identity', 'workspace', 'missing-token', 'checkout-sha',
                         'dirty-checkout', 'unexpected-origin', 'persisted-http-credentials', 'push-payload',
                         'push-parent', 'push-path', 'remote-advanced', 'target-directory', 'target-exists',
                         'target-tracked', 'artifact-metadata', 'artifact-download', 'artifact-storage-host',
                         'artifact-size', 'artifact-integrity', 'archive-inventory', 'member-integrity',
                         'image-header', 'report-identity', 'report-mismatch', 'staged-paths',
                         'lfs-attribute', 'precommit-integrity', 'commit-parent', 'file-integrity',
                         'disk-space', 'lfs-readback', 'lfs-readback-cache-not-empty'})


def context():
    env = os.environ
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'Linux',
                'GITHUB_REPOSITORY': base.REPO, 'GITHUB_REPOSITORY_ID': '1457160414',
                'GITHUB_REF': 'refs/heads/main', 'GITHUB_WORKFLOW_REF': WORKFLOW_REF,
                'GITHUB_SERVER_URL': 'https://github.com', 'GITHUB_API_URL': 'https://api.github.com'}
    if sys.platform != 'linux' or any(env.get(k) != v for k, v in expected.items()):
        raise RuntimeError('host-context')
    sha, run, attempt, event = (env.get(k, '') for k in
                                ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_EVENT_NAME'))
    if (not base.SHA.fullmatch(sha) or not base.NUMBER.fullmatch(run)
            or not base.NUMBER.fullmatch(attempt) or event not in ('push', 'workflow_dispatch')):
        raise RuntimeError('run-identity')
    workspace, temp = env.get('GITHUB_WORKSPACE', ''), env.get('RUNNER_TEMP', '')
    if not workspace or not temp or not Path(workspace).is_absolute() or not Path(temp).is_absolute():
        raise RuntimeError('workspace')
    temp = Path(temp).resolve(strict=True)
    if Path(workspace).resolve(strict=True) != base.ROOT or temp.is_relative_to(base.ROOT):
        raise RuntimeError('workspace')
    if not env.get('GH_TOKEN'):
        raise RuntimeError('missing-token')
    return {'sha': sha, 'run': run, 'attempt': attempt, 'event': event, 'temp': temp}


def check_push_shape(sha, before, parents, changed):
    if parents.decode('ascii').split() != [sha, before]:
        raise RuntimeError('push-parent')
    if changed != WORKFLOW.encode()+b'\0':
        raise RuntimeError('push-path')


def verify_revision(ctx, env):
    git = base.git
    if git(env, 'rev-parse', '--verify', 'HEAD').stdout.decode('ascii').strip() != ctx['sha']:
        raise RuntimeError('checkout-sha')
    if git(env, 'status', '--porcelain=v1', '--untracked-files=all').stdout:
        raise RuntimeError('dirty-checkout')
    origins = git(env, 'remote', 'get-url', '--all', 'origin').stdout.decode('utf-8').splitlines()
    push_origins = git(env, 'remote', 'get-url', '--push', '--all', 'origin').stdout.decode('utf-8').splitlines()
    if (len(origins) != 1 or origins[0] not in base.CANONICAL_ORIGINS
            or len(push_origins) != 1 or push_origins[0] not in base.CANONICAL_ORIGINS):
        raise RuntimeError('unexpected-origin')
    extra = git(env, 'config', '--get-regexp', r'^http\..*\.extraheader$', allow_failure=True)
    if extra.returncode not in (0, 1) or extra.stdout:
        raise RuntimeError('persisted-http-credentials')
    if ctx['event'] == 'push':
        path = Path(os.environ.get('GITHUB_EVENT_PATH', '')).resolve(strict=True)
        if not path.is_relative_to(ctx['temp']) or path.stat().st_size > 2*2**20:
            raise RuntimeError('push-payload')
        with path.open(encoding='utf-8') as stream:
            before = guarded.push_before(json.load(stream), ctx['sha'])
        parents = git(env, 'rev-list', '--parents', '-n', '1', ctx['sha']).stdout
        changed = git(env, 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', before, ctx['sha']).stdout
        check_push_shape(ctx['sha'], before, parents, changed)


def validate_metadata(data):
    run = data.get('workflow_run') if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get('id') != ITEM['id'] or data.get('name') != ITEM['name']
            or data.get('expired') is not False or data.get('size_in_bytes') != ITEM['size']
            or data.get('digest') != 'sha256:'+ITEM['sha256'] or not isinstance(run, dict)
            or run.get('id') != ITEM['run'] or run.get('repository_id') != 1457160414
            or run.get('head_repository_id') != 1457160414 or run.get('head_branch') != 'main'
            or run.get('head_sha') != ITEM['head_sha']):
        raise RuntimeError('artifact-metadata')


def download(stage, token):
    client = base.opener()
    with client.open(base.api_request(f"/actions/artifacts/{ITEM['id']}", token), timeout=30) as response:
        data = response.read(256*1024+1)
    if len(data) > 256*1024:
        raise RuntimeError('artifact-metadata')
    validate_metadata(json.loads(data))
    try:
        client.open(base.api_request(f"/actions/artifacts/{ITEM['id']}/zip", token), timeout=30)
        raise RuntimeError('artifact-download')
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise RuntimeError('artifact-download') from None
        location = exc.headers.get('Location')
    if not base.storage_url(location):
        raise RuntimeError('artifact-storage-host')
    request = urllib.request.Request(location, headers={'User-Agent': 'stronghold-review-preservation'})
    path = stage/ZIP_NAME
    size = 0
    digest = hashlib.sha256()
    with client.open(request, timeout=30) as response, path.open('xb') as stream:
        while True:
            block = response.read(256*1024)
            if not block:
                break
            size += len(block)
            if size > ITEM['size']:
                raise RuntimeError('artifact-size')
            digest.update(block)
            stream.write(block)
    if (size != ITEM['size'] or digest.hexdigest() != ITEM['sha256']
            or base.sha_file(path, ITEM['size']) != (ITEM['size'], ITEM['sha256'])):
        raise RuntimeError('artifact-integrity')
    return path


def check_reports(build, verify):
    if (not isinstance(build, dict) or not isinstance(verify, dict)
            or build.get('status') != 'illustrative_source_review_not_in_game'
            or verify.get('status') != 'review_only_clean_glb_reimport'
            or build.get('corridor_box_m') != CORRIDOR or verify.get('corridor_box_m') != CORRIDOR
            or build.get('corridor_result') != 'no source triangle surface intersects the box'
            or build.get('preview_sha256') != {name: digest for name, (_, digest) in FILES.items() if name.endswith('.png')}
            or not isinstance(verify.get('assets'), dict) or set(verify['assets']) != {Path(path).stem for path in GLBS}):
        raise RuntimeError('report-identity')
    for path, digest in GLBS.items():
        name = Path(path).stem
        observed = verify['assets'][name]
        original = (build.get('scenes', {}).get(name.rsplit('_', 1)[1].lower())
                    if name.startswith('StrongholdEntrance_') else build.get('assets', {}).get(name))
        if (not isinstance(observed, dict) or not isinstance(original, dict)
                or observed.get('sha256') != digest or original.get('sha256') != digest):
            raise RuntimeError('report-mismatch')
        a, b = observed.get('facts'), original.get('facts')
        if (not isinstance(a, dict) or not isinstance(b, dict)
                or a.get('triangles') != b.get('triangles') or a.get('material_count') != b.get('material_count')
                or not isinstance(a.get('bounds_m'), list) or not isinstance(b.get('bounds_m'), list)
                or len(a['bounds_m']) != 2 or len(b['bounds_m']) != 2):
            raise RuntimeError('report-mismatch')
        for left, right in zip(a['bounds_m'], b['bounds_m']):
            if (not isinstance(left, list) or not isinstance(right, list) or len(left) != 3 or len(right) != 3
                    or any(type(x) not in (float, int) or not math.isfinite(x) for x in left+right)
                    or any(abs(x-y) > .01 for x, y in zip(left, right))):
                raise RuntimeError('report-mismatch')
    for state in ('StrongholdEntrance_Occupied', 'StrongholdEntrance_Reclaimed'):
        if verify['assets'][state]['facts']['triangles'] != 10366:
            raise RuntimeError('report-identity')


def inspect_archive(path, stage):
    copied = {}
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 128:
            raise RuntimeError('archive-inventory')
        raw = {}
        for name, (size, digest) in FILES.items():
            data = base.read_member(archive, name, 8*2**20 if name.endswith('.png') else 512*1024)
            if (size is not None and len(data) != size) or hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError('member-integrity')
            if name.endswith('.png') and (len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n'
                    or data[12:16] != b'IHDR' or struct.unpack('>II', data[16:24]) != (960, 540)):
                raise RuntimeError('image-header')
            raw[name] = data
        build = json.loads(raw['build.report.json'], object_pairs_hook=guarded.unique_pairs)
        verify = json.loads(raw['verify.report.json'], object_pairs_hook=guarded.unique_pairs)
        check_reports(build, verify)
        for name, expected in GLBS.items():
            entry = base.safe_member(archive, name, 64*2**20)
            digest = hashlib.sha256()
            size = 0
            with archive.open(entry) as stream:
                for block in iter(lambda: stream.read(256*1024), b''):
                    size += len(block)
                    if size > entry.file_size:
                        raise RuntimeError('member-integrity')
                    digest.update(block)
            if size != entry.file_size or digest.hexdigest() != expected:
                raise RuntimeError('member-integrity')
        for name, data in raw.items():
            with (stage/name).open('xb') as dest:
                dest.write(data)
            copied[name] = hashlib.sha256(data).hexdigest()
    return copied


def expected_paths(data):
    wanted = {ZIP_REL, *((TARGET_REL/name).as_posix() for name in FILES)}
    actual = [part.decode('utf-8') for part in data.split(b'\0') if part]
    if len(actual) != len(wanted) or set(actual) != wanted:
        raise RuntimeError('staged-paths')
    return sorted(wanted)


def smudge(env, stage, store, pointer):
    base.check_pointer(pointer, ITEM)
    ceiling = base.smudge_file_ceiling(ITEM['size'])
    output, errors = stage/'readback.zip', stage/'readback.stderr'
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    command = base.git_command(*base.readback_options(store), 'lfs', 'smudge', ZIP_REL)
    with output.open('xb') as dest:
        fd = os.open(str(errors), flags, 0o600)
        with os.fdopen(fd, 'w+b') as error_stream:
            process = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=dest,
                                       stderr=error_stream, start_new_session=True,
                                       preexec_fn=lambda: base.limit_child_files(ceiling))
            try:
                process.communicate(input=pointer, timeout=60)
                if process.returncode != 0:
                    raise RuntimeError('lfs-smudge-exit')
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
                try:
                    base.report_smudge_error(error_stream, process.returncode, ceiling)
                except Exception:
                    print('LFS smudge diagnostic: unknown', flush=True)
                raise
    return output


def readback(env, stage, commit):
    store = stage/'isolated-lfs-readback'
    store.mkdir()
    scoped = base.readback_environment(env)
    options = base.readback_options(store)
    base.check_readback_environment(base.git(scoped, *options, 'lfs', 'env').stdout, store)
    pointer = base.git(env, 'show', commit+':'+ZIP_REL).stdout
    base.check_pointer(pointer, ITEM)
    cached = store/'objects'/ITEM['sha256'][:2]/ITEM['sha256'][2:4]/ITEM['sha256']
    if cached.exists() or cached.is_symlink():
        raise RuntimeError('lfs-readback-cache-not-empty')
    output = smudge(scoped, stage, store, pointer)
    wanted = ITEM['size'], ITEM['sha256']
    if base.sha_file(output, ITEM['size']) != wanted or base.sha_file(cached, ITEM['size']) != wanted:
        raise RuntimeError('lfs-readback')


def require_head(env, expected):
    if base.remote_head(env) != expected:
        raise RuntimeError('remote-advanced')


def run(ctx):
    signal.signal(signal.SIGALRM, base.overall_timeout)
    signal.alarm(540)
    if shutil.disk_usage(ctx['temp']).free < 256*2**20:
        raise RuntimeError('disk-space')
    stage = ctx['temp']/f"preserve-stronghold-review-{ctx['run']}-{ctx['attempt']}"
    stage.mkdir(mode=0o700)
    env = base.safe_git_env(stage)
    verify_revision(ctx, env)
    require_head(env, ctx['sha'])
    if (TARGET.is_symlink() or TARGET.resolve(strict=True) != TARGET
            or (TARGET/'README.md').is_symlink() or not (TARGET/'README.md').is_file()):
        raise RuntimeError('target-directory')
    names = [ZIP_NAME, *FILES]
    if any((TARGET/name).exists() or (TARGET/name).is_symlink() for name in names):
        raise RuntimeError('target-exists')
    relpaths = [(TARGET_REL/name).as_posix() for name in names]
    if base.git(env, 'ls-tree', '--name-only', 'HEAD', '--', *relpaths).stdout:
        raise RuntimeError('target-tracked')
    print('Downloading and validating the pinned stronghold review.', flush=True)
    archive = download(stage, os.environ['GH_TOKEN'])
    copies = inspect_archive(archive, stage)
    for name in names:
        with (stage/name).open('rb') as source, (TARGET/name).open('xb') as dest:
            shutil.copyfileobj(source, dest, 256*1024)
    base.git(env, 'lfs', 'install', '--local', '--skip-smudge', '--skip-repo')
    base.git(env, 'add', '--', *relpaths)
    expected_paths(base.git(env, 'diff', '--cached', '--name-only', '-z').stdout)
    if base.git(env, 'check-attr', 'filter', '--', ZIP_REL).stdout.strip() != f'{ZIP_REL}: filter: lfs'.encode():
        raise RuntimeError('lfs-attribute')
    base.check_pointer(base.git(env, 'show', ':'+ZIP_REL).stdout, ITEM)
    if base.sha_file(TARGET/ZIP_NAME, ITEM['size']) != (ITEM['size'], ITEM['sha256']):
        raise RuntimeError('precommit-integrity')
    for name, digest in copies.items():
        rel = (TARGET_REL/name).as_posix()
        if (base.sha_file(TARGET/name, 8*2**20)[1] != digest
                or hashlib.sha256(base.git(env, 'show', ':'+rel).stdout).hexdigest() != digest):
            raise RuntimeError('file-integrity')
    require_head(env, ctx['sha'])
    base.git(env, '-c', 'user.name=github-actions[bot]', '-c',
             'user.email=41898282+github-actions[bot]@users.noreply.github.com',
             'commit', '-m', 'Preserve illustrative stronghold entrance review')
    commit = base.git(env, 'rev-parse', 'HEAD').stdout.decode('ascii').strip()
    parents = base.git(env, 'rev-list', '--parents', '-n', '1', commit).stdout.decode('ascii').split()
    if not base.SHA.fullmatch(commit) or parents != [commit, ctx['sha']]:
        raise RuntimeError('commit-parent')
    expected_paths(base.git(env, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit).stdout)
    base.check_no_readback_alternates(base.readback_environment(env), ctx['sha'])
    print('Uploading one LFS object and checking a fresh remote readback.', flush=True)
    base.git(env, 'lfs', 'push', '--object-id', 'origin', ITEM['sha256'])
    readback(env, stage, commit)
    require_head(env, ctx['sha'])
    base.git(env, 'push', 'origin', commit+':refs/heads/main')
    print(json.dumps({'status': 'pushed_review_only', 'commit': commit, 'artifact': ITEM,
                      'copied_sha256': copies, 'lfs_remote_readback': 'verified'}))


def main():
    try:
        run(context())
    except Exception as exc:
        print('Stronghold review preservation refused or failed.', file=sys.stderr)
        reason = (exc.args[0] if type(exc) is RuntimeError and len(exc.args) == 1
                  and type(exc.args[0]) is str and exc.args[0] in SAFE_ERRORS
                  else base.safe_failure_reason(exc))
        print('Failure category: '+reason, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    main()
