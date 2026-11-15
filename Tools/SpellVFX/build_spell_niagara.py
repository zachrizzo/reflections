"""Builds the parametric spell Niagara systems (run inside the Unreal 5.9 editor via its MCP Python tool).

ARGS (prepended by the runner) selects systems: projectile, impact, heal, ward, tarnish_bolt, tarnish_burst, shock, bodyfx, or all.
Every look is driven by User.* parameters that C++ (UReflectionsSpellVfxSubsystem) sets per element,
so six elements share three attack systems instead of eighteen one-off assets.

Shading lives in build_spell_materials.py. Motion, colour and size curves are HLSL expressions in
SetParameters modules, which keeps every curve readable here rather than hidden in module defaults.
"""
import json
import re

T = 'NiagaraToolsets.NiagaraToolset_System.'
EA = unreal.EditorAssetLibrary
FOLDER = '/Game/Characters/Hero/SpellVFX/Systems'
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


def rl(a, b):
    return 'lerp(%sf, %sf, rand(1.0f))' % (float(a), float(b))


def obj(path):
    return unreal.load_object(None, path)


def ty(name):
    return {'classStructOrEnum': obj(TYPES[name])}


def vm_safe(expr):
    """The CPU Vector VM has no smoothstep(); expand it to t*t*(3-2t) with t = saturate((x-a)/(b-a))."""
    def expand(m):
        a, b, x = (g.strip() for g in m.groups())
        t = 'saturate((%s - %s) / (%s - %s))' % (x, a, b, a)
        return '(%s * %s * (3.0f - 2.0f * %s))' % (t, t, t)
    return re.sub(r'smoothstep\(\s*([^,()]+),\s*([^,()]+),\s*([^,()]+)\)', expand, expr)


def hl(expr):
    return {'struct': obj(HLSL), 'value': {'hlslExpression': vm_safe(expr)}}


def quat_spin(rate_expr):
    """Incrementally rotates Particles.MeshOrientation about Particles.SpinAxis (single rvalue)."""
    h = '(%s * Engine.DeltaTime * 0.5f)' % rate_expr
    q = 'Particles.MeshOrientation'
    s = '(Particles.SpinAxis * sin(%s))' % h
    return ('normalize(float4(cos({h}) * {q}.xyz + {q}.w * {s} + cross({s}, {q}.xyz), '
            'cos({h}) * {q}.w - dot({s}, {q}.xyz)))').format(h=h, q=q, s=s)


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
        # Each emitter owns its lifetime: Once for bursts and timed spawns, Infinite while attached and alive.
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
        m = await call_tool(T + 'AddModule', moduleLocationRef=self.ref(em, script),
                            moduleAsset=unreal.load_asset(path))
        return m['moduleName']

    async def setp(self, em, script, entries):
        m = await call_tool(T + 'AddSetParametersModule', moduleLocationRef=self.ref(em, script),
                            parameters=[{'variable': {'name': a, 'type': ty(k)}} for a, k, _ in entries])
        for a, _, e in entries:
            await self.expr(em, script, m['moduleName'], a, e)
        return m['moduleName']

    async def rate(self, em, rate_expr):
        m = await self.module(em, 'EmitterUpdateScript', '/Niagara/Modules/Emitter/SpawnRate')
        await self.expr(em, 'EmitterUpdateScript', m, 'SpawnRate', rate_expr)

    async def burst(self, em, count_expr, time=0.0):
        m = await self.module(em, 'EmitterUpdateScript', '/Niagara/Modules/Emitter/SpawnBurst_Instantaneous')
        await self.expr(em, 'EmitterUpdateScript', m, 'Spawn Count', count_expr)
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

    async def collide(self, em, restitution, friction, rest=True):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Collision/Collision')
        for inp, kind, v in (('Restitution', 'float', float(restitution)), ('Friction', 'float', float(friction)),
                             ('Enable Rest State', 'bool', -1 if rest else 0)):
            try:
                await self.value(em, 'ParticleUpdateScript', m, inp, kind, v)
            except Exception as ex:  # Hidden behind a switch: keep the module default.
                self.log.append('collision %s.%s: %s' % (em, inp, str(ex)[:160]))

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


async def new_system(name, users):
    path = FOLDER + '/' + name
    EA.make_directory(FOLDER)
    try:
        await call_tool('EditorToolset.EditorAppToolset.CloseEditorForAsset', assetPath=path, unsavedChanges='Discard')
    except Exception:
        pass
    if EA.does_asset_exist(path):
        EA.delete_asset(path)
    await call_tool(T + 'CreateNiagaraSystem', assetName=name, assetPath=FOLDER,
                    templateSystem=unreal.load_asset('/Niagara/DefaultAssets/DefaultSystem'))
    s = EA.load_asset(path)
    await call_tool(T + 'RemoveEmitter', emitterRef={'system': s, 'emitterName': 'Fountain'})
    variables = []
    for n, kind, default in users:
        if kind == 'float':
            dv = {'struct': obj(TYPES['float']), 'value': {'value': float(default)}}
        elif kind == 'color':
            dv = {'struct': obj('/Script/CoreUObject.LinearColor'), 'value': dict(zip('rgba', default))}
        else:
            dv = {'struct': obj('/Script/CoreUObject.Vector'), 'value': dict(zip('xyz', default))}
            kind = 'vec3'
        variables.append({'name': 'User.' + n, 'type': ty(kind), 'defaultValue': dv})
    await call_tool(T + 'AddUserVariables', system=s, variablesToAdd=variables)
    return Builder(s)


