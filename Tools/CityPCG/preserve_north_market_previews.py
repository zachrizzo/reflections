"""Preserve one pinned North Market Blender diagnostic preview, without LFS.

Only the separately reviewed workflow may invoke this on a fresh hosted runner.
Its environment guard prevents accidents, not intentional environment spoofing.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sys

import preserve_north_market_hosted as base


WORKFLOW = '.github/workflows/preserve-north-market-previews.yml'
WORKFLOW_REF = f'{base.REPO}/{WORKFLOW}@refs/heads/main'
TARGET_REL = Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/DiagnosticPreviews')
TARGET = base.ROOT / TARGET_REL
ITEM = {'key': 'east_0a73564b', 'id': 14165382017, 'run': 43723954546,
        'size': 2639804,
        'sha256': '3a690aade02e668b800c5d49426d7b142d18556a953d7ed00737861a5086d096'}
MODEL = 'SM_GLMedieval_NorthMarketDetail_east_0a73564b'
FBX_SHA = '6a1f365d71f7cf88e1df766599f323311b600cc4000e558b98a78d9e7cf6b38d'
FILES = {'preview/eye_level.png': 'east_0a73564b_eye_level.png',
         'preview/three_quarter.png': 'east_0a73564b_three_quarter.png',
         'preview/preview.report.json': 'east_0a73564b_preview.report.json'}
NOTICE = b'''# North Market diagnostic previews\n\nThese are Blender source-asset previews of one North Market building, with\nartificial lighting and background. They are not in-game screenshots and do\nnot show a placed or approved Gray London building. See the accompanying\npreview report. Unreal placement, materials, collision and gameplay remain\nunverified.\n'''
SAFE_ERRORS = frozenset({'helper-contract', 'report-duplicate-key', 'report-fields',
                         'report-identity', 'report-geometry', 'report-constant',
                         'report-size', 'preview-inventory', 'preview-integrity',
                         'staged-paths', 'remote-advanced', 'target-exists-or-redirected',
                         'target-redirected', 'git-blob-integrity', 'disk-space',
                         'copied-integrity', 'commit-parent'})


def check_helper_contract():
    """Refuse drift in the shared downloader/inspector's exact pin contract."""
    if (len([x for x in base.ARTIFACTS if x == ITEM]) != 1
            or base.PREVIEW_FILES != FILES or base.PREVIEW_MODEL != MODEL
            or base.PREVIEW_FBX_SHA != FBX_SHA):
        raise RuntimeError('helper-contract')


def context():
    env = os.environ
    required = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'RUNNER_OS': 'Linux', 'GITHUB_REPOSITORY': base.REPO,
                'GITHUB_REPOSITORY_ID': '1457160414', 'GITHUB_REF': 'refs/heads/main',
                'GITHUB_WORKFLOW_REF': WORKFLOW_REF, 'GITHUB_SERVER_URL': 'https://github.com',
                'GITHUB_API_URL': 'https://api.github.com'}
    if sys.platform != 'linux' or any(env.get(k) != v for k, v in required.items()):
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


def push_before(payload, sha):
    if not isinstance(payload, dict):
        raise RuntimeError('push-payload')
    before = payload.get('before')
    if (not isinstance(before, str) or not base.SHA.fullmatch(before) or before == '0' * 40
            or payload.get('after') != sha or payload.get('ref') != 'refs/heads/main'
            or payload.get('forced') is not False or payload.get('created') is not False
            or payload.get('deleted') is not False or not isinstance(payload.get('repository'), dict)
            or payload['repository'].get('full_name') != base.REPO):
        raise RuntimeError('push-payload')
    return before


def check_push_shape(sha, before, parents, changed):
    if parents.decode('ascii').split() != [sha, before]:
        raise RuntimeError('push-parent')
    if changed != WORKFLOW.encode() + b'\0':
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
        if not path.is_relative_to(ctx['temp']) or path.stat().st_size > 2 * 2**20:
            raise RuntimeError('push-payload')
        with path.open(encoding='utf-8') as stream:
            before = push_before(json.load(stream), ctx['sha'])
        parents = git(env, 'rev-list', '--parents', '-n', '1', ctx['sha']).stdout
        changed = git(env, 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', before, ctx['sha']).stdout
        check_push_shape(ctx['sha'], before, parents, changed)


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError('report-duplicate-key')
        result[key] = value
    return result


def check_report(data):
    if not isinstance(data, dict) or set(data) != {
            'status', 'model', 'fbx_sha256', 'bounds_m', 'render',
            'placement', 'source_world_pivot_m', 'source_yaw_deg'}:
        raise RuntimeError('report-fields')
    expected = {
        'status': 'diagnostic only: visual/game approval pending',
        'model': MODEL, 'fbx_sha256': FBX_SHA,
        'render': 'Blender Cycles CPU, 8 samples, 720x480; artificial light and background',
        'placement': 'local source only; no Unreal placement or gameplay context',
    }
    if any(data.get(key) != value for key, value in expected.items()):
        raise RuntimeError('report-identity')

    def finite_number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def vector(value):
        return isinstance(value, (list, tuple)) and len(value) == 3 and all(map(finite_number, value))

    bounds = data['bounds_m']
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 3
            or any(not isinstance(pair, (list, tuple)) or len(pair) != 2
                   or not all(map(finite_number, pair)) or pair[0] > pair[1] for pair in bounds)
            or not vector(data['source_world_pivot_m'])
            or not finite_number(data['source_yaw_deg'])):
        raise RuntimeError('report-geometry')


