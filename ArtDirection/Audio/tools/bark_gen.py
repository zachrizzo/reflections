"""Per-voice barks, possessed mutters and fillers: every voice gets its OWN wording of each intent (no line is shared).

    python bark_gen.py draft      draft voice/script/barks.json for every roster voice (resumes)
    python bark_gen.py plan       print the line counts per group
Groups match the game's bark groups (NPC archetypes) and FindVoiceCue(Actor, Group):
    Civilian_Fear (civilians), Guard_Alert + Guard_Attack (guards), Soldier_Command (soldiers), Tarnished_Mutter (all,
    played when the NPC is taken), Filler (all: a short beat before answering the Silverer).
The canon sheet's citizen barks (ArtDirection/Submission/canon.md) are INTENTS here, never literal lines.
After drafting, run uniq_fix.py to rewrite any line that collides with another speaker's.
Key: ~/.gemini/api_key (read inside gemini_tts only; never printed or stored).
"""
import sys, os, json, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_tts as G
import conv_gen as CG
import uniq_check as U

OUT = os.path.join(CG.SCRIPT, "barks.json")

# group -> (who, per voice, max words, situation, intents, good examples of the register; never reused verbatim)
GROUPS = {
    "Civilian_Fear": ("civilian", 3, 8,
        "shouted the instant they are frightened by sudden spellwork or a tarnished person, or are hurt; panicked and short",
        ["urge everyone to run", "call for help", "tell people to get indoors or hide", "they have just seen burning eyes / "
         "someone has turned", "warn people not to let it touch them", "beg not to be hurt",
         "fear for someone close to them (children, family, a friend)", "the light or lanterns failing around them"],
        ["Mum! MUM, where are you?", "Get the shutters down!", "Not me, please, not me!", "Watch! Somebody fetch the watch!"]),
    "Guard_Alert": ("guard", 3, 8,
        "a city watch guard spotting trouble in the street: loud, commanding, suspicious",
        ["challenge a stranger", "call out spellwork in the street", "order someone to stand down or show their hands",
         "sense something is wrong and warn the others", "order bystanders to clear the street"],
        ["Oi! You, stop right there!", "Hands where I can see them!", "Clear the street, all of you!", "Something's off. Eyes open."]),
    "Guard_Attack": ("guard", 2, 7,
        "a city watch guard charging into a fight: shouted, aggressive, decisive",
        ["announce an arrest", "rally the watch to attack", "order a takedown"],
        ["Watch, with me! Now!", "You're nicked, caster!", "Bring them down!"]),
    "Soldier_Command": ("soldier", 4, 7,
        "a soldier barking orders to their squad over the din of battle: shouted, clipped, urgent",
        ["hold the line / shields", "flank or move", "fall back and regroup", "push forward",
         "casters: loose spells now", "cover a wounded comrade", "rally for their side"],
        ["Shields! Hold!", "Left side, go, go!", "Back to the wall, regroup!", "Casters, loose!", "Tam's down, cover him!"]),
    "Tarnished_Mutter": ("all", 2, 6,
        "murmured by this person after the Tarnish has taken them: hollow, slow, as if something else moves the mouth; "
        "it speaks as 'we', is amused and patient, and talks about stillness, dullness, spreading and seeing. Eerie, never gory",
        ["tell the victim to stay still", "say we see you", "invite them to let it spread", "tell them not to shine",
         "admire the face it now wears", "say the glass is cracking"],
        ["Shh... stay still...", "We see you, little light.", "Such a good face... ours now.", "Let it in..."]),
    "Filler": ("all", 2, 4,
        "the first beat of their answer when a stranger suddenly speaks to them: a hesitation or surprised acknowledgement "
        "that leads into ANY answer, so it must not answer anything, give an order or mention a specific object",
        ["thinking before answering", "caught off guard"],
        ["Hm? Oh, yes?", "Er... well, now...", "Sorry, love, what?", "Right... let me think."]),
    # --- reactions to spell physics, heat and battle (orchestrator batch, 2026-11-14 evening) ---
    "React_Hurt": ("all", 2, 5,
        "cried out the instant this person is hit and hurt by a spell, a blow or a fall but stays on their feet: sharp, "
        "pained and breathless",
        ["a sharp cry, then a word about what hit them", "pain, then a plea to stop", "angry at being hit",
         "shocked that they were hurt", "clutching where it hurts"],
        ["Agh! My shoulder!", "Ow... stop, STOP!", "Ah! What was THAT?", "Nngh... that stung."]),
    "React_Knocked": ("all", 2, 5,
        "blurted as this person is thrown off their feet by a blast, a wave of water or a heavy blow and lands hard",
        ["winded on landing", "flailing in the air", "dazed on the ground", "trying to get back up"],
        ["Whoa... oof!", "Ugh... my back...", "Can't... breathe...", "Ah! Down I go!"]),
    "React_Burning": ("all", 3, 6,
        "screamed by this person while their clothes are on fire: raw panic, begging for water or help; it repeats "
        "every couple of seconds while they burn, so each line must work on its own",
        ["scream for water", "beg someone to put it out", "pure panic: it burns", "try to beat out the flames",
         "call out for someone they love"],
        ["Water! WATER!", "Get it off me! Get it OFF!", "It burns! Help me!", "Somebody, PUT IT OUT!"]),
    "React_Shocked": ("all", 2, 4,
        "forced out through clenched teeth while lightning locks this person's muscles: strangled, stuttering and jerky",
        ["cannot move", "a stuttered plea to stop", "a strangled cry", "gritted-teeth fear"],
        ["Can't... MOVE!", "St-stop it!", "Gnnh... ah-AH!", "Make it... stop..."]),
    "React_Death": ("all", 2, 5,
        "the last breath of a person struck down for good: fading and quiet, or a cry cut short; never gory",
        ["call for someone they love", "disbelief", "a cry cut short", "a quiet last word about home or their work"],
        ["Mum... I'm sorry...", "No... not yet...", "Tell Ada... I...", "Ahh... so cold..."]),
    "React_Effort": ("all", 2, 3,
        "WORDLESS sounds of physical strain: getting up off the ground, shoving, swinging or lifting",
        ["a straining grunt", "a short, sharp effort", "a pained push back up"],
        ["Hnngh!", "Hup!", "Nngh... ahh.", "Hah!"]),
    "Heat_CallGuards": ("civilian", 2, 8,
        "shouted by a witness who has just seen the Silverer (the player, a young man) hurt or kill someone in the street: "
        "calling for the guards or the watch, frightened and outraged",
        ["shout for the guards", "point the Silverer out to everyone", "outrage at what he did",
         "tell someone to fetch the watch", "say who he hurt (a neighbour, a stallholder, a stranger)"],
        ["Guards! GUARDS! Over here!", "The Silverer's killing people!", "Somebody fetch the watch, quick!",
         "He burned old Tam! I saw it!"]),
    "Heat_Halt": ("guard", 3, 7,
        "shouted by a guard straight at the Silverer (the player, a young man) who has just attacked people: ordering him to "
        "stop, surrender or drop it; firm and loud, addressing him directly",
        ["order the Silverer to halt", "order him to drop the shard or stop casting", "announce his arrest",
         "warn him that force is coming", "tell him to come quietly"],
        ["Halt, Silverer! Not one more step!", "Drop the shard. NOW.", "You're under arrest, Silverer!",
         "Come quietly or we'll make you."]),
    "Heat_Alarm": ("soldier", 2, 7,
        "a soldier raising the alarm that the Silverer (the player, a young man) has turned on the people: alerting the "
        "squad and calling everyone to arms",
        ["sound the alarm", "point out where he is", "call the squad to arms", "warn that he is dangerous"],
        ["Alarm! The Silverer's turned!", "To arms! It's him, by the well!", "Squad, on me! Hostile caster!",
         "He's dangerous, keep your distance!"]),
    # squads' battle events (soldier-squads session fires one group per event)
    "Soldier_Charge": ("soldier", 2, 6,
        "shouted by a soldier as their squad breaks formation and charges the enemy: fierce and rallying",
        ["a battle cry for their own side of the city", "order the charge"],
        ["For the Gilt! CHARGE!", "With me, NOW!", "Break ranks, take them!"]),
    "Soldier_Hold": ("soldier", 1, 6,
        "a soldier steadying the line as the squad's casters open a volley: steady and commanding",
        ["order the volley or hold the line steady"],
        ["Casters, LOOSE!", "Hold... hold... NOW!"]),
    "Soldier_AllyDown": ("soldier", 1, 6,
        "a soldier seeing a squadmate fall beside them: shocked and urgent, the grief cut short",
        ["call out that a comrade has fallen"],
        ["Man down! Cover him!", "No! Tam's DOWN!"]),
    "Soldier_EnemyDown": ("soldier", 2, 6,
        "a soldier as the enemy they were fighting drops: grim satisfaction, short",
        ["confirm the enemy is down", "move straight on to the next"],
        ["Got one!", "That's one. NEXT!"]),
    "Soldier_Retreat": ("soldier", 1, 6,
        "a soldier standing the squad down after losing the target: grudging and wary",
        ["order the stand-down and regroup"],
        ["Lost them. Fall in!", "Back to the line, lads."]),
    "Soldier_Victory": ("soldier", 1, 6,
        "a soldier when the fight is won and nobody is left: relief and pride, catching their breath",
        ["mark the win"],
        ["That's the lot. Well fought!", "It's done. Breathe."]),
}
WORDLESS = {"React_Effort"}  # vocal sounds only: exempt from the no-shared-phrase rule and from the transcript check
EVERY_INTENT = {"Soldier_Charge", "Soldier_Hold", "Soldier_AllyDown", "Soldier_EnemyDown", "Soldier_Retreat",
                "Soldier_Victory"}  # groups whose intents must all be covered by every voice (one line per intent, no rotation)
