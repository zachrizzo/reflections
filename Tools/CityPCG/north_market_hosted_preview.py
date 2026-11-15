"""Optional CPU-only preview of one verified FBX on the hosted runner."""

import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import north_market_hosted_blender as adapter
import north_market_roundtrip_common as common


def look_at(obj, point):
    from mathutils import Vector
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def run():
    workspace = adapter.hosted_context()
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError('Unexpected Blender release')
    name = common.NAMES[0]
    source = workspace / common.SOURCE_REL
    _, row, obj_path, materials = common.source_spec(source, name)
    expected = common.read_obj(obj_path, materials)
    bundle = workspace / 'ci-north-market-fbx' / name
    fbx = common.within(bundle / (name + '.fbx'), bundle)
    report = json.loads(common.within(bundle / 'verify.report.json', bundle).read_text(encoding='utf-8'))
    if report.get('fbx_sha256') != common.digest(fbx) or report.get('source_manifest_sha256') != common.MANIFEST_SHA:
        raise ValueError('Preview input does not match the verified FBX')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_normals=True,
                                use_image_search=False, use_anim=False) != {'FINISHED'}:
        raise ValueError('Preview import failed')
    obj = adapter.one_mesh(bpy)
    common.compare(expected, adapter.mesh_data(obj))
    adapter.material_textures(bpy, obj, materials, bundle)

    # This is a diagnostic lighting/camera setup, not a recreation of the game.
    coords = [tuple(v.co) for v in obj.data.vertices]
    bounds = [(min(c[i] for c in coords), max(c[i] for c in coords)) for i in range(3)]
    center = [(a + b) / 2 for a, b in bounds]
    size = [b - a for a, b in bounds]
    span = max(size)
    if not (1 < span < 200 and size[2] > 1):
        raise ValueError('Unexpected source bounds')
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 720
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('DiagnosticWorld')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (0.35, 0.39, 0.44, 1)
    background.inputs['Strength'].default_value = 0.8
    light = bpy.data.lights.new('DiagnosticSun', 'SUN')
    light.energy = 2.0
    sun = bpy.data.objects.new('DiagnosticSun', light)
    scene.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(x) for x in (25, -30, -25))
    camera = bpy.data.cameras.new('DiagnosticCamera')
    camera_obj = bpy.data.objects.new('DiagnosticCamera', camera)
    scene.collection.objects.link(camera_obj)
    scene.camera = camera_obj
    temporary = Path(__import__('os').environ['RUNNER_TEMP']).resolve(strict=True)
    out = temporary / 'north-market-textured-preview'
    out.mkdir()

    camera.type = 'PERSP'
    camera.lens = 28
    camera_obj.location = (bounds[0][1] + max(8, size[1] * 0.28), center[1], 1.7)
    look_at(camera_obj, (center[0], center[1], 2.1))
    scene.render.filepath = str(out / 'eye_level.png')
    bpy.ops.render.render(write_still=True)

    camera.type = 'ORTHO'
    camera.ortho_scale = span * 1.65
    camera_obj.location = (center[0] + span, center[1] - span, center[2] + span * 0.65)
    look_at(camera_obj, center)
    scene.render.filepath = str(out / 'three_quarter.png')
    bpy.ops.render.render(write_still=True)
    for file in ('eye_level.png', 'three_quarter.png'):
        common.within(out / file, out)
    adapter.write_report(out / 'preview.report.json', {
        'status': 'diagnostic only: visual/game approval pending', 'model': name,
        'fbx_sha256': report['fbx_sha256'], 'bounds_m': bounds,
        'render': 'Blender Cycles CPU, 8 samples, 720x480; artificial light and background',
        'placement': 'local source only; no Unreal placement or gameplay context',
        'source_world_pivot_m': row['world_pivot_m'], 'source_yaw_deg': row['yaw_deg'],
    })


if __name__ == '__main__':
    run()
