"""Builds the shared spell VFX materials (run inside the Unreal editor, UE 5.9).

All shading is a single HLSL Custom node per material so the look is readable in one place.
Materials are written to /Game/Characters/Hero/SpellVFX/Materials and saved.
"""
import unreal

FOLDER = '/Game/Characters/Hero/SpellVFX/Materials'
EA = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()

GLOW = r'''
float2 p = UV * 2 - 1;
float r = length(p);
float g = saturate(1 - r);
float halo = pow(g, 1.7);
float core = pow(g, 7) * 3.5;
return Col * A * (halo + core);
'''

RIBBON = r'''
float v = saturate(UV.y);
float edge = pow(sin(v * 3.14159), 2.2);
float core = pow(edge, 8) * 2.5;
float streak = 0.7 + 0.3 * sin(UV.x * 28 - T * 22 + v * 3);
float tail = saturate(UV.x * 4);
return Col * A * (edge * streak + core) * tail;
'''

RING = r'''
float2 p = UV * 2 - 1;
float s = sin(T * 0.7), c = cos(T * 0.7);
p = float2(p.x * c - p.y * s, p.x * s + p.y * c);
float r = length(p);
float a = atan2(p.y, p.x);
float outer = exp(-pow((r - 0.94) / 0.022, 2)) * 1.8;
float outer2 = exp(-pow((r - 0.86) / 0.012, 2));
float inner = exp(-pow((r - 0.70) / 0.014, 2)) * 1.2;
float seg = frac(a * 18 / 6.28318);
float band = step(0.735, r) * step(r, 0.835);
float glyph = band * step(0.18, seg) * step(seg, 0.82) * step(0.45, frac(r * 31 + floor(a * 18 / 6.28318) * 0.618)) * 0.55;
float tri = 0;
[unroll] for (int i = 0; i < 6; i++)
{
    float ang = 1.5708 + i * 1.0472;
    float2 n = float2(cos(ang), sin(ang));
    tri += exp(-pow((dot(p, n) + 0.35) / 0.012, 2));
}
tri *= step(r, 0.71);
float fill = pow(saturate(1 - r), 1.5) * 0.12;
return Col * A * (outer + outer2 + inner + glyph + tri * 0.9 + fill) * step(r, 1.0);
'''

SHOCK = r'''
float2 p = UV * 2 - 1;
float r = length(p);
float ring = exp(-pow((r - 0.85) / 0.09, 2));
float inner = exp(-pow((r - 0.85) / 0.025, 2)) * 1.5;
return Col * A * (ring + inner) * step(r, 1.0);
'''

DECAL = r'''
float2 p = UV * 2 - 1;
float r = length(p);
float s = sin(T * 1.2), c = cos(T * 1.2);
float2 q = float2(p.x * c - p.y * s, p.x * s + p.y * c);
float a = atan2(q.y, q.x);
float ring = exp(-pow((r - 0.93) / 0.03, 2)) * 1.6;
float dash = exp(-pow((r - 0.80) / 0.012, 2)) * step(0.5, frac(a * 16 / 6.28318));
float pulseR = frac(T * 0.9);
float pulse = exp(-pow((r - pulseR) / 0.05, 2)) * (1 - pulseR) * 0.8;
float fill = 0.10 + 0.05 * sin(T * 6);
float m = (ring + dash + pulse + fill * step(r, 0.93)) * step(r, 1.0);
return float4(Color * m * 2.0, saturate(m));
'''


