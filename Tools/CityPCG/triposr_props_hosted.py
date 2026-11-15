"""Isolated GitHub-hosted CPU TripoSR source-mesh trials; never opens Unreal."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'ArtDirection/CityPCG/MedievalLondon/ImageTo3D'
WORKFLOW='.github/workflows/triposr-medieval-props.yml'
SOURCE_COMMIT='107cefdc244c39106fa830359024f6a2f1c78871'
MODEL_REV='5b521936b01fbe1890f6f9baed0254ab6351c04a'
CHECKPOINT_SHA='429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee'
CONFIG_SHA='74ca708ce086bf68e97709ea6b3d91f14717921c04691e84043f0eb8fcc68e62'
DINO_SHA='b87c0270b97db085fd82cf114a761fd0f62ae7914fbd407c752a2260646b689c'
LICENSE_SHA='13aff551d7009dea9d44cc5e200f8493e0e9d5171be0ab19940e6f20f54c7e17'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def context():
    e=os.environ; repo='zachrizzo/reflections'
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':repo,'GITHUB_REPOSITORY_ID':'1457160414','GITHUB_REF':'refs/heads/main',
              'GITHUB_WORKFLOW_REF':f'{repo}/{WORKFLOW}@refs/heads/main'}
    if sys.platform!='linux' or any(e.get(k)!=v for k,v in expected.items()): raise RuntimeError('hosted context')
    sha=e.get('GITHUB_SHA',''); name=e.get('PROP_NAME','')
    if (not re.fullmatch(r'[0-9a-f]{40}',sha) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,39}',name)
            or e.get('GITHUB_EVENT_NAME') not in ('push','workflow_dispatch')
            or any(not re.fullmatch(r'[1-9][0-9]{0,19}',e.get(k,'')) for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'))):
        raise RuntimeError('hosted identity')
    if Path(e['GITHUB_WORKSPACE']).resolve(strict=True)!=ROOT: raise RuntimeError('workspace')
    temp=Path(e['RUNNER_TEMP']).resolve(strict=True)
    if temp==ROOT or temp.is_relative_to(ROOT) or shutil.disk_usage(temp).free<3*2**30: raise RuntimeError('disk')
    head=subprocess.run(['git','-C',str(ROOT),'rev-parse','--verify','HEAD'],stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,timeout=10,check=False)
    if head.returncode or head.stdout!=(sha+'\n').encode('ascii'): raise RuntimeError('checkout')
    with open('/proc/meminfo',encoding='ascii') as stream:
        available=next((line for line in stream if line.startswith('MemAvailable:')),None)
    if not available or not re.fullmatch(r'MemAvailable:\s+[0-9]+\s+kB\s*',available): raise RuntimeError('memory')
    if int(available.split()[1])*1024<3*2**30: raise RuntimeError('memory headroom')
    return name,temp


def preview(mesh,conditioned,path):
    import numpy as np
    from PIL import Image,ImageDraw
    canvas=Image.new('RGB',(1024,512),(226,222,211)); draw=ImageDraw.Draw(canvas)
    image=conditioned.copy(); image.thumbnail((470,440)); canvas.paste(image,(20+(470-image.width)//2,52))
    verts=np.asarray(mesh.vertices); faces=np.asarray(mesh.faces); colors=np.asarray(mesh.visual.vertex_colors)
    # Bounded flat-color diagnostic; full geometry remains in the GLB.
    stride=max(1,math.ceil(len(faces)/20000)); faces=faces[::stride]
    xyz=verts[:,[0,2,1]]; low=xyz[:,:2].min(axis=0); high=xyz[:,:2].max(axis=0)
    span=max(float(max(high-low)),1e-8); xy=(xyz[:,:2]-(low+high)/2)*(420/span)
    xy[:,0]+=758; xy[:,1]=270-xy[:,1]
    order=np.argsort(xyz[faces,2].mean(axis=1))
    for index in order:
        tri=faces[index]; color=tuple(int(v) for v in colors[tri,:3].mean(axis=0))
        draw.polygon([tuple(xy[i]) for i in tri],fill=color)
    draw.rectangle((8,8,590,39),fill=(18,18,18)); draw.text((18,16),'RAW AI SOURCE / NOT IN GAME',fill=(255,255,255))
    canvas.save(path,'PNG')


def run():
    name,temp=context(); manifest=json.loads((BASE/'inputs.json').read_text(encoding='utf-8'))
    expected=manifest.get('assets',{}).get(name)
    if manifest.get('schema')!=1 or not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{64}',expected):
        raise ValueError('input manifest')
    source=BASE/'Inputs'/f'{name}.png'; config=BASE/'Configs/config.yaml'; dino=BASE/'Configs/dino_config.json'
    upstream=temp/'TripoSR-upstream'; modeldir=temp/'TripoSR-model'; checkpoint=modeldir/'model.ckpt'
    if (source.is_symlink() or not source.is_file() or digest(source)!=expected or digest(config)!=CONFIG_SHA
            or digest(dino)!=DINO_SHA or checkpoint.stat().st_size!=1677246742 or digest(checkpoint)!=CHECKPOINT_SHA
            or digest(upstream/'LICENSE')!=LICENSE_SHA): raise ValueError('pinned source mismatch')
    sha=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True,timeout=10).strip()
    if sha!=SOURCE_COMMIT: raise ValueError('upstream revision')
    out=ROOT/f'ci-triposr-{name.lower()}'
    if out.exists() or out.is_symlink(): raise ValueError('output already exists')
    out.mkdir()
    shutil.copyfile(config,modeldir/'config.yaml')
    shutil.copyfile(dino,modeldir/'dino_config.json')
    shutil.copyfile(upstream/'LICENSE',out/'TripoSR_LICENSE.txt')
    import numpy as np
    import torch
    import trimesh
    from PIL import Image
    sys.path.insert(0,str(upstream)); sys.path.insert(0,str(ROOT/'Tools/CityPCG'))
    import triposr_skimage_mc
    shim=types.ModuleType('torchmcubes'); shim.marching_cubes=triposr_skimage_mc.marching_cubes
    sys.modules['torchmcubes']=shim
    # Inputs already have alpha; fail if upstream attempts background removal.
    rembg=types.ModuleType('rembg')
    def no_background(*args,**kwargs): raise RuntimeError('Background removal is not used for alpha inputs')
    rembg.remove=no_background; sys.modules['rembg']=rembg
    from tsr.system import TSR
    from tsr.utils import resize_foreground
    import tsr.models.tokenizers.image as tokenizer
    def local_dino(repo_id,filename,**kwargs):
        if repo_id!='facebook/dino-vitb16' or filename!='config.json': raise RuntimeError('unexpected model dependency')
        return str(modeldir/'dino_config.json')
    tokenizer.hf_hub_download=local_dino
    with Image.open(source) as im:
        rgba=im.convert('RGBA')
        if rgba.getchannel('A').getextrema()!=(0,255): raise ValueError('Expected transparent alpha input')
        foreground=resize_foreground(rgba,.85)
    foreground.save(out/'foreground.png','PNG')
    arr=np.asarray(foreground,dtype=np.float32)/255.; alpha=arr[:,:,3:4]
    conditioned=Image.fromarray(np.clip((arr[:,:,:3]*alpha+(1-alpha)*.5)*255,0,255).astype(np.uint8),'RGB')
    conditioned.save(out/'conditioned.png','PNG')
    torch.manual_seed(1450); np.random.seed(1450); torch.set_num_threads(2)
    started=time.monotonic()
    model=TSR.from_pretrained(str(modeldir),config_name='config.yaml',weight_name='model.ckpt')
    model.renderer.set_chunk_size(4096); model.eval().to('cpu')
    with torch.inference_mode():
        scene=model([conditioned],device='cpu')
        mesh=model.extract_mesh(scene,has_vertex_color=True,resolution=128)[0]
    vertices=np.asarray(mesh.vertices); faces=np.asarray(mesh.faces); colors=np.asarray(mesh.visual.vertex_colors)
    if (len(vertices)<10 or len(faces)<10 or not np.isfinite(vertices).all()
            or colors.ndim!=2 or len(colors)!=len(vertices) or colors.shape[1] not in (3,4)):
        raise ValueError('invalid generated geometry or vertex colors')
    path=out/f'{name}.glb'; raw=mesh.export(file_type='glb')
    if not isinstance(raw,bytes) or raw[:4]!=b'glTF' or not 20<len(raw)<100*2**20: raise ValueError('invalid GLB')
    with path.open('xb') as target: target.write(raw)
    reloaded=trimesh.load(path,force='scene',process=False)
    geoms=list(reloaded.geometry.values())
    if len(geoms)!=1: raise ValueError('unexpected reimport geometry count')
    imported=geoms[0]; restored=np.asarray(imported.visual.vertex_colors)
    if (len(imported.vertices)!=len(vertices) or len(imported.faces)!=len(faces)
            or restored.shape[0]!=len(vertices) or restored.shape[1]<3
            or not np.array_equal(restored[:,:3],colors[:,:3])):
        raise ValueError('GLB readback changed geometry counts or vertex colors')
    preview(mesh,conditioned,out/'diagnostic.png')
    outputs={p.name:digest(p) for p in out.iterdir() if p.is_file()}
    report={'status':'raw_mesh_requires_review','asset':name,'provider':'TripoSR','license':'MIT',
            'upstream_commit':SOURCE_COMMIT,'model_revision':MODEL_REV,'checkpoint_sha256':CHECKPOINT_SHA,
            'config_sha256':CONFIG_SHA,'dino_config_sha256':DINO_SHA,'input_sha256':expected,
            'commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'device':'CPU',
            'seed':1450,'resolution':128,'chunk_size':4096,'seconds':round(time.monotonic()-started,2),
            'torch':torch.__version__,'vertices':len(vertices),'faces':len(faces),'bounds_model_units':mesh.bounds.tolist(),
            'vertex_color_shape':list(colors.shape),'glb_readback':'single geometry; counts and RGB vertex colors match',
            'outputs_sha256':outputs,'limitations':['Arbitrary scale and pivot; unseen surfaces inferred.',
              'No Unreal import, collision, navigation, visual or gameplay validation.',
              'CPU scikit-image Lorensen adapter differs from upstream torchmcubes.']}
    with (out/'provenance.complete.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2,sort_keys=True); stream.write('\n')
    print(json.dumps({'status':report['status'],'asset':name,'vertices':len(vertices),'faces':len(faces)}))


if __name__=='__main__': run()
