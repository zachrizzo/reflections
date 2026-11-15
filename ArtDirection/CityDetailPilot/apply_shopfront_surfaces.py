"""Build the shared street finish in the Unreal Editor's Python interpreter."""

from pathlib import Path

import unreal


PILOT = '/Game/GrayLondon/CityDetailPilot'
SURFACES = f'{PILOT}/StreetFinish/Surfaces'
MASTER_NAME = 'M_GL_ShopfrontWeathered'
WEAR_NAME = 'T_GL_SurfaceWear'
MESH_NAMES = ('Bookshop', 'Provisions', 'Townhouse')
MATERIALS = unreal.MaterialEditingLibrary
ASSETS = unreal.EditorAssetLibrary

# Packing: mineral pores, paint grain, and long rain streaks. Tile size is in cm.
STONE = (.76, .03, .21)
PAINT = (.17, .61, .22)
GLASS = (.11, .13, .76)
FABRIC = (.57, .37, .06)
STYLES = {
    'stone': ('StoneBase', (.25, .23, .19), STONE, 92, .80, .85, 0),
    'stone_light': ('Limestone', (.49, .46, .39), STONE, 103, .64, .79, 0),
    'trim_green': ('PaintDeepGreen', (.034, .083, .061), PAINT, 83, 1.07, .54, 0),
    'trim_blue': ('PaintSlateBlue', (.039, .075, .127), PAINT, 87, .98, .52, 0),
    'trim_brown': ('PaintDarkOak', (.111, .064, .040), PAINT, 83, 1.00, .53, 0),
    'glass': ('ShopGlass', (.047, .102, .101), GLASS, 112, .57, .22, 0),
    'door_glass': ('DoorGlass', (.079, .130, .123), GLASS, 80, .52, .27, 0),
    'brass': ('AgedBrass', (.52, .32, .13), PAINT, 25, .63, .34, .68),
    'canvas_red': ('CanvasOxblood', (.255, .056, .044), FABRIC, 74, .83, .88, 0),
    'canvas_cream': ('CanvasNatural', (.50, .426, .30), FABRIC, 72, .76, .88, 0),
}


def get_or_create(tools, name, asset_class, factory):
    existing = unreal.load_asset(f'{SURFACES}/{name}') if ASSETS.does_asset_exist(f'{SURFACES}/{name}') else None
    asset = existing or tools.create_asset(name, SURFACES, asset_class, factory)
    if not asset:
        raise RuntimeError(f'Could not create {SURFACES}/{name}')
    return asset


def import_noise(tools, source_dir):
    if ASSETS.does_asset_exist(f'{SURFACES}/{WEAR_NAME}'):
        texture = unreal.load_asset(f'{SURFACES}/{WEAR_NAME}')
    else:
        source = Path(source_dir).resolve() / f'{WEAR_NAME}.png'
        if not source.is_file():
            raise FileNotFoundError(source)
        task = unreal.AssetImportTask()
        task.set_editor_properties({
            'filename': str(source), 'destination_path': SURFACES,
            'destination_name': WEAR_NAME, 'automated': True, 'save': False,
        })
        tools.import_asset_tasks([task])
        texture = next(iter(task.get_objects()), None)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError('Could not import the packed street wear map')
    texture.set_editor_properties({
        'srgb': False,
        'compression_settings': unreal.TextureCompressionSettings.TC_MASKS,
    })
    return texture


