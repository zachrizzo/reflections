"""Builds the four parametric Niagara systems used by crafted spells (run inside the UE 5.9 editor via the MCP
execute_python tool; ARGS, prepended by the runner, selects body, burst, arc, field or all).

Every crafted spell drives the same four systems through User.* parameters that C++ fills from the recipe's
seeded look (UReflectionsCraftedSpellSubsystem::ApplyLook): a three-colour ramp, a shape (0 sphere, 1 ring,
2 helix, 3 star, 4 shards, 5 spiral; fractions blend), density, size and motion (swirl, jitter, turbulence,
pulse, gravity). Materials are the spell core's shared sprite materials, used read-only.
The Builder below follows Tools/SpellVFX/build_spell_niagara.py.

Run fixup_crafted_niagara.py as a separate call afterwards: systems built from scratch through the toolset can compile
"UpToDate" and still never activate, and only an input edit made after the build has settled fixes them. The fixup
probes each system, repairs the ones that stay Inactive, and saves.
"""
import json

T = 'NiagaraToolsets.NiagaraToolset_System.'
EA = unreal.EditorAssetLibrary
FOLDER = '/Game/SpellCrafting/VFX'
MAT = '/Game/Characters/Hero/SpellVFX/Materials/'
TEMPLATE = '/Niagara/DefaultAssets/Templates/Emitters/'

TYPES = {
    'float': '/Script/Niagara.NiagaraFloat', 'int': '/Script/Niagara.NiagaraInt32', 'bool': '/Script/Niagara.NiagaraBool',
    'vec3': '/Script/CoreUObject.Vector3f', 'pos': '/Script/Niagara.NiagaraPosition', 'color': '/Script/CoreUObject.LinearColor',
    'vec2': '/Script/CoreUObject.Vector2f', 'quat': '/Script/CoreUObject.Quat4f',
}
HLSL = '/Script/NiagaraEditor.NiagaraExt_StackInputData_HlslExpression'
ENUM = '/Script/NiagaraEditor.NiagaraExt_StackInputData_Enum'

RU = 'normalize(float3(rand(2.0f) - 1.0f, rand(2.0f) - 1.0f, rand(2.0f) - 1.0f) + float3(0.0001f, 0.0002f, 0.0003f))'
NA = 'Particles.NormalizedAge'
TAU = '6.2832f'


def rl(a, b):
    return 'lerp(%sf, %sf, rand(1.0f))' % (float(a), float(b))


def obj(path):
    return unreal.load_object(None, path)


def ty(name):
    return {'classStructOrEnum': obj(TYPES[name])}


def hl(expr):
    return {'struct': obj(HLSL), 'value': {'hlslExpression': expr}}


# ------------------------------------------------------------------------------------------------ shapes
def shape_home():
    """Unit-scale point on the recipe's shape; x is the spell's travel axis. Needs Particles.U, V, Phase."""
    u, v = 'Particles.U', 'Particles.V'
    star_a = '(floor(%s * User.Spikes) / max(User.Spikes, 1.0f) * %s)' % (u, TAU)
    star_r = 'pow(%s, 0.6f)' % v
    helix_a = '(%s * 18.85f + step(0.5f, %s) * 3.1416f)' % (u, v)
    spiral_t = v
    spiral_a = '(floor(%s * 3.0f) * 2.0944f + %s * 7.0f)' % (u, spiral_t)
    shapes = [
        RU,
        'float3((%s - 0.5f) * 0.15f, cos(Particles.Phase), sin(Particles.Phase))' % v,
        'float3((%s * 2.0f - 1.0f) * 1.4f, cos(%s) * 0.6f, sin(%s) * 0.6f)' % (u, helix_a, helix_a),
        'float3((%s - 0.5f) * 0.25f, cos(%s) * %s, sin(%s) * %s)' % (v, star_a, star_r, star_a, star_r),
        '((%s < 0.3333f ? float3(sign(%s - 0.5f), rand(2.0f) - 1.0f, rand(2.0f) - 1.0f) : (%s < 0.6667f ? '
        'float3(rand(2.0f) - 1.0f, sign(%s - 0.5f), rand(2.0f) - 1.0f) : float3(rand(2.0f) - 1.0f, rand(2.0f) - 1.0f, sign(%s - 0.5f)))) * 0.75f)'
        % (u, v, u, v, v),
        'float3(sin(%s * 9.0f) * 0.15f, cos(%s) * %s, sin(%s) * %s)' % (spiral_t, spiral_a, spiral_t, spiral_a, spiral_t),
    ]
    terms = ['(%s) * saturate(1.0f - abs(User.Shape - %d.0f))' % (s, i) for i, s in enumerate(shapes)]
    return '(' + ' + '.join(terms) + ')'


