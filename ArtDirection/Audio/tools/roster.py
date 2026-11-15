"""Voice roster for Lanthorne's NPCs: 120 designed Gemini voices (60 F / 60 M), 20 per sex per side.

Each entry: VoiceId, sex, side, age band, archetype fit, role, persona, Voice-design description (1-2 sentences:
age, timbre, texture, attitude, accent). Deterministic (seeded) so the roster is stable across runs.
Never "London" (canon). Accents are described generically or by region, not by city of the old premise.
"""
import json, os, random

SIDES = {
    "Pewterside": {"mood": "dull, grey, everyday, rain and work",
                   "roles": {"civilian": ["clerk", "dock worker", "cab driver", "shopkeeper", "student", "pensioner", "seamstress",
                                          "chimney sweep", "night-shift nurse", "bookbinder", "tram conductor", "laundry worker"],
                             "guard": ["watch constable", "night watchman"],
                             "vendor": ["newspaper seller", "fishmonger", "tea-stall keeper"]}},
    "Giltside": {"mood": "warm, glowing, bustling festival streets",
                 "roles": {"civilian": ["baker", "festival musician", "lantern maker", "tailor", "scholar", "glassblower",
                                        "innkeeper", "street performer", "apprentice", "dancer"],
                           "guard": ["bridge guard", "city watch sergeant"],
                           "soldier": ["soldier", "squad captain", "battle mage"],
                           "vendor": ["spice trader", "flower seller", "candle vendor"]}},
    "Frostside": {"mood": "cold, cracked, bleached and starving",
                  "roles": {"civilian": ["scavenger", "refugee", "frostbitten elder", "orphan", "ice-cutter", "beggar",
                                         "hedge healer", "shelter keeper", "ruined noble", "bone carver"],
                            "guard": ["ragged gate guard", "rune-marked sentry"],
                            "vendor": ["salvage trader", "broth seller"]}},
}

AGES = [("young", "in her early twenties", "in his early twenties"), ("adult", "in her thirties", "in his thirties"),
        ("middle", "in her fifties", "in his fifties"), ("older", "in her seventies", "in his seventies")]

TIMBRE = {
    "F": ["bright, clear soprano", "warm, low alto", "husky, smoky", "breathy and light", "slightly nasal", "crisp and precise",
          "rich and rounded", "thin and reedy", "throaty and rough", "soft and velvety", "sharp and quick", "deep for a woman, steady"],
    "M": ["deep, rumbling bass", "warm baritone", "gravelly", "nasal tenor", "reedy and thin", "booming and broad",
          "soft-spoken and gentle", "raspy", "mellow and smooth", "clipped and dry", "light, boyish tenor", "hoarse and cracked"],
}
TEXTURE = ["with a slight rasp", "with a smooth finish", "with an airy edge", "with a faint quaver", "with an even steadiness",
           "with a gruff edge", "with a sing-song lilt", "with a nervous tremble", "with a tired drawl", "with a lively bounce"]
OLD_ROLES = {"pensioner", "frostbitten elder", "ruined noble"}
YOUNG_ROLES = {"student", "apprentice", "orphan", "street performer", "dancer"}
ATTITUDE = {
    "Pewterside": ["weary but polite", "dry and matter-of-fact", "kind but rushed", "gloomy and wry", "quietly worried", "brisk and practical"],
    "Giltside": ["cheerful and warm", "proud and confident", "teasing and playful", "earnest and eager", "loud and jolly", "gracious"],
    "Frostside": ["wary and suspicious", "bitter and blunt", "hollow and exhausted", "fierce and defiant", "gentle despite everything", "hushed and fearful"],
}
ACCENTS = ["soft Scottish", "lilting Welsh", "gentle Irish", "broad northern English", "Yorkshire", "rural West Country",
           "crisp, refined southern English", "working-class southern English", "Midlands", "northeastern English",
           "Merseyside-style", "Caribbean-British", "South Asian-British", "West African-British", "Eastern European"]
ARCH_FOR_ROLE = {"guard": "guard", "soldier": "soldier", "vendor": "civilian", "civilian": "civilian"}


def build(seed=1759):
    rng = random.Random(seed)
    roster, used = [], set()
    n = 1
    for sex in ("F", "M"):
        for side, spec in SIDES.items():
            roles = [(k, r) for k, rs in spec["roles"].items() for r in rs]
            # 20 voices per sex per side: 5 per age band; at least 2 guards and (Giltside) 3 soldiers
            must = [x for x in roles if x[0] in ("guard", "soldier")]
            picks = must[:]
            pool = [x for x in roles if x not in must]
            while len(picks) < 20:  # every role once before any repeats
                batch = pool[:]
                rng.shuffle(batch)
                picks += batch[: 20 - len(picks)]
            rng.shuffle(picks)
            for i, (kind, role) in enumerate(picks):
                band, fage, mage = AGES[i % 4]
                if kind == "soldier" and band == "older":
                    band, fage, mage = AGES[2]
                if role in OLD_ROLES:
                    band, fage, mage = AGES[3]
                elif role in YOUNG_ROLES:
                    band, fage, mage = AGES[0]
                for _ in range(50):
                    tim, tex, att, acc = rng.choice(TIMBRE[sex]), rng.choice(TEXTURE), rng.choice(ATTITUDE[side]), rng.choice(ACCENTS)
                    key = (sex, tim, acc, band)
                    if key not in used:
                        used.add(key)
                        break
                age = fage if sex == "F" else mage
                article = "An" if role[0] in "aeiou" else "A"
                desc = (f"{article} {role} {age}: a {tim} voice {tex}; {att}; {acc} accent.")
                roster.append({"VoiceId": f"V{n:03d}", "Sex": sex, "Side": side, "AgeBand": band, "Archetype": ARCH_FOR_ROLE[kind],
                               "Role": role, "Attitude": att, "Accent": acc, "Description": desc})
                n += 1
    return roster


if __name__ == "__main__":
    r = build()
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "roster.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    old = {v["VoiceId"]: v for v in json.load(open(out))} if os.path.exists(out) else {}
    for v in r:  # keep any Gemini voice ids already created
        if v["VoiceId"] in old and old[v["VoiceId"]].get("GeminiVoice") and old[v["VoiceId"]]["Description"] == v["Description"]:
            v["GeminiVoice"] = old[v["VoiceId"]]["GeminiVoice"]
    json.dump(r, open(out, "w"), indent=1)
    from collections import Counter
    print(len(r), Counter(v["Sex"] for v in r), Counter(v["Side"] for v in r), Counter(v["Archetype"] for v in r))
    for v in r[:3] + r[60:63]:
        print(v["VoiceId"], v["Description"])
