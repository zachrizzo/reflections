# Everything in people.json except the named people.

README = {
    "what": "The people book of Reflections: 41 named people, their cliques, the rules for generating the rest of the crowd, schedule templates, marker conventions, and every named person's barks. Written by the story session; see ArtDirection/Story/bible.md.",
    "version": "1.0 (2026-11-14)",
    "consumers": {
        "npc-lives": "schedules, markers, family/friends, fear/want/secret, infection_reactions",
        "npc-dialogue": "personality, knows, opinion_of_silverer, secret (never volunteered; see dialogue_rules), barks as style reference",
        "jam-audio": "voice_id (from ArtDirection/Audio/data/voice_roster.json, re-matched to the 14:15 roster by tools/match_voices.py; audio may swap any of them), voice_design, barks (bake one wave per line), cliques (story cliques; independent of audio's C01-C48 ids)",
        "crowd-looks": "look (a pinned look id from Tools/CrowdLooks/cast.json, story-critical people only; Lives keeps that face everywhere) and appearance (sex, age, build, side, role, clothing, gear, tags)",
        "quest-system / cutscenes": "story.quests, story.cutscenes, markers; see main-quest.md, side-quests.md, cutscenes.md",
    },
    "rules": [
        "Ids are stable snake_case; reference people only by id.",
        "voice_id is a VoiceId from the audio roster. Every named person has a different one. The voice_design.brief describes the ideal voice; if the roster voice doesn't fit, redesign from the brief and keep the VoiceId.",
        "No bark line, cured line or tarnished line is shared by two people. build_people.py checks this; keep it true when editing.",
        "side is the person's home side. found_in, when present, is where they are at game start (drifters).",
        "age_band uses crowd-looks' tags: Young (<30), Adult (30-64), Old (65+).",
        "archetype is a hint for the NPC system's archetype assets: Civilian, Timid, Brave, Guard or Soldier.",
    ],
}

DIALOGUE_RULES = {
    "secret": "Never volunteered. A person may hint at it when calm and the Silverer's standing is liked or admired, and only reveals it during their side quest.",
    "knows": "Safe facts the person shares freely; good material for share_lore replies.",
    "opinion_of_silverer": "Their starting stance. The live reputation band can soften or harden it, but never flips a 'resentful' person to 'admiring' in one step.",
    "never_says": "Words or subjects the person avoids. Their replies must not contain them.",
    "infection_band": "Pass the current band (below) so replies match the mood of the street.",
}

INFECTION_BANDS = [
    {"band": "quiet", "fraction": [0.0, 0.25], "street_mood": "Wary but normal. People gossip about the burning eyes as rumour."},
    {"band": "spreading", "fraction": [0.25, 0.5], "street_mood": "Doors shut early. People travel in pairs and talk about who has turned."},
    {"band": "rising", "fraction": [0.5, 0.75], "street_mood": "Fear in the open. Timid people stay home; brave ones gather at the clique spot to guard it."},
    {"band": "brink", "fraction": [0.75, 1.01], "street_mood": "Panic and grief. The meter's warning shows. Barks switch to their 'dread' line."},
]

