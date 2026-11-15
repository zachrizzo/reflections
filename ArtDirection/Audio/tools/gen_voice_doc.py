"""Write ArtDirection/Audio/VoiceScript.md from voice_script.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_script as V
import json
MAN_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "manifest.json")
MAN = json.load(open(MAN_P)) if os.path.exists(MAN_P) else {}
ENGINES = sorted({m["engine"] for m in MAN.values() if "engine" in m})

OUT = r"C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Audio\VoiceScript.md"
OWN = {"villain": "villain session", "npc": "npc-unify (NPC reactions)", "soldier": "soldier-squads", "talk": "NPC dialogue session (talk-back fallback)", "gameflow": "game-flow-ui"}
L = []
w = L.append
w("# Reflections: voice script (OpenAI text-to-speech)")
w("")
w("Generated offline with OpenAI's realtime audio model (" + (", ".join(f"`{e}`" for e in ENGINES) if ENGINES else "`gpt-realtime-2.1`") +
  f"); `{V.MODEL}` is the fallback for any take whose transcript doesn't match the script word for word. Voices are AI-generated, not performed by "
  "actors; the credits and the itch page must say so (see `ArtDirection/Submission/ai-declaration.md`). Names follow "
  "`ArtDirection/Submission/canon.md`. The script is `ArtDirection/Audio/tools/voice_script.py`; edit lines there and run `realtime_tts.py`.")
w("")
w("**Prompt per line** (session instructions): the actor rules, then the speaker's character and delivery brief from the table below, then the pronunciation guide. The line itself is sent as the user message `Line: <text>`.")
w("")
w("> " + V.ACTOR_RULES)
w(">")
w("> " + V.PRONOUNCE)
w("")
w("## Speakers")
w("")
w("| Speaker | Realtime voice | Character and delivery brief | Post-FX |")
w("|---|---|---|---|")
for k, (voice, inst, fx) in V.SPEAKERS.items():
    if "@" in k or k not in {l[2] for l in V.LINES}:
        continue
    w(f"| {k} | `{V.RT_VOICE[k]}` | {inst} | {fx} |")
w("")
w("NPC bark speakers are `<Group>@<Slot>`: instructions = the slot persona + the group delivery (see below).")
w("")
w("## Per-NPC voice slots")
w("")
w("Every NPC keeps one voice slot (chosen by the NPC system from its sex): F1-F3 female, M1-M3 male. Each bark group exists in every slot "
  "as `SCue_VO_<Group>_<Slot>`; `SCue_VO_<Group>` (no slot) is a fallback that picks across all slots.")
w("")
w("| Slot | Realtime voice | Persona |")
w("|---|---|---|")
for sl, (rv, tv, persona) in V.SLOTS.items():
    w(f"| {sl} | `{rv}` | {persona} |")
w("")
w("## Cues and lines")
w("")
done_base = set()
for g, (owner, event, mode) in V.GROUPS.items():
    base = V.base_group(g)
    if base != g:
        if base in done_base:
            continue
        done_base.add(base)
        og, ev, delivery, fx, n, pool = V.NPC_GROUPS[base]
        w(f"### `SCue_VO_{base}_<Slot>` ({n} line(s) per slot; fallback `SCue_VO_{base}`)")
        w("")
        w(f"Owner: {OWN[og]}. When: {ev}. Delivery: {delivery}")
        w("")
        w("| Line id | Slot | Text | Engine / voice / tries |")
        w("|---|---|---|---|")
        for lid, grp, spk, text in V.LINES:
            if V.base_group(grp) == base:
                m = MAN.get(lid)
                eng = f"`{m['engine']}` / `{m['voice']}` / {m.get('tries', 1)}" if m and "engine" in m else "not generated"
                w(f"| `{lid}` | {grp.rsplit('_', 1)[1]} | {text} | {eng} |")
        w("")
        continue
    lines = [l for l in V.LINES if l[1] == g]
    if mode == "random":
        w(f"### `SCue_VO_{g}` ({len(lines)} lines, picked at random)")
    else:
        w(f"### Narrator ({len(lines)} cues, one per line: `SCue_VO_<LineId>`)")
    w("")
    w(f"Owner: {OWN[owner]}. When: {event}.")
    w("")
    w("| Line id | Speaker | Text | Engine / voice / tries |")
    w("|---|---|---|---|")
    for lid, _, spk, text in lines:
        m = MAN.get(lid)
        eng = f"`{m['engine']}` / `{m['voice']}` / {m.get('tries', 1)}" if m and "engine" in m else "not generated"
        w(f"| `{lid}` | {spk} | {text} | {eng} |")
    w("")
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print(OUT, V.check(), "lines")
