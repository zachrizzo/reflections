"""Hosted review of full North Market buildings with varied ridge positions.

The workflow provides isolated GitHub-hosted Linux execution. Its environment
guard prevents accidental local use, not deliberate environment spoofing.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from whole_building_ridge_variation import vary_ridges
from north_market_roof_variation import fit_caption


ROOT=Path(__file__).resolve().parents[2]
REPO='zachrizzo/reflections'
WORKFLOW='.github/workflows/whole-building-roof-review.yml'
ART=Path('ArtDirection/CityPCG/MedievalOpening')
SOURCE=ART/'WholeBuildings/NorthMarketDetailedObj'
FOLLOW=ART/'FollowOn20261115'
TEXT_PINS={
    'Tools/CityPCG/build_whole_buildings_blender.py':'547f7c05aa6ddfec5d369c02624b8207f6070e30f7cc0123e21ef0af92ccb2fd',
    'Tools/CityPCG/whole_building_styles.py':'0391e2ae76c2e363480a5ba79a483e23689c2154248b19bba501026483d68977',
    'Tools/CityPCG/whole_building_ridge_variation.py':'6243210e6d700a78033684d3cf7d31741dd5b5256611b14b0e4afe08faba84ac',
    'Tools/CityPCG/north_market_roof_variation.py':'9231440bb67d9f5637be172c80d2368b9dec62d25d74be9012df79cf3cb7fe6b',
    'Tools/CityPCG/north_market_tenancies.py':'ad2604f21589a4e96881e6d964c7fa7a0e719c7927a533deb2db801f1a993b0f',
    'ArtDirection/CityPCG/Kit/build_facade_kit.py':'38b8daee10bbb38d39fb55db900c0daf4a073c031362f326fac5582293716ee3',
    'ArtDirection/CityPCG/MedievalOpening/build_medieval_facades.py':'ba170669c8e72a7349c363f8f0c2f35b51f26538b32fce01ca1f9fae3270c0f5',
    'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/build_mark_lane.py':'d41ac4ee77f04631b899d961fa966b39443b6586c5e177abe2ea44d1c38ed603',
    'ArtDirection/CityPCG/MedievalOpening/WholeBuildings/prepare_mark_lane_ue_fbx.py':'ed3ae4e7bc9ee39546572b16640925f7c45a32de9706169ac6f5c7a4e5e4d8c7',
    'ArtDirection/CityPCG/MedievalOpening/ThamesWarehouse/build_thames_warehouse.py':'725afcec49688399cf892120b2f7aaa9171d2fa0b8268acafe825926bc649a9b',
    'ArtDirection/CityPCG/MedievalOpening/Guildhall/build_guildhall.py':'fb73559e367d742cc3452537dcd99d4e2fba9a46dfcfef99924d9748c7d74baa',
    'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_east_candidate_20261115.json':'952e955b2ad5c29611b75ba404b653b90c3ddc62ae278364ca5bcb45f71cf208',
    'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_east_plan_20261115.json':'88ea66f0292864f8f6b9924d654a323edb37da9ce307754f7f9f57fc77fbc32f',
    'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_east_style_override_20261115.json':'4a1cde1f79fc474d08b46c7b49a9d67fe2e36c9da2642d041f1f560c2d24c7a7',
    'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_west_candidate_20261115.json':'d222fbcc76b4e89bc649c7ad6bc4a8b354e538a5f4c9669aec876469893b3295',
    'ArtDirection/CityPCG/MedievalOpening/FollowOn20261115/north_market_west_plan_20261115.json':'5d166014b7a688ac4e0e4b70adc4c7da70621a29d34d4e3c648262ff9414f9c0',
}
MANIFEST_SHA='a9aeb89aab3a35914d505475b697ddfa01fb48ad43b1a98c6562bf89bdf49095'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(256*1024),b''): h.update(block)
    return h.hexdigest()


def canonical(data):
    if len(data)>2*2**20: raise ValueError('Text input too large')
    data=data.replace(b'\r\n',b'\n')
    if b'\r' in data: raise ValueError('Unsupported text line ending')
    return data


def context():
    e=os.environ
    expected={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux',
              'GITHUB_REPOSITORY':REPO,'GITHUB_REPOSITORY_ID':'1457160414','GITHUB_REF':'refs/heads/main',
              'GITHUB_WORKFLOW_REF':f'{REPO}/{WORKFLOW}@refs/heads/main'}
    if sys.platform!='linux' or any(e.get(k)!=v for k,v in expected.items()): raise RuntimeError('hosted context')
    sha=e.get('GITHUB_SHA',''); side=e.get('MASSING_SIDE','')
    if (not re.fullmatch(r'[0-9a-f]{40}',sha) or side not in ('east','west')
            or e.get('GITHUB_EVENT_NAME') not in ('push','workflow_dispatch')
            or any(not re.fullmatch(r'[1-9][0-9]{0,19}',e.get(k,'')) for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'))):
        raise RuntimeError('hosted identity')
    if Path(e['GITHUB_WORKSPACE']).resolve(strict=True)!=ROOT: raise RuntimeError('workspace')
    temp=Path(e['RUNNER_TEMP']).resolve(strict=True)
    if temp==ROOT or temp.is_relative_to(ROOT) or shutil.disk_usage(temp).free<2*2**30:
        raise RuntimeError('runner disk')
    result=subprocess.run(['git','-C',str(ROOT),'rev-parse','--verify','HEAD'],
                          stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,check=False)
    if result.returncode or result.stdout!=(sha+'\n').encode('ascii'): raise RuntimeError('checkout')
    with open('/proc/meminfo',encoding='ascii') as stream:
        available=next((line for line in stream if line.startswith('MemAvailable:')),None)
    if available is None or not re.fullmatch(r'MemAvailable:\s+[0-9]+\s+kB\s*',available):
        raise RuntimeError('memory reading')
    if int(available.split()[1])*1024<1536*2**20: raise RuntimeError('runner memory')
    return side,temp/f"whole-roof-{e['GITHUB_RUN_ID']}-{e['GITHUB_RUN_ATTEMPT']}-{side}"


def text_inputs(root):
    for rel,expected in TEXT_PINS.items():
        path=root/rel
        if path.is_symlink() or not path.is_file(): raise ValueError('Missing generator input')
        data=canonical(path.read_bytes())
        if hashlib.sha256(data).hexdigest()!=expected: raise ValueError('Generator input changed')
        yield rel,data


def texture_destination(scratch,role,name):
    if not re.fullmatch(r'[A-Za-z]+',role) or name!=f'T_GLMedieval_{role}.png':
        raise ValueError('Unexpected texture role or filename')
    folder=ART/'Guildhall/Textures' if role=='GuildRubble' else ART/'Textures'
    return scratch/folder/name


def prepare():
    side,scratch=context(); inputs=list(text_inputs(ROOT))
    plan_path=ROOT/FOLLOW/f'north_market_{side}_plan_20261115.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('party_walls')!=[] or len(plan.get('buildings',[]))!=2:
        raise ValueError('Only the two reviewed unpaired plans are supported')
    manifest_path=ROOT/SOURCE/'detailed_obj_manifest.json'
    if manifest_path.is_symlink() or digest(manifest_path)!=MANIFEST_SHA:
        raise ValueError('Texture source manifest changed')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    scratch.mkdir(mode=0o700,exist_ok=False)
    for rel,data in inputs:
        target=scratch/rel; target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as out: out.write(data)
        if digest(target)!=TEXT_PINS[rel]: raise ValueError('Scratch input changed')
    textures=manifest.get('textures',{})
    if len(textures)!=9: raise ValueError('Unexpected texture inventory')
    for role,info in textures.items():
        name=Path(info['path']).name
        if name!=f'T_GLMedieval_{role}.png': raise ValueError('Unexpected texture name')
        source=ROOT/SOURCE/'Textures'/name
        if source.is_symlink() or not source.is_file() or not 8<source.stat().st_size<16*2**20 or digest(source)!=info['sha256']:
            raise ValueError('Texture differs from source manifest')
        with source.open('rb') as stream:
            if stream.read(8)!=b'\x89PNG\r\n\x1a\n': raise ValueError('Invalid source texture')
        target=texture_destination(scratch,role,name)
        target.parent.mkdir(parents=True,exist_ok=True)
        with source.open('rb') as src,target.open('xb') as out: shutil.copyfileobj(src,out,256*1024)
        if digest(target)!=info['sha256']: raise ValueError('Texture scratch copy changed')
    print('Pinned generator, plans and textures prepared in isolated scratch.')


def report_pair(before,after,plan,source_manifest):
    if (before.get('source_tile')!=plan['source_tile'] or after.get('source_tile')!=plan['source_tile']
            or before.get('roof_variation') is not None or after.get('roof_variation')!='asymmetric-ridges-v1'):
        raise ValueError('Unexpected builder report')
    base=before.get('buildings',{}); changed=after.get('buildings',{})
    wanted={item['id'] for item in plan['buildings']}
    if set(base)!=wanted or set(changed)!=wanted: raise ValueError('Builder inventory differs')
    for building in plan['buildings']:
        key=building['id']; old=base[key]; new=changed[key]
        source=source_manifest.get('buildings',{}).get(key)
        if not source or old.get('style')!=source.get('style'):
            raise ValueError('Builder style differs from the reviewed building source')
        for field in ('world_pivot_m','yaw_deg','axis_x_world_xy','axis_y_world_xy',
                      'footprint_local_m','entry','party_wall_edges','collision','style','source_height_cm'):
            if old.get(field)!=new.get(field): raise ValueError('Survey or collision metadata changed')
        if old.get('party_wall_edges')!=[] or old.get('collision') is not False:
            raise ValueError('Unexpected party wall or collision')
        if (old.get('world_pivot_m')!=building['origin_m'] or old.get('entry')!=building['entry']
                or abs(old.get('yaw_deg',math.inf)-building['rotation_yaw_deg'])>1e-5
                or abs(old.get('source_height_cm',math.inf)-100*building['source_max_height_m'])>1e-5
                or len(old.get('footprint_local_m',[]))!=len(building['footprint_local_m'])
                or any(math.dist(a,b)>2e-5 for a,b in
                       zip(old['footprint_local_m'],building['footprint_local_m']))):
            raise ValueError('Built placement differs from the surveyed plan')
        baseline_profile=old['roof_profile_local_y_z_m']
        source_profile=source['roof_profile_local_y_z_m']
        if len(baseline_profile)!=len(source_profile) or any(abs(a-b)>2e-5
                for p,q in zip(baseline_profile,source_profile) for a,b in zip(p,q)):
            raise ValueError('Baseline roof profile differs from the reviewed source')
        expected=vary_ridges(baseline_profile,key,building['source_max_height_m'])
        actual=new['roof_profile_local_y_z_m']
        if len(expected)!=len(actual) or any(abs(a-b)>1e-7 for p,q in zip(expected,actual) for a,b in zip(p,q)):
            raise ValueError('Built roof differs from the deterministic profile')
    return wanted


def checked_fbx(folder,row):
    rel=Path(row['fbx'])
    if len(rel.parts)!=2 or rel.parts[0]!='Source' or rel.suffix.lower()!='.fbx':
        raise ValueError('Unexpected FBX report path')
    path=folder/rel
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<40*2**20:
        raise ValueError('Invalid generated FBX')
    if digest(path)!=row['roundtrip']['fbx_sha256']:
        raise ValueError('FBX differs from generator round trip')
    return path


def lower_signature(obj,eave):
    """Compare position/UV/material below eaves; normals and topology remain unproven."""
    mesh=obj.data
    if len(mesh.uv_layers)!=1 or not mesh.materials: raise ValueError('Missing UV or material')
    uv=mesh.uv_layers.active.data; faces=[]
    for polygon in mesh.polygons:
        coords=[mesh.vertices[mesh.loops[i].vertex_index].co for i in polygon.loop_indices]
        if any(not all(math.isfinite(float(v)) for v in p) for p in coords): raise ValueError('Nonfinite mesh')
        texcoords=[tuple(float(v) for v in uv[i].uv) for i in polygon.loop_indices]
        if any(len(uvpoint)!=2 or not all(math.isfinite(v) for v in uvpoint) for uvpoint in texcoords):
            raise ValueError('Nonfinite FBX UV coordinate')
        if max(p.z for p in coords)>=eave-.10: continue
        if not 0<=polygon.material_index<len(mesh.materials): raise ValueError('Invalid material')
        name=mesh.materials[polygon.material_index].name
        corners=[]
        for p,texcoord in zip(coords,texcoords):
            corners.append(tuple(round(float(v),5) for v in (*p,*texcoord)))
        rotations=[tuple(corners[i:]+corners[:i]) for i in range(len(corners))]
        faces.append((name,min(rotations)))
    if not faces: raise ValueError('Missing lower building geometry')
    encoded=json.dumps(sorted(faces),separators=(',',':'),allow_nan=False).encode('ascii')
    return {'polygons':len(faces),'position_uv_material_sha256':hashlib.sha256(encoded).hexdigest()}


def roof_vertex_evidence(obj,profile):
    """Require sloped clay-tile FBX faces at every reported ridge station."""
    mesh=obj.data; tile_vertices=set()
    for polygon in mesh.polygons:
        if not 0<=polygon.material_index<len(mesh.materials):
            raise ValueError('Invalid ridge material')
        material=mesh.materials[polygon.material_index]
        if (material and material.name=='M_GLMedieval_ClayTile'
                and math.isfinite(float(polygon.normal.z)) and .05<float(polygon.normal.z)<.99):
            tile_vertices.update(polygon.vertices)
    result=[]
    for y,z in profile[1::2]:
        count=sum(1 for i in tile_vertices if abs(float(mesh.vertices[i].co.y)-y)<.002
                  and abs(float(mesh.vertices[i].co.z)-(z+.089))<.002)
        if not count: raise ValueError('FBX lacks an expected tiled ridge')
        result.append(count)
    return result


def import_one(bpy,path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.ops.import_scene.fbx(filepath=str(path),use_custom_normals=True,use_image_search=False,
                                use_anim=False)!={'FINISHED'}: raise ValueError('FBX import failed')
    objects=list(bpy.context.scene.objects)
    if len(objects)!=1 or objects[0].type!='MESH': raise ValueError('Expected one building mesh')
    obj=objects[0]
    if obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('Unexpected building state')
    if any(not math.isfinite(float(obj.matrix_world[i][j])) or
           abs(float(obj.matrix_world[i][j])-(1. if i==j else 0.))>1e-6
           for i in range(4) for j in range(4)): raise ValueError('Unexpected building transform')
    return obj


def check_reimport_facts(row,actual):
    for key in ('bounds_cm','materials','uv_layers','triangles','pre_export_channels'):
        if row.get(key)!=actual.get(key): raise ValueError('Fresh FBX channel audit failed: '+key)


def fresh_fbx_facts(obj):
    mesh=obj.data; mesh.calc_loop_triangles()
    if not mesh.vertices or not mesh.polygons or len(mesh.uv_layers)!=1 or mesh.uv_layers.active is None:
        raise ValueError('Incomplete FBX mesh channels')
    if any(not all(math.isfinite(float(value)) for value in vertex.co) for vertex in mesh.vertices):
        raise ValueError('Nonfinite FBX vertex')
    if any(m is None for m in mesh.materials): raise ValueError('Missing FBX material')
    return {'bounds_cm':[[round(fn(v.co[i] for v in mesh.vertices)*100,3) for i in range(3)] for fn in (min,max)],
            'materials':[m.name for m in mesh.materials], 'uv_layers':[layer.name for layer in mesh.uv_layers],
            'triangles':len(mesh.loop_triangles),
            'pre_export_channels':{'vertices':len(mesh.vertices),'edges':len(mesh.edges),
                                   'polygons':len(mesh.polygons),'color_attributes':len(mesh.color_attributes)}}


def check_fbx_textures(bpy,obj,textures,scratch):
    """Match every textured material's reimported image to the source PNG."""
    result={}
    for material in obj.data.materials:
        if not material.name.startswith('M_GLMedieval_') or not material.use_nodes or material.node_tree is None:
            raise ValueError('Unexpected FBX material')
        role=material.name.removeprefix('M_GLMedieval_')
        nodes=[n for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
        outputs=[n for n in material.node_tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
        if len(outputs)!=1 or len(outputs[0].inputs['Surface'].links)!=1:
            raise ValueError('Ambiguous FBX material surface')
        shader=outputs[0].inputs['Surface'].links[0].from_node
        if shader.type!='BSDF_PRINCIPLED': raise ValueError('Unsupported FBX material shader')
        color_links=shader.inputs['Base Color'].links
        if role not in textures:
            if nodes or color_links: raise ValueError('Unexpected image in solid material')
            continue
        if len(nodes)!=1 or nodes[0].image is None: raise ValueError('Missing textured material image')
        if (len(color_links)!=1 or color_links[0].from_node!=nodes[0]
                or color_links[0].from_socket.name!='Color'):
            raise ValueError('Texture does not feed the FBX base color')
        image=nodes[0].image; packed=image.packed_file
        if packed:
            if not 8<packed.size<16*2**20: raise ValueError('Invalid packed texture size')
            data=packed.data
            if len(data)!=packed.size: raise ValueError('Packed texture size mismatch')
            sha=hashlib.sha256(data).hexdigest(); kind='packed'
        else:
            path=Path(bpy.path.abspath(image.filepath)).resolve(strict=True)
            if not path.is_relative_to(scratch) or not path.is_file() or path.stat().st_size>16*2**20:
                raise ValueError('Texture path leaves isolated scratch')
            sha=digest(path); kind='external'
        if sha!=textures[role]['sha256']: raise ValueError('Reimported texture changed')
        result[role]={'sha256':sha,'storage':kind}
    if not result: raise ValueError('No textured materials found')
    return result


def add_caption(bpy,scene,camera,span):
    curve=bpy.data.curves.new('ReviewLabel','FONT'); curve.body='ILLUSTRATIVE / NOT IN GAME'
    curve.size=span*.027; curve.align_x='LEFT'; curve.align_y='BOTTOM_BASELINE'
    label=bpy.data.objects.new('ReviewLabel',curve); scene.collection.objects.link(label)
    label.parent=camera; label.location=(0,0,-1)
    white=bpy.data.materials.new('ReviewLabelWhite'); white.use_nodes=True
    nodes=white.node_tree.nodes; nodes.clear(); out=nodes.new('ShaderNodeOutputMaterial'); emit=nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value=(1,1,1,1); emit.inputs['Strength'].default_value=2
    white.node_tree.links.new(emit.outputs[0],out.inputs['Surface']); curve.materials.append(white)
    bpy.context.view_layer.update()
    frame_points=camera.data.view_frame(scene=scene)
    frame=(min(p.x for p in frame_points),max(p.x for p in frame_points),
           min(p.y for p in frame_points),max(p.y for p in frame_points))
    bounds=(min(p[0] for p in label.bound_box),max(p[0] for p in label.bound_box),
            min(p[1] for p in label.bound_box),max(p[1] for p in label.bound_box))
    position,rect=fit_caption(frame,bounds,margin=span*.04,padding=span*.012)
    label.location=(position[0],position[1],-1)
    background=bpy.data.curves.new('ReviewBackdrop','CURVE'); background.dimensions='2D'; background.fill_mode='BOTH'
    spline=background.splines.new('POLY'); spline.points.add(3)
    for point,(x,y) in zip(spline.points,((rect[0],rect[2]),(rect[1],rect[2]),(rect[1],rect[3]),(rect[0],rect[3]))):
        point.co=(x,y,0,1)
    spline.use_cyclic_u=True
    backdrop=bpy.data.objects.new('ReviewBackdrop',background); scene.collection.objects.link(backdrop)
    backdrop.parent=camera; backdrop.location=(0,0,-1.01)
    dark=bpy.data.materials.new('ReviewLabelDark'); dark.use_nodes=True
    nodes=dark.node_tree.nodes; nodes.clear(); out=nodes.new('ShaderNodeOutputMaterial'); emit=nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value=(.012,.012,.012,1)
    dark.node_tree.links.new(emit.outputs[0],out.inputs['Surface']); background.materials.append(dark)


def render(bpy,obj,bounds,path):
    from mathutils import Vector
    low,high=bounds; center=Vector(tuple((a+b)*.5 for a,b in zip(low,high)))
    span=max(high[i]-low[i] for i in range(3))
    if not 2<span<100: raise ValueError('Unexpected building size')
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=10
    scene.render.resolution_x=1024; scene.render.resolution_y=640; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.world=bpy.data.worlds.new('ReviewWorld'); scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.48,.51,.55,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=1.1
    light=bpy.data.lights.new('ReviewSun','SUN'); light.energy=2.6
    sun=bpy.data.objects.new('ReviewSun',light); scene.collection.objects.link(sun)
    sun.rotation_euler=tuple(math.radians(v) for v in (25,-30,-25))
    camera=bpy.data.objects.new('ReviewCamera',bpy.data.cameras.new('ReviewCamera')); scene.collection.objects.link(camera)
    scene.camera=camera; camera.data.type='ORTHO'; camera.data.ortho_scale=span*1.55
    camera.location=center+Vector((span*1.3,-span*.9,span*.85))
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    add_caption(bpy,scene,camera,span)
    scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
    with path.open('rb') as stream: signature=stream.read(8)
    if signature!=b'\x89PNG\r\n\x1a\n': raise ValueError('Missing review image')


def compare():
    import bpy
    if bpy.app.version!=(4,5,3): raise ValueError('Unexpected Blender version')
    side,scratch=context(); list(text_inputs(ROOT))
    plan=json.loads((scratch/FOLLOW/f'north_market_{side}_plan_20261115.json').read_text())
    baseline=scratch/'baseline'; variant=scratch/'variant'
    old=json.loads((baseline/'whole_buildings_kit.json').read_text()); new=json.loads((variant/'whole_buildings_kit.json').read_text())
    source_manifest=json.loads((ROOT/SOURCE/'detailed_obj_manifest.json').read_text(encoding='utf-8'))
    textures=source_manifest['textures']
    expected_plan=TEXT_PINS[str(FOLLOW/f'north_market_{side}_plan_20261115.json')]
    expected_candidate=TEXT_PINS[str(FOLLOW/f'north_market_{side}_candidate_20261115.json')]
    if any(r.get('plan_sha256')!=expected_plan or r.get('candidate_sha256')!=expected_candidate for r in (old,new)):
        raise ValueError('Builder input hashes differ')
    override=TEXT_PINS[str(FOLLOW/'north_market_east_style_override_20261115.json')] if side=='east' else None
    if any(r.get('style_overrides_sha256')!=override for r in (old,new)):
        raise ValueError('Builder style override differs from reviewed source')
    keys=report_pair(old,new,plan,source_manifest)
    out=ROOT/f'ci-whole-building-roof-massing-{side}'
    if out.exists() or out.is_symlink(): raise ValueError('Review output already exists')
    out.mkdir(); evidence={}
    for building in plan['buildings']:
        key=building['id']; short=key.rsplit('_',1)[-1][:8]
        before_path=checked_fbx(baseline,old['buildings'][key]); after_path=checked_fbx(variant,new['buildings'][key])
        before_obj=import_one(bpy,before_path); eave=plan['styles'][key]['eave_m']
        before_facts=fresh_fbx_facts(before_obj); check_reimport_facts(old['buildings'][key],before_facts)
        before_textures=check_fbx_textures(bpy,before_obj,textures,scratch)
        before_sig=lower_signature(before_obj,eave)
        before_ridges=roof_vertex_evidence(before_obj,old['buildings'][key]['roof_profile_local_y_z_m'])
        bounds=[[v/100 for v in row] for row in old['buildings'][key]['bounds_cm']]
        render(bpy,before_obj,bounds,out/f'{short}_before.png')
        after_obj=import_one(bpy,after_path); after_sig=lower_signature(after_obj,eave)
        after_facts=fresh_fbx_facts(after_obj); check_reimport_facts(new['buildings'][key],after_facts)
        after_textures=check_fbx_textures(bpy,after_obj,textures,scratch)
        if before_sig!=after_sig: raise ValueError('Lower facade geometry, UV or material changed')
        after_ridges=roof_vertex_evidence(after_obj,new['buildings'][key]['roof_profile_local_y_z_m'])
        render(bpy,after_obj,bounds,out/f'{short}_after.png')
        evidence[key]={'before_fbx_sha256':digest(before_path),'after_fbx_sha256':digest(after_path),
                       'fresh_fbx_facts':{'baseline':before_facts,'variant':after_facts},
                       'reimported_textures':{'baseline':before_textures,'variant':after_textures},
                       'lower_facade_check':before_sig,'fbx_ridge_vertex_counts':{'baseline':before_ridges,'variant':after_ridges},
                       'baseline_profile':old['buildings'][key]['roof_profile_local_y_z_m'],
                       'variant_profile':new['buildings'][key]['roof_profile_local_y_z_m']}
    # Retain both whole-building source trees, including generated FBXs and
    # any Blender-created texture folders, only after the comparisons pass.
    for label,folder in (('baseline',baseline),('variant',variant)):
        files=[p for p in folder.rglob('*') if p.is_file()]
        if len(files)>100 or any(p.is_symlink() for p in folder.rglob('*')) or sum(p.stat().st_size for p in files)>100*2**20:
            raise ValueError('Builder output is unsafe or too large')
        shutil.copytree(folder,out/label)
    # Keep the exact pinned source PNGs beside the review FBXs even if Blender
    # resolved an external image from elsewhere in the scratch tree.
    texture_output=out/'SourceTextures'; texture_output.mkdir()
    for role,info in textures.items():
        name=Path(info['path']).name; source=ROOT/SOURCE/'Textures'/name; target=texture_output/name
        if source.is_symlink() or digest(source)!=info['sha256'] or target.exists():
            raise ValueError('Texture source changed during review')
        with source.open('rb') as src,target.open('xb') as dst: shutil.copyfileobj(src,dst,256*1024)
        if digest(target)!=info['sha256']: raise ValueError('Texture output changed')
    files=[p for p in out.rglob('*') if p.is_file()]
    with (out/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump({'status':'review_only_not_in_game','commit':os.environ['GITHUB_SHA'],'side':side,
          'candidate_lf_sha256':expected_candidate,'plan_lf_sha256':expected_plan,
          'texture_manifest_sha256':MANIFEST_SHA,'buildings':evidence,
          'files':{p.relative_to(out).as_posix():digest(p) for p in files},
          'limits':['Complete independently generated buildings; not overlay stacks.',
            'Unreal import, exact FBX round-trip channels, collision, navigation, routes and visual approval are pending.',
            'Party-wall plans and non-symmetric or narrow roof ranges are rejected.',
            'Source GLB primitive to Unreal section mapping remains unverified.']},stream,indent=2,sort_keys=True)
        stream.write('\n')
    print('Complete-building profiles, lower facades and paired renders checked.')


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    if args==['prepare']: prepare()
    elif args==['compare']: compare()
    else: raise SystemExit('Expected prepare or compare')
