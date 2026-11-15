"""Voice script for Reflections (OpenAI TTS). Single source of truth for lines, speakers, delivery and cue groups.

Names follow ArtDirection/Submission/rename-table.md: Lanthorne; Pewterside / Giltside / Frostside; mirror shards;
step through; the Tarnish (called "it"), tarnished hosts; Wren Hale, the Silverer; the mirror; the Final Spell.
Never "London" or "Three Londons".
"""

MODEL = "gpt-4o-mini-tts"

# speaker -> (voice, delivery instructions, post-FX)
SPEAKERS = {
    "Tarnish": ("onyx",
                "You are the Tarnish, an ancient, cold presence speaking through a stolen body. Speak low, slow and close to the "
                "microphone, half-whispered and intimate, with quiet amusement and contempt. Never rush. Let words trail off.",
                "tarnish"),
    "TarnishDeath": ("onyx",
                     "You are the Tarnish, being burned away by light. Strained, cracking, fading in and out, bitter to the last "
                     "breath, the final words almost a whisper.",
                     "tarnish"),
    "Narrator": ("fable",
                 "A warm, friendly guide giving the player brief tips. Natural conversational pace, clear and concise, with a touch "
                 "of wonder. Keep pauses short. Never sound like an advert.",
                 "narrator"),
    "CivilianA": ("coral", "A frightened city dweller caught in sudden magic. Breathless, panicked, high-pitched, words tumbling out.", "bark"),
    "CivilianB": ("ash", "A frightened city dweller caught in sudden magic. Breathless, panicked, voice cracking, urgent.", "bark"),
    "GuardA": ("echo", "A city watch guard. Firm, loud and commanding, suspicious, projecting across a street.", "bark"),
    "GuardB": ("sage", "A city watch guard. Sharp, authoritative, alert and clipped, projecting across a street.", "bark"),
    "SoldierA": ("verse", "A battle-hardened soldier in a war-torn city, shouting orders over the din of battle. Urgent, gravelly, clipped.", "bark"),
    "SoldierB": ("marin", "A veteran soldier shouting orders mid-battle. Loud, decisive, urgent, slightly hoarse.", "bark"),
    "CivilianTalkA": ("coral", "A wary city dweller answering a stranger in passing. Quick, quiet and polite, a little nervous, natural pace.", "bark"),
    "CivilianTalkB": ("ash", "A tired city dweller answering a stranger in passing. Low-key, quiet, a little uneasy, natural pace.", "bark"),
    "GuardTalkA": ("echo", "A city watch guard answering a passer-by. Calm, firm and dry, not shouting, a little suspicious.", "bark"),
    "GuardTalkB": ("sage", "A city watch guard answering a passer-by. Calm, clipped and matter-of-fact, not shouting.", "bark"),
    "SoldierTalkA": ("verse", "A soldier on duty answering a civilian. Curt, steady, gruff, at speaking volume, not shouting.", "bark"),
    "SoldierTalkB": ("marin", "A soldier on duty answering a civilian. Brisk, steady and no-nonsense, at speaking volume.", "bark"),
    "TarnishedA": ("alloy", "A possessed, hollow person. Flat, slow, murmured, dreamy and wrong, as if someone else is moving the mouth.", "tarnished"),
    "TarnishedB": ("ballad", "A possessed person whispering. Flat, slow, eerie, almost lifeless, drawn-out syllables.", "tarnished"),
}