MARKERS = {
    "format": "Mk_<Side>_<Kind>_<Name>, as an actor tag on any placed actor (a Target Point is fine). Side is Pew, Gilt or Frost.",
    "kinds": ["Home", "Market", "Gate", "Inn", "Cellar", "Steps", "Yard", "Lane", "Square", "Tower", "Rift", "Workshop",
              "Camp", "Stop", "Stair", "Infirmary", "Laundry", "Doorstep", "Shelter", "Wall", "Shed", "Cistern", "Barracks"],
    "resolution": [
        "1. An actor with the exact tag.",
        "2. Otherwise any actor tagged Mk_<Side>_<Kind> (the generic kind on the same side).",
        "3. Otherwise a reachable navmesh point 10-25 m from that side's world anchor, picked by a stable hash of the person's id, so it's the same place every run.",
    ],
    "note": "The map is built by a teammate. Nothing in the story depends on geometry; every place is a marker that can sit anywhere.",
    "named_places": {
        "Mk_Gilt_Square_BellSquare": "Giltside's central square with the dry fountain. Intro and first-conversion spot.",
        "Mk_Gilt_Market_LanternRow": "Lantern Row, the candle-and-glass market (clique lantern_row).",
        "Mk_Gilt_Gate_LanternGate": "The Lantern Gate and its bridge (clique lantern_gate).",
        "Mk_Gilt_Camp_UnderGate": "The drifters' camp under the Lantern Gate (clique drifters_camp).",
        "Mk_Gilt_Inn_Lamplight": "The Lamplight inn; Wren lodges upstairs (clique lamplight).",
        "Mk_Gilt_Cellar_Lamplight": "The inn's cellar, where Hal is hidden (SQ1).",
        "Mk_Gilt_Steps_Archive": "The Archive steps (clique archive_steps).",
        "Mk_Gilt_Yard_Muster": "The Lamp Companies' muster yard (clique muster_yard).",
        "Mk_Gilt_Lane_BellLane": "Bell Lane, where the lamps are failing (clique bell_lane, SQ7).",
        "Mk_Gilt_Rift_Canal": "The canal rift post (SQ6).",
        "Mk_Gilt_Tower_GiltTower": "The Gilt Tower's sealed door.",
        "Mk_Gilt_Workshop_Furnace": "Dov's glass furnace.",
        "Mk_Gilt_Workshop_ThraleShop": "Barnaby's tailoring shop.",
        "Mk_Pew_Stop_CoalLane": "The Coal Lane tram stop (clique coal_lane_stop).",
        "Mk_Pew_Doorstep_Hester": "Hester's doorstep on Coal Lane (SQ4).",
        "Mk_Pew_Steps_FishSteps": "The Fish Steps market by the river (clique fish_steps).",
        "Mk_Pew_Square_WeighHouse": "Weigh-House Corner (clique weigh_house_corner).",
        "Mk_Pew_Stair_WeighHouse": "Foot of the Old Weigh-House stair up to the first page.",
        "Mk_Pew_Infirmary_WickStreet": "The Wick Street infirmary.",
        "Mk_Pew_Laundry_CoalLane": "The Coal Lane steam laundry.",
        "Mk_Frost_Stair_IceStairs": "The Ice Stairs (clique ice_stairs).",
        "Mk_Frost_Market_BoneMarket": "The Bone Market (clique bone_market).",
        "Mk_Frost_Shelter_LongShelter": "The Long Shelter (clique long_shelter).",
        "Mk_Frost_Gate_FrozenGate": "The gate that won't close.",
        "Mk_Frost_Wall_IceWall": "The ice wall.",
        "Mk_Frost_Shed_Sorrel": "Sorrel's shed (SQ8).",
        "Mk_Frost_Tower_FrostTower": "Inside the sealed Frost Tower (the Gilt Tower's reflection).",
    },
}

