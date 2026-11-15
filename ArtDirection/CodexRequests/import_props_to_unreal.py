import json
from pathlib import Path

import unreal


ROOT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\CodexRequests\Props2026_11_14\Source")
ASSETS = {
    "Quest": [
        "NellsLetter",
        "TramTicket",
        "JorysFiddle",
        "GlaziersEyeglass",
        "LampOilBarrel",
        "BoltOfWool",
        "BarnabysShears",
    ],
    "Pickups": [
        "PewtersideCoin",
        "GiltsideCoin",
        "FrostsideCoin",
        "MirrorShard",
        "MirrorPage",
        "GiltTowerKey",
    ],
}


def make_import_task(group, asset):
    task = unreal.AssetImportTask()
    task.set_editor_property("automated", True)
    task.set_editor_property("async_", False)
    task.set_editor_property("filename", str(ROOT / group / f"SM_{asset}.fbx"))
    task.set_editor_property("destination_path", f"/Game/LanthorneAssets/{group}")
    task.set_editor_property("destination_name", f"SM_{asset}")
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", False)
    task.set_editor_property("save", True)

    options = unreal.FbxImportUI()
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_rigid_mesh", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    task.set_editor_property("options", options)
    return task


tasks = []
for group, names in ASSETS.items():
    for asset in names:
        tasks.append(make_import_task(group, asset))

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
asset_tools.import_asset_tasks(tasks)

expected = [f"/Game/LanthorneAssets/{group}/SM_{asset}.SM_{asset}" for group, names in ASSETS.items() for asset in names]
existing = [path for path in expected if unreal.EditorAssetLibrary.does_asset_exist(path)]
for path in existing:
    unreal.EditorAssetLibrary.save_loaded_asset(unreal.EditorAssetLibrary.load_asset(path))
json.dumps({"expected": expected, "imported": existing, "missing": [path for path in expected if path not in existing]})