def rot_x(vec, angle):
    """Rotates a float3 attribute expression about the travel axis."""
    return ('float3({v}.x, {v}.y * cos({a}) - {v}.z * sin({a}), {v}.y * sin({a}) + {v}.z * cos({a}))'
            .format(v=vec, a=angle))


def ground(vec):
    """Lays a shape-space point flat on the ground: shape y,z become world x,y, shape x becomes a little height."""
    return 'float3({v}.y, {v}.z, abs({v}.x) * 0.2f)'.format(v=vec)


PULSE = '(1.0f + 0.12f * sin(Engine.Time * User.Pulse * 6.2832f))'

# Spawn expressions carry a per-build salt with no visible effect, so each build is a fresh compile.
import time as _time
SALT = int(_time.time()) % 1000000


def salted(expr, integer=False):
    if integer:
        return '(%s + (int)(0.0000001f * %d.0f))' % (expr, SALT)
    return '(%s + 0.0000001f * %d.0f)' % (expr, SALT)


class Builder:
    def __init__(self, system):
        self.S = system
        self.log = []

    def ref(self, em, script=None, module=None, inp=None, renderer=-1):
        r = {'system': self.S, 'emitterName': em}
        if script:
            r['scriptName'] = script
        if module:
            r['moduleName'] = module
        if inp:
            r['inputNameStack'] = [inp]
        if renderer >= 0:
            r['rendererIndex'] = renderer
        return r

    async def emitter(self, name, template='Minimal', local=False, loop=None):
        await call_tool(T + 'AddEmitter', system=self.S, templateEmitter=unreal.load_asset(TEMPLATE + template), emitterName=name)
        await call_tool(T + 'SetEmitterData', emitterRef=self.ref(name),
                        emitterData={'propertyValues': json.dumps({'bLocalSpace': bool(local), 'SimTarget': 'CPUSim'})})
        await self.enum(name, 'EmitterUpdateScript', 'EmitterState', 'Life Cycle Mode',
                        '/Niagara/Enums/ENiagaraEmitterLifeCycleMode.ENiagaraEmitterLifeCycleMode', 'NewEnumerator1')
        if loop is None:
            await self.enum(name, 'EmitterUpdateScript', 'EmitterState', 'Loop Behavior',
                            '/Niagara/Enums/ENiagara_EmitterStateOptions.ENiagara_EmitterStateOptions', 'NewEnumerator0')
        else:
            await self.enum(name, 'EmitterUpdateScript', 'EmitterState', 'Loop Behavior',
                            '/Niagara/Enums/ENiagara_EmitterStateOptions.ENiagara_EmitterStateOptions', 'NewEnumerator1')
            await self.value(name, 'EmitterUpdateScript', 'EmitterState', 'Loop Duration', 'float', float(loop))
        return name

    async def enum(self, em, script, module, inp, enum_path, enum_name):
        e = obj(enum_path)
        short = enum_path.split('.')[-1]
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp),
                        inputData={'struct': obj(ENUM), 'value': {'enum': e, 'enumName': '%s::%s' % (short, enum_name)}})

    async def value(self, em, script, module, inp, kind, v):
        struct = obj(TYPES[kind])
        payload = {'value': v} if kind in ('float', 'int', 'bool') else v
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp),
                        inputData={'struct': struct, 'value': payload})

    async def expr(self, em, script, module, inp, e):
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp), inputData=hl(e))

    async def module(self, em, script, path):
        m = await call_tool(T + 'AddModule', moduleLocationRef=self.ref(em, script), moduleAsset=unreal.load_asset(path))
        return m['moduleName']

    async def setp(self, em, script, entries):
        m = await call_tool(T + 'AddSetParametersModule', moduleLocationRef=self.ref(em, script),
                            parameters=[{'variable': {'name': a, 'type': ty(k)}} for a, k, _ in entries])
        for a, _, e in entries:
            await self.expr(em, script, m['moduleName'], a, e)
        return m['moduleName']

    async def rate(self, em, rate_expr):
        m = await self.module(em, 'EmitterUpdateScript', '/Niagara/Modules/Emitter/SpawnRate')
        await self.expr(em, 'EmitterUpdateScript', m, 'SpawnRate', salted(rate_expr))
        self.first_spawn = getattr(self, 'first_spawn', None) or (em, m, 'SpawnRate', rate_expr, False)

    async def burst(self, em, count_expr, time=0.0):
        m = await self.module(em, 'EmitterUpdateScript', '/Niagara/Modules/Emitter/SpawnBurst_Instantaneous')
        await self.expr(em, 'EmitterUpdateScript', m, 'Spawn Count', salted(count_expr, integer=True))
        self.first_spawn = getattr(self, 'first_spawn', None) or (em, m, 'Spawn Count', count_expr, True)
        if time:
            await self.value(em, 'EmitterUpdateScript', m, 'Spawn Time', 'float', float(time))

    async def gravity(self, em, vec_expr):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Update/Forces/GravityForce')
        await self.expr(em, 'ParticleUpdateScript', m, 'Gravity', vec_expr)

    async def drag(self, em, amount):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Update/Forces/Drag')
        await self.value(em, 'ParticleUpdateScript', m, 'Drag', 'float', float(amount))

    async def curl(self, em, strength_expr):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Update/Forces/V2/CurlNoiseForce')
        await self.expr(em, 'ParticleUpdateScript', m, 'Noise Strength', strength_expr)

    async def solve(self, em):
        await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Solvers/SolveForcesAndVelocity')

    async def renderer(self, em, props, index=0):
        await call_tool(T + 'SetRendererData', rendererRef=self.ref(em, renderer=index),
                        rendererData={'propertyValues': json.dumps(props)})

    async def replace_renderer(self, em, cls):
        await call_tool(T + 'RemoveRenderer', rendererRef=self.ref(em, renderer=0))
        r = await call_tool(T + 'AddRenderer', newRendererLocation=self.ref(em), rendererClass=unreal.load_class(None, '/Script/Niagara.' + cls))
        return r['rendererIndex']

    async def sprite(self, em, material, alignment='Unaligned', facing='FaceCamera', sort='None'):
        await self.renderer(em, {'material': {'refPath': MAT + material + '.' + material}, 'alignment': alignment,
                                 'facingMode': facing, 'sortMode': sort})

    async def light(self, em):
        idx = await self.replace_renderer(em, 'NiagaraLightRendererProperties')
        await self.renderer(em, {'bUseInverseSquaredFalloff': False, 'bAffectsTranslucency': True, 'radiusScale': 1.0}, idx)
        await self.renderer(em, {'defaultExponent': 2.0}, idx)

    async def shape_attrs(self, em):
        """U, V and Phase first, then Home: a point on the recipe's shape."""
        await self.setp(em, 'ParticleSpawnScript', [
            ('Particles.U', 'float', 'rand(1.0f)'), ('Particles.V', 'float', 'rand(1.0f)'), ('Particles.Phase', 'float', 'rand(6.2832f)')])
        await self.setp(em, 'ParticleSpawnScript', [('Particles.Home', 'vec3', shape_home())])