SCHEDULES = {
    "_about": "Blocks in game hours (0-24). Activities: sleep, home, work, eat, chat (at the clique spot with clique-mates), stroll (between markers), patrol (between work and haunt), shop, hide (stay home, doors shut), guard (stand at work marker facing out). If the game has no clock, run one game hour per real minute starting at 18:00, because the game opens at dusk. infection_overrides apply on top of any block.",
    "templates": {
        "trader": [[6, 8, "home"], [8, 12, "work"], [12, 13, "chat"], [13, 18, "work"], [18, 21, "chat"], [21, 6, "sleep"]],
        "craft": [[6, 9, "home"], [9, 13, "work"], [13, 14, "eat"], [14, 19, "work"], [19, 22, "chat"], [22, 6, "sleep"]],
        "innkeeper": [[8, 11, "home"], [11, 15, "work"], [15, 16, "shop"], [16, 2, "work"], [2, 8, "sleep"]],
        "performer": [[10, 13, "home"], [13, 16, "stroll"], [16, 19, "chat"], [19, 1, "work"], [1, 10, "sleep"]],
        "lamplighter": [[11, 16, "sleep"], [16, 18, "work"], [18, 21, "patrol"], [21, 23, "chat"], [23, 4, "patrol"], [4, 11, "sleep"]],
        "scholar": [[7, 9, "home"], [9, 18, "work"], [18, 20, "chat"], [20, 24, "home"], [0, 7, "sleep"]],
        "watch_day": [[5, 6, "home"], [6, 14, "guard"], [14, 15, "eat"], [15, 18, "patrol"], [18, 21, "chat"], [21, 5, "sleep"]],
        "watch_night": [[10, 17, "sleep"], [17, 18, "chat"], [18, 2, "guard"], [2, 6, "patrol"], [6, 10, "home"]],
        "soldier": [[5, 6, "work"], [6, 12, "patrol"], [12, 13, "eat"], [13, 18, "guard"], [18, 21, "chat"], [21, 5, "sleep"]],
        "company_soldier": [[5, 6, "home"], [6, 7, "work"], [7, 12, "patrol"], [12, 13, "eat"], [13, 18, "guard"], [18, 23, "chat"], [23, 5, "sleep"]],
        "errand": [[6, 7, "home"], [7, 12, "stroll"], [12, 13, "chat"], [13, 18, "work"], [18, 21, "chat"], [21, 6, "sleep"]],
        "conductor": [[5, 6, "home"], [6, 20, "work"], [20, 22, "chat"], [22, 5, "sleep"]],
        "elder_doorstep": [[7, 10, "home"], [10, 13, "work"], [13, 15, "home"], [15, 19, "chat"], [19, 7, "sleep"]],
        "laundry": [[4, 5, "home"], [5, 13, "work"], [13, 14, "eat"], [14, 18, "work"], [18, 21, "chat"], [21, 4, "sleep"]],
        "night_worker": [[8, 16, "sleep"], [16, 18, "chat"], [18, 8, "work"]],
        "labourer": [[4, 5, "home"], [5, 12, "work"], [12, 13, "eat"], [13, 17, "work"], [17, 21, "chat"], [21, 4, "sleep"]],
        "healer": [[6, 8, "home"], [8, 12, "work"], [12, 14, "stroll"], [14, 20, "work"], [20, 22, "chat"], [22, 6, "sleep"]],
        "shelter": [[5, 7, "work"], [7, 10, "shop"], [10, 16, "work"], [16, 18, "guard"], [18, 24, "work"], [0, 5, "sleep"]],
        "drifter": [[0, 7, "sleep"], [7, 11, "stroll"], [11, 14, "chat"], [14, 18, "stroll"], [18, 24, "chat"]],
        "special_cellar": [[0, 24, "home"]],
    },
    "infection_overrides": {
        "spreading": "Timid: chat blocks become home. Others: unchanged.",
        "rising": "Timid: everything except sleep becomes hide. Civilian: stroll and shop become home. Brave: chat moves to the work marker and becomes guard. Guard and Soldier: patrol becomes guard.",
        "brink": "Timid and Civilian: hide. Brave: guard the clique spot. Guard and Soldier: guard their work marker, then answer warn_guards alarms.",
    },
}

