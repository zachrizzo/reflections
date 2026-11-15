"""Hosted-only FBX round-trip for the North Market tenancy trial.

The complete mode preserves the whole original OBJ and adds the decorative
tenancies; overlay mode contains only those additions at the same local pivot.
Neither mode modifies or approves the baseline or a live Unreal asset.
"""
import hashlib
import io
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import north_market_hosted_blender as adapter
import north_market_roundtrip_common as common
import north_market_tenancies as tenancy


KINDS = {'complete': ('SM_NorthMarket_0a_TenancyFull', tenancy.MODEL + '_tenancies_review.obj'),
         'overlay': ('SM_NorthMarket_0a_TenancyOverlay', 'tenancies_overlay.obj')}
PREVIEW_RUN = 43731156271
PREVIEW_ARTIFACT = 14167854997
PREVIEWED_OVERLAY_SHA = 'b67371709b3050ba31e2c31ad25488f5bc83cb0ef01bd050d47e62ff87da7eec'
PREVIEWED_COMBINED_SHA = 'f52ba1bccfb11a986b78ced35a9924c437a6ccd350ac51dc90fef666731b2be5'


def check_previewed_hashes(overlay_sha, combined_sha):
    if overlay_sha != PREVIEWED_OVERLAY_SHA or combined_sha != PREVIEWED_COMBINED_SHA:
        raise ValueError('Source differs from the independently previewed trial')


def obj_for_kind(inputs, kind):
    if kind not in KINDS:
        raise ValueError('Unknown tenancy FBX kind')
    return inputs['combined' if kind == 'complete' else 'overlay']


def check_union(base, overlay, combined, material_order):
    """Prove the complete OBJ contains the original and overlay channels."""
    for key in ('vertices', 'edges', 'uv_corners'):
        if combined[key] != base[key] + overlay[key]:
            raise ValueError('Combined OBJ changed source or overlay ' + key)
    if combined['faces'] != base['faces'] + overlay['faces']:
        raise ValueError('Combined OBJ changed positions, winding, UVs, normals or assignments')
    used = set(base['slots']) | set(overlay['slots'])
    if combined['slots'] != [name for name in material_order if name in used]:
        raise ValueError('Combined OBJ material slots differ')


def check_generation_report(report, overlay_sha, combined_sha, mesh, units):
    required = {'status': 'review_only_not_unreal_validated', 'building': tenancy.BUILDING,
                'source_obj_sha256': tenancy.PINNED['obj'],
                'source_plan_lf_sha256': tenancy.PINNED['plan'],
                'overlay_sha256': overlay_sha, 'combined_sha256': combined_sha,
                'added_vertices': len(mesh.vertices), 'added_faces': len(mesh.faces), 'units': units}
    if not isinstance(report, dict) or any(report.get(key) != value for key, value in required.items()):
        raise ValueError('Generated source report does not match the exact inputs')


def expected_overlay_sha(mesh):
    text = io.StringIO()
    text.write('# Closed visual details only; no gameplay openings.\nmtllib NorthMarketDetail.mtl\n')
    tenancy.write_geometry(text, mesh)
    return hashlib.sha256(text.getvalue().encode('utf-8')).hexdigest()