# ----------------------------------------------------------------------------------------------- projectile
async def build_projectile():
    b = await new_system('NS_Spell_Projectile', [
        ('Color', 'color', (1.0, 0.32, 0.05, 1.0)), ('Color2', 'color', (1.0, 0.82, 0.45, 1.0)), ('Scale', 'float', 1.0),
        ('CoreSize', 'float', 34.0), ('SparkRate', 'float', 70.0), ('SparkGravity', 'float', 160.0), ('Jitter', 'float', 0.0),
        ('Swirl', 'float', 0.0), ('Turbulence', 'float', 250.0), ('ArcRate', 'float', 0.0), ('TrailWidth', 'float', 18.0)])
    # Hot core: a flickering white-hot centre that stays on the projectile.
    e = await b.emitter('Core', local=True)
    await b.rate(e, '45.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.14f'),
        ('Particles.Position', 'pos', RU + ' * User.Jitter * 0.25f * rand(1.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.CoreSize * User.Scale * ' + rl(0.75, 1.25)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 7.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # Coloured halo around the core.
    e = await b.emitter('Halo', local=True)
    await b.rate(e, '22.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.22f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.CoreSize * 2.8f * User.Scale * ' + rl(0.85, 1.15))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 2.2f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # Ribbon trail in world space; jitter turns it into a crackling bolt for lightning.
    e = await b.emitter('Trail', template='LocationBasedRibbon')
    await b.rate(e, '150.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.32f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + ' + RU + ' * User.Jitter * rand(1.0f)'),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.RibbonWidth', 'float', 'User.TrailWidth * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.RibbonWidth', 'float', 'User.TrailWidth * User.Scale * pow(1.0f - %s, 0.7f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 5.0f, User.Color.rgb * 2.5f, saturate(%s * 3.0f)) * pow(1.0f - %s, 1.5f), 1.0f)' % (NA, NA))])
    await b.renderer(e, {'material': {'refPath': MAT + 'M_Spell_Ribbon.M_Spell_Ribbon'}})
    # Embers / droplets / frost dust shed from the projectile, with real forces.
    e = await b.emitter('Embers')
    await b.rate(e, 'User.SparkRate')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.35, 0.85)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 8.0f * User.Scale' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s + Engine.Owner.Velocity * 0.12f' % (RU, rl(40, 170))),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * ' + rl(2.5, 6.5))])
    await b.gravity(e, 'float3(0.0f, 0.0f, User.SparkGravity)')
    await b.drag(e, 1.6)
    await b.curl(e, 'User.Turbulence')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 6.0f, User.Color.rgb * 3.0f, %s) * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    # Lightning: short arcs that snap around the bolt.
    e = await b.emitter('Arcs', local=True)
    await b.rate(e, 'User.ArcRate')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.05, 0.12)),
        ('Particles.Position', 'pos', '%s * %s * User.Scale' % (RU, rl(4, 22))),
        ('Particles.Velocity', 'vec3', RU),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s) * User.Scale' % (rl(1.5, 3.0), rl(22, 75)))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 14.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    # Arcane / water: motes spiralling in a helix behind the projectile (local X = flight direction).
    e = await b.emitter('Orbit', local=True)
    await b.rate(e, 'User.Swirl')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.5f'),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(14, 26) + ' * User.Scale'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * ' + rl(3.5, 7.0))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(-Particles.Age * 320.0f, cos(Particles.Phase + Particles.Age * 18.0f) * Particles.Rad * (1.0f - %s * 0.5f), sin(Particles.Phase + Particles.Age * 18.0f) * Particles.Rad * (1.0f - %s * 0.5f))' % (NA, NA)),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 6.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # The dynamic light riding the projectile: short-lived light particles respawned continuously, each fading
    # out over its 0.1 s life (about four overlap, summing to a steady glow). When the projectile dies the system
    # is deactivated, spawning stops and the light is gone within 0.1 s. A single long-lived light particle used
    # to outlive Deactivate() and left a coloured light on the ground at every impact.
    e = await b.emitter('Light', local=True)
    await b.rate(e, '40.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.1f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.LightRadius', 'float', '340.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * (10.0f + 3.0f * sin(Engine.Time * 37.0f)) * (1.0f - %s), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- impact
async def build_impact():
    b = await new_system('NS_Spell_Impact', [
        ('Color', 'color', (1.0, 0.32, 0.05, 1.0)), ('Color2', 'color', (1.0, 0.85, 0.5, 1.0)), ('Scale', 'float', 1.0),
        ('Normal', 'vec3', (0.0, 0.0, 1.0)), ('SparkCount', 'float', 60.0), ('SparkGravity', 'float', -980.0),
        ('DebrisCount', 'float', 0.0), ('DebrisColor', 'color', (0.25, 0.2, 0.16, 1.0)), ('DebrisMesh', 'float', 0.0),
        ('SmokeCount', 'float', 8.0), ('SmokeColor', 'color', (0.12, 0.11, 0.1, 0.55)), ('FlameCount', 'float', 0.0),
        ('ArcCount', 'float', 0.0), ('MoteCount', 'float', 24.0), ('Turbulence', 'float', 250.0), ('LightScale', 'float', 1.0)])
    up = 'User.Normal'
    e = await b.emitter('Flash', loop=0.2)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.13f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 10.0f' % up),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        # LightScale is 0.35 for muzzle flashes; keep the hand flash small so it never fills the screen.
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * (0.35f + 0.65f * User.LightScale) * lerp(170.0f, 330.0f, %s)' % NA),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 14.0f * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Shock', loop=0.4)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.38f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 4.0f' % up),
        ('Particles.SpriteFacing', 'vec3', up),
        ('Particles.SpriteAlignment', 'vec3', 'normalize(cross(%s, float3(0.31f, 0.71f, 0.63f)))' % up)])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * User.LightScale * User.LightScale * lerp(40.0f, 560.0f, 1.0f - pow(1.0f - %s, 3.0f))' % NA),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 5.0f * pow(1.0f - %s, 1.5f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Shock', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Sparks', loop=0.2)
    await b.burst(e, '(int)User.SparkCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.35, 0.95)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 6.0f' % up),
        ('Particles.Velocity', 'vec3', 'normalize(%s + %s * 1.3f) * %s * sqrt(User.Scale)' % (RU, up, rl(350, 1150))),
        ('Particles.SparkW', 'float', rl(1.6, 3.6) + ' * sqrt(User.Scale)')])
    await b.gravity(e, 'float3(0.0f, 0.0f, User.SparkGravity)')
    await b.drag(e, 2.2)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(Particles.SparkW, Particles.SparkW + length(Particles.Velocity) * 0.035f)'),
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 10.0f, User.Color.rgb * 4.0f, %s) * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.collide(e, 0.45, 0.2, rest=False)
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Debris', loop=0.2)
    await b.burst(e, '(int)User.DebrisCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(2.6, 4.2)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 10.0f * User.Scale + %s * 8.0f' % (RU, up)),
        ('Particles.Velocity', 'vec3', 'normalize(%s * 0.75f + %s + float3(0.0f, 0.0f, 0.6f)) * %s * sqrt(User.Scale)' % (RU, up, rl(260, 760))),
        ('Particles.BaseScale', 'vec3', 'float3(%s, %s, %s * (1.0f + 2.0f * User.DebrisMesh)) * User.Scale' % (rl(0.035, 0.11), rl(0.035, 0.11), rl(0.035, 0.11))),
        ('Particles.MeshIndex', 'int', '(int)User.DebrisMesh'),
        ('Particles.SpinAxis', 'vec3', RU),
        ('Particles.SpinRate', 'float', rl(4, 15)),
        ('Particles.MeshOrientation', 'quat', 'normalize(float4(%s, rand(2.0f) - 1.0f))' % RU),
        ('Particles.Color', 'color', 'float4(User.DebrisColor.rgb * %s, User.DebrisColor.a)' % rl(0.6, 1.25))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -1250.0f)')
    await b.drag(e, 0.5)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Scale', 'vec3', 'Particles.BaseScale * (1.0f - smoothstep(0.82f, 1.0f, %s))' % NA),
        ('Particles.MeshOrientation', 'quat', quat_spin('Particles.SpinRate * saturate(length(Particles.Velocity) / 150.0f)'))])
    await b.collide(e, 0.3, 0.65, rest=True)
    await b.solve(e)
    meshes = [{'mesh': {'refPath': '/Engine/BasicShapes/Cube.Cube'}}, {'mesh': {'refPath': '/Engine/BasicShapes/Cone.Cone'}}]
    idx = await b.replace_renderer(e, 'NiagaraMeshRendererProperties')
    try:
        await b.renderer(e, {'meshes': meshes, 'bOverrideMaterials': True}, idx)
        await b.renderer(e, {'overrideMaterials': [{'explicitMat': {'refPath': MAT + 'M_Spell_Debris.M_Spell_Debris'}}]}, idx)
    except Exception as ex:
        b.log.append('mesh renderer: %s' % str(ex)[:300])
    e = await b.emitter('Smoke', loop=0.2)
    await b.burst(e, '(int)User.SmokeCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(1.0, 2.1)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 20.0f * User.Scale + %s * 15.0f' % (RU, up)),
        ('Particles.Velocity', 'vec3', '(%s * 60.0f + %s * 90.0f + float3(0.0f, 0.0f, 60.0f)) * sqrt(User.Scale)' % (RU, up)),
        ('Particles.BaseSize', 'float', rl(60, 130) + ' * User.Scale'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 2.0)
    await b.curl(e, 'User.Turbulence * 0.5f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 1.6f)' % NA),
        ('Particles.Color', 'color', 'float4(User.SmokeColor.rgb, User.SmokeColor.a * (1.0f - %s) * saturate(Particles.Age * 6.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    e = await b.emitter('Flames', loop=0.2)
    await b.burst(e, '(int)User.FlameCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.35, 0.85)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 25.0f * User.Scale + %s * 20.0f' % (RU, up)),
        ('Particles.Velocity', 'vec3', '(%s * 180.0f + %s * 200.0f + float3(0.0f, 0.0f, 150.0f)) * sqrt(User.Scale)' % (RU, up)),
        ('Particles.BaseSize', 'float', rl(40, 115) + ' * User.Scale'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.gravity(e, 'float3(0.0f, 0.0f, 260.0f)')
    await b.drag(e, 3.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (0.6f + %s * 0.9f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 8.0f, User.Color.rgb * 3.0f, saturate(%s * 2.0f)) * pow(1.0f - %s, 1.5f), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Arcs', loop=0.25)
    await b.burst(e, '(int)User.ArcCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.06, 0.18)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * %s * User.Scale' % (RU, rl(10, 90))),
        ('Particles.Velocity', 'vec3', RU),
        ('Particles.Phase', 'float', 'rand(1.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s) * User.Scale' % (rl(1.5, 3.5), rl(40, 170)))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 14.0f * (1.0f - %s) * step(0.3f, frac(Particles.Age * 40.0f + Particles.Phase)), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Motes', loop=0.2)
    await b.burst(e, '(int)User.MoteCount')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.9)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * %s * User.Scale' % (RU, rl(5, 45))),
        ('Particles.Velocity', 'vec3', '%s * %s + float3(0.0f, 0.0f, 40.0f)' % (RU, rl(30, 120))),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(2.0, 5.0))])
    await b.curl(e, 'User.Turbulence')
    await b.drag(e, 1.5)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 5.0f * (1.0f - %s) * (0.6f + 0.4f * sin(Particles.Age * 22.0f + Particles.Phase)), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light', loop=0.5)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.45f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 40.0f' % up),
        ('Particles.LightRadius', 'float', '650.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 45.0f * User.LightScale * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- heal
async def build_heal():
    b = await new_system('NS_Spell_Heal', [
        ('Color', 'color', (1.0, 0.72, 0.28, 1.0)), ('Color2', 'color', (0.35, 1.0, 0.5, 1.0)), ('Scale', 'float', 1.0),
        ('Radius', 'float', 0.0)])
    e = await b.emitter('Rune', local=True, loop=2.6)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '2.6f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 3.0f)'),
        ('Particles.SpriteFacing', 'vec3', 'float3(0.0f, 0.0f, 1.0f)'),
        ('Particles.SpriteAlignment', 'vec3', 'float3(1.0f, 0.0f, 0.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * 240.0f * User.Scale * (1.0f - pow(1.0f - saturate(Particles.Age * 2.5f), 3.0f))'),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 3.5f * saturate(Particles.Age * 4.0f) * (1.0f - smoothstep(0.72f, 1.0f, %s)), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Ring', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Spiral', local=True, loop=1.7)
    await b.rate(e, '260.0f * User.Scale')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(1.0, 1.6)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(45, 78) + ' * User.Scale'),
        ('Particles.Rise', 'float', rl(80, 165) + ' * sqrt(User.Scale)'),
        ('Particles.Dir', 'float', 'sign(rand(2.0f) - 1.0f)'),
        ('Particles.BaseSize', 'float', rl(2.5, 6.5) + ' * sqrt(User.Scale)')])
    angle = '(Particles.Phase + Particles.Dir * Particles.Age * (3.0f + Particles.Age * 2.5f))'
    radius = '(Particles.Rad * (1.0f - 0.6f * %s))' % NA
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(cos({a}) * {r}, sin({a}) * {r}, Particles.Age * Particles.Rise + sin(Particles.Age * 6.0f + Particles.Phase) * 5.0f)'.format(a=angle, r=radius)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f - %s * 0.5f)' % NA),
        ('Particles.Color', 'color', 'float4(lerp(User.Color.rgb, User.Color2.rgb, %s) * 7.0f * sin(%s * 3.14159f) * (0.6f + 0.4f * sin(Particles.Age * 25.0f + Particles.Phase * 7.0f)), 1.0f)' % (NA, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Sparkles', loop=1.8)
    await b.rate(e, '110.0f * User.Scale')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.9, 1.9)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(10, 85) + ' * User.Scale'),
        ('Particles.BaseSize', 'float', rl(2.0, 5.0))])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(cos(Particles.Phase) * Particles.Rad, sin(Particles.Phase) * Particles.Rad, rand(190.0f))'),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, %s) + %s * 20.0f' % (rl(20, 70), RU))])
    await b.curl(e, '400.0f')
    await b.drag(e, 1.2)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 6.0f * sin(%s * 3.14159f) * (0.5f + 0.5f * sin(Particles.Age * 30.0f + Particles.Phase * 5.0f)), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Petals', loop=0.5)
    await b.burst(e, '(int)(46.0f * User.Scale)', time=0.25)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(3.2, 4.4)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(10, 50)),
        ('Particles.Mix', 'float', 'rand(1.0f)'),
        ('Particles.BaseSize', 'float', rl(4.0, 8.5))])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(cos(Particles.Phase) * Particles.Rad, sin(Particles.Phase) * Particles.Rad, %s)' % rl(140, 195)),
        ('Particles.Velocity', 'vec3', 'float3(cos(Particles.Phase), sin(Particles.Phase), 0.0f) * %s * sqrt(User.Scale) + float3(0.0f, 0.0f, %s)' % (rl(120, 300), rl(80, 220)))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -420.0f)')
    await b.drag(e, 1.4)
    await b.curl(e, '180.0f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb, User.Color.rgb, Particles.Mix) * 5.0f * (1.0f - smoothstep(0.7f, 1.0f, %s)) * (0.75f + 0.25f * sin(Particles.Age * 9.0f + Particles.Phase)), 1.0f)' % NA)])
    await b.collide(e, 0.25, 0.7, rest=True)
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Streaks', loop=1.2)
    await b.rate(e, '50.0f * User.Scale')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.45, 0.85)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(25, 70) + ' * User.Scale'),
        ('Particles.SparkW', 'float', rl(2.0, 3.5))])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(cos(Particles.Phase) * Particles.Rad, sin(Particles.Phase) * Particles.Rad, rand(40.0f))'),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, %s)' % rl(260, 560))])
    await b.drag(e, 1.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(Particles.SparkW, 20.0f + length(Particles.Velocity) * 0.12f)'),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 6.0f * pow(1.0f - %s, 1.3f), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Pulse', local=True, loop=0.9)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.8f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 6.0f)'),
        ('Particles.SpriteFacing', 'vec3', 'float3(0.0f, 0.0f, 1.0f)'),
        ('Particles.SpriteAlignment', 'vec3', 'float3(1.0f, 0.0f, 0.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * (60.0f + (User.Radius * 2.0f + 300.0f * User.Scale) * (1.0f - pow(1.0f - %s, 3.0f)))' % NA),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 4.0f * pow(1.0f - %s, 1.2f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Shock', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Absorb', local=True, loop=1.3)
    await b.burst(e, '(int)(70.0f * User.Scale)', time=1.1)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.5, 0.8)),
        ('Particles.StartPos', 'vec3', '%s * %s * User.Scale + float3(0.0f, 0.0f, 100.0f)' % (RU, rl(110, 170))),
        ('Particles.BaseSize', 'float', rl(2.5, 5.5))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'lerp(Particles.StartPos, float3(0.0f, 0.0f, 110.0f), %s * %s)' % (NA, NA)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 8.0f * %s, 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light', local=True, loop=2.6)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '2.6f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 110.0f)'),
        ('Particles.LightRadius', 'float', '430.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(lerp(User.Color.rgb, User.Color2.rgb, 0.5f + 0.5f * sin(Particles.Age * 3.0f)) * (14.0f + 6.0f * sin(Particles.Age * 11.0f)) * saturate(Particles.Age * 3.0f) * (1.0f - smoothstep(0.7f, 1.0f, %s)), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- ward
async def build_ward():
    b = await new_system('NS_Spell_Ward', [
        ('Color', 'color', (0.55, 0.3, 1.0, 1.0)), ('Color2', 'color', (0.6, 0.85, 1.0, 1.0)), ('Scale', 'float', 1.0)])
    e = await b.emitter('Rune', local=True, loop=2.2)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '2.2f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 3.0f)'),
        ('Particles.SpriteFacing', 'vec3', 'float3(0.0f, 0.0f, 1.0f)'),
        ('Particles.SpriteAlignment', 'vec3', 'float3(1.0f, 0.0f, 0.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * 260.0f * User.Scale * (1.0f - pow(1.0f - saturate(Particles.Age * 3.0f), 3.0f))'),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 3.5f * (1.0f - smoothstep(0.7f, 1.0f, %s)), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Ring', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Shell', local=True, loop=1.6)
    await b.rate(e, '240.0f * User.Scale')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.6, 1.1)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Theta', 'float', 'acos(rand(2.0f) - 1.0f)'),
        ('Particles.BaseSize', 'float', rl(2.5, 5.0))])
    sphere = 'float3(sin(Particles.Theta) * cos(Particles.Phase + Particles.Age * 2.2f), sin(Particles.Theta) * sin(Particles.Phase + Particles.Age * 2.2f), cos(Particles.Theta))'
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 95.0f) + %s * 120.0f * User.Scale * (0.85f + 0.15f * saturate(Particles.Age * 4.0f))' % sphere),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(lerp(User.Color.rgb, User.Color2.rgb, %s) * 6.0f * sin(%s * 3.14159f), 1.0f)' % (NA, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Pulse', local=True, loop=0.7)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.6f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 95.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * lerp(60.0f, 300.0f, 1.0f - pow(1.0f - %s, 3.0f))' % NA),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 3.0f * pow(1.0f - %s, 1.5f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Shock')
    e = await b.emitter('Light', local=True, loop=2.2)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '2.2f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 100.0f)'),
        ('Particles.LightRadius', 'float', '380.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 16.0f * saturate(Particles.Age * 4.0f) * (1.0f - smoothstep(0.65f, 1.0f, %s)), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- tarnish (enemy magic)
# Tarnished NPCs' magic (UReflectionsTarnishCasterComponent): a black-violet core inside a violet rim, sickly silver
# sparks and a smoke wake that darkens the scene. User.Gather > 0 turns the same system into the wind-up at the hand
# (motes and smoke drawn inward, no wake); User.Wisp > 0 makes the slow homing orb with silver motes circling it.
async def build_tarnish_bolt():
    b = await new_system('NS_Tarnish_Bolt', [
        ('Color', 'color', (0.30, 0.03, 0.55, 1.0)), ('Color2', 'color', (0.66, 0.70, 0.74, 1.0)),
        ('SmokeColor', 'color', (0.025, 0.01, 0.04, 0.82)), ('Scale', 'float', 1.0), ('Gather', 'float', 0.0),
        ('Wisp', 'float', 0.0)])
    flying = '(1.0f - saturate(User.Gather))'
    # Black core: a dark, dense puff that reads as a hole in the light.
    e = await b.emitter('DarkCore', local=True)
    await b.rate(e, '34.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.2f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * 30.0f * User.Scale * (1.0f + 0.5f * User.Wisp) * ' + rl(0.85, 1.15)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(0.006f, 0.002f, 0.012f, 0.95f * (1.0f - %s * %s))' % (NA, NA))])
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    # Violet rim around the core.
    e = await b.emitter('Rim', local=True)
    await b.rate(e, '26.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.22f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * 74.0f * User.Scale * (1.0f + 0.4f * User.Wisp) * ' + rl(0.85, 1.15))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 2.4f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # Smoke wake: dark puffs left behind in world space (none while gathering at the hand).
    e = await b.emitter('Smoke')
    await b.rate(e, '(70.0f + 30.0f * User.Wisp) * %s' % flying)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.5, 0.95)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 6.0f * User.Scale' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s' % (RU, rl(10, 45))),
        ('Particles.BaseSize', 'float', rl(12, 22) + ' * User.Scale'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 2.0)
    await b.curl(e, '140.0f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 2.2f)' % NA),
        ('Particles.Color', 'color', 'float4(User.SmokeColor.rgb, User.SmokeColor.a * (1.0f - %s) * saturate(Particles.Age * 8.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    # Thin violet ribbon through the smoke.
    e = await b.emitter('Trail', template='LocationBasedRibbon')
    await b.rate(e, '140.0f * %s' % flying)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.28f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position'),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.RibbonWidth', 'float', '8.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.RibbonWidth', 'float', '8.0f * User.Scale * pow(1.0f - %s, 0.7f)' % NA),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 1.8f * pow(1.0f - %s, 1.5f), 1.0f)' % NA)])
    await b.renderer(e, {'material': {'refPath': MAT + 'M_Spell_Ribbon.M_Spell_Ribbon'}})
    # Sickly silver sparks that flicker as they fall away.
    e = await b.emitter('Sparks')
    await b.rate(e, '(60.0f + 25.0f * User.Wisp) * (1.0f - 0.5f * saturate(User.Gather))')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.25, 0.6)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 9.0f * User.Scale' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s * User.Scale + Engine.Owner.Velocity * 0.1f' % (RU, rl(60, 220))),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s) * User.Scale' % (rl(1.2, 2.2), rl(5, 12)))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -160.0f)')
    await b.drag(e, 1.5)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 5.0f * (0.45f + 0.55f * sin(Particles.Age * 70.0f + Particles.Phase)) * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    # Wind-up: silver motes and dark wisps spiral into the hand.
    e = await b.emitter('GatherMotes', local=True)
    await b.rate(e, '75.0f * saturate(User.Gather)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.35, 0.55)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(45, 95) + ' * (0.6f + User.Scale)'),
        ('Particles.H', 'float', rl(-35, 35)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(2.5, 5.0))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(cos(Particles.Phase + Particles.Age * 9.0f) * Particles.Rad * (1.0f - %s), sin(Particles.Phase + Particles.Age * 9.0f) * Particles.Rad * (1.0f - %s), Particles.H * (1.0f - %s))' % (NA, NA, NA)),
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 4.0f, User.Color.rgb * 5.0f, %s) * saturate(%s * 4.0f), 1.0f)' % (NA, NA))])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('GatherSmoke', local=True)
    await b.rate(e, '28.0f * saturate(User.Gather)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.45, 0.7)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(40, 80) + ' * (0.6f + User.Scale)'),
        ('Particles.H', 'float', rl(-25, 25)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(16, 30))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(cos(Particles.Phase - Particles.Age * 6.0f) * Particles.Rad * (1.0f - %s), sin(Particles.Phase - Particles.Age * 6.0f) * Particles.Rad * (1.0f - %s), Particles.H * (1.0f - %s))' % (NA, NA, NA)),
        ('Particles.Color', 'color', 'float4(User.SmokeColor.rgb, User.SmokeColor.a * 0.8f * saturate(%s * 3.0f) * (1.0f - %s * %s))' % (NA, NA, NA))])
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    # Wisp: silver motes circling the orb in a helix behind it (local X = flight direction).
    e = await b.emitter('WispOrbit', local=True)
    await b.rate(e, '46.0f * saturate(User.Wisp) * %s' % flying)
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.6f'),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(20, 34) + ' * User.Scale'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * ' + rl(3.0, 6.0))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Position', 'pos', 'float3(-Particles.Age * 140.0f, cos(Particles.Phase + Particles.Age * 12.0f) * Particles.Rad, sin(Particles.Phase + Particles.Age * 12.0f) * Particles.Rad)'),
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 5.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    # Riding light: short-lived light particles respawned continuously, so it goes out with the projectile. The
    # caster's own point light carries the wind-up, so this one dims while gathering.
    e = await b.emitter('Light', local=True)
    await b.rate(e, '40.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.1f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.LightRadius', 'float', '300.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * (7.0f + 2.5f * sin(Engine.Time * 23.0f)) * (1.0f - 0.75f * saturate(User.Gather)) * (1.0f - %s), 1.0f)' % NA)])
    await b.light(e)
    return b


