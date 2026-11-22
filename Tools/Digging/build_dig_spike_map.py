"""Builds /Game/Maps/DigSpike/L_DigSpike from nothing: a plain one-file level (no World Partition, no external actors).

Run only through .superpowers/bin/editor-python.ps1 -Script <this file>. Every run makes a new blank level and
overwrites the map file. Prints DIG SPIKE MAP SAVED only after the save succeeded; any failure raises.
"""

import os

import unreal

MAP_PACKAGE = "/Game/Maps/DigSpike/L_DigSpike"
STAGE_MESH_PATHS = (
    "/Engine/BasicShapes/Cube.Cube",
    "/Engine/BasicShapes/Cone.Cone",
    "/Engine/BasicShapes/Cylinder.Cylinder",
)
# Movable point lights over the patch's middle, 250 cm above the ground.
CAVE_LIGHT_LOCATIONS = (
    (2800.0, -600.0, 250.0),
    (2800.0, 600.0, 250.0),
    (4000.0, -600.0, 250.0),
    (4000.0, 600.0, 250.0),
)
CAVE_LIGHT_INTENSITY = 5000.0
CAVE_LIGHT_ATTENUATION_RADIUS = 1500.0


def fail(message):
    raise RuntimeError("build_dig_spike_map: " + message)


def load_mesh(path):
    mesh = unreal.load_asset(path)
    if not isinstance(mesh, unreal.StaticMesh):
        fail("could not load static mesh " + path)
    return mesh


def spawn(actor_class, label, location=(0.0, 0.0, 0.0), rotation=None, scale=(1.0, 1.0, 1.0)):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    location = unreal.Vector(*location)
    rotation = rotation if rotation is not None else unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    actor = actors.spawn_actor_from_class(actor_class, location, rotation)
    if actor is None:
        fail("could not spawn " + label)
    actor.set_actor_label(label)
    # Set the transform again after spawning so no spawn adjustment changes it.
    actor.set_actor_location_and_rotation(location, rotation, False, True)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    if actor.get_actor_label() != label:
        fail("label of " + label + " is " + actor.get_actor_label())
    return actor


def make_movable(component, label):
    if component is None:
        fail(label + " has no component to make movable")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)


def spawn_dig_spot(label, spot_id, location, meshes):
    spot = spawn(unreal.ReflectionsDigSpot, label, location)
    spot.set_editor_property("spot_id", spot_id)
    spot.set_editor_property("stage_meshes", meshes)
    if str(spot.get_editor_property("spot_id")) != spot_id:
        fail(label + " spot_id did not stick")
    stored = spot.get_editor_property("stage_meshes")
    if len(stored) != len(meshes) or any(m is None for m in stored):
        fail(label + " stage_meshes did not stick")
    return spot


def spawn_cave_light(label, location):
    light = spawn(unreal.PointLight, label, location)
    component = light.get_component_by_class(unreal.PointLightComponent)
    make_movable(component, label)
    component.set_editor_property("intensity_units", unreal.LightUnits.UNITLESS)
    component.set_editor_property("intensity", CAVE_LIGHT_INTENSITY)
    component.set_editor_property("attenuation_radius", CAVE_LIGHT_ATTENUATION_RADIUS)
    return light


def build():
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    if world is None:
        fail("new_blank_map returned no world")

    # The cube is also the stage-0 mesh, so it is loaded once with the others.
    stage_meshes = [load_mesh(path) for path in STAGE_MESH_PATHS]
    cube = stage_meshes[0]

    # The cube ground ends at X = 1000, flush against the dig terrain's patch.
    ground = spawn(unreal.StaticMeshActor, "DigSpike_Ground", (-2000.0, 0.0, -50.0), scale=(60.0, 100.0, 1.0))
    if not ground.static_mesh_component.set_static_mesh(cube):
        fail("could not set the ground mesh")

    # The patch covers X 1000 to 5800 and Y -2400 to 2400, its ground at Z 0 (default size: 3 x 3 x 2 chunks).
    terrain = spawn(unreal.ReflectionsDigTerrain, "DigSpike_Terrain", (1000.0, -2400.0, 0.0))
    terrain.set_editor_property("ground_height_cm", 0.0)

    sun = spawn(unreal.DirectionalLight, "DigSpike_Sun", rotation=unreal.Rotator(roll=0.0, pitch=-45.0, yaw=30.0))
    make_movable(sun.root_component, "DigSpike_Sun")

    spawn(unreal.SkyAtmosphere, "DigSpike_Sky")

    sky_light = spawn(unreal.SkyLight, "DigSpike_SkyLight")
    sky_light_component = sky_light.get_component_by_class(unreal.SkyLightComponent)
    make_movable(sky_light_component, "DigSpike_SkyLight")
    sky_light_component.set_editor_property("real_time_capture", True)

    for index, location in enumerate(CAVE_LIGHT_LOCATIONS):
        spawn_cave_light("DigSpike_CaveLight" + str(index + 1), location)

    # Yaw 0 faces +X, towards the patch.
    spawn(unreal.PlayerStart, "DigSpike_Start", (400.0, 0.0, 100.0))

    spawn_dig_spot("DigSpike_SpotA", "DigSpike_A", (0.0, -300.0, 50.0), stage_meshes)
    spawn_dig_spot("DigSpike_SpotB", "DigSpike_B", (0.0, 300.0, 50.0), stage_meshes)

    map_file = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                                             "Maps", "DigSpike", "L_DigSpike.umap"))
    os.makedirs(os.path.dirname(map_file), exist_ok=True)
    # On a re-run the file already exists, so only a newer modification time proves this save wrote it.
    old_mtime = os.path.getmtime(map_file) if os.path.isfile(map_file) else None
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PACKAGE):
        fail("save_map reported failure for " + MAP_PACKAGE)
    if not os.path.isfile(map_file):
        fail("save_map succeeded but " + map_file + " is missing")
    if old_mtime is not None and os.path.getmtime(map_file) <= old_mtime:
        fail("save_map succeeded but " + map_file + " was not rewritten")
    print("saved " + map_file)


build()
print("DIG SPIKE MAP SAVED")
