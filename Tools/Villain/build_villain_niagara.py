"""Builds /Game/Villain/FX/NS_Villain_Shroud: the villain's smoke, cloth-like wisps and violet embers.

Run inside the editor (MCP Python tool) with PIE stopped:
    ns = dict(globals()); exec(compile(src, 'build_villain_niagara.py', 'exec'), ns); result = await ns['main']()

User parameters (set from C++, ReflectionsVillainFx::Shroud): Scale (body size, 1 = a man), Amount (0..3, spawn
rates), Color (ember colour). All emitters are CPU sprites in world space, so the smoke trails behind as he moves.
Helpers follow Tools/SpellVFX/build_spell_niagara.py (same toolset calls, same CPU-VM-safe expressions).
"""
import asyncio
import json

T = 'NiagaraToolsets.NiagaraToolset_System.'
FOLDER = '/Game/Villain/FX'
NAME = 'NS_Villain_Shroud'
SPELL_MAT = '/Game/Characters/Hero/SpellVFX/Materials/'
TEMPLATE = '/Niagara/DefaultAssets/Templates/Emitters/'
TYPES = {
    'float': '/Script/Niagara.NiagaraFloat', 'int': '/Script/Niagara.NiagaraInt32', 'bool': '/Script/Niagara.NiagaraBool',
    'vec3': '/Script/CoreUObject.Vector3f', 'pos': '/Script/Niagara.NiagaraPosition', 'color': '/Script/CoreUObject.LinearColor',
    'vec2': '/Script/CoreUObject.Vector2f',
}
HLSL = '/Script/NiagaraEditor.NiagaraExt_StackInputData_HlslExpression'
ENUM = '/Script/NiagaraEditor.NiagaraExt_StackInputData_Enum'
NA = 'Particles.NormalizedAge'
RU = 'normalize(float3(rand(2.0f) - 1.0f, rand(2.0f) - 1.0f, rand(2.0f) - 1.0f) + float3(0.0001f, 0.0002f, 0.0003f))'
# Fade in and out over the particle's life (no smoothstep: the CPU VM lacks it).
LIFE = 'sin(%s * 3.14159f)' % NA


def rl(a, b):
    return 'lerp(%sf, %sf, rand(1.0f))' % (float(a), float(b))


def obj(path):
    return unreal.load_object(None, path)


def ty(name):
    return {'classStructOrEnum': obj(TYPES[name])}


class Builder:
    def __init__(self, system):
        self.S = system

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

    async def emitter(self, name):
        await call_tool(T + 'AddEmitter', system=self.S, templateEmitter=unreal.load_asset(TEMPLATE + 'Minimal'), emitterName=name)
        await call_tool(T + 'SetEmitterData', emitterRef=self.ref(name),
                        emitterData={'propertyValues': json.dumps({'bLocalSpace': False, 'SimTarget': 'CPUSim'})})
        await self.enum(name, 'EmitterUpdateScript', 'EmitterState', 'Life Cycle Mode',
                        '/Niagara/Enums/ENiagaraEmitterLifeCycleMode.ENiagaraEmitterLifeCycleMode', 'NewEnumerator1')
        await self.enum(name, 'EmitterUpdateScript', 'EmitterState', 'Loop Behavior',
                        '/Niagara/Enums/ENiagara_EmitterStateOptions.ENiagara_EmitterStateOptions', 'NewEnumerator0')
        return name

    async def enum(self, em, script, module, inp, enum_path, enum_name):
        short = enum_path.split('.')[-1]
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp),
                        inputData={'struct': obj(ENUM), 'value': {'enum': obj(enum_path), 'enumName': '%s::%s' % (short, enum_name)}})

    async def value(self, em, script, module, inp, kind, v):
        payload = {'value': v} if kind in ('float', 'int', 'bool') else v
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp),
                        inputData={'struct': obj(TYPES[kind]), 'value': payload})

    async def expr(self, em, script, module, inp, e):
        await call_tool(T + 'SetStackInputData', stackInputRef=self.ref(em, script, module, inp),
                        inputData={'struct': obj(HLSL), 'value': {'hlslExpression': e}})

    async def module(self, em, script, path):
        m = await call_tool(T + 'AddModule', moduleLocationRef=self.ref(em, script), moduleAsset=unreal.load_asset(path))
        return m['moduleName']

    async def setp(self, em, script, entries):
        m = await call_tool(T + 'AddSetParametersModule', moduleLocationRef=self.ref(em, script),
                            parameters=[{'variable': {'name': a, 'type': ty(k)}} for a, k, _ in entries])
        for a, _, e in entries:
            await self.expr(em, script, m['moduleName'], a, e)

    async def rate(self, em, rate_expr):
        m = await self.module(em, 'EmitterUpdateScript', '/Niagara/Modules/Emitter/SpawnRate')
        await self.expr(em, 'EmitterUpdateScript', m, 'SpawnRate', rate_expr)

    async def drag(self, em, amount):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Update/Forces/Drag')
        await self.value(em, 'ParticleUpdateScript', m, 'Drag', 'float', float(amount))

    async def curl(self, em, strength_expr):
        m = await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Update/Forces/V2/CurlNoiseForce')
        await self.expr(em, 'ParticleUpdateScript', m, 'Noise Strength', strength_expr)

    async def solve(self, em):
        await self.module(em, 'ParticleUpdateScript', '/Niagara/Modules/Solvers/SolveForcesAndVelocity')

    async def sprite(self, em, material, alignment='Unaligned', sort='None'):
        await call_tool(T + 'SetRendererData', rendererRef=self.ref(em, renderer=0),
                        rendererData={'propertyValues': json.dumps({'material': {'refPath': SPELL_MAT + material + '.' + material},
                                                                     'alignment': alignment, 'facingMode': 'FaceCamera',
                                                                     'sortMode': sort})})


