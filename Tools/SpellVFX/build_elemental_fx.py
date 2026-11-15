"""Author independent water/healing Niagara variants in the live editor.

Uses the bundled Niagara MCP helper; run only with PIE stopped and after the two candidate assets have been duplicated by
duplicate_elemental_fx.py. All edits are limited to the named candidate assets.
"""
import json
import time

import ue_mcp as m

NS = 'NiagaraToolsets.NiagaraToolset_System'
F = '/Script/Niagara.NiagaraFloat'
I = '/Script/Niagara.NiagaraInt32'
V2 = '/Script/CoreUObject.Vector2f'
V3 = '/Script/CoreUObject.Vector3f'
COL = '/Script/CoreUObject.LinearColor'
ROOT = '/Game/Characters/Hero/SpellVFX'
MATERIAL = '/Game/Blueprints/Combat/Explosives/M_ExplosionSpark.M_ExplosionSpark'


def reference(name, script='', module='', stack=(), renderer=-1):
    return {'system': m.ref(f'{ROOT}/{name}.{name}'), 'emitterName': 'DirectionalBurst',
            'scriptName': script, 'moduleName': module, 'rendererIndex': renderer, 'inputNameStack': list(stack)}


def update(name, script, module, path, struct, value):
    for attempt in range(40):
        try:
            result = m.call(NS, 'SetStackInputData', {'stackInputRef': reference(name, script, module, path),
                            'inputData': {'struct': m.ref(struct), 'value': value}})
            break
        except m.McpError as exc:
            if 'slow task' not in str(exc) or attempt == 39:
                raise
            time.sleep(0.5)
    if result is None:
        raise RuntimeError(f'Failed to set {name} {module} {path}')


def configure(name, color, count, lifetime, sizes, cone, speeds, gravity, drag):
    edits = [
        ('EmitterUpdateScript', 'SpawnBurst_Instantaneous', ['Spawn Count'], I, {'value': count}),
        ('ParticleSpawnScript', 'InitializeParticle', ['Lifetime Min'], F, {'value': lifetime[0]}),
        ('ParticleSpawnScript', 'InitializeParticle', ['Lifetime Max'], F, {'value': lifetime[1]}),
        ('ParticleSpawnScript', 'InitializeParticle', ['Color'], COL, dict(zip('rgba', color))),
        ('ParticleSpawnScript', 'InitializeParticle', ['Sprite Size Min'], V2, {'x': sizes[0], 'y': sizes[0]}),
        ('ParticleSpawnScript', 'InitializeParticle', ['Sprite Size Max'], V2, {'x': sizes[1], 'y': sizes[1]}),
        ('ParticleSpawnScript', 'AddVelocityInCone', ['Cone Angle'], F, {'value': cone}),
        ('ParticleSpawnScript', 'AddVelocityInCone', ['Cone Axis'], V3, {'x': 1, 'y': 0, 'z': 0}),
        ('ParticleSpawnScript', 'AddVelocityInCone', ['Velocity Strength', 'Minimum'], F, {'value': speeds[0]}),
        ('ParticleSpawnScript', 'AddVelocityInCone', ['Velocity Strength', 'Maximum'], F, {'value': speeds[1]}),
        ('ParticleUpdateScript', 'GravityForce', ['Gravity'], V3, {'x': 0, 'y': 0, 'z': gravity}),
        ('ParticleUpdateScript', 'Drag', ['Drag', 'Minimum'], F, {'value': drag[0]}),
        ('ParticleUpdateScript', 'Drag', ['Drag', 'Maximum'], F, {'value': drag[1]}),
    ]
    for script, module, path, struct, value in edits:
        update(name, script, module, path, struct, value)
    renderer = reference(name, renderer=0)
    m.call(NS, 'SetRendererData', {'rendererRef': renderer,
           'rendererData': {'propertyValues': json.dumps({'Material': m.ref(MATERIAL)})}})
    print(f'Configured {name}', flush=True)


if __name__ == '__main__':
    configure('NS_WaterImpact', (0.12, 0.60, 0.92, 0.75), 48, (0.3, 0.8), (2, 7), 55, (160, 520), -750, (1, 2))
    configure('NS_HealingBurst', (0.32, 0.95, 0.38, 0.75), 45, (0.8, 1.6), (2, 5), 32, (80, 230), 20, (0.5, 1))
