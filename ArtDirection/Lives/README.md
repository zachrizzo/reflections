# NPC lives

Every townsperson in Reflections is a person: a name, a job, a personality, family and friends, a day of their own,
and a memory of what the player did to them and to the people they love.

Code: `Source/reflections/Lives/*` (lives session). Test: `Tools/Lives/verify_lives.py`. Data: the story bible's
`ArtDirection/Story/people.json` (42 named people, 13 cliques, schedule templates, generator pools), cooked as
`/Game/Lives/DA_PeopleBook` (re-import with `Tools/Lives/import_people_book.py`). `ArtDirection/Lives/people_stub.json`
is only a fallback for editors without the story file.

## What the player sees

- People walk between home, work, their haunts and their friends on a compressed clock (24 real minutes per in-game
  day by default, set in the people book). At night they go home and inside.
- Friends and family who are out at the same time look for each other, walk over, face each other and talk (a baked
  conversation from the crowd's chat director when it has one for the pair, else turns of each person's own voice
  barks). Chatty strangers sometimes talk too. Rivals don't.
- Someone who sees a friend or relative hurt, killed or taken by the Tarnish reacts by personality: brave ones get
  angry, others grieve or are afraid. They get away from the spot first, then go home. For hours afterwards they avoid
  that area and its haunts. Strangers who saw it are frightened for a while. Close family and friends who didn't see it
  hear the news.
- Each person remembers the player: healed me, hurt me, cast spells near me, saved / hurt / killed someone I love, did
  my quest, talked to me. That sets their opinion (-1..1, scaled by their warmth and temper), their greeting bark, their
  live-reply persona and whether they offer a quest.
- People stop walking when the player comes up to them (3.5 m), so they can be talked to.

## Debug view (playtest)

The overlay is **off by default** on every Play. **F7** cycles it: off, then 1 (over each head: name, job, what they are doing and where, the next schedule
step, mood, opinion of the player, and the last thing that happened to them), then 2 (also traits, LOD, a line to their
goal, and every place with its radius; auto-placed places are blue). The clock and head count are top left.

Console: `Lives.Debug 0|1|2` (stays set until changed; F7 also switches it off), `Lives.SetHour <h>`, `Lives.TimeScale <x>`, `Lives.Dump` (one line per person),
`Lives.TestWitness [name]` (someone the witness knows, near them, is taken by the Tarnish), `Lives.Enable 0|1`.
Tuning: `Lives.FullRadius`, `Lives.SpawnNamed`, `Lives.MaxSpawned`, `Lives.SpawnRadius`, `Lives.DespawnRadius`,
`Lives.AutoCastNamed`, `Lives.HidePlacedInside`, `Lives.WitnessRadius`, `Lives.UseStoryMarkers`, `Lives.ChatDirector`.

## How it works

`UReflectionsLivesSubsystem` (world, tickable) owns everything. `UReflectionsLivesMemory` (game instance) keeps the
clock and what everyone remembers, and writes it to its own slot `Reflections_Lives` on every game-flow checkpoint.
On a restart from a checkpoint, people go back to what they knew at that checkpoint. A new game forgets everything.

### Identity

- The people book is parsed from `ArtDirection/Story/people.json` in editor builds, then from `/Game/Lives/DA_PeopleBook`
  (a `UReflectionsPeopleBookAsset` holding the JSON text, so it cooks), then the stub, then built-in generator lists.
- An NPC actor is cast, in this order: by its tag `Lives_Person_<id>` (or `Person_<id>`); then, for level-placed
  actors, as the first free named person of the same sex (a matching `look` first); otherwise as a generated
  townsperson. A generated person's id comes from a hash of the actor's level and name (spawned actors: their spawn
  spot), so the same actor is the same person every run. Their name is saved, and no two living people share a name.
- Named people with no actor are spawned (`SpawnNpc`, a team look of the right sex) when their schedule puts them
  within 35 m of the player, and removed when they go inside or are far behind. At most 6 at once.
