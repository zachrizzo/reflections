"""PIE regression check for crowd destinations, pairing, ownership handoffs and density cost.

Run through PythonScriptingTools.execute_python with top-level await. Uses a temporary
PIE session on the open London map and restores every console override when finished.
Results go to Saved/CrowdImprovements/verification.json.
"""
import json
import base64
import math
from pathlib import Path
import statistics


OUT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / 'CrowdImprovements'
OUT.mkdir(parents=True, exist_ok=True)
RESULT = {'checks': {}, 'density': {}}


async def console(command):
    await call_tool('ConsoleToolset.ConsoleToolset.RunConsoleCommand', command=command)


def position(actor):
    value = actor.get_actor_location()
    return (value.x, value.y, value.z)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def check(name, passed, detail):
    RESULT['checks'][name] = {'passed': bool(passed), 'detail': detail}


async def sample_density(world, ring, stroll, spots, count):
    await console(f'Crowd.Ring.Count {count}')
    await asyncio.sleep(10.0)
    walkers = list(ring.get_walkers())
    initial = {actor.get_name(): position(actor) for actor in walkers}
    samples = []
    max_pairs = 0
    closest = []
    closest_pair = None
    minimum_distance = float('inf')
    for _ in range(28):
        await asyncio.sleep(0.35)
        row = await call_tool('PerfToolset.StatsToolset.GetFrameTimings')
        samples.append(row)
        live = list(ring.get_walkers())
        max_pairs = max(max_pairs, sum(actor.actor_has_tag('Crowd_Pair') for actor in live) // 2)
        positions = [position(actor) for actor in live]
        if len(positions) > 1:
            closest.append(min(distance(a, b) for i, a in enumerate(positions) for b in positions[i + 1:]))
            for i, point in enumerate(positions):
                for j in range(i + 1, len(positions)):
                    gap = distance(point, positions[j])
                    if gap < minimum_distance:
                        minimum_distance = gap
                        closest_pair = [{'actor': actor.get_name(), 'paired': actor.actor_has_tag('Crowd_Pair'),
                                         'in_activity': actor.actor_has_tag('NPC_NoStroll')}
                                        for actor in (live[i], live[j])]
    final = {actor.get_name(): position(actor) for actor in ring.get_walkers()}
    moved = {name: round(distance(point, final[name]), 1) for name, point in initial.items() if name in final}
    timings = {}
    for key in samples[0]:
        values = [sample[key] for sample in samples if isinstance(sample[key], (int, float))]
        if values:
            timings[key] = {'median': round(statistics.median(values), 3), 'p95': round(sorted(values)[int(0.95 * (len(values) - 1))], 3)}
    description = stroll.describe()
    output = {
        'requested': count, 'actual': ring.get_walker_count(), 'samples': len(samples),
        'ring_status': ring.describe(),
        'console_count': unreal.SystemLibrary.get_console_variable_int_value('Crowd.Ring.Count'),
        'timings_ms': timings, 'max_walking_pairs': max_pairs,
        'moved_cm': moved, 'moving_over_1m': sum(value > 100 for value in moved.values()),
        'minimum_ring_spacing_cm': round(min(closest), 1) if closest else None,
        'closest_pair': closest_pair,
        'spot_occupants': spots.get_occupied_count(), 'stroll': description,
        'destinations_in_use': sum('destination street,' not in line for line in description.splitlines()[1:]),
    }
    RESULT['density'][str(count)] = output
    (OUT / 'verification_progress.json').write_text(json.dumps(RESULT, indent=2), encoding='utf-8')
    return output


async def verify():
    if await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
        return {'error': 'An existing PIE session is active. No changes were made.'}
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_editor_world().get_path_name() != '/Game/GrayLondon/Maps/GrayLondon_Geodata.GrayLondon_Geodata':
        return {'error': 'Open GrayLondon_Geodata before running this crowd check.'}
    overrides = {'GameFlow.TitleInPIE': '0', 'Cutscene.IntroInPIE': '0', 'Crowd.Ring.Count': '12',
                 'Villain.AutoStart': '0', 'Squads.StartPatrol': '0'}
    saved = {}
    started = False
    try:
        for name, value in overrides.items():
            saved[name] = await call_tool('ConsoleToolset.ConsoleToolset.GetCVarValue', name=name)
            await console(f'{name} {value}')
        started = True
        await call_tool('EditorToolset.EditorAppToolset.StartPIE', options={
            'warmupSeconds': 3.0,
            'startTransform': {'translation': {'x': 329110.3628, 'y': 31140.4642, 'z': 151.1847},
                               'rotation': {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0}}})
        world = editor.get_game_world()
        ring = unreal.get_world_subsystem(world, unreal.ReflectionsCrowdRingSubsystem)
        stroll = unreal.get_world_subsystem(world, unreal.ReflectionsCrowdStrollSubsystem)
        spots = unreal.get_world_subsystem(world, unreal.ReflectionsCrowdSpotSubsystem)
        npcs = unreal.get_world_subsystem(world, unreal.ReflectionsNpcSubsystem)
        RESULT['world'] = world.get_path_name()
        RESULT['lanes'] = unreal.ReflectionsCrowdLaneLibrary.describe_lanes(world)
        base = await sample_density(world, ring, stroll, spots, 12)
        dense = await sample_density(world, ring, stroll, spots, 18)
        capture = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport',
                                  world={'refPath': world.get_path_name()}, maxResolution=1400)
        image_data = capture['image']
        if isinstance(image_data, str) and len(image_data) > 1000 and not image_data.startswith('urn:'):
            (OUT / 'crowd_18.png').write_bytes(base64.b64decode(image_data.split(',')[-1]))
            RESULT['screenshot'] = str(OUT / 'crowd_18.png')
        check('ring_population', base['actual'] == 12 and dense['actual'] == 18,
              {'base': base['actual'], 'dense': dense['actual']})
        check('walkers_make_progress', dense['moving_over_1m'] >= 6, dense['moving_over_1m'])
        check('street_destinations_loaded', '41 street destinations' in dense['stroll'], dense['stroll'].splitlines()[0])
        check('purposeful_trips', dense['destinations_in_use'] > 0, dense['destinations_in_use'])
        paired = [actor for actor in ring.get_walkers() if actor.actor_has_tag('Crowd_Pair')]
        check('walking_pairs_form', max(base['max_walking_pairs'], dense['max_walking_pairs']) > 0,
              {'base_max': base['max_walking_pairs'], 'dense_max': dense['max_walking_pairs']})
        check('pedestrians_keep_clearance', dense['minimum_ring_spacing_cm'] is not None and dense['minimum_ring_spacing_cm'] >= 60.0,
              dense['minimum_ring_spacing_cm'])
        if paired:
            actor = paired[0]
            brain = actor.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
            tags = list(actor.get_editor_property('tags'))
            actor.set_editor_property('tags', tags + ['NPC_NoStroll'])
            await asyncio.sleep(0.4)
            check('scene_claim_releases_walking_pair', not actor.actor_has_tag('Crowd_Pair') and not brain.is_externally_steered(),
                  {'paired': actor.actor_has_tag('Crowd_Pair'), 'steered': brain.is_externally_steered()})
            actor.set_editor_property('tags', [tag for tag in tags if str(tag) != 'Crowd_Pair'])
            await asyncio.sleep(1.4)
        target = next((actor for actor in ring.get_walkers()
                       if not actor.actor_has_tag('NPC_NoStroll') and not npcs.is_npc_in_scene(actor)), None)
        if target:
            brain = target.get_component_by_class(unreal.ReflectionsNpcReactionComponent)
            stimulus = unreal.ReflectionsNpcStimulus()
            stimulus.kind = unreal.ReflectionsNpcStimulusKind.SPELL_NOISE
            stimulus.location = target.get_actor_location()
            stimulus.radius = 500.0
            stimulus.intensity = 20.0
            npcs.report_stimulus(stimulus)
            await asyncio.sleep(0.5)
            reaction = str(brain.get_editor_property('reaction'))
            check('danger_handoff', 'CALM' not in reaction and not target.actor_has_tag('Crowd_Pair') and not brain.is_externally_steered(),
                  {'reaction': reaction, 'paired': target.actor_has_tag('Crowd_Pair'), 'steered': brain.is_externally_steered()})
        RESULT['completed'] = True
    except Exception as error:
        RESULT['error'] = str(error)
    finally:
        if started and await call_tool('EditorToolset.EditorAppToolset.IsPIERunning'):
            await call_tool('EditorToolset.EditorAppToolset.StopPIE')
        for name, value in saved.items():
            await console(f'{name} {value}')
        (OUT / 'verification.json').write_text(json.dumps(RESULT, indent=2), encoding='utf-8')
    return RESULT


await verify()