# group -> (owner, event, cue mode). "random": one cue picks among all lines in the group; "each": one cue per line.
GROUPS = {
    "Tarnish_Taunt": ("villain", "Taunt while possessing a host or during the boss fight", "random"),
    "Tarnish_Hop": ("villain", "The Tarnish takes a new host (play with SCue_Villain_Hop)", "random"),
    "Tarnish_Manifest": ("villain", "True form appears (play after SCue_Villain_Manifest)", "random"),
    "Tarnish_PhaseTwo": ("villain", "Boss phase two: it tears loose from its shroud", "random"),
    "Tarnish_Cured": ("villain", "The player burns the Tarnish out of someone (at most once per 10 s)", "random"),
    "Tarnish_Hurt": ("villain", "Hit by the Final Spell (with SCue_Villain_Hurt)", "random"),
    "Tarnish_Death": ("villain", "Death (with SCue_Villain_Death)", "random"),
    "Civilian_Fear": ("npc", "Civilian / Timid starts Fleeing or is attacked", "random"),
    "Guard_Alert": ("npc", "Guard enters Alert / Investigating", "random"),
    "Guard_Attack": ("npc", "Guard switches to Attacking", "random"),
    "Soldier_Command": ("soldier", "Soldier / SoldierCaster squad command (on engage, every few seconds in combat)", "random"),
    "Tarnished_Mutter": ("npc", "Tarnished (Infected / VillainHost) idle or aggro mutter (layer with SCue_Infected_Growl)", "random"),
    "Civilian_Talk": ("talk", "Calm civilian answers when the player talks to them (NPC dialogue fallback)", "random"),
    "Guard_Talk": ("talk", "Calm guard answers when the player talks to them (NPC dialogue fallback)", "random"),
    "Soldier_Talk": ("talk", "Calm soldier answers when the player talks to them (NPC dialogue fallback)", "random"),
    "Narrator": ("gameflow", "Narration and one-time tips (one cue per line)", "each"),
}