async def new_system():
    path = FOLDER + '/' + NAME
    EA = unreal.EditorAssetLibrary
    EA.make_directory(FOLDER)
    try:
        await call_tool('EditorToolset.EditorAppToolset.CloseEditorForAsset', assetPath=path, unsavedChanges='Discard')
    except Exception:
        pass
    if EA.does_asset_exist(path):
        EA.delete_asset(path)
    await call_tool(T + 'CreateNiagaraSystem', assetName=NAME, assetPath=FOLDER,
                    templateSystem=unreal.load_asset('/Niagara/DefaultAssets/DefaultSystem'))
    s = EA.load_asset(path)
    await call_tool(T + 'RemoveEmitter', emitterRef={'system': s, 'emitterName': 'Fountain'})
    users = [('Scale', 'float', 1.0), ('Amount', 'float', 1.0), ('Color', 'color', (0.32, 0.04, 0.62, 1.0))]
    variables = []
    for n, kind, default in users:
        if kind == 'float':
            dv = {'struct': obj(TYPES['float']), 'value': {'value': float(default)}}
        else:
            dv = {'struct': obj('/Script/CoreUObject.LinearColor'), 'value': dict(zip('rgba', default))}
        variables.append({'name': 'User.' + n, 'type': ty(kind), 'defaultValue': dv})
    await call_tool(T + 'AddUserVariables', system=s, variablesToAdd=variables)
    return Builder(s)