CANON_EXAMPLES = {
    "Pewterside": '"Did you see their eyes?" / "Someone get help!" / "Get inside, quick!"',
    "Giltside": '"Silverer! Thank the light." / "The lanterns are going dark!" / "Keep the children close."',
    "Frostside": '"Another one\'s turned." / "Don\'t let it touch you." / "The cold\'s coming again."',
    "Tarnished": '"Stay... still..." / "We see you."',
}


WORDLESS_RULE = ("These are WORDLESS: write only the sound itself as letters (grunts, gasps, efforts such as Hnngh!, Hup!, "
                 "Nngh... ahh., Hah!, Ugh!, Oof!), 1 to 3 sounds, no real words at all. Vary them per person.")
WORDED_RULE = ("Every line must include at least one real word (a cry alone such as \"Agh!\" is not enough), may start with a "
               "short cry, and must be easy to say through pain or panic. Keep each one personal to this speaker.")


def groups_for(v):
    a = v["Archetype"]
    return [g for g, spec in GROUPS.items() if spec[0] in (a, "all")]


def intents_for(v, group, k):
    """Rotate intents across voices so every intent is used and neighbours differ."""
    n, pool = GROUPS[group][1], GROUPS[group][4]
    if group in EVERY_INTENT:
        return list(pool[:n])
    return [pool[(k * n + j) % len(pool)] for j in range(n)]


