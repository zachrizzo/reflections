"""Build or inspect a review-only North Market scene on the hosted runner."""
import json
import math
from pathlib import Path
import runpy
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import north_market_street_review_common as c
import north_market_roundtrip_common as source
import north_market_hosted_blender as adapter
import north_market_tenancy_preview as tenancy_preview


def write_json(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,sort_keys=True); stream.write('\n')


def only_new_objects(bpy,before):
    added=[obj for obj in bpy.data.objects if obj not in before]
    if not added or not any(obj.type=='MESH' for obj in added):
        raise ValueError('import created no mesh')
    return added


def mesh_facts(objects):
    meshes=[obj for obj in objects if obj.type=='MESH']
    if not meshes: raise ValueError('missing meshes')
    count=0; vertices=0; materials=[]; low=[math.inf]*3; high=[-math.inf]*3
    for obj in meshes:
        obj.data.calc_loop_triangles()
        count+=len(obj.data.loop_triangles); vertices+=len(obj.data.vertices)
        materials.extend(m.name for m in obj.data.materials if m)
        for vertex in obj.data.vertices:
            point=obj.matrix_world @ vertex.co
            if not all(math.isfinite(float(x)) for x in point):
                raise ValueError('non-finite mesh coordinates')
            for axis in range(3):
                low[axis]=min(low[axis],float(point[axis])); high[axis]=max(high[axis],float(point[axis]))
    if not 0<count<300000 or not vertices or not materials:
        raise ValueError('invalid imported mesh budget or materials')
    return {'meshes':len(meshes),'vertices':vertices,'triangles':count,
            'bounds_m':[low,high],'dimensions_m':[high[i]-low[i] for i in range(3)],
            'materials':sorted(set(materials))}


def import_prop(bpy,path,label,position,yaw):
    before=set(bpy.data.objects)
    if bpy.ops.import_scene.gltf(filepath=str(path))!={'FINISHED'}:
        raise ValueError('GLB import failed')
    added=only_new_objects(bpy,before); bpy.context.view_layer.update(); facts=mesh_facts(added)
    if any(obj.parent and obj.parent not in added for obj in added):
        raise ValueError('prop import unexpectedly parented to an existing scene object')
    if label=='handcart' and facts['triangles']!=9432:
        raise ValueError('handcart geometry differs from the audited source')
    if label=='cargo' and facts['triangles']!=2892:
        raise ValueError('cargo geometry differs from the audited source')
    expected={'handcart':(2.7281,1.606,1.3446),'cargo':(1.0871,.9282,.685)}.get(label)
    if expected and (any(abs(a-b)>.01 for a,b in zip(facts['dimensions_m'],expected,strict=True))
                     or abs(facts['bounds_m'][0][2])>.01):
        raise ValueError('quay prop scale or ground pivot differs from its audit')
    parent=bpy.data.objects.new('Placement_'+label,None)
    bpy.context.scene.collection.objects.link(parent)
    roots=[obj for obj in added if obj.parent not in added]
    for obj in roots: obj.parent=parent
    parent.location=position; parent.rotation_euler[2]=math.radians(yaw)
    for i,obj in enumerate(sorted((o for o in added if o.type=='MESH'),key=lambda o:o.name)):
        obj.name=f'Prop_{label}_{i:02d}'
    return facts


