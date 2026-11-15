"""Preserve one exact hosted tenancy FBX review ZIP with remote LFS readback.

The workflow controls the hosted runner. Environment checks prevent accidents,
not deliberate spoofing. No Unreal assets or existing review bundles change.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

import preserve_north_market_hosted as base


WORKFLOW = '.github/workflows/preserve-north-market-tenancy-fbx.yml'
WORKFLOW_REF = f'{base.REPO}/{WORKFLOW}@refs/heads/main'
TARGET_REL = Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/TenancyFBXReview')
TARGET = base.ROOT/TARGET_REL
ZIP_NAME = 'north_market_0a_tenancy_fbx_review.zip'
ZIP_REL = (TARGET_REL/ZIP_NAME).as_posix()
ITEM = {'id': 14169141736, 'run': 43732112368, 'size': 3226263,
        'sha256': 'e65a5ee3c694cc84647ebac96dc34bd48f4513cf9e22d6402f167136ebd0f79a',
        'head_sha': '585c82abe6ae99ed03678f17cdfcc81e489fbfe7',
        'name': 'north-market-tenancy-fbx-roundtrip-east-0a73564b'}
MODELS = {
    'overlay': {'name': 'SM_NorthMarket_0a_TenancyOverlay',
                'sha256': 'def07e18449cad312b7a808071ff569397e1288c656614d6d8bcc5dd6cb559cb',
                'vertices': 1704, 'polygons': 1278, 'slots': 8},
    'complete': {'name': 'SM_NorthMarket_0a_TenancyFull',
                 'sha256': '463667e61e1307b70856487a3523da2e660473ca1fa7a122c6d657d2a4f5960d',
                 'vertices': 14909, 'polygons': 11372, 'slots': 13},
}
SOURCE_OBJ = '5ca906f6b995d50cd956d89c9382856ba464366c23db6b93f0a886dfaec1a57f'
SOURCE_MANIFEST = 'a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095'
OVERLAY_OBJ = 'b67371709b3050ba31e2c31ad25488f5bc83cb0ef01bd050d47e62ff87da7eec'
COMBINED_OBJ = 'f52ba1bccfb11a986b78ced35a9924c437a6ccd350ac51dc90fef666731b2be5'
BASELINE_FBX = '314cbe152add14d5793bcc0070788ae60dabaa5525e8320bb39bca69c08698dc'
REPORT_FIELDS = ('status', 'kind', 'model', 'source_manifest_sha256', 'source_obj_sha256',
                 'source_plan_lf_sha256', 'source_mtl_sha256', 'overlay_obj_sha256',
                 'combined_obj_sha256', 'baseline_fbx_sha256', 'fbx_sha256', 'preview_run',
                 'preview_artifact', 'world_pivot_m', 'yaw_deg', 'source_axes', 'scene_unit',
                 'scene_unit_scale', 'blender_version', 'uv_layer', 'facts', 'textures', 'normal_repair')
SAFE_ERRORS = frozenset({'host-context', 'run-identity', 'workspace', 'missing-token', 'checkout-sha',
                         'dirty-checkout', 'unexpected-origin', 'persisted-http-credentials', 'push-payload',
                         'push-parent', 'push-path', 'remote-advanced', 'target-directory', 'target-exists',
                         'target-tracked', 'artifact-metadata', 'artifact-download', 'artifact-storage-host',
                         'artifact-size', 'artifact-integrity', 'archive-inventory', 'report-duplicate',
                         'report-identity', 'report-mismatch', 'fbx-integrity', 'staged-paths',
                         'lfs-attribute', 'precommit-integrity', 'commit-parent', 'report-integrity',
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


def push_before(payload, sha):
    if not isinstance(payload, dict):
        raise RuntimeError('push-payload')
    before = payload.get('before')
    if (not isinstance(before, str) or not base.SHA.fullmatch(before) or before == '0'*40
            or payload.get('after') != sha or payload.get('ref') != 'refs/heads/main'
            or payload.get('forced') is not False or payload.get('created') is not False
            or payload.get('deleted') is not False or not isinstance(payload.get('repository'), dict)
            or payload['repository'].get('full_name') != base.REPO):
        raise RuntimeError('push-payload')
    return before


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
            before = push_before(json.load(stream), ctx['sha'])
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
    # Never forward GitHub Authorization to the artifact storage host.
    request = urllib.request.Request(location, headers={'User-Agent': 'north-market-tenancy-fbx-preservation'})
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


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError('report-duplicate')
        result[key] = value
    return result


def check_reports(kind, export, verify):
    model = MODELS[kind]
    expected = {'status': 'review_only_no_unreal_approval', 'kind': kind, 'model': model['name'],
                'fbx_sha256': model['sha256'], 'source_obj_sha256': SOURCE_OBJ,
                'source_manifest_sha256': SOURCE_MANIFEST, 'overlay_obj_sha256': OVERLAY_OBJ,
                'combined_obj_sha256': COMBINED_OBJ, 'baseline_fbx_sha256': BASELINE_FBX,
                'preview_run': 43731156271, 'preview_artifact': 14167854997,
                'scene_unit': 'metres', 'scene_unit_scale': 1.0, 'source_axes': '+X entrance, +Z up',
                'blender_version': '4.5.3 LTS', 'uv_layer': 'UVMap', 'normal_repair': None}
    if (not isinstance(export, dict) or not isinstance(verify, dict)
            or export.get('phase') != 'export' or verify.get('phase') != 'verify'
            or any(verify.get(key) != value for key, value in expected.items())):
        raise RuntimeError('report-identity')
    if any(key not in export or key not in verify or export[key] != verify[key] for key in REPORT_FIELDS):
        raise RuntimeError('report-mismatch')
    facts = verify.get('facts')
    if (not isinstance(facts, dict) or facts.get('vertices') != model['vertices']
            or facts.get('polygons') != model['polygons'] or not isinstance(facts.get('slots'), list)
            or len(facts['slots']) != model['slots']):
        raise RuntimeError('report-identity')


def inspect_archive(path, stage):
    """Read only two exact reports and hash both FBX members without extracting."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 128:
            raise RuntimeError('archive-inventory')
        for kind, model in MODELS.items():
            raw = base.read_member(archive, f'{kind}/verify.report.json', 512*1024)
            old = base.read_member(archive, f'{kind}/export.report.json', 512*1024)
            verify = json.loads(raw, object_pairs_hook=unique_pairs)
            export = json.loads(old, object_pairs_hook=unique_pairs)
            check_reports(kind, export, verify)
            entry = base.safe_member(archive, f"{kind}/{model['name']}.fbx", 64*2**20)
            digest = hashlib.sha256()
            size = 0
            with archive.open(entry) as stream:
                for block in iter(lambda: stream.read(256*1024), b''):
                    size += len(block)
                    if size > entry.file_size:
                        raise RuntimeError('fbx-integrity')
                    digest.update(block)
            if size != entry.file_size or digest.hexdigest() != model['sha256']:
                raise RuntimeError('fbx-integrity')
            name = kind+'.verify.report.json'
            with (stage/name).open('xb') as stream:
                stream.write(raw)
            result[name] = hashlib.sha256(raw).hexdigest()
    return result