CLIQUES = [
    {"id": "lantern_row", "name": "Lantern Row", "side": "Giltside", "spot": "Mk_Gilt_Market_LanternRow",
     "members": ["ilse_varrow", "barnaby_thrale", "dov_merriman", "amos_saffery"],
     "dynamic": "Old trade friends and a newcomer. Ilse and Barnaby are fifty years of shared gossip; Dov and Amos bicker about money; all four tease Ilse about her apprentice."},
    {"id": "lantern_gate", "name": "The Lantern Gate", "side": "Giltside", "spot": "Mk_Gilt_Gate_LanternGate",
     "members": ["maud_kettering", "nell_bramley"],
     "dynamic": "A sergeant and her youngest guard. Maud is hard on Nell because she's afraid for her; Nell takes it as proof she's failing."},
    {"id": "lamplight", "name": "The Lamplight", "side": "Giltside", "spot": "Mk_Gilt_Inn_Lamplight",
     "members": ["goldie_fairweather", "jory_pell", "corin_ashby"],
     "dynamic": "The inn's regulars. Goldie mothers both men, Jory plays for his supper, and Corin comes in to warm up between lamp rounds. All three know something is wrong with Goldie and are too kind to ask."},
    {"id": "archive_steps", "name": "The Archive Steps", "side": "Giltside", "spot": "Mk_Gilt_Steps_Archive",
     "members": ["tobias_quell", "odette_vane", "lucan_marlowe"],
     "dynamic": "A salon on the steps. The Professor lectures, Odette punctures him, and Lucan performs for both of them."},
    {"id": "muster_yard", "name": "The Muster Yard", "side": "Giltside", "spot": "Mk_Gilt_Yard_Muster",
     "members": ["sela_brask", "ros_thrale", "emeric_dunstan"],
     "dynamic": "A captain, a soldier who disagree about the drifters and both know it, and the old hornblower who carried Brask off the ice thirty years ago and is the only one allowed to call her lad. Brask likes Ros and would never say so."},
    {"id": "third_company_table", "name": "The Third Company's Table at the Lamplight", "side": "Giltside", "spot": "Mk_Gilt_Inn_Lamplight",
     "members": ["aldric_mayne", "bram_tolley", "cosmo_fennick", "damaris_hobb"],
     "dynamic": "Off-duty soldiers at the corner table of Goldie's taproom (the company's tavern block, 18:00-23:00). Mayne runs the table like a drill; Damaris mothers the recruit; Bram says little and pays for everyone; Cosmo tells tall tales that the other three correct."},
    {"id": "bell_lane", "name": "Bell Lane", "side": "Giltside", "spot": "Mk_Gilt_Lane_BellLane",
     "members": ["pim_ashgrove", "tobin_lark", "hollis_greave"],
     "dynamic": "Two young men and a tired guard who keeps an eye on them. Tobin teases Pim; Hollis pretends not to care about either."},
    {"id": "coal_lane_stop", "name": "Coal Lane Tram Stop", "side": "Pewterside", "spot": "Mk_Pew_Stop_CoalLane",
     "members": ["edie_bramley", "hester_quaile", "walter_dunmore", "sid_kettle"],
     "dynamic": "The old guard of Coal Lane. Hester holds court, Walter adores her silently, Edie keeps time, and Sid fetches and carries for all of them."},
    {"id": "fish_steps", "name": "The Fish Steps", "side": "Pewterside", "spot": "Mk_Pew_Steps_FishSteps",
     "members": ["bet_crawley", "agnes_moth", "ada_pollard", "ned_lusk"],
     "dynamic": "Market-morning regulars. Bet roars, Agnes yawns, Ada tells stories nobody finishes, and Ned listens to all of them."},
    {"id": "weigh_house_corner", "name": "Weigh-House Corner", "side": "Pewterside", "spot": "Mk_Pew_Square_WeighHouse",
     "members": ["ivy_harker", "horace_pratt", "winnie_cobb", "frank_dunning"],
     "dynamic": "The corner's daily argument. Frank shouts, Horace predicts doom, Winnie pours tea for both, and Ivy tries to take statements."},
    {"id": "ice_stairs", "name": "The Ice Stairs", "side": "Frostside", "spot": "Mk_Frost_Stair_IceStairs",
     "members": ["gunnar_skarre", "mother_rook", "tilly_frane"],
     "dynamic": "A grandmother, her granddaughter and the ice-cutter who looks after both of them without being asked."},
    {"id": "bone_market", "name": "The Bone Market", "side": "Frostside", "spot": "Mk_Frost_Market_BoneMarket",
     "members": ["greta_holm", "brenna_cold", "sorrel_vey"],
     "dynamic": "Three hard women who trade dark jokes the way other people trade news."},
    {"id": "drifters_camp", "name": "The Drifters under the Gate", "side": "Frostside", "found_in": "Giltside", "spot": "Mk_Gilt_Camp_UnderGate",
     "members": ["kit_marrow", "fen_lowry"],
     "dynamic": "Two Frostside drifters stuck in Giltside. Kit wants to go home; Fen will do anything to stay."},
    {"id": "long_shelter", "name": "The Long Shelter", "side": "Frostside", "spot": "Mk_Frost_Shelter_LongShelter",
     "members": ["marta_quarry", "dagny_thorn", "eskil_varn"],
     "dynamic": "The shelter's keepers. Marta runs it, Dagny guards its useless gate, and Eskil loves Marta and has never said a word."},
]