def import_building(bpy,bundle,fbx,key,position,yaw):
    name=c.MODELS[key]['name']
    _,_,obj_path,materials=source.source_spec(c.ROOT/c.BUILDING_BASE,name)
    expected=source.read_obj(obj_path,materials)
    before=set(bpy.data.objects)
    if bpy.ops.import_scene.fbx(filepath=str(fbx),use_custom_normals=True,
                                use_image_search=False,use_anim=False)!={'FINISHED'}:
        raise ValueError('FBX import failed')
    added=only_new_objects(bpy,before); meshes=[o for o in added if o.type=='MESH']
    if len(added)!=1 or len(meshes)!=1: raise ValueError('unexpected FBX object count')
    obj=meshes[0]
    if obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('unexpected FBX parent, modifiers, vertex groups or shape keys')
    if len(obj.data.uv_layers)!=1 or len(obj.data.color_attributes)!=0:
        raise ValueError('unexpected FBX UV or color channels')
    c.check_identity(obj.matrix_world)
    facts=source.compare(expected,adapter.mesh_data(obj))
    textures=adapter.material_textures(bpy,obj,materials,bundle)
    obj.name='Building_'+key
    obj.location=position; obj.rotation_euler=(0,0,math.radians(yaw)); obj.scale=(1,1,1)
    bpy.context.view_layer.update(); c.check_pose(obj.matrix_world,position,yaw)
    # Avoid Blender's .001 slot renaming before importing the other verified FBX.
    for material in obj.data.materials:
        if material: material.name=key+'_'+material.name
    return {'face_check':facts,'textures':textures}


def import_tenancy_overlay(bpy,folder):
    overlay=folder/'tenancies_overlay.obj'
    combined=folder/(c.MODELS['east_0a73564b']['name']+'_tenancies_review.obj')
    report=json.loads((folder/'tenancies.report.json').read_text(encoding='utf-8'))
    c.check_tenancy_report(report,c.digest(overlay),c.digest(combined))
    _,_,_,materials=source.source_spec(c.ROOT/c.BUILDING_BASE,c.MODELS['east_0a73564b']['name'])
    expected=source.read_obj(overlay,materials)
    before=set(bpy.data.objects)
    if bpy.ops.wm.obj_import(filepath=str(overlay),forward_axis='Y',up_axis='Z',global_scale=1.0,
                             use_split_objects=False,use_split_groups=False)!={'FINISHED'}:
        raise ValueError('tenancy overlay OBJ import failed')
    added=only_new_objects(bpy,before)
    if len(added)!=1 or added[0].type!='MESH': raise ValueError('unexpected tenancy overlay objects')
    obj=added[0]
    if obj.parent or obj.modifiers or obj.vertex_groups or obj.data.shape_keys:
        raise ValueError('unexpected tenancy overlay parent or modifiers')
    if len(obj.data.uv_layers)!=1 or len(obj.data.color_attributes)!=0:
        raise ValueError('unexpected tenancy overlay UV or color channels')
    c.check_identity(obj.matrix_world)
    if len(obj.data.vertices)!=report['added_vertices'] or len(obj.data.polygons)!=report['added_faces']:
        raise ValueError('tenancy overlay geometry counts differ')
    tenancy_preview.normalize_overlay_slot_order(obj,expected['slots'])
    actual=adapter.mesh_data(obj)
    actual['slots']=[tenancy_preview.original_material_name(x) for x in actual['slots']]
    actual['faces']=[(tenancy_preview.original_material_name(role),corners) for role,corners in actual['faces']]
    facts=source.compare(expected,actual)
    textures={}
    for index,mat in enumerate(obj.data.materials):
        name=tenancy_preview.original_material_name(mat.name)
        spec=materials[name]
        obj.data.materials[index]=tenancy_preview.additional_material(bpy,name,spec,folder)
        textures[name]=spec['texture'] if spec['texture'] else {'kind':'solid','kd':spec['kd']}
    obj.name='Shopfront_Overlay_east_0a'; obj.location=(0,0,0); obj.rotation_euler=(0,0,0); obj.scale=(1,1,1)
    bpy.context.view_layer.update(); c.check_pose(obj.matrix_world,[0,0,0],0)
    return {'overlay_sha256':c.TENANCY_OVERLAY_SHA,'face_check':facts,'textures':textures,
            'status':'closed visual details, review only; no Unreal or gameplay approval'}


def kit_mesh(bpy,mesh,label,position,yaw,materials):
    vertices=[]; faces=[]; roles=[]
    for points,role,_ in mesh.triangles:
        start=len(vertices); vertices.extend(points); faces.append((start,start+1,start+2)); roles.append(role)
    data=bpy.data.meshes.new('Mesh_'+label); data.from_pydata(vertices,[],faces); data.update()
    names=sorted(set(roles))
    for name in names: data.materials.append(materials[name])
    for face,role in zip(data.polygons,roles,strict=True): face.material_index=names.index(role)
    obj=bpy.data.objects.new('Prop_'+label+'_00',data); bpy.context.scene.collection.objects.link(obj)
    obj.location=position; obj.rotation_euler[2]=math.radians(yaw)
    return {'triangles':len(faces),'materials':names}