def expected_paths(data):
    want = {ZIP_REL, *(TARGET_REL/(key+'.verify.report.json') for key in MODELS)}
    want = {str(path).replace('\\', '/') for path in want}
    actual = [part.decode('utf-8') for part in data.split(b'\0') if part]
    if len(actual) != len(want) or set(actual) != want:
        raise RuntimeError('staged-paths')
    return sorted(want)


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
    stage = ctx['temp']/f"preserve-tenancy-fbx-{ctx['run']}-{ctx['attempt']}"
    stage.mkdir(mode=0o700)
    env = base.safe_git_env(stage)
    verify_revision(ctx, env)
    require_head(env, ctx['sha'])
    if (TARGET.is_symlink() or TARGET.resolve(strict=True) != TARGET
            or (TARGET/'README.md').is_symlink() or not (TARGET/'README.md').is_file()):
        raise RuntimeError('target-directory')
    names = [ZIP_NAME] + [key+'.verify.report.json' for key in MODELS]
    if any((TARGET/name).exists() or (TARGET/name).is_symlink() for name in names):
        raise RuntimeError('target-exists')
    relpaths = [(TARGET_REL/name).as_posix() for name in names]
    if base.git(env, 'ls-tree', '--name-only', 'HEAD', '--', *relpaths).stdout:
        raise RuntimeError('target-tracked')
    print('Downloading and verifying the pinned FBX review archive.', flush=True)
    archive = download(stage, os.environ['GH_TOKEN'])
    reports = inspect_archive(archive, stage)
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
    for name, digest in reports.items():
        rel = (TARGET_REL/name).as_posix()
        if (base.sha_file(TARGET/name, 512*1024)[1] != digest
                or hashlib.sha256(base.git(env, 'show', ':'+rel).stdout).hexdigest() != digest):
            raise RuntimeError('report-integrity')
    require_head(env, ctx['sha'])
    base.git(env, '-c', 'user.name=github-actions[bot]', '-c',
             'user.email=41898282+github-actions[bot]@users.noreply.github.com',
             'commit', '-m', 'Preserve review-only North Market tenancy FBX bundle')
    commit = base.git(env, 'rev-parse', 'HEAD').stdout.decode('ascii').strip()
    parents = base.git(env, 'rev-list', '--parents', '-n', '1', commit).stdout.decode('ascii').split()
    if not base.SHA.fullmatch(commit) or parents != [commit, ctx['sha']]:
        raise RuntimeError('commit-parent')
    expected_paths(base.git(env, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', commit).stdout)
    base.check_no_readback_alternates(base.readback_environment(env), ctx['sha'])
    print('Uploading the LFS object and verifying a fresh remote readback.', flush=True)
    base.git(env, 'lfs', 'push', '--object-id', 'origin', ITEM['sha256'])
    readback(env, stage, commit)
    require_head(env, ctx['sha'])
    base.git(env, 'push', 'origin', commit+':refs/heads/main')
    print(json.dumps({'status': 'pushed_review_only', 'commit': commit, 'artifact': ITEM,
                      'report_sha256': reports, 'lfs_remote_readback': 'verified'}))


def main():
    try:
        run(context())
    except Exception as exc:
        print('Tenancy FBX preservation refused or failed.', file=sys.stderr)
        reason = (exc.args[0] if type(exc) is RuntimeError and len(exc.args) == 1
                  and type(exc.args[0]) is str and exc.args[0] in SAFE_ERRORS
                  else base.safe_failure_reason(exc))
        print('Failure category: '+reason, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