PRINCIPALS = [
    {"id": "wren_hale", "name": "Wren Hale", "say": "REN HAIL", "sex": "M", "age": 25, "side": "Giltside",
     "role": "the hero; the Silverer",
     "personality": {"traits": ["steady", "wry", "guarded"],
                     "speech_style": "Short, warm, a little wry. Jokes when he's frightened, goes quiet when he's angry.",
                     "never_says": ["traveller", "magic"]},
     "history": "Ilse Varrow's apprentice from twelve. His mother, Elin Hale, went into the glass nine years ago and never came back. Lodges above the Lamplight inn.",
     "flaw": "He polishes everyone else's reflection and never looks at his own; he hasn't looked into a mirror on purpose since his mother went.",
     "voice_design": {"brief": "A man in his mid-twenties with a warm, steady, mid-range baritone and a soft, educated Giltside accent; calm and grounded, with a dry, wry lift at the end of a joke.",
                      "delivery": "warm, steady, a little wry"},
     "look": {"note": "The existing hero (young adult man, warm brown skin, short black curls) in the silvered coat with the cut-ring clasp."}},
    {"id": "the_tarnish", "name": "the Tarnish", "pronoun": "it", "role": "the villain",
     "personality": {"traits": ["patient", "amused", "intimate"],
                     "speech_style": "Close, low and slow; never shouts. Talks about faces, fit, polish and wearing people. Says people's secrets out loud.",
                     "never_says": ["I", "me (it says 'we' through the tarnished; it speaks as 'I' only in its true form, rarely)"]},
     "voice_design": {"brief": "An ageless, sexless voice, very low and close to the ear, dry as dust on glass; unhurried and gently amused, every word savoured.",
                      "delivery": "whispered, close, amused"},
     "note": "Its existing lines are in canon.md; new ones are in main-quest.md and cutscenes.md."},
    {"id": "elin_hale", "name": "Elin Hale", "role": "Wren's mother; a Silverer lost in the glass nine years ago. Never appears. The Tarnish uses her against Wren in the finale.",
     "sex": "F"},
    {"id": "the_glazier", "name": "the Glazier", "role": "the first Silverer, who made the Lanthorne Glass and cut the city in three. Historical; name lost."},
]

