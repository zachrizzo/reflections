"""Inputs and small validation helpers for the hosted-only street review."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import stat
import subprocess
import sys
import zipfile


ROOT=Path(__file__).resolve().parents[2]
REPO='zachrizzo/reflections'
WORKFLOW='.github/workflows/north-market-street-review.yml'
BASE=Path('ArtDirection/CityPCG/MedievalOpening')
BUILDING_BASE=BASE/'WholeBuildings/NorthMarketDetailedObj'
REVIEW=BUILDING_BASE/'HostedFBXReview'
BUILDER=Path('ArtDirection/MedievalLondon/MarketDressing/build_market_dressing.py')
KIT=BASE/'MarketDressingKit/build_market_dressing.py'
TENANCY=Path('Tools/CityPCG/north_market_tenancies.py')
PLAN=BASE/'FollowOn20261115/north_market_east_plan_20261115.json'
GROUND=BASE/'Ground/Source'
QUAY=Path('ArtDirection/MedievalLondon/QuayDressing/Source')
MANIFEST=BUILDING_BASE/'detailed_obj_manifest.json'
INPUTS={
    BUILDER:'d78c583bb31dbd34e60e981a8b4259919a3aa30634a169352d0ab32fa7ca6271',
    KIT:'7461853706acd6f31312ee87548f6a30f31ae00e83cb8bd65efbd8e43764362d',
    TENANCY:'ad2604f21589a4e96881e6d964c7fa7a0e719c7927a533deb2db801f1a993b0f',
    # Git stores LF; the Windows working copy may use CRLF.
    PLAN:'88ea66f0292864f8f6b9924d654a323edb37da9ce307754f7f9f57fc77fbc32f',
    MANIFEST:'a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095',
    GROUND/'T_GL1450_Ground_Color.png':'ab6590f4ea1621c7b615f5d37ccab8d9b1cb6d7f4f44d414e69195499bf3a986',
    GROUND/'T_GL1450_Ground_Normal.png':'7639ce0d61ecd4db48c91cc0eb471b2902c7a6799fbf8ab1c8e02864ee668b57',
    GROUND/'T_GL1450_Ground_Roughness.png':'9e6c7033edb47f13fb571bf249abc2be4f9f8a4ce49557ec665ea499ad93b0a8',
    QUAY/'SM_GL1450_QuayHandcart.glb':'fcd2082e0d250f60d7114e04a7c5eef57a00d13fe1c40e7cd5ba781bf21f9f0b',
    QUAY/'SM_GL1450_QuayCargo.glb':'4307780781abdba27ba8b4dab3d4219212e5723f0b4a693351523b7dbbf57f51',
    REVIEW/'east_0a73564b.zip':'3a690aade02e668b800c5d49426d7b142d18556a953d7ed00737861a5086d096',
    REVIEW/'east_31c9ff1a.zip':'bf30b04ea539b92e3bc518f19e75ce13566ab6ebf622285db9e9a3a271541c9b',
    BUILDING_BASE/'tenancies_overlay_east_0a73564b.obj':'b67371709b3050ba31e2c31ad25488f5bc83cb0ef01bd050d47e62ff87da7eec',
    Path('Tools/CityPCG/north_market_roundtrip_common.py'):'02d6c54cf6d1400de23dae5c43e2e9fa69dfa45dbc10a08fc856a5fdc9da74fe',
    Path('Tools/CityPCG/north_market_hosted_blender.py'):'4d6782256cf9618aa95a40ea452c29bffeb11d3d2bd82925365dd87edaa82f75',
    Path('Tools/CityPCG/north_market_tenancy_preview.py'):'9602c5a97021c64674ec5839b9203949f3aaaf36db564849bb45d6957db0ccd8',
}
TENANCY_OVERLAY_SHA='b67371709b3050ba31e2c31ad25488f5bc83cb0ef01bd050d47e62ff87da7eec'
TENANCY_COMBINED_SHA='f52ba1bccfb11a986b78ced35a9924c437a6ccd350ac51dc90fef666731b2be5'
MODELS={
    'east_0a73564b':{'name':'SM_GLMedieval_NorthMarketDetail_east_0a73564b',
                     'fbx_sha256':'6a1f365d71f7cf88e1df766599f323311b600cc4000e558b98a78d9e7cf6b38d'},
    'east_31c9ff1a':{'name':'SM_GLMedieval_NorthMarketDetail_east_31c9ff1a',
                     'fbx_sha256':'09c58737a493392e161befb651ecd34b93cc079723b8ef0370906d9a4a20af02'},
}
PROP_LAYOUT={
    # Artistic local staging ONLY. These are not placements in Gray London.
    'market_stall':([26.65,-17.90,0.0],0.0),
    'crate_group':([26.55,-26.00,0.0],0.0),
    'cask_group':([26.55,-27.30,0.0],0.0),
    'handcart':([29.20,-29.00,0.0],90.0),
    'cargo':([28.40,-31.40,0.0],0.0),
    'trestle':([25.98,-24.00,0.0],0.0),
    'bowl_a':([26.32,-24.30,0.7925],0.0),
    'bowl_b':([26.32,-23.85,0.7925],0.0),
    'ale_stake':([25.90,-17.50,3.00],0.0),
}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(256*1024),b''): h.update(chunk)
    return h.hexdigest()


def canonical_plan_digest(data):
    if not isinstance(data,bytes) or len(data)>1024*1024:
        raise ValueError('invalid plan bytes')
    canonical=data.replace(b'\r\n',b'\n')
    if b'\r' in canonical:
        raise ValueError('unsupported plan line ending')
    return hashlib.sha256(canonical).hexdigest()


def verify_plan_bytes(data,expected):
    if canonical_plan_digest(data)!=expected:
        raise ValueError('plan content hash mismatch')


def hosted_context():
    e=os.environ
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':REPO,'GITHUB_REF':'refs/heads/main',
              'GITHUB_WORKFLOW_REF':f'{REPO}/{WORKFLOW}@refs/heads/main'}
    if sys.platform!='linux' or any(e.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('not the designated hosted review workflow')
    if not re.fullmatch(r'[0-9a-f]{40}',e.get('GITHUB_SHA','')):
        raise RuntimeError('missing commit identity')
    if any(not re.fullmatch(r'[1-9][0-9]{0,19}',e.get(k,'')) for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT')):
        raise RuntimeError('missing run identity')
    workspace=Path(e.get('GITHUB_WORKSPACE','')).resolve(strict=True)
    temp=Path(e.get('RUNNER_TEMP','')).resolve(strict=True)
    if workspace!=ROOT or temp==ROOT or temp.is_relative_to(ROOT):
        raise RuntimeError('unexpected hosted workspace')
    check=subprocess.run(['git','-C',str(workspace),'rev-parse','--verify','HEAD'],
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,check=False)
    if check.returncode or check.stdout!=(e['GITHUB_SHA']+'\n').encode('ascii'):
        raise RuntimeError('checkout does not match the reported commit')
    scratch=temp/f"north-market-street-{e['GITHUB_RUN_ID']}-{e['GITHUB_RUN_ATTEMPT']}"
    return workspace,scratch


def validate_inputs(root):
    root=Path(root).resolve(strict=True)
    for rel,sha in INPUTS.items():
        path=root/rel
        if path.is_symlink() or not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError('source file absent or redirected')
        if rel==PLAN:
            if path.stat().st_size>1024*1024: raise ValueError('plan exceeds size limit')
            verify_plan_bytes(path.read_bytes(),sha)
        elif digest(path)!=sha:
            raise ValueError('source file hash mismatch')


def relative_pose(origin,yaw,other_origin,other_yaw):
    if (len(origin)!=3 or len(other_origin)!=3 or
            not all(math.isfinite(float(x)) for x in (*origin,yaw,*other_origin,other_yaw))):
        raise ValueError('invalid building pose')
    angle=math.radians(yaw); dx=other_origin[0]-origin[0]; dy=other_origin[1]-origin[1]
    return ([math.cos(angle)*dx+math.sin(angle)*dy,
             -math.sin(angle)*dx+math.cos(angle)*dy,other_origin[2]-origin[2]],
            other_yaw-yaw)


def check_matrix(matrix,expected,tolerance=1e-5):
    if any(not math.isfinite(float(matrix[i][j])) or
           abs(float(matrix[i][j])-expected[i][j])>tolerance for i in range(4) for j in range(4)):
        raise ValueError('building transform differs from the required pose')


def check_identity(matrix):
    check_matrix(matrix,[[1.0 if i==j else 0.0 for j in range(4)] for i in range(4)],1e-6)


def check_pose(matrix,position,yaw):
    if len(position)!=3 or not all(math.isfinite(float(x)) for x in (*position,yaw)):
        raise ValueError('invalid requested pose')
    angle=math.radians(yaw); s=math.sin(angle); co=math.cos(angle)
    check_matrix(matrix,[[co,-s,0.,position[0]],[s,co,0.,position[1]],
                         [0.,0.,1.,position[2]],[0.,0.,0.,1.]])


def scene_recipe(manifest,plan):
    rows={v['source_artifact']['file'].removesuffix('.obj'):v for v in manifest['buildings'].values()}
    first=rows[MODELS['east_0a73564b']['name']]; second=rows[MODELS['east_31c9ff1a']['name']]
    pivot,yaw=first['world_pivot_m'],first['yaw_deg']
    other,other_yaw=relative_pose(pivot,yaw,second['world_pivot_m'],second['yaw_deg'])
    entry=[x for x in plan['buildings'] if x['id'].endswith('0a73564b5b0ed26a')]
    if len(entry)!=1 or entry[0]['entry']['edge']!=21:
        raise ValueError('surveyed entry changed')
    x,y=entry[0]['entry']['center_local_xy_m']
    if abs(x-25.89503)>0.0001 or abs(y+21.055861)>0.0001:
        raise ValueError('surveyed entry coordinates changed')
    return {'origin_world_m':pivot,'origin_yaw_deg':yaw,'secondary_local_m':other,
            'secondary_yaw_deg':other_yaw,'entry_local_m':[x,y],
            'props':{k:{'position_m':v[0],'yaw_deg':v[1]} for k,v in PROP_LAYOUT.items()},
            'prop_placements':'illustrative only; no live placement or clearance approval'}


def check_tenancy_report(report,overlay_sha,combined_sha):
    if (not isinstance(report,dict) or report.get('status')!='review_only_not_unreal_validated'
            or report.get('building')!='Tile_p03_p01_roof_0a73564b5b0ed26a'
            or report.get('source_obj_sha256')!='5ca906f6b995d50cd956d89c9382856ba464366c23db6b93f0a886dfaec1a57f'
            or report.get('source_plan_lf_sha256')!=INPUTS[PLAN]
            or not isinstance(report.get('units'),list) or len(report['units'])!=7
            or report.get('added_vertices')!=1704 or report.get('added_faces')!=1278
            or report.get('overlay_sha256')!=TENANCY_OVERLAY_SHA or overlay_sha!=TENANCY_OVERLAY_SHA
            or report.get('combined_sha256')!=TENANCY_COMBINED_SHA or combined_sha!=TENANCY_COMBINED_SHA):
        raise ValueError('tenancy output differs from the reviewed hosted trial')


def safe_archive_name(info):
    name=info.filename
    if '\\' in name or '\x00' in name or ':' in name: return False
    raw=name[:-1] if name.endswith('/') else name
    if any(v in ('','..','.') for v in raw.split('/')): return False
    p=PurePosixPath(name)
    if p.is_absolute() or any(v in ('','..','.') for v in p.parts): return False
    mode=(info.external_attr>>16)&0o170000
    return mode in (0,stat.S_IFREG,stat.S_IFDIR) and not (info.flag_bits&1)


def unpack_building(archive_path,dest,key):
    """Bounded extraction of one already SHA-pinned review archive."""
    model=MODELS[key]['name']; wanted={model+'.fbx','verify.report.json','export.report.json'}
    image_names={f'T_GLMedieval_{n}.png' for n in ('ClayTile','Fieldstone','GuildRubble',
        'LimePlaster','Oak','ShopGreen','ShopRed','WarmPlaster','WeatheredOak')}
    dest.mkdir()
    with zipfile.ZipFile(archive_path) as z:
        entries=z.infolist(); seen=set(); selected=[]; total=0
        if len(entries)>256: raise ValueError('archive inventory exceeds bound')
        for entry in entries:
            if not safe_archive_name(entry) or entry.filename in seen:
                raise ValueError('unsafe or duplicate archive member')
            seen.add(entry.filename)
            if entry.is_dir(): continue
            parts=PurePosixPath(entry.filename).parts
            if parts[0]!=model: continue  # e.g. the separate optional preview
            if not ((len(parts)==2 and parts[-1] in wanted) or
                    (2<=len(parts)<=3 and parts[-1] in image_names)):
                raise ValueError('unexpected model archive member')
            if entry.compress_type not in (0,8) or entry.file_size<=0 or entry.file_size>32*2**20:
                raise ValueError('archive member exceeds bound')
            total+=entry.file_size; selected.append((entry,parts))
        if total>48*2**20: raise ValueError('archive output exceeds bound')
        for entry,parts in selected:
            target=dest.joinpath(*parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(entry) as src,target.open('xb') as out:
                shutil.copyfileobj(src,out,256*1024)
    bundle=dest/model; fbx=bundle/(model+'.fbx')
    report=json.loads((bundle/'verify.report.json').read_text(encoding='utf-8'))
    if (digest(fbx)!=MODELS[key]['fbx_sha256'] or report.get('model')!=model or
            report.get('phase')!='verify' or report.get('fbx_sha256')!=MODELS[key]['fbx_sha256'] or
            report.get('source_manifest_sha256')!=INPUTS[MANIFEST]):
        raise ValueError('verified FBX report mismatch')
    return bundle,fbx


def prepare():
    root,scratch=hosted_context(); validate_inputs(root)
    if scratch.exists() or scratch.is_symlink(): raise ValueError('scratch already exists')
    if shutil.disk_usage(scratch.parent).free<512*2**20: raise RuntimeError('insufficient runner disk')
    scratch.mkdir(mode=0o700)
    # Preserve __file__ layout so the unmodified reviewed Blender script writes
    # only into this fresh runner scratch tree, not the repository or editor.
    dest=scratch/BUILDER; dest.parent.mkdir(parents=True)
    with (root/BUILDER).open('rb') as src,dest.open('xb') as out: shutil.copyfileobj(src,out)
    if digest(dest)!=INPUTS[BUILDER]: raise ValueError('scratch builder hash mismatch')
    print('Hosted review inputs verified; scratch builder prepared.')


def generate_tenancy():
    root,scratch=hosted_context(); validate_inputs(root)
    if scratch.is_symlink() or not scratch.is_dir() or scratch.resolve(strict=True)!=scratch:
        raise ValueError('missing isolated scratch')
    destination=scratch/'tenancy'
    report=runpy.run_path(str(root/TENANCY))['generate'](destination)
    overlay=destination/'tenancies_overlay.obj'
    combined=destination/(MODELS['east_0a73564b']['name']+'_tenancies_review.obj')
    check_tenancy_report(report,digest(overlay),digest(combined))
    print('Regenerated tenancy overlay matches the reviewed hosted trial.')


if __name__=='__main__':
    if sys.argv[1:]==['prepare']: prepare()
    elif sys.argv[1:]==['tenancy']: generate_tenancy()
    else: raise SystemExit('Expected prepare or tenancy')
