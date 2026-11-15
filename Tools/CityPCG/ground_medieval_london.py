"""Give the Medieval London ground real cobbled streets and grass yards.

The 500 m ground block used one cobble image stretched across its whole face,
which reads as giant blobs. This imports two CC0 Poly Haven cobblestone sets
and a street mask painted from the town layout, builds one world-aligned
material (cobbles where the mask says street, the project's Poly Haven grass
everywhere else, both tiled at real size) and puts it on the ground block.

Sources: Saved/FableStreets_polyhaven (downloaded 2026-11-15 from
polyhaven.com, licence CC0) and T_GL1450_TownStreetMask.png written by
Saved/FableStreets_tools/make_mask.py; rerun that after changing the layout.

Run in the editor's async Python tool with this directory on sys.path, the map
open outside Play and the town lease held: `run()`. It saves only its own new
packages under FOLDER; save the map with build_medieval_london_map.save_town().
"""

from pathlib import Path

from build_medieval_london_map import ROOT, require_town_editor

FOLDER = f'{ROOT}/Ground/TownGround'
NAME = 'M_GL1450_TownGround'
GRASS = '/Game/GrayLondon/Geodata/Textures/leafy_grass_'
GROUND_LABEL = 'Ground | City footprint 500 m'
SOURCE_DIR = 'FableStreets_polyhaven'
# asset name: (source file below Saved/SOURCE_DIR, kind)
SOURCES = {
    'T_GL1450_Cobble_Color': ('cobblestone_floor_04/cobblestone_floor_04_diff_2k.jpg', 'color'),
    'T_GL1450_Cobble_Normal': ('cobblestone_floor_04/cobblestone_floor_04_nor_dx_2k.jpg', 'normal'),
    'T_GL1450_Cobble_Rough': ('cobblestone_floor_04/cobblestone_floor_04_rough_2k.jpg', 'linear'),
    'T_GL1450_MossCobble_Color': ('mossy_cobblestone/mossy_cobblestone_diff_2k.jpg', 'color'),
    'T_GL1450_MossCobble_Normal': ('mossy_cobblestone/mossy_cobblestone_nor_dx_2k.jpg', 'normal'),
    'T_GL1450_MossCobble_Rough': ('mossy_cobblestone/mossy_cobblestone_rough_2k.jpg', 'linear'),
    'T_GL1450_TownStreetMask': ('T_GL1450_TownStreetMask.png', 'mask'),
}
TOWN_SIZE_CM = 50000.0   # the mask covers the whole ground block, centred on the origin
COBBLE_TILE_CM = 290.0   # one repeat of a cobble texture (about 14 setts across)
GRASS_TILE_CM = 380.0
PATCH_CM = 4300.0        # size of the slow patches that vary brightness and moss
COBBLE_BRIGHTNESS = 1.6  # the scanned setts are darker than the plaster and timber above them
COBBLE_ROUGHNESS_LIFT = .12


def import_textures(unreal):
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / SOURCE_DIR
    library = unreal.EditorAssetLibrary
    textures = {}
    for name, (relative, kind) in SOURCES.items():
        path = f'{FOLDER}/{name}'
        if not library.does_asset_exist(path):
            source = saved / relative
            if not source.is_file():
                raise RuntimeError(f'Missing ground source file: {source}')
            task = unreal.AssetImportTask()
            task.set_editor_properties({'filename': str(source), 'destination_path': FOLDER,
                                        'destination_name': name, 'automated': True,
                                        'save': False, 'replace_existing': False})
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = library.load_asset(path)
        if not isinstance(texture, unreal.Texture2D):
            raise RuntimeError(f'Could not import {name}.')
        if kind == 'normal':
            texture.set_editor_properties({'compression_settings': unreal.TextureCompressionSettings.TC_NORMALMAP,
                                           'srgb': False})
        elif kind == 'linear':
            texture.set_editor_property('srgb', False)
        elif kind == 'mask':
            texture.set_editor_properties({'compression_settings': unreal.TextureCompressionSettings.TC_GRAYSCALE,
                                           'srgb': False})
        textures[name] = texture
    for key, suffix in (('grass_color', 'Diffuse'), ('grass_normal', 'nor_dx'), ('grass_rough', 'Rough')):
        textures[key] = library.load_asset(GRASS + suffix)
        if not isinstance(textures[key], unreal.Texture2D):
            raise RuntimeError('The project grass textures are missing.')
    return textures


