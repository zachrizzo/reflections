"""Second pass after build_crafted_niagara.py, run as its own call once the build's compiles have settled.

Systems built from scratch through the Niagara toolset can compile "UpToDate" yet never activate (they stay Inactive in
the frame they spawn). One later input edit that forces a full recompile fixes them for good, saved or not. This pass
probes each crafted system, and for any that does not activate re-sets the first emitter's spawn expression with a
fresh no-op salt, recompiles, saves and probes again.
"""
import json
import time

T = 'NiagaraToolsets.NiagaraToolset_System.'
HLSL = '/Script/NiagaraEditor.NiagaraExt_StackInputData_HlslExpression'
EA = unreal.EditorAssetLibrary
NAMES = ARGS or ['NS_Crafted_Body', 'NS_Crafted_Burst', 'NS_Crafted_Arc', 'NS_Crafted_Field']
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


async def probe(system):
    c = unreal.NiagaraFunctionLibrary.spawn_system_at_location(world, system, unreal.Vector(0, 0, -5000), unreal.Rotator(0, 0, 0),
                                                               unreal.Vector(1, 1, 1), False, True)
    await asyncio.sleep(0.5)
    active = bool(c and c.is_active())
    if c:
        c.destroy_component(c)
    return active


async def wait_compile(system):
    for _ in range(240):
        cs = await call_tool(T + 'GetSystemCompileState', system=system)
        if not cs['bIsCompiling']:
            return cs['aggregateStatus']
        await asyncio.sleep(0.25)
    return 'timeout'


async def first_spawn_input(system):
    summary = json.loads(json.dumps(await call_tool(T + 'GetSystemSummary', system=system), default=str))
    emitters = summary.get('emitters') or summary.get('emitterSummaries') or []
    em = emitters[0]['emitterName']
    topo = json.loads(json.dumps(await call_tool(T + 'GetScriptStackTopology',
                                                 scriptRef={'system': system, 'emitterName': em, 'scriptName': 'EmitterUpdateScript'}), default=str))
    for m in topo.get('modules', []):
        name = m.get('moduleName', '')
        if name.startswith('SpawnRate') or name.startswith('SpawnBurst'):
            inp = 'SpawnRate' if name.startswith('SpawnRate') else 'Spawn Count'
            vals = json.loads(json.dumps(await call_tool(T + 'GetModuleInputValues',
                                                         moduleRef={'system': system, 'emitterName': em, 'scriptName': 'EmitterUpdateScript', 'moduleName': name}), default=str))
            for i in vals['inputs']:
                if i['name'] == inp:
                    return em, name, inp, i['value']['value'].get('hlslExpression'), inp == 'Spawn Count'
    raise RuntimeError('no spawn module on the first emitter of ' + system.get_name())


out = {}
for n in NAMES:
    s = unreal.load_asset('/Game/SpellCrafting/VFX/' + n)
    before = await probe(s)
    if before:
        out[n] = 'activates'
        continue
    em, module, inp, expr, integer = await first_spawn_input(s)
    salt = int(time.time() * 1000) % 1000000
    new = '((%s) + (int)(0.0000001f * %d.0f))' % (expr, salt) if integer else '((%s) + 0.0000001f * %d.0f)' % (expr, salt)
    await call_tool(T + 'SetStackInputData', stackInputRef={'system': s, 'emitterName': em, 'scriptName': 'EmitterUpdateScript',
                                                            'moduleName': module, 'inputNameStack': [inp]},
                    inputData={'struct': unreal.load_object(None, HLSL), 'value': {'hlslExpression': new}})
    status = await wait_compile(s)
    EA.save_loaded_asset(s, False)
    out[n] = 'fixed' if await probe(s) else 'STILL INACTIVE (%s)' % status
RESULT = json.dumps(out)
RESULT
