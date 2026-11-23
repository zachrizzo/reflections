"""Render the matched Unreal surface captures side by side for review."""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_posed_surfaces import classify_body_triangles, mask_image, surface


def render(directory, mask_dir, output):
    capture=directory/'surface'
    labels=json.loads((directory/'clipping.json').read_text())['frames']
    output.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_WORKBENCH'
    scene.render.resolution_x=960
    scene.render.resolution_y=600
    scene.render.image_settings.file_format='PNG'
    studio=scene.display.shading
    studio.light='STUDIO'
    studio.color_type='OBJECT'
    studio.background_type='WORLD'
    scene.world=bpy.data.worlds.new('Dark gray studio')
    scene.world.color=(.052,.061,.074)
    studio.show_cavity=True
    studio.cavity_type='BOTH'
    studio.show_shadows=False
    studio.show_specular_highlight=True
    bpy.ops.object.camera_add(location=(0,-6,1.22))
    scene.camera=bpy.context.object
    scene.camera.rotation_euler=(Vector((0,0,1.22))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.type='ORTHO'
    scene.camera.data.ortho_scale=2.42
    mask=mask_image(mask_dir/'SmoothSource'/'InstalledTorso.tga')
    def text(label,x,z,size):
        curve=bpy.data.curves.new(label,'FONT')
        curve.body=label
        curve.size=size
        curve.align_x='CENTER'
        caption=bpy.data.objects.new(label,curve)
        scene.collection.objects.link(caption)
        caption.location=(x,-.36,z)
        caption.rotation_euler=(math.pi/2,0,0)
        caption.color=(.86,.9,.95,1)
        return curve

    message=text('GILTBARNABY   /   STEP AND TURN',0,1.89,.050)
    modes=(('skinned',-.62,'PHYSICS OFF'),('cloth',.62,'PHYSICS ON'))
    for _,x,name in modes:
        text(name,x,.53,.048)
    text('Matched poses from Unreal Engine',0,.62,.035)
    parts={}
    for mode,x,_ in modes:
        for key,colour in [('body',(.61,.40,.29,1)),('face',(.61,.40,.29,1)),
                           (mode,(.055,.38,.30,1))]:
            points,tri=surface(capture/f'000_{key}.bin')
            if key=='body':
                body_mask=classify_body_triangles(mask_dir/'smoothed_masked',points,tri,mask,
                                                  'T_PanelCoveredTorso')
                tri=tri[body_mask!=0]
            mesh=bpy.data.meshes.new(mode+' '+key)
            mesh.from_pydata(points,[],tri[:,[0,2,1]].tolist())
            mesh.polygons.foreach_set('use_smooth',np.ones(len(mesh.polygons),dtype=bool))
            obj=bpy.data.objects.new(mode+' '+key,mesh)
            scene.collection.objects.link(obj)
            obj.color=colour
            obj.location.x=x
            parts[mode,key]=obj
    rendered=0
    for i,frame in enumerate(labels):
        if i%2 or not frame['matched_pose']:
            continue
        phase=frame['phase'].upper()
        message.body=f'GILTBARNABY   /   {phase}'
        angle=-math.radians(frame['yaw_deg']+12)
        for (mode,key),obj in parts.items():
            xyz,_=surface(capture/f'{i:03d}_{key}.bin')
            xyz*=.01
            xyz[:,1]*=-1
            obj.rotation_euler.z=angle
            obj.data.vertices.foreach_set('co',xyz.ravel())
            obj.data.update()
        scene.render.filepath=str(output/f'{rendered:03d}.png')
        bpy.ops.render.render(write_still=True)
        rendered+=1


if __name__=='__main__':
    render(*map(Path,sys.argv[sys.argv.index('--')+1:]))