GENERATOR = {
    "_about": "Rules for the unnamed crowd. Seed every pick with a stable hash of the actor's name (or NPC id) so a person is the same every run. Generated people get a persona for live replies and use their roster voice's baked lines; they get no new baked lines of their own, so nothing they say can repeat a named person's line.",
    "steps": [
        "1. Side = the side the NPC spawns in. Sex = from its look tag (NPC_Voice_F/M).",
        "2. Given name from the side's pool for that sex, surname from the side's pool. Reject a full name that a named person or another generated person already has.",
        "3. Job from the side's job pool, weighted toward the roster role of the NPC's VoiceId if it has one.",
        "4. Three traits: one from each of the three trait columns, never all three matching another generated person on the same side.",
        "5. One speech style, one tic, one fear and one want from the side's pools; schedule template from the job.",
        "6. Opinion of the Silverer: weighted by side (Giltside: 50% likes, 30% wary, 20% admires; Pewterside: 40% wary, 40% neutral, 20% likes; Frostside: 50% wary, 30% resentful, 20% likes).",
    ],
    "names": {
        "Giltside": {
            "F": ["Amberly", "Clemency", "Sabine", "Rosamund", "Lettice", "Aurelie", "Philippa", "Damaris", "Celandine", "Honora", "Isolde", "Marisol", "Viola", "Juniper", "Seraphine", "Blanche", "Cordelia", "Elodie", "Fenella", "Gisela", "Hermione", "Lavinia", "Perpetua", "Saffron"],
            "M": ["Aldous", "Benedict", "Cosmo", "Darius", "Emeric", "Fabian", "Gideon", "Horatio", "Ignatius", "Julian", "Leander", "Maximilian", "Octavian", "Peregrine", "Quentin", "Rafferty", "Sebastian", "Tancred", "Valentine", "Wystan", "Ambrose", "Cyprian", "Florian", "Lorcan"],
            "surnames": ["Goldwin", "Brassington", "Larkspur", "Ambersley", "Candlewick", "Brightmore", "Sunderby", "Waxley", "Glimmerton", "Fairbright", "Oakengild", "Lampwright", "Honeyfold", "Radiance", "Embery", "Saffrey", "Sparkworth", "Guildford", "Sheaffe", "Torchwell"],
        },
        "Pewterside": {
            "F": ["Doris", "Maureen", "Peg", "Joan", "Elsie", "Ivy", "Gladys", "Mavis", "Nora", "Win", "Dot", "Flo", "Hilda", "Ida", "Lil", "Madge", "Olive", "Pearl", "Queenie", "Rene", "Sal", "Vi", "Bess", "Kath"],
            "M": ["Albert", "Bert", "Cyril", "Dennis", "Ern", "Fred", "George", "Harold", "Len", "Norman", "Percy", "Ron", "Stan", "Ted", "Vic", "Wilf", "Alf", "Clem", "Den", "Herb", "Joe", "Reg", "Sid", "Wally"],
            "surnames": ["Pratt", "Dunmore", "Hobb", "Smalley", "Grice", "Tapper", "Mudd", "Leadbetter", "Slate", "Pewsey", "Raine", "Tinsley", "Drabble", "Dimmock", "Fogg", "Kettleby", "Ashby-Low", "Greyling", "Puddifoot", "Stubbs"],
        },
        "Frostside": {
            "F": ["Ylva", "Runa", "Signe", "Hedda", "Tove", "Inga", "Maren", "Solveig", "Vigdis", "Astrid", "Brynja", "Dagrun", "Embla", "Frida", "Gudrun", "Hild", "Ingrid", "Liv", "Ragna", "Sigrun", "Thyra", "Una", "Wenna", "Yrsa"],
            "M": ["Arne", "Bjorn", "Calder", "Destin", "Egil", "Finnr", "Grim", "Halvard", "Ivar", "Jarl", "Knut", "Leif", "Magnus", "Njal", "Orm", "Ragnar", "Sten", "Torvald", "Ulf", "Vidar", "Aske", "Brand", "Hakon", "Rurik"],
            "surnames": ["Rime", "Skarde", "Holt", "Thornby", "Frane", "Hale-Ice", "Coldwater", "Snowe", "Vardholm", "Whitlock", "Ashfrost", "Bleakley", "Hoarstone", "Glasswick", "Shiver", "Crackenby", "Pale", "Starke", "Winterbourne", "Haugr"],
        },
        "_never": ["Kell", "Lila", "Holland", "Rhy", "Osaron", "London", "any name of a real public person"],
    },
    "jobs": {
        "Giltside": ["lantern maker", "candle seller", "glassblower", "tailor", "spice trader", "baker", "flower seller", "innkeeper", "festival musician", "dancer", "street performer", "apprentice", "scholar", "bridge guard", "Lantern Watch sergeant", "Lamp Company soldier", "Lamp Company captain", "battle caster", "bell-ringer", "gilder"],
        "Pewterside": ["tram conductor", "laundry worker", "fishmonger", "night nurse", "dock worker", "tea-stall keeper", "newspaper seller", "clerk", "cab driver", "chimney sweep", "bookbinder", "seamstress", "pensioner", "student", "shopkeeper", "watch constable", "night watchman"],
        "Frostside": ["ice-cutter", "broth seller", "bone carver", "hedge healer", "scavenger", "salvage trader", "shelter keeper", "gate guard", "Wall Company soldier", "ice-wall defender", "elder", "orphan", "drifter", "rune carver", "beggar", "fallen house-keeper"],
    },
    "traits": {
        "_about": "Pick one from each column. Column A is temper, B is how they treat others, C is what drives them.",
        "A": ["anxious", "calm", "hot-tempered", "gloomy", "cheerful", "nervy", "stoic", "dreamy", "brisk", "sly", "sardonic", "earnest"],
        "B": ["generous", "suspicious", "nosy", "shy", "bossy", "loyal", "flirtatious", "blunt", "polite", "scornful", "motherly", "teasing"],
        "C": ["proud", "greedy", "devout about light", "homesick", "ambitious", "grieving", "curious", "lazy", "protective", "vain", "superstitious", "hopeful"],
    },
    "speech_styles": {
        "Giltside": ["warm and showy, lots of praise", "fast festival patter", "formal, a little pompous", "sing-song and teasing", "loud and confident, a touch boastful", "polished and careful, like someone minding manners"],
        "Pewterside": ["dry and flat, says little", "grumbling, every sentence a complaint", "chatty, gossip in every line", "plain and practical", "deadpan, jokes without smiling", "slow and kindly"],
        "Frostside": ["blunt and terse", "dark jokes about the cold", "suspicious questions back at you", "old sayings and short proverbs", "hoarse and quick, words bitten off", "quiet and watchful"],
    },
    "tics": ["clears their throat before bad news", "rubs their hands for warmth", "repeats the last word you said", "laughs at their own jokes", "taps their nose", "counts under their breath", "hums", "squints at the sky", "fiddles with a button", "sighs before answering", "pats their pockets", "glances over their shoulder", "names the weather", "calls everyone by a nickname", "corrects your grammar", "spits for luck"],
    "fears": {
        "Giltside": ["the lamps going out", "being called a coward", "the curfew bell", "a drifter taking their job", "their son marching to the rift", "a mirror in their own house"],
        "Pewterside": ["the river", "losing the job", "being noticed", "the landlord", "nobody coming if they shout", "the fog at the end of the street"],
        "Frostside": ["the fog", "the cracks widening", "a cold night with no shelter place", "being left behind", "warm-siders taking what's left", "still water"],
    },
    "wants": {
        "Giltside": ["the war over by festival", "a medal", "a shop of their own", "their sweetheart home from the Company", "to be painted", "to see Frostside once, safely"],
        "Pewterside": ["a dry roof", "a quiet pint", "a better job across the river", "their kids to get out", "a warm coat for winter", "one day off"],
        "Frostside": ["coal", "a whole loaf", "to see the gold side", "their family together under one roof", "the wall to hold one more winter", "to sleep without the fog"],
    },
    "secrets": ["owes money they can't pay", "has a tarnished relative they haven't reported", "came through a rift and hides it", "stole a mirror shard", "loves someone in their clique and won't say", "is going blind, or deaf", "deserted a post", "sold someone out to the Watch"],
}


