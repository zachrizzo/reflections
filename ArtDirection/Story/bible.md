# Reflections: story bible

Owner: the story session. This is the source the quest, cutscene, NPC-lives, voice and dialogue sessions build from. Names, pronunciation and the never-say list come from [canon.md](../Submission/canon.md). If this file and canon.md disagree, canon.md wins; tell the story session.

Companion files in this folder:
- [main-quest.md](main-quest.md): beats, triggers, objectives and lines.
- [cutscenes.md](cutscenes.md): six shot-by-shot scripts, each anchored to a named marker.
- [side-quests.md](side-quests.md): twelve side quests.
- [people.json](people.json): the people book. It has 48 named people, their cliques, the generator rules for the rest of the crowd, and every person's barks.
- [conversations.md](conversations.md): street-conversation seeds per clique, and the barks in readable form.

## The premise in one breath

Lanthorne was once one city with one great mirror, the **Lanthorne Glass**, hung at the top of the Gilt Tower to throw lantern light into every street. The Glass saw every face in the city for three hundred years and kept a little of each one, and the dark half of all those faces grew in its silvering. That dark is **the Tarnish**. When it woke and tried to step out wearing the city's faces, the Glass's maker cut the mirror into three leaves and the city split with it. Now three reflections of Lanthorne share every street, and the Tarnish is caught in the cracks between them.

It is getting out. **Wren Hale**, one of the last Silverers, has to bring the three leaves back together, the **mirror pages**, so that the mirror is whole and its light can burn the Tarnish out.

Title line (already in game): *"Lanthorne was cut into three reflections, and only one is the version its maker meant. The Tarnish wants the final cut."*

## The Glass and its maker

- **The Glazier** was the maker. Their name is lost; the city remembers only the title. They were the first Silverer.
- **The Lanthorne Glass** was a hinged mirror of three leaves, like a book that stands open. That is why its pieces are called **pages**, and why a whole mirror is "the book complete" in the code.
- **The cut.** The Glazier broke the hinges. Each leaf fell into its own reflection of the city, and each reflection hid its leaf high up, where the light reaches: the Old Weigh-House roof in Pewterside, the Gilt Tower in Giltside, and the Frost Tower in Frostside. The Frost Tower is the Gilt Tower's own reflection, sealed shut by cracks.
- **What the Glazier wrote.** Each page carries one line, scratched into the silvering. These are the lines the pickups and cutscenes use, in pickup order:
  1. Pewterside: *"I cut it in three, so no one dark could hold it all."*
  2. Giltside: *"Let each side believe it is the true one. Pride makes a good lock."*
  3. Frostside: *"The city I meant is the one they make together. Finish it."*
- **The answer to the title line.** None of the three reflections is the version the maker meant. The meant city is all three, standing together. The Tarnish wants "the final cut": one reflection with one face on every person, its own. The ending says this through Ilse, and nobody explains it twice.

## The Silverers