def add_ground(bpy,root):
    data=bpy.data.meshes.new('IllustrativeGroundMesh')
    data.from_pydata([(24,-38,-0.025),(38,-38,-0.025),(38,2,-0.025),(24,2,-0.025)],[],[(0,1,2,3)])
    data.update(); uv=data.uv_layers.new(name='GroundUV')
    for poly in data.polygons:
        for loop in poly.loop_indices:
            x,y,_=data.vertices[data.loops[loop].vertex_index].co
            uv.data[loop].uv=((x-24)/15.12,(y+38)/12.13)
    mat=bpy.data.materials.new('Illustrative_CobbleEarth'); mat.use_nodes=True
    nodes=mat.node_tree.nodes; links=mat.node_tree.links; shader=nodes.get('Principled BSDF')
    for role,suffix in (('color','Color'),('normal','Normal'),('roughness','Roughness')):
        node=nodes.new('ShaderNodeTexImage')
        node.image=bpy.data.images.load(str(root/c.GROUND/f'T_GL1450_Ground_{suffix}.png'),check_existing=True)
        node.image.colorspace_settings.name='sRGB' if role=='color' else 'Non-Color'
        node.extension='REPEAT'
        if role=='color': links.new(node.outputs['Color'],shader.inputs['Base Color'])
        elif role=='roughness': links.new(node.outputs['Color'],shader.inputs['Roughness'])
        else:
            normal=nodes.new('ShaderNodeNormalMap'); links.new(node.outputs['Color'],normal.inputs['Color'])
            links.new(normal.outputs['Normal'],shader.inputs['Normal'])
    data.materials.append(mat)
    obj=bpy.data.objects.new('ReviewGround_Illustrative',data); bpy.context.scene.collection.objects.link(obj)


def add_lighting_and_camera(bpy):
    scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=12
    scene.render.resolution_x=1024; scene.render.resolution_y=576; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    if scene.world is None: scene.world=bpy.data.worlds.new('ReviewWorld')
    scene.world.use_nodes=True; bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(0.48,0.51,0.55,1); bg.inputs['Strength'].default_value=0.75
    light=bpy.data.lights.new('ReviewSun','SUN'); light.energy=2.0
    sun=bpy.data.objects.new('ReviewSun',light); scene.collection.objects.link(sun)
    sun.rotation_euler=tuple(math.radians(x) for x in (25,-30,-25))
    camera=bpy.data.cameras.new('StreetReviewCamera'); obj=bpy.data.objects.new('StreetReviewCamera',camera)
    scene.collection.objects.link(obj); scene.camera=obj; camera.lens=27
    # A camera-relative, emissive caption appears only in diagnostic renders.
    text=bpy.data.curves.new('ReviewCaption','FONT'); text.body='ILLUSTRATIVE REVIEW  /  NOT IN GAME'; text.size=0.038
    caption=bpy.data.objects.new('ReviewCaption',text); scene.collection.objects.link(caption)
    caption.parent=obj; caption.location=(-0.60,0.315,-1.0)
    mat=bpy.data.materials.new('ReviewCaptionWhite'); mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF'); shader.inputs['Base Color'].default_value=(1,1,1,1)
    if 'Emission Color' in shader.inputs:
        shader.inputs['Emission Color'].default_value=(1,1,1,1); shader.inputs['Emission Strength'].default_value=2.0
    text.materials.append(mat)
    return obj


def point_camera(camera,location,target):
    from mathutils import Vector
    camera.location=location; camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()


