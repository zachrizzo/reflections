"""M_LanthorneGarment graph: cloth shading for every fitted garment (editor Python; exec'd by a caller).

Defines build(mat), which rebuilds a material's graph in place. Parameter names are the same as the original master's
(BaseColor, Tint, Normal, ORM), so every existing MI keeps its overrides and simply picks up the new shading:
  * BaseColor x Tint x fabric tone x edge -> Base Color. Tint keeps its meaning: the tone averages 1. WeaveTone (default
    0.10) makes thread tops lighter and gaps darker, faded at distance. Mottle (default 0.04) is a soft value-noise
    variation, because Codex's base-colour textures are one solid colour. EdgeDarken (default 0.15) darkens toward
    silhouettes and fold edges through a Fresnel term (exponent 3).
  * Roughness = ORM.G x Roughness (scalar, default 0.85, cloth).
  * Metallic = ORM.B x Metallic (scalar, default 0). The original wired ORM.B straight to Metallic, and ORM defaults to a
    white texture, so every garment rendered fully metallic: dark and flat, with no diffuse.
  * AO = ORM.R (unchanged).
  * Normal = the Normal texture whiteout-blended with a procedural plain-weave normal in UV space. WeaveScale is threads
    per UV unit (default 150, about 6 mm threads on Codex's garments, which have about 0.9 m per UV unit; boots have
    about 0.3 m). WeaveStrength (default 0.35) sets its depth. The weave fades out where a thread is smaller than about
    a pixel: it fades by pixel depth between about 2.5 m and 6 m, scaled by WeaveScale, so it doesn't shimmer at
    distance. fwidth isn't used because the project has ray tracing on, and ray-tracing hit shaders have no derivatives.
No new textures: the weave is maths in one Custom node.
"""
import unreal

MEL = unreal.MaterialEditingLibrary

WEAVE_HLSL = r'''
float2 p = UV * Scale;
float k = 150.0 / max(Scale, 1.0);
float fade = saturate((600.0 * k - Depth) / (350.0 * k));
float h[3];
float2 o[3] = { float2(0.0, 0.0), float2(0.02, 0.0), float2(0.0, 0.02) };
[unroll] for (int i = 0; i < 3; i++)
{
    float2 q = p + o[i];
    float warp = sin(3.14159 * frac(q.x)) * (0.55 + 0.45 * sin(3.14159 * q.y + 3.14159 * floor(q.x)));
    float weft = sin(3.14159 * frac(q.y)) * (0.55 - 0.45 * sin(3.14159 * q.x + 3.14159 * floor(q.y)));
    h[i] = max(warp, weft);
}
float2 g = float2(h[1] - h[0], h[2] - h[0]) / 0.02;
float3 w = normalize(float3(-g * Strength * 0.25 * fade, 1.0));
return normalize(float3(N.xy + w.xy, N.z * w.z));
'''

# Brightness multiplier for BaseColor (about 1 on average, so Tint keeps its meaning): thread tops lighter and gaps
# darker (+-Amount, faded like the normal) and a soft value-noise mottle about 7 cells per UV unit (+-Mottle).
TONE_HLSL = r'''
float2 p = UV * Scale;
float k = 150.0 / max(Scale, 1.0);
float fade = saturate((600.0 * k - Depth) / (350.0 * k));
float warp = sin(3.14159 * frac(p.x)) * (0.55 + 0.45 * sin(3.14159 * p.y + 3.14159 * floor(p.x)));
float weft = sin(3.14159 * frac(p.y)) * (0.55 - 0.45 * sin(3.14159 * p.x + 3.14159 * floor(p.y)));
float h = max(warp, weft);
float2 m = UV * 7.0;
float2 i0 = floor(m);
float2 f = frac(m);
f = f * f * (3.0 - 2.0 * f);
float a = frac(sin(dot(i0, float2(127.1, 311.7))) * 43758.5453);
float b = frac(sin(dot(i0 + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
float c = frac(sin(dot(i0 + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
float d = frac(sin(dot(i0 + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
float n = lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
return 1.0 + Amount * 2.0 * (h - 0.6) * fade + Mottle * 2.0 * (n - 0.5);
'''


def _tex_param(mat, name, x, y, tex, sampler=None):
    e = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    e.set_editor_property('parameter_name', name)
    if sampler is not None:
        e.set_editor_property('sampler_type', sampler)
    e.set_editor_property('texture', unreal.load_asset(tex))
    return e


def _scalar(mat, name, value, x, y):
    e = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property('parameter_name', name)
    e.set_editor_property('default_value', value)
    return e


