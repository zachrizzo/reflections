import json
import unreal


ASSETS = {
    "Quest": ["NellsLetter", "TramTicket", "JorysFiddle", "GlaziersEyeglass", "LampOilBarrel", "BoltOfWool", "BarnabysShears"],
    "Pickups": ["PewtersideCoin", "GiltsideCoin", "FrostsideCoin", "MirrorShard", "MirrorPage", "GiltTowerKey"],
}


report = {}
for group, names in ASSETS.items():
    for asset in names:
        path = f"/Game/LanthorneAssets/{group}/SM_{asset}.SM_{asset}"
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        body = mesh.get_editor_property("body_setup")
        aggregate = body.get_editor_property("agg_geom")
        collision = {
            "boxes": len(aggregate.get_editor_property("box_elems")),
            "spheres": len(aggregate.get_editor_property("sphere_elems")),
            "capsules": len(aggregate.get_editor_property("sphyl_elems")),
            "convexes": len(aggregate.get_editor_property("convex_elems")),
        }
        report[path] = {
            "materials": [slot.material_interface.get_path_name() if slot.material_interface else None for slot in mesh.get_static_materials()],
            "collision": collision,
        }

print(json.dumps(report, indent=2))
