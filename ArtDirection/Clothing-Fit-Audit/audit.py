import bpy, pathlib, json, math, statistics, traceback
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils import Quaternion
ROOT=pathlib.Path(r'C:\Users\zachc\Documents\Unreal Projects\reflections')
BASE=ROOT/'ArtDirection/Three-Londons-Wardrobe'; OUT=ROOT/'ArtDirection/Clothing-Fit-Audit'
FILES={'Coin Clerk':'Merchant/Merchant.blend','Ferry Pilot':'Red London/FerryPilot/FerryPilot_Outfit.blend','Bridge Guard':'Red London/Bridge Guard/BridgeGuard-Outfit.blend','Festival Drummer':'Red London/Festival Drummer/FestivalDrummer-Outfit.blend','Archive Apprentice':'Red London/Archive Apprentice/ArchiveApprentice.blend','Glass Artisan':'Red London/Glass Artisan/GlassArtisan.blend','Iven':'White London - Rags and Tattoos/IvenMetaHuman/IvenRook_MetaHuman_Outfit.blend','Hero':'Hero/Hero_Wardrobe.blend'}
POSES={'rest':{},'reach':{'upperarm_l':(0.0,0.0,-0.45),'upperarm_r':(0.0,0.0,0.45)},'stride':{'thigh_l':(0.35,0.0,0.0),'thigh_r':(-0.35,0.0,0.0),'upperarm_l':(-0.2,0.0,0.0),'upperarm_r':(0.2,0.0,0.0)}}
def category(n):
 s=n.lower().split('_')[-1]
 if any(w in s for w in ['shield','ledger','scales','pouch','glass','glyph','tattoo','beater','drum','handcoil','satchel','belt','hat','armor','sash','harness']): return 'accessory or rigid prop'
 if any(w in s for w in ['boot','sandal']): return 'footwear'
 if any(w in s for w in ['capelet','skirt','tails','apron']): return 'loose or layered clothing'
 return 'fitted clothing or outer layer'
def surface(obj,dg):
 e=obj.evaluated_get(dg); m=e.to_mesh(); m.calc_loop_triangles();
 v=[e.matrix_world @ x.co for x in m.vertices]; f=[tuple(t.vertices) for t in m.loop_triangles]
 tree=BVHTree.FromPolygons(v,f,all_triangles=True); e.to_mesh_clear(); return tree

def attr(obj,color):
 ca=obj.data.color_attributes.get('FitDistance') or obj.data.color_attributes.new(name='FitDistance',type='BYTE_COLOR',domain='POINT')
 obj.data.color_attributes.active_color=ca
 if color:
  for x in ca.data:x.color=color
 return ca

def camera_setup():
 scene=bpy.context.scene
 for o in scene.objects:
  if o.type=='MESH':o.hide_render=False; o.hide_set(False)
 camd=bpy.data.cameras.new('AuditCamera'); cam=bpy.data.objects.new('AuditCamera',camd); scene.collection.objects.link(cam)
 cam.location=(2.7,-5.6,2.0); cam.rotation_euler=(Vector((0,0,0.88))-cam.location).to_track_quat('-Z','Y').to_euler(); camd.type='ORTHO'; camd.ortho_scale=2.35; scene.camera=cam
 scene.render.engine='BLENDER_WORKBENCH'; scene.display.shading.light='STUDIO'; scene.display.shading.color_type='VERTEX'; scene.display.shading.background_type='WORLD'; scene.display.shading.show_shadows=True; scene.display.shading.show_cavity=True
 if scene.world is None:scene.world=bpy.data.worlds.new('AuditWorld')
 scene.world.color=(0.10,0.10,0.10); scene.render.resolution_x=800; scene.render.resolution_y=800; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False

def percentile(x,q):
 x=sorted(x); return round(x[round((len(x)-1)*q)],2) if x else None