def source_inputs(workspace):
    """Recompute the pinned overlay, prove its merge, and bind the base FBX."""
    source = workspace / common.SOURCE_REL
    manifest, row, original, materials = common.source_spec(source, tenancy.MODEL)
    if tenancy.source_digest('plan', tenancy.PLAN) != tenancy.PINNED['plan']:
        raise ValueError('Surveyed plan changed')
    plan = json.loads(tenancy.PLAN.read_text(encoding='utf-8'))
    buildings = [item for item in plan['buildings'] if item['id'] == tenancy.BUILDING]
    if len(buildings) != 1:
        raise ValueError('Selected building is not unique')
    party = {edge for item in plan.get('party_walls', []) for key, edge in item['edges'].items()
             if key == tenancy.BUILDING}
    mesh, units = tenancy.make_details(buildings[0], party)
    generated = workspace / 'ci-north-market-tenancy'
    if generated.is_symlink() or generated.resolve(strict=True) != generated:
        raise ValueError('Generated review directory is redirected')
    overlay = common.within(generated/'tenancies_overlay.obj', generated)
    combined = common.within(generated/(tenancy.MODEL+'_tenancies_review.obj'), generated)
    report_path = common.within(generated/'tenancies.report.json', generated)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    overlay_sha, combined_sha = common.digest(overlay), common.digest(combined)
    check_previewed_hashes(overlay_sha, combined_sha)
    if overlay_sha != expected_overlay_sha(mesh):
        raise ValueError('Overlay differs from the regenerated surveyed details')
    check_generation_report(report, overlay_sha, combined_sha, mesh, units)
    copied_materials = common.read_mtl(generated, manifest)
    if copied_materials != materials:
        raise ValueError('Generated source materials differ from the original')
    baseline = workspace/'ci-north-market-fbx'/tenancy.MODEL
    base_fbx = common.within(baseline/(tenancy.MODEL+'.fbx'), baseline)
    base_report = json.loads(common.within(baseline/'verify.report.json', baseline).read_text(encoding='utf-8'))
    if (base_report.get('phase') != 'verify' or base_report.get('model') != tenancy.MODEL
            or base_report.get('source_manifest_sha256') != common.MANIFEST_SHA
            or base_report.get('source_obj_sha256') != tenancy.PINNED['obj']
            or base_report.get('fbx_sha256') != common.digest(base_fbx)):
        raise ValueError('Baseline FBX is not the independently verified source')
    base = common.read_obj(original, materials)
    addon = common.read_obj(overlay, materials)
    full = common.read_obj(combined, materials)
    check_union(base, addon, full, materials)
    return {'manifest': manifest, 'row': row, 'materials': materials, 'generated': generated,
            'overlay': overlay, 'combined': combined, 'overlay_sha256': overlay_sha,
            'combined_sha256': combined_sha, 'baseline_fbx_sha256': base_report['fbx_sha256'],
            'expected': {'complete': full, 'overlay': addon}}


def report_matches(previous, current):
    fields = ('kind', 'model', 'source_manifest_sha256', 'source_obj_sha256',
              'source_plan_lf_sha256', 'source_mtl_sha256', 'overlay_obj_sha256',
              'combined_obj_sha256', 'baseline_fbx_sha256', 'fbx_sha256',
              'preview_run', 'preview_artifact',
              'world_pivot_m', 'yaw_deg', 'source_axes', 'scene_unit', 'scene_unit_scale', 'blender_version',
              'uv_layer', 'facts', 'textures', 'normal_repair')
    if not isinstance(previous, dict) or previous.get('phase') != 'export':
        raise ValueError('Missing export report')
    for field in fields:
        if field not in previous or previous[field] != current.get(field):
            raise ValueError('Fresh reimport differs from export: ' + field)


