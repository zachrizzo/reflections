"""Builds the villain's materials in /Game/Villain/Materials (run inside the editor through the MCP Python tool).

Every look is one or two Custom HLSL nodes fed by plain parameter nodes, so the shading reads here, not in a graph.
Parameters the C++ sets: Glow, Flash (body / shroud / eyes), Intensity (overlays), Color / Progress / Band / Opacity
(telegraph). Safe to re-run: an existing material is cleared and rebuilt in place (no delete, so it works during PIE).
"""
import unreal

MEL = unreal.MaterialEditingLibrary
FOLDER = '/Game/Villain/Materials'
AR = unreal.AssetRegistryHelpers.get_asset_registry()
LOG = []


def get_or_create(name):
    path = '%s/%s' % (FOLDER, name)
    existing = unreal.load_asset(path)
    if existing:
        MEL.delete_all_material_expressions(existing)
        return existing
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    return tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def node(mat, cls, x, y):
    return MEL.create_material_expression(mat, cls, x, y)


def scalar(mat, name, default, x, y):
    n = node(mat, unreal.MaterialExpressionScalarParameter, x, y)
    n.set_editor_property('parameter_name', name)
    n.set_editor_property('default_value', default)
    return n


def vector(mat, name, rgba, x, y):
    n = node(mat, unreal.MaterialExpressionVectorParameter, x, y)
    n.set_editor_property('parameter_name', name)
    n.set_editor_property('default_value', unreal.LinearColor(*rgba))
    return n


def const(mat, value, x, y):
    n = node(mat, unreal.MaterialExpressionConstant, x, y)
    n.set_editor_property('r', value)
    return n


def custom(mat, code, inputs, out_type, x, y, desc='Custom'):
    """inputs: list of (name, expression). out_type: 1..4 floats."""
    n = node(mat, unreal.MaterialExpressionCustom, x, y)
    n.set_editor_property('code', code)
    n.set_editor_property('description', desc)
    types = {1: unreal.CustomMaterialOutputType.CMOT_FLOAT1, 2: unreal.CustomMaterialOutputType.CMOT_FLOAT2,
             3: unreal.CustomMaterialOutputType.CMOT_FLOAT3, 4: unreal.CustomMaterialOutputType.CMOT_FLOAT4}
    n.set_editor_property('output_type', types[out_type])
    pins = []
    for name, _ in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property('input_name', name)
        pins.append(pin)
    n.set_editor_property('inputs', pins)
    for name, src in inputs:
        if not MEL.connect_material_expressions(src, '', n, name):
            LOG.append('connect failed: %s.%s' % (desc, name))
    return n


def time(mat, x, y):
    return node(mat, unreal.MaterialExpressionTime, x, y)


def fresnel(mat, exponent, x, y):
    n = node(mat, unreal.MaterialExpressionFresnel, x, y)
    n.set_editor_property('exponent', exponent)
    n.set_editor_property('base_reflect_fraction', 0.0)
    return n


def out(mat, expr, prop):
    if not MEL.connect_material_property(expr, '', prop):
        LOG.append('property connect failed: %s %s' % (mat.get_name(), prop))


USAGE = {
    'M_Villain_Body': ['MATUSAGE_SKELETAL_MESH', 'MATUSAGE_INSTANCED_STATIC_MESHES'],
    'M_Villain_InfectedOverlay': ['MATUSAGE_SKELETAL_MESH'],
    'M_Villain_BurnedOverlay': ['MATUSAGE_SKELETAL_MESH'],
    'M_Villain_Shroud': [],
    'M_Villain_Eye': [],
    'M_Villain_Telegraph': [],
    'M_Villain_Mirror': ['MATUSAGE_INSTANCED_STATIC_MESHES'],
    'M_Villain_Heart': [],
}


def finish(mat):
    # Without the usage flags a cooked build draws the default material on skeletal meshes (and in the editor
    # the first frames do too). Static meshes need no flag.
    for usage in USAGE.get(mat.get_name(), []):
        MEL.set_base_material_usage(mat, getattr(unreal.MaterialUsage, usage), True)
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    return mat


RIM = '''
float pulse = 0.85 + 0.15 * sin(T * 2.3);
return Rim.rgb * Fres * 3.2 * Glow * pulse + float3(1.0, 0.94, 0.86) * Flash * (0.35 + Fres * 1.5);
'''


