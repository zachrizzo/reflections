# Side quests

Owner: the story session. Built by the quest-system session. People are in [people.json](people.json) by id; conventions (the `Person_<id>` tags, `Mk_…` markers, "talk to") are as in [main-quest.md](main-quest.md#conventions).

There are nine short quests. Each grows out of one person's problem and uses only these mechanics:
- talk;
- go to a marker;
- step through;
- cast a spell (including the **cure-on-hit** rule: a spell hit returns a tarnished NPC's `OnNpcInfection` to `None`);
- rescue someone from the tarnished;
- find and deliver a quest item (the quest system's item pickup);
- defend a spot.

**Rewards** use what already exists:
- shards: `UReflectionsWorldLibrary::AwardCoin(World)`;
- reputation: `UReflectionsReputationSubsystem::AdjustReputation(Player, Delta)`;
- lore and journal text;
- changes to how people behave and what they say. The quest system sets a story flag; npc-lives and the barks read it.

| Id | Title | Side | Giver | Mechanics | Opens |
|---|---|---|---|---|---|
| SQ1 | The Cellar at the Lamplight | Giltside | Goldie Fairweather | talk, go to marker, rescue (cure) | after MQ02 |
| SQ2 | After the Humming | Giltside | Jory Pell | find item, cure, deliver | after MQ02, if Jory was cured |
| SQ3 | Letters Through the Glass | Giltside → Pewterside | Nell Bramley | deliver item across sides, step through | after MQ03 objective 1 |
| SQ4 | The Queen of Coal Lane | Pewterside | Hester Quaile | talk, defend a spot, rescue | first visit to Pewterside |
| SQ5 | The Glazier's Eyeglass | Giltside ↔ Pewterside | Prof. Tobias Quell | talk, listen, find and deliver | after MQ03 |
| SQ6 | Something Whole | Giltside | Kit Marrow | talk, defend a spot, rescue | after MQ05 starts |
| SQ7 | The Lamps on Bell Lane | Giltside | Corin Ashby | spells at markers, deliver | after MQ01 |
| SQ8 | Sorrel's Shed | Frostside | Sorrel Vey | go to marker, rescue ×3, deliver a message | holding a Frostside shard (from SQ6) and standing in Frostside's streets |
| SQ9 | Unsigned | Giltside | Barnaby Thrale | talk, deliver, deliver | after MQ01 |

Every quest can be skipped. None blocks the main quest. Lines have ids `SQx_nn`, and none repeats a line anywhere else in the story.

---

## SQ1 The Cellar at the Lamplight

**Hook:** Wren's landlady has kept her tarnished husband chained in the cellar for nine days, hoping for a miracle. She's ashamed and terrified, and she loves him.

- **Opens:** after MQ02, when Wren has learned that light cures. Goldie's next greeting becomes SQ1_01.
- **Steps:**
  1. "Talk to Goldie at the Lamplight" (`Person_goldie_fairweather` / `Mk_Gilt_Inn_Lamplight`).
  2. "Go down to the Lamplight's cellar" (`Mk_Gilt_Cellar_Lamplight`). Hal (`Person_hal_fairweather`) starts tarnished and in a scripted hold (`IsScripted`), so he can't be talked to.
  3. When Wren comes within 4 m, the hold ends ("the chain gives"). Hal is now a normal tarnished enemy.
  4. "Burn the Tarnish out of Hal". It completes on Hal's `OnNpcInfection` → `None`.
  5. "Tell Goldie". Talk to her.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ1_01 | goldie_fairweather | step 1 | "Sweetling. Is it true you can bring them back? Truly?" |
| SQ1_02 | goldie_fairweather | step 1 | "Hal's in the cellar. Nine days. Don't you dare tell Maud." |
| SQ1_03 | wren_hale | step 1 | "I won't. Give me the key." |
| SQ1_04 | hal_fairweather | step 2, tarnished, through the hatch | "Marigold... we are so cold down here." |
| SQ1_05 | hal_fairweather | step 3 | "Open the hatch. We only want to see you." |
| SQ1_06 | wren_hale | step 4, on cure | "Hal. Hal, look at me. Your own eyes." |
| SQ1_07 | hal_fairweather | after the cure | "Nine days in the dark, and you brought me up." (his `thanks` bark) |
| SQ1_08 | goldie_fairweather | step 5 | "I fed him through a hatch like a dog. Nine days. Nine." |
| SQ1_09 | goldie_fairweather | step 5 | "Take this. Hal kept it from the bridge. It's grey glass." |

- **Fail:** if Hal dies, the quest ends with SQ1_F1, and Goldie's barks use the `dread` line for the rest of the run.

| Id | Speaker | Line |
|---|---|---|
| SQ1_F1 | goldie_fairweather | "Don't. Don't say anything. Just go upstairs, Wren." |

- **Reward:** `AwardCoin(Gray)` (a Pewterside shard), +10 reputation. Story flag `Hal_Home`: Hal appears at the Lamplight bar on the `innkeeper` schedule's work marker, and Goldie's greeting changes to SQ1_10.

| Id | Speaker | Line |
|---|---|---|
| SQ1_10 | goldie_fairweather | "Hal's complaining about the ale again. Isn't it wonderful?" |

---

## SQ2 After the Humming

**Hook:** Jory is himself again, but he can't play. He dropped his fiddle when he was taken, and he still hears the Tarnish humming under every tune he thinks of.

- **Opens:** after MQ02, if Jory was cured. Jory stands at `Mk_Gilt_Inn_Lamplight`.
- **Steps:**
  1. "Talk to Jory".
  2. "Find Jory's fiddle in Bell Square" (`Mk_Gilt_Square_BellSquare`). Two tarnished stand near it; the quest system asks the villain or NPC system for them, or uses any tarnished within 30 m.
  3. "Burn the Tarnish out of the people by the fiddle (0/2)", or drive them off.
  4. Pick up the fiddle (quest item).
  5. "Bring the fiddle to Jory".
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ2_01 | jory_pell | step 1 | "I keep reaching for my fiddle, Ren. I left it in the square." |
| SQ2_02 | jory_pell | step 1 | "Every tune I think of, there's something humming under it." |
| SQ2_03 | wren_hale | step 2, in sight of it | "Someone's standing over it. Two someones." |
| SQ2_04 | wren_hale | step 4 | "Bridge is cracked. Strings are fine. He'll live." |
| SQ2_05 | jory_pell | step 5 | "You found it. Oh, you beauty. Hold still, let me try." |
| SQ2_06 | jory_pell | step 5, after a pause | "It's still humming. But I'm louder. I'm louder than it." |

- **Reward:** +10 reputation. Story flag `Jory_Plays`: the Lamplight plays fiddle music (an audio cue loop at the inn), Jory's lines use his `cured_lines`, and in CS06 his distant tune plays (CS06_06). If the flag is off, CS06_06 is skipped.

---

## SQ3 Letters Through the Glass

**Hook:** a young guard who hides that she's a drifter has written to the mother she lost through a rift fourteen years ago. The mother still rides the tram with an empty seat beside her.

- **Opens:** after MQ03 objective 1 (Wren has a Pewterside shard).
- **Steps:**
  1. "Talk to Nell at the Lantern Gate" (`Person_nell_bramley`). She gives the letter (quest item).
  2. "Find Edie Bramley at the Coal Lane tram stop in Pewterside" (`Person_edie_bramley` / `Mk_Pew_Stop_CoalLane`).
  3. "Give Edie the letter". Edie gives a ticket stub (quest item) and a Giltside shard.
  4. "Bring the ticket to Nell".
- **If Edie is tarnished** when Wren arrives (possible at high infection), cure her first. Her first line is then SQ3_06 instead of SQ3_04.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ3_01 | nell_bramley | step 1 | "Sorry, I mean, this is nothing. It's a letter. To Pewterside." |
| SQ3_02 | nell_bramley | step 1 | "Coal Lane. Edie Bramley. She'd be old now. If she's... if." |
| SQ3_03 | wren_hale | step 1 | "I'll find her. What do I tell her?" |
| SQ3_04 | edie_bramley | step 3 | "That's her hand. That's her writing. Nine years old, she was." |
| SQ3_05 | edie_bramley | step 3 | "Give her this. The stub from that day. And this glass came through when she went. Take it." |
| SQ3_06 | edie_bramley | cured first | "My head's full of other people's voices. You've got a letter? For me?" |
| SQ3_07 | nell_bramley | step 4 | "She kept the ticket. Fourteen years. Steady, Nell. Steady." |

- **Reward:** `AwardCoin(Red)` (a Giltside shard from Edie), +10 reputation. Story flag `Nell_Letter`: Nell's `idle` bark becomes SQ3_08, and Edie's becomes SQ3_09.

| Id | Speaker | Line |
|---|---|---|
| SQ3_08 | nell_bramley | "Next stop, Coal Lane. Mum used to say that. Funny." |
| SQ3_09 | edie_bramley | "Two tickets, please. One's for my girl. She's on the gold side." |

---

## SQ4 The Queen of Coal Lane

**Hook:** the street's self-appointed queen is going blind and won't go indoors until every one of "her subjects" is home. Tonight the tarnished are coming down Coal Lane. This is the whiteboard's "last Queen" idea (see [bible.md](bible.md#the-last-queen-idea-from-the-whiteboard)).

- **Opens:** on the first visit to Pewterside. Hester greets Wren, and the quest starts automatically if the Tarnish meter reaches the `spreading` band while Wren is in Pewterside.
- **Steps:**
  1. "Talk to Hester on her doorstep" (`Person_hester_quaile` / `Mk_Pew_Doorstep_Hester`).
  2. "Defend Coal Lane: keep the tarnished off Hester's doorstep (60 s)". The quest system asks the villain or NPC system for 3–4 tarnished hunters within 40 m of the marker. **(quest system)** The defence holds if no clean NPC within 8 m of the marker is converted.
  3. **If Hester is tarnished** during the defence: the objective changes to "Burn the Tarnish out of Hester", and completes on her cure.
  4. "Talk to Walter" (`Person_walter_dunmore`, at the stop or next to Hester).
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ4_01 | hester_quaile | step 1 | "My subjects are out after dark, young man. I won't go in till they're home." |
| SQ4_02 | hester_quaile | step 1 | "Something's coming down the lane. I can hear its feet. Wrong feet." |
| SQ4_03 | wren_hale | step 1 | "Stay on the step, Your Majesty. I've got the lane." |
| SQ4_04 | sid_kettle | defence starts | "Right. Nan stays behind me. Right." |
| SQ4_05 | walter_dunmore | defence, halfway | "That's check, you blasted things! Check!" |
| SQ4_06 | hester_quaile | Hester cured | "Was I... no. Don't tell me. The Queen was never gone." |
| SQ4_07 | hester_quaile | defence held | "My subjects are home. Every one. You may go." |
| SQ4_08 | walter_dunmore | step 4 | "Hester. Fifty-one years I've carried this. Will you blasted well have it?" |
| SQ4_09 | hester_quaile | after SQ4_08 | "Walter Dunmore. I can't see the ring. I can hear you shaking. Yes." |

- **Fail:** Hester dies. The quest fails with SQ4_F1, and Coal Lane's barks use `dread` for the rest of the run. The *optional* hard lose rule in the bible is not built by default.

| Id | Speaker | Line |
|---|---|---|
| SQ4_F1 | sid_kettle | "Nan. Nan? Right. Right. Right." |

- **Reward:** +15 reputation. Story flag `Coal_Lane_Safe`: Pewterside civilians on Coal Lane will use `warn_guards` for Wren at once, and Hester's greeting becomes SQ4_10.

| Id | Speaker | Line |
|---|---|---|
| SQ4_10 | hester_quaile | "Our royal Silverer. Walter, curtsey. Oh, don't, your knee." |

---

## SQ5 The Glazier's Eyeglass

**Hook:** a scholar needs a relic to read the mirror's riddle. The relic belongs to a lonely old woman, who wants nothing for it except someone to listen to her story to the end.

- **Opens:** after MQ03 (Wren can go to Pewterside).
- **Steps:**
  1. "Talk to Professor Quell on the Archive steps" (`Person_tobias_quell`).
  2. "Find Ada Pollard on the Fish Steps in Pewterside" (`Person_ada_pollard`).
  3. "Listen to Ada's story": stay within 4 m of her while SQ5_04 to SQ5_07 play (about 25 s). Walking away pauses the story, and coming back resumes it.
  4. She gives the eyeglass (quest item).
  5. "Bring the eyeglass to Professor Quell".
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ5_01 | tobias_quell | step 1 | "The Glazier ground a lens to read silvered script. Which is to say, the pages." |
| SQ5_02 | tobias_quell | step 1 | "A family in Pewterside kept it. Pollard. Find it, and I'll read what the pages say." |
| SQ5_03 | ada_pollard | step 2 | "The eyeglass? Oh, dearie. Sit down. It's a long story, isn't it, Arthur?" |
| SQ5_04 | ada_pollard | step 3 | "My granny's granny swept the Glazier's floor. Every morning, glass dust." |
| SQ5_05 | ada_pollard | step 3 | "The night of the cut, the Glazier put this in her apron and said, keep it from the dark." |
| SQ5_06 | ada_pollard | step 3 | "Nine of us have kept it. In a sugar tin, mostly. Arthur thought it was a button." |
| SQ5_07 | ada_pollard | step 3 | "You listened to the end. Nobody does. Here. Take it, dearie." |
| SQ5_08 | tobias_quell | step 5 | "Remarkable. With this, the script reads plain. Each page has a line, and the last one..." |
| SQ5_09 | tobias_quell | step 5 | "...says a Silverer must look into the whole mirror. Into it, not at it. I don't know what that costs." |
| SQ5_10 | wren_hale | step 5 | "Nine years of not looking. Seems about due." |

- **Reward:** +5 reputation and lore. The journal entry: "The last page asks the Silverer to look into the whole mirror." This sets up CS05 and the finale. Story flag `Eyeglass`: Ada's greeting becomes SQ5_11.

| Id | Speaker | Line |
|---|---|---|
| SQ5_11 | ada_pollard | "There's my good listener. Arthur, it's the Silverer. Sit, sit." |

---

## SQ6 Something Whole

**Hook:** two Frostside drifters are camped under the Lantern Gate. At the dusk bell the Third Company will push them back through the canal rift, into the cold. One of them wants to go home; the other will do anything not to. And something is coming through the rift tonight.

- **Opens:** after MQ05 starts, when Wren is back in Giltside.
- **Steps:**
  1. "Talk to Kit under the Lantern Gate" (`Person_kit_marrow` / `Mk_Gilt_Camp_UnderGate`).
  2. "Talk to Ros at the canal rift post" (`Person_ros_thrale` / `Mk_Gilt_Rift_Canal`).
  3. "Defend the drifters' camp (90 s)" at `Mk_Gilt_Camp_UnderGate`. Tarnished come "through the rift": the quest system asks the villain or NPC system for 4 tarnished near `Mk_Gilt_Rift_Canal`, and they hunt toward the camp. Ros and the Third Company squad help if squads are live.
  4. **Fen** (`Person_fen_lowry`): at 45 s she walks toward the rift, called by the voice. If she is converted, the objective "Burn the Tarnish out of Fen" is added.
  5. "Talk to Captain Brask" (`Person_sela_brask`, at the camp after the defence; else she speaks 2D).
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ6_01 | kit_marrow | step 1 | "Dusk bell, they send us back. Fen says she'll go in the canal first." |
| SQ6_02 | fen_lowry | step 1 | "Says who? I'm not going back. It's warm here. Warm." |
| SQ6_03 | ros_thrale | step 2 | "Orders are orders, glass-boy. I've been losing count of who goes past me." |
| SQ6_04 | ros_thrale | step 2 | "Rift's humming loud tonight. Something's coming through with the drifters." |
| SQ6_05 | wren_hale | step 3 starts | "Nobody's going in the canal. Hold here with me." |
| SQ6_06 | fen_lowry | step 4 | "It knows my name. It says it's warm where it is." |
| SQ6_07 | kit_marrow | step 4 | "Fen, don't! Don't answer it!" |
| SQ6_08 | fen_lowry | Fen cured | "It lied. It wasn't warm. It was nothing." |
| SQ6_09 | sela_brask | step 5 | "They held the gate with us. They stay. That's the new order." |
| SQ6_10 | kit_marrow | step 5 | "Here. It's whole, look. Not a crack in it. Frostside glass." |

- **Fail:** none. If Kit or Fen dies, the other gives SQ6_F1 and the reward.

| Id | Speaker | Line |
|---|---|---|
| SQ6_F1 | kit_marrow | "We came all this way. All this way for the cold to find us." |

- **Reward:** `AwardCoin(White)` (a Frostside shard, Kit's "whole thing"), +10 reputation. This shard lets Wren reach Frostside's streets early where the map allows, which opens SQ8. Story flag `Drifters_Stay`: Brask's `idle` bark becomes SQ6_11.

| Id | Speaker | Line |
|---|---|---|
| SQ6_11 | sela_brask | "Drifters on the gate roster. Never thought I'd write that." |

---

## SQ7 The Lamps on Bell Lane

**Hook:** a devout lamplighter promised his dying father that Bell Lane would never go dark. He has run out of oil and has been watering the lamps, and they are failing one by one, with the Tarnish waiting in the gaps.

- **Opens:** after MQ01.
- **Steps:**
  1. "Talk to Corin on Bell Lane" (`Person_corin_ashby` / `Mk_Gilt_Lane_BellLane`).
  2. "Relight the failing lamps on Bell Lane (0/3)": cast a fire spell within 3 m of each of `Mk_Gilt_Lane_BellLane_Lamp1`, `_Lamp2` and `_Lamp3`.
     - Fallback if there are no lamp markers: three points 8 m apart along the Bell Lane marker's forward axis.
     - **(quest system)** Any spell cast while Wren stands within 3 m of the point counts if the quest system can't tell elements apart.
     - A light VFX can mark each lamp as lit.
  3. After the second lamp, one tarnished steps "out of the unlit". Cure it or drive it off; this is optional.
  4. "Talk to Corin".
  5. "Ask Dov for lamp oil" (`Person_dov_merriman`, Lantern Row) → "Bring the oil to Corin" (quest item).
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ7_01 | corin_ashby | step 1 | "Three lamps on Bell Lane won't take. I've trimmed them. I've prayed over them." |
| SQ7_02 | corin_ashby | step 1 | "You carry fire in your hands, Silverer. Would you lend it to them?" |
| SQ7_03 | wren_hale | first lamp lit | "There. Burn, you stubborn thing." |
| SQ7_04 | corin_ashby | step 4 | "They'll fail again. I've been watering the oil. Father would weep." |
| SQ7_05 | dov_merriman | step 5 | "Oil for Corin? By the furnace, why didn't the fool ask? Take the barrel." |
| SQ7_06 | corin_ashby | oil delivered | "Real oil. Bell Lane will hold till dawn. Light holds. It holds." |

- **Reward:** +10 reputation. Story flag `Bell_Lane_Lit`: Corin's `dread` bark is never used again (his lane is safe), and his greeting becomes SQ7_07.

| Id | Speaker | Line |
|---|---|---|
| SQ7_07 | corin_ashby | "Not one flicker all night, Silverer. Not one." |

---

## SQ8 Sorrel's Shed

**Hook:** a Frostside healer has kept three tarnished tied up in her shed, testing cures. Light is the only thing that has ever worked, and her lamp is dry. One of the three is a Giltside dancer who fell through a rift.

- **Opens:** Wren is in Frostside's streets (not inside the sealed Frost Tower) and Sorrel is present. In practice this follows SQ6's Frostside shard, where the map has Frostside streets. **Skip it entirely if the map has no Frostside streets.**
- **Steps:**
  1. "Talk to Sorrel at the Bone Market" (`Person_sorrel_vey`).
  2. "Go to Sorrel's shed" (`Mk_Frost_Shed_Sorrel`). Three tarnished are held there, in scripted holds. One of them is `Person_petra_lisle`.
  3. "Burn the Tarnish out of Sorrel's patients (0/3)". Each hold ends when that patient is hit by a spell, so they never fight back mid-cure.
  4. "Talk to Petra".
  5. "Tell Lucan that Petra is alive" (`Person_lucan_marlowe`, Giltside).
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ8_01 | sorrel_vey | step 1 | "You burn it out with light. I've seen you. My shed. Now." |
| SQ8_02 | sorrel_vey | step 2 | "Three of them. Tied, fed, alive. Don't look at me like that." |
| SQ8_03 | sorrel_vey | each cure | "Show me again. Slower. Again." |
| SQ8_04 | petra_lisle | step 4 | "Gold. Your coat's got gold in it. Am I home? Am I near home?" |
| SQ8_05 | petra_lisle | step 4 | "Lucan. Tell Lucan I kept dancing. In my head. The whole time." |
| SQ8_06 | lucan_marlowe | step 5 | "Alive? She's... Lucan can't... I can't breathe. Say it again." |
| SQ8_07 | lucan_marlowe | step 5 | "Then I'll learn to walk through glass if it kills me." |

- **Reward:** +15 reputation. Story flag `Petra_Found`: Lucan's `dread` and `idle` barks are replaced by SQ8_08.

| Id | Speaker | Line |
|---|---|---|
| SQ8_08 | lucan_marlowe | "She's alive. Five, six, seven, eight. She's alive." |

---

## SQ9 Unsigned

**Hook:** fifty years ago a proud apprentice walked out on her master tailor. Ever since, bolts of wool have been turning up on his doorstep with no name. Neither of them will say the first word.

- **Opens:** after MQ01.
- **Steps:**
  1. "Talk to Barnaby on Lantern Row" (`Person_barnaby_thrale`).
  2. "Ask Odette Vane about the wool" (`Person_odette_vane`, Archive steps).
  3. Odette gives a bolt of wool (quest item). "Bring it to Barnaby".
  4. Barnaby gives his old shears (quest item). "Bring the shears to Odette".
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ9_01 | barnaby_thrale | step 1 | "Wool on the doorstep again, Silverer. Good wool. No name. Now then, who?" |
| SQ9_02 | odette_vane | step 2 | "Wool? Darling, I don't give wool away. Take this one to him. From a customer." |
| SQ9_03 | barnaby_thrale | step 3 | "From a customer. With a gold selvedge. Only one hand hems like that." |
| SQ9_04 | barnaby_thrale | step 3 | "Give her these. My first shears. She always wanted them. Tell her... tell her the seam held." |
| SQ9_05 | odette_vane | step 4 | "His shears. The old... Barnaby. He remembered the seam." |
| SQ9_06 | odette_vane | step 4 | "Go away, darling. Nobody sees me like this. Thank you. Go." |

- **Reward:** +5 reputation. Story flag `Seam_Held`: Barnaby and Odette's clique lines change (see [conversations.md](conversations.md), lantern_row and archive_steps "after SQ9"), and Odette's greeting becomes SQ9_07.

| Id | Speaker | Line |
|---|---|---|
| SQ9_07 | odette_vane | "Silverer. I'm sewing with the old man on Thursdays. Don't." |

---

## SQ10 The Watch Book

**Hook:** Sergeant Kettering keeps a page in the Watch book for every Silverer. Wren's page has marks on it: complaints from people who saw the light go where it shouldn't. A gate can't be held when the crowd is frightened of the person standing behind it. **This is the quest where the Silverer's heat matters.**

- **Opens:** after MQ06 (the key). Best offered when the Silverer has heat (any witnessed crime). If the quest system can't read heat yet, offer it anyway: the lines fit a clean record too, because people fear what Wren carries.
- **Steps:**
  1. "Talk to Sergeant Kettering at the Lantern Gate" (`Person_maud_kettering`).
  2. "Good marks": burn the Tarnish out of 2 people at the Lantern Gate (`Spot_LanternGate`, 40 m), and "Ask Nell Bramley to vouch for you" (`Person_nell_bramley`).
  3. "Bad marks": "Find Corporal Greave on Bell Lane" (`Person_hollis_greave`). She holds the witness statements. **Choice:** have them read out, or have the page lost.
  4. Return to Maud.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ10_01 | maud_kettering | offer | "Every Silverer gets a page in the Watch book, citizen. Yours has marks. Noted." |
| SQ10_02 | maud_kettering | offer | "Folk who saw your light go wrong. A gate can't hold if the crowd fears the one behind it." |
| SQ10_03 | wren_hale | accept | "Then tell me how to clean it." |
| SQ10_04 | maud_kettering | step 2 starts | "Good marks first. Two faces back from the Tarnish, here at my gate. Then Bramley speaks for you." |
| SQ10_05 | nell_bramley | step 2, talk | "I'll vouch, Sergeant! Sorry, I mean, I'd like to vouch. Properly." |
| SQ10_06 | maud_kettering | step 2 done | "Two. Noted. Now the bad marks. Corporal Greave holds the statements on Bell Lane." |
| SQ10_07 | hollis_greave | step 3, talk | "Statements. Eleven of them. Course there are. Want them read, or want them lost?" |
| SQ10_08 | hollis_greave | choice: read them | "Your call. A spell through a window. A man knocked flat on Lantern Row. It goes on a while." |
| SQ10_09 | hollis_greave | choice: lose the page | "Page fell in the canal. Shame. You owe me a flask of tea." |
| SQ10_10 | maud_kettering | turn in | "Clean page. Noted. Don't make me open the book again." |

- **Reward:** +10 reputation with Maud, +5 with Nell. Flag `Silverer_RecordClean` (both choices). "Lose the page" also sets `Watch_Page_Lost`, costs 10 with Maud and gives +5 with Hollis.
- **What `Silverer_RecordClean` should do (npc-lives / NPC system):** reset the Silverer's heat to zero, let witnesses' crime memories fade to "heard", and stop guards hunting. That's what makes heat matter: a wanted Silverer can clear the page by doing good in the open and owning the bad.
- **After:**

| Id | Speaker | Line |
|---|---|---|
| SQ10_11 | maud_kettering | "Your page is still clean, citizen. I check it every morning." |

---

## SQ11 Shield and Lamp

**Hook:** the Third Lamp Company walks the canal rift tonight, and Sergeant Mayne wants the Silverer in the middle of the line, where it's bright. Steel pins the tarnished; Wren burns them clean. Then Bram pins one that won't fight back, because it's looking at the recruit. It's Cosmo's brother, Wat.

- **Opens:** after MQ05 (Hold the Line). **Not while the Silverer is wanted:** if heat is high (or `Silverer_RecordClean` is missing after a witnessed crime), Mayne refuses with SQ11_W1 instead of the offer, which points the player at SQ10.
- **Steps:**
  1. "Muster with the Third Company at the canal rift" (`Spot_CanalRift`). Brask's squad should be there if squads are live: Mayne, Bram, Cosmo, Damaris and Emeric are its named members.
  2. "Hold the canal rift with the Third (60 s)" and "Burn the Tarnish out of 3 people" at `Spot_CanalRift` (4 tarnished come through). Fails if Cosmo dies.
  3. "Talk to Captain Brask": Bram has one pinned on his shield. **Choice:** burn it out, or cut it down.
  4. a. *Burn it out:* "Burn the Tarnish out of Wat". b. *Cut it down:* Brask won't let her people do it this time: "Cut down the pinned tarnished" (the player's kill).
  5. Return to Mayne.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ11_01 | aldric_mayne | offer | "Silverer. The Third walks the canal rift tonight. The Captain won't ask you. I'm asking, charmingly." |
| SQ11_02 | aldric_mayne | offer | "Steel pins them, you burn them clean. Nobody we cut down comes back. That's the Captain's word, not mine." |
| SQ11_W1 | aldric_mayne | offered while wanted | "Not while the Watch has your name in its book. Clean the page first, Silverer." |
| SQ11_03 | damaris_hobb | step 1 starts | "Lantern's lit, chicks. Silverer in the middle, where it's bright." |
| SQ11_04 | emeric_dunstan | step 1 done | "One long blast and we march! HA! Fine night for a tale!" |
| SQ11_05 | wren_hale | step 2 starts | "Hold them still. I'll do the rest." |
| SQ11_06 | bram_tolley | first cure | "That's one back. Behind me, you. You're safe now." |
| SQ11_07 | cosmo_fennick | second cure | "Two back! Sarge, are you counting? I'm counting!" |
| SQ11_08 | bram_tolley | step 3 starts | "Got one on the shield. It's not fighting. It's looking at Cosmo." |
| SQ11_09 | cosmo_fennick | step 3 starts | "Wat? Wat, it's me. Sarge, that's my brother. That's Wat!" |
| SQ11_10 | sela_brask | step 3, talk | "Silverer. It's pinned. Burn it out or I cut it down. Choose." |
| SQ11_11 | sela_brask | choice: burn it out | "Thirty seconds. Tolley, hold." |
| SQ11_12 | sela_brask | choice: cut it down | "Then you do it. My people have done enough of this." |
| SQ11_13 | cosmo_fennick | Wat cured | "Wat. Your eyes. Your eyes are yours. Mum's going to scream." |
| SQ11_14 | aldric_mayne | Wat cured | "Charming. Truly. I'll put that one on the roll as found." |
| SQ11_15 | cosmo_fennick | Wat cut down | "No. No, no, he was looking at me. He knew me." |
| SQ11_16 | bram_tolley | Wat cut down | "I had him. I had him still. I'm sorry, Cosmo." |
| SQ11_17 | aldric_mayne | turn in | "The Third thanks you. The Captain will nod at you once. Treasure it." |

| Id | Speaker | Line |
|---|---|---|
| SQ11_F1 | aldric_mayne | "Fennick's down. First week. I'll write to his mother myself." |
| SQ11_18 | sela_brask | "You fought on my line, Silverer. You can stand on it again." |

- **Reward:** a Giltside shard, +15 reputation with Brask, +10 with Mayne. The step unlocks say which way it went: `Quest_sq11_shield_and_lamp.cure_wat` (Wat goes home to his mother) or `Quest_sq11_shield_and_lamp.cut_wat` (opens SQ12). SQ11_18 is the "after" line.
- **If Wat dies during "burn it out"** (a stray spell or a soldier), treat it as "cut it down": play SQ11_15/16 and open SQ12. The field `ifKilledNext` says so; the quest system can ignore it.

---

## SQ12 The Empty Chair

**Hook:** the consequence. Wren cut down Cosmo's brother at the canal rift. Now Cosmo's chair at the Third Company's table is empty, his spear is gone, and something in the canal fog is talking in Wat's voice. Someone has to bring the recruit back, and someone has to tell his mother.

- **Opens:** only after `Quest_sq11_shield_and_lamp.cut_wat`. A player who burned Wat clean never sees this quest; that is the point.
- **Steps:**
  1. "Talk to Damaris Hobb at the Lamplight" (`Person_damaris_hobb`).
  2. "Find Cosmo at the canal rift" (`Spot_CanalRift`) and talk to him (`Person_cosmo_fennick`). The Tarnish speaks through the fog. **Choice:** own it, or tell him Wat was already gone. Fails if Cosmo dies.
  3. "Tell Marjory Fennick on Lantern Row" (`Person_marjory_fennick`). **Choice:** the truth, or the kinder lie.
  4. Return to Damaris.
- **Lines:**

| Id | Speaker | When | Line |
|---|---|---|---|
| SQ12_01 | damaris_hobb | offer | "Cosmo's gone, dear. Took Wat's cap and his spear. Mercy, I know where." |
| SQ12_02 | damaris_hobb | offer | "The canal. He says the fog's still calling in his brother's voice. Bring him back to us." |
| SQ12_03 | wren_hale | step 2 starts | "Cosmo! Step back from the edge." |
| SQ12_04 | cosmo_fennick | step 2, talk | "It talks like him. In the fog. It says Wat's still in there and you burned nothing." |
| SQ12_05 | the_tarnish | step 2, at the rift | "Come and look, little brother. Your Silverer spends people like coins." |
| SQ12_06 | cosmo_fennick | choice: own it | "I do. I do hate you. Help me up anyway." |
| SQ12_07 | cosmo_fennick | choice: he was already gone | "You didn't know him. You didn't. Take me home anyway." |
| SQ12_08 | marjory_fennick | step 3, talk | "You're the Silverer who was at the canal. Cosmo won't look at me. Tell me." |
| SQ12_09 | marjory_fennick | choice: the truth | "Then you'll carry him. Every day. Get away from my barrow." |
| SQ12_10 | marjory_fennick | choice: the lie | "Thank you for bringing my other boy home. Thank you." |
| SQ12_11 | damaris_hobb | turn in | "He's at the table. He's not talking. That's a start, dear." |

| Id | Speaker | Line |
|---|---|---|
| SQ12_F1 | damaris_hobb | "The fog took both Fennick boys. No lantern tonight." |
| SQ12_12 | cosmo_fennick | "I keep Wat's cap in my helmet now. For luck. It doesn't work." |

- **Reward:** no coin; it's a grief quest. Choices move standing: owning it costs 10 with Cosmo and gives +10 with Brask (she respects it); the truth to Marjory costs 25 with Marjory and sets `Fennick_Truth`; the lie gives +10 with Marjory and sets `Fennick_Lie` (Cosmo knows, and his after line stays the same either way). SQ12_12 is the "after" line.

---

## Notes for the quest system

- **Spawning tarnished on request:** SQ2, SQ4 and SQ6 ask for tarnished near a marker. The villain has `Villain.Convert` (the nearest tarnished converts the clean NPC nearest the player), and the NPC system has `SetInfection`. The simplest robust path is `SetInfection(Infected)` on 2–4 crowd NPCs within 40 m of the marker, which gives them the Tarnish look, makes them hostile and counts them on the meter. If no crowd NPC is near, the step completes after its timer with no fight.
- **Scripted holds:** for Hal (SQ1) and Sorrel's patients (SQ8), use the NPC system's scripted hold, which can't be talked to, and `EndScriptedHold` on the step's event.
- **Quest items:** the letter, ticket stub, fiddle, eyeglass, oil, wool and shears. These are journal entries with an icon name only; they need no meshes. The fiddle in SQ2 can be any small pickup prop.
- **Flags:** `Hal_Home`, `Jory_Plays`, `Nell_Letter`, `Coal_Lane_Safe`, `Eyeglass`, `Drifters_Stay`, `Bell_Lane_Lit`, `Petra_Found`, `Seam_Held`, `Silverer_RecordClean`, `Watch_Page_Lost`, `Fennick_Truth`, `Fennick_Lie`. SQ11's outcome is the step unlock `Quest_sq11_shield_and_lamp.cure_wat` or `.cut_wat`.
  - Set them with `UReflectionsLivesSubsystem::SetStoryFlag(Name, true)` and read them with `HasStoryFlag`. They are saved with checkpoints.
  - npc-lives acts on `Hal_Home` (Hal moves to the inn). The crowd director reads the flags to pick conversation seed E.
- **"After" lines** (SQ1_10, SQ3_08, SQ3_09, SQ4_10, SQ5_11, SQ6_11, SQ7_07, SQ8_08, SQ9_07, SQ10_11, SQ11_18, SQ12_12):
  - The quest system plays each one **once**, the first time the player talks to (or comes within 3 m of) that person after the flag is set.
  - That is all they need. They don't replace barks permanently, so no change to the bark player is needed.
  - The bark swaps described above ("becomes", "replaced by") are optional polish, for npc-unify if there's time.
