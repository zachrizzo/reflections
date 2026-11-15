"""Render a compact preview of the exported modules in an isolated Blender."""
import bpy
import math
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for i, kind in enumerate(('Bookshop', 'Provisions', 'Townhouse')):
    bpy.ops.import_scene.fbx(filepath=str(root/'Source'/('SM_GL_Shopfront_'+kind+'.fbx')))
    ob = bpy.context.selected_objects[0]
    ob.location.y = (i-1)*4.25

bpy.ops.mesh.primitive_plane_add(size=200)
floor=bpy.context.object
floor.name='Preview floor'
mat=bpy.data.materials.new('Preview floor')
mat.diffuse_color=(.16,.16,.15,1)
floor.data.materials.append(mat)

bpy.ops.object.light_add(type='AREA', location=(5,-4,10))
light=bpy.context.object
light.data.energy=2500
light.data.shape='DISK'
light.data.size=9
bpy.ops.object.light_add(type='AREA', location=(3,7,7))
bpy.context.object.data.energy=1400
bpy.context.object.data.size=8

bpy.ops.object.camera_add(location=(14,-9,6))
camera=bpy.context.object
camera.rotation_euler=(Vector((0,0,1.45))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=15.0
scene=bpy.context.scene
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.render.resolution_x=1500
scene.render.resolution_y=700
scene.render.resolution_percentage=100
scene.world.color=(.18,.18,.18)
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(root/'shopfront_preview.png')
bpy.ops.render.render(write_still=True)