- **What a Silverer is:** one of the few people who can walk through the glass. The Silverers were a guild of mirror-menders who kept the city's glass clean. Silvering a mirror and stepping through one are the same trade to them.
- **How it works in game:** a Silverer steps through using a **mirror shard** from the side they're going to. Each step costs most of their strength, which is the game's magic meter. Shards are found in the streets, and the people of each side drop them.
- **Their mark:** an incomplete ring with three parallel cuts, worn as a brass clasp at the chest (the hero's coat has it). The common name for it is "the cut ring".
- **Now:** there are two Silverers left in Giltside. Ilse Varrow is too old for the glass to take her. Wren is the other.
- **Spells and the cure:** a spell's light can burn the Tarnish out of a person if it is cast in time. This is the game's cure-on-hit rule. Ordinary people know it only as a rumour ("light hurts it"). Wren learns it as fact in the first act.
- **Steel and light.** The Watch, the Lamp Companies and the Wall Company fight with swords, spears and wands, so the tarnished can be stopped in melee. But steel only stops the body; only light gives the person back. Every melee kill of a tarnished is a neighbour who stays dead. That is the moral weight of the fights: Captain Brask's soldiers cut them down, and Wren burns them clean. Side quests that say "burn the Tarnish out of X" fail or turn grim if X is killed instead.
- **The sides never mix.** Each side dresses only as itself: rags and furs only in Frostside, red and oxblood only in Giltside. Fitted clothes only, rags included. A drifter still wears their own side's clothes, which is how everyone knows they're a drifter.
- **Everything has consequences.** People see what the Silverer does. A spell through a window, a bystander knocked flat or burned, a neighbour killed: witnesses remember, call the Watch, flee, and mourn (people.json barks `witness_crime`, `flee_silverer`, `call_guards`, `mourning`). That is the Silverer's **heat**. A wanted Silverer is refused by the Third Company (SQ11) and can clear the page with Sergeant Kettering (SQ10, `Silverer_RecordClean`). Choosing steel over light has a cost of its own (SQ11 → SQ12).

## The Tarnish

- Always "it". It has no body of its own until the end; it wears people. A **host** has burning eyes, a black aura and a violet glow. It burns its hosts out in about half a minute and leaps, as black smoke, into someone new.
- **The tarnished** are people it has taken. Their eyes burn, black smoke clings to them, and they speak slowly and flatly as "we". They hunt the untaken. They tackle a person, hold them down and breathe black smoke into them, and that person gets up tarnished. They are still the same people inside, which is why curing them matters.
- **Its voice:** close, low, unhurried and amused. It never shouts and never threatens gore. It talks about faces, fit, polish and wearing people. It knows what people hide, because it lives in reflections and has seen them alone in their mirrors. That is its cruelty: it says the secret out loud.
- **What it wants:** to be the only face in the mirror. If it takes enough of the city (the Tarnish meter reaching its cap), Lanthorne is lost: "THE TARNISH HAS TAKEN LANTHORNE."
- **Where it ends:** when the mirror is whole, its true form rises at the top of the Frost Tower, the cracked reflection of the Gilt Tower. Only the Final Spell can hurt it there.

## Wren Hale, the Silverer

- **Who:** a young man in his mid-twenties, the hero model (warm brown skin, short black curls). Say "REN HAIL". He lives in Giltside, in a rented room above the Lamplight inn.
- **Voice:** warm, steady, a little wry. He jokes when he's frightened and goes quiet when he's angry. His lines are short.
- **History:** Wren was Ilse Varrow's apprentice from the age of twelve. His mother, **Elin Hale**, was a Silverer who went into the glass nine years ago and didn't come back. Ilse told him the Tarnish took her. That is true, but it is not the whole of it (see Ilse's secret in people.json).
- **His flaw:** he spends his life polishing other people's reflections and never looks at his own. He hasn't looked into a mirror on purpose since his mother went. The Tarnish's finale line, "Now look into it", is aimed straight at that.
- **His coat:** the silvered coat, cut by Barnaby Thrale. Its sheen takes each side's light: charcoal with a madder-red lining in Pewterside, oxblood and antique gold in Giltside, chalk ivory and storm blue in Frostside. The cut ring is at his chest.
- **What he wants:** to finish what his mother started, and to stop being the last of something.

## The three sides, by mood

Never describe them by how much magic they have or by who rules them. Describe how they look, feel and sound, and what the people are like.

### Giltside (GILT-side), where the game starts: warm, lantern-lit, at war
- **Look:** amber lantern light on wet brass, gold leaf on shop signs, warm stone, banners and bells. It never gets fully dark, because Lantern Law says every lamp burns all night now.
- **Mood:** festive on the surface, brittle underneath. Giltside is at war with the Tarnish. The Lamp Companies march to the rift posts, a curfew bell rings at dusk, recruiting tables stand in the squares, and the laughter is a little too loud.
- **People:** proud, generous, showy, superstitious about light. They love their side and are starting to fear everyone who isn't from it. People who come through the rifts from the other sides ("drifters") camp under the Lantern Gate, and the Watch doesn't know what to do with them.
- **Sound:** bells, fiddles, boots in step, sizzling wicks.

### Pewterside (PYOO-ter-side): dull, grey, everyday
- **Look:** grey stone, grey rain, grey tin roofs, steam from laundries, trams, tea stalls and a slow river. Everything is the colour of a spoon.
- **Mood:** steady, tired, stubborn. Pewterside gets on with it. They don't make a fuss, and that is both their strength and their flaw: they look away from things until those things are at the door.
- **People:** dry, practical, unimpressed, kind in a way they'd never call kind. Neighbours know each other's business. Old people run the streets.
- **Sound:** tram bells, rain on tin, kettles, a newspaper seller who never stops.

### Frostside (FROST-side): cold, cracked, bleached
- **Look:** white stone gone chalky, frost on everything, cracks running through walls, streets and faces of buildings like breaks in glass. The light is thin and blue.
- **Mood:** hungry, hard, watchful. Frostside is where the Tarnish first pushed against the glass, and it shows. People live close together for warmth, behind a wall of packed ice and timber they keep patching.
- **People:** blunt, sardonic, fiercely loyal to their own, suspicious of anyone warm. Gallows humour. They share everything and forgive nothing.
- **Sound:** wind, cracking ice, ladles on iron pots, an old woman singing.

## Factions and groups (light touch)

| Group | Side | What they are |
|---|---|---|
| The Lantern Watch | Giltside | The city watch: sergeants, gate and bridge guards. They enforce Lantern Law and the curfew. |
| The Lamp Companies | Giltside | The marching squads sent to hold the rift posts. Medieval kit: oxblood tabards with the lantern sigil, mail and plate, shields, swords and spears. Captain Sela Brask leads the Third Company; its named soldiers are Sergeant Aldric Mayne, Bram Tolley (shield-bearer), Cosmo Fennick (recruit), Damaris Hobb (lamp-bearer), Emeric Dunstan (hornblower) and Ros Thrale. They are the Silverer's allies, not friends: they fight beside Wren and keep a book on him. |
| The Silverers | (Giltside) | The mirror-menders' guild. Two are left. |
| The Coal Lane watch | Pewterside | One young constable and a lot of opinionated pensioners. |
| The Wall Company | Frostside | The defenders of the ice wall. Underfed and underthanked. |
| The Long Shelter | Frostside | A communal shelter, run by Marta Quarry, where half of Frostside sleeps. |
| Drifters | any | People leaked between sides by the rifts. |

## The arc, mapped onto what already exists

The whiteboard's six beats, grouped into four acts. Every trigger below is an event the game already fires; [main-quest.md](main-quest.md) has the detail.

| Act | Spine beats | Where | What happens | Game events used |
|---|---|---|---|---|
| **I. Lantern Law** | 1 Start, 2 Learn | Giltside | Intro cutscene. Wren meets Ilse and learns to aim and cast. The Tarnish takes its first face. Wren watches his best friend, Jory, get tackled and turned (cutscene 2), then cures someone for the first time and learns that light burns it out. | Play begins; game-flow tips (Aim, Cast); villain first host; first conversion; NPC infection → None |
| **II. Through the Glass** | 3 Explore | Giltside → Pewterside | Wren finds a Pewterside shard and steps down. He climbs to the Old Weigh-House roof and takes the first page (cutscene 3). Pewterside's people meet him: some kind, some sour. | Shard picked up; `OnWorldChanged` → Pewterside; `OnPagesChanged` 1 |
| **III. Hold the Line** | 4 Hold the line | Pewterside → Giltside | The Tarnish feels the page move and pushes harder. Wren steps back up, holds the Lantern Gate with the Watch, and earns the Gilt Tower key from Sergeant Kettering. He opens the tower (cutscene 4) and takes the second page. Most side quests live here. | Infection meter; `OnWorldChanged` → Giltside; `OnKeyAdded` GiltTowerKey; sealed door opened; `OnPagesChanged` 2 |
| **IV. The Cracked Crown** | 5 Towers, 6 Final Spell | Giltside → Frostside | Inside the tower Wren steps up into its cracked reflection, the Frost Tower, and takes the last page. The mirror is whole (cutscene 5). He climbs to the top, where the Tarnish rises. He burns it out with the Final Spell, and the ending (cutscene 6) plays. | `OnWorldChanged` → Frostside; `OnBookComplete`; villain manifest; Final Spell; villain defeat; `ShowVictory` |

**Losing** is the Tarnish meter reaching its cap. Story framing: when it holds that many faces, it has enough to wear the city.

## The "last Queen" idea (from the whiteboard)

We kept the idea but not a monarch, because describing a side by who rules it is on canon's never-say list. **Hester Quaile, "the Queen of Coal Lane"**, is a Pewterside pensioner whom the whole street calls its queen. She is the anchor of the side quest [The Queen of Coal Lane](side-quests.md#sq4-the-queen-of-coal-lane).
- **Default (no new code):** if Hester is tarnished, the quest fails until Wren cures her, and Coal Lane's barks turn despairing.
- **Optional hard rule (needs a game-flow hook):** if Hester dies, or stays tarnished for 60 seconds, the game is lost with the line "Coal Lane has gone dark. The Tarnish has Pewterside." Only build this if the team wants a second lose condition; it is not in the jam scope.

## Tone rules for every writer

1. **Short lines.** Barks are under about 3 seconds. Cutscene lines are under about 5 seconds.
2. **Every person sounds like themselves.** Use the speech style, tics and favourite words in people.json, and never the words on their never-say list.
3. **No two people share a line.** That holds even for one-word barks. If two people would say "Run!", one says "Run!" and the other says "Feet, now!"
4. **Dark is allowed; gore isn't.** Death, grief, fear and cruelty are in scope (M rating). Graphic description, sexual content, slurs and real-world hate are not. The tarnished are frightening because they are still the people you knew.
5. **Mood, not magic.** Describe the sides by look and feel.
6. **The Tarnish is always "it"**, and it speaks quietly.
7. **Never say:** London, Grey/Red/White/Black London, Kell, Lila, Holland, Rhy, Osaron, Antari, "As Travars", blood magic, "traveller" for Wren, any real brand or place. In player-facing text the sides are Pewterside, Giltside and Frostside; Gray, Red and White are code names only.

## Pronunciation (for voice scripts)

Lanthorne = "Lant-horn". Pewterside = "Pyoo-ter-side". Silverer = "Sil-ver-er". Wren Hale = "Ren Hail". Ilse Varrow = "ILL-suh VARR-oh". Brask = "BRASK". Quaile = "KWAIL". Skarre = "SKAR". Others are said as spelled.