def build_material(unreal, textures, material=None):
    """Create the ground material, or rebuild the node graph of an existing one."""
    edit = unreal.MaterialEditingLibrary
    sampler = unreal.MaterialSamplerType
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            NAME, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    else:
        material.modify()
        edit.delete_all_material_expressions(material)
    if not material:
        raise RuntimeError('Could not create the town ground material.')
    row = [0]

    def node(cls, column, **properties):
        expression = edit.create_material_expression(material, cls, -1500 + column * 230, row[0])
        row[0] += 110
        for name, value in properties.items():
            expression.set_editor_property(name, value)
        return expression

    def link(source, target, pin):
        if not edit.connect_material_expressions(source, '', target, pin):
            raise RuntimeError(f'Could not connect the ground material input {pin!r}.')

    def math(cls, a, b=None, column=4, **properties):
        expression = node(cls, column, **properties)
        link(a, expression, 'A')
        if b is not None:
            link(b, expression, 'B')
        return expression

    position = node(unreal.MaterialExpressionWorldPosition, 0)
    flat = node(unreal.MaterialExpressionComponentMask, 1, r=True, g=True, b=False, a=False)
    link(position, flat, '')

    def sample(key, tile, kind):
        uv = math(unreal.MaterialExpressionDivide, flat, column=2, const_b=tile)
        texture = node(unreal.MaterialExpressionTextureSample, 3, texture=textures[key], sampler_type=kind)
        link(uv, texture, 'UVs')
        return texture

    def blend(a, b, alpha, column=5):
        expression = node(unreal.MaterialExpressionLinearInterpolate, column)
        link(a, expression, 'A')
        link(b, expression, 'B')
        link(alpha, expression, 'Alpha')
        return expression

    # Slow patches, taken from a huge copy of the grass image's green channel.
    patch_rgb = sample('grass_color', PATCH_CM, sampler.SAMPLERTYPE_COLOR)
    patch = node(unreal.MaterialExpressionComponentMask, 4, r=False, g=True, b=False, a=False)
    link(patch_rgb, patch, '')
    moss_bias = math(unreal.MaterialExpressionSubtract, patch, const_b=.2)
    moss_gain = math(unreal.MaterialExpressionMultiply, moss_bias, const_b=4.0)
    moss = node(unreal.MaterialExpressionSaturate, 4)
    link(moss_gain, moss, '')
    shade_gain = math(unreal.MaterialExpressionMultiply, patch, const_b=1.1)
    shade = math(unreal.MaterialExpressionAdd, shade_gain, const_b=.68)

    # The street mask: shift world XY so the block's corner is UV 0,0.
    mask_shift = math(unreal.MaterialExpressionAdd, flat, column=2, const_b=TOWN_SIZE_CM * .5)
    mask_uv = math(unreal.MaterialExpressionDivide, mask_shift, column=2, const_b=TOWN_SIZE_CM)
    mask_texture = node(unreal.MaterialExpressionTextureSample, 3, texture=textures['T_GL1450_TownStreetMask'],
                        sampler_type=sampler.SAMPLERTYPE_LINEAR_GRAYSCALE)
    link(mask_uv, mask_texture, 'UVs')
    # Break the painted edge up with the patches so grass creeps onto the setts.
    edge_noise = math(unreal.MaterialExpressionSubtract, patch, const_b=.35)
    edge_noise = math(unreal.MaterialExpressionMultiply, edge_noise, const_b=.5)
    street = math(unreal.MaterialExpressionAdd, mask_texture, edge_noise)
    street = math(unreal.MaterialExpressionSubtract, street, const_b=.5)
    street = math(unreal.MaterialExpressionMultiply, street, const_b=5.0)
    street = math(unreal.MaterialExpressionAdd, street, const_b=.5)
    street_alpha = node(unreal.MaterialExpressionSaturate, 4)
    link(street, street_alpha, '')

    outputs = {}
    for channel, kind, target in (('Color', sampler.SAMPLERTYPE_COLOR, unreal.MaterialProperty.MP_BASE_COLOR),
                                  ('Normal', sampler.SAMPLERTYPE_NORMAL, unreal.MaterialProperty.MP_NORMAL),
                                  ('Rough', sampler.SAMPLERTYPE_LINEAR_COLOR, unreal.MaterialProperty.MP_ROUGHNESS)):
        clean = sample(f'T_GL1450_Cobble_{channel}', COBBLE_TILE_CM, kind)
        mossy = sample(f'T_GL1450_MossCobble_{channel}', COBBLE_TILE_CM * 1.13, kind)
        grass = sample('grass_' + channel.lower(), GRASS_TILE_CM, kind)
        cobbles = blend(clean, mossy, moss)
        if channel == 'Color':
            cobbles = math(unreal.MaterialExpressionMultiply, cobbles, column=5, const_b=COBBLE_BRIGHTNESS)
        elif channel == 'Rough':
            cobbles = math(unreal.MaterialExpressionAdd, cobbles, column=5, const_b=COBBLE_ROUGHNESS_LIFT)
        surface = blend(grass, cobbles, street_alpha, column=6)
        if channel == 'Color':
            surface = math(unreal.MaterialExpressionMultiply, surface, shade, column=7)
        outputs[channel] = surface
        if not edit.connect_material_property(surface, '', target):
            raise RuntimeError(f'Could not connect the ground material output {channel}.')
    edit.recompile_material(material)
    return material


def run(rebuild=False):
    """Import what is missing, build the material once, and put it on the ground block.

    `run(rebuild=True)` rewrites the existing material's graph after a constant changes.
    """
    import unreal

    _, world = require_town_editor(unreal)
    textures = import_textures(unreal)
    path = f'{FOLDER}/{NAME}'
    material = unreal.EditorAssetLibrary.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if material is None or rebuild:
        material = build_material(unreal, textures, material)
    ground, = (actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor)
               if actor.get_actor_label() == GROUND_LABEL)
    component = ground.get_component_by_class(unreal.StaticMeshComponent)
    component.modify()
    component.set_material(0, material)
    packages = [material.get_package(), *(textures[name].get_package() for name in SOURCES)]
    names = [package.get_name() for package in packages]
    if any(not name.startswith(FOLDER + '/') for name in names):
        raise RuntimeError(f'Unexpected ground packages: {names}')
    if not unreal.EditorLoadingAndSavingUtils.save_packages(packages, only_dirty=False):
        raise RuntimeError('Could not save the town ground packages.')
    return {'saved': names, 'ground': ground.get_actor_label(), 'map_saved': False}