def checked_preview(stage, hashes):
    if set(hashes) != set(FILES.values()):
        raise RuntimeError('preview-inventory')
    for name, digest in hashes.items():
        path = stage / name
        if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or path.is_symlink() or not path.is_file()
                or base.sha_file(path, 8 * 2**20)[1] != digest):
            raise RuntimeError('preview-integrity')
    report = (stage / FILES['preview/preview.report.json']).read_bytes()
    if len(report) > 128 * 1024:
        raise RuntimeError('report-size')
    check_report(json.loads(report, object_pairs_hook=unique_json,
                            parse_constant=lambda _: (_ for _ in ()).throw(RuntimeError('report-constant'))))


def checked_names(output):
    expected = {*(TARGET_REL / name for name in FILES.values()), TARGET_REL / 'README.md'}
    try:
        names = [Path(x.decode('utf-8')) for x in output.split(b'\0') if x]
    except UnicodeError:
        raise RuntimeError('staged-paths') from None
    if len(names) != len(expected) or set(names) != expected:
        raise RuntimeError('staged-paths')
    return sorted(path.as_posix() for path in expected)


def require_current_head(env, expected):
    if base.remote_head(env) != expected:
        raise RuntimeError('remote-advanced')


def check_target(exists, symlink, parent, expected_parent, tree_output):
    if exists or symlink or parent != expected_parent or tree_output:
        raise RuntimeError('target-exists-or-redirected')


def check_blobs(env, revision, hashes):
    for name, digest in hashes.items():
        rel = (TARGET_REL / name).as_posix()
        # A filter or LFS pointer cannot silently replace approved file bytes.
        blob = base.git(env, 'show', revision + ':' + rel).stdout
        if hashlib.sha256(blob).hexdigest() != digest:
            raise RuntimeError('git-blob-integrity')


def run(ctx):
    signal.signal(signal.SIGALRM, base.overall_timeout)
    signal.alarm(480)
    if shutil.disk_usage(ctx['temp']).free < 64 * 2**20:
        raise RuntimeError('disk-space')
    stage = ctx['temp'] / f"preserve-north-market-previews-{ctx['run']}-{ctx['attempt']}"
    stage.mkdir(mode=0o700)
    env = base.safe_git_env(stage)
    verify_revision(ctx, env)
    require_current_head(env, ctx['sha'])
    # Check both the sparse worktree and full committed tree before creating a
    # new directory. No existing destination may be reused or overwritten.
    check_target(TARGET.exists(), TARGET.is_symlink(), TARGET.parent.resolve(strict=True),
                 TARGET.parent, base.git(env, 'ls-tree', '--name-only', 'HEAD', '--', TARGET_REL.as_posix()).stdout)
    print('Downloading the pinned review ZIP and checking the three preview members.', flush=True)
    archive = base.download(ITEM, stage, os.environ['GH_TOKEN'])
    hashes = base.inspect_preview(archive, stage)
    checked_preview(stage, hashes)
    # download() checks the whole ZIP hash; inspect_preview() also checks the
    # original FBX hash and PNG dimensions. Only the three named files leave it.
    if TARGET.parent.resolve(strict=True) != TARGET.parent:
        raise RuntimeError('target-redirected')
    TARGET.mkdir(mode=0o755)
    if TARGET.resolve(strict=True) != TARGET:
        raise RuntimeError('target-redirected')
    for name, digest in hashes.items():
        with (stage / name).open('rb') as src, (TARGET / name).open('xb') as dst:
            shutil.copyfileobj(src, dst, 256 * 1024)
        if base.sha_file(TARGET / name, 8 * 2**20)[1] != digest:
            raise RuntimeError('copied-integrity')
    with (TARGET / 'README.md').open('xb') as stream:
        stream.write(NOTICE)
    hashes['README.md'] = hashlib.sha256(NOTICE).hexdigest()
    relpaths = [(TARGET_REL / name).as_posix() for name in hashes]
    base.git(env, 'add', '--', *relpaths)
    checked_names(base.git(env, 'diff', '--cached', '--name-only', '-z').stdout)
    check_blobs(env, '', hashes)
    require_current_head(env, ctx['sha'])
    base.git(env, '-c', 'user.name=github-actions[bot]', '-c',
             'user.email=41898282+github-actions[bot]@users.noreply.github.com',
             'commit', '-m', 'Preserve North Market Blender diagnostic previews')
    commit = base.git(env, 'rev-parse', 'HEAD').stdout.decode('ascii').strip()
    parents = base.git(env, 'rev-list', '--parents', '-n', '1', commit).stdout.decode('ascii').split()
    if not base.SHA.fullmatch(commit) or parents != [commit, ctx['sha']]:
        raise RuntimeError('commit-parent')
    checked_names(base.git(env, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit).stdout)
    check_blobs(env, commit, hashes)
    require_current_head(env, ctx['sha'])
    # Non-force push: an ordinary concurrent advance after this check rejects it.
    base.git(env, 'push', 'origin', commit + ':refs/heads/main')
    print(json.dumps({'status': 'pushed-diagnostic-only', 'commit': commit,
                      'source_commit': ctx['sha'], 'artifact': ITEM, 'sha256': hashes}))


def main():
    try:
        check_helper_contract()
        run(context())
    except Exception as exc:
        # Avoid exposing signed URLs, request data, or credentials in logs.
        print('Preview preservation refused or failed.', file=sys.stderr)
        reason = (exc.args[0] if type(exc) is RuntimeError and len(exc.args) == 1
                  and type(exc.args[0]) is str and exc.args[0] in SAFE_ERRORS
                  else base.safe_failure_reason(exc))
        print('Failure category: ' + reason, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