COMMON = [
    ('ColorA', 'color', (0.7, 0.3, 1.0, 1.0)), ('ColorB', 'color', (0.95, 0.8, 1.0, 1.0)), ('ColorC', 'color', (0.15, 0.05, 0.25, 1.0)),
    ('Shape', 'float', 0.0), ('Density', 'float', 1.0), ('Size', 'float', 30.0), ('Swirl', 'float', 1.0), ('Jitter', 'float', 0.0),
    ('Turbulence', 'float', 120.0), ('Pulse', 'float', 0.5), ('Spikes', 'float', 5.0), ('Glow', 'float', 1.0), ('Gravity', 'float', 0.0),
    ('Scale', 'float', 1.0), ('Intensity', 'float', 1.0),
]


async def new_system(name, users):
    path = FOLDER + '/' + name
    EA.make_directory(FOLDER)
    if EA.does_asset_exist(path):
        EA.delete_asset(path)
    await call_tool(T + 'CreateNiagaraSystem', assetName=name, assetPath=FOLDER,
                    templateSystem=unreal.load_asset('/Niagara/DefaultAssets/DefaultSystem'))
    s = EA.load_asset(path)
    await call_tool(T + 'RemoveEmitter', emitterRef={'system': s, 'emitterName': 'Fountain'})
    variables = []
    for n, kind, default in COMMON + users:
        if kind == 'float':
            dv = {'struct': obj(TYPES['float']), 'value': {'value': float(default)}}
        elif kind == 'color':
            dv = {'struct': obj('/Script/CoreUObject.LinearColor'), 'value': dict(zip('rgba', default))}
        elif kind == 'pos':
            dv = {'struct': obj('/Script/CoreUObject.Vector'), 'value': dict(zip('xyz', default))}
        else:
            dv = {'struct': obj('/Script/CoreUObject.Vector'), 'value': dict(zip('xyz', default))}
            kind = 'vec3'
        variables.append({'name': 'User.' + n, 'type': ty(kind), 'defaultValue': dv})
    await call_tool(T + 'AddUserVariables', system=s, variablesToAdd=variables)
    return Builder(s)