async def build_tarnish_burst():
    b = await new_system('NS_Tarnish_Burst', [
        ('Color', 'color', (0.30, 0.03, 0.55, 1.0)), ('Color2', 'color', (0.66, 0.70, 0.74, 1.0)),
        ('SmokeColor', 'color', (0.025, 0.01, 0.04, 0.82)), ('Scale', 'float', 1.0), ('Normal', 'vec3', (0.0, 0.0, 1.0)),
        ('Amount', 'float', 1.0), ('LightScale', 'float', 1.0)])
    up = 'User.Normal'
    # A dark sphere that swells and thins: the light is swallowed before it flares.
    e = await b.emitter('DarkFlash', loop=0.4)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.38f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 12.0f' % up),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * (0.35f + 0.65f * User.Amount) * lerp(50.0f, 230.0f, 1.0f - pow(1.0f - %s, 3.0f))' % NA),
        ('Particles.Color', 'color', 'float4(0.006f, 0.002f, 0.012f, 0.92f * pow(1.0f - %s, 1.5f))' % NA)])
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    e = await b.emitter('Flash', loop=0.2)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.16f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 10.0f' % up),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * (0.35f + 0.65f * User.LightScale) * lerp(140.0f, 280.0f, %s)' % NA),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 9.0f * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Shock', loop=0.45)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.42f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 4.0f' % up),
        ('Particles.SpriteFacing', 'vec3', up),
        ('Particles.SpriteAlignment', 'vec3', 'normalize(cross(%s, float3(0.31f, 0.71f, 0.63f)))' % up)])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Scale * User.Amount * lerp(40.0f, 380.0f, 1.0f - pow(1.0f - %s, 3.0f))' % NA),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 4.0f * pow(1.0f - %s, 1.5f), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Shock', alignment='CustomAlignment', facing='CustomFacingVector')
    e = await b.emitter('Sparks', loop=0.2)
    await b.burst(e, '(int)(55.0f * User.Amount * sqrt(max(User.Scale, 0.3f)))')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.3, 0.85)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 6.0f' % RU),
        ('Particles.Velocity', 'vec3', 'normalize(%s + %s * 0.7f) * %s * sqrt(max(User.Scale, 0.3f))' % (RU, up, rl(280, 900))),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s)' % (rl(1.5, 2.6), rl(8, 20)))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -650.0f)')
    await b.drag(e, 2.2)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 6.0f * (0.45f + 0.55f * sin(Particles.Age * 60.0f + Particles.Phase)) * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Smoke', loop=0.2)
    await b.burst(e, '(int)(14.0f * User.Amount * min(User.Scale, 3.0f))')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(1.0, 1.9)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 22.0f * User.Scale + %s * 15.0f' % (RU, up)),
        ('Particles.Velocity', 'vec3', '(%s * 80.0f + %s * 90.0f + float3(0.0f, 0.0f, 40.0f)) * sqrt(User.Scale)' % (RU, up)),
        ('Particles.BaseSize', 'float', rl(50, 110) + ' * pow(User.Scale, 0.7f)'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 2.4)
    await b.curl(e, '180.0f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 1.7f)' % NA),
        ('Particles.Color', 'color', 'float4(User.SmokeColor.rgb, User.SmokeColor.a * (1.0f - %s) * saturate(Particles.Age * 6.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    # Violet motes that drift up out of the smoke.
    e = await b.emitter('Motes', loop=0.2)
    await b.burst(e, '(int)(26.0f * User.Amount)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.5)),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 25.0f * User.Scale' % RU),
        ('Particles.Velocity', 'vec3', '%s * %s + %s * 40.0f' % (up, rl(60, 180), RU)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(2.5, 5.5))])
    await b.gravity(e, 'float3(0.0f, 0.0f, 60.0f)')
    await b.drag(e, 1.2)
    await b.curl(e, '220.0f')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 4.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light', loop=0.3)
    await b.burst(e, '1')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.26f'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + %s * 30.0f' % up),
        ('Particles.LightRadius', 'float', '420.0f * sqrt(max(User.Scale, 0.3f))')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 14.0f * User.LightScale * pow(1.0f - %s, 2.0f), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- shock (electrified body)
