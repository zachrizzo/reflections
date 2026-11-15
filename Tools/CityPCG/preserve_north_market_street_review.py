"""Preserve one exact hosted street-review ZIP and its diagnostic images.

The companion workflow provides GitHub-hosted isolation. Context guards
prevent accidents, not deliberately spoofed environments. No signed URL,
credential, binary content or arbitrary error is printed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile


ROOT=Path(__file__).resolve().parents[2]
REPO='zachrizzo/reflections'
WORKFLOW='.github/workflows/preserve-north-market-street-review.yml'
TARGET_REL=Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/HostedStreetReview')
TARGET=ROOT/TARGET_REL
README=TARGET_REL/'README.md'
HELPER=Path('Tools/CityPCG/preserve_north_market_hosted.py')
HELPER_SHA='4fb89ffaf18072f21c6858170871c67322573ca41c5cf63f876e7c349c41bed2'
ARTIFACT={'id':14168477672,'run':43732127254,'size':35334942,
          'name':'north-market-street-illustrative-review',
          'sha256':'021114d3c208f9aed1f4c6d874c24e6306050244ad17426d491d9106cf2be698',
          'key':'north-market-street-illustrative-review'}
SOURCE_COMMIT='d57edf7f327568482844e23b0137875c89df8149'
COPIES=('street_eye_level.png','street_trestle.png','manifest.json','build.report.json')
ZIP_NAME=ARTIFACT['key']+'.zip'
TEXTURES={f'T_GLMedieval_{n}.png' for n in ('ClayTile','Fieldstone','GuildRubble',
          'LimePlaster','Oak','ShopGreen','ShopRed','WarmPlaster','WeatheredOak')}
ASSETS={f'ReusableAssets/{n}' for n in ('market_stall.glb','crate_group.glb','cask_group.glb',
        'handcart.glb','cargo.glb','LondonMarketProps.mtl','trestle.obj','bowl_a.obj','ale_stake.obj')}
ASSETS|={f'ReusableAssets/Tenancies/{n}' for n in ('tenancies_overlay.obj','tenancies.report.json','NorthMarketDetail.mtl')}
ASSETS|={f'ReusableAssets/Tenancies/Textures/{n}' for n in TEXTURES}
OUTPUTS=ASSETS|{'north_market_street_review.blend','north_market_street_review.glb',
                 'street_eye_level.png','street_trestle.png'}
MEMBERS=OUTPUTS|{'manifest.json','build.report.json'}
SHA40=re.compile(r'[0-9a-f]{40}\Z')
SHA256=re.compile(r'[0-9a-f]{64}\Z')


def digest(path,limit):
    h=hashlib.sha256(); size=0
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(256*1024),b''):
            size+=len(block)
            if size>limit: raise ValueError('file-size')
            h.update(block)
    return size,h.hexdigest()


def context():
    e=os.environ
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':REPO,'GITHUB_REPOSITORY_ID':'1457160414','GITHUB_REF':'refs/heads/main',
              'GITHUB_WORKFLOW_REF':f'{REPO}/{WORKFLOW}@refs/heads/main',
              'GITHUB_SERVER_URL':'https://github.com','GITHUB_API_URL':'https://api.github.com'}
    if sys.platform!='linux' or any(e.get(k)!=v for k,v in expected.items()): raise RuntimeError('context')
    sha,run,attempt,event=(e.get(k,'') for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_EVENT_NAME'))
    if (not SHA40.fullmatch(sha) or not re.fullmatch(r'[1-9][0-9]{0,19}',run)
            or not re.fullmatch(r'[1-9][0-9]{0,19}',attempt) or event not in ('push','workflow_dispatch')):
        raise RuntimeError('identity')
    workspace,temp=e.get('GITHUB_WORKSPACE',''),e.get('RUNNER_TEMP','')
    if not workspace or not temp or not Path(workspace).is_absolute() or not Path(temp).is_absolute():
        raise RuntimeError('workspace')
    if Path(workspace).resolve(strict=True)!=ROOT or Path(temp).resolve(strict=True).is_relative_to(ROOT):
        raise RuntimeError('workspace')
    if not e.get('GH_TOKEN'): raise RuntimeError('missing-token')
    return {'sha':sha,'run':run,'attempt':attempt,'event':event,'temp':Path(temp).resolve(strict=True)}


def load_helper():
    path=ROOT/HELPER
    if path.is_symlink() or digest(path,2**20)[1]!=HELPER_SHA: raise RuntimeError('helper-pin')
    spec=importlib.util.spec_from_file_location('pinned_market_preserver',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def check_push_shape(sha,before,parents,changed):
    if parents!=[sha,before] or changed!=WORKFLOW.encode()+b'\0': raise RuntimeError('push-shape')


def verify_revision(h,ctx,env):
    if h.git(env,'rev-parse','--verify','HEAD').stdout.decode('ascii').strip()!=ctx['sha']:
        raise RuntimeError('checkout')
    if h.git(env,'status','--porcelain=v1','--untracked-files=all').stdout: raise RuntimeError('dirty')
    origins=h.git(env,'remote','get-url','--all','origin').stdout.decode().splitlines()
    pushes=h.git(env,'remote','get-url','--push','--all','origin').stdout.decode().splitlines()
    if len(origins)!=1 or origins[0] not in h.CANONICAL_ORIGINS or len(pushes)!=1 or pushes[0] not in h.CANONICAL_ORIGINS:
        raise RuntimeError('origin')
    extra=h.git(env,'config','--get-regexp',r'^http\..*\.extraheader$',allow_failure=True)
    if extra.returncode not in (0,1) or extra.stdout: raise RuntimeError('extraheader')
    if ctx['event']=='push':
        path=Path(os.environ.get('GITHUB_EVENT_PATH','')).resolve(strict=True)
        if not path.is_relative_to(ctx['temp']) or path.stat().st_size>2*2**20: raise RuntimeError('event')
        payload=json.loads(path.read_text(encoding='utf-8')); before=h.push_before(payload,ctx['sha'])
        parents=h.git(env,'rev-list','--parents','-n','1',ctx['sha']).stdout.decode('ascii').split()
        changed=h.git(env,'diff','--no-ext-diff','--no-renames','--name-only','-z',before,ctx['sha']).stdout
        check_push_shape(ctx['sha'],before,parents,changed)


def check_metadata(data):
    if (not isinstance(data,dict) or data.get('id')!=ARTIFACT['id'] or data.get('name')!=ARTIFACT['name']
            or data.get('size_in_bytes')!=ARTIFACT['size'] or data.get('digest')!='sha256:'+ARTIFACT['sha256']
            or data.get('expired') is not False or not isinstance(data.get('workflow_run'),dict)
            or data['workflow_run'].get('id')!=ARTIFACT['run']
            or data['workflow_run'].get('repository_id')!=1457160414
            or data['workflow_run'].get('head_repository_id')!=1457160414
            or data['workflow_run'].get('head_branch')!='main'
            or data['workflow_run'].get('head_sha')!=SOURCE_COMMIT): raise RuntimeError('artifact-metadata')


def download(h,stage,token):
    client=h.opener()
    with client.open(h.api_request(f"/actions/artifacts/{ARTIFACT['id']}",token),timeout=30) as response:
        raw=response.read(256*1024+1)
    if len(raw)>256*1024: raise RuntimeError('metadata-size')
    check_metadata(json.loads(raw))
    try:
        client.open(h.api_request(f"/actions/artifacts/{ARTIFACT['id']}/zip",token),timeout=30)
        raise RuntimeError('missing-redirect')
    except urllib.error.HTTPError as exc:
        if exc.code!=302: raise RuntimeError('artifact-download') from None
        location=exc.headers.get('Location')
    if not h.storage_url(location): raise RuntimeError('storage-host')
    request=urllib.request.Request(location,headers={'User-Agent':'north-market-street-preservation'})
    path=stage/ZIP_NAME; sha=hashlib.sha256(); size=0
    with client.open(request,timeout=60) as response,path.open('xb') as dest:
        for block in iter(lambda:response.read(256*1024),b''):
            size+=len(block)
            if size>ARTIFACT['size']: raise RuntimeError('artifact-size')
            sha.update(block); dest.write(block)
    if size!=ARTIFACT['size'] or sha.hexdigest()!=ARTIFACT['sha256'] or digest(path,size)!=(size,ARTIFACT['sha256']):
        raise RuntimeError('artifact-integrity')
    return path


def validate_members(entries):
    if len(entries)>128: raise ValueError('zip-inventory')
    seen=set(); files={}; allowed_dirs=set()
    for name in MEMBERS:
        parts=PurePosixPath(name).parts
        allowed_dirs.update('/'.join(parts[:i])+'/' for i in range(1,len(parts)))
    for entry in entries:
        name=entry.filename; raw=name[:-1] if name.endswith('/') else name
        if ('\\' in name or '\x00' in name or ':' in name or PurePosixPath(name).is_absolute()
                or any(p in ('','.','..') for p in raw.split('/')) or name in seen):
            raise ValueError('zip-path')
        seen.add(name); mode=(entry.external_attr>>16)&0o170000
        if mode not in (0,stat.S_IFREG,stat.S_IFDIR) or entry.flag_bits&1: raise ValueError('zip-mode')
        if entry.is_dir():
            if name not in allowed_dirs: raise ValueError('zip-directory')
            continue
        if (name not in MEMBERS or entry.compress_type not in (0,8) or entry.file_size<=0
                or entry.file_size>160*2**20): raise ValueError('zip-member')
        files[name]=entry
    if set(files)!=MEMBERS or sum(i.file_size for i in files.values())>200*2**20:
        raise ValueError('zip-inventory')
    return files


def read_small(archive,entry,limit):
    if entry.file_size>limit: raise ValueError('report-size')
    with archive.open(entry) as stream: data=stream.read(limit+1)
    if len(data)!=entry.file_size or len(data)>limit: raise ValueError('report-size')
    return data


def check_png_header(prefix):
    if (len(prefix)<24 or prefix[:8]!=b'\x89PNG\r\n\x1a\n' or prefix[12:16]!=b'IHDR'
            or struct.unpack('>II',prefix[16:24])!=(1024,576)):
        raise ValueError('preview-png')


def check_reports(manifest,report,report_sha):
    if (not isinstance(manifest,dict) or not isinstance(report,dict)
            or manifest.get('status')!='review-only; no Unreal placement or gameplay validation'
            or report.get('status')!='illustrative review only; not a playable or map-approved scene'
            or manifest.get('commit')!=SOURCE_COMMIT or report.get('commit')!=SOURCE_COMMIT
            or manifest.get('build_report_sha256')!=report_sha
            or manifest.get('output_sha256')!=report.get('files')
            or not isinstance(report.get('files'),dict) or set(report['files'])!=OUTPUTS):
        raise ValueError('report-content')
    if any(not isinstance(x,str) or not SHA256.fullmatch(x) for x in report['files'].values()):
        raise ValueError('report-hash')
    facts=manifest.get('independent_glb_reimport')
    if (not isinstance(facts,dict) or type(facts.get('meshes')) is not int or facts['meshes']<10
            or type(facts.get('triangles')) is not int or not 0<facts['triangles']<300000):
        raise ValueError('report-reimport')


def inspect_archive(path,stage):
    """Verify every manifest-listed byte stream; copy only the four small outputs."""
    with zipfile.ZipFile(path) as archive:
        entries=validate_members(archive.infolist())
        if any(entries[name].file_size>8*2**20 for name in ('street_eye_level.png','street_trestle.png')):
            raise ValueError('preview-size')
        manifest_raw=read_small(archive,entries['manifest.json'],2*2**20)
        report_raw=read_small(archive,entries['build.report.json'],4*2**20)
        manifest=json.loads(manifest_raw); report=json.loads(report_raw)
        check_reports(manifest,report,hashlib.sha256(report_raw).hexdigest())
        output_hashes={}
        for name in sorted(OUTPUTS):
            sha=hashlib.sha256(); size=0; prefix=b''
            dest=(stage/name).open('xb') if name in COPIES else None
            try:
                with archive.open(entries[name]) as src:
                    for block in iter(lambda:src.read(256*1024),b''):
                        size+=len(block)
                        if size>entries[name].file_size: raise ValueError('member-size')
                        if len(prefix)<24: prefix=(prefix+block)[:24]
                        sha.update(block)
                        if dest: dest.write(block)
            finally:
                if dest: dest.close()
            if size!=entries[name].file_size or sha.hexdigest()!=report['files'][name]:
                raise ValueError('member-hash')
            if name.endswith('.png') and name in COPIES:
                check_png_header(prefix)
            if name in COPIES: output_hashes[name]=sha.hexdigest()
        for name,data in (('manifest.json',manifest_raw),('build.report.json',report_raw)):
            with (stage/name).open('xb') as stream: stream.write(data)
            output_hashes[name]=hashlib.sha256(data).hexdigest()
    return output_hashes


def isolated_readback(h,env,stage,commit,rel):
    store=stage/'isolated-lfs-readback'; store.mkdir()
    scoped=h.readback_environment(env); options=h.readback_options(store)
    h.check_readback_environment(h.git(scoped,*options,'lfs','env').stdout,store)
    pointer=h.git(env,'show',commit+':'+rel).stdout; h.check_pointer(pointer,ARTIFACT)
    cached=store/'objects'/ARTIFACT['sha256'][:2]/ARTIFACT['sha256'][2:4]/ARTIFACT['sha256']
    if cached.exists() or cached.is_symlink(): raise RuntimeError('cache-not-empty')
    output=stage/'isolated-lfs-output'; errpath=stage/'isolated-lfs-stderr'
    flags=os.O_RDWR|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    with output.open('xb') as sink:
        fd=os.open(str(errpath),flags,0o600)
        with os.fdopen(fd,'w+b') as errors:
            process=subprocess.Popen(h.git_command(*options,'lfs','smudge',rel),env=scoped,
                stdin=subprocess.PIPE,stdout=sink,stderr=errors,start_new_session=True,
                preexec_fn=lambda:h.limit_child_files(h.smudge_file_ceiling(ARTIFACT['size'])))
            try:
                process.communicate(input=pointer,timeout=120)
                if process.returncode!=0: raise RuntimeError('smudge-exit')
            except BaseException:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                process.wait(timeout=5)
                try: h.report_smudge_error(errors,process.returncode,h.SMUDGE_FILE_CEILING)
                except Exception: print('LFS smudge diagnostic: unknown',flush=True)
                raise
    expected=(ARTIFACT['size'],ARTIFACT['sha256'])
    if digest(output,ARTIFACT['size'])!=expected or digest(cached,ARTIFACT['size'])!=expected:
        raise RuntimeError('lfs-readback')


def overall_timeout(_signum,_frame):
    raise TimeoutError('overall-timeout')


def run(ctx):
    signal.signal(signal.SIGALRM,overall_timeout)
    signal.alarm(840)
    if shutil.disk_usage(ctx['temp']).free<512*2**20: raise RuntimeError('disk-space')
    stage=ctx['temp']/f"preserve-street-review-{ctx['run']}-{ctx['attempt']}"; stage.mkdir(mode=0o700)
    h=load_helper(); env=h.safe_git_env(stage)
    print('Checking checkout and fresh destination.',flush=True)
    verify_revision(h,ctx,env)
    if h.remote_head(env)!=ctx['sha']: raise RuntimeError('remote-advanced')
    if TARGET.is_symlink() or TARGET.resolve(strict=True)!=TARGET or not (ROOT/README).is_file():
        raise RuntimeError('target')
    names=[ZIP_NAME,*COPIES]; rels=[(TARGET_REL/name).as_posix() for name in names]
    if any((TARGET/name).exists() or (TARGET/name).is_symlink() for name in names): raise RuntimeError('target-exists')
    if h.git(env,'ls-tree','--name-only','HEAD','--',*rels).stdout: raise RuntimeError('target-tracked')
    h.check_no_readback_alternates(h.readback_environment(env),ctx['sha'])
    print('Downloading and verifying the pinned scene archive.',flush=True)
    archive=download(h,stage,os.environ['GH_TOKEN'])
    print('Checking exact archive members, images and reports.',flush=True)
    copied=inspect_archive(archive,stage)
    for name in names:
        with (stage/name).open('rb') as src,(TARGET/name).open('xb') as dst: shutil.copyfileobj(src,dst,256*1024)
    h.git(env,'lfs','install','--local','--skip-smudge','--skip-repo')
    h.git(env,'add','--',README.as_posix(),*rels)
    changed=h.git(env,'diff','--cached','--name-only','-z').stdout.split(b'\0')
    if sorted(x.decode('utf-8') for x in changed if x)!=sorted(rels): raise RuntimeError('staged-paths')
    zip_rel=(TARGET_REL/ZIP_NAME).as_posix()
    if h.git(env,'check-attr','filter','--',zip_rel).stdout.strip()!=f'{zip_rel}: filter: lfs'.encode():
        raise RuntimeError('lfs-attribute')
    h.check_pointer(h.git(env,'show',':'+zip_rel).stdout,ARTIFACT)
    if digest(TARGET/ZIP_NAME,ARTIFACT['size'])!=(ARTIFACT['size'],ARTIFACT['sha256']): raise RuntimeError('zip-copy')
    for name,sha in copied.items():
        rel=(TARGET_REL/name).as_posix()
        if digest(TARGET/name,8*2**20)[1]!=sha or hashlib.sha256(h.git(env,'show',':'+rel).stdout).hexdigest()!=sha:
            raise RuntimeError('staged-copy')
    if h.remote_head(env)!=ctx['sha']: raise RuntimeError('remote-advanced')
    h.git(env,'-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com',
          'commit','-m','Preserve illustrative North Market street review')
    commit=h.git(env,'rev-parse','HEAD').stdout.decode('ascii').strip()
    if not SHA40.fullmatch(commit) or h.git(env,'rev-list','--parents','-n','1',commit).stdout.decode().split()!=[commit,ctx['sha']]:
        raise RuntimeError('commit-parent')
    if digest(TARGET/ZIP_NAME,ARTIFACT['size'])!=(ARTIFACT['size'],ARTIFACT['sha256']):
        raise RuntimeError('prepush-integrity')
    print('Uploading and independently reading back the LFS archive.',flush=True)
    h.git(env,'lfs','push','--object-id','origin',ARTIFACT['sha256'])
    isolated_readback(h,env,stage,commit,zip_rel)
    if h.remote_head(env)!=ctx['sha']: raise RuntimeError('remote-advanced')
    print('LFS readback verified; pushing the review-only commit.',flush=True)
    h.git(env,'push','origin',commit+':refs/heads/main')
    print(json.dumps({'status':'pushed-review-only','commit':commit,'source_commit':ctx['sha'],
                      'archive_sha256':ARTIFACT['sha256'],'copied_sha256':copied,'lfs_remote_readback':'verified'}))


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try: run(context())
    except Exception:
        print('Street review preservation failed; no request details are logged.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