# ------------------------------------------------------------------------------------------------ body
async def build_body():
    """Rides on projectiles, satellites, mines and fuses (attached, local X = travel direction)."""
    b = await new_system('NS_Crafted_Body', [('Light', 'float', 1.0)])
    e = await b.emitter('Core', local=True)
    await b.rate(e, '40.0f * User.Density')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.15f'),
        ('Particles.Position', 'pos', RU + ' * User.Jitter * 0.3f * rand(1.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Size * User.Scale * ' + rl(0.8, 1.2)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorB.rgb * 6.0f * User.Glow * User.Intensity * %s * (1.0f - %s), 1.0f)' % (PULSE, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    # Shell: the recipe's silhouette, spinning about the travel axis.
    e = await b.emitter('Shell', local=True)
    await b.rate(e, '170.0f * User.Density')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.3, 0.6)),
        ('Particles.BaseSize', 'float', rl(2.0, 5.5))])
    await b.shape_attrs(e)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', '%s * User.Size * 1.6f * User.Scale * %s + %s * User.Jitter * rand(1.0f)'
         % (rot_x('Particles.Home', 'Engine.Time * User.Swirl'), PULSE, RU)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * sqrt(User.Scale) * (1.0f - %s * 0.5f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorB.rgb * 5.0f, User.ColorA.rgb * 3.0f, %s) * User.Glow * User.Intensity '
         '* (0.7f + 0.3f * sin(Engine.Time * User.Pulse * 6.2832f + Particles.Phase)), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # Ribbon trail in world space.
    e = await b.emitter('Trail', template='LocationBasedRibbon')
    await b.rate(e, '110.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.3f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + ' + RU + ' * User.Jitter * rand(1.0f)'),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.RibbonWidth', 'float', 'User.Size * 0.55f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.RibbonWidth', 'float', 'User.Size * 0.55f * User.Scale * pow(1.0f - %s, 0.8f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorA.rgb * 3.5f, User.ColorC.rgb * 2.0f, %s) * User.Intensity * pow(1.0f - %s, 1.4f), 1.0f)' % (NA, NA))])
    await b.renderer(e, {'material': {'refPath': MAT + 'M_Spell_Ribbon.M_Spell_Ribbon'}})
    # Motes shed into the world, with the recipe's gravity and turbulence.
    e = await b.emitter('Motes')
    await b.rate(e, '75.0f * User.Density * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.4, 1.0)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * User.Size * 0.7f * User.Scale' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s + Engine.Owner.Velocity * 0.1f' % (RU, rl(30, 150))),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * sqrt(User.Scale) * ' + rl(2.0, 6.0))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -User.Gravity)')
    await b.drag(e, 1.6)
    await b.curl(e, 'User.Turbulence')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(lerp(User.ColorA.rgb * 4.0f, User.ColorC.rgb * 1.5f, %s) * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light', local=True)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '1000.0f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.LightRadius', 'float', '260.0f * User.Scale * clamp(User.Size / 30.0f, 0.6f, 2.5f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 14.0f * User.Glow * User.Intensity * User.Light * %s, 1.0f)' % PULSE)])
    await b.light(e)
    return b


# ------------------------------------------------------------------------------------------------ burst
async def build_burst():
    """Payload detonation, shaped by the recipe. World space, one shot."""
    b = await new_system('NS_Crafted_Burst', [('Normal', 'vec3', (0.0, 0.0, 1.0)), ('Radius', 'float', 200.0)])
    up = 'User.Normal'
    tan = 'normalize(cross(%s, float3(0.31f, 0.71f, 0.63f)))' % up
    bit = 'cross(%s, %s)' % (up, tan)
    to_world = '(Particles.Home.x * {n} + Particles.Home.y * {t} + Particles.Home.z * {b})'.format(n=up, t=tan, b=bit)
    e = await b.emitter('Flash', loop=0.2)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.12f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 10.0f' % up),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * lerp(0.7f, 1.5f, %s) * max(User.Radius, 60.0f) * 1.3f' % NA),
        ('Particles.Color', 'color', 'float4(User.ColorB.rgb * 12.0f * User.Glow * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # The shape itself, thrown outward so the blast reads as a ring, star, spiral or helix.
    e = await b.emitter('Shaped', loop=0.2)
    await b.burst(e, '(int)(110.0f * User.Density * clamp(sqrt(User.Scale), 0.4f, 2.0f) + 12.0f)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.45, 0.9)),
        ('Particles.BaseSize', 'float', rl(3.0, 7.5))])
    await b.shape_attrs(e)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 6.0f' % up),
        ('Particles.Velocity', 'vec3', '%s * max(User.Radius, 60.0f) * %s + %s * 40.0f' % (to_world, rl(2.6, 3.6), up))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -User.Gravity)')
    await b.drag(e, 3.2)
    await b.curl(e, 'User.Turbulence * 0.6f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * sqrt(max(User.Scale, 0.3f)) * (1.0f - %s * 0.6f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(lerp(User.ColorB.rgb * 9.0f, User.ColorA.rgb * 4.0f, saturate(%s * 2.0f)), User.ColorC.rgb * 1.5f, '
         'saturate(%s * 2.0f - 1.0f)) * User.Glow * (1.0f - %s), 1.0f)' % (NA, NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Ring', loop=0.5)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.42f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 4.0f' % up),
        ('Particles.SpriteFacing', 'vec3', up),
        ('Particles.SpriteAlignment', 'vec3', tan)])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * lerp(40.0f, max(User.Radius, 60.0f) * 2.3f, 1.0f - pow(1.0f - %s, 3.0f))' % NA),
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 5.0f * User.Glow * pow(1.0f - %s, 1.5f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Shock', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Sparks', loop=0.2)
    await b.burst(e, '(int)(45.0f * User.Density * clamp(sqrt(User.Scale), 0.3f, 1.6f))')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.3, 0.8)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 6.0f' % up),
        ('Particles.Velocity', 'vec3', 'normalize(%s + %s * 1.2f) * %s * sqrt(max(User.Scale, 0.3f))' % (RU, up, rl(300, 1100))),
        ('Particles.SparkW', 'float', rl(1.5, 3.2))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -900.0f - User.Gravity)')
    await b.drag(e, 2.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(Particles.SparkW, Particles.SparkW + length(Particles.Velocity) * 0.035f)'),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorB.rgb * 10.0f, User.ColorA.rgb * 4.0f, %s) * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Haze', loop=0.2)
    await b.burst(e, '(int)(6.0f * User.Density + 2.0f)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.6)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 0.3f * max(User.Radius, 60.0f) + %s * 15.0f' % (RU, up)),
        ('Particles.Velocity', 'vec3', '(%s * 50.0f + %s * 70.0f)' % (RU, up)),
        ('Particles.BaseSize', 'float', rl(0.35, 0.7) + ' * max(User.Radius, 60.0f)'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 2.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 1.2f)' % NA),
        ('Particles.Color', 'color', 'float4(User.ColorC.rgb * 1.2f, 0.45f * (1.0f - %s) * saturate(Particles.Age * 6.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    e = await b.emitter('Light', loop=0.5)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.4f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 40.0f' % up),
        ('Particles.LightRadius', 'float', 'max(User.Radius, 60.0f) * 2.6f')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 40.0f * User.Glow * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.light(e)
    return b