# Attached at the middle of a body that took an Electrify hit, for the hit's Duration: arcs snapping all over a
# capsule of User.Height x User.Radius (local space, Z up from the attach point), sparks spitting off it, a cold glow
# and a flickering light. C++ sizes the capsule from the body's bounds and deactivates it when the shock ends.
async def build_spell_shock():
    b = await new_system('NS_Spell_Shock', [
        ('Color', 'color', (0.42, 0.5, 1.0, 1.0)), ('Color2', 'color', (0.85, 0.9, 1.0, 1.0)), ('Scale', 'float', 1.0),
        ('Height', 'float', 170.0), ('Radius', 'float', 26.0), ('Intensity', 'float', 1.0)])
    on_body = ('float3(cos(Particles.Phase) * User.Radius * %s, sin(Particles.Phase) * User.Radius * %s, (rand(1.0f) - 0.5f) * User.Height)'
               % (rl(0.7, 1.15), rl(0.7, 1.15)))
    e = await b.emitter('Arcs', local=True)
    await b.rate(e, '110.0f * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.04, 0.1)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', RU),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s) * User.Scale' % (rl(1.5, 3.2), rl(18, 62)))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 16.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Sparks')
    await b.rate(e, '45.0f * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.2, 0.45)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', 'Engine.Owner.Position + ' + on_body),
        ('Particles.Velocity', 'vec3', '%s * %s' % (RU, rl(120, 340))),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s)' % (rl(1.0, 1.8), rl(5, 12)))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -900.0f)')
    await b.drag(e, 1.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 7.0f * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    e = await b.emitter('Glow', local=True)
    await b.rate(e, '24.0f * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.12f'),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, (rand(1.0f) - 0.5f) * User.Height * 0.8f)'),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * User.Radius * ' + rl(2.0, 3.4))])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 1.4f * (1.0f - %s), 1.0f)' % NA)])
    await b.sprite(e, 'M_Spell_Glow')
    e = await b.emitter('Light', local=True)
    await b.rate(e, '40.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.1f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.LightRadius', 'float', '280.0f * User.Scale')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * User.Intensity * (3.0f + 7.0f * saturate(sin(Engine.Time * 53.0f) * sin(Engine.Time * 31.0f) + 0.3f)) * (1.0f - %s), 1.0f)' % NA)])
    await b.light(e)
    return b