async def build():
    b = await new_system()
    body = 'Engine.Owner.Position + float3((rand(2.0f) - 1.0f) * 30.0f, (rand(2.0f) - 1.0f) * 30.0f, %s) * User.Scale'

    # Thick black smoke that clings to him and rolls upward.
    e = await b.emitter('Smoke')
    await b.rate(e, '38.0f * User.Amount * sqrt(User.Scale)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(1.1, 2.3)),
        ('Particles.Position', 'pos', body % rl(0, 175)),
        ('Particles.Velocity', 'vec3', '(%s * 18.0f + float3(0.0f, 0.0f, %s)) * User.Scale' % (RU, rl(25, 70))),
        ('Particles.BaseSize', 'float', rl(45, 100) + ' * User.Scale'),
        ('Particles.SpriteRotation', 'float', 'rand(360.0f)')])
    await b.drag(e, 1.4)
    await b.curl(e, '140.0f * User.Scale')
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize * (0.6f + %s * 1.1f)' % NA),
        ('Particles.Color', 'color', 'float4(0.006f, 0.004f, 0.010f, 0.78f * %s)' % LIFE)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', sort='ViewDepth')

    # Wisps: long dark streaks that spiral off him like torn cloth.
    e = await b.emitter('Wisps')
    await b.rate(e, '20.0f * User.Amount * sqrt(User.Scale)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.7)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Rad', 'float', rl(18, 40)),
        ('Particles.SparkW', 'float', rl(5, 11))])
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Position', 'pos', 'Engine.Owner.Position + float3(cos(Particles.Phase) * Particles.Rad, sin(Particles.Phase) * Particles.Rad, %s) * User.Scale' % rl(30, 175)),
        ('Particles.Velocity', 'vec3', '(float3(-sin(Particles.Phase), cos(Particles.Phase), 0.0f) * %s + float3(0.0f, 0.0f, %s)) * User.Scale' % (rl(45, 110), rl(35, 120)))])
    await b.curl(e, '230.0f * User.Scale')
    await b.drag(e, 0.9)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(Particles.SparkW, 26.0f + length(Particles.Velocity) * 0.45f) * User.Scale'),
        ('Particles.Color', 'color', 'float4(0.010f, 0.006f, 0.016f, 0.9f * %s)' % LIFE)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_SoftPuff', alignment='VelocityAligned', sort='ViewDepth')

    # Violet embers: the magic in him, so he reads even against black.
    e = await b.emitter('Embers')
    await b.rate(e, '16.0f * User.Amount * sqrt(User.Scale)')
    await b.setp(e, 'ParticleSpawnScript', [
        ('Particles.Lifetime', 'float', rl(0.8, 1.9)),
        ('Particles.Phase', 'float', 'rand(6.2832f)'),
        ('Particles.Position', 'pos', body % rl(20, 180)),
        ('Particles.Velocity', 'vec3', '(%s * 15.0f + float3(0.0f, 0.0f, %s)) * User.Scale' % (RU, rl(20, 65))),
        ('Particles.BaseSize', 'float', rl(2.0, 4.5) + ' * sqrt(User.Scale)')])
    await b.curl(e, '120.0f * User.Scale')
    await b.drag(e, 1.1)
    await b.setp(e, 'ParticleUpdateScript', [
        ('Particles.SpriteSize', 'vec2', 'float2(1.0f, 1.0f) * Particles.BaseSize'),
        ('Particles.Color', 'color', 'float4(User.Color.rgb * 7.0f * %s * (0.6f + 0.4f * sin(Particles.Age * 21.0f + Particles.Phase)), 1.0f)' % LIFE)])
    await b.solve(e)
    await b.sprite(e, 'M_Spell_Glow')
    return b


async def finish(b):
    s = b.S
    EA = unreal.EditorAssetLibrary
    await call_tool('EditorToolset.EditorAppToolset.OpenEditorForAsset', assetPath=s.get_path_name().split('.')[0])
    await asyncio.sleep(1.0)
    cs = None
    for _ in range(240):
        cs = await call_tool(T + 'GetSystemCompileState', system=s)
        if not cs['bIsCompiling']:
            break
        await asyncio.sleep(0.25)
    cs = json.loads(json.dumps(cs, default=str))
    errors = [(x['emitterName'], x['scriptName'], x['errorSummary'][:600]) for x in cs['scripts'] if x['errorSummary']]
    bad = [(x['emitterName'], x['scriptName']) for x in cs['scripts'] if x['lastCompileStatus'] == 'Error']
    issues = json.loads(json.dumps(await call_tool(T + 'GetStackIssues', system=s), default=str))
    if not bad:
        EA.save_loaded_asset(s, False)
    await call_tool('EditorToolset.EditorAppToolset.CloseEditorForAsset', assetPath=s.get_path_name().split('.')[0],
                    unsavedChanges='Save' if not bad else 'Discard')
    return {'system': s.get_path_name(), 'status': cs['aggregateStatus'], 'bad': bad, 'errors': errors, 'issues': str(issues)[:2500]}


async def main():
    if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
        raise RuntimeError('PIE is running; Niagara assets cannot be edited now.')
    return await finish(await build())
