from pathlib import Path
import unreal


PROJECT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections")
SOURCE = PROJECT / "ArtDirection" / "CodexRequests" / "Clothing2026_11_14" / "Giltside" / "Props"
STATUS = PROJECT / "ArtDirection" / "CodexRequests" / "clothing_status.md"
DESTINATION = "/Game/LanthorneAssets/Giltside/Props"


def import_one(fbx):
    task = unreal.AssetImportTask()
    task.filename = str(fbx)
    task.destination_path = DESTINATION
    task.automated = True
    task.replace_existing = True
    task.save = True
    ui = unreal.FbxImportUI()
    ui.import_mesh = True
    ui.import_as_skeletal = False
    ui.import_materials = True
    ui.import_textures = True
    ui.static_mesh_import_data.combine_meshes = True
    ui.static_mesh_import_data.auto_generate_collision = True
    ui.static_mesh_import_data.generate_lightmap_u_vs = True
    task.options = ui
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    path = f"{DESTINATION}/{fbx.stem}.{fbx.stem}"
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError(f"Missing expected import {path}")
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return path


def main():
    paths = [import_one(fbx) for fbx in sorted(SOURCE.glob("SM_Giltside_MedievalShield*.fbx"))]
    old = STATUS.read_text(encoding="utf-8") if STATUS.exists() else ""
    with STATUS.open("a", encoding="utf-8") as out:
        for path in paths:
            if path not in old:
                out.write(f"- `{path}` — Imported static-mesh shield; Local Hunyuan3D-2 + Blender export; simple collision generated.\n")
    unreal.log(f"Imported {len(paths)} Giltside medieval shields.")


if __name__ == "__main__":
    main()