CRACKS = '''
float2 q = UV * 9.0;
float2 cell = floor(q);
float2 f = frac(q);
float d1 = 8.0;
float d2 = 8.0;
for (int y = -1; y <= 1; y++)
{
    for (int x = -1; x <= 1; x++)
    {
        float2 g = float2(x, y);
        float2 h = frac(sin(float2(dot(cell + g, float2(127.1, 311.7)), dot(cell + g, float2(269.5, 183.3)))) * 43758.5453);
        float d = length(g + h - f);
        if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
    }
}
float crack = 1.0 - saturate((d2 - d1) / 0.045);
float tarnish = frac(sin(dot(floor(UV * 23.0), float2(41.3, 289.1))) * 43758.5453) * 0.5 + 0.5 * sin(UV.x * 31.0 + UV.y * 17.0);
'''

RIM2 = '''
float pulse = 0.85 + 0.15 * sin(T * 2.3);
float3 rim = Rim.rgb * FresWide * 2.2 + float3(0.92, 0.9, 1.0) * FresEdge * 2.6;
'''


def build_body():
    """Cracked, tarnished silver: dark metal that catches the sky, cracks that glow, a two-tone rim (silver edge, violet)."""
    m = get_or_create('M_Villain_Body')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property('two_sided', False)
    uv = node(m, unreal.MaterialExpressionTextureCoordinate, -1300, -300)
    t = time(m, -1300, -180)
    base = custom(m, CRACKS + 'return lerp(float3(0.006, 0.005, 0.009), float3(0.075, 0.072, 0.085), saturate(0.35 + 0.4 * tarnish)) * (1.0 - crack * 0.6);',
                  [('UV', uv)], 3, -600, -400, 'TarnishedSilver')
    out(m, base, unreal.MaterialProperty.MP_BASE_COLOR)
    out(m, const(m, 0.85, -600, -250), unreal.MaterialProperty.MP_METALLIC)
    rough = custom(m, CRACKS + 'return 0.28 + 0.4 * saturate(tarnish);', [('UV', uv)], 1, -600, -150, 'TarnishRoughness')
    out(m, rough, unreal.MaterialProperty.MP_ROUGHNESS)
    e = custom(m, CRACKS + RIM2 + '''
float3 cracks = lerp(Rim.rgb * 3.0, float3(1.0, 0.95, 1.0), 0.35) * crack * (0.55 + 0.45 * sin(T * 2.7 + UV.y * 9.0));
return (rim + cracks * 2.4) * Glow * pulse + float3(1.0, 0.94, 0.86) * Flash * (0.35 + FresWide * 1.5);
''', [('UV', uv), ('T', t), ('FresWide', fresnel(m, 3.0, -1300, 0)), ('FresEdge', fresnel(m, 8.0, -1300, 100)),
         ('Glow', scalar(m, 'Glow', 1.0, -1300, 200)), ('Flash', scalar(m, 'Flash', 0.0, -1300, 300)),
         ('Rim', vector(m, 'RimColor', (0.36, 0.06, 0.82, 1), -1300, 400))], 3, -600, 100, 'CracksAndRim')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


