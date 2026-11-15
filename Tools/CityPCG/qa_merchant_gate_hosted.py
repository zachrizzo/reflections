"""Independent hosted-only Merchant Gate source QA and flat-color previews.

The GitHub-hosted workflow supplies isolation. Environment checks prevent
accidental local execution but are not attestation against deliberate spoofing.
No Unreal, Blender, model generation, GPU, or external Python package is used.
"""
import argparse
from array import array
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import zlib


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'ci-merchant-gate-source'
OUTPUT = ROOT/'ci-merchant-gate-qa'
REPO = 'zachrizzo/reflections'
WORKFLOW = '.github/workflows/merchant-gate-hosted-source.yml'
WORKFLOW_REF = f'{REPO}/{WORKFLOW}@refs/heads/main'
TEXTURES = {'Fieldstone':'T_GLMedieval_Fieldstone.png', 'WarmPlaster':'T_GLMedieval_WarmPlaster.png',
            'Oak':'T_GLMedieval_Oak.png', 'WeatheredOak':'T_GLMedieval_WeatheredOak.png',
            'ClayTile':'T_GLMedieval_ClayTile.png'}
COLORS = {'Fieldstone':(.46,.40,.32), 'WarmPlaster':(.64,.56,.43), 'Oak':(.15,.088,.05),
          'WeatheredOak':(.21,.16,.11), 'ClayTile':(.23,.104,.07),
          'LeadedGlass':(.045,.075,.080), 'Lead':(.055,.055,.050)}
INPUTS = {'Tools/CityPCG/export_merchant_gate_hosted.py','Tools/CityPCG/build_merchant_gate_procedural.py',
          'Tools/CityPCG/test_build_merchant_gate_procedural.py','Tools/CityPCG/test_export_merchant_gate_hosted.py',
          'Tools/CityPCG/audit_merchant_gate.py','Tools/CityPCG/extract_tile_frontages.py',
          'ArtDirection/CityPCG/MedievalOpening/MarketDressingKit/build_market_dressing.py',
          'ArtDirection/CityPCG/MedievalOpening/Landmarks/MerchantGate/References/merchant_gate_imagegen_v1.png',
          WORKFLOW} | {'ArtDirection/CityPCG/MedievalOpening/Textures/'+name for name in TEXTURES.values()}
GENERATED = {'MerchantGate.obj','MerchantGate.mtl'} | {'Textures/'+name for name in TEXTURES.values()}
BASELINE_RUN = {'run_id':'43721087489','artifact_id':'14164940841',
                'archive_sha256':'54e24a40c833ca18a195ee0fce293cd16d458ae047630c506ffa15b7ab0ae150'}
BASELINE_HASHES = {
    'MerchantGate.obj':'e340cac42ef998101e892d27f66fd86f75deba405399cbffa37f7f9072d6911d',
    'MerchantGate.mtl':'e7e47f6c109444295db0711ed3bc25cb2a9aa54d9b38a54a778839bdda494fb5',
    'Textures/T_GLMedieval_ClayTile.png':'4276741826d160b3c00bd3d053eb174849b328a76ecd22caa01f1cfc3445afaf',
    'Textures/T_GLMedieval_Fieldstone.png':'845a6082959cf5429e024eb86d05db087114b963cb1170533a4c989701cf03b1',
    'Textures/T_GLMedieval_Oak.png':'30f2d82d684242c658fdfe217b26d1c9aa680c240a187ea81cea0308ff20159a',
    'Textures/T_GLMedieval_WarmPlaster.png':'9e070704a80237ba6c17e35392f6060672710af53127565b066682ab246350d5',
    'Textures/T_GLMedieval_WeatheredOak.png':'b6dd5807706308ffabb22f9afcf2e45836c4ae34c9f0951397c92989dcf46425',
}
QA_CODE = ('Tools/CityPCG/qa_merchant_gate_hosted.py','Tools/CityPCG/test_qa_merchant_gate_hosted.py')
SHA = re.compile(r'[0-9a-f]{40}\Z')
RUN_ID = re.compile(r'[1-9][0-9]{0,19}\Z')
MAX_SECONDS = 120
MAX_MEMORY = 512*2**20
MAX_RSS = 256*2**20
MAX_FILE = 16*2**20
MAX_TRIANGLES = 20000


