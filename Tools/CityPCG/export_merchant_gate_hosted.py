"""Export review-only Merchant Gate source on the designated hosted Actions VM.

This is a separate entrypoint. It never calls or changes the Windows editor
guard. The workflow, not environment strings, provides actual isolation;
these environment checks prevent accidents, not deliberate impersonation.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import build_merchant_gate_procedural as gate
from audit_merchant_gate import audit_geometry


PROJECT = Path(__file__).resolve().parents[2]
REPOSITORY = 'zachrizzo/reflections'
REPOSITORY_ID = '1457160414'
WORKFLOW = '.github/workflows/merchant-gate-hosted-source.yml'
BRANCH = 'refs/heads/main'
WORKFLOW_REF = f'{REPOSITORY}/{WORKFLOW}@{BRANCH}'
OUTPUT = PROJECT / 'ci-merchant-gate-source'
MAX_WALL_SECONDS = 120
MAX_CPU_SECONDS = 90
MAX_ADDRESS_SPACE = 512 * 2**20
MAX_RSS = 256 * 2**20
MAX_FILE = 64 * 2**20
MAX_TOTAL_OUTPUT = 64 * 2**20
MIN_AVAILABLE_RAM = 1 * 2**30
MIN_FREE_DISK = 128 * 2**20
SHA_PATTERN = re.compile(r'[0-9a-f]{40}\Z')
DECIMAL_PATTERN = re.compile(r'[1-9][0-9]{0,19}\Z')


def hosted_context():
    """Reject non-hosted or mismatched contexts before geometry or output."""
    env = os.environ
    expected = {'GITHUB_ACTIONS':'true', 'RUNNER_ENVIRONMENT':'github-hosted',
                'RUNNER_OS':'Linux', 'GITHUB_REPOSITORY':REPOSITORY,
                'GITHUB_REPOSITORY_ID':REPOSITORY_ID, 'GITHUB_REF':BRANCH,
                'GITHUB_SERVER_URL':'https://github.com', 'GITHUB_WORKFLOW_REF':WORKFLOW_REF}
    if sys.platform != 'linux' or any(env.get(k) != value for k,value in expected.items()):
        raise RuntimeError('Not the designated GitHub-hosted Linux workflow context')
    event = env.get('GITHUB_EVENT_NAME')
    sha = env.get('GITHUB_SHA','')
    run_id = env.get('GITHUB_RUN_ID','')
    attempt = env.get('GITHUB_RUN_ATTEMPT','')
    if (event not in {'workflow_dispatch','push'} or not SHA_PATTERN.fullmatch(sha)
            or not DECIMAL_PATTERN.fullmatch(run_id) or not DECIMAL_PATTERN.fullmatch(attempt)):
        raise RuntimeError('Missing or invalid Actions event, SHA, run ID or attempt')
    workspace = env.get('GITHUB_WORKSPACE','')
    if not workspace or not Path(workspace).is_absolute():
        raise RuntimeError('Missing or invalid GitHub workspace')
    try:
        if Path(workspace).resolve(strict=True) != PROJECT:
            raise RuntimeError('GitHub workspace does not match this checkout')
    except OSError as exc:
        raise RuntimeError('Cannot resolve GitHub workspace') from exc
    return {'repository':REPOSITORY,'repository_id':REPOSITORY_ID,'commit':sha,
            'event':event,'run_id':run_id,'attempt':attempt,'workflow_ref':WORKFLOW_REF,
            'runner_os':env['RUNNER_OS'],'runner_environment':env['RUNNER_ENVIRONMENT'],
            'image_os':env.get('ImageOS','unknown'),'image_version':env.get('ImageVersion','unknown'),
            'python':sys.version.split()[0]}


def git(*args):
    result = subprocess.run(['git','-C',str(PROJECT),*args],stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,timeout=10,check=False)
    if result.returncode:
        raise RuntimeError('Git could not verify the hosted checkout')
    return result.stdout


def validate_push_payload(payload, sha):
    """A push may change only this workflow in one non-merge commit."""
    if not isinstance(payload,dict):
        raise RuntimeError('Missing push event payload')
    before,after = payload.get('before'),payload.get('after')
    if (not isinstance(before,str) or not SHA_PATTERN.fullmatch(before) or before=='0'*40
            or after != sha or payload.get('ref') != BRANCH or payload.get('forced') is not False
            or payload.get('created') is not False or payload.get('deleted') is not False
            or not isinstance(payload.get('repository'),dict)
            or payload['repository'].get('full_name') != REPOSITORY):
        raise RuntimeError('Push event is not an ordinary main-branch update')
    parent_line = git('rev-list','--parents','-n','1',sha).decode('ascii').strip().split()
    if parent_line != [sha,before]:
        raise RuntimeError('Push must contain one single-parent commit')
    changed = git('diff','--no-ext-diff','--no-renames','--name-only','-z',before,sha)
    if changed != WORKFLOW.encode('utf-8') + b'\0':
        raise RuntimeError('Push may change only the hosted workflow file')


def verify_revision(context):
    if git('rev-parse','--verify','HEAD').decode('ascii').strip() != context['commit']:
        raise RuntimeError('Checkout HEAD does not match the triggering commit')
    if context['event'] != 'push':
        return
    event_path,runner_temp = os.environ.get('GITHUB_EVENT_PATH',''),os.environ.get('RUNNER_TEMP','')
    if not event_path or not runner_temp:
        raise RuntimeError('Missing push event or runner temp path')
    try:
        event = Path(event_path).resolve(strict=True)
        temp = Path(runner_temp).resolve(strict=True)
        if not event.is_relative_to(temp) or event.stat().st_size > 2*2**20:
            raise RuntimeError('Push event path is outside runner temp or too large')
        with event.open('r',encoding='utf-8') as stream:
            payload = json.load(stream)
    except (OSError,ValueError) as exc:
        raise RuntimeError('Cannot inspect push event') from exc
    validate_push_payload(payload,context['commit'])


def input_paths():
    files = [Path(__file__).resolve().relative_to(PROJECT),
             Path('Tools/CityPCG/build_merchant_gate_procedural.py'),
             Path('Tools/CityPCG/test_build_merchant_gate_procedural.py'),
             Path('Tools/CityPCG/test_export_merchant_gate_hosted.py'),
             Path('Tools/CityPCG/audit_merchant_gate.py'),
             Path('Tools/CityPCG/extract_tile_frontages.py'),
             gate.MARKET_GUARD_PATH.relative_to(PROJECT),gate.REFERENCE.relative_to(PROJECT),
             Path(WORKFLOW)]
    files.extend(Path(relative) for _,relative,_ in gate.MATERIALS.values() if relative)
    if len(files) != len(set(files)):
        raise RuntimeError('Duplicate input path')
    return files


def file_info(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(256*1024),b''):
            sha.update(block)
    return {'sha256':sha.hexdigest(),'bytes':path.stat().st_size}


def pin_inputs():
    paths = input_paths()
    names = [p.as_posix() for p in paths]
    git('ls-files','--error-unmatch','--',*names)
    if git('status','--porcelain=v1','--untracked-files=no','--',*names):
        raise RuntimeError('One or more hosted inputs differ from the checkout')
    result = {}
    for relative in paths:
        path = PROJECT / relative
        if path.resolve(strict=True) != path or not path.is_file():
            raise RuntimeError('Missing or redirected hosted input')
        result[relative.as_posix()] = file_info(path)
    gate.validate_inputs()
    return result


def available_ram():
    with open('/proc/meminfo','r',encoding='ascii') as stream:
        for line in stream:
            fields = line.split()
            if fields and fields[0] == 'MemAvailable:' and len(fields) == 3 and fields[2] == 'kB':
                return int(fields[1])*1024
    raise RuntimeError('Cannot determine hosted available memory')


def apply_limits():
    """Linux process ceilings; called only after hosted-context validation."""
    import resource
    for kind,limit in ((resource.RLIMIT_AS,MAX_ADDRESS_SPACE),(resource.RLIMIT_FSIZE,MAX_FILE),
                       (resource.RLIMIT_CPU,MAX_CPU_SECONDS)):
        _,hard = resource.getrlimit(kind)
        target = min(limit,hard) if hard != resource.RLIM_INFINITY else limit
        if target <= 0:
            raise RuntimeError('Hosted resource limit is unusable')
        resource.setrlimit(kind,(target,target))
    def time_exceeded(_signum,_frame):
        raise RuntimeError('Hosted export exceeded its wall-clock limit')
    signal.signal(signal.SIGALRM,time_exceeded)
    signal.setitimer(signal.ITIMER_REAL,MAX_WALL_SECONDS)


def validate_resource_state(elapsed,ram,disk,rss):
    values = (elapsed,ram,disk,rss)
    if (not all(isinstance(value,(int,float)) and math.isfinite(value) and value >= 0 for value in values)
            or elapsed>MAX_WALL_SECONDS or ram<MIN_AVAILABLE_RAM or disk<MIN_FREE_DISK or rss>MAX_RSS):
        raise RuntimeError('Hosted export exceeded its time or resource guard')


class HostedGuard:
    def __init__(self):
        self.started = time.monotonic()
        self.min_ram = math.inf
        self.min_disk = math.inf
        self.peak_rss = 0
        self.check()

    def check(self):
        import resource
        elapsed = time.monotonic()-self.started
        ram = available_ram()
        disk = shutil.disk_usage(PROJECT).free
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024  # Linux reports KiB.
        self.min_ram,self.min_disk,self.peak_rss = min(self.min_ram,ram),min(self.min_disk,disk),max(self.peak_rss,rss)
        validate_resource_state(elapsed,ram,disk,rss)
        if OUTPUT.exists():
            if OUTPUT.resolve(strict=True) != OUTPUT or OUTPUT.parent != PROJECT:
                raise RuntimeError('Hosted output directory was redirected')
            total = 0
            for path in OUTPUT.rglob('*'):
                if path.is_symlink():
                    raise RuntimeError('Hosted output contains a redirect')
                if path.is_file():
                    total += path.stat().st_size
            if total > MAX_TOTAL_OUTPUT:
                raise RuntimeError('Hosted output exceeded its size cap')


def verify_mtl(path,texture_dir):
    materials = {}
    role = None
    with path.open('r',encoding='utf-8') as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == 'newmtl' and len(fields)==2 and fields[1].startswith('M_GLMedieval_'):
                role = fields[1][len('M_GLMedieval_'):]
                if role not in gate.MATERIALS or role in materials:
                    raise RuntimeError('Invalid or duplicate material role')
                materials[role] = {}
            elif role is not None and fields[0] in {'Kd','map_Kd'} and fields[0] not in materials[role]:
                materials[role][fields[0]] = fields[1:]
            else:
                raise RuntimeError('Unsupported material record')
    if set(materials) != set(gate.MATERIALS):
        raise RuntimeError('Material slots differ from the source palette')
    for role,(color,relative,expected_sha) in gate.MATERIALS.items():
        data = materials[role]
        expected_color = (1.,1.,1.) if relative else color
        try:
            actual_color = tuple(float(value) for value in data['Kd'])
        except (KeyError,ValueError) as exc:
            raise RuntimeError('Invalid material color') from exc
        if actual_color != expected_color:
            raise RuntimeError('Material diffuse color differs')
        if relative:
            filename = Path(relative).name
            if data.get('map_Kd') != ['Textures/'+filename] or gate.digest(texture_dir/filename) != expected_sha:
                raise RuntimeError('Material texture path or hash differs')
        elif 'map_Kd' in data:
            raise RuntimeError('Unexpected material texture')


def generate(context):
    apply_limits()
    guard = HostedGuard()
    verify_revision(context)
    inputs = pin_inputs()
    guard.check()
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise RuntimeError('Hosted output directory already exists')
    OUTPUT.mkdir()
    guard.check()
    mesh = gate.build_gate('full',checkpoint=guard.check)
    first_audit = audit_geometry(mesh.triangles())
    guard.check()
    if first_audit['status'] != 'passed':
        raise RuntimeError('In-memory continuous passage audit failed')
    textures = OUTPUT/'Textures'
    textures.mkdir()
    for _,relative,expected in gate.MATERIALS.values():
        if not relative:
            continue
        guard.check()
        with (PROJECT/relative).open('rb') as source,(textures/Path(relative).name).open('xb') as dest:
            for block in iter(lambda: source.read(256*1024),b''):
                dest.write(block)
                guard.check()
        if gate.digest(textures/Path(relative).name) != expected:
            raise RuntimeError('Copied texture hash mismatch')
    with (OUTPUT/'MerchantGate.mtl').open('x',encoding='utf-8',newline='\n') as stream:
        gate.write_mtl(stream)
    verify_mtl(OUTPUT/'MerchantGate.mtl',textures)
    guard.check()
    obj = OUTPUT/'MerchantGate.obj'
    with obj.open('x',encoding='utf-8',newline='\n') as stream:
        gate.write_obj(stream,mesh,checkpoint=guard.check)
    guard.check()
    with obj.open('r',encoding='utf-8') as stream:
        readback = gate.read_obj(stream)
    gate.verify_faces(readback,mesh.faces)
    second_audit = audit_geometry(face[1] for face in readback)
    guard.check()
    if second_audit != first_audit or second_audit['status'] != 'passed':
        raise RuntimeError('Read-back continuous passage audit failed or changed')
    if any(file_info(PROJECT/path) != expected for path,expected in inputs.items()):
        raise RuntimeError('Hosted inputs changed during export')
    outputs = {path.relative_to(OUTPUT).as_posix():file_info(path)
               for path in sorted(OUTPUT.rglob('*')) if path.is_file()}
    manifest = {'status':'unreviewed_hosted_source_not_gameplay','context':context,
                'inputs':inputs,'outputs':outputs,'audit':second_audit,
                'elapsed_seconds':time.monotonic()-guard.started,
                'min_available_memory_bytes':guard.min_ram,'min_free_disk_bytes':guard.min_disk,
                'peak_rss_bytes':guard.peak_rss,'max_address_space_bytes':MAX_ADDRESS_SPACE,
                'max_wall_seconds':MAX_WALL_SECONDS,'max_output_bytes':MAX_TOTAL_OUTPUT,
                'limitations':['Environment checks prevent accidents, not deliberate spoofing',
                               'Decorative windows are solid-backed', 'Not visually reviewed',
                               'No verified placement, collision, navigation, or Unreal import',
                               'Roof texture exposure is an unreviewed approximation']}
    guard.check()
    with (OUTPUT/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(manifest,stream,indent=2)
        stream.write('\n')
    guard.check()
    return OUTPUT


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        context = hosted_context()
        print(f'Completed review-only source bundle: {generate(context).name}')
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as exc:
        print(f'Hosted export refused or stopped: {exc}',file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
