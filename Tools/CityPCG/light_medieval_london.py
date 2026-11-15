"""Set soft daylight and street haze in the owned Medieval London map."""

from build_medieval_london_map import require_town_editor


def run():
    import unreal

    _, world = require_town_editor(unreal)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    def find_or_add(cls, label):
        existing = [actor for actor in actors.get_all_level_actors() if actor.get_actor_label() == label]
        if existing:
            return existing[0]
        actor = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, 0))
        if not actor:
            raise RuntimeError(f'Could not add {label}')
        actor.set_actor_label(label)
        return actor

    sun, = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.DirectionalLight)
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_properties({
        'intensity': 2.8, 'light_source_angle': 1.8, 'use_temperature': True, 'temperature': 5600.0,
    })
    atmosphere, = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkyAtmosphere)
    atmosphere.get_component_by_class(unreal.SkyAtmosphereComponent).set_editor_property('mie_scattering_scale', .018)
    sky, = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkyLight)
    sky.get_component_by_class(unreal.SkyLightComponent).set_intensity(1.08)

    fog = find_or_add(unreal.ExponentialHeightFog, 'London | Low street haze')
    fog.get_component_by_class(unreal.ExponentialHeightFogComponent).set_editor_properties({
        'fog_density': .021, 'fog_height_falloff': .30, 'fog_max_opacity': .52, 'start_distance': 750.0,
    })
    grade = find_or_add(unreal.PostProcessVolume, 'London | Soft daylight grade')
    grade.set_editor_property('unbound', True)
    settings = grade.get_editor_property('settings')
    settings.set_editor_properties({'override_color_saturation': True,
                                    'color_saturation': unreal.Vector4(.88, .89, .93, 1),
                                    'override_auto_exposure_bias': True, 'auto_exposure_bias': -.15})
    grade.set_editor_property('settings', settings)

    lantern_mesh = unreal.EditorAssetLibrary.load_asset('/Game/LanthorneAssets/Giltside/City/SM_Giltside_LanternPost')
    if not isinstance(lantern_mesh, unreal.StaticMesh):
        raise RuntimeError('Could not find the existing Giltside lantern post.')
    corners = [(-23050, -425), (-23050, 425), (-18300, -530), (-18300, 530),
               (-10900, -500), (-10900, 500), (-3100, -3270), (-3100, 3270),
               (3100, -3270), (3100, 3270)]
    for index, (x, y) in enumerate(corners, 1):
        lantern = find_or_add(unreal.StaticMeshActor, f'London | Lantern {index:02d}')
        post = lantern.get_component_by_class(unreal.StaticMeshComponent)
        post.set_static_mesh(lantern_mesh)
        post.set_collision_profile_name('NoCollision')
        lantern.set_actor_location(unreal.Vector(x, y, 1), False, True)
        glow = find_or_add(unreal.PointLight, f'London | Lantern glow {index:02d}')
        lamp = glow.get_component_by_class(unreal.PointLightComponent)
        lamp.set_mobility(unreal.ComponentMobility.MOVABLE)
        lamp.set_editor_properties({'intensity': 180.0, 'attenuation_radius': 470.0,
                                    'use_temperature': True, 'temperature': 2250.0, 'cast_shadows': False})
        glow.set_actor_location(unreal.Vector(x, y, 265), False, True)
    if not unreal.EditorLoadingAndSavingUtils.save_packages([world.get_package()], only_dirty=False):
        raise RuntimeError('Could not save Medieval London lighting.')
    return {'package': world.get_package().get_name(), 'lighting': 'soft daylight and low street haze'}