# Ground marks left by impacts: one material, look picked by Kind (0 scorch, 1 frost, 2 wet, 3 lightning burn,
# 4 dirt, 5 arcane rune). Fade is DecalLifetimeOpacity: 1 during the component's fade delay, then down to 0.
# Returns (opacity, glow, roughness, 0); glowing parts (embers, burn streaks, rune) cool faster than the mark fades.
GROUND = r'''
float2 p = UV * 2 - 1;
float r = length(p);
float2 q = p * 2.6 + Seed * 0.731;
float n = 0, amp = 0.5;
[unroll] for (int o = 0; o < 4; o++)
{
    float2 i = floor(q);
    float2 f = frac(q);
    float2 u = f * f * (3 - 2 * f);
    float h00 = frac(sin(dot(i, float2(127.1, 311.7))) * 43758.5453);
    float h10 = frac(sin(dot(i + float2(1, 0), float2(127.1, 311.7))) * 43758.5453);
    float h01 = frac(sin(dot(i + float2(0, 1), float2(127.1, 311.7))) * 43758.5453);
    float h11 = frac(sin(dot(i + float2(1, 1), float2(127.1, 311.7))) * 43758.5453);
    n += amp * lerp(lerp(h00, h10, u.x), lerp(h01, h11, u.x), u.y);
    q = q * 2.07 + 3.1;
    amp *= 0.5;
}
float blob = 1 - smoothstep(0.42, 0.95, r + (n - 0.47) * 0.7);
float core = 1 - smoothstep(0.0, 0.55, r + (n - 0.47) * 0.5);
float a = atan2(p.y, p.x);
float rays = pow(saturate(abs(cos(a * 3.5 + n * 7.0 + Seed))), 30.0) * (1 - smoothstep(0.15, 0.95, r));
float lines = pow(saturate(1 - abs(frac(n * 7.0 + r * 1.5) - 0.5) * 2.0), 14.0);
float2 cell = floor(p * 34.0 + Seed);
float speck = step(0.86, frac(sin(dot(cell, float2(12.9898, 78.233))) * 43758.5453));
float ring = exp(-pow((r - 0.74) / 0.045, 2)) + exp(-pow((r - 0.56) / 0.02, 2)) * 0.6;
float hot = Fade * Fade * Fade * Fade;
float w0 = saturate(1 - abs(Kind - 0));
float w1 = saturate(1 - abs(Kind - 1));
float w2 = saturate(1 - abs(Kind - 2));
float w3 = saturate(1 - abs(Kind - 3));
float w4 = saturate(1 - abs(Kind - 4));
float w5 = saturate(1 - abs(Kind - 5));
// 6: tarnish stain (enemy magic) - a black-violet blot with glowing veins and silver flecks.
// 7: tarnish burst warning - a violet ring at the blast edge with a smoky fill; C++ ramps Strength 0.15 -> 1.
float w6 = saturate(1 - abs(Kind - 6));
float w7 = saturate(1 - abs(Kind - 7));
float veins = pow(saturate(1 - abs(frac(n * 5.0 + a * 0.32 + Seed * 0.1) - 0.5) * 2.0), 10.0) * (1 - smoothstep(0.2, 0.9, r));
float edge = exp(-pow((r - 0.93) / 0.035, 2));
float fill = (1 - smoothstep(0.86, 0.96, r)) * (0.45 + 0.55 * n);
float op = w0 * blob * (0.75 + 0.25 * core)
         + w1 * blob * (0.45 + 0.45 * lines)
         + w2 * blob * 0.55
         + w3 * saturate(blob * 0.45 + rays)
         + w4 * blob * (0.7 + 0.3 * lines)
         + w5 * saturate(blob * 0.18 + ring * 0.85)
         + w6 * saturate(blob * (0.82 + 0.18 * core) + veins * blob * 0.3)
         + w7 * saturate(edge * 0.95 + fill * 0.4);
float glow = w0 * (speck * blob * 1.5 + core * 0.8) * hot * 3.0
           + w1 * blob * lines * 0.25 * Fade
           + w3 * rays * hot * 6.0
           + w5 * ring * hot * 1.4
           + w6 * (veins * blob * 2.2 + speck * blob * 0.6) * hot
           + w7 * (edge * 3.0 + fill * 0.35);
float rough = w0 * 0.95 + w1 * 0.2 + w2 * 0.05 + w3 * 0.9 + w4 * 1.0 + w5 * 0.7 + w6 * 0.45 + w7 * 0.8;
return float4(saturate(op) * Fade * Strength, glow * Strength, rough, 0);
'''

GROUND_COLOR = r'''
float w0 = saturate(1 - abs(Kind - 0));
float w1 = saturate(1 - abs(Kind - 1));
float w2 = saturate(1 - abs(Kind - 2));
float w3 = saturate(1 - abs(Kind - 3));
float w4 = saturate(1 - abs(Kind - 4));
float w5 = saturate(1 - abs(Kind - 5));
float w6 = saturate(1 - abs(Kind - 6));
float w7 = saturate(1 - abs(Kind - 7));
return w6 * float3(0.010, 0.005, 0.016) + w7 * Color * 0.04
     + w0 * float3(0.012, 0.010, 0.009) + w1 * float3(0.70, 0.82, 0.93) + w2 * float3(0.02, 0.025, 0.03)
     + w3 * float3(0.02, 0.02, 0.025) + w4 * float3(0.09, 0.07, 0.05) + w5 * Color * 0.05;
'''


