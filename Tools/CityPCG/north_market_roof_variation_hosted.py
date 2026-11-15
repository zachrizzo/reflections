"""Build and inspect the North Market variation on its isolated hosted runner.

The environment check prevents accidental local execution, not deliberate
spoofing. This review output is not an Unreal map or an approved placement.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import north_market_roof_variation as variation
import north_market_roundtrip_common as source
import north_market_hosted_blender as adapter
import north_market_tenancy_preview as preview
import north_market_street_review_common as street


ROOT=Path(__file__).resolve().parents[2]
WORKFLOW='.github/workflows/north-market-roof-variation.yml'
REPO='zachrizzo/reflections'
ART=Path('ArtDirection/CityPCG/MedievalOpening')
SOURCE=ART/'WholeBuildings/NorthMarketDetailedObj'
PLAN=ART/'FollowOn20261115/north_market_east_plan_20261115.json'
BASELINE=SOURCE/'HostedStreetReview/north-market-street-illustrative-review.zip'
ZIP_SHA='021114d3c208f9aed1f4c6d874c24e6306050244ad17426d491d9106cf2be698'
BLEND_SHA='4139c2e2536ab643c4fe420e7cf0d6299413d4744b11c80d3a3ad11a5222b905'
PLAN_SHA='88ea66f0292864f8f6b9924d654a323edb37da9ce307754f7f9f57fc77fbc32f'
PINS={
    Path('Tools/CityPCG/north_market_tenancies.py'):'ad2604f21589a4e96881e6d964c7fa7a0e719c7927a533deb2db801f1a993b0f',
    Path('Tools/CityPCG/north_market_tenancy_preview.py'):'9602c5a97021c64674ec5839b9203949f3aaaf36db564849bb45d6957db0ccd8',
    Path('Tools/CityPCG/north_market_roundtrip_common.py'):'02d6c54cf6d1400de23dae5c43e2e9fa69dfa45dbc10a08fc856a5fdc9da74fe',
    Path('Tools/CityPCG/north_market_hosted_blender.py'):'4d6782256cf9618aa95a40ea452c29bffeb11d3d2bd82925365dd87edaa82f75',
    Path('Tools/CityPCG/north_market_street_review_common.py'):'5e45b7d0ad2f3ff4f1afd2b7c757dc8331698134b90fe2e8f40143c9506f865e',
}
OUT=ROOT/'ci-north-market-roof-variation'


def context():
    env=os.environ
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
        'GITHUB_REPOSITORY':REPO,'GITHUB_REPOSITORY_ID':'1457160414','GITHUB_REF':'refs/heads/main',
        'GITHUB_WORKFLOW_REF':f'{REPO}/{WORKFLOW}@refs/heads/main'}
    if sys.platform!='linux' or any(env.get(k)!=v for k,v in expected.items()):
        raise RuntimeError('Unexpected hosted workflow context')
    sha=env.get('GITHUB_SHA','')
    if (not re.fullmatch(r'[0-9a-f]{40}',sha) or env.get('GITHUB_EVENT_NAME') not in ('push','workflow_dispatch')
            or any(not re.fullmatch(r'[1-9][0-9]{0,19}',env.get(k,''))
                   for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'))):
        raise RuntimeError('Invalid hosted run identity')
    if Path(env['GITHUB_WORKSPACE']).resolve(strict=True)!=ROOT:
        raise RuntimeError('Unexpected workspace')
    temp=Path(env['RUNNER_TEMP']).resolve(strict=True)
    if temp==ROOT or temp.is_relative_to(ROOT): raise RuntimeError('Invalid runner temporary directory')
    result=subprocess.run(['git','-C',str(ROOT),'rev-parse','--verify','HEAD'],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=False,timeout=10)
    if result.returncode or result.stdout!=(sha+'\n').encode('ascii'):
        raise RuntimeError('Checkout and workflow SHA differ')
    if shutil.disk_usage(temp).free < 2*2**30:
        raise RuntimeError('Insufficient runner disk space')
    with open('/proc/meminfo',encoding='ascii') as stream:
        available=next((line for line in stream if line.startswith('MemAvailable:')),None)
    if available is None or not re.fullmatch(r'MemAvailable:\s+[0-9]+\s+kB\s*',available):
        raise RuntimeError('Cannot verify runner memory')
    if int(available.split()[1])*1024 < 1536*2**20:
        raise RuntimeError('Insufficient runner memory')
    return temp/f"north-market-roof-{env['GITHUB_RUN_ID']}-{env['GITHUB_RUN_ATTEMPT']}"


def validated_inputs():
    for rel,pin in PINS.items():
        path=ROOT/rel
        if path.is_symlink() or source.digest(path)!=pin: raise ValueError('Review helper changed')
    plan=ROOT/PLAN
    if plan.is_symlink() or plan.stat().st_size>1024*1024:
        raise ValueError('Plan missing or too large')
    street.verify_plan_bytes(plan.read_bytes(),PLAN_SHA)
    archive=ROOT/BASELINE
    if archive.is_symlink() or archive.stat().st_size!=35334942 or source.digest(archive)!=ZIP_SHA:
        raise ValueError('Preserved street archive changed')
    return json.loads(plan.read_text(encoding='utf-8'))


def blend_entry(entries):
    matches=[entry for entry in entries if entry.filename=='north_market_street_review.blend']
    if len(matches)!=1: raise ValueError('Expected exactly one baseline scene')
    entry=matches[0]; mode=(entry.external_attr>>16)&0o170000
    if (mode not in (0,stat.S_IFREG) or entry.flag_bits&1 or entry.is_dir()
            or not 0<entry.file_size<=160*2**20 or entry.compress_type not in (0,8)):
        raise ValueError('Unsafe baseline scene member')
    return entry


def prepare():
    scratch=context(); validated_inputs()
    scratch.mkdir(mode=0o700,exist_ok=False)
    target=scratch/'baseline.blend'; digest=hashlib.sha256(); size=0
    with zipfile.ZipFile(ROOT/BASELINE) as archive:
        entry=blend_entry(archive.infolist())
        with archive.open(entry) as stream,target.open('xb') as out:
            for part in iter(lambda:stream.read(256*1024),b''):
                size+=len(part)
                if size>entry.file_size: raise ValueError('Baseline exceeds member size')
                out.write(part); digest.update(part)
    if size!=entry.file_size or digest.hexdigest()!=BLEND_SHA:
        raise ValueError('Baseline scene bytes differ')
    print('Pinned baseline scene prepared.')


def write_json(path, data):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(data,stream,indent=2,sort_keys=True); stream.write('\n')


def expected_mesh(mesh,materials):
    faces=[]; used=set(); edges=set()
    for indices,role in zip(mesh.faces,mesh.roles):
        pts=[mesh.vertices[i] for i in indices]
        normal,uvs=variation.tenancy.normal_and_uv(pts,variation.TILES[role])
        material='M_GLMedieval_'+role; used.add(material)
        faces.append((material,tuple(tuple(p)+tuple(uv)+tuple(normal) for p,uv in zip(pts,uvs))))
        for a,b in zip(indices,indices[1:]+indices[:1]): edges.add((min(a,b),max(a,b)))
    return {'vertices':len(mesh.vertices),'edges':len(edges),'uv_corners':sum(len(f) for _,f in faces),
            'slots':[name for name in materials if name in used], 'faces':faces}


def check_original(obj,key,expected):
    if obj.type!='MESH' or obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('Unexpected original building object')
    data=adapter.mesh_data(obj); prefix=key+'_'
    def clean(name):
        if not name.startswith(prefix): raise ValueError('Unexpected original material name')
        return name[len(prefix):]
    data['slots']=[clean(name) for name in data['slots']]
    data['faces']=[(clean(name),corners) for name,corners in data['faces']]
    return source.compare(expected,data)


def add_overlay(bpy,key,mesh,materials,original,assets):
    path=assets/(key+'_upper_roof_overlay.obj')
    with path.open('x',encoding='utf-8',newline='\n') as out:
        out.write('# Review only: closed shutters and decorative dormers.\nmtllib NorthMarketDetail.mtl\n')
        variation.write_geometry(out,mesh)
    expected=expected_mesh(mesh,materials); readback=source.read_obj(path,materials)
    source.compare(expected,readback)
    before=set(bpy.data.objects)
    if bpy.ops.wm.obj_import(filepath=str(path),forward_axis='Y',up_axis='Z',global_scale=1.0,
                              use_split_objects=False,use_split_groups=False)!={'FINISHED'}:
        raise ValueError('Overlay import failed')
    added=list(set(bpy.data.objects)-before)
    if len(added)!=1: raise ValueError('Unexpected overlay object count')
    obj=added[0]
    if obj.type!='MESH' or obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('Unexpected overlay object')
    street.check_identity(obj.matrix_world)
    preview.normalize_overlay_slot_order(obj,readback['slots'])
    actual=adapter.mesh_data(obj)
    actual['slots']=[preview.original_material_name(x) for x in actual['slots']]
    actual['faces']=[(preview.original_material_name(name),corners) for name,corners in actual['faces']]
    facts=source.compare(readback,actual)
    for i,mat in enumerate(obj.data.materials):
        name=preview.original_material_name(mat.name)
        if name not in materials: raise ValueError('Unknown overlay material')
        obj.data.materials[i]=preview.additional_material(bpy,name,materials[name],assets)
    obj.name='UpperRoof_Overlay_'+key
    obj.location=original.location.copy(); obj.rotation_euler=original.rotation_euler.copy(); obj.scale=(1,1,1)
    bpy.context.view_layer.update()
    street.check_matrix(obj.matrix_world,original.matrix_world)
    return obj,{'obj_sha256':source.digest(path),'obj_readback':facts}


def build():
    import bpy
    from mathutils import Vector
    scratch=context(); plan=validated_inputs(); baseline=scratch/'baseline.blend'
    if baseline.is_symlink() or source.digest(baseline)!=BLEND_SHA:
        raise ValueError('Baseline scene is not the pinned source')
    if bpy.app.version!=(4,5,3): raise ValueError('Unexpected Blender version')
    if bpy.ops.wm.open_mainfile(filepath=str(baseline),load_ui=False)!={'FINISHED'}:
        raise ValueError('Cannot open baseline scene')
    if OUT.exists() or OUT.is_symlink(): raise ValueError('Refusing to replace an output')
    OUT.mkdir(); assets=OUT/'OverlaySources'; assets.mkdir(); (assets/'Textures').mkdir()
    manifest=None; materials=None; rows={}
    for key,(bid,style) in variation.MODELS.items():
        name=street.MODELS[key]['name']
        manifest,row,objpath,materials=source.source_spec(ROOT/SOURCE,name)
        rows[key]=(row,objpath,style,bid)
    shutil.copyfile(ROOT/SOURCE/'NorthMarketDetail.mtl',assets/'NorthMarketDetail.mtl')
    for info in manifest['textures'].values():
        name=Path(info['path']).name; src=ROOT/SOURCE/'Textures'/name; dest=assets/'Textures'/name
        if src.is_symlink() or dest.exists() or source.digest(src)!=info['sha256']:
            raise ValueError('Unexpected original texture')
        shutil.copyfile(src,dest)
        if source.digest(dest)!=info['sha256']: raise ValueError('Texture copy failed')
    if source.digest(assets/'NorthMarketDetail.mtl')!=manifest['material_sha256']:
        raise ValueError('Material copy failed')
    recipe=street.scene_recipe(manifest,plan)
    if bpy.data.objects.get('Shopfront_Overlay_east_0a') is None:
        raise ValueError('Baseline shopfront is missing')
    overlays={}; evidence={}
    for key,(row,objpath,style,bid) in rows.items():
        original=bpy.data.objects.get('Building_'+key)
        if original is None: raise ValueError('Baseline building missing')
        pos=[0,0,0] if key=='east_0a73564b' else recipe['secondary_local_m']
        yaw=0 if key=='east_0a73564b' else recipe['secondary_yaw_deg']
        bpy.context.view_layer.update(); street.check_pose(original.matrix_world,pos,yaw)
        base_check=check_original(original,key,source.read_obj(objpath,materials))
        building=next(b for b in plan['buildings'] if b['id']==bid)
        party={edge for item in plan.get('party_walls',[]) for who,edge in item['edges'].items() if who==bid}
        mesh,details=variation.make_variation(building,row,style,party)
        obj,checks=add_overlay(bpy,key,mesh,materials,original,assets)
        overlays[key]=obj; evidence[key]={'source_face_check':base_check,'additions':details,**checks}
    scene=bpy.context.scene
    if scene.world is None or not scene.world.use_nodes: raise ValueError('Missing baseline lighting')
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=1.15
    sun=bpy.data.objects.get('ReviewSun')
    if sun is None or sun.type!='LIGHT': raise ValueError('Missing baseline sun')
    sun.data.energy=2.6
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=12
    scene.render.resolution_x=1024; scene.render.resolution_y=576; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    camera=scene.camera
    if camera is None or camera.type!='CAMERA': raise ValueError('Missing baseline camera')
    camera.data.type='PERSP'; camera.data.lens=34
    images={}
    for key,(row,objpath,style,bid) in rows.items():
        obj=bpy.data.objects['Building_'+key]
        b=next(b for b in plan['buildings'] if b['id']==bid)
        outline=b['footprint_local_m']; front=max(p[0] for p in outline)
        entry_y=b['entry']['center_local_xy_m'][1]
        height=b['roof_profile_local_y_z_m'][0][1]
        location=obj.matrix_world @ Vector((front+23,entry_y-14,height+4.2))
        target=obj.matrix_world @ Vector((front-2,entry_y,height*.83))
        camera.location=location; camera.rotation_euler=(target-location).to_track_quat('-Z','Y').to_euler()
        for label,hide in (('before',True),('after',False)):
            for overlay in overlays.values(): overlay.hide_render=hide
            path=OUT/f'{key}_{label}.png'; scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            if not path.is_file() or path.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':
                raise ValueError('Missing review image')
            images[path.name]=source.digest(path)
    for overlay in overlays.values(): overlay.hide_render=False
    bpy.ops.file.pack_all()
    blend=OUT/'north_market_roof_variation_review.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj.type in {'MESH','EMPTY'}: obj.select_set(True)
    glb=OUT/'north_market_roof_variation_review.glb'
    if bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                                 export_yup=True,export_materials='EXPORT')!={'FINISHED'}:
        raise ValueError('Review GLB export failed')
    files=[p for p in OUT.rglob('*') if p.is_file()]
    if sum(p.stat().st_size for p in files)>200*2**20: raise ValueError('Review output too large')
    write_json(OUT/'build.report.json',{'status':'review_only_not_in_game',
        'commit':os.environ['GITHUB_SHA'],'baseline_zip_sha256':ZIP_SHA,'baseline_blend_sha256':BLEND_SHA,
        'source_plan_lf_sha256':PLAN_SHA,'source_manifest_sha256':source.MANIFEST_SHA,
        'images':images,'buildings':evidence,'mesh_names':sorted(o.name for o in scene.objects if o.type=='MESH'),
        'files':{p.relative_to(OUT).as_posix():source.digest(p) for p in files},
        'limits':['New details are separate geometry; original sources and tenancy are unchanged.',
                  'Shutters cover selected existing upper lights; dormers intersect uncut source roofs.',
                  'Surveyed poses are review only. Props/ground are illustrative.',
                  'No Unreal import, collision, navigation, route, streaming or visual approval.']})
    print('Variation source, before/after renders and review scene created.')


def verify():
    import bpy
    context(); report=json.loads((OUT/'build.report.json').read_text(encoding='utf-8'))
    if report.get('commit')!=os.environ['GITHUB_SHA']: raise ValueError('Report commit mismatch')
    for name,sha in report['files'].items():
        path=(OUT/name).resolve(strict=True)
        if not path.is_relative_to(OUT.resolve(strict=True)) or source.digest(path)!=sha:
            raise ValueError('Review output hash mismatch')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.ops.import_scene.gltf(filepath=str(OUT/'north_market_roof_variation_review.glb'))!={'FINISHED'}:
        raise ValueError('Review GLB could not be reimported')
    meshes=[o for o in bpy.data.objects if o.type=='MESH']
    if {o.name for o in meshes}!=set(report['mesh_names']):
        raise ValueError('Reimported GLB mesh inventory differs')
    for obj in meshes:
        if not obj.data.polygons or any(not all(math.isfinite(float(v)) for v in point.co) for point in obj.data.vertices):
            raise ValueError('Invalid reimported geometry')
    write_json(OUT/'manifest.json',{'status':'review_only_not_in_game','commit':report['commit'],
        'build_report_sha256':source.digest(OUT/'build.report.json'),'outputs':report['files'],
        'independent_glb_reimport':'matching mesh names and finite vertices only', 'limits':report['limits']})
    print('Review output hashes and fresh-process GLB inventory verified.')


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    if args==['prepare']: prepare()
    elif args==['build']: build()
    elif args==['verify']: verify()
    else: raise SystemExit('Expected prepare, build or verify')
