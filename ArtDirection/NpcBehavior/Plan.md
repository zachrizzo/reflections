# NPC behaviour plan

**Status:** the design is ready, and work in the game waits for your go-ahead (2026-11-22). It has been tested outside the game on thousands of generated towns.

The decisions were made in the shared working doc, [Reflections — NPC Behaviour Plan](https://claude.ai/artifact/7uQmF7zhGqpDiEU8nhB8Ya). This file is the copy for the sessions that build it. The test results are on the page [A Town of Forty](https://claude.ai/artifact/Dzjg3MQToEnZpubfXKj4uR).

The game is changing completely, so NPCs are being built from scratch. The old NPC system, the conversation code and every recorded voice line were removed on 2026-11-21 (commit 903d49ff, not pushed). Only the 137 custom designed voices carry over. They are defined in `ArtDirection/Audio/data/voice_roster.json`.

## 1. What we're building, and why

**The bar.** In your words, NPCs "as real and alive as GTA 6, but with the complexity of the new Fable."

- **Everyone is someone.** Every face in the world is a named person with a home, a job, family, feelings, memories and secrets. Death is permanent, and the people who knew them remember it.
- **Lives are procedural.** Each new game builds a new town with new lives, so no two playthroughs are alike.
- **Every event has a cause the player can find.** This is the guard against Fable's lesson: Playground dropped procedural NPCs because they felt random.

**Goals**

- Streets that feel lived in.
- People who react to what the player did, each in their own way.
- Stories already under way when the player arrives.
- A different town every game.

**Non-goals**

- An AI model making each NPC's decisions. It costs too much to run for thousands of people; rules and scores do the job.
- Generating speech while the game runs: you don't want to pay per player.
- Open, typed conversation, for now.

**Anti-goals: failure even if it technically works**

- NPCs that feel random.
- Towns that go off the rails, such as a killing every year, or everyone in debt.
- The same stories in every playthrough.
- Anything with a cost per player.

## 2. Decisions so far

| Date | Decision |
|---|---|
| 2026-11-21 | Design NPCs from scratch, because the game is changing completely |
| 2026-11-21 | Remove the old NPC system, the conversation system and the sword set |
| 2026-11-21 | Keep the 137 designed voices; remove every recorded line |
| 2026-11-21 | Aim for GTA 6's living streets with Fable's depth |
| 2026-11-21 | Everyone is someone: every face is a named, persistent person |
| 2026-11-21 | Lives are procedural: a new town and new lives every playthrough |
| 2026-11-21 | Option 3: goal-driven lives plus a generated history; build goal-driven lives first |
| 2026-11-21 | Keep option 3 whole, with no cut-down version |
| 2026-11-21 | Plan in the working doc; mirror the approved plan here |
| 2026-11-22 | Each town gets a director that leaves out about a third of the kinds of trouble (measured, section 4) |
| 2026-11-22 | The spike generator is the reference implementation, and the C++ version must rebuild its towns exactly (section 5) |
| 2026-11-22 | The director also features two kinds of trouble per town, so headlines vary more (section 4.1) |

## 3. The system at a glance

```
 content you curate            new game                                   in play
 ------------------            --------                                   -------
 names, traits, trades,   ->   TOWN GENERATOR                        ->   DAILY LIFE
 event rules and texts,        seed -> founders -> 25 years,              clock, schedules, needs and goals;
 places on the map,            month by month, through one rulebook       the same rulebook keeps running;
 line bank                     -> director -> check score, re-roll        the player is an actor in it
                               -> MINDS: who remembers what                  |
                               -> TOWN SAVE (the day the player arrives)     MINDS: memory, gossip, opinions
                                                                             BODIES: full MetaHuman near, crowd far
                                                                             TALK: lines picked from the line bank
```

- **A person is a record, and the body is a costume.** Everyone is simulated all the time as a few kilobytes of data. Only people near the player get a body.
- **One rulebook.** The same event rules make the 25-year history and keep running during play.

## 4. What the tests showed

Everything below comes from the throwaway spike in `ArtDirection/NpcBehavior/Spike/`, which runs outside the game. The names, trades and numbers are placeholders.

| Test | Result |
|---|---|
| Consistency (`check.py`) | **0 problems in 4,032 towns of 40**: 1,209,600 town-months and 666,735 events, each checked against 14 kinds of check (list below). The first run found 9 kinds of bug, and bigger runs found two rare crashes. All are fixed. |
| Same seed, same town (`stress.py`) | Identical event lists in separate processes. `out/golden.json` has reference digests for 10 towns and full event lists for 3. |
| Town sizes (`stress.py`) | **0 problems at 20, 40, 80 and 160 people.** Per-person rates stay steady: about 10 to 13 thefts and 28 to 37 marriages per 100 people over 25 years. Time grows with the square of the town size (section 5.6). |
| Sameness (`sameness.py`, 1,000 towns) | See section 4.1. |
| Memory and gossip (`minds.py`, 112 towns) | See section 4.2. |

**The 14 checks**

- On every event:
  - its causes come before it;
  - nobody in it is unborn, dead or gone;
  - no child is in an adult event;
  - everyone in it is named in its text;
  - no kin marry.
- On every month:
  - spouses agree, and both are alive;
  - no child lives without a grown-up;
  - every open shop has an owner in town;
  - each worker is on one shop's books;
  - open debts, secrets, beliefs, courtships and affairs all have people in town;
  - every parent was at least 16 at the birth;
  - no two living people go by the same name;
  - money stays between -400 and 5,000 silver;
  - nobody is over 100.

**Bugs the checks caught, all fixed**

- Someone courted in the month they died.
- Children were left alone when a step-parent remarried or left.
- A founding widow was 14 at her child's birth.
- A shop kept a dead owner when that owner had two shops.
- A shop was left without an owner when its owner shut a different shop.
- Debts, secrets and beliefs outlived the people who carried them.
- A killer blamed someone else for their own killing, which crashed the generator.
- A teenager who inherited a shop in the month they turned 16 was then apprenticed to themself, which also crashed it. It happened once in about 2,000 towns.
- Someone who had just run off with a lover still turned cold on a newly wed couple that month.
- A forbidding parent stayed in the story after they died. Now: "With Philippa gone, Corin and Emma marry at last."
- Money fell without limit. It now has a floor of -150: the destitute live on charity. At the top, a master with workers can save over 3,000 silver in 25 years, so the sanity bound is 5,000.
- A theft from someone who works in another person's shop didn't name the victim.
- Towns of 80 or more ran out of placeholder names. A reused name now comes with the surname ("Mara Cobb"). The real name list must be large enough for the town's size.

### 4.1 How alike are towns?

A **story shape** is three events in a row along a chain of causes, such as theft → blame → fight. Overlap is the share of story shapes two towns have in common, averaged over every pair of towns.

| Rules | Towns that pass the interest check | Story shapes per town | Overlap |
|---|---:|---:|---:|
| Five people (first test) | 7% | 6.8 | 13.7% |
| Forty people, families and births | 88% | 27.5 | 23.7% |
| More ways for each situation to end | 81% | 31.7 | 26.2% |
| A temperament for each town | 84% | 32.8 | 24.1% |
| A director for each town (1,000 towns) | 48% | 23.9 | 17.7% |
| The director also features two kinds of trouble; final rules (1,000 towns) | 50% | 24.6 | 17.2% |

**Lessons**

- Simulation on its own makes big towns alike.
- Adding more endings made it worse.
- A director that picks each town's themes is what works.
- Featuring two kinds of trouble per town spread the headlines out: theft fell from 57% of headlines to 50%.

**Headline stories.** A headline is the three most common kinds of event in a town's biggest story, leaving out everyday life.

- Across 1,000 towns there are 182 different headlines.
- The most common, a theft with a silent witness and someone wrongly blamed, leads 12.5% of towns. Next comes an affair that's found out and ends in a fight, at 8%.
- Two random new games open on the same headline 3.9% of the time.

### 4.3 Known weaknesses

- **Theft is in too many headlines: half of them.** It is the only way out of money trouble so far, and the chains it starts (a silent witness, blame, a fight) are the longest in the rulebook.
  - Fix: more ways out of money trouble, such as poaching, selling heirlooms, working for a shady patron, or leaving town for work.
  - These depend on the setting (question 2). The same test (`sameness.py`, `kind_in_headline`) will show whether they work.
- **Everyday shapes are in most towns.** A wedding followed by a rival who wishes the couple well is in about three towns in four. That's life, not a flaw, but such shapes shouldn't headline.
- **The interest check keeps about half of all towns.** A town takes about a second, so the re-rolls cost little, and in C++ even less.
- **Sameness counts kinds of event, not people or reasons.** It may make towns look more alike than they'd feel to a player.
- **The gossip and opinion rates are starting points.** They need tuning by feel in the game.
- **Life moves slowly at calendar pace.** That's question 12.

### 4.2 Memory and gossip

`minds.py` replays each town's history month by month, then plays 30 days after the player arrives.

**What people carry into the game** (112 towns)

| Measure | Result |
|---|---:|
| Memories each person keeps, at most | 40 (the cap) |
| Things that happened to them | 20% |
| Hearsay or town news | 80% |
| Older than 10 years | 15% |
| Adults who know part of the town's biggest story | 76% |
| Kept secrets that leaked by gossip | none, in 112 towns |
| Kinds of memory topic in use, as (kind of event, how they know it) | 146 |

**How fast word spreads after the player does something.** Each figure is the share of adults who know the player did it.

| What the player did | Day 1 | Day 3 | Day 7 | Day 30 |
|---|---:|---:|---:|---:|
| A killing, with a witness who tells | 23% | 59% | 89% | 97% |
| A theft, with a witness who tells | 15% | 38% | 73% | 100% |
| A theft, with a witness who keeps quiet | 3% | 3% | 6% | 33%, as slips |
| A kindness | 5% | 12% | 26% | 87% |
| A theft nobody saw | 0% | 0% | 0% | 0% |

- **A witness decides on the spot whether to tell, by the same rule the history uses.** Honest people tell, and so do gossips and anyone fond of the victim.
  - 67% of witnesses tell about a theft, and 99% about a killing.
- **The victim knows quickly when the witness talks.** Overall, 67% of theft victims know who did it by day 3.
- **A theft nobody saw.** The victim knows something is missing, but nobody ever learns it was the player.
- **Opinions after 30 days:**
  - a seen theft turns 75% of adults against the player;
  - a killing turns 97% against;
  - a kindness wins over 65%.

## 5. The town generator: what the game version must do

**The reference is `Spike/gen_lives.py`.** Port it rule by rule in the same order, then prove the port against `Spike/out/golden.json`.

### 5.1 Data

| Record | Fields |
|---|---|
| Person | id, the name the town calls them, given name, surname, sex, birth month, traits (2), who they're attracted to, parents, children, spouse, house, workplace, money, drinks, friends, sick or hurt until, when they died, left or arrived, the event where they left the story |
| Workplace | id, trade, place, owner, workers, open |
| Event | id, month, kind, actors (ordered), causes (earlier event ids), secret, text |
| Pair values | like (each way), love (each way), spark and affinity (per pair) |
| Loose threads | secrets (keepers, who knew at the time), beliefs (holder, suspect, wrong?), debts, feuds, blackmail, courtships (with any parent who forbade it), affairs, rivals, grudges (with their cause) |

### 5.2 A month, in order

1. economy
2. town events (accidents, flood, fire, failed harvest, fever, gifts)
3. every third month: feelings, business, people moving in and out
4. romance
5. family
6. money
7. crime
8. secrets
9. conflict
10. deaths

Every rule sees who is in town right now, not who was there at the start of the month.

### 5.3 The director and the temperament

Each town draws:

- **trait weights:** some traits are common and some rare;
- **five moods**, each a multiplier: love, crime, luck, temper and money;
- **story types switched off:** 35% of the 16 directed kinds;
- **two featured kinds of trouble:** drawn from affair, theft, rivalry, drink, blackmail, sabotage, fight and feud, among those still switched on. Each is three times as likely. Unless it is featured, theft runs at half its base rate.

### 5.4 The interest check and re-rolls

A town passes when all of these hold:

- at least 10 open tensions;
- at least 55% of adults involved with someone else;
- a cause chain at least 5 events long;
- at least 7 groups of event;
- no kind of event more than 16% of the total;
- at least 22 kinds of event used.

A town that fails re-rolls with seed `seed*1000+attempt`. If 60 tries all fail, the closest one is kept.

### 5.5 Exactness rules for the port

- **Random numbers.** Use SplitMix64 exactly as written in `Rng`, including `random()`, `below()`, `randint()`, `uniform()`, `choice()`, `choices()` and `sample()`. Don't use library RNGs or distributions.
- **Order.**
  - Lists and maps iterate in insertion order. In C++, use `TArray`, or arrays indexed by id; never iterate a `TMap` or `TSet` to make a decision.
  - Every loop over a set runs in ascending id order.
  - The order of an event's actors is part of its meaning.
- **Numbers.** Use doubles, with operations in the same order, and no fast-math in the module (MSVC's default `/fp:precise`).
- **Text.** Build event text from templates with parameters (names, places, amounts) kept in a string table. The setting can then change words without touching the rules, and the golden test compares the parameters as well as the finished text.

### 5.6 Speed

The spike runs in Python on one core, with the checks on and 14 towns running at once:

| People | Seconds per town, checks included |
|---:|---:|
| 20 | 0.36 |
| 40 | 1.28 |
| 80 | 5.48 |
| 160 | 23.2 |

- **Time grows with the square of the town size**, because the romance and feelings rules weigh every pair.
- **C++ should be about 50 to 100 times faster.** That puts 160 people at about 0.2 to 0.4 s.
- **Towns over about 150 people need social circles.** Pair rules then run only between people who meet: family, work, neighbours, friends, and a few chance meetings each quarter. That keeps the cost linear. The circle rule must be added to the Python reference first, so the golden test still applies.
- **Test gate:** a 40-person town in under 50 ms, and a 300-person town in under 1 s, in a shipping build.

## 6. Minds: memory, gossip and opinion

The reference is `Spike/minds.py`.

**A memory** holds:

- the event;
- how they know it: they did it, were there, saw it, were the victim, or heard it;
- who told them;
- how strong it is;
- when they learned it;
- whether they know who did it. A victim can know something was stolen without knowing by whom.

**How memories are kept**

- **Cap.** Each person keeps 40. When there are more, the one with the lowest importance × strength goes.
  - Importance is the kind's weight, ×3 if they were in it, ×2 if kin were, ×1.5 if a friend was.
- **Fading.**
  - Hearsay halves every 30 months.
  - What happened to them halves every 240 months.
  - The heaviest things about them or theirs never fade (weight 8 and above).

**Secrets**

- Only the people who knew at the time know a secret.
- It can travel only after a slip, an exposure, a confession or someone being caught.

**Gossip**

- **Where people meet:**
  - in history: six talks a month, 70% with family, friends, workmates or housemates, the rest by chance;
  - in play: home in the evening, work by day, and the market or tavern for about half the adults.
- **What gets told.** In each talk, the speaker passes on the juiciest thing they know that the listener doesn't. Juiciness is weight × strength × freshness.
- **How likely a talk passes something on:** 0.35, multiplied by:
  - 2.2 for gossips;
  - 0.35 for shy people;
  - urgency, which runs from 0.3 to 3 by juiciness.
- Hearsay arrives at 70% of the teller's strength.

**Witnesses**

- A witness tells if they are honest, a gossip or fond of the victim. A witness to a killing tells unless they are sly. The history uses the same rule.
- A witness to a killing goes straight to the family. A body is town news at once; who did it is not.
- A witness who keeps quiet may let it slip: 2% a day, or 8% for gossips.

**Opinion of the player.** Each kind of event the player is in has a value (theft −30, killing −90, kindness +20).

- That value is multiplied by the memory's strength.
- It is doubled for the victim.
- It is weighed more by honest people and less by forgiving ones.

Opinion will set prices, greetings, who helps, who calls the guards and who runs.

## 7. The town save

`Spike/out/town_save_example.json` is the format-1 example: the file the game loads on the day the player arrives. The save game will store the same structure plus everything that happens in play.

**What it holds**

- seed, month and temperament;
- **people:**
  - name, family, house, workplace and job;
  - traits, money, drink and goal;
  - friends, plus feelings toward the 8 people they like most and least, and anyone they love;
  - up to 40 memories;
- workplaces, events, open secrets, beliefs, debts, feuds, blackmail, courtships and affairs.

At 40 people it is about 340 KB of indented JSON. The game's binary form will be far smaller.

## 8. Daily life in play (proposal, not yet tested)

- **A clock and schedules.** A job sets the shape of a day. Inside it, people choose from their needs (food, sleep, money, company) and their goals (pay a debt, court someone, get even). The goal comes from the generator: "Find 40 silver before Oswin takes everything."
- **Off screen, people are records.** They move between places on their schedules and meet whoever is there. Gossip runs on those meetings (section 6). On screen they get bodies.
- **The same event rules keep running**, with the player as an actor. Theft, killing and kindness by the player go through the same witness, blame, feud and opinion rules as the town's own events.
- **Story pace (a choice for you, question 12).** The history rules make about 6 notable events a year in a town of 40. At calendar pace, a player would see almost none during a playthrough.
  - Proposal: relationship, money, crime and conflict rules run at one rulebook month per game day, steered toward people the player knows.
  - Births, ageing and natural deaths stay at calendar pace.

## 9. Bodies and performance (facts already measured)

All of these are editor measurements on a Ryzen 7 9700X with an RTX 5080.

- **A full MetaHuman costs about 1.2 ms of game thread**, or 0.5 ms with animation LOD. The jam capped a street at 12.
- **Mass/MetaHuman Crowd costs about 1.0 ms of game thread and 0.4 ms of GPU for 40 walkers.** It wasn't ready:
  - heads were white and bald, with no hair, and clothes floated;
  - its instances exist only on the GPU;
  - a walker swapped for a full NPC became a different person.
- **Partial-ragdoll hit reactions broke poses.** One crash condition: "BoneIndex out of range of SpaceBases".
- **Spawning needs care:**
  - preload looks first: a spawn once stalled for 228 ms;
  - snap to the floor;
  - turn off walking off ledges.

**Proposal:**

- a full MetaHuman within about 30 m;
- a cheap crowd body playing the same person out to about 100 m;
- no body beyond that, or indoors.

The real distances come from a benchmark in phase 4.

## 10. Talk: the line bank

- **How it works.** Lines are written and voiced once, in all 137 voices. Rules pick the line that fits the person, their memories and the moment, and the player picks what to say from a set of choices.
- **Naming people.** Lines name people by role ("the miller", "my brother"); full names go in subtitles.
- **Size.** The current rules use 146 memory topics (the kind of event × how they know it). With a few variants and two moods per topic, plus greetings, trade and reactions, that's about 1,000 to 1,500 lines per voice.
- **Cost, paid once.** About $92 to $140 for 1,000 lines a voice on Gemini Flash TTS at 2027 prices, with retakes. The cost table is in the working doc.

## 11. Build order

Each phase ends with a test that must pass before the next begins. Source edits and compiles follow the project's build rules: only while the editor is up and the train isn't running.

| Phase | What | Done when |
|---|---|---|
| 0 | Finish the removal: delete `DT_NpcVoiceRoster`, remove the "Conversation Test NPC" from `L_TestTown`, run a full editor build | The editor builds clean with no NPC leftovers |
| 1 | **Town generator in C++.** A new runtime module, `TownSim`, in plain C++ with no UObjects in the core and a thin subsystem on top. Port `Rng`, then the rules in month order, then the check and the score. | The RNG and seeds 1–10 match `golden.json` exactly; the check finds 0 problems in 1,000 towns; a 40-person town takes under 50 ms |
| 2 | **Minds in C++**, plus loading and saving the town save | Gossip curves within 10 points of section 4.2; a save round-trips with no change |
| 3 | **The town in the world**, in Test Town first: house, workplace and haunt markers; the clock; schedules; off-screen movement | 40 people keep their schedules for a game week, and every one is where their record says |
| 4 | **Bodies:** a costume when near, crowd bodies at middle distance, and a benchmark | The person keeps the same face and clothes across every body swap; busy-street numbers measured (question 7) |
| 5 | **Play-time rules:** the player as an actor, witnesses, opinions driving prices, greetings and guards, and story pace | The four section 4.2 scenarios behave the same in the game as in the spike |
| 6 | **Talk:** the line bank pipeline and choice-based conversation | Needs questions 2 and 3 answered |
| 7 | **Tools:** a "why?" inspector on any NPC, the town register as a readable book, the seed shown for bug reports | Any event in the game can be traced to its causes |

**First implementation step, on your go-ahead.**

1. Phase 0's cleanup, at the next editor restart.
2. Phase 1's first piece: create the `TownSim` module and port `Rng`, with its golden test.

Neither needs the setting, the map or any art.

## 12. Open questions

| # | Question | Status | What it blocks |
|---|---|---|---|
| 1 | What is the new game? What does the player do, and what are the people there for? | **Yours to answer** | What the rules are about, from phase 5 on |
| 2 | Where and when is it set? | **Yours to answer** | Names, trades, event texts, looks, line bank |
| 3 | How does the player talk to people? | Proposal: picking lines from a set, voiced from the line bank | Phase 6 |
| 4 | Do NPCs fight, and on whose side? | **Yours to answer** | Combat reactions, guards |
| 5 | Who lives in Test Town first, and how busy should it feel? | Proposal: start with 40 people, the size the spike tested most | Phase 3 |
| 6 | Is there a time of day? | Proposal: yes, a day clock; schedules need one | Phase 3 |
| 7 | How many people on screen in the busiest street? | From the phase 4 benchmark | Phase 4 |
| 8 | What hardware and frame rate are we targeting? | **Yours to answer** | Phase 4 budgets |
| 9 | Do NPCs remember what the player did? | Settled: yes, everyone does (section 6) | — |
| 10 | Where do the Dwarf, Elf and Orc fit? | **Yours to answer** | Content |
| 11 | Can Kimodo animation be used commercially, and is it good enough on a MetaHuman? | Separate animation track | Animation, not this plan |
| 12 | How fast do lives move during play? | Proposal: drama at one rulebook month per game day, ageing at calendar pace (section 8) | Phase 5 |

## 13. Files

All of these are in `ArtDirection/NpcBehavior/Spike/`. They are throwaway tools, not game code.

| File | What it is |
|---|---|
| `gen_lives.py` | The generator and the reference rulebook. `python gen_lives.py` writes the page and `out/towns40.json` |
| `minds.py` | Memory, gossip, opinions and the town save. `python minds.py --towns 112` writes `out/minds.json` and `out/town_save_example.json` |
| `check.py` | The consistency checks. `python check.py --towns 4032 --save out/check_1000.json` |
| `stress.py` | Determinism, the golden file and town sizes. Writes `out/stress.json` and `out/golden.json` |
| `sameness.py` | How alike towns are. `python sameness.py --towns 1000 --save out/sameness_final.json` |
| `page_template.html` | The results page |
| `gen_lives_v1.py`, `page_template_v1.html` | Version 1, the five-person test |

On Windows, run them with `PYTHONIOENCODING=utf-8`.