def build_master(tools, texture):
    world_aligned = unreal.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture')
    if not world_aligned:
        raise RuntimeError('The engine WorldAlignedTexture function is unavailable')
    material = get_or_create(tools, MASTER_NAME, unreal.Material, unreal.MaterialFactoryNew())
    MATERIALS.delete_all_material_expressions(material)

    def node(kind, x, y, **properties):
        expression = MATERIALS.create_material_expression(material, kind, x, y)
        if properties:
            expression.set_editor_properties(properties)
        return expression

    def connect(src, dst, input_name, output_name=''):
        if not MATERIALS.connect_material_expressions(src, output_name, dst, input_name):
            raise RuntimeError(f'Could not connect {src.get_name()} {output_name} to {dst.get_name()} {input_name}')

    def connect_output(src, prop, output_name=''):
        if not MATERIALS.connect_material_property(src, output_name, prop):
            raise RuntimeError(f'Could not connect {prop} in {material.get_name()}')

    def scalar(name, default, x, y):
        return node(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default)

    def vector(name, color, x, y):
        return node(unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
                    default_value=unreal.LinearColor(*color, 1))

    noise = node(unreal.MaterialExpressionTextureObject, -1260, 0, texture=texture,
                 sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    scale = scalar('TileSizeCm', 100, -1260, 180)
    projection = node(unreal.MaterialExpressionMaterialFunctionCall, -1000, 0)
    projection.set_material_function(world_aligned)
    connect(noise, projection, 'TextureObject')
    connect(scale, projection, 'TextureSize')

    weights = vector('WearChannels', STONE, -1000, 370)
    mixture = node(unreal.MaterialExpressionDotProduct, -725, 40)
    connect(projection, mixture, 'A', 'XYZ Texture')
    connect(weights, mixture, 'B')
    deviation = node(unreal.MaterialExpressionAdd, -550, 40, const_b=-.5)
    connect(mixture, deviation, 'A')
    intensity = scalar('Weathering', .8, -550, 190)
    wear = node(unreal.MaterialExpressionMultiply, -360, 20)
    connect(deviation, wear, 'A')
    connect(intensity, wear, 'B')
    albedo_scale = node(unreal.MaterialExpressionAdd, -180, -100, const_b=1)
    connect(wear, albedo_scale, 'A')
    tint = vector('SurfaceTint', (.33, .31, .27), -180, -275)
    albedo = node(unreal.MaterialExpressionMultiply, 0, -150)
    connect(tint, albedo, 'A')
    connect(albedo_scale, albedo, 'B')
    connect_output(albedo, unreal.MaterialProperty.MP_BASE_COLOR)

    roughness = scalar('Roughness', .74, -350, 290)
    roughness_wear = node(unreal.MaterialExpressionMultiply, -180, 300, const_b=-.25)
    connect(wear, roughness_wear, 'A')
    roughness_sum = node(unreal.MaterialExpressionAdd, 0, 250)
    connect(roughness, roughness_sum, 'A')
    connect(roughness_wear, roughness_sum, 'B')
    roughness_clamp = node(unreal.MaterialExpressionClamp, 160, 250, min_default=.10, max_default=.96)
    connect(roughness_sum, roughness_clamp, 'Input')
    connect_output(roughness_clamp, unreal.MaterialProperty.MP_ROUGHNESS)
    metallic = scalar('Metallic', 0, 160, 435)
    connect_output(metallic, unreal.MaterialProperty.MP_METALLIC)

    errors = MATERIALS.recompile_material(material)
    if errors:
        raise RuntimeError(f'Street finish material failed to compile: {list(errors)}')
    return material


def build_surfaces(source_dir):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    texture = import_noise(tools, source_dir)
    material = build_master(tools, texture)
    paths = [texture.get_path_name(), material.get_path_name()]
    for name, color, weights, size, strength, roughness, metallic in STYLES.values():
        instance = get_or_create(tools, f'MI_GL_{name}', unreal.MaterialInstanceConstant,
                                 unreal.MaterialInstanceConstantFactoryNew())
        MATERIALS.set_material_instance_parent(instance, material)
        for key, value in (('SurfaceTint', color), ('WearChannels', weights)):
            if not MATERIALS.set_material_instance_vector_parameter_value(instance, key, unreal.LinearColor(*value, 1)):
                raise RuntimeError(f'Could not set {key} for {name}')
        for key, value in (('TileSizeCm', size), ('Weathering', strength), ('Roughness', roughness), ('Metallic', metallic)):
            if not MATERIALS.set_material_instance_scalar_parameter_value(instance, key, value):
                raise RuntimeError(f'Could not set {key} for {name}')
        paths.append(instance.get_path_name())
    return save_paths(paths)


def apply_surfaces():
    surfaces = {f'GL_{slot}': unreal.load_asset(f'{SURFACES}/MI_GL_{style[0]}') for slot, style in STYLES.items()}
    if any(not interface for interface in surfaces.values()):
        raise RuntimeError('Build and save the street finish materials before assigning mesh slots')
    planned = []
    for name in MESH_NAMES:
        mesh = unreal.load_asset(f'{PILOT}/SM_GL_Shopfront_{name}')
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError(f'Could not load shopfront mesh {name}')
        slot_names = [str(slot.get_editor_property('material_slot_name')) for slot in mesh.get_editor_property('static_materials')]
        if not slot_names or any(slot not in surfaces for slot in slot_names):
            raise RuntimeError(f'Found unexpected material slots on {name}: {slot_names}')
        planned.append((mesh, slot_names))
    for mesh, slot_names in planned:
        mesh.modify()
        for index, slot in enumerate(slot_names):
            mesh.set_material(index, surfaces[slot])
    return save_paths(mesh.get_path_name() for mesh, _ in planned)


def save_paths(paths):
    saved = {}
    for path in paths:
        saved[path.split('.', 1)[0]] = ASSETS.save_asset(path, only_if_is_dirty=False)
    if not all(saved.values()):
        raise RuntimeError(f'Street finish package save failed: {saved}')
    return saved