# Mk_ tag -> the quest system's Story Marker name (ArtDirection/Quests/README.md). One marker may carry both names.
STORY_NAMES = {
    "Mk_Gilt_Square_BellSquare": "Spot_BellSquare", "Mk_Gilt_Market_LanternRow": "Spot_LanternRow",
    "Mk_Gilt_Gate_LanternGate": "Spot_LanternGate", "Mk_Gilt_Camp_UnderGate": "Spot_DrifterCamp",
    "Mk_Gilt_Inn_Lamplight": "Spot_Lamplight", "Mk_Gilt_Cellar_Lamplight": "Spot_LamplightCellar",
    "Mk_Gilt_Steps_Archive": "Spot_ArchiveSteps", "Mk_Gilt_Yard_Muster": "Spot_MusterYard",
    "Mk_Gilt_Lane_BellLane": "Spot_BellLane", "Mk_Gilt_Rift_Canal": "Spot_CanalRift",
    "Mk_Gilt_Tower_GiltTower": "Tower_Giltside", "Mk_Gilt_Workshop_Furnace": "Spot_Furnace",
    "Mk_Gilt_Workshop_ThraleShop": "Spot_ThraleShop", "Mk_Gilt_Workshop_Vane": "Spot_VaneAtelier",
    "Mk_Gilt_Home_Barracks": "Spot_GiltBarracks", "Mk_Gilt_Home_WatchBarracks": "Spot_WatchBarracks",
    "Mk_Pew_Stop_CoalLane": "Spot_CoalLaneStop", "Mk_Pew_Doorstep_Hester": "Spot_HesterDoorstep",
    "Mk_Pew_Steps_FishSteps": "Spot_FishSteps", "Mk_Pew_Square_WeighHouse": "Spot_WeighHouseCorner",
    "Mk_Pew_Stair_WeighHouse": "Tower_Pewterside", "Mk_Pew_Infirmary_WickStreet": "Spot_WickStreetInfirmary",
    "Mk_Pew_Laundry_CoalLane": "Spot_CoalLaneLaundry",
    "Mk_Frost_Stair_IceStairs": "Spot_IceStairs", "Mk_Frost_Market_BoneMarket": "Spot_BoneMarket",
    "Mk_Frost_Shelter_LongShelter": "Spot_LongShelter", "Mk_Frost_Gate_FrozenGate": "Spot_FrozenGate",
    "Mk_Frost_Wall_IceWall": "Spot_IceWall", "Mk_Frost_Shed_Sorrel": "Spot_SorrelShed",
    "Mk_Frost_Tower_FrostTower": "Tower_Frostside", "Mk_Frost_Cistern": "Spot_Cistern",
    "Mk_Frost_Home_Barracks": "Spot_FrostBarracks",
}
MARKERS["story_names"] = dict(STORY_NAMES, **{
    "_about": "The quest system's Reflections Story Marker names for each Mk_ place. Map owner: give one Story Marker both names (Marker Name = the Spot_/Tower_ name, plus the Mk_ tag). Every person's home is Home_<id> (people[].markers_story.home); quest givers can also use QuestGiver_<id>.",
    "extra": ["Spot_BellLaneLamp1", "Spot_BellLaneLamp2", "Spot_BellLaneLamp3", "Item_Fiddle", "CutsceneAnchor_BurningEyes"]})


