"""Builds ../quests.json (quest-system format, ArtDirection/Quests/README.md "Writing quests (JSON)") from the line
tables in ../main-quest.md and ../side-quests.md. Lines are objects {id, speaker, text}; voice cue = SCue_VO_<id>."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); STORY = os.path.dirname(HERE)

LINES = {}
for f in ("main-quest.md", "side-quests.md"):
    for row in open(os.path.join(STORY, f), encoding="utf-8"):
        cells = [c.strip() for c in row.split("|")]
        if len(cells) < 4 or not re.fullmatch(r"(MQ|SQ)\w*_\w+", cells[1] or ""):
            continue
        m = re.search(r'"(.+)"', cells[-2])
        if m:
            LINES[cells[1]] = {"id": cells[1], "speaker": cells[2], "text": m.group(1)}
used = set()

def L(*ids):
    out = []
    for i in ids:
        assert i in LINES, i
        used.add(i); out.append(LINES[i])
    return out

def obj(type, text, **kw):
    return {"type": type, "text": text, **kw}

def step(id, title, description, objectives, lines=(), speaker=None, **kw):
    s = {"id": id, "title": title, "description": description, "objectives": objectives}
    if lines: s["lines"] = list(lines)
    if speaker: s["speaker"] = speaker
    s.update(kw)
    return s

MAIN = {
    "id": "main", "main": True, "title": "The Mirror Made Whole",
    "summary": "Bring the three mirror pages together, make the mirror whole, and burn the Tarnish out of Lanthorne.",
    "side": "Giltside",
    "steps": [
        step("intro", "Lantern Law", "Dusk bell. The Lamp Companies are marching again, and Ilse wants me on Lantern Row.",
             [obj("event", "Watch", target="CutsceneDone", arg="Intro", timeout=4)]),
        step("lantern_row", "Lantern Row", "Ilse made me cast at a lamp post like I was twelve again. She's frightened. She doesn't get frightened.",
             [obj("talkTo", "Find Ilse Varrow on Lantern Row", target="ilse_varrow", marker="Spot_LanternRow")],
             lines=L("MQ01_01", "MQ01_02", "MQ01_03", "MQ01_04"), speaker="ilse_varrow"),
        step("cast", "Lantern Row", "Light's the only thing it hates.",
             [obj("spellHit", "Cast a spell", spell="Any", target="Spot_LanternRow", radius=2500)],
             lines=L("MQ01_05"), speaker="ilse_varrow", linesOn="complete"),
        step("first_face", "The First Face", "It took Jory in the middle of Bell Square. Light brought him back. I didn't know it could.",
             [obj("goTo", "Find the burning eyes", target="Spot_BellSquare", radius=1200)],
             lines=L("MQ02_01"), speaker="wren_hale", startOn={"event": "VillainFirstHost"}, cutsceneOnComplete="BurningEyes"),
        step("cure_jory", "The First Face", "Light burns it out, if you're quick.",
             [obj("spellHit", "Burn the Tarnish out of Jory", target="jory_pell", requireInfected=True, cure=True,
                  fallbackText="Burn the Tarnish out of them", fallbackTarget="Infected")],
             lines=L("MQ02_02", "MQ02_03"), linesOnComplete=L("MQ02_05", "MQ02_06"), linesOnFail=L("MQ02_07")),
        step("through_glass", "Through the Glass", "One page in each side. The first is in Pewterside. I'm going down through the glass.",
             [obj("event", "Find a Pewterside shard", target="ShardCollected", arg="Pewterside",
                  hints=["Drifters bring them through. Ask under the Lantern Gate."]),
              obj("worldJump", "Step down into Pewterside", side="Pewterside")],
             lines=L("MQ03_01", "MQ03_02", "MQ03_03", "MQ03_04"), speaker="ilse_varrow", ordered=True,
             optionalTalk={"kit_marrow": L("MQ03_05"), "jory_pell": L("MQ02_04")}, linesOnObjective={"0": L("MQ03_06")}),
        step("dull_as_ever", "Dull as Ever", "Pewterside's grey as a spoon and twice as stubborn. The first page was on the Weigh-House roof, under eleven years of pigeons.",
             [obj("goTo", "Find the Old Weigh-House", target="Spot_WeighHouseCorner", radius=1500, optional=True),
              obj("event", "Climb to the Weigh-House roof", target="PageFound", arg="Pewterside", marker="Tower_Pewterside")],
             optionalTalk={"ivy_harker": L("MQ04_01", "MQ04_02"), "winnie_cobb": L("MQ04_03"), "horace_pratt": L("MQ04_04")},
             cutsceneOnFirstPage="FirstPage"),
        step("hold_line", "Hold the Line", "We held the Lantern Gate. Three people walked away with their own eyes. Maud didn't say thank you, which means she meant it.",
             [obj("worldJump", "Step back up into Giltside", side="Giltside"),
              obj("spellHit", "Hold the Lantern Gate: burn the Tarnish out of 3 people", target="Infected", cure=True, count=3,
                  marker="Spot_LanternGate", radius=4000, spawn="Infected", spawnCount=3)],
             ordered=True, lines=L("MQ05_03"), speaker="maud_kettering",
             progressLines={"1": L("MQ05_04"), "2": L("MQ05_05")}, meterLines={"0.75": L("MQ05_06")}, squadLines=L("MQ05_07"),
             ifCutsceneSkipped={"FirstPage": L("MQ05_01", "MQ05_02")}),
        step("key", "The Key Where Light Won't Go Out", "Maud hid the tower key under a lamp that never goes out. She's been guarding it from her own captain's face.",
             [obj("event", "Find the Gilt Tower key", target="KeyFound", arg="GiltTowerKey")],
             lines=L("MQ06_01", "MQ06_02", "MQ06_03", "MQ06_04"), speaker="maud_kettering", linesOnComplete=L("MQ06_05")),
        step("gilt_tower", "The Gilt Tower", "The second page was in the Gilt Tower, where it's always been. The Tarnish says I'm building it a door.",
             [obj("goTo", "Open the Gilt Tower", target="Tower_Giltside", radius=400),
              obj("event", "Take the page inside the tower", target="PageFound", arg="Giltside")],
             ordered=True, cutsceneOnDoorOpened="GiltTower", linesOnObjective={"1": L("MQ07_01")}),
        step("cracked_crown", "The Cracked Crown", "Third leaf, in the cracked tower. The mirror is whole. Now it burns.",
             [obj("worldJump", "Step up into Frostside from inside the tower", side="Frostside"),
              obj("event", "Take the last page", target="BookComplete")],
             ordered=True, lines=L("MQ08_01", "MQ08_02", "MQ08_03"), speaker="ilse_varrow",
             linesOnObjective={"0": L("MQ08_04", "MQ08_05")}),
        step("let_the_light_through", "Let the Light Through", "It's gone. I looked into the whole mirror, and the only face in it was mine.",
             [obj("event", "Climb to the top of the Frost Tower", target="FinaleStarted", marker="Tower_Frostside"),
              obj("event", "Burn out the Tarnish with the Final Spell", target="BossDefeated")],
             ordered=True),
    ],
}

def sq(id, title, summary, giver, side, steps, reward, requires=None, requiresUnlocks=None, offer=(), turnIn=(), fail=None, **kw):
    q = {"id": id, "title": title, "summary": summary, "giver": giver, "side": side,
         "offer": list(offer), "reward": reward, "steps": steps}
    if turnIn is False:
        q["turnIn"] = False
    else:
        q["turnInLines"] = list(turnIn)
    if requires: q["requires"] = requires
    if requiresUnlocks: q["requiresUnlocks"] = requiresUnlocks
    if fail: q["fail"] = fail
    q.update(kw)
    return q

SIDE = [
    sq("sq1_cellar", "The Cellar at the Lamplight", "Goldie has kept her tarnished husband chained in the inn's cellar for nine days.",
       "goldie_fairweather", "Giltside", [
           step("cellar", "Down the Stairs", "Hal's been in the cellar nine days. Goldie feeds him through a hatch.",
                [obj("goTo", "Go down to the Lamplight's cellar", target="Spot_LamplightCellar", radius=400)],
                lines=L("SQ1_04"), speaker="hal_fairweather", linesAt="arrive"),
           step("cure", "Hal", "The chain gave.",
                [obj("spellHit", "Burn the Tarnish out of Hal", target="hal_fairweather", requireInfected=True, cure=True)],
                lines=L("SQ1_05"), speaker="hal_fairweather", endHoldOnStart="hal_fairweather",
                linesOnComplete=L("SQ1_06", "SQ1_07"), failIfDies="hal_fairweather")],
       {"coins": 1, "coinSide": "Pewterside", "reputation": {"goldie_fairweather": 15}, "unlocks": ["Hal_Home"]},
       requiresUnlocks=["Quest_main.first_face"], offer=L("SQ1_01", "SQ1_02", "SQ1_03"), turnIn=L("SQ1_08", "SQ1_09"),
       fail=L("SQ1_F1"), afterLine=L("SQ1_10"), startsTarnished=["hal_fairweather"], scriptedHold=["hal_fairweather"]),
    sq("sq2_humming", "After the Humming", "Jory can't play. His fiddle is lying in Bell Square, and two tarnished stand over it.",
       "jory_pell", "Giltside", [
           step("fiddle", "Bell Square", "Someone's standing over it. Two someones.",
                [obj("spellHit", "Burn the Tarnish out of the people by the fiddle", target="Infected", cure=True, count=2,
                     marker="Spot_BellSquare", radius=1500, spawn="Infected", spawnCount=2),
                 obj("collect", "Pick up Jory's fiddle", target="Fiddle", marker="Item_Fiddle")],
                lines=L("SQ2_03"), speaker="wren_hale", linesOnComplete=L("SQ2_04")),
           step("bring", "Bring It Home", "Bridge is cracked. Strings are fine.",
                [obj("deliver", "Bring the fiddle to Jory", item="Fiddle", target="jory_pell")])],
       {"reputation": {"jory_pell": 15}, "unlocks": ["Jory_Plays"]},
       requiresUnlocks=["Quest_main.cure_jory"], requiresAlive=["jory_pell"], offer=L("SQ2_01", "SQ2_02"), turnIn=L("SQ2_05", "SQ2_06")),
    sq("sq3_letters", "Letters Through the Glass", "Nell, a guard who hides that she's a drifter, writes to the mother she lost through a rift.",
       "nell_bramley", "Giltside", [
           step("deliver", "Coal Lane", "Edie Bramley. She'd be old now.",
                [obj("worldJump", "Step down into Pewterside", side="Pewterside"),
                 obj("deliver", "Give Edie Bramley the letter at the Coal Lane tram stop", item="Letter", target="edie_bramley", marker="Spot_CoalLaneStop")],
                ordered=True, giveItems=["Letter"], linesOnComplete=L("SQ3_04", "SQ3_05"), linesIfTargetWasCured=L("SQ3_06"),
                rewardOnComplete={"coins": 1, "coinSide": "Giltside", "items": ["TicketStub"]}),
           step("return", "Two Tickets", "She kept the ticket. Fourteen years.",
                [obj("deliver", "Bring the ticket to Nell", item="TicketStub", target="nell_bramley")])],
       {"reputation": {"nell_bramley": 15, "edie_bramley": 15}, "unlocks": ["Nell_Letter"]},
       requiresUnlocks=["Quest_main.through_glass"], offer=L("SQ3_01", "SQ3_02", "SQ3_03"), turnIn=L("SQ3_07"),
       afterLine=L("SQ3_08", "SQ3_09")),
    sq("sq4_queen", "The Queen of Coal Lane", "Hester won't go indoors until her subjects are home, and the tarnished are coming down Coal Lane.",
       "hester_quaile", "Pewterside", [
           step("defend", "Wrong Feet", "Something's coming down the lane.",
                [obj("protect", "Defend Coal Lane: keep the tarnished off Hester's doorstep", target="Spot_HesterDoorstep",
                     radius=800, seconds=60, spawn="Infected", spawnCount=4)],
                lines=L("SQ4_04"), speaker="sid_kettle", linesAt={"30": L("SQ4_05")},
                ifInfected={"hester_quaile": {"text": "Burn the Tarnish out of Hester", "linesOnCure": L("SQ4_06")}},
                linesOnComplete=L("SQ4_07"), failIfDies="hester_quaile"),
           step("walter", "Fifty-One Years", "Walter has carried a ring for fifty-one years.",
                [obj("talkTo", "Talk to Walter", target="walter_dunmore")], lines=L("SQ4_08", "SQ4_09"))],
       {"reputation": {"hester_quaile": 20, "walter_dunmore": 10, "sid_kettle": 10}, "unlocks": ["Coal_Lane_Safe"]},
       offer=L("SQ4_01", "SQ4_02", "SQ4_03"), fail=L("SQ4_F1"), afterLine=L("SQ4_10"), turnIn=False,
       autoOffer={"onFirstWorldJump": "Pewterside", "orInfectionBand": "spreading"}),
    sq("sq5_eyeglass", "The Glazier's Eyeglass", "Professor Quell needs the Glazier's lens. An old woman in Pewterside has it, and wants only to be listened to.",
       "tobias_quell", "Giltside", [
           step("find_ada", "The Fish Steps", "A family in Pewterside kept it. Pollard.",
                [obj("talkTo", "Find Ada Pollard on the Fish Steps in Pewterside", target="ada_pollard", marker="Spot_FishSteps")],
                lines=L("SQ5_03"), speaker="ada_pollard", linesOn="complete"),
           step("listen", "The Whole Story", "Nobody ever hears the end of one of Ada's stories.",
                [obj("protect", "Listen to Ada's story", target="ada_pollard", radius=400, seconds=25)],
                lines=L("SQ5_04", "SQ5_05", "SQ5_06"), speaker="ada_pollard", pauseLinesWhenOutside=True,
                linesOnComplete=L("SQ5_07"), rewardOnComplete={"items": ["Eyeglass"]}),
           step("bring", "Into, Not At", "The last page asks the Silverer to look into the whole mirror.",
                [obj("deliver", "Bring the eyeglass to Professor Quell", item="Eyeglass", target="tobias_quell")])],
       {"reputation": {"tobias_quell": 10, "ada_pollard": 20}, "unlocks": ["Eyeglass"]},
       requiresUnlocks=["Quest_main.through_glass"], offer=L("SQ5_01", "SQ5_02"), turnIn=L("SQ5_08", "SQ5_09", "SQ5_10"),
       afterLine=L("SQ5_11")),
    sq("sq6_whole", "Something Whole", "At the dusk bell the Third Company will push the drifters back into the canal rift. Something is coming through it tonight.",
       "kit_marrow", "Giltside", [
           step("ros", "The Rift Post", "Rift's humming loud tonight.",
                [obj("talkTo", "Talk to Ros at the canal rift post", target="ros_thrale", marker="Spot_CanalRift")],
                lines=L("SQ6_03", "SQ6_04"), speaker="ros_thrale", linesOn="complete"),
           step("defend", "Under the Gate", "Nobody's going in the canal.",
                [obj("protect", "Defend the drifters' camp", target="Spot_DrifterCamp", radius=1200, seconds=90,
                     spawn="Infected", spawnCount=4, spawnMarker="Spot_CanalRift")],
                lines=L("SQ6_05"), speaker="wren_hale", linesAt={"45": L("SQ6_06", "SQ6_07")},
                ifInfected={"fen_lowry": {"text": "Burn the Tarnish out of Fen", "linesOnCure": L("SQ6_08")}}),
           step("brask", "New Orders", "They held the gate with us.",
                [obj("talkTo", "Talk to Captain Brask", target="sela_brask", marker="Spot_DrifterCamp")],
                lines=L("SQ6_09"), speaker="sela_brask", linesOn="complete")],
       {"coins": 1, "coinSide": "Frostside", "reputation": {"kit_marrow": 15, "fen_lowry": 15, "sela_brask": 10}, "unlocks": ["Drifters_Stay"]},
       requiresUnlocks=["Quest_main.hold_line"], offer=L("SQ6_01", "SQ6_02"), turnIn=L("SQ6_10"), fail=L("SQ6_F1"),
       failNote="Kit or Fen dying does not fail the quest; the survivor says SQ6_F1 and the reward is still given.",
       afterLine=L("SQ6_11")),
    sq("sq7_lamps", "The Lamps on Bell Lane", "Corin promised his dying father Bell Lane would never go dark. He's been watering the oil.",
       "corin_ashby", "Giltside", [
           step("relight", "Three Lamps", "Three lamps on Bell Lane won't take.",
                [obj("spellHit", "Relight the failing lamps on Bell Lane", spell="Fire", target="Spot_BellLaneLamp1", radius=300),
                 obj("spellHit", "Relight the failing lamps on Bell Lane", spell="Fire", target="Spot_BellLaneLamp2", radius=300),
                 obj("spellHit", "Relight the failing lamps on Bell Lane", spell="Fire", target="Spot_BellLaneLamp3", radius=300)],
                linesOnObjective={"0": L("SQ7_03")}, spawnAfterObjective={"1": {"spawn": "Infected", "spawnCount": 1}}),
           step("confess", "Watered Oil", "He's been watering the oil.",
                [obj("talkTo", "Talk to Corin", target="corin_ashby")], lines=L("SQ7_04"), speaker="corin_ashby"),
           step("oil", "Real Oil", "Dov has oil. Corin never asked.",
                [obj("talkTo", "Ask Dov for lamp oil", target="dov_merriman", marker="Spot_LanternRow"),
                 obj("deliver", "Bring the oil to Corin", item="LampOil", target="corin_ashby")],
                ordered=True, linesOnObjective={"0": L("SQ7_05")}, giveItemsOnObjective={"0": ["LampOil"]})],
       {"reputation": {"corin_ashby": 15, "dov_merriman": 5}, "unlocks": ["Bell_Lane_Lit"]},
       requiresUnlocks=["Quest_main.lantern_row"], offer=L("SQ7_01", "SQ7_02"), turnIn=L("SQ7_06"), afterLine=L("SQ7_07")),
    sq("sq8_shed", "Sorrel's Shed", "A Frostside healer keeps three tarnished tied in her shed. One is a Giltside dancer who fell through a rift.",
       "sorrel_vey", "Frostside", [
           step("shed", "The Shed", "Three of them. Tied, fed, alive.",
                [obj("goTo", "Go to Sorrel's shed", target="Spot_SorrelShed", radius=500)], lines=L("SQ8_02"), speaker="sorrel_vey", linesAt="arrive"),
           step("cure", "Patients", "Light is the only thing that's ever worked.",
                [obj("spellHit", "Burn the Tarnish out of Sorrel's patients", target="Infected", marker="Spot_SorrelShed", radius=800,
                     cure=True, count=3, spawn="Infected", spawnCount=2, includePerson="petra_lisle", scriptedHold=True)],
                progressLines={"1": L("SQ8_03")}),
           step("petra", "Gold in Your Coat", "Petra kept dancing, in her head, the whole time.",
                [obj("talkTo", "Talk to Petra", target="petra_lisle")], lines=L("SQ8_04", "SQ8_05"), speaker="petra_lisle"),
           step("lucan", "She's Alive", "Lucan needs to hear it.",
                [obj("talkTo", "Tell Lucan that Petra is alive", target="lucan_marlowe", marker="Spot_ArchiveSteps")],
                lines=L("SQ8_06", "SQ8_07"), speaker="lucan_marlowe", linesOn="complete")],
       {"reputation": {"sorrel_vey": 15, "petra_lisle": 20, "lucan_marlowe": 20}, "unlocks": ["Petra_Found"]},
       offer=L("SQ8_01"), turnIn=False, afterLine=L("SQ8_08"), startsTarnished=["petra_lisle"],
       availability="Only when the hero is in Frostside's streets (not inside the sealed Frost Tower). Skip if the map has no Frostside streets."),
    sq("sq9_unsigned", "Unsigned", "For fifty years someone has left wool on Barnaby's doorstep, unsigned.",
       "barnaby_thrale", "Giltside", [
           step("odette", "A Customer", "Good wool. No name.",
                [obj("talkTo", "Ask Odette Vane about the wool", target="odette_vane", marker="Spot_ArchiveSteps")],
                lines=L("SQ9_02"), speaker="odette_vane", linesOn="complete", rewardOnComplete={"items": ["Wool"]}),
           step("wool", "Gold Selvedge", "Only one hand hems like that.",
                [obj("deliver", "Bring the wool to Barnaby", item="Wool", target="barnaby_thrale")],
                linesOnComplete=L("SQ9_03", "SQ9_04"), rewardOnComplete={"items": ["Shears"]}),
           step("shears", "The Seam Held", "Barnaby's first shears.",
                [obj("deliver", "Bring the shears to Odette", item="Shears", target="odette_vane")],
                linesOnComplete=L("SQ9_05", "SQ9_06"))],
       {"reputation": {"barnaby_thrale": 10, "odette_vane": 10}, "unlocks": ["Seam_Held"]},
       requiresUnlocks=["Quest_main.lantern_row"], offer=L("SQ9_01"), turnIn=False, afterLine=L("SQ9_07")),
    # ---- 2026-11-14 batch: the open-world systems (heat, allied soldiers, consequences)
    sq("sq10_watch_book", "The Watch Book", "Maud keeps a page on every Silverer. Wren's has marks on it.",
       "maud_kettering", "Giltside", [
           step("good_marks", "Good Marks", "Two faces back at the gate, and Nell to speak for me.",
                [obj("spellHit", "Burn the Tarnish out of 2 people at the Lantern Gate", target="Infected", cure=True, count=2,
                     marker="Spot_LanternGate", radius=4000, spawn="Infected", spawnCount=2),
                 obj("talkTo", "Ask Nell Bramley to vouch for you", target="nell_bramley", marker="Spot_LanternGate")],
                lines=L("SQ10_04"), speaker="maud_kettering", linesOnObjective={"1": L("SQ10_05")}, linesOnComplete=L("SQ10_06")),
           step("bad_marks", "Bad Marks", "Hollis has eleven statements about me. Eleven.",
                [obj("talkTo", "Find Corporal Greave on Bell Lane", target="hollis_greave", marker="Spot_BellLane")],
                lines=L("SQ10_07"), speaker="hollis_greave", choicePerson="hollis_greave",
                choices=[{"id": "read", "text": "Read them to me. All of them.", "response": L("SQ10_08")[0], "next": "End",
                          "reward": {"reputation": {"maud_kettering": 10}},
                          "journal": "Hollis read me every one. I'd rather have the bruise than the page."},
                         {"id": "lose", "text": "Lose the page, Hollis.", "response": L("SQ10_09")[0], "next": "End",
                          "reward": {"reputation": {"maud_kettering": -10, "hollis_greave": 5}, "unlocks": ["Watch_Page_Lost"]},
                          "journal": "The page went in the canal. Maud will know. Maud always knows."}])],
       {"reputation": {"maud_kettering": 10, "nell_bramley": 5}, "unlocks": ["Silverer_RecordClean"]},
       requiresUnlocks=["Quest_main.key"], offer=L("SQ10_01", "SQ10_02"), accept=L("SQ10_03"), turnIn=L("SQ10_10"),
       afterLine=L("SQ10_11"),
       availability="Best offered when the Silverer has heat (any witnessed crime); otherwise offer after main.key. "
                    "On Unlocked Silverer_RecordClean: reset the Silverer's heat, let witnesses' crime memories fade, stop guards hunting."),
    sq("sq11_shield_and_lamp", "Shield and Lamp", "The Third Lamp Company walks the canal rift tonight, and the Sergeant wants the Silverer in the middle of the line.",
       "aldric_mayne", "Giltside", [
           step("muster", "The Third Marches", "Mayne, Bram, Damaris with the lantern, Emeric with the horn, and Cosmo, first week.",
                [obj("goTo", "Muster with the Third Company at the canal rift", target="Spot_CanalRift", radius=1500)],
                lines=L("SQ11_03"), speaker="damaris_hobb", linesOnComplete=L("SQ11_04"),
                squadNote="If squads are live, the Third Company squad (Brask's soldiers: aldric_mayne, bram_tolley, cosmo_fennick, "
                          "damaris_hobb, emeric_dunstan) forms at Spot_CanalRift as the hero's ally for steps muster to pinned."),
           step("hold", "Steel and Light", "Steel pins them. I burn them clean.",
                [obj("protect", "Hold the canal rift with the Third (60 s)", target="Spot_CanalRift", radius=1200, seconds=60,
                     spawn="Infected", spawnCount=4),
                 obj("spellHit", "Burn the Tarnish out of 3 people", target="Infected", cure=True, count=3,
                     marker="Spot_CanalRift", radius=3000, progressLines={"1": L("SQ11_06"), "2": L("SQ11_07")})],
                lines=L("SQ11_05"), speaker="wren_hale", failIfDies="cosmo_fennick"),
           step("pinned", "Pinned", "Bram had one on his shield. It wasn't fighting. It was looking at Cosmo.",
                [obj("talkTo", "Talk to Captain Brask", target="sela_brask", marker="Spot_CanalRift", spawn="Infected", spawnCount=1)],
                lines=L("SQ11_08", "SQ11_09", "SQ11_10"), choicePerson="sela_brask", failIfDies="cosmo_fennick",
                choices=[{"id": "burn", "text": "Hold him. I'll burn it out.", "response": L("SQ11_11")[0], "next": "cure_wat",
                          "journal": "Thirty seconds, Brask said."},
                         {"id": "cut", "text": "Cut it down.", "response": L("SQ11_12")[0], "next": "cut_wat",
                          "journal": "Brask wouldn't let her people do it. So it was me."}]),
           step("cure_wat", "Wat", "Wat Fennick, back with his own eyes. His mother is going to scream.",
                [obj("spellHit", "Burn the Tarnish out of Wat", target="Infected", cure=True, count=1, marker="Spot_CanalRift", radius=3000)],
                linesOnComplete=L("SQ11_13", "SQ11_14"), next="End", ifKilledNext="cut_wat"),
           step("cut_wat", "Wat", "He knew Cosmo. Right up to the end, he knew him.",
                [obj("defeat", "Cut down the pinned tarnished", target="Infected", count=1, marker="Spot_CanalRift", radius=3000)],
                linesOnComplete=L("SQ11_15", "SQ11_16"), next="End")],
       {"coins": 1, "coinSide": "Giltside", "reputation": {"sela_brask": 15, "aldric_mayne": 10}},
       requiresUnlocks=["Quest_main.hold_line"], offer=L("SQ11_01", "SQ11_02"), turnIn=L("SQ11_17"), fail=L("SQ11_F1"),
       afterLine=L("SQ11_18"), offerIfWanted=L("SQ11_W1"),
       availability="Refuse with offerIfWanted (SQ11_W1) while the Silverer is wanted (heat high, or a witnessed crime and no "
                    "Silverer_RecordClean). Otherwise offer after main.hold_line."),
    sq("sq12_empty_chair", "The Empty Chair", "Cosmo's chair at the Third Company's table is empty, and the canal fog is talking in his brother's voice.",
       "damaris_hobb", "Giltside", [
           step("canal", "The Edge", "Cosmo took Wat's cap and his spear and went to the canal.",
                [obj("goTo", "Find Cosmo at the canal rift", target="Spot_CanalRift", radius=1500),
                 obj("talkTo", "Talk to Cosmo", target="cosmo_fennick", marker="Spot_CanalRift")],
                ordered=True, lines=L("SQ12_03"), speaker="wren_hale", linesOnObjective={"0": L("SQ12_05"), "1": L("SQ12_04")},
                choicePerson="cosmo_fennick", failIfDies="cosmo_fennick",
                choices=[{"id": "own", "text": "I did it. Hate me. Not yourself.", "response": L("SQ12_06")[0], "next": "mother",
                          "reward": {"reputation": {"cosmo_fennick": -10, "sela_brask": 10}},
                          "journal": "He hates me. He let me help him up anyway."},
                         {"id": "gone", "text": "He was gone before the shield touched him.", "response": L("SQ12_07")[0], "next": "mother",
                          "journal": "I told him Wat was already gone. Neither of us believed it."}]),
           step("mother", "Marjory", "Somebody has to tell their mother. It should be me.",
                [obj("talkTo", "Tell Marjory Fennick on Lantern Row", target="marjory_fennick", marker="Spot_LanternRow")],
                lines=L("SQ12_08"), speaker="marjory_fennick", choicePerson="marjory_fennick",
                choices=[{"id": "truth", "text": "I cut him down. It was my call.", "response": L("SQ12_09")[0], "next": "End",
                          "reward": {"reputation": {"marjory_fennick": -25}, "unlocks": ["Fennick_Truth"]},
                          "journal": "I told her the truth. She told me to get away from her barrow."},
                         {"id": "lie", "text": "The Tarnish took him. We couldn't reach him.", "response": L("SQ12_10")[0], "next": "End",
                          "reward": {"reputation": {"marjory_fennick": 10}, "unlocks": ["Fennick_Lie"]},
                          "journal": "I lied to her, and she thanked me for it. Cosmo heard every word."}])],
       {"reputation": {"damaris_hobb": 10}},
       requiresUnlocks=["Quest_sq11_shield_and_lamp.cut_wat"], offer=L("SQ12_01", "SQ12_02"), turnIn=L("SQ12_11"),
       fail=L("SQ12_F1"), afterLine=L("SQ12_12"),
       availability="Only after SQ11 ended with cut_wat. A player who burned Wat clean never sees this quest."),
]

ITEMS = {"Letter": "Nell's letter to her mother", "TicketStub": "A fourteen-year-old tram ticket stub", "Fiddle": "Jory's fiddle",
         "Eyeglass": "The Glazier's eyeglass", "LampOil": "A small barrel of real lamp oil", "Wool": "A bolt of wool with a gold selvedge",
         "Shears": "Barnaby's first shears"}

out = {
    "_readme": "Story quests for the quest system, built by ArtDirection/Story/tools/build_quests.py from main-quest.md and side-quests.md. "
               "Every line is {id, speaker, text}; its voice cue is /Game/Audio/Jam/Voice/Cues/SCue_VO_<id>. Fields beyond the README format "
               "(cutscene*, lines*On*, ifInfected, startsTarnished, scriptedHold, afterLine, giveItems, rewardOnComplete, failIfDies, "
               "ordered, optional, requireInfected/cure) are story intent: support what's cheap, ignore the rest, and the quest still works. "
               "Person ids are people.json ids (actor tag Person_<id>); markers use the Story Marker names in people.json -> markers.story_names.",
    "_cutsceneTriggers": {"Intro": "new game (game flow's PlayNewGameIntro; the quest only waits, 4 s timeout)", "BurningEyes": "main.first_face goTo complete",
                          "FirstPage": "first PageFound of any side", "GiltTower": "the Gilt Tower sealed door's OnOpened",
                          "MirrorWhole": "BookComplete (played by the cutscene/game side, not the quest)", "Ending": "villain-finale calls it after the dissolve"},
    "items": [{"id": k, "name": v} for k, v in ITEMS.items()],
    "quests": [MAIN] + SIDE,
}
unused = sorted(set(LINES) - used)
json.dump(out, open(os.path.join(STORY, "quests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"wrote quests.json: {len(out['quests'])} quests, {len(used)} lines used, {len(LINES)} parsed")
print("not placed in quests.json (ambient/villain/lose lines):", unused)