def run(name,rel):
 bpy.ops.wm.open_mainfile(filepath=str(BASE/rel)); scene=bpy.context.scene
 meshes=[o for o in scene.objects if o.type=='MESH']
 body=next(o for o in meshes if 'fitting' in o.name.lower() and 'body' in o.name.lower())
 face=next((o for o in meshes if 'fitting' in o.name.lower() and ('face' in o.name.lower() or 'head' in o.name.lower())),None)
 rig=next(o for o in scene.objects if o.type=='ARMATURE')
 clothes=[o for o in meshes if o!=body and o!=face and o.name.startswith('SK_')]
 camera_setup(); attr(body,(0.42,0.42,0.42,1));
 if face:attr(face,(0.42,0.42,0.42,1))
 results={'source':str((BASE/rel).relative_to(ROOT)),'body_vertices':len(body.data.vertices),'head_vertices':len(face.data.vertices) if face else 0,'poses':{}}
 for pose, rotations in POSES.items():
  if pose!='rest' and name!='Coin Clerk': continue
  for b in rig.pose.bones:
   b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion((1,0,0,0));b.location=(0,0,0);b.scale=(1,1,1)
  for bone,angles in rotations.items():
   b=rig.pose.bones.get(bone)
   if b:
    from mathutils import Euler
    b.rotation_quaternion=Euler(angles,'XYZ').to_quaternion()
  bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();trees=[('body',surface(body,dg))]
  if face and pose=='rest':trees.append(('head',surface(face,dg)))
  pr={'surfaces':[t[0] for t in trees],'objects':{}}
  for o in clothes:
   cat=category(o.name);e=o.evaluated_get(dg);m=e.to_mesh(); ca=attr(o,None)
   distances=[]; negative=0; bins={'0-5mm':0,'5-30mm':0,'30-60mm':0,'over-60mm':0,'possible-inside-over-2mm':0}; face_nearest=0
   for i,v in enumerate(m.vertices):
    p=e.matrix_world@v.co; candidates=[]
    for tag,tree in trees:
     hit=tree.find_nearest(p)
     if hit[0] is not None:candidates.append((hit[3],tag,hit))
    if not candidates:continue
    distance,tag,hit=min(candidates,key=lambda a:a[0]); distances.append(distance*1000); face_nearest+=tag=='head'
    signed=(p-hit[0]).dot(hit[1]); inside=signed < -0.002
    if distance < .005: bins['0-5mm']+=1; color=(0.05,0.45,1,1)
    elif distance < .03: bins['5-30mm']+=1;color=(0.10,0.85,0.2,1)
    elif distance < .06: bins['30-60mm']+=1;color=(1.0,0.55,0.02,1)
    else: bins['over-60mm']+=1;color=(0.9,0.03,0.03,1)
    if inside:bins['possible-inside-over-2mm']+=1;color=(1.0,0.0,0.85,1)
    if cat=='accessory or rigid prop':color=(0.16,0.16,0.16,1)
    if i<len(ca.data):ca.data[i].color=color
   e.to_mesh_clear()
   pr['objects'][o.name]={'category':cat,'vertices':len(distances),'median_distance_mm':percentile(distances,.5),'p95_distance_mm':percentile(distances,.95),'max_distance_mm':round(max(distances),2) if distances else None,'nearest_head_vertices':face_nearest,'bins':bins}
  results['poses'][pose]=pr
  scene.render.filepath=str(OUT/(name.replace(' ','_')+'_'+pose+'.png'));bpy.ops.render.render(write_still=True)
 return results
all_results={'method':'Evaluated Blender world-space garment vertices to nearest triangle of body and, in rest pose, separate head/neck proxy. mm; nearest-normal sign is only a screening estimate, not robust inside/outside. Synthetic posed tests use armature transforms; head proxy is static and omitted in poses.','characters':{}}
for name,rel in FILES.items():
 try:all_results['characters'][name]=run(name,rel)
 except Exception as ex:all_results['characters'][name]={'error':str(ex),'trace':traceback.format_exc()}
 with open(OUT/'fit-audit.json','w') as f:json.dump(all_results,f,indent=2)
 print('AUDIT COMPLETE:',name,flush=True)