# ----------------------------------------------------------------------------------------------- body fx (afflictions)
# Attached to a body after a Burn, Freeze or water Push hit, for the hit's Duration: rising embers and smoke (burn),
# frost mist and falling ice glints (freeze), dripping water and mist (wet). C++ picks the mix through the *Rate
# parameters and sizes the capsule (User.Height x User.Radius, Z up from the pelvis) from the body's bounds.
async def build_spell_bodyfx():
    b = await new_system('NS_Spell_BodyFx', [
        ('Color', 'color', (1.0, 0.35, 0.06, 1.0)), ('Color2', 'color', (1.0, 0.8, 0.4, 1.0)),
        ('SmokeColor', 'color', (0.07, 0.06, 0.055, 0.55)), ('Height', 'float', 170.0), ('Radius', 'float', 26.0),
        ('EmberRate', 'float', 0.0), ('SmokeRate', 'float', 0.0), ('FrostRate', 'float', 0.0), ('DripRate', 'float', 0.0),
        ('Intensity', 'float', 1.0)])
    on_body = ('Engine.Owner.Position + float3(cos(Particles.Phase) * User.Radius * %s, sin(Particles.Phase) * User.Radius * %s, '
               '(rand(1.0f) - 0.5f) * User.Height)' % (rl(0.6, 1.1), rl(0.6, 1.1)))
    # Burn: embers lifting off the body.
    e = await b.emitter('Embers')
    await b.rate(e, 'User.EmberRate * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.5, 1.1)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, %s) + %s * 30.0f' % (rl(60, 160), RU)),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(2.0, 4.5))])
    await b.curl(e, '220.0f')
    await b.drag(e, 1.2)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(lerp(User.Color2.rgb * 7.0f, User.Color.rgb * 3.0f, %s) * (1.0f - %s), 1.0f)' % (NA, NA))])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    # Burn: dark smoke curling up from the body.
    e = await b.emitter('Smoke')
    await b.rate(e, 'User.SmokeRate * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.9, 1.6)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, %s)' % rl(40, 90)),
        ('Particles.BaseSize', 'float', rl(20, 38)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.curl(e, '120.0f')
    await b.drag(e, 1.5)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 2.0f)' % NA),
        ('Particles.Color', 'color', 'float4(User.SmokeColor.rgb, User.SmokeColor.a * (1.0f - %s) * saturate(Particles.Age * 4.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    # Freeze: pale mist hugging the body and ice glints falling off it.
    e = await b.emitter('FrostMist')
    await b.rate(e, 'User.FrostRate * 0.5f * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.4)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', 'float3(0.0f, 0.0f, %s) + %s * 12.0f' % (rl(-25, 5), RU)),
        ('Particles.BaseSize', 'float', rl(22, 40)),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 2.0)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (1.0f + %s * 1.4f)' % NA),
        ('Particles.Color', 'color', 'float4(0.75f, 0.88f, 1.0f, 0.32f * (1.0f - %s) * saturate(Particles.Age * 4.0f))' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')
    e = await b.emitter('FrostGlints')
    await b.rate(e, 'User.FrostRate * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.4, 0.9)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', '%s * 40.0f' % RU),
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * ' + rl(1.5, 3.5))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -500.0f)')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 6.0f * (0.5f + 0.5f * sin(Particles.Age * 40.0f + Particles.Phase)) * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    # Wet: water dripping off the body.
    e = await b.emitter('Drips')
    await b.rate(e, 'User.DripRate * User.Intensity')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.35, 0.7)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', on_body),
        ('Particles.Velocity', 'vec3', '%s * 25.0f' % RU),
        ('Particles.SpriteSize', 'vec2', 'float2(%s, %s)' % (rl(1.2, 2.2), rl(4, 9)))])
    await b.gravity(e, 'float3(0.0f, 0.0f, -980.0f)')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color2.rgb * 2.5f * (1.0f - %s), 1.0f)' % NA)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow', alignment='VelocityAligned')
    # A soft light in the element's colour while it lasts (embers glow, frost gleams).
    e = await b.emitter('Light', local=True)
    await b.rate(e, '40.0f')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', '0.1f'),
        ('Particles.Position', 'pos', 'float3(0.0f, 0.0f, 0.0f)'),
        ('Particles.LightRadius', 'float', '220.0f')])
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.Color', 'color', 'float4(User.Color.rgb * User.Intensity * saturate(User.EmberRate + User.FrostRate) * 0.04f * (2.5f + 0.8f * sin(Engine.Time * 17.0f)) * (1.0f - %s), 1.0f)' % NA)])
    await b.light(e)
    return b