# (line id, group, speaker, text)
LINES = [
    # --- The Tarnish ---
    ("Tarnish_Taunt_01", "Tarnish_Taunt", "Tarnish", "Every face in Lanthorne will wear me, sooner or later."),
    ("Tarnish_Taunt_02", "Tarnish_Taunt", "Tarnish", "You polish. I spread."),
    ("Tarnish_Taunt_03", "Tarnish_Taunt", "Tarnish", "Look closer, Silverer. I'm already on you."),
    ("Tarnish_Taunt_04", "Tarnish_Taunt", "Tarnish", "Three reflections... and I am in all of them."),
    ("Tarnish_Taunt_05", "Tarnish_Taunt", "Tarnish", "Break the glass if you like. I'll still be here."),
    ("Tarnish_Taunt_06", "Tarnish_Taunt", "Tarnish", "This one is warm. I think I'll keep it."),
    ("Tarnish_Hop_01", "Tarnish_Hop", "Tarnish", "A new face. How fitting."),
    ("Tarnish_Hop_02", "Tarnish_Hop", "Tarnish", "Not that one... this one."),
    ("Tarnish_Hop_03", "Tarnish_Hop", "Tarnish", "Did you miss me?"),
    ("Tarnish_Manifest_01", "Tarnish_Manifest", "Tarnish", "Enough masks. See what Lanthorne was always hiding."),
    ("Tarnish_Manifest_02", "Tarnish_Manifest", "Tarnish", "Its maker wanted one true Lanthorne. I'll make the final cut."),
    ("Tarnish_PhaseTwo_01", "Tarnish_PhaseTwo", "Tarnish", "You only scratched the surface."),
    ("Tarnish_Cured_01", "Tarnish_Cured", "Tarnish", "You can't polish them all."),
    ("Tarnish_Cured_02", "Tarnish_Cured", "Tarnish", "There are always more faces."),
    ("Tarnish_Hurt_01", "Tarnish_Hurt", "TarnishDeath", "No... that light!"),
    ("Tarnish_Hurt_02", "Tarnish_Hurt", "TarnishDeath", "Stop... shining!"),
    ("Tarnish_Hurt_03", "Tarnish_Hurt", "TarnishDeath", "It burns... it burns clean..."),
    ("Tarnish_Death_01", "Tarnish_Death", "TarnishDeath", "Polish all you like... everything dulls again..."),
    ("Tarnish_Death_02", "Tarnish_Death", "TarnishDeath", "I was... the truest reflection..."),
    # --- Civilians (fear) ---
    ("Civilian_Fear_01", "Civilian_Fear", "CivilianA", "Run! Get away from it!"),
    ("Civilian_Fear_02", "Civilian_Fear", "CivilianB", "Help! Somebody help!"),
    ("Civilian_Fear_03", "Civilian_Fear", "CivilianA", "Please, don't hurt me!"),
    ("Civilian_Fear_04", "Civilian_Fear", "CivilianB", "Magic! Get inside, get inside!"),
    ("Civilian_Fear_05", "Civilian_Fear", "CivilianA", "Its eyes... they're burning! Run!"),
    ("Civilian_Fear_06", "Civilian_Fear", "CivilianB", "No, no, no, no..."),
    # --- Guards ---
    ("Guard_Alert_01", "Guard_Alert", "GuardA", "Halt! Who goes there?"),
    ("Guard_Alert_02", "Guard_Alert", "GuardB", "Stop right there, caster!"),
    ("Guard_Alert_03", "Guard_Alert", "GuardA", "Spellwork in the street! Stand down!"),
    ("Guard_Attack_01", "Guard_Attack", "GuardB", "That's it, you're coming with us!"),
    ("Guard_Attack_02", "Guard_Attack", "GuardA", "Take them down!"),
    ("Guard_Attack_03", "Guard_Attack", "GuardB", "For the watch!"),
    # --- Soldiers (Giltside) ---
    ("Soldier_Command_01", "Soldier_Command", "SoldierA", "Shields up! Hold the line!"),
    ("Soldier_Command_02", "Soldier_Command", "SoldierB", "Casters, on me!"),
    ("Soldier_Command_03", "Soldier_Command", "SoldierA", "Flank left! Go, go!"),
    ("Soldier_Command_04", "Soldier_Command", "SoldierB", "Fall back! Regroup!"),
    ("Soldier_Command_05", "Soldier_Command", "SoldierA", "Loose your spells! Now!"),
    ("Soldier_Command_06", "Soldier_Command", "SoldierB", "Push forward! For Giltside!"),
    # --- Tarnished ---
    ("Tarnished_Mutter_01", "Tarnished_Mutter", "TarnishedA", "So... dull... so quiet..."),
    ("Tarnished_Mutter_02", "Tarnished_Mutter", "TarnishedB", "Hold still... let it spread..."),
    ("Tarnished_Mutter_03", "Tarnished_Mutter", "TarnishedA", "The glass is cracked... let it in..."),
    # --- Calm talk replies (NPC dialogue fallback) ---
    ("Civilian_Talk_01", "Civilian_Talk", "CivilianTalkA", "Can't stop now. Mind the glass."),
    ("Civilian_Talk_02", "Civilian_Talk", "CivilianTalkB", "Strange times. Keep out of the cold."),
    ("Civilian_Talk_03", "Civilian_Talk", "CivilianTalkA", "Keep your head down out here."),
    ("Guard_Talk_01", "Guard_Talk", "GuardTalkA", "Move along. The watch has eyes on you."),
    ("Guard_Talk_02", "Guard_Talk", "GuardTalkB", "No spellwork in the street. Understood?"),
    ("Guard_Talk_03", "Guard_Talk", "GuardTalkA", "Keep it quiet and you'll have no trouble."),
    ("Soldier_Talk_01", "Soldier_Talk", "SoldierTalkA", "Keep your distance. We march on orders."),
    ("Soldier_Talk_02", "Soldier_Talk", "SoldierTalkB", "Not now. We're holding this street."),
    ("Soldier_Talk_03", "Soldier_Talk", "SoldierTalkA", "Stay behind the line."),
    # --- Narrator / tips (game flow) ---
    ("Narrator_Intro", "Narrator", "Narrator", "Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut."),
    ("Narrator_Tip_Aim", "Narrator", "Narrator", "Hold to aim. The glow shows where your spell will land."),
    ("Narrator_Tip_Cast", "Narrator", "Narrator", "Then cast. Each element answers differently: fire burns, ice slows, lightning leaps."),
    ("Narrator_Tip_Shard", "Narrator", "Narrator", "Mirror shards let you step through. Stepping through also takes most of your magic."),
    ("Narrator_Tip_StepThrough", "Narrator", "Narrator", "Step up into the next side, or down into the one below. Pewterside, Giltside, Frostside: the same streets, in three different lights."),
    ("Narrator_Tip_Crafting", "Narrator", "Narrator", "Build your own spells. Choose a form, an element, and how it behaves, then cast what you made."),
    ("Narrator_FirstHost", "Narrator", "Narrator", "The Tarnish has taken a face. Watch for the burning eyes."),
    ("Narrator_MirrorWhole", "Narrator", "Narrator", "The mirror is whole. The Final Spell is yours. Now burn out the Tarnish."),
    ("Narrator_FinalSpellHint", "Narrator", "Narrator", "Ordinary spells barely touch it. Only the Final Spell can burn it out."),
    ("Narrator_Victory", "Narrator", "Narrator", "The Tarnish is burned out. Lanthorne is itself again."),
]

BANNED = ("london", "three londons")

