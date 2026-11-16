"""Import the small CC0 Poly Haven plants that the town layout scatters.

Sources: Saved/FableStreets_polyhaven/<name>/<name>_1k.gltf, downloaded
2026-11-15 from polyhaven.com (licence CC0). Each file holds a few variants of
one plant, laid out side by side; each variant becomes its own Nanite mesh with
no collision. New assets go under PLANT_FOLDER only, and
only those are saved. build_medieval_london_map.py picks up every static mesh
it finds there on its next `repack()`.

Run in the editor's async Python tool with this directory on sys.path, the map
open outside Play and the town lease held: `run()`.
"""

from pathlib import Path

from build_medieval_london_map import PLANT_FOLDER, require_town_editor

SOURCE_DIR = 'FableStreets_polyhaven'
PLANTS = ('shrub_03', 'shrub_04', 'weed_plant_02', 'nettle_plant', 'fern_02')


def import_options(unreal):
    pipeline = unreal.InterchangeGenericAssetsPipeline()
    pipeline.get_editor_property('animation_pipeline').set_editor_property('import_animations', False)
    pipeline.get_editor_property('mesh_pipeline').set_editor_properties({
        'import_static_meshes': True, 'import_skeletal_meshes': False,
        'combine_static_meshes_behavior': unreal.InterchangeCombineStaticMeshesBehavior.DO_NOT_COMBINE,
        'collision': False, 'build_nanite': True, 'nanite_triangle_threshold': 0,
        'generate_lightmap_u_vs': False})
    stack = unreal.InterchangePipelineStackOverride()
    stack.add_pipeline(pipeline)
    return stack


def run(names=PLANTS):
    import unreal

    require_town_editor(unreal)
    library = unreal.EditorAssetLibrary
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / SOURCE_DIR
    report = {}
    for name in names:
        folder = f'{PLANT_FOLDER}/{name}'
        existing = library.list_assets(folder, recursive=True, include_folder=False) if library.does_directory_exist(folder) else []
        if not any(isinstance(library.load_asset(path), unreal.StaticMesh) for path in existing):
            source = saved / name / f'{name}_1k.gltf'
            if not source.is_file():
                raise RuntimeError(f'Missing plant source file: {source}')
            task = unreal.AssetImportTask()
            task.set_editor_properties({'filename': str(source), 'destination_path': folder,
                                        'destination_name': f'SM_GL1450_Plant_{name}', 'automated': True,
                                        'save': False, 'replace_existing': False, 'options': import_options(unreal)})
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = library.list_assets(folder, recursive=True, include_folder=False)
        assets = [library.load_asset(path) for path in paths]
        meshes = [asset for asset in assets if isinstance(asset, unreal.StaticMesh)]
        if not meshes:
            raise RuntimeError(f'{name} imported no static mesh; nothing saved for it.')
        packages = [asset.get_package() for asset in assets if asset]
        if any(not package.get_name().startswith(folder + '/') for package in packages):
            raise RuntimeError(f'Unexpected packages for {name}.')
        if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
            raise RuntimeError(f'Could not save the {name} packages.')
        report[name] = []
        for mesh in meshes:
            box = mesh.get_bounding_box()
            report[name].append({
                'mesh': mesh.get_name(), 'triangles': mesh.get_num_triangles(0),
                'nanite': bool(mesh.get_editor_property('nanite_settings').get_editor_property('enabled')),
                'size_cm': [round(box.max.x - box.min.x), round(box.max.y - box.min.y), round(box.max.z - box.min.z)],
                'packages': len(packages)})
    return report
