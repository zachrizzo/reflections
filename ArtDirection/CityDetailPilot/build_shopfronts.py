"""Build original, modular street-level fronts for the Gray London pilot.

Blender metres, Z up, front +X; 4 m bay, bottom-centre pivot.  These are
shallow decorative overlays: keep collision on the original city shell.
"""
import bpy
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'Source'
OUT.mkdir(parents=True, exist_ok=True)

PALETTE = {
    'stone': (0.33, 0.31, 0.27, 1),
    'stone_light': (0.53, 0.51, 0.45, 1),
    'trim_green': (0.08, 0.14, 0.13, 1),
    'trim_blue': (0.09, 0.13, 0.18, 1),
    'trim_brown': (0.16, 0.10, 0.07, 1),
    'glass': (0.09, 0.16, 0.18, 1),
    'door_glass': (0.14, 0.20, 0.20, 1),
    'brass': (0.46, 0.31, 0.12, 1),
    'canvas_red': (0.32, 0.12, 0.10, 1),
    'canvas_cream': (0.60, 0.56, 0.44, 1),
}

def mat(name):
    m = bpy.data.materials.get('GL_' + name)
    if m:
        return m
    m = bpy.data.materials.new('GL_' + name)
    m.diffuse_color = PALETTE[name]
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = PALETTE[name]
    bsdf.inputs['Roughness'].default_value = .3 if 'glass' in name else .72
    bsdf.inputs['Metallic'].default_value = .65 if name == 'brass' else 0
    return m

def cube(name, pos, size, material, bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat(material))
    if bevel:
        mod = ob.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return ob

def frame(y, z, width, height, trim, x=.18, thickness=.075):
    d = .10
    for yy in (y-width/2+thickness/2, y+width/2-thickness/2):
        cube('frame_stile', (x, yy, z), (d, thickness, height), trim, .008)
    for zz in (z-height/2+thickness/2, z+height/2-thickness/2):
        cube('frame_rail', (x, y, zz), (d, width, thickness), trim, .008)

def front(kind):
    trim = {'bookshop':'trim_green','provisions':'trim_blue','townhouse':'trim_brown'}[kind]
    # A thin backing covers the flat geodata texture; the wall remains intact.
    cube('backing', (.045,0,1.60), (.09,4.0,3.20), 'stone', .005)
    cube('base_course', (.15,0,.17), (.25,4,.34), 'stone_light')
    for yy in (-1.87,1.87):
        cube('pilaster', (.17,yy,1.62), (.28,.25,3.02), 'stone_light')
        for zz in (.43, 2.87):
            cube('pilaster_cap', (.23,yy,zz), (.38,.33,.12), 'stone_light')
    cube('fascia', (.19,0,2.72), (.28,3.5,.43), trim)
    cube('fascia_inner', (.345,0,2.72), (.045,3.18,.29), 'trim_brown', .005)
    for z in (2.49,2.98,3.10):
        cube('cornice', (.27,0,z), (.36,3.85,.07), 'stone_light', .012)
    if kind == 'townhouse':
        door_y=-.98; win_y=.66; win_w=1.65
    else:
        door_y=1.13; win_y=-.59; win_w=2.14
    cube('door_panel', (.12,door_y,1.20), (.10,.88,2.18), trim, .01)
    frame(door_y,1.20,.99,2.25,'stone_light', .20, .09)
    cube('door_glass', (.19,door_y,1.56), (.05,.60,.91), 'door_glass', .008)
    frame(door_y,1.56,.66,.98,trim,.23,.055)
    for zz in (.38,.74):
        cube('door_recessed_panel', (.20,door_y,zz), (.04,.61,.25), 'trim_brown', .007)
    cube('brass_handle', (.26,door_y-.30,1.07), (.10,.055,.10), 'brass', .018)
    cube('window_glass', (.115,win_y,1.45), (.09,win_w,1.92), 'glass', .005)
    frame(win_y,1.45,win_w,1.92,trim,.19,.10)
    for frac in (-.25,.25):
        cube('window_mullion', (.235,win_y+win_w*frac,1.45), (.09,.055,1.78), trim, .006)
    cube('window_transom', (.24,win_y,1.96), (.10,win_w-.12,.065), trim, .006)
    cube('window_sill', (.25,win_y,.47), (.38,win_w+.16,.14), 'stone_light')
    if kind != 'townhouse':
        # Individual striped slats give the shallow awning a readable silhouette.
        for i in range(12):
            yy=-1.66+(i+.5)*3.32/12
            ob=cube('awning_stripe', (.51,yy,2.45), (.73,3.32/12+.002,.045),
                    'canvas_red' if i%2 == 0 else 'canvas_cream', .003)
            ob.rotation_euler[1]=math.radians(-16)
        for yy in (-1.50,1.50):
            cube('awning_bracket', (.37,yy,2.32), (.62,.045,.045), 'brass', .004)
    parts=list(bpy.context.selected_objects)
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name='SM_GL_Shopfront_' + kind.title()
    bpy.context.scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return obj

for kind in ('bookshop','provisions','townhouse'):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    ob=front(kind)
    bpy.ops.export_scene.fbx(filepath=str(OUT / (ob.name+'.fbx')), use_selection=True,
        object_types={'MESH'}, axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
        bake_anim=False, path_mode='AUTO')
    print('BUILT', ob.name, 'polygons', len(ob.data.polygons), 'UV layers', len(ob.data.uv_layers))