- Soldiers, enemies and the tarnished get no life. Actors tagged `Lives_None` are skipped.
- Lives adds the tags `NPC_NoStroll` (so the crowd's stroll lets the body go), `Lives_Steered` and `Lives_Person_<id>`.

### Schedules and places

- Steps are `{at, do, where}`. `where` is `home`, `work`, `haunt` (the person's haunts, rotated by day), `social` (a
  haunt where a friend or relative is out right now), or a marker name. Before the first step of the day, the last
  step still runs.
- Places are the quest system's story markers (`AReflectionsStoryMarker`, name in `MarkerName` or a tag, `Radius`).
  When a map has none of a name, the story marker subsystem's own fallback places one. Without that subsystem, Lives
  places it: a placed townsperson's home is a few steps from where the level put them, and work places and haunts go
  on a ring around the townspeople. Optional `Door_<place>` markers give the door people go in and out at.
- Walking: nav-mesh paths when there is a nav mesh, straight lines otherwise, walk gait, speed by age. At the place
  they mill around inside its radius (patrols wider). Stuck: two re-paths, then they call it arrived.
- Indoors (home, sleep, grieving): people Lives spawned are removed. Placed ones wait at their door, or are hidden and
  held with `Lives.HidePlacedInside 1`.

### Bodies

Lives steers a calm NPC through `SetExternallySteered(true)`. Any other reaction (alert, flee, investigate, fight,
down), a scripted hold, or infection hands the body straight back to the NPC system, the same rule as the crowd's
stroll. When the NPC is calm again, Lives picks up from where it stands.

### Life LOD

- Full: actors within 60 m of the player. They walk, meet, chat, greet and react, and think twice a second.
- Far: actors beyond 60 m think every 1.5 s. When nobody sees them, they skip the walk and are put where their
  schedule says.
- Virtual: named people without an actor, and Mass pedestrians claimed by the crowd. Only their schedule advances
  (every 3 s). `GetPersonGoal` gives where they should be.

## For other systems

Include `Lives/ReflectionsLivesSubsystem.h`. `UReflectionsLivesSubsystem::Get(this)`:

| Who | Call |
|---|---|
| Dialogue persona | `GetPersonaText(Actor)` (ready text) or `GetPersonaFacts(Actor)` (struct): name, job, age, side, traits, summary, speech style, quirk, likes/dislikes/fear, family and friends by name, activity, mood (and who it is about), recent events, what they remember of the player. **Never the secret or quest internals.** `GetGreetingHint(Actor)` |
| Dialogue / quests | `RememberPlayer(Actor, EReflectionsPlayerDeed::Talked)`, `CompleteQuestFor(PersonId)`, `IsQuestAvailable(PersonId)` |
| Anyone | `GetPersonId(Actor)`, `FindActorForPerson(Id)`, `GetPersonName(Id)`, `GetMood(Id)`, `GetPlayerMemory(Id)`, `OnLifeEvent` |
| Map / lighting | `GetTimeOfDayHours()`, `GetDayFraction()`, `GetDay()`, `OnHourChanged(Hour)`. Lives never touches lighting. |
| Crowd (Mass) | `ClaimPersonForCrowdAgent(AgentKey)`, `GetPersonGoal(PersonId, OutGoal)`. Tag a promoted actor `Lives_Person_<Id>` and it keeps its person. |
| Audio | Bark groups Lives plays when the cue exists: `Greet_Warm`, `Greet_Neutral`, `Greet_Cold`, `Greet_Afraid`, `Greet_Grieving`, `Grief`, and `Remark` / `Talk` / `Chat` for street chats. |

Chat director: set `Lives.ChatDirector` to `<world subsystem class path>:<function>`, where the function is
`(TArray<AActor*> Speakers, [FName Spot]) -> bool`. Lives calls it when two people start a chat. If it returns
false, Lives plays turns of barks instead.

## people.json schema (v1)

See the top of `people_stub.json` for a full example. Per person: `id` (stable forever), `name`, `sex` F|M, `age`
Young|Adult|Old, `side`, `job`, `jobTitle`, `archetype`, `look`, `home` (default `Home_<id>`), `work` (default
`Work_<job>`), `haunts[]`, `personality{traits[], warmth, courage, temper, chattiness}`, `summary`, `speechStyle`,
`quirk`, `likes[]`, `dislikes[]`, `fear`, `secret`, `family[{id, relation}]`, `friends[]`, `rivals[]`, `schedule` (a key
of `schedules` or inline steps), `quest`. Top level: `day{realMinutesPerDay, startHour}`, `schedules{}`,
`generator{firstNames{F,M}, surnames, jobs[{job, jobTitle, weight, schedule, side}], traits, quirks, speechStyles,
likes, fears, haunts, schedules, friendsPerPerson[min,max]}`. Built-in schedules: `day_worker`, `early_riser`,
`night_owl`, `idler`, `guard_watch`. Family and friendship go both ways, whichever side lists them.

Packaging: re-import after the story file changes (Python):
`unreal.ReflectionsPeopleBookAsset.import_from_file(unreal.load_asset('/Game/Lives/DA_PeopleBook'), path)`, then save.
`/Game/Lives` must be in `DirectoriesToAlwaysCook` (it is loaded by path).

## Consequences (merged build 19:30, Nov 14; not yet verified in PIE)

- **Deaths ripple.** A death at Wren's hand marks the person dead and killed by the player (saved). Family mourn for
  16 game hours and friends for 8, 1.5 times longer when Wren did it. From 17:00 to 23:00 the bereaved keep vigil at the
  lost one's door. Afterwards the persona keeps "They killed X; you will never forgive it". A placed townsperson that Wren
  killed stays gone after a reload.
- **Fear and hatred.** `GetPlayerFeeling(PersonId)` returns 0, 1 (afraid) or 2 (hates) once opinion is at or below -0.35.
  Both keep out of Wren's way within 7 m: the afraid run about 16 m unless they are brave, the hateful walk off with a cold
  bark. They no longer stop when Wren walks up. The overlay shows "Keeping away from the Silverer".
- **Crimes.** Lives binds npc-unify's `OnPlayerCrime(Victim, Crime, Witness, Location, Heat)` by name, after a signature
  check. `ReportPlayerCrime(Crime, Victim, Location, Witness)` on Lives does the same for anyone who calls it.
  Witnesses lose opinion of Wren (the `WitnessedCrime` deed and a `Crimes` count), feel afraid, angry or wary, and carry
  an event such as "saw the Silverer steal from Tom (friend)" into their persona. The story flag `Silverer_RecordClean`
  fades all of this to hearsay.
- **Soldiers of the town** (Brask's company) run on the book's `company_soldier` / `soldier` templates, with a built-in
  `soldier_watch` fallback: barracks, patrol between post and haunt, the inn. They spawn as the friendly Guard archetype
  in a Giltside Soldier look. Squads' marching soldiers (`NPC_Soldier`) still have no life.
- **Sides never mix.** Casting and spawning match the look's `Look_Side_*` tag. Without a tag the look's name decides:
  Gilt or Red is Giltside, Frost, White or Rag is Frostside. Spawned looks also match sex and job. The least-worn face
  is picked, never one already worn within 30 m.

## Status (Nov 14, 15:55)

**Verified in PIE on train #7 (Lvl_HeroSampleCrowd), 8 of 8 checks** (`Tools/Lives/verify_lives.py`, results and pictures in
`ArtDirection/Lives/Screenshots/`, raw log in `verify_lives.json`):

| Check | Result |
|---|---|
| Every NPC has a person | 14/14 actors cast as story people (Ilse Varrow, Barnaby Thrale, Sergeant Maud Kettering, Goldie Fairweather, Jory Pell...) |
| Names unique | yes |
| Persona has no secrets | yes (checked against each person's `secret`) |
| Schedules move people | at 12:00, 7 of 14 walked to their work places / clique spots |
| Friends meet and chat | Ilse Varrow and Amos Saffery (Lantern Row clique) met at Lantern Row and talked; Maud went to meet Goldie |
| A witness reacts | Ilse was taken by the Tarnish: Amos (her clique) turned **grieving**, got away from the spot, and his persona now says "saw Ilse Varrow (one of their crowd) taken by the Tarnish"; Barnaby and Odette went home grieving, Dov and Maud angry, Goldie, Jory and Lucan fled afraid; friends out of sight "heard" |
| Night | people went home and inside (several still away, afraid, as the Tarnish spread from Ilse) |

Also seen in that session: the cutscene session spawned Jory Pell through `SpawnPerson`; quests set story flags through
`SetStoryFlag`; the Lives snapshot saves with each game-flow checkpoint ("Lives snapshot saved: 42 people").

**Mock city run (train #9, Lvl_MockCity with markers and navmesh, 16:29), 6 of 8** (`Screenshots/Mock_*`):
everyone cast (7 of 7 townsfolk embodied, 42 people tracked), names unique, no secrets; real places resolved
(each person's own `Home_<id>` front door, `Mk_Gilt_Market_LanternRow`, `Mk_Gilt_Workshop_*`, `Mk_Pew_Stop_CoalLane`...);
Goldie Fairweather taken: Tobin Lark (friend) reacted and remembers it, Ilse, Maud, Tobias, Lucan, Hollis grieve, Hal (her
husband, in the cellar) grieves, Dov and Ros are angry; at night everyone not grieving or away went home to sleep.
Misses: (1) noon movement 3 of 8 (most embodied people were already at or near their noon place; the rest are virtual
and simply "are" there); (2) no chat: the two clique-mates on Bell Lane both walked to the exact marker point and kept
shoving each other, so they never "arrived" and never looked for company. Fixed for train #10: each person walks to
their own spot within the place's radius. Also moved the Lives clock line below the world-jump panel.

**Known gaps**
- The A-E pictures were taken with the overlay on the engine debug canvas, which the MCP viewport capture leaves out.
  Train #8 draws it in Slate (`ReflectionsLivesOverlay`): see `F_overlay_level1.png` / `F_overlay_level2.png` (train #8,
  16:04). In that picture tags sat high and overlapped in a crowd; the next build anchors them on the head bone, shows
  only name + activity beyond 18 m, and moves or drops cards that would cover a nearer one (compiles; not yet seen).
- Train #8 (READY, compiles): stricter casting (sex, guard/civilian, age tags; unknown-sex bodies never get a named
  person), story-clique conversations through the crowd director's `PlayConversationById`, persona wording fixes,
  separate doors on a shared generic home. Not PIE-tested yet.
- The night check counts describe lines loosely (it passed, but it counts virtual people too).
- On the test map every place is auto-placed (no `Mk_` markers), so walks are short; the real map's markers replace them.
