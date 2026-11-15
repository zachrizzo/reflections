"""Writes ../conversations.md = conversations_seeds.md + the bark tables rendered from ../people.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); STORY = os.path.dirname(HERE)
people = json.load(open(os.path.join(STORY, "people.json"), encoding="utf-8"))
seeds = open(os.path.join(HERE, "conversations_seeds.md"), encoding="utf-8").read().rstrip()
INTENTS = [("greet", "the Silverer comes within talk range, or the player starts a conversation"),
           ("idle", "a calm remark to nobody (npc-unify's Remark trigger)"),
           ("see_tarnished", "sees a tarnished or a host within about 15 m"),
           ("flee", "starts fleeing"),
           ("spell_near", "a spell lands or is cast within about 6 m"),
           ("thanks", "the Silverer cured or saved someone near them, or finished their quest"),
           ("dread", "the infection band is rising or brink (replaces idle)"),
           ("farewell", "the player ends a conversation or walks away"),
           ("witness_crime", "sees the Silverer hurt or kill someone (Lives WitnessedCrime / NPC OnPlayerCrime)"),
           ("flee_silverer", "flees from the Silverer: after a crime, or when their opinion and the Silverer's heat are bad"),
           ("call_guards", "shouts for help after a crime: the Watch, the Coal Lane constable, the Wall Company; soldiers rally their own"),
           ("knocked_down", "knocked off their feet: a blast, a shove, a hit reaction or ragdoll they get up from"),
           ("on_fire", "set alight by a fire spell or burning ground"),
           ("shocked", "hit by lightning or a shock spell"),
           ("mourning", "grieving someone the player killed: near the body, or the next time the player talks to them (Greet_Grieving)"),
           ("battle_1", "soldiers only: squad engaged (battle order 1)"),
           ("battle_2", "soldiers only: squad engaged (battle order 2)"),
           ("patrol_1", "soldiers only: walking a patrol block"),
           ("patrol_2", "soldiers only: walking a patrol block"),
           ("enemy_down", "soldiers only: a tarnished goes down to steel (it stays dead)")]
out = [seeds, "", "<!-- BARKS: generated from people.json by tools/build_conversations.py; edit people_src.py, not this section -->",
       "## Barks, by person", "",
       "Fifteen bark intents per named person (eight base, seven for the open-world systems), plus four battle and patrol barks for soldiers, in that person's voice. The audio session bakes one wave per line, as `SCue_VO_Bark_<VoiceId>_<intent>`, and npc-unify plays them. Generated crowd people use their roster voice's own lines instead.", "",
       "| Intent | Plays when |", "|---|---|"] + [f"| `{k}` | {v} |" for k, v in INTENTS] + [""]
for side in ("Giltside", "Pewterside", "Frostside"):
    out.append(f"### {side}"); out.append("")
    for p in [p for p in people["people"] if p["side"] == side]:
        where = f", found in {p['found_in']}" if p.get("found_in") else ""
        out.append(f"**{p['name']}** (`{p['id']}`, {p['voice_id']}, {p['job']}{where}). {p['personality']['speech_style']}")
        out.append("")
        out.append("| Intent | Line |"); out.append("|---|---|")
        for k, _ in INTENTS:
            if k in p["barks"]:
                out.append(f"| {k} | \"{p['barks'][k]}\" |")
        for extra in ("cured_lines", "tarnished_lines"):
            for i, l in enumerate(p["story"].get(extra, []), 1):
                out.append(f"| {extra[:-6]} {i} | \"{l}\" |")
        out.append("")
open(os.path.join(STORY, "conversations.md"), "w", encoding="utf-8").write("\n".join(out))
print("wrote conversations.md")
