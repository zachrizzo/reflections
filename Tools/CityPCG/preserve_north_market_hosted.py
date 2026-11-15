"""Preserve four exact North Market review ZIPs from a GitHub-hosted job.

No credentials or signed download URLs are logged. The workflow selects the
GitHub-hosted runner; environment checks guard accidents, not deliberate spoofing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile


ROOT=Path(__file__).resolve().parents[2]
REPO='zachrizzo/reflections'
CANONICAL_ORIGINS={'https://github.com/zachrizzo/reflections',
                   'https://github.com/zachrizzo/reflections.git'}
LFS_ENDPOINT='https://github.com/zachrizzo/reflections.git/info/lfs'
WORKFLOW='.github/workflows/preserve-north-market-hosted.yml'
WORKFLOW_REF=f'{REPO}/{WORKFLOW}@refs/heads/main'
TARGET_REL=Path('ArtDirection/CityPCG/MedievalOpening/WholeBuildings/NorthMarketDetailedObj/HostedFBXReview')
TARGET=ROOT/TARGET_REL
README=TARGET_REL/'README.md'
ARTIFACTS=(
    {'key':'east_0a73564b','id':14165382017,'run':43723954546,'size':2639804,
     'sha256':'3a690aade02e668b800c5d49426d7b142d18556a953d7ed00737861a5086d096'},
    {'key':'east_31c9ff1a','id':14165792197,'run':43723954546,'size':1460426,
     'sha256':'bf30b04ea539b92e3bc518f19e75ce13566ab6ebf622285db9e9a3a271541c9b'},
    {'key':'west_d08bbb3b','id':14165916795,'run':43723954546,'size':1322370,
     'sha256':'dff11277e5fed7d87ef008bf76188b3f7bd35178a12495b41005115a1b873391'},
    {'key':'west_736fd5c6','id':14165658843,'run':43724753596,'size':1564718,
     'sha256':'159538f2ceab546b41a7ac4b79895500029c2f80093ca2ff071ba593d251dfbe'},
)
PREVIEW_FILES={'preview/eye_level.png':'east_0a73564b_eye_level.png',
               'preview/three_quarter.png':'east_0a73564b_three_quarter.png',
               'preview/preview.report.json':'east_0a73564b_preview.report.json'}
PREVIEW_MODEL='SM_GLMedieval_NorthMarketDetail_east_0a73564b'
PREVIEW_FBX_SHA='6a1f365d71f7cf88e1df766599f323311b600cc4000e558b98a78d9e7cf6b38d'
SHA=re.compile(r'[0-9a-f]{40}\Z')
NUMBER=re.compile(r'[1-9][0-9]{0,19}\Z')


def context():
    env=os.environ
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':REPO,'GITHUB_REPOSITORY_ID':'1457160414',
              'GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW_REF':WORKFLOW_REF,
              'GITHUB_SERVER_URL':'https://github.com','GITHUB_API_URL':'https://api.github.com'}
    if sys.platform!='linux' or any(env.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('host-context')
    sha,run,attempt,event=(env.get(k,'') for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_EVENT_NAME'))
    if not SHA.fullmatch(sha) or not NUMBER.fullmatch(run) or not NUMBER.fullmatch(attempt) or event not in ('push','workflow_dispatch'):
        raise RuntimeError('run-identity')
    workspace,temp=env.get('GITHUB_WORKSPACE',''),env.get('RUNNER_TEMP','')
    if not workspace or not temp or not Path(workspace).is_absolute() or not Path(temp).is_absolute():
        raise RuntimeError('workspace')
    if Path(workspace).resolve(strict=True)!=ROOT or Path(temp).resolve(strict=True).is_relative_to(ROOT):
        raise RuntimeError('workspace')
    if not env.get('GH_TOKEN'):
        raise RuntimeError('missing-token')
    return {'sha':sha,'run':run,'attempt':attempt,'event':event,'temp':Path(temp).resolve(strict=True)}


def safe_git_env(stage):
    env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','GCM_'))
         and k.upper() not in {'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'}}
    askpass=stage/'askpass.sh'
    with askpass.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('#!/bin/sh\ncase "$1" in\n  *sername*) printf "%s\\n" x-access-token ;;\n  *assword*) printf "%s\\n" "$GH_TOKEN" ;;\n  *) exit 1 ;;\nesac\n')
    askpass.chmod(0o700)
    env.update({'GIT_ASKPASS':str(askpass),'GIT_TERMINAL_PROMPT':'0','GIT_LFS_SKIP_SMUDGE':'1',
                'GIT_TRACE':'0','GIT_CURL_VERBOSE':'0'})
    return env


def git(env,*args,allow_failure=False):
    command=['git','-C',str(ROOT),'-c','credential.helper=','-c','core.hooksPath=/dev/null',
             '-c','http.followRedirects=false','-c','lfs.url='+LFS_ENDPOINT,
             '-c','lfs.pushurl='+LFS_ENDPOINT,'-c','remote.origin.lfsurl='+LFS_ENDPOINT,
             '-c','remote.origin.lfspushurl='+LFS_ENDPOINT,*args]
    result=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)
    if result.returncode and not allow_failure:
        raise RuntimeError('git-command')
    return result


def push_before(payload,sha):
    if not isinstance(payload,dict):
        raise RuntimeError('push-payload')
    before=payload.get('before')
    if (not isinstance(before,str) or not SHA.fullmatch(before) or before=='0'*40
            or payload.get('after')!=sha or payload.get('ref')!='refs/heads/main'
            or payload.get('forced') is not False or payload.get('created') is not False
            or payload.get('deleted') is not False or not isinstance(payload.get('repository'),dict)
            or payload['repository'].get('full_name')!=REPO):
        raise RuntimeError('push-payload')
    return before


def check_push_shape(sha,before,parents,changed):
    if parents.decode('ascii').split()!=[sha,before]:
        raise RuntimeError('push-parent')
    if changed!=WORKFLOW.encode()+b'\0':
        raise RuntimeError('push-path')


def verify_revision(ctx,env):
    if git(env,'rev-parse','--verify','HEAD').stdout.decode('ascii').strip()!=ctx['sha']:
        raise RuntimeError('checkout-sha')
    if git(env,'status','--porcelain=v1','--untracked-files=all').stdout:
        raise RuntimeError('dirty-checkout')
    origins=git(env,'remote','get-url','--all','origin').stdout.decode('utf-8').splitlines()
    push_origins=git(env,'remote','get-url','--push','--all','origin').stdout.decode('utf-8').splitlines()
    if (len(origins)!=1 or origins[0] not in CANONICAL_ORIGINS
            or len(push_origins)!=1 or push_origins[0] not in CANONICAL_ORIGINS):
        raise RuntimeError('unexpected-origin')
    extra=git(env,'config','--get-regexp',r'^http\..*\.extraheader$',allow_failure=True)
    if extra.returncode not in (0,1) or extra.stdout:
        raise RuntimeError('persisted-http-credentials')
    if ctx['event']=='push':
        path=Path(os.environ.get('GITHUB_EVENT_PATH','')).resolve(strict=True)
        if not path.is_relative_to(ctx['temp']) or path.stat().st_size>2*2**20:
            raise RuntimeError('push-payload')
        with path.open(encoding='utf-8') as stream:
            payload=json.load(stream)
        before=push_before(payload,ctx['sha'])
        parents=git(env,'rev-list','--parents','-n','1',ctx['sha']).stdout
        changed=git(env,'diff','--no-ext-diff','--no-renames','--name-only','-z',before,ctx['sha']).stdout
        check_push_shape(ctx['sha'],before,parents,changed)


def remote_head(env):
    lines=git(env,'ls-remote','--exit-code','origin','refs/heads/main').stdout.decode('ascii').splitlines()
    if len(lines)!=1:
        raise RuntimeError('remote-main')
    parts=lines[0].split()
    if len(parts)!=2 or not SHA.fullmatch(parts[0]) or parts[1]!='refs/heads/main':
        raise RuntimeError('remote-main')
    return parts[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())


def api_request(path,token):
    url='https://api.github.com/repos/'+REPO+path
    return urllib.request.Request(url,headers={'Accept':'application/vnd.github+json',
        'Authorization':'Bearer '+token,'User-Agent':'north-market-review-preservation',
        'X-GitHub-Api-Version':'2022-11-28'})


def validate_metadata(data,item):
    if (not isinstance(data,dict) or data.get('id')!=item['id'] or data.get('expired') is not False
            or data.get('name')!='north-market-fbx-review-'+item['key'].replace('_','-')
            or data.get('size_in_bytes')!=item['size'] or data.get('digest')!='sha256:'+item['sha256']
            or not isinstance(data.get('workflow_run'),dict) or data['workflow_run'].get('id')!=item['run']):
        raise RuntimeError('artifact-metadata')


def storage_url(url):
    if not isinstance(url,str) or len(url)>8192:
        return False
    try:
        p=urllib.parse.urlsplit(url)
        host=(p.hostname or '').lower()
        return (p.scheme=='https' and p.username is None and p.password is None and p.port in (None,443)
                and not p.fragment and (host.endswith('.blob.core.windows.net')
                or host.endswith('.actions.githubusercontent.com') or host.endswith('.githubusercontent.com')))
    except ValueError:
        return False


def sha_file(path,limit):
    sha=hashlib.sha256(); size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(256*1024),b''):
            size+=len(block)
            if size>limit:
                raise RuntimeError('file-size')
            sha.update(block)
    return size,sha.hexdigest()


def download(item,stage,token):
    client=opener()
    with client.open(api_request(f"/actions/artifacts/{item['id']}",token),timeout=30) as response:
        raw=response.read(256*1024+1)
    if len(raw)>256*1024:
        raise RuntimeError('artifact-metadata')
    validate_metadata(json.loads(raw),item)
    try:
        client.open(api_request(f"/actions/artifacts/{item['id']}/zip",token),timeout=30)
        raise RuntimeError('missing-artifact-redirect')
    except urllib.error.HTTPError as exc:
        if exc.code!=302:
            raise RuntimeError('artifact-download') from None
        location=exc.headers.get('Location')
    if not storage_url(location):
        raise RuntimeError('artifact-storage-host')
    # A fresh request contains no GitHub Authorization header. Redirects are
    # disabled for both requests so credentials cannot cross origins.
    request=urllib.request.Request(location,headers={'User-Agent':'north-market-review-preservation'})
    path=stage/(item['key']+'.zip')
    sha=hashlib.sha256(); size=0
    with client.open(request,timeout=30) as response,path.open('xb') as dest:
        while True:
            block=response.read(256*1024)
            if not block: break
            size+=len(block)
            if size>item['size']:
                raise RuntimeError('artifact-size')
            sha.update(block); dest.write(block)
    if size!=item['size'] or sha.hexdigest()!=item['sha256'] or sha_file(path,item['size'])!=(size,item['sha256']):
        raise RuntimeError('artifact-integrity')
    return path


def safe_member(archive,name,limit):
    matches=[i for i in archive.infolist() if i.filename==name]
    if len(matches)!=1:
        raise RuntimeError('preview-member')
    entry=matches[0]
    mode=(entry.external_attr>>16)&0o170000
    if (entry.is_dir() or entry.flag_bits&1 or mode not in (0,stat.S_IFREG)
            or entry.compress_type not in (0,8) or entry.file_size<=0 or entry.file_size>limit):
        raise RuntimeError('preview-member')
    return entry


def read_member(archive,name,limit):
    entry=safe_member(archive,name,limit)
    with archive.open(entry) as stream:
        data=stream.read(limit+1)
        if len(data)!=entry.file_size or len(data)>limit:
            raise RuntimeError('preview-size')
    return data


def inspect_preview(zip_path,stage):
    with zipfile.ZipFile(zip_path) as archive:
        if len(archive.infolist())>256:
            raise RuntimeError('preview-inventory')
        preview_raw=read_member(archive,'preview/preview.report.json',128*1024)
        verify_raw=read_member(archive,PREVIEW_MODEL+'/verify.report.json',512*1024)
        preview=json.loads(preview_raw); verified=json.loads(verify_raw)
        if (preview.get('model')!=PREVIEW_MODEL or verified.get('model')!=PREVIEW_MODEL
                or verified.get('phase')!='verify' or preview.get('fbx_sha256')!=PREVIEW_FBX_SHA
                or verified.get('fbx_sha256')!=PREVIEW_FBX_SHA):
            raise RuntimeError('preview-report')
        fbx=safe_member(archive,PREVIEW_MODEL+'/'+PREVIEW_MODEL+'.fbx',64*2**20)
        sha=hashlib.sha256(); size=0
        with archive.open(fbx) as stream:
            for block in iter(lambda:stream.read(256*1024),b''):
                size+=len(block)
                if size>fbx.file_size: raise RuntimeError('preview-fbx-size')
                sha.update(block)
        if size!=fbx.file_size or sha.hexdigest()!=PREVIEW_FBX_SHA:
            raise RuntimeError('preview-fbx-hash')
        values={}
        for source,dest_name in PREVIEW_FILES.items():
            data=preview_raw if source.endswith('.json') else read_member(archive,source,8*2**20)
            if source.endswith('.png') and (len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n'
                    or data[12:16]!=b'IHDR' or struct.unpack('>II',data[16:24])!=(720,480)):
                raise RuntimeError('preview-png')
            dest=stage/dest_name
            with dest.open('xb') as stream: stream.write(data)
            values[dest_name]=hashlib.sha256(data).hexdigest()
        return values


def check_pointer(data,item):
    expected=(f"version https://git-lfs.github.com/spec/v1\noid sha256:{item['sha256']}\nsize {item['size']}\n").encode()
    if data!=expected:
        raise RuntimeError('lfs-pointer')


def run(ctx):
    signal.alarm(540)
    if shutil.disk_usage(ctx['temp']).free<256*2**20:
        raise RuntimeError('disk-space')
    stage=ctx['temp']/f"preserve-north-market-{ctx['run']}-{ctx['attempt']}"
    stage.mkdir()
    env=safe_git_env(stage)
    print('Checking checkout and main branch.',flush=True)
    verify_revision(ctx,env)
    if remote_head(env)!=ctx['sha']:
        raise RuntimeError('remote-advanced')
    if TARGET.is_symlink() or TARGET.resolve(strict=True)!=TARGET or not (ROOT/README).is_file():
        raise RuntimeError('target-directory')
    names=[item['key']+'.zip' for item in ARTIFACTS]+list(PREVIEW_FILES.values())
    if any((TARGET/name).exists() or (TARGET/name).is_symlink() for name in names):
        raise RuntimeError('target-exists')
    relpaths=[(TARGET_REL/name).as_posix() for name in names]
    # Check the tree as well as the worktree, even if a sparse pattern changes.
    if git(env,'ls-tree','--name-only','HEAD','--',*relpaths).stdout:
        raise RuntimeError('target-tracked')
    print('Checkout and fresh destination verified.',flush=True)
    token=os.environ['GH_TOKEN']
    print('Downloading and verifying the four pinned artifact ZIPs.',flush=True)
    paths={item['key']:download(item,stage,token) for item in ARTIFACTS}
    print('All four artifact ZIPs verified.',flush=True)
    print('Checking the selected diagnostic previews.',flush=True)
    preview_hashes=inspect_preview(paths['east_0a73564b'],stage)
    print('Diagnostic previews verified.',flush=True)
    for item in ARTIFACTS:
        if sha_file(paths[item['key']],item['size'])!=(item['size'],item['sha256']):
            raise RuntimeError('prestage-integrity')
    # Each approved destination is a fresh, explicit file; nothing is extracted
    # besides the three exact diagnostic preview members above.
    for name in names:
        source=paths[name[:-4]] if name.endswith('.zip') else stage/name
        with source.open('rb') as src,(TARGET/name).open('xb') as dst:
            shutil.copyfileobj(src,dst,256*1024)
    git(env,'lfs','install','--local','--skip-smudge','--skip-repo')
    git(env,'add','--',README.as_posix(),*relpaths)
    changed=git(env,'diff','--cached','--name-only','-z').stdout.split(b'\0')
    if sorted(x.decode('utf-8') for x in changed if x)!=sorted(relpaths):
        raise RuntimeError('staged-paths')
    for item in ARTIFACTS:
        rel=(TARGET_REL/(item['key']+'.zip')).as_posix()
        if git(env,'check-attr','filter','--',rel).stdout.strip()!=f'{rel}: filter: lfs'.encode():
            raise RuntimeError('lfs-attribute')
        check_pointer(git(env,'show',':'+rel).stdout,item)
        if sha_file(TARGET/(item['key']+'.zip'),item['size'])!=(item['size'],item['sha256']):
            raise RuntimeError('precommit-integrity')
    for name,digest in preview_hashes.items():
        rel=(TARGET_REL/name).as_posix()
        if (sha_file(TARGET/name,8*2**20)[1]!=digest
                or hashlib.sha256(git(env,'show',':'+rel).stdout).hexdigest()!=digest):
            raise RuntimeError('preview-stage-integrity')
    print('Staged LFS pointers and preview files verified.',flush=True)
    if remote_head(env)!=ctx['sha']:
        raise RuntimeError('remote-advanced')
    git(env,'-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit','-m','Preserve review-only North Market FBX bundles')
    commit=git(env,'rev-parse','HEAD').stdout.decode('ascii').strip()
    if not SHA.fullmatch(commit) or git(env,'rev-list','--parents','-n','1',commit).stdout.decode('ascii').split()!=[commit,ctx['sha']]:
        raise RuntimeError('commit-parent')
    oids=[item['sha256'] for item in ARTIFACTS]
    for item in ARTIFACTS:
        if sha_file(TARGET/(item['key']+'.zip'),item['size'])!=(item['size'],item['sha256']):
            raise RuntimeError('prepush-integrity')
    print('Uploading the four verified LFS objects.',flush=True)
    git(env,'lfs','push','--object-id','origin',*oids)
    print('LFS upload completed; checking remote readback.',flush=True)
    # Refetch only these LFS objects into a fresh store, then hash actual bytes.
    verify_store=stage/'lfs-readback'; verify_store.mkdir()
    includes=','.join((TARGET_REL/(item['key']+'.zip')).as_posix() for item in ARTIFACTS)
    git(env,'-c','lfs.storage='+str(verify_store),'-c','lfs.fetchrecentalways=false',
        'lfs','fetch','--refetch','--include='+includes,'--exclude=','origin',commit)
    for item in ARTIFACTS:
        oid=item['sha256']; path=verify_store/'objects'/oid[:2]/oid[2:4]/oid
        if sha_file(path,item['size'])!=(item['size'],oid):
            raise RuntimeError('lfs-readback')
    print('Remote LFS readback verified.',flush=True)
    if remote_head(env)!=ctx['sha']:
        raise RuntimeError('remote-advanced')
    # No force or lease override: a concurrent advance makes this push fail.
    print('Pushing the review-only commit to main.',flush=True)
    git(env,'push','origin',commit+':refs/heads/main')
    print(json.dumps({'status':'pushed-review-only','commit':commit,'source_commit':ctx['sha'],
                      'artifacts':[{k:item[k] for k in ('key','id','run','size','sha256')} for item in ARTIFACTS],
                      'preview_sha256':preview_hashes,'lfs_remote_readback':'verified'}))


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        run(context())
    except Exception:
        # Do not print exception text: HTTP and Git errors may contain tokens or signed URLs.
        print('Preservation refused or failed; no sensitive request details are logged.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