def build_shroud():
    m = get_or_create('M_Villain_Shroud')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property('two_sided', True)
    m.set_editor_property('opacity_mask_clip_value', 0.5)
    uv = node(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    t = time(m, -1200, 120)
    out(m, vector(m, 'BaseColor', (0.008, 0.006, 0.012, 1), -600, -400), unreal.MaterialProperty.MP_BASE_COLOR)
    out(m, const(m, 0.75, -600, -250), unreal.MaterialProperty.MP_ROUGHNESS)
    out(m, const(m, 0.08, -600, -170), unreal.MaterialProperty.MP_SPECULAR)
    e = custom(m, RIM2 + 'return (Rim.rgb * FresWide * 1.1 + float3(0.92, 0.9, 1.0) * FresEdge * 1.9) * Glow * pulse + float3(1.0, 0.94, 0.86) * Flash * (0.3 + FresWide);',
               [('FresWide', fresnel(m, 4.0, -900, 0)), ('FresEdge', fresnel(m, 9.0, -900, 60)), ('Glow', scalar(m, 'Glow', 1.0, -900, 100)),
                ('Flash', scalar(m, 'Flash', 0.0, -900, 180)), ('Rim', vector(m, 'RimColor', (0.36, 0.06, 0.82, 1), -900, 260)), ('T', t)],
               3, -500, 0, 'Rim')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    # Tattered hem: vertical strips of random length, swaying a little; v = 0 at the neck, 1 at the hem.
    mask = custom(m, '''
float col = floor(UV.x * 56.0);
float r = frac(sin(col * 12.9898 + 4.1) * 43758.5453);
float r2 = frac(sin(col * 78.233 + 1.7) * 24634.6345);
float len = 0.72 + r * 0.28 + sin(T * (0.8 + r2) + col) * 0.015;
return UV.y < len ? 1.0 : 0.0;
''', [('UV', uv), ('T', t)], 1, -500, 300, 'Tatters')
    out(m, mask, unreal.MaterialProperty.MP_OPACITY_MASK)
    # Loose, shifting cloth: sway and ripple grow toward the hem.
    wp = node(m, unreal.MaterialExpressionWorldPosition, -1200, 400)
    nrm = node(m, unreal.MaterialExpressionVertexNormalWS, -1200, 520)
    wpo = custom(m, '''
float w = saturate(UV.y);
w = w * w;
float3 sway = float3(sin(T * 1.3 + WP.z * 0.021 + WP.x * 0.011), cos(T * 1.05 + WP.z * 0.027 + WP.y * 0.013), 0.0) * 10.0;
float ripple = sin(T * 3.1 + UV.x * 31.4159 + UV.y * 12.0) * 3.5 + sin(T * 5.3 + UV.x * 62.83 - UV.y * 20.0) * 1.5;
return (sway + N * ripple) * w * Wind;
''', [('UV', uv), ('T', t), ('WP', wp), ('N', nrm), ('Wind', scalar(m, 'Wind', 1.0, -1200, 640))], 3, -500, 520, 'Cloth')
    out(m, wpo, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return finish(m)


def build_eye():
    m = get_or_create('M_Villain_Eye')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    e = custom(m, 'return EyeColor.rgb * 45.0 * Glow + float3(1, 1, 1) * Flash * 20.0;',
               [('EyeColor', vector(m, 'EyeColor', (0.92, 0.8, 1.0, 1), -900, 0)), ('Glow', scalar(m, 'Glow', 1.0, -900, 120)),
                ('Flash', scalar(m, 'Flash', 0.0, -900, 220))], 3, -500, 0, 'Eye')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


VEINS = '''
float a = sin(WP.x * 0.085 + sin(WP.z * 0.06 + T * 0.55) * 2.2) * sin(WP.y * 0.08 + WP.z * 0.045 - T * 0.3);
float b = sin(WP.z * 0.11 + sin(WP.x * 0.05 + WP.y * 0.05) * 3.0 + T * 0.4);
float v = min(abs(a), abs(b));
float core = saturate(1.0 - v * 11.0);
float edge = saturate(1.0 - v * 4.0) - core;
float pulse = 0.65 + 0.35 * sin(T * 3.0 + WP.z * 0.02);
'''


def build_infected():
    m = get_or_create('M_Villain_InfectedOverlay')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided', False)
    wp = node(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    t = time(m, -1200, 120)
    f = fresnel(m, 2.4, -1200, 240)
    i = scalar(m, 'Intensity', 1.0, -1200, 360)
    c = vector(m, 'VeinColor', (0.5, 0.09, 1.0, 1), -1200, 480)
    e = custom(m, VEINS + 'return Vein.rgb * (edge * 1.6 * pulse + Fres * 1.8) * Intensity;',
               [('WP', wp), ('T', t), ('Fres', f), ('Intensity', i), ('Vein', c)], 3, -500, 0, 'VeinGlow')
    o = custom(m, VEINS + 'return saturate((core * 0.92 + edge * 0.45 + Fres * 0.55) * Intensity);',
               [('WP', wp), ('T', t), ('Fres', f), ('Intensity', i)], 1, -500, 300, 'VeinOpacity')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    out(m, o, unreal.MaterialProperty.MP_OPACITY)
    return finish(m)


def build_burned():
    m = get_or_create('M_Villain_BurnedOverlay')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    wp = node(m, unreal.MaterialExpressionWorldPosition, -1200, 0)
    t = time(m, -1200, 120)
    i = scalar(m, 'Intensity', 1.0, -1200, 240)
    code = '''
float n = frac(sin(dot(floor(WP.xyz * 0.25), float3(12.9898, 78.233, 37.719))) * 43758.5453);
float ember = step(0.985, n) * (0.5 + 0.5 * sin(T * 4.0 + n * 40.0));
'''
    e = custom(m, code + 'return float3(0.018, 0.016, 0.015) + float3(1.0, 0.35, 0.1) * ember * 3.0;', [('WP', wp), ('T', t)], 3, -500, 0, 'Ash')
    o = custom(m, code + 'return saturate(0.72 * Intensity + ember);', [('WP', wp), ('T', t), ('Intensity', i)], 1, -500, 250, 'AshOpacity')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    out(m, o, unreal.MaterialProperty.MP_OPACITY)
    return finish(m)


TELE = '''
float2 d = UV - 0.5;
float r = length(d) * 2.0;
float inside = step(r, 1.0);
float b = max(Band, 0.005);
float ring = saturate(1.0 - abs(r - (1.0 - b * 0.5)) / (b * 0.5));
float fill = saturate((Progress - r) * 25.0) * step(0.001, Progress);
float front = saturate(1.0 - abs(r - Progress) * 22.0) * step(0.001, Progress) * step(Progress, 0.999);
float ang = atan2(d.y, d.x);
float rune = step(0.82, frac(ang * 1.9099 + T * 0.35)) * step(0.6, r) * step(r, 0.74);
float flick = 0.85 + 0.15 * sin(T * 13.0);
'''


def build_telegraph():
    m = get_or_create('M_Villain_Telegraph')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided', True)
    uv = node(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    t = time(m, -1200, 100)
    p = scalar(m, 'Progress', 0.0, -1200, 200)
    b = scalar(m, 'Band', 0.07, -1200, 300)
    op = scalar(m, 'Opacity', 1.0, -1200, 400)
    c = vector(m, 'Color', (0.32, 0.04, 0.62, 1), -1200, 500)
    e = custom(m, TELE + 'return Color.rgb * (ring * 6.0 + fill * 0.9 + front * 5.0 + rune * 2.5) * flick * inside;',
               [('UV', uv), ('T', t), ('Progress', p), ('Band', b), ('Color', c)], 3, -500, 0, 'TelegraphColor')
    o = custom(m, TELE + 'return saturate(ring * 0.95 + fill * 0.45 + front * 0.85 + rune * 0.5) * inside * Opacity;',
               [('UV', uv), ('T', t), ('Progress', p), ('Band', b), ('Opacity', op)], 1, -500, 300, 'TelegraphOpacity')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    out(m, o, unreal.MaterialProperty.MP_OPACITY)
    return finish(m)


def build_mirror():
    """Tarnished mirror glass: near-chrome with dark tarnish blooms, violet-lit edges."""
    m = get_or_create('M_Villain_Mirror')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property('two_sided', True)
    uv = node(m, unreal.MaterialExpressionTextureCoordinate, -1200, -300)
    t = time(m, -1200, -200)
    tarnish = 'float tn = saturate(0.5 + 0.5 * sin(UV.x * 11.0 + sin(UV.y * 7.0) * 2.0) * sin(UV.y * 9.0 + 1.3));'
    out(m, custom(m, tarnish + 'return lerp(float3(0.82, 0.81, 0.88), float3(0.09, 0.07, 0.11), tn * 0.7);', [('UV', uv)], 3, -600, -350, 'Silver'),
        unreal.MaterialProperty.MP_BASE_COLOR)
    out(m, const(m, 1.0, -600, -250), unreal.MaterialProperty.MP_METALLIC)
    out(m, custom(m, tarnish + 'return 0.05 + 0.35 * tn;', [('UV', uv)], 1, -600, -150, 'MirrorRough'), unreal.MaterialProperty.MP_ROUGHNESS)
    # Look pass: a hard silver flash when a spinning shard's face turns to the camera (the 'mirror glint'), a brighter edge,
    # and (second pass) a steady silver self-glow so the shards stay bright against the dark core even in Frostside's light.
    e = custom(m, 'float glint = pow(saturate(1.0 - Fres), 28.0); return (Rim.rgb * Fres * 3.0 + float3(0.92, 0.9, 1.0) * Edge * 3.5) * Glow * (0.8 + 0.2 * sin(T * 3.0)) + float3(1.0, 0.98, 1.0) * glint * 9.0 + float3(0.78, 0.77, 0.86) * 1.4 * Glow + Flash * 4.0;',
               [('Fres', fresnel(m, 3.0, -1200, 0)), ('Edge', fresnel(m, 9.0, -1200, 80)), ('Glow', scalar(m, 'Glow', 1.0, -1200, 160)),
                ('Flash', scalar(m, 'Flash', 0.0, -1200, 240)), ('Rim', vector(m, 'RimColor', (0.36, 0.06, 0.82, 1), -1200, 320)), ('T', t)],
               3, -600, 50, 'EdgeGlow')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


def build_heart():
    """The burning core: violet ringed, white-hot centre, pulsing. The thing to shoot."""
    m = get_or_create('M_Villain_Heart')
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    e = custom(m, 'float core = pow(saturate(Fres), 0.6); return lerp(float3(1.0, 0.96, 1.0) * 40.0, float3(0.55, 0.12, 1.0) * 26.0, core) * Glow + float3(1, 1, 1) * Flash * 30.0;',
               [('Fres', fresnel(m, 1.5, -900, 0)), ('Glow', scalar(m, 'Glow', 1.0, -900, 120)), ('Flash', scalar(m, 'Flash', 0.0, -900, 220))],
               3, -500, 0, 'Heart')
    out(m, e, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(m)


built = [build_body(), build_shroud(), build_eye(), build_infected(), build_burned(), build_telegraph(), build_mirror(), build_heart()]
saved = unreal.EditorLoadingAndSavingUtils.save_packages([b.get_outermost() for b in built], True)
RESULT = {'built': [b.get_path_name() for b in built], 'saved': saved, 'log': LOG}
