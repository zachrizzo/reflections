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