async def finish(b):
    s = b.S
    # GetSystemCompileState can report UpToDate before the VM compile has even started; opening the
    # asset editor forces a real compile, so wait on that and then trust the per-script status.
    await call_tool('EditorToolset.EditorAppToolset.OpenEditorForAsset', assetPath=s.get_path_name().split('.')[0])
    await asyncio.sleep(1.0)
    for _ in range(240):
        cs = await call_tool(T + 'GetSystemCompileState', system=s)
        if not cs['bIsCompiling']:
            break
        await asyncio.sleep(0.25)
    cs = json.loads(json.dumps(cs, default=str))
    errors = [(x['emitterName'], x['scriptName'], x['errorSummary'][:600]) for x in cs['scripts'] if x['errorSummary']]
    issues = await call_tool(T + 'GetStackIssues', system=s)
    issues = json.loads(json.dumps(issues, default=str))
    bad = [(x['emitterName'], x['scriptName']) for x in cs['scripts'] if x['lastCompileStatus'] == 'Error']
    if bad:
        raise RuntimeError('%s failed to compile: %s (see the Niagara message log)' % (s.get_name(), bad))
    EA.save_loaded_asset(s, False)
    await call_tool('EditorToolset.EditorAppToolset.CloseEditorForAsset', assetPath=s.get_path_name().split('.')[0], unsavedChanges='Save')
    return {'system': s.get_path_name(), 'status': cs['aggregateStatus'], 'errors': errors, 'log': b.log,
            'issues': str(issues)[:3000]}


if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
    raise RuntimeError('PIE is running; Niagara assets cannot be edited now.')
which = ARGS or ['all']
builders = {'projectile': build_projectile, 'impact': build_impact, 'heal': build_heal, 'ward': build_ward,
            'tarnish_bolt': build_tarnish_bolt, 'tarnish_burst': build_tarnish_burst,
            'shock': build_spell_shock, 'bodyfx': build_spell_bodyfx}
results = []
for key, fn in builders.items():
    if 'all' in which or key in which:
        results.append(await finish(await fn()))
json.dumps(results, indent=1)