def hosted_context():
    env=os.environ
    required={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':REPO,'GITHUB_REPOSITORY_ID':'1457160414',
              'GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW_REF':WORKFLOW_REF,
              'GITHUB_SERVER_URL':'https://github.com'}
    if sys.platform!='linux' or any(env.get(k)!=v for k,v in required.items()):
        raise RuntimeError('Not the designated GitHub-hosted Linux context')
    sha,run,attempt,event=(env.get(k,'') for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_EVENT_NAME'))
    if not SHA.fullmatch(sha) or not RUN_ID.fullmatch(run) or not RUN_ID.fullmatch(attempt) or event not in {'push','workflow_dispatch'}:
        raise RuntimeError('Invalid GitHub run identity')
    workspace=env.get('GITHUB_WORKSPACE','')
    if not workspace or not Path(workspace).is_absolute() or Path(workspace).resolve(strict=True)!=ROOT:
        raise RuntimeError('Invalid GitHub workspace')
    return {'repository':REPO,'commit':sha,'run_id':run,'attempt':attempt,'event':event,
            'workflow_ref':WORKFLOW_REF,'runner_environment':'github-hosted','runner_os':'Linux',
            'image_os':env.get('ImageOS','unknown'),'image_version':env.get('ImageVersion','unknown'),
            'python':sys.version.split()[0]}


def git(*args):
    result=subprocess.run(['git','-C',str(ROOT),*args],stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=10,check=False)
    if result.returncode:
        raise RuntimeError('Git could not verify the checkout')
    return result.stdout


def verify_revision(context):
    sha=context['commit']
    if git('rev-parse','--verify','HEAD').decode('ascii').strip()!=sha:
        raise RuntimeError('Checkout does not match the triggering commit')
    if context['event']!='push':
        return
    event_path,temp=os.environ.get('GITHUB_EVENT_PATH',''),os.environ.get('RUNNER_TEMP','')
    if not event_path or not temp:
        raise RuntimeError('Missing push event path')
    path=Path(event_path).resolve(strict=True)
    if not path.is_relative_to(Path(temp).resolve(strict=True)) or path.stat().st_size>2*2**20:
        raise RuntimeError('Unsafe push event path')
    with path.open(encoding='utf-8') as stream:
        payload=json.load(stream)
    before=payload.get('before')
    if (not isinstance(before,str) or not SHA.fullmatch(before) or before=='0'*40
            or payload.get('after')!=sha or payload.get('ref')!='refs/heads/main'
            or payload.get('created') is not False or payload.get('deleted') is not False
            or payload.get('forced') is not False or not isinstance(payload.get('repository'),dict)
            or payload['repository'].get('full_name')!=REPO):
        raise RuntimeError('Invalid workflow push')
    if git('rev-list','--parents','-n','1',sha).decode('ascii').strip().split()!=[sha,before]:
        raise RuntimeError('Push must be a single-parent commit')
    if git('diff','--no-ext-diff','--no-renames','--name-only','-z',before,sha)!=WORKFLOW.encode()+b'\0':
        raise RuntimeError('Push may change only the workflow file')


def apply_limits():
    import resource
    for kind,limit in ((resource.RLIMIT_AS,MAX_MEMORY),(resource.RLIMIT_FSIZE,MAX_FILE),(resource.RLIMIT_CPU,90)):
        _,hard=resource.getrlimit(kind)
        cap=min(limit,hard) if hard!=resource.RLIM_INFINITY else limit
        if cap<=0:
            raise RuntimeError('Unusable process limit')
        resource.setrlimit(kind,(cap,cap))
    def timeout(_sig,_frame):
        raise RuntimeError('Hosted QA exceeded the time limit')
    signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,MAX_SECONDS)


def validate_resources(elapsed,available,disk,rss):
    values=(elapsed,available,disk,rss)
    if (not all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in values)
            or elapsed>MAX_SECONDS or available<2**30 or disk<128*2**20 or rss>MAX_RSS):
        raise RuntimeError('Hosted QA exceeded its resource guard')


class Guard:
    def __init__(self):
        self.started=time.monotonic()
        self.min_available=math.inf
        self.max_rss=0
        self.check()

    def check(self):
        import resource
        available=None
        with open('/proc/meminfo',encoding='ascii') as stream:
            for line in stream:
                fields=line.split()
                if fields and fields[0]=='MemAvailable:' and len(fields)==3 and fields[2]=='kB':
                    available=int(fields[1])*1024
                    break
        if available is None:
            raise RuntimeError('Cannot read hosted available memory')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        self.min_available=min(self.min_available,available)
        self.max_rss=max(self.max_rss,rss)
        validate_resources(time.monotonic()-self.started,available,shutil.disk_usage(ROOT).free,rss)


