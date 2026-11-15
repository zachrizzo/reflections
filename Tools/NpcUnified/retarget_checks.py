"""Rewrites the older NPC checks so that they run on any map (the old test maps were deleted on 2026-11-14 and Gray
London is the only map). Standard library only; run it from a terminal, not in the editor:

    python Tools/NpcUnified/retarget_checks.py            # rewrites the checks listed below, in place
    python Tools/NpcUnified/retarget_checks.py --dry-run  # only says what it would change

What it changes in each check:
  - the "wrong map is open" refusal goes;
  - after StartPIE it waits for the hero to have been put down (a streamed city takes a while), up to 20 s;
  - every position that was a coordinate of the old test level becomes W(x, y, z): the same offsets as before, but
    measured from where the hero stands when PIE starts, with the hero's own forward as "ahead" and the ground at
    the hero's feet. The old level had two test sites (around 1500,500 and around -700,350); both now sit on the
    hero's start, so "move the hero to the other site" no longer moves it.
A check that has been rewritten carries the marker line and is left alone on a second run.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = ('verify_npc_sorcery.py', 'verify_npc_reactions.py', 'verify_npc_reactions2.py', 'verify_npc_heat.py', 'diag_tarnish_cast.py',
          'verify_npc_batch2.py', 'verify_npc_melee.py', 'verify_npc_system.py')
MARKER = '# retargeted: positions are relative to where the hero stands when PIE starts (see retarget_checks.py)'

HELPER = MARKER + '''
_frame = {}


def W(x, y, z=0.0):
    """A position of the old test level, as the same offset from where the hero stood when PIE started."""
    if not _frame:
        game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        hero = unreal.GameplayStatics.get_player_pawn(game, 0)
        here = hero.get_actor_location()
        ahead = hero.get_actor_forward_vector()
        ahead = unreal.Vector(ahead.x, ahead.y, 0.0).normal()
        _frame.update(here=here, ahead=ahead, right=unreal.Vector(-ahead.y, ahead.x, 0.0))
    sites = ((1500.0, 500.0), (-700.0, 350.0))
    ox, oy = min(sites, key=lambda s: (x - s[0]) ** 2 + (y - s[1]) ** 2)
    forward, right = -(y - oy), x - ox          # the old checks looked down -Y, with +X to their right
    here, a, r = _frame['here'], _frame['ahead'], _frame['right']
    return unreal.Vector(here.x + a.x * forward + r.x * right, here.y + a.y * forward + r.y * right, here.z - 90.0 + z)


async def hero_is_down():
    """Waits (up to 20 s) until PIE has a hero that has stopped falling, then fixes the frame W() measures from."""
    for _ in range(40):
        await asyncio.sleep(0.5)
        game = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        hero = unreal.GameplayStatics.get_player_pawn(game, 0) if game else None
        if hero and abs(hero.get_velocity().z) < 5.0:
            break
    await asyncio.sleep(1.0)
    W(1500.0, 500.0, 90.0)


'''

POSITION = re.compile(r'unreal\.Vector\(\s*(-?\d[^,()]*?)\s*,\s*(-?\d[^,()]*?)\s*,\s*(-?\d[^,()]*?)\s*\)')
# Measurements that assumed "away from the hero" was the old level's -Y: now along the hero's own forward.
AHEAD = "((s['x'] - before['x']) * _frame['ahead'].x + (s['y'] - before['y']) * _frame['ahead'].y)"
AXIS_FIXES = (
    ("away = max(before['y'] - s['y'] for s in samples)", "away = max(" + AHEAD + " for s in samples)"),
    ("or before['y'] - s['y'] >= 40), None)", "or " + AHEAD + " >= 40), None)"),
    ("'moved_away_cm': max(before['y'] - s['y'] for s in samples)", "'moved_away_cm': max(" + AHEAD + " for s in samples)"),
)


def is_place(x_text, y_text):
    """An absolute place on the old level (not an offset such as 0, 0, 100)."""
    def number(text):
        m = re.match(r'-?\d+(?:\.\d+)?', text.strip())
        return abs(float(m.group())) if m else 0.0
    return number(x_text) >= 300.0 or number(y_text) >= 300.0


def rewrite(source):
    notes = []
    if MARKER in source:
        return source, ['already retargeted']
    # 1. the refusal to run on another map
    pattern = re.compile(r"elif open_map != 'Lvl_HeroSampleCrowd':\n\s+result\['abort'\] = [^\n]+\n")
    source, count = pattern.subn('', source)
    notes.append('map refusal removed: %d' % count)
    # 2. wait for the hero instead of a fixed three seconds
    source, count = re.subn(r"(\n\s+)await asyncio\.sleep\(3\.0\)(\n\s+world = unreal\.get_editor_subsystem)", r"\1await hero_is_down()\2", source, count=1)
    notes.append('hero wait: %d' % count)
    # 3. positions
    def place(match):
        if not is_place(match.group(1), match.group(2)):
            return match.group(0)
        return 'W(%s, %s, %s)' % (match.group(1), match.group(2), match.group(3))
    source, _ = POSITION.subn(place, source)
    notes.append('positions: %d' % source.count('W('))
    fixed = 0
    for was, now in AXIS_FIXES:
        if was in source:
            source = source.replace(was, now)
            fixed += 1
    notes.append('axis fixes: %d' % fixed)
    # 4. the helper goes in after the imports and the first definitions: before the line that reads the open map
    anchor = re.search(r"^open_map = ", source, re.M)
    if not anchor:
        anchor = re.search(r"^if unwrap\(await call_tool", source, re.M)
    if not anchor:
        return source, notes + ['NO PLACE FOR THE HELPER: not rewritten']
    source = source[:anchor.start()] + HELPER + source[anchor.start():]
    return source, notes


def main():
    dry = '--dry-run' in sys.argv
    for name in CHECKS:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print(name, ': not there')
            continue
        before = io.open(path, encoding='utf-8').read()
        after, notes = rewrite(before)
        ok = True
        try:
            import ast
            compile(after, name, 'exec', flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        except SyntaxError as error:
            ok = False
            notes.append('DOES NOT COMPILE: %s' % error)
        left = len(re.findall(r'Lvl_HeroSampleCrowd', after))
        print('%s: %s; old map named %d time(s)%s' % (name, '; '.join(notes), left, '' if ok else ' -> NOT WRITTEN'))
        if ok and not dry and after != before:
            io.open(path, 'w', encoding='utf-8', newline='').write(after)


if __name__ == '__main__':
    main()
