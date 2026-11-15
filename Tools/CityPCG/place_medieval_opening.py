"""Preview or save only the authored medieval east frontage on Gray London."""

import math

from apply_facade_pcg import ACTOR_PACKAGES
from import_medieval_kit import DESTINATION, opening_world

WALL = "OSM Tile_p03_p00"
FIRST_CORNER = (330316.9, 30994.2)
SECOND_CORNER = (330522.2, 32328.3)
WALL_OUT = (-.988362, .152123)
TANGENT = (.152123, .988362)
STYLES = ("Chandler", "Mercer", "Scrivener", "Mercer", "Chandler", "Scrivener")
SOUTH_STYLES = ("Scrivener", "Mercer")
WIDTH = 450
OFFSET = 2.5


def trace(unreal, world, start, end):
    result = unreal.SystemLibrary.line_trace_single(
        world, unreal.Vector(*start), unreal.Vector(*end), unreal.TraceTypeQuery.ECC_VISIBILITY, True, [],
        unreal.DrawDebugTrace.NONE)
    return result.to_tuple() if result else None


def wall_point(section, index, along):
    if section == "South":
        corner, tangent = (330314.434, 30094.2), (.00274, .999996)
        offset = index * WIDTH + along
        return tuple(value + factor * offset for value, factor in zip(corner, tangent))
    corner, tangent = (FIRST_CORNER if index < 3 else SECOND_CORNER), TANGENT
    offset = (index % 3) * WIDTH + along
    return tuple(value + factor * offset for value, factor in zip(corner, tangent))


def plan(unreal, world, section):
    outward = WALL_OUT if section == "East" else (-.999996, .00274)
    styles = STYLES if section == "East" else SOUTH_STYLES
    yaw = math.degrees(math.atan2(outward[1], outward[0]))
    frontages = []
    for index, style in enumerate(styles):
        for along in (6, WIDTH / 2, WIDTH - 6):
            x, y = wall_point(section, index, along)
            for z in (123, 393, 830, 1450):
                start = (x + outward[0] * 55, y + outward[1] * 55, z)
                end = (x - outward[0] * 16, y - outward[1] * 16, z)
                hit = trace(unreal, world, start, end)
                if (not hit or hit[9].get_actor_label() != WALL or
                        math.hypot(hit[4].x - x, hit[4].y - y) > 1.3 or
                        hit[7].x * outward[0] + hit[7].y * outward[1] < .995):
                    raise RuntimeError(f"Opening facade {index + 1} left the surveyed wall at {(x, y, z)}.")
        x, y = wall_point(section, index, WIDTH / 2)
        floor_offset = 106 if section == "East" else 45
        floor_x, floor_y = x + outward[0] * floor_offset, y + outward[1] * floor_offset
        floor_hit = trace(unreal, world, (floor_x, floor_y, 200), (floor_x, floor_y, -40))
        expected_ground = 28 if section == "East" else 10
        if not floor_hit or abs(floor_hit[4].z - expected_ground) > 4:
            raise RuntimeError(f"Opening facade {index + 1} has an unexpected footway height.")
        label = f"MedievalOpening_{section}_{index + 1:02}_{style}"
        mesh_id = f"SM_GLMedieval_{style}"
        location = [x + outward[0] * OFFSET, y + outward[1] * OFFSET, floor_hit[4].z - .35]
        frontages.append({"label": label, "mesh_id": mesh_id, "location_cm": location,
                          "yaw_deg": yaw, "seed": index + (952 if section == "East" else 958), "scale": [1, 1, 1]})
    return frontages


def run(mode="preview", section="East"):
    import unreal

    if mode not in ("preview", "save"):
        raise ValueError("Choose preview or save.")
    if section not in ("East", "South"):
        raise ValueError("Choose East or South.")
    world = opening_world(unreal)
    frontages = plan(unreal, world, section)
    assets = unreal.EditorAssetLibrary
    paths = {row["mesh_id"]: f"{DESTINATION}/{row['mesh_id']}" for row in frontages}
    missing = [path for path in paths.values() if not assets.does_asset_exist(path)]
    if mode == "preview":
        return {"placements": frontages, "wall_probes_passed": len(frontages) * 12, "missing_meshes": missing}
    if missing:
        raise RuntimeError(f"Import the medieval kit first: {missing}")

    actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = {a.get_actor_label() for a in actor_system.get_all_level_actors()}
    existing.update(str(desc.get_editor_property("label"))
                    for desc in unreal.WorldPartitionBlueprintLibrary.get_actor_descs() or [])
    placed_labels = {row["label"] for row in frontages} & existing
    if placed_labels:
        raise RuntimeError(f"Medieval opening actors already exist: {sorted(placed_labels)}")
    meshes = {name: assets.load_asset(path) for name, path in paths.items()}
    if any(not isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values()):
        raise RuntimeError("A planned medieval facade is missing its static mesh.")
    created = []
    try:
        for row in frontages:
            actor = actor_system.spawn_actor_from_class(
                unreal.StaticMeshActor, unreal.Vector(*row["location_cm"]), unreal.Rotator(0, 0, row["yaw_deg"]))
            if not actor:
                raise RuntimeError(f"Could not place {row['label']}.")
            created.append(actor)
            actor.set_actor_label(row["label"])
            actor.set_folder_path(f"MedievalOpening/{section}Frontage")
            actor.set_actor_enable_collision(False)
            mesh_component = actor.static_mesh_component
            mesh_component.set_collision_profile_name("NoCollision")
            mesh_component.set_editor_property("can_ever_affect_navigation", False)
            if not mesh_component.set_static_mesh(meshes[row["mesh_id"]]):
                raise RuntimeError(f"Could not assign {row['mesh_id']}.")
            if str(mesh_component.get_collision_profile_name()) != "NoCollision":
                raise RuntimeError(f"Unexpected collision profile on {row['label']}.")
        opening_world(unreal)
        packages = [actor.get_package() for actor in created]
        names = [package.get_name() for package in packages]
        if len(set(names)) != len(created) or any(not package.startswith(ACTOR_PACKAGES) for package in names):
            raise RuntimeError(f"The facades did not get dedicated external actor packages: {names}")
    except Exception:
        for actor in reversed(created):
            actor_system.destroy_actor(actor)
        raise
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError(f"Could not save the facade actor packages: {names}")
    multi_user = unreal.MultiUserClientStatics
    if multi_user.get_multi_user_connection_status_detail() == unreal.MultiUserConnectionStatus.CONNECTED:
        multi_user.persist_specified_packages(names)
    return {"placements": frontages, "wall_probes_passed": len(frontages) * 12, "saved_packages": names}