def digest_stream(stream,guard,limit=8*2**20):
    sha=hashlib.sha256()
    size=0
    while True:
        data=stream.read(256*1024)
        if not data:
            break
        size+=len(data)
        if size>limit:
            raise RuntimeError('File exceeds the QA size limit')
        sha.update(data)
        guard.check()
    return {'sha256':sha.hexdigest(),'bytes':size}


def info(path,guard,limit=8*2**20):
    if path.is_symlink() or path.resolve(strict=True)!=path or not path.is_file():
        raise RuntimeError('Missing or redirected QA input')
    with path.open('rb') as stream:
        return digest_stream(stream,guard,limit)


def git_blob(path,sha,guard):
    process=subprocess.Popen(['git','-C',str(ROOT),'cat-file','blob',sha+':'+path],
                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        result=digest_stream(process.stdout,guard)
        if process.wait(timeout=10)!=0:
            raise RuntimeError('Cannot read committed input blob')
        return result
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def verify_output_info(name,actual,reported):
    if name not in BASELINE_HASHES or actual!=reported or reported.get('sha256')!=BASELINE_HASHES[name]:
        raise RuntimeError('Source output hash differs: '+name)


def check_manifest(context,guard):
    if SOURCE.is_symlink() or SOURCE.resolve(strict=True)!=SOURCE or not SOURCE.is_dir():
        raise RuntimeError('Missing or redirected source directory')
    if {p.name for p in SOURCE.iterdir()}!={'MerchantGate.obj','MerchantGate.mtl','manifest.json','Textures'}:
        raise RuntimeError('Unexpected source bundle inventory')
    textures=SOURCE/'Textures'
    if textures.is_symlink() or textures.resolve(strict=True)!=textures or not textures.is_dir():
        raise RuntimeError('Invalid texture directory')
    if {p.name for p in textures.iterdir()}!=set(TEXTURES.values()):
        raise RuntimeError('Unexpected texture inventory')
    path=SOURCE/'manifest.json'
    manifest_info=info(path,guard,64*1024)
    with path.open(encoding='utf-8') as stream:
        manifest=json.load(stream)
    src=manifest.get('context',{})
    if (manifest.get('status')!='unreviewed_hosted_source_not_gameplay'
            or any(src.get(key)!=context[key] for key in ('repository','commit','run_id','attempt','event','workflow_ref','runner_environment','runner_os'))):
        raise RuntimeError('Source provenance differs from this hosted run')
    if set(manifest.get('outputs',{}))!=GENERATED or set(manifest.get('inputs',{}))!=INPUTS:
        raise RuntimeError('Source manifest file inventory differs')
    if (any(not isinstance(record,dict) or set(record)!={'sha256','bytes'}
            or not isinstance(record['bytes'],int) or record['bytes']<0
            for record in manifest['outputs'].values())
            or sum(record['bytes'] for record in manifest['outputs'].values())>MAX_FILE):
        raise RuntimeError('Source bundle exceeds the QA size cap')
    for name,expected in manifest['outputs'].items():
        verify_output_info(name,info(SOURCE/name,guard),expected)
    for name,expected in manifest['inputs'].items():
        if git_blob(name,context['commit'],guard)!=expected:
            raise RuntimeError('Source input differs from committed Git blob: '+name)
    for name in QA_CODE:
        if info(ROOT/name,guard)!=git_blob(name,context['commit'],guard):
            raise RuntimeError('QA code differs from committed Git blob')
    return manifest,manifest_info


def check_mtl():
    records={}
    role=None
    with (SOURCE/'MerchantGate.mtl').open(encoding='utf-8') as stream:
        for line in stream:
            fields=line.split()
            if not fields:
                continue
            if fields[0]=='newmtl' and len(fields)==2 and fields[1].startswith('M_GLMedieval_'):
                role=fields[1][len('M_GLMedieval_'):]
                if role not in COLORS or role in records:
                    raise RuntimeError('Invalid material role')
                records[role]={}
            elif role is not None and fields[0] in {'Kd','map_Kd'} and fields[0] not in records[role]:
                records[role][fields[0]]=fields[1:]
            else:
                raise RuntimeError('Unexpected material record')
    if set(records)!=set(COLORS):
        raise RuntimeError('Material role inventory differs')
    for role,data in records.items():
        try:
            rgb=tuple(map(float,data.get('Kd',[])))
        except ValueError as exc:
            raise RuntimeError('Invalid material color') from exc
        expected=(1.,1.,1.) if role in TEXTURES else COLORS[role]
        if rgb!=expected or data.get('map_Kd')!=(['Textures/'+TEXTURES[role]] if role in TEXTURES else None):
            raise RuntimeError('Material color or texture reference differs')
    return {role:record.get('map_Kd',[None])[0] for role,record in sorted(records.items())}


def clip(points,axis,limit,sign):
    result=[]
    for a,b in zip(points,points[1:]+points[:1]):
        da,db=sign*(a[axis]-limit),sign*(b[axis]-limit)
        if da>=0:
            result.append(a)
        if (da>=0)!=(db>=0):
            t=da/(da-db)
            result.append(tuple(x+t*(y-x) for x,y in zip(a,b)))
    return result


def ray_x(points,y,z):
    a,b,c=points
    by,bz,cy,cz=b[1]-a[1],b[2]-a[2],c[1]-a[1],c[2]-a[2]
    d=by*cz-bz*cy
    if abs(d)<1e-10:
        return None
    dy,dz=y-a[1],z-a[2]
    u,v=(dy*cz-dz*cy)/d,(by*dz-bz*dy)/d
    return a[0]+u*(b[0]-a[0])+v*(c[0]-a[0]) if min(u,v,1-u-v)>=-1e-7 else None


def intersects_passage(points):
    """Clip a triangle to the continuous Y/Z clearance, without X sampling."""
    section=list(points)
    for axis,limit,sign in ((1,-1.25,1),(1,1.25,-1),(2,.06,1),(2,2.70,-1)):
        section=clip(section,axis,limit,sign) if section else []
    return bool(section)


def check_obj(manifest,guard):
    vertices=[]; uvs=[]; normal=None; role=None; library=None
    nv=nt=nn=nf=blocked=0
    bounds=[[float('inf')]*3,[-float('inf')]*3]
    roles=collections.Counter()
    probes={'left':(-2.20,1.10),'right':(2.20,1.10),'header':(0,3.75),'lumen':(0,3.05)}
    hits={name:[] for name in probes}
    triangles=[]
    with (SOURCE/'MerchantGate.obj').open(encoding='utf-8') as stream:
        for line in stream:
            if len(line)>4096:
                raise RuntimeError('OBJ record exceeds size limit')
            fields=line.split()
            if not fields or fields[0].startswith('#'):
                continue
            kind=fields[0]
            if kind=='mtllib' and fields==['mtllib','MerchantGate.mtl'] and library is None:
                library=fields[1]
            elif kind=='v' and len(fields)==4:
                point=tuple(map(float,fields[1:]))
                if not all(math.isfinite(v) for v in point): raise RuntimeError('Invalid vertex')
                vertices.append(point); nv+=1
            elif kind=='vt' and len(fields)==3:
                uv=tuple(map(float,fields[1:]))
                if not all(math.isfinite(v) for v in uv): raise RuntimeError('Invalid UV')
                uvs.append(uv); nt+=1
            elif kind=='vn' and len(fields)==4:
                normal=tuple(map(float,fields[1:])); nn+=1
            elif kind=='usemtl' and len(fields)==2 and fields[1].startswith('M_GLMedieval_'):
                role=fields[1][len('M_GLMedieval_'):]
                if role not in COLORS: raise RuntimeError('Unknown OBJ material')
            elif kind=='f' and len(fields)==4 and role is not None:
                expected=[f'{3*nf+i}/{3*nf+i}/{nf+1}' for i in (1,2,3)]
                if fields[1:]!=expected or len(vertices)!=3 or len(uvs)!=3 or normal is None:
                    raise RuntimeError('Unexpected OBJ face structure')
                a,b,c=vertices
                u=tuple(b[i]-a[i] for i in range(3)); v=tuple(c[i]-a[i] for i in range(3))
                cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                length=math.sqrt(sum(x*x for x in cross))
                if (not math.isfinite(length) or length<1e-10 or not all(math.isfinite(x) for x in normal)
                        or abs(sum(x*x for x in normal)-1)>1e-8
                        or sum(cross[i]/length*normal[i] for i in range(3))<1-1e-8):
                    raise RuntimeError('Degenerate triangle or inconsistent normal')
                for point in vertices:
                    for axis in range(3):
                        bounds[0][axis]=min(bounds[0][axis],point[axis]); bounds[1][axis]=max(bounds[1][axis],point[axis])
                blocked+=intersects_passage(vertices)
                for name,(y,z) in probes.items():
                    hit=ray_x(vertices,y,z)
                    if hit is not None: hits[name].append(hit)
                triangles.append((role,tuple(vertices),normal))
                roles[role]+=1; nf+=1
                if nf>MAX_TRIANGLES:
                    raise RuntimeError('Triangle count exceeds QA cap')
                vertices=[]; uvs=[]; normal=None
                if nf%256==0: guard.check()
            else:
                raise RuntimeError('Unexpected OBJ record')
    if (library is None or vertices or uvs or normal is not None or (nv,nt,nn)!=(3*nf,3*nf,nf)
            or not triangles or set(roles)!=set(COLORS) or blocked
            or bounds!=[[-3.5,-6.5,0.0],[3.5,6.5,8.0]]):
        raise RuntimeError('OBJ bounds, structure or passage failed')
    if hits['lumen'] or any(not hits[n] or max(hits[n])-min(hits[n])<3.8 for n in ('left','right','header')):
        raise RuntimeError('Pier, header or lumen probe failed')
    prior=manifest.get('audit',{})
    if (prior.get('status')!='passed' or prior.get('triangles')!=nf or prior.get('obstructing_triangles')!=blocked
            or prior.get('clear_width_m')!=2.5 or prior.get('clear_height_m')!=2.7):
        raise RuntimeError('Independent audit disagrees with source manifest')
    report={'triangles':nf,'vertices':nv,'uvs':nt,'normals':nn,'bounds_m':bounds,
            'clear_width_m':2.5,'clear_height_m':2.7,'ignored_floor_band_m':.06,
            'obstructing_triangles':blocked,'role_triangles':dict(sorted(roles.items())),
            'pier_header_surface_hit_spans_m':{n:max(hits[n])-min(hits[n]) for n in ('left','right','header')},
            'lumen_hit_count':len(hits['lumen'])}
    return triangles,report


def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(v):
    n=math.sqrt(dot(v,v))
    return tuple(x/n for x in v)


FONT={
 'A':('01110','10001','10001','11111','10001','10001','10001'),
 'C':('01111','10000','10000','10000','10000','10000','01111'),
 'E':('11111','10000','10000','11110','10000','10000','11111'),
 'F':('11111','10000','10000','11110','10000','10000','10000'),
 'G':('01111','10000','10000','10111','10001','10001','01111'),
 'I':('111','010','010','010','010','010','111'),
 'L':('10000','10000','10000','10000','10000','10000','11111'),
 'M':('10001','11011','10101','10101','10001','10001','10001'),
 'N':('10001','11001','10101','10011','10001','10001','10001'),
 'O':('01110','10001','10001','10001','10001','10001','01110'),
 'R':('11110','10001','10001','11110','10100','10010','10001'),
 'S':('01111','10000','10000','01110','00001','00001','11110'),
 'T':('11111','00100','00100','00100','00100','00100','00100'),
 'U':('10001','10001','10001','10001','10001','10001','01110'),
 '-':('00000','00000','00000','11111','00000','00000','00000'),
 ' ':('000','000','000','000','000','000','000')}


def preview(triangles,eye,guard):
    width,height=600,460
    eye=unit(eye); right=unit(cross((0,0,1),eye)); up=unit(cross(eye,right))
    all_points=[p for _,points,_ in triangles for p in points]
    projected=[(dot(p,right),dot(p,up)) for p in all_points]
    xmin,xmax=min(p[0] for p in projected),max(p[0] for p in projected)
    ymin,ymax=min(p[1] for p in projected),max(p[1] for p in projected)
    scale=min((width-36)/(xmax-xmin),(height-70)/(ymax-ymin))
    cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
    pixels=bytearray((227,223,214))*(width*height)
    depth=array('f',[-1e30])*(width*height)
    light=unit((.75,-.45,1))
    for number,(role,points,normal) in enumerate(triangles):
        if number%32==0: guard.check()
        xyz=[(width/2+(dot(p,right)-cx)*scale,35+(height-35)/2-(dot(p,up)-cy)*scale,dot(p,eye)) for p in points]
        (x0,y0,z0),(x1,y1,z1),(x2,y2,z2)=xyz
        area=(x1-x0)*(y2-y0)-(y1-y0)*(x2-x0)
        if abs(area)<1e-10: continue
        sign=1 if area>0 else -1
        area=abs(area)
        left,rightbound=max(0,math.floor(min(x0,x1,x2))),min(width-1,math.ceil(max(x0,x1,x2)))
        top,bottom=max(35,math.floor(min(y0,y1,y2))),min(height-1,math.ceil(max(y0,y1,y2)))
        shade=.44+.56*max(0,dot(normal,light))
        color=bytes(round(255*max(0,min(1,c*shade))**(1/2.2)) for c in COLORS[role])
        e0x,e1x,e2x=-(y2-y1)*sign,-(y0-y2)*sign,-(y1-y0)*sign
        for y in range(top,bottom+1):
            if y%64==0: guard.check()
            py,px=y+.5,left+.5
            e0=((x2-x1)*(py-y1)-(y2-y1)*(px-x1))*sign
            e1=((x0-x2)*(py-y2)-(y0-y2)*(px-x2))*sign
            e2=((x1-x0)*(py-y0)-(y1-y0)*(px-x0))*sign
            for x in range(left,rightbound+1):
                if e0>=0 and e1>=0 and e2>=0:
                    z=(e0*z0+e1*z1+e2*z2)/area
                    offset=y*width+x
                    if z>depth[offset]:
                        depth[offset]=z
                        pixels[3*offset:3*offset+3]=color
                e0+=e0x; e1+=e1x; e2+=e2x
    xpos=12
    for ch in 'FLAT SOURCE - NOT IN GAME':
        glyph=FONT[ch]
        for y,row in enumerate(glyph):
            for x,pixel in enumerate(row):
                if pixel=='1':
                    for dy in (0,1):
                        for dx in (0,1):
                            pos=((10+2*y+dy)*width+xpos+2*x+dx)*3
                            pixels[pos:pos+3]=bytes((35,35,35))
        xpos+=2*(len(glyph[0])+1)
    guard.check()
    return width,height,pixels


def png_chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)