# ------------------------------------------------------------------------------------------------ arc
async def build_arc():
    """A jagged beam between User.Start and User.End: rays, chain arcs, storm-eye arcs."""
    b = await new_system('NS_Crafted_Arc', [('Start', 'pos', (0.0, 0.0, 0.0)), ('End', 'pos', (100.0, 0.0, 0.0)), ('Length', 'float', 100.0)])
    axis = 'normalize(User.End - User.Start + float3(0.001f, 0.0f, 0.0f))'
    e = await b.emitter('Bolt')
    await b.rate(e, 'clamp(User.Length * 0.9f + 80.0f, 80.0f, 4000.0f)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.05, 0.12)),
        ('Particles.U', 'float', 'rand(1.0f)'),
        ('Particles.Position', 'pos', 'lerp(User.Start, User.End, Particles.U) + %s * (User.Jitter * 1.5f + 3.0f) * rand(1.0f) * sin(Particles.U * 3.1416f)' % RU),
        ('Particles.Velocity', 'vec3', '%s + %s * 0.35f * saturate(User.Jitter / 8.0f)' % (axis, RU)),
        ('Particles.SpriteSize', 'vec2', 'float2(%s + User.Size * 0.12f, %s) * sqrt(max(User.Scale, 0.3f))' % (rl(1.5, 3.0), rl(25, 70)))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorB.rgb * 12.0f * User.Glow * User.Intensity * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Halo')
    await b.rate(e, 'clamp(User.Length * 0.12f + 10.0f, 10.0f, 600.0f)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.12, 0.22)),
        ('Particles.Position', 'pos', 'lerp(User.Start, User.End, rand(1.0f))'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * (User.Size * 1.4f + 20.0f) * ' + rl(0.7, 1.3)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 2.2f * User.Intensity * sin(%s * 3.1416f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Sparks')
    await b.rate(e, '45.0f * User.Density')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.2, 0.5)),
        ('Particles.Position', 'pos', 'User.End + %s * 8.0f' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s' % (RU, rl(150, 600))),
        ('Particles.SparkW', 'float', rl(1.2, 2.5))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -900.0f)')
    await b.drag(e, 1.5)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(Particles.SparkW, Particles.SparkW + length(Particles.Velocity) * 0.03f)'),
        ('Particles.Color', 'color', 'float4(User.ColorB.rgb * 8.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    return b


# ------------------------------------------------------------------------------------------------ field
async def build_field():
    """Ground fields: nova/rune/aura circles, rain clouds, gravity vortices, hazard pools. Attached at the anchor."""
    b = await new_system('NS_Crafted_Field', [('Radius', 'float', 300.0), ('Rain', 'float', 0.0), ('Height', 'float', 0.0),
                                              ('Pull', 'float', 0.0), ('Ring', 'float', 1.0)])
    disc = 'float3(cos(Particles.Phase), sin(Particles.Phase), 0.0f) * sqrt(rand(1.0f)) * User.Radius'
    e = await b.emitter('Circle')
    await b.rate(e, '5.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.6f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(0.0f, 0.0f, 3.0f)'),
        ('Particles.SpriteFacing', 'vec3', 'float3(0.0f, 0.0f, 1.0f)'),
        ('Particles.SpriteAlignment', 'vec3', 'float3(cos(Engine.Time * User.Swirl * 0.3f), sin(Engine.Time * User.Swirl * 0.3f), 0.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(0.0f, 0.0f, 3.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(2.0f, 2.0f) * User.Radius * %s' % PULSE),
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 2.2f * User.Ring * User.Intensity * sin(%s * 3.1416f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Ring', alignment='CustomAlignment', facing='CustomFacingVector')
    # Edge motes: swirl around the rim, drawn inward (Pull > 0) or lifted (Pull < 0).
    e = await b.emitter('Edge')
    await b.rate(e, '150.0f * User.Density * clamp(User.Radius / 300.0f, 0.4f, 3.0f) * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.6, 1.2)),
        ('Particles.Phase', 'float', 'rand(6.2832f)')])
    rim = 'float3(cos(Particles.Phase), sin(Particles.Phase), 0.0f)'
    tangent = 'float3(-sin(Particles.Phase), cos(Particles.Phase), 0.0f)'
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * User.Radius * %s + float3(0.0f, 0.0f, rand(10.0f))' % (rim, rl(0.9, 1.0))),
        ('Particles.Velocity', 'vec3', '%s * User.Swirl * 45.0f - %s * max(User.Pull, 0.0f) * %s + float3(0.0f, 0.0f, %s + max(-User.Pull, 0.0f) * %s)'
         % (tangent, rim, rl(150, 380), rl(10, 60), rl(250, 600))),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(3.0, 8.0))])
    await b.curl(e, 'User.Turbulence * 0.4f')
    await b.drag(e, 0.6)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(lerp(User.ColorA.rgb * 4.0f, User.ColorC.rgb, %s) * User.Glow * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    # Fill: the recipe's shape laid flat on the ground, spinning.
    e = await b.emitter('Fill')
    await b.rate(e, '110.0f * User.Density * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.4, 0.9)),
        ('Particles.BaseSize', 'float', rl(3.0, 7.0))])
    await b.shape_attrs(e)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * User.Radius * 0.85f + float3(0.0f, 0.0f, 6.0f + Particles.Age * 30.0f)'
         % ground(rot_x('Particles.Home', 'Engine.Time * User.Swirl * 0.6f'))),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorB.rgb * 5.0f, User.ColorA.rgb * 2.5f, %s) * User.Glow * sin(%s * 3.1416f), 1.0f)' % (NA, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    # Rain: a churning cloud and the streaks falling from it.
    e = await b.emitter('Cloud')
    await b.rate(e, '45.0f * User.Rain * User.Density * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(1.0, 1.8)),
        ('Particles.Phase', 'float', 'rand(6.2832f)')])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 1.1f + float3(0.0f, 0.0f, User.Height) + %s * 40.0f' % (disc, RU)),
        ('Particles.Velocity', 'vec3', '%s * 30.0f' % RU),
        ('Particles.BaseSize', 'float', rl(90, 170) + ' * clamp(User.Radius / 350.0f, 0.6f, 2.0f)'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (0.8f + %s * 0.4f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorC.rgb * 1.5f, User.ColorA.rgb * 0.8f, 0.3f), 0.55f * sin(%s * 3.1416f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    e = await b.emitter('Drops')
    await b.rate(e, '140.0f * User.Rain * User.Density * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', 'max(User.Height, 100.0f) / 1700.0f'),
        ('Particles.Phase', 'float', 'rand(6.2832f)')])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s + float3(0.0f, 0.0f, User.Height)' % disc),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, -1700.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s)' % (rl(2.0, 3.5), rl(45, 90)))])
    await b.solve(e)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.ColorB.rgb * 5.0f * User.Glow, 1.0f)')])
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    # Vortex: spiralling in (gravity) or up (updraft).
    e = await b.emitter('Vortex')
    await b.rate(e, '120.0f * abs(User.Pull) * User.Density * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.4)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(0.9, 1.4) + ' * User.Radius'),
        ('Particles.Rise', 'float', rl(40, 260)),
        ('Particles.BaseSize', 'float', rl(3.0, 7.0))])
    angle = '(Particles.Phase + Particles.Age * (3.0f + abs(User.Swirl)) * sign(User.Swirl + 0.001f))'
    radius = '(Particles.Rad * lerp(1.0f, step(0.0f, User.Pull) * 0.08f + step(User.Pull, -0.01f) * 0.35f, %s))' % NA
    height = '(Particles.Rise * lerp(1.0f, step(0.0f, User.Pull) * 0.15f + step(User.Pull, -0.01f) * 3.0f, %s))' % NA
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(cos({a}) * {r}, sin({a}) * {r}, {h})'.format(a=angle, r=radius, h=height)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(lerp(User.ColorA.rgb * 4.0f, User.ColorB.rgb * 6.0f, %s) * User.Glow * sin(%s * 3.1416f), 1.0f)' % (NA, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light')
    await b.rate(e, '6.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.45f'),
        ('Particles.LightRadius', 'float', 'User.Radius * 1.6f + 150.0f')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(0.0f, 0.0f, 90.0f + User.Height * 0.5f)'),
        ('Particles.Color', 'color', 'float4(User.ColorA.rgb * 5.0f * User.Glow * User.Intensity * sin(%s * 3.1416f), 1.0f)' % NA)])
    await b.light(e)
    return b