def build():
    import bpy
    if bpy.app.version!=(4,5,3): raise RuntimeError('unexpected Blender release')
    root,scratch=c.hosted_context(); c.validate_inputs(root)
    if not scratch.is_dir() or scratch.is_symlink(): raise RuntimeError('missing prepared scratch')
    out=root/'ci-north-market-street-review'
    if out.exists() or out.is_symlink(): raise RuntimeError('review output already exists')
    out.mkdir(); assets=out/'ReusableAssets'; assets.mkdir(); archives=scratch/'review-bundles'; archives.mkdir()
    manifest=json.loads((root/c.MANIFEST).read_text(encoding='utf-8'))
    plan=json.loads((root/c.PLAN).read_text(encoding='utf-8')); recipe=c.scene_recipe(manifest,plan)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    evidence={}
    for key in c.MODELS:
        dest=archives/key; bundle,fbx=c.unpack_building(root/c.REVIEW/(key+'.zip'),dest,key)
        pos=[0,0,0] if key=='east_0a73564b' else recipe['secondary_local_m']
        yaw=0 if key=='east_0a73564b' else recipe['secondary_yaw_deg']
        evidence[key]=import_building(bpy,bundle,fbx,key,pos,yaw)
    tenancy=scratch/'tenancy'
    if tenancy.is_symlink() or not tenancy.is_dir() or tenancy.resolve(strict=True)!=tenancy:
        raise ValueError('missing independently regenerated tenancy')
    tenancy_evidence=import_tenancy_overlay(bpy,tenancy)
    generated=scratch/'Saved/MedievalLondon/MarketDressing'
    sources={'market_stall':generated/'SM_GL1450_MarketStall.glb',
             'crate_group':generated/'SM_GL1450_CratesAndBasket.glb',
             'cask_group':generated/'SM_GL1450_CaskAndSack.glb',
             'handcart':root/c.QUAY/'SM_GL1450_QuayHandcart.glb',
             'cargo':root/c.QUAY/'SM_GL1450_QuayCargo.glb'}
    props={}
    for label,path in sources.items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16*2**20:
            raise ValueError('prop source missing or exceeds limit')
        dst=assets/(label+'.glb')
        with path.open('rb') as src,dst.open('xb') as target: shutil.copyfileobj(src,target,256*1024)
        position,yaw=c.PROP_LAYOUT[label]
        props[label]={'source_sha256':c.digest(dst),'facts':import_prop(bpy,dst,label,position,yaw)}
    kit=runpy.run_path(str(root/c.KIT)); material_map={}
    for name,color in kit['MATERIALS'].items():
        mat=bpy.data.materials.new(name); mat.diffuse_color=(*color,1); mat.use_nodes=True
        mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color,1)
        material_map[name]=mat
    meshes={'trestle':kit['stallboard'](),'bowl_a':kit['turned_bowl'](),
            'bowl_b':kit['turned_bowl'](),'ale_stake':kit['ale_stake']()}
    for label,mesh in meshes.items():
        position,yaw=c.PROP_LAYOUT[label]
        props[label]=kit_mesh(bpy,mesh,label,position,yaw,material_map)
    (assets/'LondonMarketProps.mtl').write_bytes(kit['material_bytes']())
    for label in ('trestle','bowl_a','ale_stake'):
        (assets/(label+'.obj')).write_bytes(kit['obj_bytes'](meshes[label]))
    # Publish the independently regenerated overlay separately, never the
    # combined building OBJ (which would duplicate the existing FBX shell).
    tenancy_assets=assets/'Tenancies'; tenancy_assets.mkdir()
    for rel in (Path('tenancies_overlay.obj'),Path('tenancies.report.json'),Path('NorthMarketDetail.mtl')):
        with (tenancy/rel).open('rb') as src,(tenancy_assets/rel).open('xb') as dst:
            shutil.copyfileobj(src,dst,256*1024)
    (tenancy_assets/'Textures').mkdir()
    for image in sorted((tenancy/'Textures').iterdir()):
        if image.is_symlink() or not image.is_file() or image.suffix!='.png':
            raise ValueError('unexpected tenancy texture')
        with image.open('rb') as src,(tenancy_assets/'Textures'/image.name).open('xb') as dst:
            shutil.copyfileobj(src,dst,256*1024)
    add_ground(bpy,root); camera=add_lighting_and_camera(bpy)
    scene=bpy.context.scene
    views=(('street_eye_level.png',(30.8,-14.8,1.7),(25.9,-21.05,2.1)),
           ('street_trestle.png',(30.7,-27.8,1.7),(25.9,-23.4,2.0)))
    for name,location,target in views:
        point_camera(camera,location,target); scene.render.filepath=str(out/name)
        bpy.ops.render.render(write_still=True)
    bpy.ops.file.pack_all()
    for image in bpy.data.images:
        if image.source=='FILE' and image.filepath and not image.packed_file:
            raise ValueError('scene has an unpacked external image')
    blend=out/'north_market_street_review.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj.type in {'MESH','EMPTY'}: obj.select_set(True)
    glb=out/'north_market_street_review.glb'
    if bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                                 export_yup=True,export_materials='EXPORT')!={'FINISHED'}:
        raise ValueError('review scene GLB export failed')
    images=[out/name for name,_,_ in views]
    if any(path.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n' for path in images):
        raise ValueError('missing rendered PNG')
    meshes=sorted(o.name for o in scene.objects if o.type=='MESH')
    if len(meshes)<10: raise ValueError('incomplete review scene')
    files=[blend,glb,*images,*sorted(p for p in assets.rglob('*') if p.is_file())]
    if sum(p.stat().st_size for p in files)>200*2**20: raise ValueError('scene output exceeds limit')
    write_json(out/'build.report.json',{
        'status':'illustrative review only; not a playable or map-approved scene',
        'commit':__import__('os').environ['GITHUB_SHA'],'blender':bpy.app.version_string,
        'recipe':recipe,'inputs':{p.as_posix():{'sha256':h,'raw_sha256':c.digest(root/p),
            'hash_method':'sha256_lf_canonical' if p==c.PLAN else 'sha256_raw'} for p,h in c.INPUTS.items()},
        'fbx_evidence':evidence,'tenancy_evidence':tenancy_evidence,'props':props,'mesh_object_names':meshes,
        'files':{p.relative_to(out).as_posix():c.digest(p) for p in files},
        'limitations':['Props and ground are illustrative; no live-world placements or floor evidence',
          'No Unreal import, collision, navigation, gameplay, streaming or visual approval',
          'Ale-stake is an artistic tavern cue, not a verified historic tenancy',
          'Tenancy overlay and original shell are visual only; the combined OBJ must not be stacked over the FBX'],
    })
    print('Hosted review scene built; independent GLB verification pending.')


def verify():
    import bpy
    root,_=c.hosted_context(); out=root/'ci-north-market-street-review'
    report=json.loads((out/'build.report.json').read_text(encoding='utf-8'))
    if report.get('commit')!=__import__('os').environ['GITHUB_SHA']:
        raise ValueError('build identity mismatch')
    for name,sha in report['files'].items():
        path=(out/name).resolve(strict=True)
        if not path.is_relative_to(out.resolve(strict=True)) or c.digest(path)!=sha:
            raise ValueError('scene file hash mismatch')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.ops.import_scene.gltf(filepath=str(out/'north_market_street_review.glb'))!={'FINISHED'}:
        raise ValueError('review scene GLB reimport failed')
    bpy.context.view_layer.update()
    meshes=[obj for obj in bpy.data.objects if obj.type=='MESH']
    actual={obj.name for obj in meshes}; expected=set(report['mesh_object_names'])
    if actual!=expected: raise ValueError('review scene mesh inventory differs')
    facts=mesh_facts(meshes)
    write_json(out/'manifest.json',{
        'status':'review-only; no Unreal placement or gameplay validation',
        'commit':report['commit'],'build_report_sha256':c.digest(out/'build.report.json'),
        'output_sha256':report['files'],'independent_glb_reimport':facts,
        'limitations':report['limitations'],
    })
    print('Review GLB reimport and output hashes verified.')


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if args==['build']: build()
    elif args==['verify']: verify()
    else: raise SystemExit('Expected build or verify')