def fresh(name):
    path = FOLDER + '/' + name
    if EA.does_asset_exist(path):
        EA.delete_asset(path)
    return TOOLS.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def custom(mat, code, inputs, output_type, x=-500, y=0):
    node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property('code', code)
    node.set_editor_property('output_type', output_type)
    ins = []
    for n in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', n)
        ins.append(ci)
    node.set_editor_property('inputs', ins)
    return node


def particle_inputs(mat, node, with_time=False):
    uv = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, -100)
    col = MEL.create_material_expression(mat, unreal.MaterialExpressionParticleColor, -900, 50)
    MEL.connect_material_expressions(uv, '', node, 'UV')
    MEL.connect_material_expressions(col, 'RGB', node, 'Col')
    MEL.connect_material_expressions(col, 'A', node, 'A')
    if with_time:
        t = MEL.create_material_expression(mat, unreal.MaterialExpressionTime, -900, 200)
        MEL.connect_material_expressions(t, '', node, 'T')


def particle_usages(mat):
    for u in (unreal.MaterialUsage.MATUSAGE_NIAGARA_SPRITES, unreal.MaterialUsage.MATUSAGE_NIAGARA_RIBBONS,
              unreal.MaterialUsage.MATUSAGE_NIAGARA_MESH_PARTICLES):
        MEL.set_material_usage(mat, u)