# Spoken input differs from the script only to fix pronunciation; subtitles always keep the script text.
PHONETIC = {"Lanthorne": "Lant-horn", "Frostside": "Frost-side", "Giltside": "Gilt-side", "Pewterside": "Pewter-side"}
SAY = {}  # per-line full overrides, if ever needed


def spoken(lid, text):
    if lid in SAY:
        return SAY[lid]
    for a, b in PHONETIC.items():
        text = text.replace(a, b)
    return text

# Realtime voices (gpt-realtime family). The realtime voice set has no onyx/fable, so these differ from SPEAKERS' TTS voices.
RT_VOICE = {"CivilianTalkA": "coral", "CivilianTalkB": "ash", "GuardTalkA": "echo", "GuardTalkB": "sage",
            "SoldierTalkA": "verse", "SoldierTalkB": "ballad", "Tarnish": "cedar", "TarnishDeath": "cedar", "Narrator": "marin", "CivilianA": "coral", "CivilianB": "ash",
            "GuardA": "echo", "GuardB": "sage", "SoldierA": "verse", "SoldierB": "ballad", "TarnishedA": "alloy", "TarnishedB": "shimmer"}

PRONOUNCE = ("Pronunciation: Lanthorne is LANT-horn; Pewterside is PYOO-ter-side; Giltside is GILT-side; Frostside is FROST-side; "
             "Silverer is SIL-ver-er; Tarnish is TAR-nish.")

ACTOR_RULES = ("You are a professional voice actor recording a single line for a video game. You will be given exactly one line. "
               "Perform it once, word for word, exactly as written: do not add, drop, change, translate or repeat any words, and do not "
               "greet, answer, explain or ask anything. Speak only the line, in English, in character.")


def check():
    ids = [l[0] for l in LINES]
    assert len(ids) == len(set(ids)), "duplicate line id"
    for lid, grp, spk, text in LINES:
        assert grp in GROUPS, lid
        assert spk in SPEAKERS, lid
        assert not any(b in text.lower() for b in BANNED), lid
    return len(LINES)




# ======================================================================================================================
# Per-NPC voices (v2). Each NPC has a stable voice slot (sex + index) chosen by the NPC system; every bark group exists
# in every slot, so an NPC always speaks with ITS voice. The single-voice NPC lines above become legacy (not rebuilt).
# ======================================================================================================================
SLOTS = {  # slot -> (realtime voice, TTS fallback voice, persona)
    "F1": ("coral", "coral", "a young woman in her twenties with a quick, bright voice"),
    "F2": ("sage", "sage", "a woman in her forties with a firm, slightly husky, practical voice"),
    "F3": ("shimmer", "shimmer", "an older woman in her sixties with a thinner, warm but shaky voice"),
    "M1": ("ash", "ash", "a young man in his twenties with a quick, tense voice"),
    "M2": ("echo", "echo", "a man in his forties with a steady, gruff voice"),
    "M3": ("verse", "verse", "an older man in his sixties with a deep, weathered, slower voice"),
}