def build(mat):
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property('two_sided', True)
    base = _tex_param(mat, 'BaseColor', -900, -300, '/Engine/EngineResources/WhiteSquareTexture')
    tint = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -900, -60)
    tint.set_editor_property('parameter_name', 'Tint')
    tint.set_editor_property('default_value', unreal.LinearColor(1, 1, 1, 1))
    mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -500, -220)
    MEL.connect_material_expressions(base, 'RGB', mul, 'A')
    MEL.connect_material_expressions(tint, '', mul, 'B')
    # Fabric tone: weave + mottle brightness, then a soft Fresnel darkening toward silhouettes and fold edges.
    uv0 = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -900, -560)
    tone_scale = _scalar(mat, 'WeaveScale', 150.0, -900, -500)
    tone_amt = _scalar(mat, 'WeaveTone', 0.10, -900, -440)
    mottle = _scalar(mat, 'Mottle', 0.04, -900, -380)
    tone = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -650, -520)
    tone.set_editor_property('description', 'FabricTone')
    tone.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    tone.set_editor_property('code', TONE_HLSL)
    tins = []
    for n in ('UV', 'Scale', 'Amount', 'Mottle', 'Depth'):
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', n)
        tins.append(ci)
    tone.set_editor_property('inputs', tins)
    MEL.connect_material_expressions(uv0, '', tone, 'UV')
    MEL.connect_material_expressions(tone_scale, '', tone, 'Scale')
    MEL.connect_material_expressions(tone_amt, '', tone, 'Amount')
    MEL.connect_material_expressions(mottle, '', tone, 'Mottle')
    depth = MEL.create_material_expression(mat, unreal.MaterialExpressionPixelDepth, -900, -620)
    MEL.connect_material_expressions(depth, '', tone, 'Depth')
    toned = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -350, -300)
    MEL.connect_material_expressions(mul, '', toned, 'A')
    MEL.connect_material_expressions(tone, '', toned, 'B')
    fres = MEL.create_material_expression(mat, unreal.MaterialExpressionFresnel, -650, -150)
    fres.set_editor_property('exponent', 3.0)
    fres.set_editor_property('base_reflect_fraction', 0.0)
    edge_amt = _scalar(mat, 'EdgeDarken', 0.15, -900, -200)
    one_minus = MEL.create_material_expression(mat, unreal.MaterialExpressionOneMinus, -650, -60)
    MEL.connect_material_expressions(edge_amt, '', one_minus, '')
    edge = MEL.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -450, -120)
    edge.set_editor_property('const_a', 1.0)
    MEL.connect_material_expressions(one_minus, '', edge, 'B')
    MEL.connect_material_expressions(fres, '', edge, 'Alpha')
    final = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, -220)
    MEL.connect_material_expressions(toned, '', final, 'A')
    MEL.connect_material_expressions(edge, '', final, 'B')
    MEL.connect_material_property(final, '', unreal.MaterialProperty.MP_BASE_COLOR)

    orm = _tex_param(mat, 'ORM', -900, 420, '/Engine/EngineResources/WhiteSquareTexture', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    rough = _scalar(mat, 'Roughness', 0.85, -900, 700)
    metal = _scalar(mat, 'Metallic', 0.0, -900, 800)
    mr = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -500, 520)
    MEL.connect_material_expressions(orm, 'G', mr, 'A')
    MEL.connect_material_expressions(rough, '', mr, 'B')
    MEL.connect_material_property(mr, '', unreal.MaterialProperty.MP_ROUGHNESS)
    mm = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -500, 640)
    MEL.connect_material_expressions(orm, 'B', mm, 'A')
    MEL.connect_material_expressions(metal, '', mm, 'B')
    MEL.connect_material_property(mm, '', unreal.MaterialProperty.MP_METALLIC)
    MEL.connect_material_property(orm, 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)

    nrm = _tex_param(mat, 'Normal', -900, 100, '/Engine/EngineMaterials/DefaultNormal', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    uv, scale = uv0, tone_scale      # one UV node and one WeaveScale parameter drive both the tone and the normal
    strength = _scalar(mat, 'WeaveStrength', 0.35, -900, 380)
    cus = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -450, 150)
    cus.set_editor_property('description', 'FabricWeave')
    cus.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    cus.set_editor_property('code', WEAVE_HLSL)
    ins = []
    for n in ('UV', 'Scale', 'Strength', 'N', 'Depth'):
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', n)
        ins.append(ci)
    cus.set_editor_property('inputs', ins)
    MEL.connect_material_expressions(uv, '', cus, 'UV')
    MEL.connect_material_expressions(scale, '', cus, 'Scale')
    MEL.connect_material_expressions(strength, '', cus, 'Strength')
    MEL.connect_material_expressions(nrm, 'RGB', cus, 'N')
    MEL.connect_material_expressions(depth, '', cus, 'Depth')
    MEL.connect_material_property(cus, '', unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(mat)
    return mat


def stats(mat):
    st = MEL.get_statistics(mat)
    out = {}
    for k in ('num_pixel_shader_instructions', 'num_vertex_shader_instructions', 'num_samplers', 'num_pixel_texture_samples'):
        try:
            out[k] = st.get_editor_property(k)
        except Exception:
            pass
    return out