def additive(name, code, inputs, with_time=False):
    mat = fresh(name)
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided', True)
    node = custom(mat, code, inputs, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    particle_inputs(mat, node, with_time)
    MEL.connect_material_property(node, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    particle_usages(mat)
    MEL.recompile_material(mat)
    return mat


def soft_puff():
    mat = fresh('M_Spell_SoftPuff')
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided', True)
    node = custom(mat, r'''
float2 p = UV * 2 - 1;
float r = length(p);
float w = sin(atan2(p.y, p.x) * 5 + A * 9) * 0.06;
return A * pow(saturate(1 - r + w), 2.2);
''', ['UV', 'Col', 'A'], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    particle_inputs(mat, node)
    fade = MEL.create_material_expression(mat, unreal.MaterialExpressionDepthFade, -250, 120)
    fade.set_editor_property('fade_distance_default', 40.0)
    MEL.connect_material_expressions(node, '', fade, 'Opacity')
    col = MEL.create_material_expression(mat, unreal.MaterialExpressionParticleColor, -500, -200)
    MEL.connect_material_property(col, 'RGB', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(fade, '', unreal.MaterialProperty.MP_OPACITY)
    particle_usages(mat)
    MEL.recompile_material(mat)
    return mat


def debris():
    mat = fresh('M_Spell_Debris')
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    col = MEL.create_material_expression(mat, unreal.MaterialExpressionParticleColor, -800, 0)
    fres = MEL.create_material_expression(mat, unreal.MaterialExpressionFresnel, -800, 200)
    fres.set_editor_property('exponent', 3.0)
    node = custom(mat, r'''return Col * (F * 1.8 + 0.04) * A;''', ['Col', 'A', 'F'],
                  unreal.CustomMaterialOutputType.CMOT_FLOAT3, -450, 150)
    MEL.connect_material_expressions(col, 'RGB', node, 'Col')
    MEL.connect_material_expressions(col, 'A', node, 'A')
    MEL.connect_material_expressions(fres, '', node, 'F')
    MEL.connect_material_property(col, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(node, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    rough = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, 350)
    rough.set_editor_property('r', 0.35)
    MEL.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
    particle_usages(mat)
    MEL.recompile_material(mat)
    return mat


def aim_decal():
    mat = fresh('M_Spell_AimDecal')
    mat.set_editor_property('material_domain', unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    node = custom(mat, DECAL, ['UV', 'Color', 'T'], unreal.CustomMaterialOutputType.CMOT_FLOAT4)
    uv = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, -100)
    color = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -900, 50)
    color.set_editor_property('parameter_name', 'Color')
    color.set_editor_property('default_value', unreal.LinearColor(1.0, 0.45, 0.1, 1.0))
    t = MEL.create_material_expression(mat, unreal.MaterialExpressionTime, -900, 250)
    MEL.connect_material_expressions(uv, '', node, 'UV')
    MEL.connect_material_expressions(color, 'RGB', node, 'Color')
    MEL.connect_material_expressions(t, '', node, 'T')
    rgb = MEL.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -250, -50)
    rgb.set_editor_property('r', True); rgb.set_editor_property('g', True); rgb.set_editor_property('b', True)
    alpha = MEL.create_material_expression(mat, unreal.MaterialExpressionComponentMask, -250, 100)
    alpha.set_editor_property('a', True)
    MEL.connect_material_expressions(node, '', rgb, '')
    MEL.connect_material_expressions(node, '', alpha, '')
    MEL.connect_material_property(rgb, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(rgb, '', unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(alpha, '', unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    return mat


def scalar(mat, name, value, x, y):
    node = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', value)
    return node


def mask(mat, channel, x, y):
    node = MEL.create_material_expression(mat, unreal.MaterialExpressionComponentMask, x, y)
    for c in 'rgba':
        node.set_editor_property(c, c == channel)
    return node


def ground_mark():
    mat = fresh('M_Spell_GroundMark')
    mat.set_editor_property('material_domain', unreal.MaterialDomain.MD_DEFERRED_DECAL)
    # Lit, premultiplied alpha. With Substrate on: a lit Translucent decal does not compile, colored transmittance
    # ignores Opacity (the whole projection box went dark), and an unlit decal only adds light, so it cannot darken.
    mat.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ALPHA_COMPOSITE)
    mat.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    uv = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -1100, -200)
    kind = scalar(mat, 'Kind', 0.0, -1100, -50)
    seed = scalar(mat, 'Seed', 0.0, -1100, 50)
    strength = scalar(mat, 'Strength', 1.0, -1100, 150)
    fade = MEL.create_material_expression(mat, unreal.MaterialExpressionDecalLifetimeOpacity, -1100, 250)
    color = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -1100, 400)
    color.set_editor_property('parameter_name', 'Color')
    color.set_editor_property('default_value', unreal.LinearColor(1.0, 0.3, 0.05, 1.0))
    node = custom(mat, GROUND, ['UV', 'Kind', 'Seed', 'Strength', 'Fade'], unreal.CustomMaterialOutputType.CMOT_FLOAT4, -700, 0)
    for src, pin in ((uv, 'UV'), (kind, 'Kind'), (seed, 'Seed'), (strength, 'Strength'), (fade, 'Fade')):
        MEL.connect_material_expressions(src, '', node, pin)
    tint = custom(mat, GROUND_COLOR, ['Kind', 'Color'], unreal.CustomMaterialOutputType.CMOT_FLOAT3, -700, 350)
    MEL.connect_material_expressions(kind, '', tint, 'Kind')
    MEL.connect_material_expressions(color, 'RGB', tint, 'Color')
    opacity, glow, rough = mask(mat, 'r', -350, -100), mask(mat, 'g', -350, 50), mask(mat, 'b', -350, 200)
    for m in (opacity, glow, rough):
        MEL.connect_material_expressions(node, '', m, '')
    hot = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, 50)
    MEL.connect_material_expressions(color, 'RGB', hot, 'A')
    MEL.connect_material_expressions(glow, '', hot, 'B')
    base = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, 300)  # premultiplied
    MEL.connect_material_expressions(tint, '', base, 'A')
    MEL.connect_material_expressions(opacity, '', base, 'B')
    MEL.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
    # Premultiplied alpha: every output is scaled by the mask, or the whole projection box shows.
    rough_pm = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, 450)
    MEL.connect_material_expressions(rough, '', rough_pm, 'A')
    MEL.connect_material_expressions(opacity, '', rough_pm, 'B')
    MEL.connect_material_property(rough_pm, '', unreal.MaterialProperty.MP_ROUGHNESS)
    spec = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -150, 600)
    spec.set_editor_property('const_a', 0.5)
    MEL.connect_material_expressions(opacity, '', spec, 'B')
    MEL.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
    MEL.connect_material_property(hot, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(opacity, '', unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    return mat


BUILDERS = {
    'glow': lambda: additive('M_Spell_Glow', GLOW, ['UV', 'Col', 'A']),
    'ribbon': lambda: additive('M_Spell_Ribbon', RIBBON, ['UV', 'Col', 'A', 'T'], with_time=True),
    'ring': lambda: additive('M_Spell_Ring', RING, ['UV', 'Col', 'A', 'T'], with_time=True),
    'shock': lambda: additive('M_Spell_Shock', SHOCK, ['UV', 'Col', 'A']),
    'puff': soft_puff,
    'debris': debris,
    'aim_decal': aim_decal,
    'ground_mark': ground_mark,
}
EA.make_directory(FOLDER)
# ARGS (set by the caller) picks materials by key; rebuilding one leaves the other assets untouched.
which = globals().get('ARGS') or list(BUILDERS)
made = [BUILDERS[k]() for k in which]
for m in made:
    EA.save_loaded_asset(m, False)
[m.get_path_name() for m in made]
