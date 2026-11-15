import os
from pathlib import Path
import unreal


PROJECT = Path(r"C:\Users\zachc\Documents\Unreal Projects\reflections")
SOURCE = PROJECT / "ArtDirection" / "CodexRequests" / "City2026_11_14" / "Source"
STATUS = PROJECT / "ArtDirection" / "CodexRequests" / "status.md"


def import_fbx(fbx, side):
    destination = f"/Game/LanthorneAssets/{side}/City"
    task = unreal.AssetImportTask()
    task.filename = str(fbx)
    task.destination_path = destination
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
    ui.static_mesh_import_data.import_translation = unreal.Vector(0, 0, 0)
    ui.static_mesh_import_data.import_rotation = unreal.Rotator(0, 0, 0)
    ui.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = ui
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    expected = f"{destination}/{fbx.stem}.{fbx.stem}"
    if unreal.EditorAssetLibrary.does_asset_exist(expected):
        unreal.EditorAssetLibrary.save_asset(expected, only_if_is_dirty=False)
        return expected
    return None


def append_status(paths):
    existing = STATUS.read_text(encoding="utf-8") if STATUS.exists() else ""
    rows = []
    for path in paths:
        if path in existing:
            continue
        tool = ("Local Hunyuan3D-2 facade reference + Blender modular reconstruction"
                if "Facade" in path else "Local Hunyuan3D-2 + Blender export")
        rows.append(f"- `{path}` — {tool}")
    if rows:
        prefix = "\n\n## Mock city kit — 2026-11-14\n" if "## Mock city kit — 2026-11-14" not in existing else ""
        with STATUS.open("a", encoding="utf-8") as handle:
            handle.write(prefix + "\n".join(rows) + "\n")


def main():
    landed = []
    for side in ("Pewterside", "Giltside", "Frostside"):
        city_dir = SOURCE / side / "City"
        for fbx in sorted(city_dir.glob("SM_*.fbx")):
            path = import_fbx(fbx, side)
            if not path:
                raise RuntimeError(f"Import did not create expected asset for {fbx}")
            landed.append(path)
            unreal.log(f"Imported {path}")
    append_status(landed)
    unreal.log(f"Completed {len(landed)} city static-mesh imports.")


if __name__ == "__main__":
    main()
