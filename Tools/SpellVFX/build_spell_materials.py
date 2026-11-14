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


EA.make_directory(FOLDER)
made = [
    additive('M_Spell_Glow', GLOW, ['UV', 'Col', 'A']),
    additive('M_Spell_Ribbon', RIBBON, ['UV', 'Col', 'A', 'T'], with_time=True),
    additive('M_Spell_Ring', RING, ['UV', 'Col', 'A', 'T'], with_time=True),
    additive('M_Spell_Shock', SHOCK, ['UV', 'Col', 'A']),
    soft_puff(),
    debris(),
    aim_decal(),
]
for m in made:
    EA.save_loaded_asset(m, False)
[m.get_path_name() for m in made]
