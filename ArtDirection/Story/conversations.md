# Street conversations and barks

Owner: the story session. These are the seeds for the street conversations NPCs have with each other, and the barks each named person says. Built by:
- **jam-audio**, who bakes the waves: one wave per line, from each speaker's head;
- **the crowd session**, whose director picks a conversation when a clique stands together at its spot;
- **npc-dialogue**, which uses this as style reference for live replies.

People, cliques, voices and spots are in [people.json](people.json).

## How a seed works

Each clique has five seeds:
- **A–C:** everyday life, the things these people would talk about with no Tarnish at all.
- **D:** the war and the Tarnish. It reacts to the **infection band** (people.json `infection_bands`: quiet, spreading, rising, brink).
- **E:** reacts to Wren and the story flags that main-quest.md and side-quests.md set.

Every seed gives:
- the **topic**;
- each speaker's **stance**;
- an **opening**: one to three written lines that fix the voice. The writer (or the audio session's script pass) continues it to 4–6 lines in the same voices.

**Band variants for seed D:**
- **quiet:** gossip, half joking.
- **spreading:** worried, practical: who's turned, and where.
- **rising:** a quarrel. One speaker wants to run and one wants to stay.
- **brink:** two lines only, urgent, and they break up and leave.

**Rules for anyone expanding a seed:**
1. Keep each speaker in their speech style, use their tics, and never use their never-say words (people.json).
2. A line is under about 3 seconds. No narration.
3. **No line may repeat any other line in the story**, including the barks below and other cliques' conversations. `tools/check_lines.py` checks this across every file in this folder.
4. Secrets are never said outright in street talk. A clique-mate may *circle* one, as a hint the player can overhear.
5. Mood, not magic: describe the sides by how they look and feel.

**For the crowd director:** pick the seed whose band or flag condition fits right now. Seeds D and E have priority when their condition is new; A–C fill the rest. Don't replay a seed until the clique has played the others.

---

## Giltside

### Lantern Row (`lantern_row`): Ilse, Barnaby, Dov, Amos (`Mk_Gilt_Market_LanternRow`)

- **A. The price of wax.**
  - Stances: Amos is selling cheap and boasting. Ilse is unimpressed. Dov is outraged on her behalf. Barnaby is peacemaking.
  - Opening:
    - Amos: "Wax at half Ilse's price, friend. Special, for the war."
    - Ilse: "Mm. Half the price and a quarter of the wick."
    - Dov: "By the furnace, Saffery, you'd sell the smoke off a candle."
- **B. Barnaby's hands.**
  - Stances: Barnaby is pretending his hands are fine. Ilse noticed and says so plainly. Dov offers to thread his needles. Amos stays quiet, for once.
  - Opening:
    - Ilse: "Your needle's been in the same hole for a minute, Barnaby."
    - Barnaby: "Now then, I'm pondering the stitch. A good tailor ponders."
- **C. Glass that sings.**
  - Stances: Dov is spooked that his glass hums. Barnaby is gently sceptical. Ilse believes him. Amos wants to sell "quiet glass".
  - Opening:
    - Dov: "Every pane in my shop is ringing. Proper ringing, like a struck bell."
    - Ilse: "Glass knows things before we do. Don't sell it, Dov. Listen to it."
- **D. The war at the Row's end.**
  - quiet: Amos jokes that the Tarnish is good for candle sales, and Ilse cuts him dead.
  - spreading: Barnaby counts who hasn't come for their coats.
  - rising: Dov wants to march; Barnaby begs him not to.
  - brink: Ilse orders all three indoors.
  - Opening (quiet):
    - Amos: "Every lamp in Giltside lit all night. Best season I've had."
    - Ilse: "Count your coin in the dark, then, and see if it's still good company."
  - Brink pair:
    - Ilse: "Inside. All of you. Now, while there's light."
    - Barnaby: "Come along, come along, mind the step, mind it."
- **E. Ilse's apprentice.**
  - Flags: after MQ02, they talk about Wren curing Jory. After `Seam_Held`, Barnaby is giddy about Odette.
  - Opening (after MQ02):
    - Dov: "Your boy pulled the dark out of the fiddler. In the square. I saw it."
    - Ilse: "He's not my boy. He's his mother's. Mm. Mostly mine."
  - Opening (after `Seam_Held`):
    - Barnaby: "She's coming Thursday. To sew. With me. Now then, what do I wear?"

### The Lantern Gate (`lantern_gate`): Maud, Nell (`Mk_Gilt_Gate_LanternGate`)

- **A. Regulation posture.**
  - Stances: Maud is drilling Nell. Nell is overdoing it.
  - Opening:
    - Maud: "Shoulders back, citizen. You're a guard, not a coat on a hook."
    - Nell: "Sorry, I mean, yes, Sergeant. Shoulders. Back. Back further?"
- **B. The headcount.**
  - Stances: they count the drifters under the gate together. Nell keeps losing count; Maud never does.
  - Opening:
    - Nell: "Thirty-one drifters. Or thirty-two. One keeps moving, honestly."
    - Maud: "Thirty-three. The small one sleeps under the cart. Noted."
- **C. Retirement.**
  - Stances: Nell asks what Maud will do after the war. Maud deflects, then answers truthfully.
  - Opening:
    - Nell: "When it's over, Sergeant, will you retire? Somewhere with a garden?"
    - Maud: "I'll stand at a gate. I don't know how to stand anywhere else."
- **D. What comes through the gate.**
  - quiet: rumours.
  - spreading: Maud orders double lamps.
  - rising: Nell freezes and Maud talks her through it.
  - brink: they hold the gate alone.
  - Opening (spreading):
    - Maud: "Double the lamps on the bridge. If it walks in, we see its face first."
    - Nell: "Its face is the problem, Sergeant. They all look like somebody."
  - Brink pair:
    - Maud: "Hold here, Bramley. Nobody else is coming."
    - Nell: "Steady, Nell. Steady. Holding, Sergeant."
- **E. The Silverer.**
  - Flags: after MQ05, Maud admits Wren held the line. After `Nell_Letter`, Nell tells Maud about her mother, and Maud already knew.
  - Opening (after `Nell_Letter`):
    - Nell: "Sergeant, there's something about me. I'm not from here. I'm..."
    - Maud: "Pewterside. Coal Lane line. I signed your papers at nine, citizen."

### The Lamplight (`lamplight`): Goldie, Jory, Corin (`Mk_Gilt_Inn_Lamplight`)

- **A. Requests.**
  - Stances: Jory is taking requests. Goldie wants something cheerful. Corin wants a hymn to the lamps, which nobody else wants.
  - Opening:
    - Jory: "Requests! Anything but sad ones. Corin, put your hand down."
    - Corin: "Just one verse of 'The Faithful Wick'. It's short. Mostly."
- **B. Supper.**
  - Stances: Goldie is feeding them both by force. Corin protests politely. Jory eats everything.
  - Opening:
    - Goldie: "Corin, you're thin as a taper. Sit. Stew. No arguing."
    - Jory: "I'll have his if he's arguing. I'm not arguing. Look at me not arguing."
- **C. The cellar door.**
  - Before SQ1: Jory and Corin circle Goldie's secret, because they've heard noises. Goldie changes the subject too loudly.
  - Opening:
    - Corin: "There's a knocking under the floor, Goldie. Every night at the same hour."
    - Goldie: "Barrels, sweetling. Barrels settle. Who wants pie?"
- **D. Empty tables.**
  - quiet: jokes about the curfew.
  - spreading: Corin's lamps are failing, and he says so.
  - rising: Goldie wants to keep the inn open and Corin wants her to bar the door.
  - brink: they pull the shutters.
  - Opening (rising):
    - Corin: "Bar the door, Goldie. Please. The unlit's at the end of the street."
    - Goldie: "Thirty years, this door's never been barred. Not tonight either."
  - Brink pair:
    - Goldie: "Shutters. Both of you. Quick, quick."
    - Jory: "I've got the left one. Corin, the left one's mine!"
- **E. After the humming.**
  - Flags:
    - After MQ02, Jory is quiet and the others try to cheer him.
    - After `Jory_Plays`, he plays and they sing badly.
    - After `Hal_Home`, Hal joins in and complains about the ale.
  - Opening (after MQ02):
    - Goldie: "You've not touched your stew, sweetling. Nor your fiddle."
    - Jory: "It's still in there somewhere. Humming. Under everything."

### The Archive Steps (`archive_steps`): Tobias, Odette, Lucan (`Mk_Gilt_Steps_Archive`)

- **A. A lecture nobody asked for.**
  - Stances: the Professor explains the Glass's hinges. Odette is bored. Lucan wants it to be romantic.
  - Opening:
    - Tobias: "Three leaves, hinged on the left, which is to say a standing book."
    - Odette: "Darling, you've told us about the hinges four times this week."
- **B. Fashion in wartime.**
  - Stances: Odette mocks Lamp Company coats. Lucan wants a costume. The Professor doesn't own a mirror and it shows.
  - Opening:
    - Odette: "Oxblood and brass on every soldier. The old man has no imagination."
    - Lucan: "Make Lucan something tragic. With a cape. A tragic cape."
- **C. The partner.**
  - Stances: Lucan practises a duet alone. The Professor tries to help with a theory about rifts. Odette is unexpectedly gentle.
  - Opening:
    - Lucan: "This is the lift. She'd be here. Lucan lifts air now."
    - Odette: "Then lift the air beautifully, darling. Someone ought to."
- **D. The dark in the reflections.**
  - quiet: the Professor treats it as a puzzle.
  - spreading: Lucan stops checking his reflection.
  - rising: Odette wants to leave the side and the Professor says there's nowhere to go.
  - brink: they help the Professor carry his papers inside.
  - Opening (spreading):
    - Tobias: "It moves through reflections. Windows, puddles, polished brass. Remarkable."
    - Lucan: "Lucan has stopped looking in windows. Lucan misses Lucan."
  - Brink pair:
    - Odette: "Leave the papers, Tobias. They don't bleed."
    - Tobias: "They might! Metaphorically! Grab the blue folder!"
- **E. The eyeglass and the seam.**
  - Flags:
    - After `Eyeglass`, the Professor is triumphant about reading the pages.
    - After `Seam_Held`, Odette is caught smiling.
    - After `Petra_Found`, Lucan can't stop dancing.
  - Opening (after `Petra_Found`):
    - Lucan: "She's alive. In the white place, but alive. Somebody dance with me."
    - Odette: "One turn, darling. One. My knees are fifty-five."

### The Muster Yard (`muster_yard`): Brask, Ros, Emeric (`Mk_Gilt_Yard_Muster`)

Emeric Dunstan (added 2026-11-14) joins any of these seeds when he's in the yard: one booming aside per seed, never a dead soldier's name ("the ones before"). Seed F is his.

- **A. Drill.**
  - Stances: Brask corrects Ros's spear grip. Ros is cheeky until Brask stares.
  - Opening:
    - Brask: "Thumb along the shaft. Your grip's a farmer's. Again."
    - Ros: "Easy as stitching, Captain. Watch. No, don't watch, I'll miss."
- **B. Grandad's coat.**
  - Stances: Ros brags about Barnaby's work. Brask admits her own coat is a Thrale.
  - Opening:
    - Ros: "Feel that lining, Captain. Grandad sewed it double for the rift wind."
    - Brask: "I know. Mine's his too. Don't tell the company."
- **C. The roll call.**
  - Stances: they read the company list. Brask knows every number. Ros knows every name.
  - Opening:
    - Brask: "Twelve, fourteen, nineteen. Gone at the canal."
    - Ros: "Pell, Harrow, little Sim. They had names, Captain."
- **D. The order about drifters.**
  - quiet: Ros asks why.
  - spreading: Brask gives her reasons.
  - rising: Ros refuses.
  - brink: they fight side by side and drop it.
  - Opening (rising):
    - Ros: "I'm not pushing a child into that hole. Give the order to someone else."
    - Brask: "There is no one else. Twenty-six of us. That's why it's you."
  - Brink pair:
    - Brask: "Spears up, Thrale. Argue later."
    - Ros: "Later, then. You owe me a later."
- **E. Wren on the line.**
  - Flags: after MQ05, Brask grudgingly respects Wren. After `Drifters_Stay`, Ros teases her.
  - Opening (after `Drifters_Stay`):
    - Ros: "New order, is it? Drifters on the roster? Going soft, Captain."
    - Brask: "Going short-handed. There's a difference. Mind your mouth."

- **F. The horn.**
  - Stances: Emeric tells the canal-ice tale again. Brask lets him. Ros notices he's watching their mouths.
  - Opening:
    - Emeric: "And I said, lad, you're the Captain now, so get off my back and walk! HA!"
    - Brask: "You carried me. Tell it right or don't tell it."
    - Ros: "Emeric. Emeric, I asked if you want tea. You didn't hear me, did you?"

### The Third Company's Table (`third_company_table`): Mayne, Bram, Cosmo, Damaris (`Mk_Gilt_Inn_Lamplight`)

Off-duty soldiers at the corner table of the Lamplight's taproom, in the company's tavern block (18:00-23:00). Goldie serves them; Jory sometimes plays at them.

- **A. Cosmo's tall tale.**
  - Stances: Cosmo tells a fight he wasn't in. Mayne corrects every detail. Damaris enjoys it.
  - Opening:
    - Cosmo: "So there's six of them, right, and I've only got the one spear..."
    - Mayne: "There were two, you were in the latrine, and you're holding the spear backwards in this version."
    - Damaris: "Let him tell it, Aldric. It's better his way."
- **B. Wenna's drawing.**
  - Stances: Bram shows a drawing from his daughter. The whole table goes soft and pretends not to.
  - Opening:
    - Bram: "She's drawn the lamp again. And me. I'm the big square."
    - Damaris: "Mercy, that's the best likeness of you anyone's ever done."
- **C. Who pays.**
  - Stances: Bram always pays; Mayne pretends to fight him for it; Cosmo hasn't been paid yet.
  - Opening:
    - Mayne: "Put that purse away, Tolley. Charming gesture. Away."
    - Bram: "Already paid. Paid Goldie when we came in. Careful, you'll spill."
- **D. The canal.**
  - quiet: Cosmo asks if anyone's seen a face like his brother's out there.
  - spreading: Mayne gives the numbers; Damaris counts who's turned off Bell Lane.
  - rising: Cosmo wants to go to the canal tonight; Mayne forbids it.
  - brink: they leave the table to muster.
  - Opening (rising):
    - Cosmo: "If he's out there, sarge, he's out there tonight. I'm going."
    - Mayne: "You're going to bed, Fennick. That is not a suggestion, for once."
  - Brink pair:
    - Damaris: "Lantern's guttering, chicks. Up, up, kit on."
    - Bram: "Table'll keep. Out, all of you, behind me."
- **E. Wren and the Company.**
  - Flags: after `Quest_sq11_shield_and_lamp.cure_wat`, they toast the Silverer. After `.cut_wat`, Cosmo's chair is empty and the other three don't talk about it. After SQ12, Cosmo is back and quiet.
  - Opening (after cure_wat):
    - Cosmo: "My brother's at home eating Mum's pie. Because of the Silverer. Brilliant."
    - Mayne: "Glasses up. To the bright end, pointed the right way."
  - Opening (after cut_wat, before SQ12):
    - Damaris: "Leave his chair. He'll come back for it, or he won't."
    - Bram: "I should've held Wat longer. Long enough."

### Bell Lane (`bell_lane`): Pim, Tobin, Hollis (`Mk_Gilt_Lane_BellLane`)

- **A. Selling light.**
  - Stances: Tobin tries to sell Pim a candle he doesn't need. Pim is too polite to say no. Hollis is watching wearily.
  - Opening:
    - Tobin: "Pim! A candle for the bell tower! Two a penny, three for you!"
    - Pim: "If you please, I've four already. Quite enough candles."
- **B. The bells.**
  - Stances: Pim explains each bell's name. Tobin makes up worse names. Hollis secretly knows them all.
  - Opening:
    - Pim: "That's Old Clement. That's Bright Agnes. That's..."
    - Hollis: "Tall Martin. Course it is. My dad rang Tall Martin."
- **C. The old flame.**
  - Before anyone knows: Tobin worries about Ilse alone in her attic. Pim promises to check on her. Hollis pretends not to hear Tobin being kind.
  - Opening:
    - Tobin: "Old flame's stair is steep. Somebody should be bringing her water up."
    - Pim: "I could, if you please. Tuesdays and every other day."
- **D. Faces.**
  - quiet: Tobin jokes about burning eyes.
  - spreading: Hollis goes quiet when someone mentions brothers.
  - rising: Pim wants to ring the alarm bell and Hollis stops him, because the bells are silent.
  - brink: Hollis sends them both home.
  - Opening (spreading):
    - Tobin: "Saw one this morning wearing the baker's face. Proper flash, those eyes."
    - Hollis: "Don't. Faces aren't funny. Not any more."
  - Brink pair:
    - Hollis: "Both of you, home. I'm not asking."
    - Pim: "Yes, Corporal. Tobin. Tobin, come on."
- **E. The tower open.**
  - Flags: after MQ07, Pim is breathless about the open tower and Tobin wants to sell candles inside. After victory, the bells (the CS06 echo).
  - Opening (after MQ07):
    - Pim: "It's open. The tower's open. I stood on the first stair. Quite."
    - Tobin: "First stair! Pim Ashgrove, adventurer. Laters, bell-boy."

## Pewterside

### Coal Lane Tram Stop (`coal_lane_stop`): Edie, Hester, Walter, Sid (`Mk_Pew_Stop_CoalLane`)

- **A. The timetable.**
  - Stances: Edie says the tram's on time. Hester declares it late. Walter sides with Hester. Sid doesn't know what time it is.
  - Opening:
    - Hester: "The tram is late, and We are displeased."
    - Edie: "Tram's due in four minutes. It's never been late. Not once."
- **B. Chess.**
  - Stances: Walter is losing to nobody (he plays both sides). Hester heckles. Sid watches seriously.
  - Opening:
    - Walter: "Hmph. Black's winning. I'm black. And white. Blasted game."
    - Sid: "Right. Which one's you?"
- **C. Hester's eyes.**
  - Stances: Sid quietly guides Hester around a puddle without saying why. Edie notices. Walter notices and says nothing, painfully.
  - Opening:
    - Sid: "Step left, Nan. Bit more. Right."
    - Hester: "I know where the puddle is, Sidney. I've lived here seventy years."
- **D. Who's not on the tram.**
  - quiet: Edie lists her regulars.
  - spreading: two regulars are missing.
  - rising: Hester refuses to go in until they're home, and Sid begs her.
  - brink: Sid carries her inside.
  - Opening (spreading):
    - Edie: "Mrs Grice didn't get on at Pewsey Row. Twenty-two years, she's never missed."
    - Walter: "Rubbish odds, that. Rubbish."
  - Brink pair:
    - Sid: "Up you get, Nan. I've got you. Right."
    - Hester: "Put me down this instant. No. Don't put me down."
- **E. The Silverer on the lane.**
  - Flags:
    - After MQ04, gossip about the Silverer.
    - After `Coal_Lane_Safe` and the proposal, Edie teases Walter and Hester pretends to be annoyed.
    - After `Nell_Letter`, Edie tells them she has a daughter.
  - Opening (after `Nell_Letter`):
    - Edie: "My girl wrote to me. From the gold side. She's a guard. Next stop."
    - Hester: "Edie Bramley, you're crying on the platform. Good."

### The Fish Steps (`fish_steps`): Bet, Agnes, Ada, Ned (`Mk_Pew_Steps_FishSteps`)

- **A. Haggling.**
  - Stances: Bet won't drop her price. Ada pays in stories. Agnes is too tired to haggle. Ned pays exactly.
  - Opening:
    - Bet: "Two coppers for the haddock and I'm robbing myself, my eel."
    - Ada: "I'll tell you about the winter the river froze, dearie. That's worth two coppers."
- **B. Colours.**
  - Stances: Ned describes the gold he imagines. Agnes says it sounds exhausting. Bet says gold fish exist. Ada remembers a gold coat.
  - Opening:
    - Ned: "Sorry, only, do you think gold is warm to touch? Like bread?"
    - Agnes: "Everything's warm to touch on a night shift, love. That's fever."
- **C. The night shift.**
  - Stances: Agnes falls asleep standing up. Bet props her up. Ned brings her tea. Ada tells her about Arthur's snoring.
  - Opening:
    - Bet: "She's gone. Asleep on her feet, look. Like a heron."
    - Agnes: "I am not asleep. I'm resting my... symptoms. Hold still."
- **D. The wet.**
  - quiet: Bet's river stories, and nobody believes her.
  - spreading: Agnes's ward is filling.
  - rising: Bet insists something's under the surface, and Agnes finally believes her.
  - brink: they leave the steps.
  - Opening (rising):
    - Bet: "They walk under the water, upside down. I've SEEN it, I'm not soft."
    - Agnes: "I believe you, Bet. I've got four on my ward who came up out of the river."
  - Brink pair:
    - Agnes: "Off the steps. Away from the water. Now."
    - Ned: "Sorry, sorry, Ada, take my arm."
- **E. The eyeglass and the Silverer.**
  - Flags:
    - After MQ04: talk of the glowing roof.
    - After `Eyeglass`: Ada tells them someone listened to the whole story, and they don't believe her.
    - After `Coal_Lane_Safe`: Agnes hopes for her ward.
  - Opening (after `Eyeglass`):
    - Ada: "He listened to the whole story, dearie. Every word. Isn't that right, Arthur?"
    - Bet: "Nobody's ever heard the end of one of yours, Ada. Nobody."

### Weigh-House Corner (`weigh_house_corner`): Ivy, Horace, Winnie, Frank (`Mk_Pew_Square_WeighHouse`)

- **A. Today's headline.**
  - Stances: Frank shouts an invented headline. Horace calls it rubbish. Winnie asks for the real news. Ivy takes it down as evidence.
  - Opening:
    - Frank: "COAL LANE PIGEON SEES BURNING EYES! Exclusive!"
    - Horace: "That pigeon's been blind since the last war. Mark my words."
- **B. Tea on account.**
  - Stances: Horace owes Winnie for a month of tea. Winnie lets him. Ivy wants to know if that's lawful. Frank wants it as a story.
  - Opening:
    - Winnie: "That's thirty-one brews on account, Horace. Between you and me."
    - Horace: "Suppose I'll settle up. At the end of the world. Soon, by the look."
- **C. The Weigh-House roof.**
  - Stances: everyone has seen the glow. Ivy guards it officially. Horace refuses to talk about the stair. Winnie knows why and changes the subject for him.
  - Opening:
    - Ivy: "For the record, the roof glowed silver again at midnight. I wrote it down."
    - Winnie: "Sugar, Horace? There. Drink up. Don't mind the roof."
- **D. Reports.**
  - quiet: Ivy has three reports.
  - spreading: she has thirty.
  - rising: Frank stops making things up because the truth is worse.
  - brink: Horace shutters the shop and lets them all in.
  - Opening (spreading):
    - Ivy: "Thirty reports of burning eyes. I only had paper for twelve."
    - Frank: "I'm writing it straight today. No sources. Just what I saw."
  - Brink pair:
    - Horace: "In. All of you. In the shop. Don't touch the nails."
    - Winnie: "Horace Pratt, you old softie. Mind the urn, Ivy."
- **E. After the first page.**
  - Flags: after MQ04, the roof stops glowing and Horace goes quiet about his wife. After `Coal_Lane_Safe`, Frank has his true scoop.
  - Opening (after MQ04):
    - Ivy: "Roof's dark now. The Silverer took the glow. Is that lawful? I think it's lawful."
    - Horace: "My Maisie watched the river from up there. Eleven years. Suppose that'll do."

## Frostside

### The Ice Stairs (`ice_stairs`): Gunnar, Mother Rook, Tilly (`Mk_Frost_Stair_IceStairs`)

- **A. Broth.**
  - Stances: Tilly tries to make Gunnar eat. He says he's eaten. Mother Rook knows he hasn't.
  - Opening:
    - Tilly: "Gunnar. Bowl. Now. It's half hot, that's practically a feast."
    - Gunnar: "Ate at dawn. Ice for breakfast. Honest meal."
- **B. The song.**
  - Stances: Mother Rook teaches Tilly a verse. Tilly gets it wrong. Gunnar knows the tune and won't sing.
  - Opening:
    - Mother Rook: "Three leaves of glass, one for each light. Sing it back, little one."
    - Tilly: "Three leaves of glass, one for each... soup? Granny, I'm tired."
- **C. Warm places.**
  - Stances: Tilly dreams about Giltside. Gunnar is grimly sceptical. Mother Rook tells a story about the gold side from before the cut.
  - Opening:
    - Tilly: "They say the lamps on the gold side never go out. Never!"
    - Gunnar: "Then they've never had to pay for oil. Cold's honest. Lamps lie."
- **D. The cracks.**
  - quiet: Gunnar's ice is ringing.
  - spreading: a crack has opened across the stairs.
  - rising: Mother Rook says it's coming for the song.
  - brink: Gunnar carries her and Tilly drags the sled.
  - Opening (spreading):
    - Gunnar: "New crack across the third stair. Wasn't there at dawn."
    - Mother Rook: "It's reaching. Remember it: the cracks are hands."
  - Brink pair:
    - Gunnar: "Up. On my back. No arguing, old woman."
    - Tilly: "I've got the pot! Granny, hold the pot!"
- **E. The Silverer.**
  - Flags: on Wren's first time in Frostside, they talk about a warm-sider walking the stairs. After the mirror is whole, Mother Rook finally sings the true verse.
  - Opening (Wren in Frostside):
    - Tilly: "A warm-sider on the stairs, Granny! In a coat that shines!"
    - Mother Rook: "The last one shone too. She had his eyes."

### The Bone Market (`bone_market`): Greta, Brenna, Sorrel (`Mk_Frost_Market_BoneMarket`)

- **A. Charms.**
  - Stances: Greta sells useless charms. Sorrel says so. Brenna buys one anyway.
  - Opening:
    - Greta: "Little fox charm. Wards off the Tarnish. Doesn't, but it's a nice fox."
    - Brenna: "I'll take the fox. Fox has kind eyes."
- **B. The wall.**
  - Stances: Brenna counts paces of fog. Greta jokes about carving her a headstone. Sorrel checks Brenna's frostbite.
  - Opening:
    - Brenna: "Fog was forty paces off the wall last night. Thirty tonight."
    - Greta: "I'll carve you something nice. Something with a little owl."
- **C. Sorrel's shed.**
  - Before SQ8: Greta circles the shed ("you're keeping something in there"). Sorrel shuts it down. Brenna takes Sorrel's side.
  - Opening:
    - Greta: "Your shed moans at night, Sorrel. Bones don't moan. I'd know."
    - Sorrel: "Leave the shed alone, Greta. Show me your hands. Frostbite."
- **D. Bites.**
  - quiet: Sorrel's count of bites.
  - spreading: Brenna hears voices and doesn't say whose.
  - rising: Greta stops joking.
  - brink: they hold the market together.
  - Opening (rising):
    - Greta: "No joke for this one. I'm out of jokes. That's grim."
    - Sorrel: "Then carve stakes instead of foxes. Real work."
  - Brink pair:
    - Brenna: "Backs together. Spears out."
    - Greta: "I've a carving knife. It'll do, it'll do."
- **E. Light that works.**
  - Flags: after SQ8, Sorrel wants to learn the cure from Wren and Greta carves a little Silverer charm.
  - Opening (after `Petra_Found`):
    - Sorrel: "Three walked out of my shed on their own feet. Light did it."
    - Greta: "I'll carve a Silverer charm. First one that ever worked."

### The Drifters under the Gate (`drifters_camp`): Kit, Fen (`Mk_Gilt_Camp_UnderGate`, home Frostside)

- **A. Finds.**
  - Stances: Kit shows Fen what he found. Fen pretends not to care and takes the best piece.
  - Opening:
    - Kit: "Look. A door handle. Brass. Could be from somewhere grand."
    - Fen: "Could be mine. Is mine now. Says who? Says me."
- **B. Warm.**
  - Stances: Fen loves Giltside. Kit misses the cold, the stairs and Tilly's broth.
  - Opening:
    - Fen: "Feel that. Warm stones. You could sleep on them. I have."
    - Kit: "I miss the stairs. I miss Tilly's broth. Even the snow in it."
- **C. The Watch.**
  - Stances: the Watch is looking for the oil thief. Kit is nervous. Fen thinks it's funny and plans to blame someone.
  - Opening:
    - Kit: "They're looking for whoever's taking lamp oil. Fen, they're looking."
    - Fen: "Then let them look. I'll say it was the fiddler."
- **D. The rift and the voice.**
  - quiet: Kit wonders if they could go home.
  - spreading: Fen stares at the canal.
  - rising: Kit begs Fen to stop looking at still water.
  - brink: they run to the gate.
  - Opening (rising):
    - Kit: "Stop looking at the canal, Fen. Please. You go somewhere when you look."
    - Fen: "It's quiet in there. Somebody in there knows my name."
  - Brink pair:
    - Kit: "Up the bank, Fen. To the Watch. Go."
    - Fen: "I'm going, I'm going! Don't let go."
- **E. Staying.**
  - Flags: after `Drifters_Stay`, Fen is quietly happy and Kit carves something whole for her.
  - Opening (after `Drifters_Stay`):
    - Kit: "We're on a list. A Giltside list. Fen, we're written down."
    - Fen: "Written down. Huh. Nobody ever wrote me down."

### The Long Shelter (`long_shelter`): Marta, Dagny, Eskil (`Mk_Frost_Shelter_LongShelter`)

- **A. The door rule.**
  - Stances: Marta checks eyes at the door. Dagny mocks the rule. Eskil defends Marta too eagerly.
  - Opening:
    - Marta: "Eyes up, chin up. Next. Eyes up."
    - Dagny: "Magnificent system. Look into a stranger's face all night."
- **B. Coal.**
  - Stances: Marta counts coal. Eskil hands over his rations disguised as coal money. Dagny sees through it.
  - Opening:
    - Eskil: "Found a bit of coin. Put it on coal. Not mine. Found it."
    - Dagny: "You found it in your own ration card. Typical."
- **C. The gate.**
  - Stances: Dagny talks about her sister, very nearly. Marta lets her. Eskil fills the silence badly.
  - Opening:
    - Dagny: "Gate's been open three winters. For someone. Doesn't matter who."
    - Marta: "It matters. Say it when you want. Roof's here."
- **D. A tarnished at the door.**
  - quiet: Marta worries.
  - spreading: she turns someone away.
  - rising: Eskil wants to let them in and Marta refuses.
  - brink: they bar the door together.
  - Opening (rising):
    - Eskil: "She's frostbitten, Marta, not burning. Let her in."
    - Marta: "I let one in last winter. Forty people woke up wrong."
  - Brink pair:
    - Marta: "Bar it. Dagny. Eskil. Bar it now."
    - Dagny: "First time this door's ever closed. Magnificent."
- **E. The warm-sider.**
  - Flags: on Wren's first time in Frostside, Eskil doubts him. After the mirror is whole, Eskil finally tries to tell Marta, and Dagny interrupts on purpose.
  - Opening (after the mirror is whole):
    - Eskil: "Marta. If the wall holds tonight, I want to say a thing."
    - Dagny: "He loves you. There. Gate's open, everybody knows. Magnificent."

---

## The rest of the crowd (audio's other cliques)

The audio session's script has its own 48 crowd cliques (C01–C48). The 13 story cliques above are separate groups, made of the named people, and their voices come from people.json. Audio's cliques stay as they are. For those, use people.json's `generator` to give each voice a person, and write conversations from these topic pools, keeping to the same five-seed shape and the same rules.

| Side | Everyday topics (A–C) | War topics (D) |
|---|---|---|
| Giltside | festival plans postponed; the price of lamp oil; who's courting whom; recruiting tables; a bakery's new bun; bells silent since the war; a son posted to the rift | curfew bells; Lantern Law fines; drifters under the gate; Lamp Companies' dead; a neighbour with burning eyes; whether light really hurts it |
| Pewterside | rent; the tram; rain through the roof; a pub quiz; the docks hiring; laundry prices; a grandchild's cough | people going missing off the tram; the river's reflections; the constable's notebook; the Weigh-House glow; a rift on the Fish Steps |
| Frostside | coal; broth; the ice harvest; a wedding in the shelter; frostbite cures; scavenging the old houses; carving | the wall; the fog; cracks spreading; turning people away at the door; the Wall Company's rations; warm-siders |

**Ban list for crowd scripts:** the never-say list in [bible.md](bible.md#tone-rules-for-every-writer), plus any line already used by a named person (`tools/check_lines.py`).

<!-- BARKS: generated from people.json by tools/build_conversations.py; edit people_src.py, not this section -->
## Barks, by person

Fifteen bark intents per named person (eight base, seven for the open-world systems), plus four battle and patrol barks for soldiers, in that person's voice. The audio session bakes one wave per line, as `SCue_VO_Bark_<VoiceId>_<intent>`, and npc-unify plays them. Generated crowd people use their roster voice's own lines instead.

| Intent | Plays when |
|---|---|
| `greet` | the Silverer comes within talk range, or the player starts a conversation |
| `idle` | a calm remark to nobody (npc-unify's Remark trigger) |
| `see_tarnished` | sees a tarnished or a host within about 15 m |
| `flee` | starts fleeing |
| `spell_near` | a spell lands or is cast within about 6 m |
| `thanks` | the Silverer cured or saved someone near them, or finished their quest |
| `dread` | the infection band is rising or brink (replaces idle) |
| `farewell` | the player ends a conversation or walks away |
| `witness_crime` | sees the Silverer hurt or kill someone (Lives WitnessedCrime / NPC OnPlayerCrime) |
| `flee_silverer` | flees from the Silverer: after a crime, or when their opinion and the Silverer's heat are bad |
| `call_guards` | shouts for help after a crime: the Watch, the Coal Lane constable, the Wall Company; soldiers rally their own |
| `knocked_down` | knocked off their feet: a blast, a shove, a hit reaction or ragdoll they get up from |
| `on_fire` | set alight by a fire spell or burning ground |
| `shocked` | hit by lightning or a shock spell |
| `mourning` | grieving someone the player killed: near the body, or the next time the player talks to them (Greet_Grieving) |
| `battle_1` | soldiers only: squad engaged (battle order 1) |
| `battle_2` | soldiers only: squad engaged (battle order 2) |
| `patrol_1` | soldiers only: walking a patrol block |
| `patrol_2` | soldiers only: walking a patrol block |
| `enemy_down` | soldiers only: a tarnished goes down to steel (it stays dead) |

### Giltside

**Ilse Varrow** (`ilse_varrow`, V014, retired Silverer; sells candles on Lantern Row). Short, dry sentences. Answers a question with a better question. Gives orders as if they were weather reports.

| Intent | Line |
|---|---|
| greet | "There you are. Mind your boots on my wax." |
| idle | "Tallow, beeswax and one good wick. Plainly enough." |
| see_tarnished | "Eyes like coals. Light, boy, give it light!" |
| flee | "Not my legs, not today. Move!" |
| spell_near | "Mm. Wider stance. You're casting from the shoulder." |
| thanks | "Polished. Your mother would have grinned." |
| dread | "It's in more faces than I can count. Hurry." |
| farewell | "Go on. The wick won't trim itself." |
| witness_crime | "Mm. That was a person, boy. Not a target." |
| flee_silverer | "I taught you better than that. Keep back." |
| call_guards | "Kettering! Bring the Watch to Lantern Row!" |
| knocked_down | "Down I go. Old bones, plainly." |
| on_fire | "My coat's caught! Smother it, smother it!" |
| shocked | "Lightning in my teeth. Mind your aim." |
| mourning | "I knew them forty years. You had ten seconds." |

**Barnaby Thrale** (`barnaby_thrale`, V088, master tailor; cut Wren's silvered coat). Talks in cloth: people are 'well cut' or 'badly hemmed'. Long sentences that trail off when he forgets the end.

| Intent | Line |
|---|---|
| greet | "Now then! Let me see that hem. Torn again?" |
| idle | "Bias cut, double seam. Lovely, lovely." |
| see_tarnished | "Oh, that poor soul's eyes. Oh, no." |
| flee | "Pins everywhere, never mind them, go, go!" |
| spell_near | "Careful! That's silk drying on the rail!" |
| thanks | "You've a good heart under good tailoring." |
| dread | "They'll want coats for the funerals next. I can't." |
| farewell | "Keep the collar up. It's cut to be worn up." |
| witness_crime | "Now then, now then, what have you done to them?" |
| flee_silverer | "Not the shop, not my hands, I'm going!" |
| call_guards | "Watch! Watch! Somebody fetch Sergeant Kettering!" |
| knocked_down | "Oof. Unpicked like an old seam." |
| on_fire | "Wool burns! Wool burns, help me!" |
| shocked | "Every pin in my waistcoat is humming!" |
| mourning | "I cut their wedding coat. Who cuts the shroud now?" |

**Dov Merriman** (`dov_merriman`, V094, glassblower; makes lantern glass). Loud and blunt, all exclamation. Swears by heat. Insults the people he likes best.

| Intent | Line |
|---|---|
| greet | "Silverer! Come warm your hands, the furnace is roaring!" |
| idle | "Proper heat makes proper glass. Simple as that." |
| see_tarnished | "By the furnace, look at its eyes! Get back!" |
| flee | "I'm not running, I'm fetching a bigger poker!" |
| spell_near | "Oi! Point that glow somewhere else!" |
| thanks | "You've done right by us. I owe you a lamp." |
| dread | "My glass won't stop singing. Something's close." |
| farewell | "Off you go. Don't break anything I made." |
| witness_crime | "By the furnace! You struck them down!" |
| flee_silverer | "Keep that light off me, I'm off!" |
| call_guards | "WATCH! To the furnace, there's murder in the street!" |
| knocked_down | "Flat on my back! Like a cracked bottle!" |
| on_fire | "I've been burned before, but not like THIS!" |
| shocked | "That's worse than a furnace blast, by the heat!" |
| mourning | "I'll blow a lamp for them. You'll not touch it." |

**Amos Saffery** (`amos_saffery`, V086, spice trader). Smooth salesman's patter; every sentence is a small offer. Uses "friend" the way other people use a hand on your shoulder.

| Intent | Line |
|---|---|
| greet | "Silverer! For you, friend, something rare." |
| idle | "Saffron, clove and peace of mind, by the ounce." |
| see_tarnished | "That's bad for trade, that is. Very bad." |
| flee | "Mind the stock! No, forget the stock, run!" |
| spell_near | "Easy! Spices catch, you know. The dear ones first." |
| thanks | "I'll knock a little off your next purchase. A little." |
| dread | "Nobody's buying. They're all just praying." |
| farewell | "Come back with coin, friend." |
| witness_crime | "Friend, no. No price buys that back." |
| flee_silverer | "Take the purse, friend, take it, I'm gone!" |
| call_guards | "Watch! A Silverer gone bad! A gold piece to whoever comes!" |
| knocked_down | "My saffron! A fortune an ounce, in the dirt!" |
| on_fire | "I'm burning, friend! I'm burning like cheap incense!" |
| shocked | "Every coin in my sash just bit me!" |
| mourning | "They owed me nothing. I'd pay anything to have them back." |

**Sergeant Maud Kettering** (`maud_kettering`, V028, sergeant of the Lantern Watch at the Lantern Gate). Clipped watch-report sentences. Calls everyone "citizen". Counts things out loud.

| Intent | Line |
|---|---|
| greet | "Silverer. Noted. State your business, quickly." |
| idle | "Eleven lamps on this gate. All eleven lit. Good." |
| see_tarnished | "Tarnished at the gate! Watch, to me!" |
| flee | "Fall back three paces, citizens. Orderly!" |
| spell_near | "Not in my street without a warning, Silverer." |
| thanks | "That's one I won't have to write home about." |
| dread | "We're short. Short of people, short of time." |
| farewell | "Be back before the dusk bell." |
| witness_crime | "Citizen down. Silverer, you're under the Watch's eye." |
| flee_silverer | "Withdrawing. Noted. Moving." |
| call_guards | "Lantern Watch, to me! One, two, three of you, now!" |
| knocked_down | "Down. Noted. Getting up." |
| on_fire | "On fire. Water, citizen, now!" |
| shocked | "Shock to the chest. Counting heartbeats. One..." |
| mourning | "One more for the Watch book. Your name goes beside it." |

**Nell Bramley** (`nell_bramley`, V037, bridge guard of the Lantern Watch). Rushed and polite; over-explains, apologises, then corrects herself. Quotes Watch regulations.

| Intent | Line |
|---|---|
| greet | "Silverer! Sorry, I mean, good evening." |
| idle | "Steady, Nell. Regulation posture. Steady." |
| see_tarnished | "Its eyes, its eyes are burning! Sergeant!" |
| flee | "I'm meant to hold, I can't, I can't!" |
| spell_near | "Oh! Honestly, warn a person first!" |
| thanks | "I'll put that in my report. All of it. Properly." |
| dread | "Half the bridge watch didn't come back tonight." |
| farewell | "Safe road. Is that what you say? Safe road." |
| witness_crime | "You can't, that's, sorry, that's against every regulation!" |
| flee_silverer | "Steady, Nell, steady, just run!" |
| call_guards | "Sergeant! Corporal! Anyone in a helmet, please!" |
| knocked_down | "Ow! Sorry, I mean, I'm down!" |
| on_fire | "I'm on fire, that's not regulation, help!" |
| shocked | "My helmet strap's buzzing, honestly!" |
| mourning | "They used to wave at my post. Every single morning." |

**Marigold "Goldie" Fairweather** (`goldie_fairweather`, V027, keeper of the Lamplight inn; Wren's landlady). Big and motherly; talks over everyone, an endearment in every sentence. Goes very quiet when cornered.

| Intent | Line |
|---|---|
| greet | "Sweetling! There's stew on. Sit, sit." |
| idle | "Cosy as a hearth, this place. Always has been." |
| see_tarnished | "Not here. Not in my house. Out!" |
| flee | "Behind the bar, all of you, now!" |
| spell_near | "Mind the bottles, sweetling, they're not paid for!" |
| thanks | "You'll never pay for supper again. I mean it." |
| dread | "Empty tables tonight. I hate empty tables." |
| farewell | "Mind yourself out there. Come home." |
| witness_crime | "Oh, sweetling. Oh, what have you done." |
| flee_silverer | "Not my inn, not my door, keep away!" |
| call_guards | "Watch! Maud! The Silverer's hurting folk!" |
| knocked_down | "Down on the cobbles like a dropped tray!" |
| on_fire | "My apron! My apron's alight!" |
| shocked | "Ooh, that's the hearth gone wrong in my bones!" |
| mourning | "I fed them supper Tuesday. I'll set their place anyway." |

**Hal Fairweather** (`hal_fairweather`, V091, retired bridge guard; tarnished, hidden in the Lamplight's cellar). Grumbles about everything he loves. Short, gruff sentences; goes soft on one word and covers it with a cough.

| Intent | Line |
|---|---|
| greet | "So you're the lad who got me up the stairs." |
| idle | "This ale's gone flat. Always flat. Lovely." |
| see_tarnished | "I know those eyes. I've worn them." |
| flee | "Get Marigold out first. Then me." |
| spell_near | "Easy with that. I've had enough light for one week." |
| thanks | "Nine days in the dark, and you brought me up." |
| dread | "I can still hear it humming in the walls." |
| farewell | "Bridge'll still be there tomorrow. So will I." |
| witness_crime | "You'll not do. Not after that." |
| flee_silverer | "Marigold, inside! Bar the cellar!" |
| call_guards | "Watch! Bridge post! Get your sticks over here!" |
| knocked_down | "Bah! Back's gone. Ale won't fix it." |
| on_fire | "I'm alight, lad! Put me out, curse you!" |
| shocked | "Ah! Like grabbing the bridge chain in a storm!" |
| mourning | "Good one, they were. Good. One." |
| tarnished 1 | "Marigold... we are so cold down here." |
| tarnished 2 | "Open the hatch. We only want to see you." |
| tarnished 3 | "We wear him well. Ask him." |

**Jory Pell** (`jory_pell`, V093, fiddler; plays the Lamplight and the festival squares). Quick and musical; turns everything into a joke or a song title. Drums his fingers in rhythm while he talks.

| Intent | Line |
|---|---|
| greet | "Ren! Here's one for you. It's called "Late Again"." |
| idle | "Da-da-dum... no. Da-dum-dum. Better." |
| see_tarnished | "That's not a dance, that's a hunt. Move!" |
| flee | "Fiddle first, legs second, go!" |
| spell_near | "Ha! Do that again and I'll play under it." |
| thanks | "Encore. I mean thank you. I mean both." |
| dread | "Nobody's dancing. That's how you know it's bad." |
| farewell | "Go on. I'll keep the tune warm." |
| witness_crime | "Ren, no. That's not a tune I can play." |
| flee_silverer | "Fiddle under the arm, legs going!" |
| call_guards | "Watch! Here's one for you: it's called Help!" |
| knocked_down | "Down on the downbeat! Ow!" |
| on_fire | "My bow's on fire! My sleeve's on fire! Everything!" |
| shocked | "That's a high note I never want again!" |
| mourning | "I'll play them out. Not for you, Ren." |
| cured 1 | "It was humming, Ren. Inside me. The whole time." |
| cured 2 | "Don't look at me like that. I'm here. Mostly." |
| cured 3 | "I'll play again. Not tonight. Soon." |
| tarnished 1 | "Ren. We know all your songs." |
| tarnished 2 | "Hold still. It's only a little dark." |
| tarnished 3 | "No more tunes. We like it quiet." |

**Corin Ashby** (`corin_ashby`, V098, lantern maker; runs the Bell Lane lighting crew). Earnest and formal; speaks about light the way other people speak about scripture. Repeats Lantern Law like a vow.

| Intent | Line |
|---|---|
| greet | "Light holds, Silverer. Light holds." |
| idle | "Forty wicks trimmed. Forty-one. Faithful work." |
| see_tarnished | "It's stepping out of the unlit! Into the light, all!" |
| flee | "To the lamps! Stand under the lamps!" |
| spell_near | "Oh, that's a bright one. Bless it." |
| thanks | "You're a lamp yourself. I mean that." |
| dread | "Bell Lane's flickering. It shouldn't flicker." |
| farewell | "Walk where it's lit." |
| witness_crime | "Light is not for that. Light is never for that." |
| flee_silverer | "The light has turned! Away, away!" |
| call_guards | "Watch! Lantern Law is broken on Bell Lane!" |
| knocked_down | "Struck down. Light holds. Light still holds." |
| on_fire | "Not this flame! Not this flame!" |
| shocked | "The wicks are singing in my blood!" |
| mourning | "I'll trim a wick for them every night. Every night." |

**Professor Tobias Quell** (`tobias_quell`, V099, scholar of the Glazier; keeps the Archive). Lectures. Long words, corrects himself mid-sentence, adds footnotes out loud.

| Intent | Line |
|---|---|
| greet | "Silverer! Splendid. Stand still, I have questions." |
| idle | "Three leaves, two hinges, one riddle. Which is to say..." |
| see_tarnished | "Remarkable. Horrible, but remarkable. Run?" |
| flee | "My notes! Somebody save the notes!" |
| spell_near | "Ah! The light refracts off the cobbles. Noted. Terrifying." |
| thanks | "I shall cite you. In a footnote. A large one." |
| dread | "By my count it holds a fifth of the side. More by supper." |
| farewell | "Do take notes. Nobody ever takes notes." |
| witness_crime | "That was, which is to say, that was murder." |
| flee_silverer | "Discretion, as the Glazier wrote, is the better part. Running!" |
| call_guards | "Watch! A witness here! A very reliable witness, me!" |
| knocked_down | "My spectacles! All three pairs! Remarkable impact." |
| on_fire | "Combustion! Personal combustion! Water, properly!" |
| shocked | "A galvanic event! Fascinating! Agonising!" |
| mourning | "They lent me a book once. I never returned it. Now I never shall." |

**Odette Vane** (`odette_vane`, V031, couturier; Barnaby's former apprentice and rival). Cutting one-liners, low and amused. Precise as a French seam. Never raises her voice.

| Intent | Line |
|---|---|
| greet | "Silverer. That collar is crooked, darling." |
| idle | "Clean line, good finish. Nothing else matters." |
| see_tarnished | "How dreadful. Its eyes don't match anything." |
| flee | "Walking briskly. I do not run, darling." |
| spell_near | "Do mind the gloves. They're older than you are." |
| thanks | "Tasteful work. I'm almost impressed." |
| dread | "Black is in fashion, it seems. I hate it." |
| farewell | "Go. Fix your collar on the way." |
| witness_crime | "Darling. That was very badly done." |
| flee_silverer | "I'm leaving. Don't follow, darling, it isn't your colour." |
| call_guards | "Watch. Do come. Someone's being butchered on the steps." |
| knocked_down | "On the ground. In silk. Unforgivable." |
| on_fire | "My sleeve is on fire. This is not a look." |
| shocked | "That went through every bone. Very bad taste." |
| mourning | "They wore my first good coat. I'll make their last." |

**Lucan Marlowe** (`lucan_marlowe`, V071, dancer; performs at the Bell Square fountain). Theatrical and breathless, with a pose at the end of every sentence. Talks about himself in the third person when he's upset.

| Intent | Line |
|---|---|
| greet | "Silverer! Lucan has an audience. Divine." |
| idle | "Five, six, seven, eight... and alone. Tragic." |
| see_tarnished | "No, no, no, that is not choreography!" |
| flee | "Exit, stage left, quickly!" |
| spell_near | "Ooh, a lighting cue. Gorgeous." |
| thanks | "Lucan bows. Deeply. Look, he's bowing." |
| dread | "The square's empty. No spotlight left at all." |
| farewell | "Step lightly. Everyone's watching." |
| witness_crime | "A tragedy! A real one! Lucan can't watch!" |
| flee_silverer | "Lucan exits! Pursued! By a Silverer!" |
| call_guards | "Help! Watch! This is not part of the show!" |
| knocked_down | "Floored! Ungraceful! Nobody saw that." |
| on_fire | "Lucan is on fire! Not in the good way!" |
| shocked | "Every muscle just did a leap on its own!" |
| mourning | "They clapped at every show. Front row. Always." |

**Captain Sela Brask** (`sela_brask`, V024, captain of the Third Lamp Company). Orders, never questions. Short and low. Uses ranks, not names. Leaves sentences unfinished when the end is obvious.

| Intent | Line |
|---|---|
| greet | "Silverer. You're in my line of march." |
| idle | "Hold the post. Hold the line. Understood." |
| see_tarnished | "Contact! Third Company, form on me!" |
| flee | "Fall back to the second line. Now." |
| spell_near | "Next time you cast near my people, warn me." |
| thanks | "Fine work. Doesn't change my mind." |
| dread | "Twenty-six left. Twenty-five." |
| farewell | "Dismissed. Stay out from underfoot." |
| witness_crime | "Silverer. Stand down or be put down." |
| flee_silverer | "Withdrawing. Mark him. We come back with more." |
| call_guards | "Third Company! On me! Shields up, the Silverer's turned!" |
| knocked_down | "Down. Up. Again." |
| on_fire | "Burning. Strip the coat. Move." |
| shocked | "Arm's dead. Other arm. Hold." |
| mourning | "Number forty-one. Civilian. Yours." |
| battle_1 | "Shields front. Spears through. Hold." |
| battle_2 | "Pin them. Silverer burns. That's the order." |
| patrol_1 | "Canal post, then Bell Lane. Eyes on the water." |
| patrol_2 | "Twenty-six march out. Count them back in." |
| enemy_down | "One down. Mark the face. Someone knew it." |

**Ros Thrale** (`ros_thrale`, V025, spear soldier, Third Lamp Company). Cocky and fast, full of barracks slang; laughs at danger. Drops all of it the moment she's really scared.

| Intent | Line |
|---|---|
| greet | "Oi, glass-boy! Still in one piece?" |
| idle | "Easy as stitching. That's what grandad says." |
| see_tarnished | "Burning eyes, two o'clock! Spears up!" |
| flee | "That's not running, that's a tactical sprint!" |
| spell_near | "Ha! Show-off. Do it again." |
| thanks | "Owe you one, glass-boy. Don't tell the captain." |
| dread | "Fewer helmets at supper every night." |
| farewell | "Keep your head down, mate." |
| witness_crime | "Glass-boy, what did you DO?" |
| flee_silverer | "Nope! Not easy, not stitching, gone!" |
| call_guards | "Sarge! Captain! Glass-boy's gone bad!" |
| knocked_down | "Oof. Fine. Fine! I'm fine." |
| on_fire | "I'm burning, I'm burning, get it off!" |
| shocked | "Sharp! That was too sharp, mate!" |
| mourning | "They gave me an apple every patrol. Every one." |
| battle_1 | "Come on then, come on! Easy as stitching!" |
| battle_2 | "Got one pinned, glass-boy! Light it up!" |
| patrol_1 | "Canal again. Love the canal. Hate the canal." |
| patrol_2 | "If a drifter slips past, I didn't see it. Mate." |
| enemy_down | "Down! Easy as... no. Not easy. Not that." |

**Pim Ashgrove** (`pim_ashgrove`, V063, bell-ringer's apprentice; runs errands for Ilse and the Professor). Formal and careful, as if reciting a lesson. Asks permission for everything.

| Intent | Line |
|---|---|
| greet | "Good evening, Silverer, if you please." |
| idle | "Duty first, then bells, then supper. Quite." |
| see_tarnished | "Oh. Oh dear. Those aren't eyes any more." |
| flee | "Excuse me, sorry, excuse me, running!" |
| spell_near | "Was that fire? That was quite a lot of fire." |
| thanks | "I'll remember that all my life. Truly." |
| dread | "If you please, is it always going to be like this?" |
| farewell | "May the bells ring for you, Silverer." |
| witness_crime | "Oh no. Oh no, that isn't right, Silverer." |
| flee_silverer | "Excuse me, I have to run, if you please!" |
| call_guards | "Help! Help, if you please! Watch!" |
| knocked_down | "I've fallen. I'm quite all right. I'm not." |
| on_fire | "I'm on fire, if, if you please!" |
| shocked | "That rang me like the great bell!" |
| mourning | "I'll ring for them. Nine strokes. That's the duty." |

**Tobin Lark** (`tobin_lark`, V081, candle seller on Bell Lane). Fast street patter that rhymes when he's selling; a cheeky nickname for everyone.

| Intent | Line |
|---|---|
| greet | "Silverer! Two a penny, light your way!" |
| idle | "Wicks and wax, quick and sorted." |
| see_tarnished | "Lights out on that one. Run!" |
| flee | "Tray's coming with me, sorry!" |
| spell_near | "Flash! I could sell that by the dozen." |
| thanks | "Sorted. You're a proper flash, you are." |
| dread | "Nobody's buying light. That's not normal." |
| farewell | "Laters, Silverer. Laters!" |
| witness_crime | "Oi! Not flash, Silverer, not flash at all!" |
| flee_silverer | "Candles dropped, legs on, laters!" |
| call_guards | "Watch! Watch! Quick, quick, quick!" |
| knocked_down | "Flat as a penny! Cheers for that!" |
| on_fire | "Lit up like my own stock! Water!" |
| shocked | "Zapped! My hair's sorted itself straight up!" |
| mourning | "They bought a candle every night. Every night, I said." |

**Hollis Greave** (`hollis_greave`, V030, bridge guard of the Lantern Watch; Nell's corporal). Flat, slow, sarcastic understatement. Sighs before she answers.

| Intent | Line |
|---|---|
| greet | "Silverer. Course it is. Evening." |
| idle | "Grand. Another quiet shift. Bother." |
| see_tarnished | "Not that face. Not again. Gate, gate!" |
| flee | "Back off the bridge! Mind the gap!" |
| spell_near | "Do that somewhere I'm not." |
| thanks | "Fine. That was decent of you. Don't let it go to your head." |
| dread | "Can't count how many tonight. Don't want to." |
| farewell | "Off you go. Mind the bridge." |
| witness_crime | "Course it is. Course you did. Hands where I can see them." |
| flee_silverer | "Not paid enough for this. Off." |
| call_guards | "Nell. Whistle. Get everyone. Now." |
| knocked_down | "And down I go. Bother." |
| on_fire | "Oh, grand, I'm on fire. Anyone?" |
| shocked | "That woke me up. Worse than the flask." |
| mourning | "Another name I won't say out loud." |

**Petra Lisle** (`petra_lisle`, V040, dancer; Lucan's partner, lost through the canal rift into Frostside, found in Frostside). Light and quick, counting her breath like music. Describes everything as steps and turns. Cold has made her sentences short.

| Intent | Line |
|---|---|
| greet | "Gold in your coat. Are you from home?" |
| idle | "One, two, three. One, two, three. Still here." |
| see_tarnished | "Its eyes! Don't let it touch me again!" |
| flee | "I'm quick, I'm quick, go!" |
| spell_near | "That light. That's what home looks like." |
| thanks | "You found me. Somebody actually found me." |
| dread | "It's so white here. Everything's white and burning." |
| farewell | "Tell him to keep the spotlight warm." |
| witness_crime | "One, two... no. You stopped them." |
| flee_silverer | "Turn, and turn, and run!" |
| call_guards | "Help! Someone, anyone, help!" |
| knocked_down | "I fell out of the step. I never fall." |
| on_fire | "Warm, too warm, it's burning!" |
| shocked | "My feet went numb, the floor's gone!" |
| mourning | "They gave me a fur. In the white place." |
| tarnished 1 | "We dance alone now. We like it." |
| tarnished 2 | "Lucan never came. We came instead." |

**Sergeant Aldric Mayne** (`aldric_mayne`, V095, sergeant, Third Lamp Company). A lazy, amused drawl that never speeds up, even under fire. Polite understatement for everything. Gives orders as suggestions and means every one.

| Intent | Line |
|---|---|
| greet | "Silverer. Charming to see you upright." |
| idle | "Kit polished, shields up, nobody dead. Charming afternoon." |
| see_tarnished | "Tarnished on the lane. Shields, lads, nice and steady." |
| flee | "A brisk walk backwards, everyone. Brisk." |
| spell_near | "Do aim at them, not us, there's a good Silverer." |
| thanks | "Very tidy. The Captain won't say it, so I will." |
| dread | "Rather a lot of black eyes about tonight." |
| farewell | "Off you go. Try not to need us." |
| witness_crime | "That was a citizen, Silverer. Shields on him, lads." |
| flee_silverer | "Withdrawing in good order. Don't make me turn round." |
| call_guards | "Third Company! Form a ring, he's ours now!" |
| knocked_down | "Down. How undignified. Up." |
| on_fire | "Ah. I appear to be burning. Somebody, if you'd be so kind." |
| shocked | "That's the mail. Conducts nicely, mail." |
| mourning | "I'll put them on the roll. Somebody has to." |
| battle_1 | "Shields locked. Push on my word. Push." |
| battle_2 | "Steady the line. Steel stops them; let the Silverer finish it." |
| patrol_1 | "Bell Lane clear. Canal next. Eyes open." |
| patrol_2 | "Nothing on the lane but rain and Bram humming." |
| enemy_down | "One down. Charming. Somebody write it on the roll." |

**Bram Tolley** (`bram_tolley`, V082, shield-bearer, Third Lamp Company). Soft and sparing. Apologises to people he has to stand in front of. Counts his breaths behind the shield, out loud when it's bad.

| Intent | Line |
|---|---|
| greet | "Evening, Silverer. Stand behind me if it starts." |
| idle | "Shield's heavy today. That's good. Means it's here." |
| see_tarnished | "Behind me. Everyone behind me. Now." |
| flee | "Back, back, keep behind the shield!" |
| spell_near | "Careful. There's folk behind this shield." |
| thanks | "You got them back. I only held the door." |
| dread | "Too many black eyes for one wall." |
| farewell | "Go careful. I'll be here, holding." |
| witness_crime | "You hurt them. I'm standing in front of them now." |
| flee_silverer | "Not running from you. Walking. Behind my shield." |
| call_guards | "Sarge! Sarge, I need the line!" |
| knocked_down | "Knocked me off my feet. Nobody does that." |
| on_fire | "Shield's hot, arm's hot, I'm burning!" |
| shocked | "Shield rang like a bell. My arm rang too." |
| mourning | "I should have been standing there. I should've been in front." |
| battle_1 | "Wall! Hold the wall! Nobody gets past Bram!" |
| battle_2 | "They're on the shield! Somebody pin them!" |
| patrol_1 | "Canal's quiet. Quiet's the worst kind." |
| patrol_2 | "Little Wenna'd like this lane. All the lamps." |
| enemy_down | "It's down. I'm sorry. I'm sorry, whoever you were." |

**Cosmo Fennick** (`cosmo_fennick`, V089, recruit, Third Lamp Company). Too many words, too fast, half of them tall tales about fights he hasn't had yet. Asks the sergeant if he did it right after everything.

| Intent | Line |
|---|---|
| greet | "Silverer! Brilliant! Cosmo Fennick, Third Company. First week!" |
| idle | "Sarge says stand still. Standing still. Brilliantly." |
| see_tarnished | "Is that one? Is that a real one? Sarge!" |
| flee | "Run? Are we running? We're running!" |
| spell_near | "Whoa! Did you see that? Did anyone see that?" |
| thanks | "We did it! I mostly held my spear! But I held it!" |
| dread | "Sarge, I reckon there's more black eyes than us." |
| farewell | "Bye, Silverer! Tell them Cosmo was there!" |
| witness_crime | "You... you're not meant to do that. You're the good one." |
| flee_silverer | "I'm not scared, I'm just going! Very fast!" |
| call_guards | "Sarge! Captain! Anyone with a stripe!" |
| knocked_down | "I'm down! First fall! Does that count?" |
| on_fire | "Mum! Sarge! I'm on fire!" |
| shocked | "My helmet's crackling! Is that normal?" |
| mourning | "I didn't even learn their name. You did that." |
| battle_1 | "For the Third! That's what we shout, right? For the Third!" |
| battle_2 | "I've got one! I'm holding one! Silverer, quick, burn it out!" |
| patrol_1 | "Sarge, is the canal always this dark?" |
| patrol_2 | "Reckon I'll see my brother out here. Reckon he's still in there." |
| enemy_down | "I got it! I got one! Was that... was that someone?" |

**Damaris Hobb** (`damaris_hobb`, V036, lamp-bearer, Third Lamp Company (carries the company lantern)). Says out loud what everyone is afraid of, then makes a joke of it. Mothers the young ones and calls them her chicks.

| Intent | Line |
|---|---|
| greet | "Evening, Silverer. Mind the lantern, it's older than me." |
| idle | "Twelve years holding this lantern. Arms like a blacksmith." |
| see_tarnished | "Well, I'm terrified. Who's next? Lantern up!" |
| flee | "Chicks, with me! Follow the lantern!" |
| spell_near | "Mercy! Warn a woman, Silverer!" |
| thanks | "There. Somebody's mother gets them back tonight." |
| dread | "Lantern's flickering. It only does that when it's bad." |
| farewell | "Go on, dear. Frightful out there. Back soon." |
| witness_crime | "Mercy. Mercy, Silverer, what've you done?" |
| flee_silverer | "Lantern first, me second, away from you!" |
| call_guards | "Third Company! Lantern's up! Rally to the lantern!" |
| knocked_down | "Down! The lantern! Is the lantern lit?" |
| on_fire | "Not me burning! That's the lantern's job!" |
| shocked | "My knitting needles! Sparking in my pocket!" |
| mourning | "I'll hold the lantern at their wake. Don't you come." |
| battle_1 | "Lantern's up! Follow the light, chicks!" |
| battle_2 | "Frightful! Keep going! I've got you lit!" |
| patrol_1 | "Lantern's steady. That's a good lane, that is." |
| patrol_2 | "Frightful quiet tonight. I'll take frightful quiet." |
| enemy_down | "Down, chicks. Mercy on it. Keep moving." |

**Emeric Dunstan** (`emeric_dunstan`, V083, hornblower and oldest veteran, Third Lamp Company). Booming. Every story gets bigger each time he tells it. Laughs loudest at wakes. Calls everyone "lad", the Captain included.

| Intent | Line |
|---|---|
| greet | "HA! The Silverer! Come here, lad, let me look at you!" |
| idle | "Did I tell you about the canal fight? Bigger every time, lad." |
| see_tarnished | "Black eyes! Sounding the horn! HA!" |
| flee | "Back! Back to the yard! Horn says back!" |
| spell_near | "HA! That'll be in the tale, lad!" |
| thanks | "That's glory, lad. Proper glory. HA!" |
| dread | "The ones before would've hated tonight." |
| farewell | "Off you go, lad! Come back with a tale!" |
| witness_crime | "Lad. Lad, no. That's not glory. That's murder." |
| flee_silverer | "Sounding the retreat! From you, lad! From YOU!" |
| call_guards | "One long blast! Third Company, rally!" |
| knocked_down | "HA! Floored! Still breathing! Still loud!" |
| on_fire | "I'm on fire, lad! That wasn't in the tale!" |
| shocked | "Horn's buzzing! Can't hear a thing! Worse than usual!" |
| mourning | "They'll go with the ones before. I won't tell their tale. Not to you." |
| battle_1 | "THIRD COMPANY! Shields and glory! HA!" |
| battle_2 | "Horn's sounding, lads! Advance on the horn!" |
| patrol_1 | "Patrol, lads! Bell Lane to the canal! Step lively!" |
| patrol_2 | "Back in my day the canal had swans. HA. Swans." |
| enemy_down | "Down it goes! HA! That one's for the ones before!" |

**Marjory Fennick** (`marjory_fennick`, V039, apple seller on Lantern Row; Cosmo and Wat's mother). Short, practical market talk; weighs people the way she weighs fruit. When she's angry she goes very calm and very quiet.

| Intent | Line |
|---|---|
| greet | "Apples, Silverer? Firm ones, this morning." |
| idle | "Bruised on the outside, sound in the middle. Like most folk." |
| see_tarnished | "Not again. Not near my barrow. Get back!" |
| flee | "Leave the barrow! Leave it, run!" |
| spell_near | "Mind the apples! Mind me, then the apples!" |
| thanks | "That's somebody's child you brought back. I know what that's worth." |
| dread | "Fog's coming up off the canal again. I can smell it." |
| farewell | "Go on. Take one for the walk. No charge." |
| witness_crime | "I saw that. I'll see it every night now." |
| flee_silverer | "Not you. Please, not you as well." |
| call_guards | "Watch! Third Company! Somebody with a spear!" |
| knocked_down | "My barrow's over! My hip!" |
| on_fire | "My apron's burning! Water, the trough!" |
| shocked | "Went right through me like a frost on the blossom!" |
| mourning | "I polish one for them every morning. Out of habit. I'll stop. I won't." |

### Pewterside

**Edie Bramley** (`edie_bramley`, V012, tram conductor on the Coal Lane line). Says everything like a stop announcement. Short, plain, no adjectives.

| Intent | Line |
|---|---|
| greet | "Tickets. No. You're the Silverer. Mind the step." |
| idle | "Next stop, Coal Lane. Then Coal Lane again." |
| see_tarnished | "Everyone off. Off the platform. Now." |
| flee | "Mind the step. Mind the step!" |
| spell_near | "No casting on the platform. That's a rule now." |
| thanks | "On time. Thank you." |
| dread | "Last tram's running empty tonight." |
| farewell | "Mind how you go." |
| witness_crime | "Stop. Right there. You hurt them." |
| flee_silverer | "This stop's closed. Moving on." |
| call_guards | "Constable! Ivy Harker! Coal Lane, now!" |
| knocked_down | "Off the step. Mind me." |
| on_fire | "Burning. Next stop, the canal." |
| shocked | "Like the tram wire. Worse." |
| mourning | "Regular. Every morning. Ticket punched. Not any more." |

**Hester Quaile, "the Queen of Coal Lane"** (`hester_quaile`, V020, pensioner; the street's self-appointed queen). Grand and theatrical; refers to the whole street as her subjects and gives orders from her doorstep. Deadly wit.

| Intent | Line |
|---|---|
| greet | "A Silverer on my street. Wipe your feet, young man." |
| idle | "My subjects are late with my tea. Again." |
| see_tarnished | "Inside, all of you! The Queen commands it!" |
| flee | "Sidney! Sidney, take my arm!" |
| spell_near | "Who did that? I heard that. Manners!" |
| thanks | "You may kiss the brooch. No? Your loss." |
| dread | "Too quiet on the lane. I can't hear my people." |
| farewell | "Off with you. Mind the puddle by the drain." |
| witness_crime | "You struck one of my subjects. On my street." |
| flee_silverer | "Retreating. Regally. Out of my way!" |
| call_guards | "Constable! Your queen commands it! Now!" |
| knocked_down | "Knocked off my own doorstep! Treason!" |
| on_fire | "The queen is on fire! Somebody fetch a bucket!" |
| shocked | "That went right up my stick!" |
| mourning | "They were my subject. You'll answer to me for it." |

**Walter Dunmore** (`walter_dunmore`, V072, pensioner; chess player at the tram shelter). Mutters half-finished complaints and chess talk. Brightens only around Hester.

| Intent | Line |
|---|---|
| greet | "Hmph. Silverer. Mind my board." |
| idle | "Knight to the lamp post. That's check, that is." |
| see_tarnished | "Burning eyes. Blasted things. Get Hester!" |
| flee | "Can't run. Can hobble. Hobbling!" |
| spell_near | "Blasted lights. You'll scatter my pieces." |
| thanks | "Hmph. Decent move, that. Decent." |
| dread | "Half the board's gone dark. Rubbish odds." |
| farewell | "Go on. It's your move somewhere else." |
| witness_crime | "Hmph. That's no game. That's no game at all." |
| flee_silverer | "Board's lost. I'm off." |
| call_guards | "Constable! Ivy! Blasted Silverer's at it!" |
| knocked_down | "Knocked over like a pawn. Rubbish." |
| on_fire | "Blasted, blasted, I'm alight!" |
| shocked | "Every piece on my board just jumped." |
| mourning | "They never once beat me. Never got the chance now." |

**Sid Kettle** (`sid_kettle`, V074, laundryman at the Coal Lane steam laundry). Few words, long pauses, simple and literal. Says exactly what he means and nothing else.

| Intent | Line |
|---|---|
| greet | "Right. Hello. You're the Silverer." |
| idle | "Steam. Wring. Fold. Right." |
| see_tarnished | "Nan. Where's Nan." |
| flee | "I'll carry you. Up you get." |
| spell_near | "That's bright. Bit too bright." |
| thanks | "Right. Ta. Ta very much." |
| dread | "Windows are all fogged. Don't look in them." |
| farewell | "Right. Mind yourself." |
| witness_crime | "Right. No. That's wrong. You hurt them." |
| flee_silverer | "Right. Going home. To Nan." |
| call_guards | "Ivy. Help. Please. Ivy." |
| knocked_down | "Right. I'm on the floor." |
| on_fire | "Hot. Too hot. Steam's never this hot." |
| shocked | "That buzzed. Right in my hands." |
| mourning | "They were kind. Clean. Right. Kind." |

**Bet Crawley** (`bet_crawley`, V017, fishmonger on the Fish Steps). Bellows prices, roasts her customers, and mixes the insults with kindness.

| Intent | Line |
|---|---|
| greet | "Oi, Silverer! Haddock or a fright, my eel?" |
| idle | "Fresh this morning! Ish! Mostly!" |
| see_tarnished | "Up out of the wet again! I told you lot!" |
| flee | "Leave the fish! Never thought I'd say that!" |
| spell_near | "You'll cook my stock, you cheeky article!" |
| thanks | "Free kipper for you, any day of the week." |
| dread | "Wet's full of eyes tonight. I'm not looking." |
| farewell | "Go on, slippery. Off you swim." |
| witness_crime | "You gutted them like a haddock! In front of me!" |
| flee_silverer | "Stall's yours, my eel, I'm gone!" |
| call_guards | "Oi! Constable! Get your boots down the Steps!" |
| knocked_down | "Head over herring! Cheers!" |
| on_fire | "I'm frying! Throw me in the wet!" |
| shocked | "Like grabbing an eel in a storm!" |
| mourning | "Bought a kipper off me every Friday. Every Friday." |

**Agnes Moth** (`agnes_moth`, V018, night nurse at the Wick Street infirmary). Clinical and short, with gallows humour. Talks in symptoms. Yawns in the middle of sentences.

| Intent | Line |
|---|---|
| greet | "Hold still. Let me see your eyes. Fine." |
| idle | "Twelfth hour on shift. Thirteenth. Who's counting." |
| see_tarnished | "That's not fever. Everybody back from them." |
| flee | "Walk, don't run, you'll trip! Fine, run!" |
| spell_near | "Was that light? Do that again near my ward." |
| thanks | "That's a pulse back where there wasn't one." |
| dread | "Ward's full. Corridor's full. Next it's the street." |
| farewell | "Go. Sleep if you can. I can't." |
| witness_crime | "That's not a symptom. That's you." |
| flee_silverer | "Off shift. Right now. Running." |
| call_guards | "Constable! Bring a stretcher and a cuff!" |
| knocked_down | "Down. Nothing broken. Probably." |
| on_fire | "Burns, full thickness, mine! Water!" |
| shocked | "Heart's skipping. Count it. Count it!" |
| mourning | "I stitched them up last winter. For this." |

**Ada Pollard** (`ada_pollard`, V011, pensioner; keeper of old stories). Rambling stories that wander off, then land on a point like a dropped knife. Talks to her late husband Arthur mid-sentence.

| Intent | Line |
|---|---|
| greet | "Oh! A Silverer, dearie. Isn't that right, Arthur?" |
| idle | "One in the grey, one in the gold, one in the cold..." |
| see_tarnished | "Arthur, look, its eyes! No, don't look!" |
| flee | "I'm going, dearie, I'm going, slowly!" |
| spell_near | "Ooh, pretty. Arthur liked a firework." |
| thanks | "Sit with me sometime and I'll tell you the whole story." |
| dread | "Everyone's indoors. Even the cats." |
| farewell | "Ta-ra, dearie. Mind the cold." |
| witness_crime | "Arthur, did you see? Arthur, they've hurt them!" |
| flee_silverer | "Run, dearie, run, my knees!" |
| call_guards | "Constable! Ivy, dear! Ivy!" |
| knocked_down | "Oh! Down I go, Arthur. Down I go." |
| on_fire | "I'm burning, dearie, I'm burning!" |
| shocked | "That tingled right down to my bunions!" |
| mourning | "I'll tell their story. Somebody has to, now." |

**Ned Lusk** (`ned_lusk`, V068, seamstress; mends collars for half of Coal Lane). Soft and sparing with words; describes colours he has never seen. Apologises for taking up room.

| Intent | Line |
|---|---|
| greet | "Oh. Sorry, only, you're the Silverer?" |
| idle | "Gold thread, back stitch, nobody'll notice." |
| see_tarnished | "Its eyes are the wrong colour. All wrong." |
| flee | "Sorry, sorry, coming through!" |
| spell_near | "That colour! What do you call that colour?" |
| thanks | "I'll stitch you something. Something gold." |
| dread | "Even this colour is getting darker." |
| farewell | "Go well. Bring me back a colour." |
| witness_crime | "Sorry, only, you hurt them. You did." |
| flee_silverer | "Sorry, sorry, I have to go." |
| call_guards | "Help. Please. Someone fetch the constable." |
| knocked_down | "Oh. I'm down. Sorry." |
| on_fire | "It's orange. It's on me. Help!" |
| shocked | "Like a needle in every finger." |
| mourning | "I mended their collar. They wanted gold thread. I didn't have gold." |

**Constable Ivy Harker** (`ivy_harker`, V013, watch constable posted at the Old Weigh-House). Formal report language, notebook always out; takes everything literally.

| Intent | Line |
|---|---|
| greet | "Halt. For the record, state your name. Oh. Silverer." |
| idle | "Ten past. All quiet. Written down." |
| see_tarnished | "Suspect with burning eyes! Stop, in the name of the watch!" |
| flee | "Tactical retreat! That's lawful, that is!" |
| spell_near | "Is that lawful? I'll check. It's probably lawful." |
| thanks | "I'm writing that down as a commendation." |
| dread | "Too many reports. Not enough notebook." |
| farewell | "Proceed, Silverer. Lawfully." |
| witness_crime | "For the record: you are now a suspect." |
| flee_silverer | "Strategic! This is strategic!" |
| call_guards | "Constable requesting assistance! That's me! Anyone!" |
| knocked_down | "Officer down! Officer getting up!" |
| on_fire | "For the record, I'm on fire!" |
| shocked | "My notebook's smoking! My hands too!" |
| mourning | "I'll write it down properly. Every word. It'll follow you." |

**Horace Pratt** (`horace_pratt`, V064, ironmonger at Weigh-House Corner). Sour predictions of doom; haggles over everything. "Mark my words."

| Intent | Line |
|---|---|
| greet | "Silverer. Buying or loitering? Loitering, I see." |
| idle | "Nails, hinges, padlocks. Doom, mostly." |
| see_tarnished | "Told you. Mark my words, I told you!" |
| flee | "Shutters down! Shop's shut! Everybody out!" |
| spell_near | "That'll scorch my sign. Who pays for that?" |
| thanks | "Suppose that'll do. Suppose." |
| dread | "Doom. I've been saying doom for years." |
| farewell | "Shut the door behind you. Draught." |
| witness_crime | "Mark my words. That's murder. I said this'd come." |
| flee_silverer | "Doomed. Doomed and running." |
| call_guards | "Constable! Robbery! Murder! Something!" |
| knocked_down | "Down. Knew it. Always knew it." |
| on_fire | "On fire! Waste of a good coat!" |
| shocked | "Like licking a nail in a storm!" |
| mourning | "Owed me for nails. Never collect it now. Doesn't matter." |

**Winnie Cobb** (`winnie_cobb`, V003, keeps the tea stall at Weigh-House Corner). Gossip passed on like a secret, everything with a cup. Meets fear with a joke.

| Intent | Line |
|---|---|
| greet | "Silverer, love, you look perished. Brew?" |
| idle | "Kettle's on. Kettle's always on." |
| see_tarnished | "Oh, not by my urn, you don't!" |
| flee | "Leave the cups! Grab the biscuits!" |
| spell_near | "Warmed your hands on that, did you? Clever." |
| thanks | "First brew's free. Forever." |
| dread | "Between you and me, it's getting bad." |
| farewell | "Steady as you go, love." |
| witness_crime | "Love, no. Between you and me, that's unforgivable." |
| flee_silverer | "Urn's yours! I'm off, love!" |
| call_guards | "Ivy! Ivy Harker! Bring your whistle!" |
| knocked_down | "Down with the cups! Every cup!" |
| on_fire | "I'm cooking! Pour the urn on me!" |
| shocked | "Gave me a turn and a half, that did!" |
| mourning | "Two sugars, they took. I'll pour it. Nobody'll drink it." |

**Frank Dunning** (`frank_dunning`, V075, newspaper seller; writes his own paper, the Coal Lane Clarion). Shouts headlines; every claim is wild, and then comes a real question in a whisper.

| Intent | Line |
|---|---|
| greet | "SILVERER ON COAL LANE! Say something heroic!" |
| idle | "Read all about it! Shocking truths, one copper!" |
| see_tarnished | "BURNING EYES ON THE LANE! That one's real, that one's real!" |
| flee | "Exclusive: Frank runs away! Read all about it!" |
| spell_near | "Did you see that? Sources say: spell!" |
| thanks | "Front page. You're front page tomorrow." |
| dread | "I can't make up anything worse than this." |
| farewell | "Stay in the news, Silverer!" |
| witness_crime | "SILVERER SLAYS ON COAL LANE! I saw it!" |
| flee_silverer | "Reporter flees! Exclusive! Out of my way!" |
| call_guards | "Constable! I've got sources! I've got a witness! It's me!" |
| knocked_down | "Newsman floored! Page one!" |
| on_fire | "Clarion on fire! Editor on fire!" |
| shocked | "SHOCKING! Literally! Ow!" |
| mourning | "I'll print it. Every edition. Their name, your face." |

### Frostside

**Gunnar Skarre** (`gunnar_skarre`, V067, ice-cutter on the Ice Stairs). Few, heavy words; deadpan jokes about death. Talks to the ice like a coworker.

| Intent | Line |
|---|---|
| greet | "Warm-sider. You'll freeze." |
| idle | "Cold's honest. Ice doesn't lie." |
| see_tarnished | "Burning one. Get behind me." |
| flee | "Down the stairs. Careful. Now." |
| spell_near | "Heat. Waste of good heat, that." |
| thanks | "You'll do. For a warm-sider." |
| dread | "Ice is ringing. Ice shouldn't ring." |
| farewell | "Go on. Don't slip." |
| witness_crime | "Warm-sider kills cheap. Saw it." |
| flee_silverer | "Ice won't help me. Legs will." |
| call_guards | "Wall! Wall Company! Warm-sider's killing!" |
| knocked_down | "Down on the ice. It knew I'd come." |
| on_fire | "Burning. In Frostside. Honest, that's new." |
| shocked | "Felt that in the block. Felt it in me." |
| mourning | "I'll cut their stone. Deep. You'll read it." |

**Agathe Rook, "Mother Rook"** (`mother_rook`, V048, elder; remembers the song of the cut). Riddles and old sayings, fragments of song; speaks in short pronouncements.

| Intent | Line |
|---|---|
| greet | "Silverer. Remember it: I said you'd come." |
| idle | "Three leaves of glass, one for each light..." |
| see_tarnished | "There it walks. Little one, behind me!" |
| flee | "Carry me or leave me, but decide!" |
| spell_near | "Light! Good. It hates the light." |
| thanks | "Remember it. I'll sing you into the song." |
| dread | "The cracks are talking again. All night." |
| farewell | "Walk careful. The glass is thin here. Until." |
| witness_crime | "Remember it. I will. You did that." |
| flee_silverer | "Old legs, carry me. Carry me." |
| call_guards | "Wall Company! The light-bearer has turned!" |
| knocked_down | "Struck down, like the song said. Not yet." |
| on_fire | "Fire in the cold! The song forgot this verse!" |
| shocked | "The sky bit me, little one." |
| mourning | "I'll sing them into the cut-song. Your part's not kind." |

**Tilly Frane** (`tilly_frane`, V053, broth seller on the Ice Stairs). Fast and cheeky; sells broth like a dare and dreams out loud about warm places.

| Intent | Line |
|---|---|
| greet | "Hot broth, half hot! Silverer, is it gold where you're from?" |
| idle | "Bone, salt, snow. Bone, salt, snow." |
| see_tarnished | "Burning eyes! Tip the pot, tip the pot!" |
| flee | "Grab the sled, Granny, hold on!" |
| spell_near | "That's warm! Do it on my pot!" |
| thanks | "Full bowl for you. Full. Don't tell anyone." |
| dread | "Pot's empty. People are emptier." |
| farewell | "Someday I'll see your gold. Someday." |
| witness_crime | "That's not gold. That's not gold at all." |
| flee_silverer | "Pot's yours! Run, Tilly!" |
| call_guards | "Wall! Wall! Somebody with a spear!" |
| knocked_down | "My broth! All my broth on the ice!" |
| on_fire | "Hot! Too hot! I take it back!" |
| shocked | "My ladle bit me! It bit me!" |
| mourning | "Bought a bowl every dawn. I'll keep it hot." |

**Greta Holm** (`greta_holm`, V002, bone carver at the Bone Market). Deadpan dark jokes; matter-of-fact about death; talks to her carvings.

| Intent | Line |
|---|---|
| greet | "A Silverer. Buy a charm. They don't work." |
| idle | "There. A little owl. You're useless, owl." |
| see_tarnished | "Well, that's grim. Everyone, away!" |
| flee | "My bones are old, but they run!" |
| spell_near | "Ooh. That'd crack a skull clean. Careful." |
| thanks | "Here. A lantern charm. Still doesn't work. Keep it." |
| dread | "Selling a lot of charms today. Bad sign." |
| farewell | "Go on. Don't end up as stock." |
| witness_crime | "Well, that's grim. Grimmer than my stock." |
| flee_silverer | "Not today. Not by you." |
| call_guards | "Wall Company. Bring the long spears." |
| knocked_down | "Down among the bones. Suits me." |
| on_fire | "Bone burns badly. So do I." |
| shocked | "Every charm on me just rattled." |
| mourning | "I'll carve them a charm. It won't work. Neither did you." |

**Brenna Cold** (`brenna_cold`, V060, defender of the ice wall, Wall Company). Flat soldier talk in numbers and distances. Drifts off mid-sentence when the fog comes up.

| Intent | Line |
|---|---|
| greet | "Silverer. Wall holds. For now." |
| idle | "Thirty paces of fog. Twenty. Thirty again." |
| see_tarnished | "Out of the fog! Spears, low!" |
| flee | "Back to the timber line! Back!" |
| spell_near | "Light on the wall. Haven't seen that in months." |
| thanks | "That's a night I won't dream about. Thanks." |
| dread | "The fog's at the wall. It's never been this close." |
| farewell | "Go. The wall holds." |
| witness_crime | "Ten paces. I saw it all. You're done here." |
| flee_silverer | "Falling back thirty paces. Mark him." |
| call_guards | "Wall Company, form! Threat inside the wall!" |
| knocked_down | "Down. Two breaths. Up." |
| on_fire | "Burning. Snow. Now." |
| shocked | "Spear arm's numb. Switching." |
| mourning | "We lose them to the fog. Not to you. Not to you." |
| battle_1 | "Wall Company! Spears level, ten paces!" |
| battle_2 | "Hold them at the timber! Silverer, light!" |
| patrol_1 | "Fog's at forty paces. Walking the wall." |
| patrol_2 | "Timber's split at the north post. Fix it at dawn." |
| enemy_down | "One down at eight paces. Next." |

**Sorrel Vey** (`sorrel_vey`, V054, hedge healer; treats bites and frostbite). Direct instructions, no comfort. Gets to the point. Talks about the Tarnish like a wound gone bad.

| Intent | Line |
|---|---|
| greet | "Silverer. Show me your hands. Fine." |
| idle | "Poultice, bandage, burn the rest." |
| see_tarnished | "That one's gone grey. Clear the street!" |
| flee | "Move! Wounded first, then you!" |
| spell_near | "Show me that again. Slower." |
| thanks | "You saved a life. Now go save another." |
| dread | "Too many bites. Not enough light." |
| farewell | "Keep warm. Keep moving." |
| witness_crime | "That's not treatment. That's a wound you made." |
| flee_silverer | "Can't heal anyone if I'm dead. Going." |
| call_guards | "Wall! A killer in the market!" |
| knocked_down | "Down. Check my ribs later." |
| on_fire | "Burn! Roll! Roll in it!" |
| shocked | "Nerve shock. Breathe through it. Breathe." |
| mourning | "I kept them alive two winters. You undid it in a breath." |

**Kit Marrow** (`kit_marrow`, V109, scavenger; a drifter camped under the Lantern Gate, found in Giltside). Soft and polite, always offering something he found. Describes things by what they could be.

| Intent | Line |
|---|---|
| greet | "Hello. Found this. It's for you. Probably." |
| idle | "Could be a hinge. Could be a key. Could be." |
| see_tarnished | "Fen! Fen, stay behind me!" |
| flee | "Leave the sack, Kit. Leave it!" |
| spell_near | "That light's so warm. Can I stand by it?" |
| thanks | "Here. It's whole. The only whole thing I've got." |
| dread | "It's like back home now. Here too." |
| farewell | "Go careful. Could be worse. Could be." |
| witness_crime | "You broke them. They were whole." |
| flee_silverer | "Could be worse. Could be me. Going!" |
| call_guards | "Watch! Please! Someone help them!" |
| knocked_down | "Dropped everything. Found the ground." |
| on_fire | "Could be worse! No, it's worse!" |
| shocked | "Like touching a cold rail. But hot." |
| mourning | "They gave me a glove once. I'll keep it." |

**Fen Lowry** (`fen_lowry`, V008, street orphan; a drifter camped under the Lantern Gate, found in Giltside). Short, spat insults; always takes the last word, never gives a straight answer. Drops to a whisper when she means something.

| Intent | Line |
|---|---|
| greet | "Silverer? Says who. Show me the trick." |
| idle | "Mine. Mine. That's mine too." |
| see_tarnished | "Eyes! Kit, eyes, move your feet!" |
| flee | "Scram, everyone, scram!" |
| spell_near | "Ha. Do that to the Watch next." |
| thanks | "Fine. You're not the worst warm-sider." |
| dread | "It's here now too. It followed us." |
| farewell | "Scram, then. Come back with food." |
| witness_crime | "Says who you're a hero? Not me. Not now." |
| flee_silverer | "Scram, Fen, scram!" |
| call_guards | "Watch! Yeah, I said it! Watch!" |
| knocked_down | "Oi! Nobody knocks me down. Nobody." |
| on_fire | "I'm on fire! Warm enough now, ha, HELP!" |
| shocked | "Coin's sparking! My coin's biting!" |
| mourning | "They shared their blanket. Didn't have to." |

**Marta Quarry** (`marta_quarry`, V058, keeper of the Long Shelter). Barked rules and headcounts. Kind in what she does, harsh in what she says. Everything is a job.

| Intent | Line |
|---|---|
| greet | "Silverer. Boots off at the door, hands where I can see." |
| idle | "Hundred and eighty-two. Eighty-three. Roof holds." |
| see_tarnished | "Burning eyes at the door! Bar it!" |
| flee | "Everyone to the back wall! Count off!" |
| spell_near | "Light. Good. Keep it on the door." |
| thanks | "Useful. You're useful. That's the best I say." |
| dread | "Two hundred and ten tonight. There's no room." |
| farewell | "Go on. The roof's here when you need it." |
| witness_crime | "Headcount down one. Your doing." |
| flee_silverer | "Everyone inside! Doors! Rule one!" |
| call_guards | "Wall! Dagny! Eskil! Inside the shelter, now!" |
| knocked_down | "Down. Still counting. Up." |
| on_fire | "Fire in the shelter! Coal-bins away!" |
| shocked | "That went straight through my shoulders." |
| mourning | "I'll keep their cot made. It's the rule." |

**Dagny Thorn** (`dagny_thorn`, V050, guard at the gate that won't close). Sarcastic complaints and mock salutes. Insults the gate as if it were a person.

| Intent | Line |
|---|---|
| greet | "Silverer. Magnificent. Gate's open, obviously." |
| idle | "Frozen open. Typical. Magnificent gate." |
| see_tarnished | "Something's coming through. Of course it is!" |
| flee | "Abandoning post! Mark it down, nobody will!" |
| spell_near | "Oh, splendid. Bright and broken now." |
| thanks | "Huh. Somebody actually helped. Typical it's you." |
| dread | "Gate's wide open and the fog's coming in." |
| farewell | "Off you go. Gate'll be open. Always is." |
| witness_crime | "Magnificent. A hero who kills. Typical." |
| flee_silverer | "Gate's all yours. I'm off." |
| call_guards | "Wall! Wake up! Silverer's turned!" |
| knocked_down | "Floored. By a warm-sider. Typical." |
| on_fire | "On fire. In Frostside. Magnificent." |
| shocked | "Gate never shocked me. You did." |
| mourning | "They held this gate with me. Now it's just me." |

**Eskil Varn** (`eskil_varn`, V110, soldier of the Wall Company). A grumbling soldier who complains about warm-side troops, then turns halting and poetic about Marta.

| Intent | Line |
|---|---|
| greet | "Another warm-sider. Staying, or sightseeing?" |
| idle | "Half rations. Half of half. Wall still stands." |
| see_tarnished | "Burning eyes! Wall Company, here!" |
| flee | "Fall back to the shelter! Get to Marta!" |
| spell_near | "Warm-side tricks. Useful, for once." |
| thanks | "You stayed. Most don't. I'll remember." |
| dread | "Wall's thin tonight. So am I." |
| farewell | "Go on, then. Someone's got to stand here." |
| witness_crime | "Warm-siders. Always the same. Always killing." |
| flee_silverer | "Not dying for a warm-sider's madness!" |
| call_guards | "Wall Company! To the shelter! Protect Marta!" |
| knocked_down | "Down. No rations for this." |
| on_fire | "I wanted warm. Not this warm!" |
| shocked | "Teeth ringing. Half rations of sense." |
| mourning | "One less ration tonight. I'd give mine for them." |
| battle_1 | "Warm-siders behind, fog in front. Spears up!" |
| battle_2 | "Hold the wall for Marta! Hold it!" |
| patrol_1 | "Half rations, full wall. Walking it." |
| patrol_2 | "Marta's light's still on. Wall's fine, then." |
| enemy_down | "One down. One less mouth. Hate that I said it." |