def write_preview(path,eye,triangles,guard):
    width,height,pixels=preview(triangles,eye,guard)
    compressor=zlib.compressobj(6)
    pieces=[]
    for y in range(height):
        pieces.append(compressor.compress(b'\0'+pixels[y*width*3:(y+1)*width*3]))
        if y%64==0: guard.check()
    pieces.append(compressor.flush())
    data=b''.join(pieces)
    with path.open('xb') as stream:
        stream.write(b'\x89PNG\r\n\x1a\n')
        stream.write(png_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0)))
        stream.write(png_chunk(b'tEXt',b'Description\0Flat color review of source geometry; not in game'))
        stream.write(png_chunk(b'IDAT',data))
        stream.write(png_chunk(b'IEND',b''))


def run(context):
    apply_limits()
    guard=Guard()
    verify_revision(context)
    manifest,source_manifest_info=check_manifest(context,guard)
    materials=check_mtl()
    triangles,geometry=check_obj(manifest,guard)
    guard.check()
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise RuntimeError('QA output already exists')
    OUTPUT.mkdir()
    if OUTPUT.resolve(strict=True)!=OUTPUT or OUTPUT.parent!=ROOT:
        raise RuntimeError('QA output was redirected')
    previews={}
    for name,eye in (('entrance_flat.png',(1,0,.08)),('three_quarter_flat.png',(1.6,-1.15,1.0))):
        guard.check()
        path=OUTPUT/name
        write_preview(path,eye,triangles,guard)
        previews[name]=info(path,guard,MAX_FILE)
    report={'status':'independent_offline_source_qa_passed_not_gameplay','context':context,
            'source_manifest':source_manifest_info,'source_outputs':manifest['outputs'],
            'baseline_run':BASELINE_RUN,'baseline_output_hashes':BASELINE_HASHES,
            'input_git_blobs_verified':len(INPUTS),'qa_code':{p:info(ROOT/p,guard) for p in QA_CODE},
            'materials':materials,'geometry':geometry,'previews':previews,
            'elapsed_seconds':time.monotonic()-guard.started,'min_available_bytes':guard.min_available,
            'peak_rss_bytes':guard.max_rss,
            'limitations':['GitHub environment checks prevent accidents but are not attestation',
                           'Baseline hashes came from the embedded manifest of the SHA-verified earlier ZIP; its individual files were not independently extracted',
                           'Source and QA manifests vary by run metadata and resource readings; preview PNGs have no earlier baseline',
                           'Pier and header probes measure surface-hit spans, not continuous solid masonry or collision',
                           'Flat-color previews do not display texture details',
                           'No Unreal import, collision, navigation, placement or gameplay validation']}
    guard.check()
    with (OUTPUT/'qa_manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2); stream.write('\n')
    return OUTPUT


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        context=hosted_context()
        print('Hosted review-only QA complete:',run(context).name)
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as exc:
        print('Hosted QA refused or stopped:',str(exc),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
