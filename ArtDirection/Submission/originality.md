# Originality: what echoes *Shades of Magic*, and what to call things instead

Rule 8 bans material that infringes anyone's IP, and rule 15(g) lets Epic disqualify an entry it thinks may infringe copyright ([rules.md](rules.md)). The team's whiteboard says it too: "Others' IP is banned: rename the worlds, coins and characters."

Ideas and tropes such as parallel worlds aren't protected. Distinctive names, characters and specific combinations are, and they're what a judge would recognize. Schwab's books have Grey, Red, White and Black London, Antari travellers who cross between them using a token from the destination, Kell's coat with many sides, and Osaron, who possesses people. Our game lines up with that on five points at once.

## What a player would recognize

| Element | Where it shows today | Why it echoes the novels | Risk |
| --- | --- | --- | --- |
| The worlds **Gray London, Red London, White London** | World-jump HUD panel, the arrival banner ("RED LONDON", "Crossing into White London…"), prompts, refusal text, concept-art titles | Same three names and colour scheme as the books (Grey, Red, White London). The world identities match too: plain non-magic city, vivid magic-rich city, bleached and brutal city. | **High** |
| Working title **"Three Londons"** | Concept art, docs, possibly the window title or menu | Says the book's premise outright | **High** |
| Crossing with **a coin of the destination London** | HUD ("Coins: Gray 1 · Red 1 · White 0"), coin pickups, refusal reasons, README wording "the coin is a token of the place you're going" | In the books a traveller needs a token from the world they're going to. That's the most recognizable mechanic in the series. | **High** |
| The hero's **long, high-collared coat that changes per world** | Runtime coat tint per London; concept art `Three-Londons-Wardrobe/Hero/*` | Kell's coat with many sides is the series' signature costume. `ArtDirection/Three-Londons-Wardrobe/prompts.md:108` asked the image generator for a coat "inspired by Kell's high-collared, many-sided coat from A Darker Shade of Magic". | **High** in the art; medium in play |
| A **faceless shadow villain who possesses people**, infecting the city | Villain/finale (in progress), infection meter (game-flow-ui), concept `09-shadow-cloth-boss` | Close to Osaron in the third book | Medium |
| **White London** look: runes and tattoos, chalk, starving survivors | Wardrobe folders "White London – Runes" and "Rags and Tattoos" | The books' White London is drained of magic and its people are marked with binding runes | Medium. Fine once renamed. |
| Book/tower pages: "THE BOOK IS WHOLE. Three pages, one spell. Now stop him." | World-jump HUD | Generic | Low. Rename to match the set. |

The full list of strings, with file, line and owner, is in [rename-table.md](rename-table.md), written once a name set is chosen.

### Changes worth making in any case

1. **Remove "London" from everything a player sees**: HUD, banners, menus, the window title, the itch page and the video. Internal asset paths such as `/Game/Characters/RedLondon/` never reach the player and can stay.
2. **Stop calling the worlds by colour.** The grades can stay gray, red and white. The names shouldn't.
3. **Optional, one config change:** set the world-jump **Coin Rule** to `current` or `any` instead of `destination` (`DA_WorldJumpConfig`, owner world-jump). That breaks the "token from where you're going" link with the books.
4. **Keep the concept-art prompts private.** Don't post `Three-Londons*` images or prompts on the itch page or in the dev log. The hero coat art in particular came from a prompt that names the book.

## Three original name sets

All three keep the art (drab gray, vivid red, bleached white) and the mechanics. Only names and framing change. Each set also gives the game a **Director's Cut** angle, which it currently lacks and rule 7(g) requires.

### A. "Three Takes": the city is a film shot three times (recommended)

| Thing | New name |
| --- | --- |
| Game title | **Three Takes** |
| Gray world | **The Release**: the safe, drab version that shipped |
| Red world | **The Director's Cut**: the vivid version that was meant to be, full of magic |
| White world | **The Cutting Room**: bleached and starving, where everything that was cut ends up |
| Coins | **Frames**: a frame of film from the take you're cutting to |
| World jump | **Cut** ("Hold X: cut up", "Cutting to The Director's Cut…") |
| Hero | **Slate**, a runner who can step between takes |
| The coat | **The continuity coat**: it never stays the same colour between takes |
| Villain | **The Editor**, who splices himself into people. The infection meter becomes **Spliced**. |
| Tower pages / finale | **Script pages** ("THE SCRIPT IS WHOLE. Three pages, one scene. Now cut him."). The finale is the **Final Cut**. |

*Pitch:* One city, shot three times. Cut between the takes, collect the frames, and stop the Editor from splicing himself into everyone before the final cut.
*Theme:* Explicit. The player's job is to restore the director's cut.

### B. "Reflections": three reflections of one city

| Thing | New name |
| --- | --- |
| Game title | **Reflections** (already the project's name) |
| City | **Lanthorne** |
| Gray world | **Pewterside**: the dull, everyday reflection |
| Red world | **Giltside**: warm, rich and bright with magic |
| White world | **Frostside**: cracked, cold and starving |
| Coins | **Shards**: a mirror shard of the side you're stepping into |
| World jump | **Step through** |
| Hero | **Wren Hale, the Silverer**, who can walk through mirrors |
| The coat | **The silvered coat**: its sheen takes on each side's light |
| Villain | **The Tarnish**, which spreads through reflections and takes over faces. The infection meter becomes **Tarnish**. |
| Tower pages / finale | **Mirror pages** ("THE MIRROR IS WHOLE…") |

*Pitch:* Three reflections of one city, and a Tarnish creeping through all of them. Step through the glass and burn it out before it takes every face.
*Theme:* Weak. You'd need a line such as "Lanthorne was cut into three reflections, and only one is the version its maker meant."

### C. "Cut Content": three builds of the same game

| Thing | New name |
| --- | --- |
| Game title | **Cut Content** |
| Gray world | **Shipped**: the safe, focus-tested build |
| Red world | **Vision**: the build the director actually wanted |
| White world | **Scrapped**: the cut build, half-textured and bleached white |
| Coins | **Patches**: a patch from the build you're switching to |
| World jump | **Branch** ("Hold X: branch up") |
| Hero | **The Playtester** |
| The coat | **The placeholder coat**: its colour was never finalized, so it takes each build's palette |
| Villain | **Lorem**, the boss they cut, possessing NPCs to get back into the game. The infection meter becomes **Corruption**. |
| Tower pages / finale | **Design-doc pages** ("THE DESIGN DOC IS WHOLE…") |

*Pitch:* Three builds of one game: the one that shipped, the one the director wanted, and the one that got cut. The boss they cut is possessing everyone. Patch him out.
*Theme:* Direct. It's the jam's own "the feature that didn't quite make it". The meta humour clashes with the grounded, photoreal art, though.

### Title check

A standard web search (2026-11-14) found no game called "Three Takes", "Cut Content" or "Silvered". The nearest match is *Triple Take* (2022, platformer). "Reflections" is a generic word that several small games use.

## Decision

**Waiting on the team's choice.** Once a set is chosen, [rename-table.md](rename-table.md) lists every player-visible string with its file and owner, and each owner gets their rows.