async def finish(b):
    s = b.S
    # A system built from scratch through the toolset can compile "UpToDate" yet never activate at runtime (found
    # 2026-11-14: NS_Crafted_Body/Field, and the spell core's NS_Spell_* systems, stayed Inactive in the very frame they
    # spawned). One more input edit after the build, which forces a full recompile, makes them run, so re-set the
    # first spawn expression and verify below by spawning the system and checking it activates.
    em, module, inp, expr, integer = b.first_spawn
    await b.expr(em, 'EmitterUpdateScript', module, inp, salted('(%s)' % expr, integer))
    for _ in range(240):
        cs = await call_tool(T + 'GetSystemCompileState', system=s)
        if not cs['bIsCompiling']:
            break
        await asyncio.sleep(0.25)
    cs = json.loads(json.dumps(cs, default=str))
    errors = [(x['emitterName'], x['scriptName'], x['errorSummary'][:600]) for x in cs['scripts'] if x['errorSummary']]
    issues = await call_tool(T + 'GetStackIssues', system=s)
    issues = json.loads(json.dumps(issues, default=str))
    EA.save_loaded_asset(s, False)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    probe = unreal.NiagaraFunctionLibrary.spawn_system_at_location(world, s, unreal.Vector(0, 0, -5000), unreal.Rotator(0, 0, 0),
                                                                   unreal.Vector(1, 1, 1), False, True)
    await asyncio.sleep(0.5)
    active = bool(probe and probe.is_active())
    if probe:
        probe.destroy_component(probe)
    return {'system': s.get_path_name(), 'status': cs['aggregateStatus'], 'activates': active, 'errors': errors, 'log': b.log,
            'issues': str(issues)[:3000]}


if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
    raise RuntimeError('PIE is running; Niagara assets cannot be edited now.')
which = ARGS or ['all']
builders = {'body': build_body, 'burst': build_burst, 'arc': build_arc, 'field': build_field}
results = []
for key, fn in builders.items():
    if 'all' in which or key in which:
        results.append(await finish(await fn()))
RESULT = json.dumps(results, indent=1)
RESULT