def person(v):
    return (f"{v['VoiceId']}: {v['Role']}, {'woman' if v['Sex'] == 'F' else 'man'}, {v['AgeBand']} age, "
            f"{v['Attitude']}, lives in {v['Side']}")


def draft_batch(key, group, batch, avoid):
    who, n, maxw, situation, _intents, good = GROUPS[group]
    people = "\n".join(f"{person(v)}; intents: " + "; ".join(intents) for v, intents in batch)
    canon = CANON_EXAMPLES["Tarnished"] if group == "Tarnished_Mutter" else (
        "; ".join(f"{s}: {e}" for s, e in CANON_EXAMPLES.items() if s != "Tarnished") if group == "Civilian_Fear" else "")
    prompt = f"""{CG.CANON}

You are a screenwriter for a grounded fantasy game. Write the "{group}" lines: {situation}.
For EACH person below write exactly {n} lines, one per listed intent. At most {maxw} words per line.
Quality first:
- Sound like a real person in that moment: idiomatic, plain everyday words, instantly clear when heard once in passing.
- Personality comes from small concrete touches: how they address people (love, mate, pet, sir, lads, a squadmate's
  first name), a word from their trade, something from their own side of the city. Never from odd metaphors, poetic
  phrasing, fancy vocabulary or jokes that need explaining.
- Teen-safe: no gore or injury detail, nothing about blood, veins or self-harm, no slurs, no oaths, no swearing.
- Every person must sound different, so no two lines may be the same or near-copies, but never make a line strange
  just to be different.
The register to aim for (examples only, do not reuse): {" / ".join(f'"{g}"' for g in good)}
{f"Canon lines showing the intent (write new wording, never these exact lines): {canon}" if canon else ""}
People:
{people}
{WORDLESS_RULE if group in WORDLESS else WORDED_RULE if group.startswith("React_") else ""}
Give each line a delivery "style" of at most 6 words (emotion, volume and pace only; never age, accent or gender).
You may CAPITALISE one word for emphasis and use "..." for hesitation.
Return JSON: {{"voices": [{{"id": "V001", "lines": [{{"text": "...", "style": "..."}}]}}]}}"""
    intents_of = {v["VoiceId"]: intents for v, intents in batch}
    for attempt in range(3):
        try:
            o = CG.gen_json(key, prompt, temperature=0.8)
        except Exception as e:
            print(group, "err", G.scrub(e, key)[:150], flush=True); time.sleep(8); continue
        res = {}
        for item in o.get("voices", []):
            got = [{"Text": t["text"].strip(), "Style": t.get("style", "").strip()} for t in item.get("lines", [])
                   if isinstance(t, dict) and CG.clean_ok(t.get("text", ""), maxw) and CG.C_ok(t.get("style", "x"))
                   and (group != "Filler" or len(U.norm(t.get("text", "")).split()) >= 2)
                   and (U.is_wordless(t.get("text", "")) if group in WORDLESS
                        else not U.is_wordless(t.get("text", "")) if group.startswith("React_") else True)]
            if len(got) >= n:
                its = intents_of.get(item.get("id"), [])
                res[item.get("id")] = [dict(x, Intent=its[i]) if i < len(its) else x for i, x in enumerate(got[:n])]
        if all(v["VoiceId"] in res for v, _ in batch):
            return res
    return res