NPC_GROUPS = {  # group -> (owner, event, delivery, fx, lines per slot, line pool)
    "Civilian_Fear": ("npc", "Civilian/Timid starts Fleeing or is hit",
                      "A frightened city dweller caught in sudden magic: panicked, breathless, urgent.", "bark", 2,
                      ["Run! Get away from it!", "Help! Somebody help!", "Please, don't hurt me!", "Magic! Get inside, get inside!",
                       "Its eyes... they're burning! Run!", "No, no, no, no..."]),
    "Guard_Alert": ("npc", "Guard enters Alert / Investigating",
                    "A city watch guard spotting trouble: loud, commanding and suspicious, projecting across a street.", "bark", 2,
                    ["Halt! Who goes there?", "Stop right there, caster!", "Spellwork in the street! Stand down!",
                     "You there! Show me your hands!", "Something's wrong here. Stay sharp."]),
    "Guard_Attack": ("npc", "Guard switches to Attacking",
                     "A city watch guard charging into a fight: shouted, aggressive and decisive.", "bark", 1,
                     ["That's it, you're coming with us!", "Take them down!", "For the watch!"]),
    "Soldier_Command": ("soldier", "Soldier / SoldierCaster squad command (on engage, every few seconds in combat)",
                        "A soldier in a war-torn street barking orders to their squad over the din of battle: shouted, clipped, urgent.", "bark", 3,
                        ["Shields up! Hold the line!", "Casters, on me!", "Flank left! Go, go!", "Fall back! Regroup!",
                         "Loose your spells! Now!", "Push forward! For Giltside!"]),
    "Tarnished_Mutter": ("npc", "Tarnished (Infected / VillainHost) idle or aggro mutter (layer with SCue_Infected_Growl)",
                         "A person possessed by the Tarnish: hollow, flat, slow and murmured, as if someone else is moving the mouth.", "tarnished", 2,
                         ["So... dull... so quiet...", "Hold still... let it spread...", "The glass is cracked... let it in...",
                          "Join us... don't shine...", "We are... the Tarnish..."]),
    "Civilian_Talk": ("talk", "Calm civilian answer when the player talks to them",
                      "A city dweller answering a stranger in passing: quick, quiet, a little uneasy, natural pace.", "bark", 1,
                      ["Can't stop now. Mind the glass.", "Strange times. Keep out of the cold.", "Keep your head down out here."]),
    "Guard_Talk": ("talk", "Calm guard answer when the player talks to them",
                   "A city watch guard answering a passer-by: calm, firm and dry, not shouting.", "bark", 1,
                   ["Move along. The watch has eyes on you.", "No spellwork in the street. Understood?", "Keep it quiet and you'll have no trouble."]),
    "Soldier_Talk": ("talk", "Calm soldier answer when the player talks to them",
                     "A soldier on duty answering a civilian: curt, steady, at speaking volume, not shouting.", "bark", 1,
                     ["Keep your distance. We march on orders.", "Not now. We're holding this street.", "Stay behind the line."]),
}

LEGACY_NPC_GROUPS = {"Civilian_Fear", "Guard_Alert", "Guard_Attack", "Soldier_Command", "Tarnished_Mutter",
                     "Civilian_Talk", "Guard_Talk", "Soldier_Talk"}
LEGACY_LINES = [l for l in LINES if l[1] in LEGACY_NPC_GROUPS]
LINES = [l for l in LINES if l[1] not in LEGACY_NPC_GROUPS]
for _g in LEGACY_NPC_GROUPS:
    GROUPS.pop(_g, None)

for _si, (_slot, (_rv, _tv, _persona)) in enumerate(SLOTS.items()):
    for _g, (_owner, _event, _delivery, _fx, _n, _pool) in NPC_GROUPS.items():
        _spk = f"{_g}@{_slot}"
        SPEAKERS[_spk] = (_tv, f"You are {_persona}. {_delivery}", _fx)
        RT_VOICE[_spk] = _rv
        GROUPS[f"{_g}_{_slot}"] = (_owner, f"{_event}; voice slot {_slot}", "random")
        for _j in range(_n):
            _text = _pool[(_si * _n + _j + (_si // 3)) % len(_pool)]
            LINES.append((f"{_g}_{_slot}_{_j + 1}", f"{_g}_{_slot}", _spk, _text))


# The Tarnish's story lines (ArtDirection/Story via voice/script/story.json): same Tarnish voice and FX as above.
# One cue per line, /Game/Audio/Jam/Voice/Cues/SCue_VO_<LineId>; 2D/3D per line from story.json "Att".
def _story_tarnish():
    import json as _json, os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "voice", "script", "story.json")
    if not _os.path.exists(_p):
        return [], {}
    _s = _json.load(open(_p, encoding="utf-8")).get("Scripted", {})
    _ls = [(lid, "Story_Tarnish", "Tarnish", v["Text"]) for lid, v in sorted(_s.items())
           if v["Voice"] == "TARNISH" and not v.get("AliasOf")]
    return _ls, {lid: v.get("Att", "2D") for lid, v in _s.items() if v["Voice"] == "TARNISH"}


STORY_TARNISH_LINES, STORY_ATT = _story_tarnish()
if STORY_TARNISH_LINES:
    GROUPS["Story_Tarnish"] = ("villain", "Story lines (cutscenes, main quest); see ArtDirection/Story", "sequence")
    LINES += STORY_TARNISH_LINES

def base_group(group):
    """'Civilian_Fear_F1' -> 'Civilian_Fear' for slot groups; other groups unchanged."""
    head, _, tail = group.rpartition("_")
    return head if tail in SLOTS and head in NPC_GROUPS else group


if __name__ == "__main__":
    print(check(), "lines")