def run():
    workspace = adapter.hosted_context()
    import bpy
    if bpy.app.version != (4, 5, 3):
        raise RuntimeError('Unexpected Blender release')
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if len(args) != 2 or args[0] not in ('export', 'verify') or args[1] not in KINDS:
        raise ValueError('Expected -- export|verify complete|overlay')
    phase, kind = args
    inputs = source_inputs(workspace)
    name, _ = KINDS[kind]
    obj_path = obj_for_kind(inputs, kind)
    expected = inputs['expected'][kind]
    root = workspace/'ci-north-market-tenancy-fbx'
    if not root.exists():
        if phase != 'export' or root.is_symlink():
            raise ValueError('Review root is missing or redirected')
        root.mkdir()
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ValueError('Review root is redirected')
    out = root/kind
    if phase == 'export':
        out.mkdir()  # refuse all existing results
    elif out.is_symlink() or not out.is_dir() or out.resolve() != out:
        raise ValueError('Review bundle is missing or redirected')
    fbx = out/(name+'.fbx')
    previous = None
    if phase == 'verify':
        common.within(fbx, out)
        previous = json.loads(common.within(out/'export.report.json', out).read_text(encoding='utf-8'))
        if previous.get('fbx_sha256') != common.digest(fbx):
            raise ValueError('FBX differs from its export report')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if phase == 'export':
        result = bpy.ops.wm.obj_import(filepath=str(obj_path), forward_axis='Y', up_axis='Z',
                                       global_scale=1.0, use_split_objects=False, use_split_groups=False)
    else:
        result = bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_normals=True,
                                          use_image_search=False, use_anim=False)
    if result != {'FINISHED'}:
        raise ValueError('Blender import failed')
    obj = adapter.one_mesh(bpy)
    if phase == 'export':
        obj.name = name
        obj.data.name = name
        adapter.set_slot_order(obj, expected['slots'])
    elif obj.name != name:
        raise ValueError('Reimported FBX object name differs')
    repair = None
    actual = adapter.mesh_data(obj)
    if phase == 'export':
        try:
            facts = common.compare(expected, actual)
        except ValueError:
            # Repair is allowed only when positions, UVs and materials map
            # unambiguously to finite flat source normals. Full comparison is
            # still mandatory before export and in a fresh FBX process.
            repair = adapter.restore_flat_source_normals(obj, expected, actual, apply=True)
            facts = common.compare(expected, adapter.mesh_data(obj))
    else:
        if previous.get('normal_repair') is not None:
            repair = adapter.restore_flat_source_normals(obj, expected, actual, apply=False)
        facts = common.compare(expected, adapter.mesh_data(obj))
    textures = adapter.material_textures(bpy, obj, inputs['materials'],
                                         inputs['generated'] if phase == 'export' else out)
    if phase == 'export':
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.export_scene.fbx(
            filepath=str(fbx), use_selection=True, object_types={'MESH'}, global_scale=1.0,
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True,
            bake_space_transform=False, axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True,
            mesh_smooth_type='EDGE' if repair else 'FACE', use_triangles=False, bake_anim=False,
            path_mode='COPY', embed_textures=False)
        if result != {'FINISHED'}:
            raise ValueError('FBX export failed')
        common.within(fbx, out)
    # Re-read and recheck original inputs, generated variant, and baseline.
    after = source_inputs(workspace)
    for field in ('overlay_sha256', 'combined_sha256', 'baseline_fbx_sha256'):
        if after[field] != inputs[field]:
            raise ValueError('Source changed during FBX round-trip')
    unit_scale = bpy.context.scene.unit_settings.scale_length
    if not math.isfinite(unit_scale) or abs(unit_scale-1.0) > 1e-8:
        raise ValueError('Unexpected scene unit scale')
    report = {'status': 'review_only_no_unreal_approval', 'phase': phase, 'kind': kind, 'model': name,
              'source_manifest_sha256': common.MANIFEST_SHA, 'source_obj_sha256': tenancy.PINNED['obj'],
              'source_plan_lf_sha256': tenancy.PINNED['plan'], 'source_mtl_sha256': tenancy.PINNED['mtl'],
              'overlay_obj_sha256': inputs['overlay_sha256'], 'combined_obj_sha256': inputs['combined_sha256'],
              'baseline_fbx_sha256': inputs['baseline_fbx_sha256'], 'fbx_sha256': common.digest(fbx),
              'preview_run': PREVIEW_RUN, 'preview_artifact': PREVIEW_ARTIFACT,
              'world_pivot_m': inputs['row']['world_pivot_m'], 'yaw_deg': inputs['row']['yaw_deg'],
              'source_axes': '+X entrance, +Z up', 'scene_unit': 'metres', 'scene_unit_scale': unit_scale,
              'blender_version': bpy.app.version_string, 'uv_layer': obj.data.uv_layers.active.name,
              'facts': facts, 'textures': textures, 'normal_repair': repair,
              'limits': ['Closed decorative doors and hatches; no gameplay openings.',
                         'No Unreal import, collision, navigation, placement or gameplay validation.',
                         'Blender round-trip alone cannot prove Unreal scale, orientation, tangents or appearance.']}
    if phase == 'verify':
        report_matches(previous, report)
    adapter.write_report(out/(phase+'.report.json'), report)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    run()