def draft():
    key = G.load_key()
    r = CG.roster()
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    used = {U.norm(t) for _, _, t in U.collect()}
    for group in GROUPS:
        voices = [v for v in r if group in groups_for(v)]
        todo = [(v, intents_for(v, group, k)) for k, v in enumerate(voices) if group not in out.get(v["VoiceId"], {})]
        batches = [todo[i:i + 8] for i in range(0, len(todo), 8)]
        # run 3 at a time; each wave sees the lines the previous waves wrote
        for w in range(0, len(batches), 3):
            wave = batches[w:w + 3]
            with ThreadPoolExecutor(3) as ex:
                results = list(ex.map(lambda b: draft_batch(key, group, b, used), wave))
            for res in results:
                for vid, items in res.items():
                    out.setdefault(vid, {})[group] = items
                    used.update(U.norm(x["Text"]) for x in items)
            json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        have = sum(1 for v in voices if group in out.get(v["VoiceId"], {}))
        print(group, have, "/", len(voices), "voices", flush=True)


def plan():
    r = CG.roster()
    tot = 0
    for g, spec in GROUPS.items():
        nv = sum(1 for v in r if g in groups_for(v))
        print(f"{g:18s} {nv:4d} voices x {spec[1]} = {nv * spec[1]}")
        tot += nv * spec[1]
    print("total", tot)


if __name__ == "__main__":
    {"draft": draft, "plan": plan}[sys.argv[1]]()