# Story-critical people keep one finished face everywhere (crowd-looks' cast.json ids; Lives matches the look class name).
# Everyone else is cast at runtime by sex, side and role. No Giltside soldier looks and no Pewterside looks exist yet.
LOOK_PINS = {
    "ilse_varrow": "GiltMaren", "barnaby_thrale": "GiltBarnaby", "jory_pell": "GiltHaruto", "pim_ashgrove": "GiltArchivist",
    "maud_kettering": "GiltRowena", "nell_bramley": "GiltBridgeGuard", "goldie_fairweather": "GiltCoinClerk",
    "dov_merriman": "GiltGlassman", "petra_lisle": "GiltDrummer",
    "mother_rook": "FrostHyeon", "kit_marrow": "FrostIven", "fen_lowry": "FrostNia", "gunnar_skarre": "FrostSilas",
    "brenna_cold": "FrostSaran",
    # Pewterside: crowd-looks' grey PewLook_* copies of the Giltside outfits (same faces, re-tinted). The sides are offset
    # copies far apart, so a Pew face and its Giltside twin are never on screen together. Free faces go to Bet, Sid and Frank;
    # Edie wears Nell's face on purpose (her granddaughter). Ada is left to runtime casting (7 women, 6 women's looks).
    "hester_quaile": "PewLook_Maren", "edie_bramley": "PewLook_BridgeGuard", "ivy_harker": "PewLook_Rowena",
    "winnie_cobb": "PewLook_CoinClerk", "bet_crawley": "PewLook_Priya", "agnes_moth": "PewLook_Drummer",
    "walter_dunmore": "PewLook_Barnaby", "horace_pratt": "PewLook_Glassman", "sid_kettle": "PewLook_Ferryman",
    "frank_dunning": "PewLook_Ramon", "ned_lusk": "PewLook_Archivist",
}

# Until cast.json lists the Pewterside looks (relayed by the orchestrator for crowd-looks, 2026-11-14 evening).
PEW_LOOKS = {f"PewLook_{n}": {"id": f"PewLook_{n}", "sex": s, "side": "Pewterside"} for n, s in [
    ("Archivist", "M"), ("Barnaby", "M"), ("BridgeGuard", "F"), ("CoinClerk", "F"), ("Drummer", "F"), ("Ferryman", "M"),
    ("Glassman", "M"), ("Haruto", "M"), ("Maren", "F"), ("Priya", "F"), ("Ramon", "M"), ("Rowena", "F")]}
