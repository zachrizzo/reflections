"""Throwaway spike, version 2: a town of about 40 people over 25 years.

NOT game code. Families, births and a second generation, workplaces with
owners and workers, and about 50 kinds of event. Rules and numbers are
placeholders for judging whether rule-driven histories read like stories
(ArtDirection/NpcBehavior/Plan.md). Names are placeholders until the
setting is known. Version 1 (five people) is gen_lives_v1.py.

    python gen_lives.py                      # 3 towns of about 40 people
    python gen_lives.py --seeds 7 8 --people 40

Writes out/towns40.json and out/town40.html, and prints each chronicle.
"""
import argparse
import json
import os

SEASONS = ["winter", "winter", "spring", "spring", "spring", "summer",
           "summer", "summer", "autumn", "autumn", "autumn", "winter"]

FIRST = {
    "F": ["Edda", "Lise", "Mara", "Agnes", "Ysolde", "Bette", "Wenna", "Hild", "Joan", "Maud", "Tilda", "Rosa",
          "Alys", "Cecily", "Emma", "Isolde", "Juliana", "Margery", "Nell", "Petra", "Sabine", "Una", "Avice",
          "Beatrix", "Clemence", "Dulcie", "Elena", "Gwen", "Hawise", "Ida", "Kat", "Lettice", "Mabel", "Odile",
          "Philippa", "Rohese", "Sybil", "Thea", "Willa", "Ermina", "Fenna", "Greta", "Helois", "Jacoba"],
    "M": ["Harl", "Oswin", "Wat", "Tobin", "Aldric", "Bram", "Piers", "Godric", "Hob", "Simon", "Ned", "Corin",
          "Alard", "Bennet", "Colin", "Drogo", "Edric", "Fulk", "Gerard", "Hugh", "Ivo", "Jack", "Lambert",
          "Martin", "Nicol", "Osbert", "Quentin", "Ralf", "Sewin", "Tam", "Ulric", "Walter", "Yves", "Arnold",
          "Baldwin", "Conrad", "Denis", "Elias", "Gilbert", "Herve", "Jory", "Kit", "Lowen", "Merrick"],
}
SURNAMES = ["Fenn", "Cobb", "Pike", "Thorne", "Ashby", "Marsh", "Crane", "Hale", "Brook", "Tull", "Wren",
            "Barrow", "Dunn", "Garrow", "Holt", "Kemp", "Lowe", "Mercer", "Nash", "Orme", "Pryor", "Rook",
            "Sallow", "Vane", "Webb", "Ayre", "Burl", "Croft", "Dale", "Esk"]

# trade: (workplace, monthly income, most owners in town). Living costs about 6 a month.
TRADES = {
    "baker": ("bakery", 7, 2), "smith": ("forge", 8, 2), "miller": ("mill", 9, 1),
    "carter": ("carter's yard", 6, 2), "tavern keeper": ("tavern", 8, 2), "weaver": ("weaving shed", 6, 2),
    "herbalist": ("herb garden", 5, 1), "fisher": ("jetty", 5, 3), "butcher": ("butcher's shop", 7, 2),
    "cooper": ("cooperage", 6, 1), "chandler": ("chandlery", 6, 1), "mason": ("mason's yard", 7, 2),
    "tailor": ("tailor's shop", 6, 1), "potter": ("pottery", 5, 1), "tanner": ("tannery", 6, 1),
}
RIVER = {"miller", "fisher", "tanner", "weaver"}

TRAITS = ["kind", "greedy", "proud", "jealous", "honest", "gossipy",
          "hot-headed", "forgiving", "sly", "ambitious", "lazy", "shy"]
CLASH = [{"kind", "greedy"}, {"honest", "sly"}, {"forgiving", "hot-headed"},
         {"ambitious", "lazy"}, {"gossipy", "shy"}, {"forgiving", "jealous"}]

GROUP = {
    "courting": "love", "marriage": "love", "unrequited": "love", "affair": "love", "caught": "love",
    "separation": "love", "jealousy": "love", "breakup": "love", "forbids": "love", "elope": "love",
    "runaway": "love", "parentage": "love",
    "friends": "bond", "gift": "bond", "adopt": "bond", "apprentice": "bond", "forgive_debt": "bond",
    "borrow": "money", "repay": "money", "callin": "money", "takeover": "money", "inherit": "money",
    "hardtimes": "money", "hire": "money", "buys": "money", "closes": "money", "inherit_wp": "money",
    "theft": "crime", "exposed": "crime", "silence": "crime", "blame": "crime", "slip": "crime",
    "confess": "crime", "blackmail": "crime", "sabotage": "crime", "killing": "crime", "exiled": "crime",
    "fight": "conflict", "peace": "conflict", "rumor": "conflict", "rivalry": "conflict", "feud": "conflict", "feud_end": "conflict",
    "flood": "hardship", "fire": "hardship", "harvest": "hardship", "fever": "hardship", "accident": "hardship",
    "birth": "life", "death": "life", "leaves": "life", "arrival": "life", "family": "life", "found": "life",
    "drink": "life", "sober": "life",
}


# story types the director can switch off per town
DIRECTED = ["affair", "theft", "rivalry", "takeover", "drink", "rumor", "blackmail", "sabotage", "forbids",
            "jealousy", "unrequited", "fight", "feud", "buys", "callin", "elope"]
DIRECTOR_OFF = 0.35
# ...and features two kinds of trouble it leans toward, so the biggest story isn't nearly always a theft
FEATURABLE = ["affair", "theft", "rivalry", "drink", "blackmail", "sabotage", "fight", "feud"]
FEATURE_BOOST = 3.0
THEFT_BASE = 0.5


MASK = (1 << 64) - 1


# Port rule: every loop over a set runs in ascending id order (sorted), and dicts are iterated in
# insertion order, so a C++ port that keeps the same orders rebuilds the same towns.
class Rng:
    """Portable SplitMix64. Every draw comes from random(), with no library algorithms behind it,
    so a C++ port seeded the same way rebuilds the same town event for event."""

    def __init__(self, seed):
        self.s = seed & MASK

    def u64(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def random(self):
        return (self.u64() >> 11) * (1.0 / 9007199254740992.0)

    def below(self, n):
        return min(n - 1, int(self.random() * n))

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def choices(self, seq, weights):
        total, cum = 0.0, []
        for wt in weights:
            total += wt
            cum.append(total)
        x = self.random() * total
        for item, c in zip(seq, cum):
            if x < c:
                return [item]
        return [seq[-1]]

    def sample(self, seq, k):
        pool = list(seq)
        for i in range(k):
            j = i + self.below(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]


class Workplace:
    def __init__(self, wid, trade):
        self.id, self.trade = wid, trade
        self.place, self.income, _ = TRADES[trade]
        self.owner = None
        self.workers = set()
        self.open = True


class Person:
    def __init__(self, pid, first, surname, sex, birth_t, traits, attracted):
        self.id, self.first, self.surname, self.sex = pid, first, surname, sex
        self.given = first
        self.birth_t, self.traits, self.attracted = birth_t, traits, attracted
        self.parents, self.children = [], []
        self.money = 0.0
        self.trade = None
        self.wp = None
        self.house = None
        self.alive, self.gone = True, False
        self.spouse = None
        self.sick_until = self.hurt_until = -1
        self.sick_cause = None
        self.last_blow = self.desperate = None
        self.last_theft = self.last_hardtimes = -999
        self.drink = False
        self.died = self.left = None
        self.arrived = None
        self.friends = set()
        self.worked = False
        self.exit_eid = None  # the event where they died or left

    def has(self, t):
        return t in self.traits

    @property
    def here(self):
        return self.alive and not self.gone


class World:
    def __init__(self, seed, n=40, years=25):
        self.seed, self.years, self.target = seed, years, n
        self.rng = Rng(seed)
        self.t = 0
        self.events, self.people, self.wps = [], [], []
        self.like, self.love, self.spark, self.affinity = {}, {}, {}, {}
        self.grudge, self.cooldown, self.flags = {}, {}, set()
        self.debts, self.secrets, self.beliefs, self.blackmails = [], [], [], []
        self.courting, self.affairs, self.feuds, self.rivals = {}, {}, {}, set()
        self.siblings = set()
        self.next_house = 0
        # each town gets its own temperament: some traits common, some rare, some kinds of trouble louder
        self.trait_w = {t: self.rng.choice([0.25, 1, 1, 3]) for t in TRAITS}
        self.mood = {k: self.rng.choice([0.35, 1, 1, 2.2]) for k in ("love", "crime", "luck", "temper", "money")}
        # the director: each town leaves out about a third of the kinds of trouble
        self.off = set(self.rng.sample(DIRECTED, int(len(DIRECTED) * DIRECTOR_OFF)))
        on = [k for k in FEATURABLE if k not in self.off]
        self.featured = set(self.rng.sample(on, min(2, len(on))))
        self.found_town()

    # ---------- people ----------
    def age(self, p):
        return (self.t - p.birth_t) / 12

    def adult(self, p):
        return self.age(p) >= 16

    def here(self):
        return [p for p in self.people if p.here]

    def P(self, pid):
        return self.people[pid]

    def pick_traits(self, parents=()):
        rng = self.rng
        pool = [t for p in parents for t in p.traits]
        while True:
            t = []
            for _ in range(2):
                if pool and rng.random() < 0.4:
                    t.append(rng.choice(pool))
                else:
                    t.append(rng.choices(TRAITS, [self.trait_w[x] for x in TRAITS])[0])
            if t[0] != t[1] and set(t) not in CLASH:
                return t

    def name(self, sex):
        ever = {p.given for p in self.people}
        living = {p.given for p in self.here()}
        free = [f for f in FIRST[sex] if f not in ever] or [f for f in FIRST[sex] if f not in living]
        return self.rng.choice(free or FIRST[sex])

    def surname(self):
        used = {p.surname for p in self.people}
        free = [s for s in SURNAMES if s not in used]
        return self.rng.choice(free or SURNAMES)

    def add_person(self, sex, surname, age=None, birth_t=None, parents=()):
        rng = self.rng
        if birth_t is None:
            birth_t = self.t - int(age * 12) - rng.randint(0, 11)
        opp = "M" if sex == "F" else "F"
        r = rng.random()
        attracted = {opp} if r < 0.88 else ({sex} if r < 0.94 else {"F", "M"})
        given = self.name(sex)
        call = given  # what the town calls them: the first name, or first name and surname when it's taken
        if any(q.given == given for q in self.here()):
            call = f"{given} {surname}"
            while any(q.first == call for q in self.people):
                call += " the younger"
        p = Person(len(self.people), call, surname, sex, birth_t, self.pick_traits(parents), attracted)
        p.given = given
        p.parents = [q.id for q in parents]
        for q in parents:
            q.children.append(p.id)
        self.people.append(p)
        for q in self.people[:-1]:
            pair = frozenset((p.id, q.id))
            self.spark[pair] = rng.random()
            self.affinity[pair] = rng.uniform(-15, 30)
            self.like[p.id, q.id] = self.natural(p, q) + rng.uniform(-10, 10)
            self.like[q.id, p.id] = self.natural(q, p) + rng.uniform(-10, 10)
            self.love[p.id, q.id] = self.love[q.id, p.id] = 0.0
        return p

    def kin(self, a, b):
        if a.id in b.parents or b.id in a.parents:
            return True
        if set(a.parents) & set(b.parents):
            return True
        return frozenset((a.id, b.id)) in self.siblings

    def feud_between(self, a, b):
        return self.feuds.get(frozenset((a.surname, b.surname))) if a.surname != b.surname else None

    def natural(self, a, b):
        """Where a's feeling for b settles if nothing happens."""
        v = 8.0 + self.affinity[frozenset((a.id, b.id))]
        if self.kin(a, b):
            v += 40
        if a.spouse == b.id:
            v += 40
        if b.id in a.friends:
            v += 15
        shared = set(a.traits) & set(b.traits) - {"jealous", "hot-headed", "proud", "sly", "greedy"}
        v += 10 * len(shared)
        if b.has("kind"):
            v += 10
        if a.has("proud") and b.has("proud"):
            v -= 15
        if (a.has("honest") and b.has("sly")) or (a.has("sly") and b.has("honest")):
            v -= 12
        if a.has("kind") and b.has("greedy"):
            v -= 8
        if b.has("hot-headed"):
            v -= 6
        if b.drink:
            v -= 6
        if self.feud_between(a, b) is not None and not self.kin(a, b) and a.spouse != b.id:
            v -= 25
        for pid in a.parents:
            if self.like.get((pid, b.id), 0) < -50 and not self.kin(a, b):
                v -= 12
                break
        return v

    def maybe_feud(self, a, b, cause, chance=0.35):
        """A serious wrong between two families can start a feud."""
        if a.surname == b.surname or self.kin(a, b) or a.spouse == b.id or not (a.here and b.here):
            return
        key = frozenset((a.surname, b.surname))
        if key in self.feuds or ("feud", key) in self.flags:
            return
        def has_kin(p):
            return any(q.here and q is not p and (self.kin(p, q) or q.spouse == p.id) for q in self.people)
        if has_kin(a) and has_kin(b) and self.allowed("feud") and self.rng.random() < min(1.0, chance * self.boost("feud")):
            self.flags.add(("feud", key))
            x, y = sorted((a.surname, b.surname))
            self.feuds[key] = self.ev("feud", [a, b], f"The {x}s and the {y}s stop speaking. It's a feud now.", [cause])

    # ---------- the founding ----------
    def found_town(self):
        rng = self.rng
        founders = int(self.target * 0.65)
        while len(self.people) < founders:
            r = rng.random()
            house = self.new_house()
            if r < 0.45:
                sn = self.surname()
                h = self.add_person("M", sn, rng.randint(20, 42))
                w = self.add_person("F", sn, max(18, min(42, self.age(h) + rng.randint(-6, 3))))
                self.wed(h, w, house, founding=True)
                for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
                    youngest = min(self.age(h), self.age(w))
                    if youngest < 20:
                        break
                    k = self.add_person(rng.choice("FM"), sn, rng.randint(0, int(min(12, youngest - 18))), parents=(h, w))
                    k.house = house
            elif r < 0.7:
                p = self.add_person(rng.choice("FM"), self.surname(), rng.randint(18, 40))
                p.house = house
            elif r < 0.85:
                sn = self.surname()
                a = self.add_person(rng.choice("FM"), sn, rng.randint(18, 36))
                b = self.add_person(rng.choice("FM"), sn, max(18, self.age(a) + rng.randint(-5, 5)))
                a.house = b.house = house
                self.siblings.add(frozenset((a.id, b.id)))
                word = {("F", "F"): "sisters", ("M", "M"): "brothers"}.get((a.sex, b.sex), "brother and sister")
                self.ev("family", [a, b], f"{a.first} and {b.first} {sn} are {word} and share a house.")
            else:
                sn = self.surname()
                par = self.add_person(rng.choice("FM"), sn, rng.randint(26, 44))
                par.house = house
                kids = []
                for _ in range(rng.choice([1, 2])):
                    k = self.add_person(rng.choice("FM"), sn, rng.randint(1, int(min(12, self.age(par) - 18))), parents=(par,))
                    k.house = house
                    kids.append(k)
                word = "widow" if par.sex == "F" else "widower"
                self.ev("family", [par] + kids, f"{par.first} {sn}, a {word}, is raising {self.names(kids)} alone.")
        for p in self.people:
            p.money = rng.randint(10, 45) if self.adult(p) else 0
        for p in sorted(self.people, key=lambda q: -self.age(q)):
            if self.adult(p):
                self.give_work(p, founding=True)
        for a in self.people:
            for b in self.people:
                if a is not b:
                    self.like[a.id, b.id] = self.natural(a, b) + rng.uniform(-10, 10)

    def new_house(self):
        self.next_house += 1
        return self.next_house

    def names(self, ps):
        ps = [p.first for p in ps]
        return ps[0] if len(ps) == 1 else ", ".join(ps[:-1]) + " and " + ps[-1]

    def move_house(self, p, h):
        """p moves to house h. Children under 16 they leave behind with no other grown-up come along."""
        old = p.house
        p.house = h
        if old is None or old == h:
            return
        if any(q.here and self.adult(q) and q.house == old for q in self.people):
            return
        for k in self.people:
            if k.here and not self.adult(k) and k.house == old:
                k.house = h

    def wed(self, a, b, house=None, founding=False):
        a.spouse, b.spouse = b.id, a.id
        h = house or self.new_house()
        self.move_house(a, h)
        self.move_house(b, h)
        self.love[a.id, b.id] = max(self.love[a.id, b.id], 70.0)
        self.love[b.id, a.id] = max(self.love[b.id, a.id], 70.0)
        if founding:
            self.ev("marriage", [a, b], f"{a.first} and {b.first} {a.surname} are married.")

    # ---------- work ----------
    def owners_of(self, trade):
        return [w for w in self.wps if w.open and w.trade == trade and w.owner is not None]

    def open_trades(self):
        return [t for t, (_, _, mx) in TRADES.items() if len(self.owners_of(t)) < mx]

    def wpname(self, w):
        o = self.P(w.owner) if w.owner is not None else None
        return f"{o.first}'s {w.place}" if o else f"the {w.place}"

    def join(self, p, w):
        self.leave_wp(p)
        p.wp = w.id
        p.trade = w.trade
        w.workers.add(p.id)

    def own(self, p, w):
        if p.wp is not None and p.wp != w.id and self.wps[p.wp].owner == p.id:
            w.owner = p.id  # keeps their own place and owns this one too
            w.workers.discard(p.id)
            return
        self.leave_wp(p)
        p.wp = w.id
        p.trade = w.trade
        w.owner = p.id

    def leave_wp(self, p):
        if p.wp is None:
            return
        w = self.wps[p.wp]
        w.workers.discard(p.id)
        if w.owner == p.id:
            w.owner = None
        p.wp = None

    def give_work(self, p, founding=False):
        rng = self.rng
        p.worked = True
        if p.spouse is not None and rng.random() < 0.35:
            s = self.P(p.spouse)
            if s.wp is not None and self.wps[s.wp].owner == s.id:
                self.join(p, self.wps[s.wp])
                return None
        for sib in self.people:
            if sib is not p and frozenset((p.id, sib.id)) in self.siblings and sib.wp is not None and rng.random() < 0.5:
                if self.wps[sib.wp].owner == sib.id:
                    self.join(p, self.wps[sib.wp])
                    return None
        free = self.open_trades()
        if free and (founding or rng.random() < 0.5):
            w = Workplace(len(self.wps), rng.choice(free))
            self.wps.append(w)
            self.own(p, w)
            return None
        shops = [w for w in self.wps if w.open and w.owner is not None and len(w.workers) < 3]
        if shops:
            w = max(shops, key=lambda w: self.like[p.id, w.owner] + rng.uniform(-10, 10))
            self.join(p, w)
            return w
        return None

    # ---------- events ----------
    def allowed(self, kind):
        return kind not in self.off

    def boost(self, kind):
        return FEATURE_BOOST if kind in self.featured else 1.0

    def ev(self, kind, actors, text, causes=(), secret=False):
        e = {
            "id": len(self.events), "t": self.t, "year": self.t // 12 + 1, "season": SEASONS[self.t % 12],
            "kind": kind, "group": GROUP[kind], "actors": list(dict.fromkeys(p.id for p in actors)), "text": text,
            "causes": sorted({c for c in causes if c is not None}), "secret": secret,
        }
        self.events.append(e)
        return e["id"]

    def recent(self, mark, months):
        if mark and self.t - mark[1] <= months:
            return mark[0]
        return None

    def hurt(self, a, b, amount, cause):
        self.like[a.id, b.id] -= amount
        if self.like[a.id, b.id] < -30 and cause is not None:
            self.grudge.setdefault((a.id, b.id), cause)

    def ready(self, key, months):
        if self.t - self.cooldown.get(key, -9999) < months:
            return False
        self.cooldown[key] = self.t
        return True

    def open_debt(self, borrower=None):
        for d in self.debts:
            if d["open"] and (borrower is None or d["b"] == borrower.id):
                return d
        return None

    def kids_home(self, p):
        return [self.P(c) for c in p.children if self.P(c).here and not self.adult(self.P(c))]

    # ---------- monthly rules ----------
    def step(self):
        quarter = self.t % 3 == 0
        self.economy(self.here())
        self.town_events(self.here())
        if quarter:
            self.feelings(self.here())
            self.business(self.here())
            self.moving(self.here())
        self.romance(self.here())
        self.family(self.here())
        self.money_rules(self.here())
        self.crime(self.here())
        self.secrets_rules(self.here())
        self.conflict(self.here(), quarter)
        self.mortality(self.here())
        self.t += 1

    def economy(self, people):
        rng = self.rng
        for p in people:
            if not self.adult(p):
                continue
            if p.wp is None:
                income = 5.5
            else:
                w = self.wps[p.wp]
                if w.owner == p.id:
                    income = w.income * (1 + 0.15 * len(w.workers))
                    if any(frozenset((p.id, o.owner)) in self.rivals for o in self.owners_of(w.trade) if o.owner != p.id):
                        income *= 0.85
                else:
                    income = w.income * 0.75
            income *= (0.7 if p.has("lazy") else 1) * (1.2 if p.has("ambitious") else 1) * (0.7 if p.drink else 1)
            income += rng.uniform(-2, 2)
            if self.t < p.sick_until or self.t < p.hurt_until:
                income = 0
            kids = len(self.kids_home(p))
            spend = (5 if p.spouse is not None else 6) + 0.8 * kids - (0.8 if p.has("greedy") else 0)
            if p.money < 0:
                spend = min(spend, 4.2 + 0.6 * kids)
            p.money = max(-150.0, p.money + income - spend)

    def town_events(self, people):
        rng = self.rng
        adults = [p for p in people if self.adult(p)]
        for p in adults:
            if p.wp is not None and rng.random() < 0.0005 * (2 if p.drink else 1):
                w = self.wps[p.wp]
                place = f"the {w.place}" if w.owner == p.id else self.wpname(w)
                aid = self.ev("accident", [p], f"{p.first} is badly hurt in an accident at {place}.")
                p.hurt_until = self.t + rng.randint(3, 8)
                p.last_blow = (aid, self.t)
                if rng.random() < 0.1:
                    self.die(p, "dies of the injuries", [aid])
        if rng.random() > 0.012 * self.mood["luck"] or not adults:
            return
        kind = rng.choice(["flood", "fire", "harvest", "fever"])
        if kind == "flood":
            places = [w for w in self.wps if w.open and w.trade in RIVER]
            if not places:
                return
            hit = [self.P(i) for w in places for i in ([w.owner] if w.owner is not None else []) + sorted(w.workers) if self.P(i).here]
            eid = self.ev("flood", hit, f"The river floods and wrecks {self.names_list([self.wpname(w) for w in places])}.")
            for w in places:
                if w.owner is not None:
                    self.P(w.owner).money -= rng.randint(35, 70)
        elif kind == "fire":
            places = [w for w in self.wps if w.open and w.owner is not None]
            if not places:
                return
            w = rng.choice(places)
            hit = [self.P(w.owner)] + [self.P(i) for i in sorted(w.workers) if self.P(i).here]
            eid = self.ev("fire", hit, f"Fire guts {self.wpname(w)}.")
            self.P(w.owner).money -= rng.randint(45, 90)
        elif kind == "harvest":
            hit = adults
            eid = self.ev("harvest", [], "The harvest fails, and the whole town goes short that winter.")
            for p in hit:
                p.money -= rng.randint(8, 18)
        else:
            hit = rng.sample(people, min(len(people), rng.choice([1, 2, 2, 3])))
            eid = self.ev("fever", hit, f"Fever comes to town. {self.names(hit)} {'falls' if len(hit) == 1 else 'fall'} sick.")
            for p in hit:
                p.sick_until = self.t + rng.randint(2, 5)
                p.sick_cause = eid
        for p in hit:
            p.last_blow = (eid, self.t)
        if kind in ("flood", "fire"):
            owners = [p for p in hit if p.wp is not None and self.wps[p.wp].owner == p.id]
            offers = [(k, p) for p in owners for k in adults if k not in hit and k.money > 60 and k.spouse != p.id
                      and (k.has("kind") or self.like[k.id, p.id] > 45)]
            if offers and rng.random() < 0.6:
                k, p = max(offers, key=lambda kp: self.like[kp[0].id, kp[1].id])
                amt = rng.choice([20, 30, 40])
                k.money -= amt
                p.money += amt
                self.ev("gift", [k, p], f"{k.first} gives {p.first} {amt} silver to rebuild, and asks nothing back.", [eid])
                self.like[p.id, k.id] += 30

    def names_list(self, items):
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

    def feelings(self, people):
        rng = self.rng
        for a in people:
            for b in people:
                if a is b:
                    continue
                rate = 0.03
                if a.has("forgiving") or a.has("kind"):
                    rate = 0.09
                if a.has("jealous") or a.has("proud") or a.has("hot-headed"):
                    rate = 0.012
                key = (a.id, b.id)
                self.like[key] += (self.natural(a, b) - self.like[key]) * rate
                if key in self.grudge and self.like[key] > -8:
                    cause = self.grudge.pop(key)
                    if self.ready(("peace", a.id, b.id), 24):
                        self.ev("peace", [a, b], f"{a.first} finally forgives {b.first}.", [cause])
        adults = [p for p in people if self.adult(p)]
        for a in adults:
            for b in adults:
                if (a.id < b.id and b.id not in a.friends and not self.kin(a, b) and a.spouse != b.id
                        and self.like[a.id, b.id] > 48 and self.like[b.id, a.id] > 48
                        and self.love[a.id, b.id] < 40 and self.love[b.id, a.id] < 40 and frozenset((a.id, b.id)) not in self.courting
                        and len(a.friends) < 2 and len(b.friends) < 2 and rng.random() < 0.25):
                    a.friends.add(b.id)
                    b.friends.add(a.id)
                    how = rng.choice(["become close friends", "become fast friends", "grow as close as family"])
                    self.ev("friends", [a, b], f"{a.first} and {b.first} {how}.")
        for p in people:
            if p.drink and (p.has("ambitious") or self.kids_home(p)) and rng.random() < 0.03:
                p.drink = False
                self.ev("sober", [p], f"{p.first} gives up the drink.")

    def romance(self, people):
        rng = self.rng
        adults = [p for p in people if self.age(p) >= 17]
        ages = {p.id: self.age(p) for p in adults}
        for a in adults:
            for b in adults:
                if a is b or b.sex not in a.attracted or abs(ages[a.id] - ages[b.id]) > 15:
                    continue
                pair = frozenset((a.id, b.id))
                spark = self.spark[pair]
                if spark < 0.5 or self.kin(a, b) or self.like[a.id, b.id] < (0 if spark > 0.8 else 15):
                    continue
                grow = 1.2 * spark + rng.uniform(0, 1)
                if a.spouse is not None and a.spouse != b.id:
                    grow *= 1.2 if self.like[a.id, a.spouse] < 0 else 0.45
                self.love[a.id, b.id] = min(100, self.love[a.id, b.id] + grow)

        for a in adults:
            for b in adults:
                if a.id >= b.id or self.kin(a, b) or not (a.here and b.here):
                    continue
                pair = frozenset((a.id, b.id))
                lab, lba = self.love[a.id, b.id], self.love[b.id, a.id]
                if lab < 30 and lba < 30 and pair not in self.courting:
                    continue
                free = a.spouse is None and b.spouse is None
                if free and pair not in self.courting and lab >= 45 and lba >= 45:
                    busy = any((a.id in pr or b.id in pr) for pr in self.courting)
                    if not busy:
                        cid = self.ev("courting", [a, b], f"{a.first} and {b.first} start courting.")
                        c = {"eid": cid, "since": self.t, "forbid": None}
                        self.check_forbid(a, b, c)
                        self.courting[pair] = c
                elif pair in self.courting:
                    c = self.courting[pair]
                    if c["forbid"] is None and self.t % 3 == 0:
                        self.check_forbid(a, b, c)
                    if not free:
                        self.courting.pop(pair)
                    elif min(lab, lba) < 30:
                        self.courting.pop(pair)
                        self.ev("breakup", [a, b], f"{a.first} and {b.first} break it off.", [c["eid"]])
                    elif self.t - c["since"] >= 6 and min(lab, lba) >= 60 and rng.random() < 0.08:
                        self.courting.pop(pair)
                        self.marry(a, b, c, people)
                for x, y in ((a, b), (b, a)):
                    if (self.love[x.id, y.id] >= 80 and self.love[y.id, x.id] < 15
                            and ("unreq", x.id) not in self.flags and x.spouse != y.id and self.allowed("unrequited")):
                        self.flags.add(("unreq", x.id))
                        hidden = x.has("shy") or x.spouse is not None
                        if rng.random() < (0.65 if not hidden else 0.5):
                            continue
                        eid = self.ev("unrequited", [x, y],
                                      f"{x.first} falls for {y.first}, who doesn't feel the same" + (". It stays a secret." if hidden else "."),
                                      secret=hidden)
                        if hidden:
                            self.add_secret({"eid": eid, "kind": "love", "keepers": {x.id}, "doer": x.id,
                                                 "victim": y.id, "open": True})
                married = [p for p in (a, b) if p.spouse is not None]
                lover_of = {i for pr in self.affairs for i in pr}
                if (married and a.spouse != b.id and pair not in self.affairs and min(lab, lba) >= 65
                        and a.id not in lover_of and b.id not in lover_of
                        and self.cooldown.get(("lover", a.id), pair) == pair and self.cooldown.get(("lover", b.id), pair) == pair
                        and ("affairs", a.id) not in self.flags and ("affairs", b.id) not in self.flags):
                    chance = 0.004 * self.mood["love"] * (2 if (a.has("sly") or b.has("sly")) else 1) * (0.2 if (a.has("honest") or b.has("honest")) else 1) * self.boost("affair")
                    before = self.cooldown.get(("caught", pair))
                    if before is not None:
                        chance *= 0.3 if self.cooldown.get(("restarts", pair), 0) < 1 else 0
                    if self.allowed("affair") and rng.random() < chance:
                        wronged = [self.P(p.spouse).first for p in married]
                        if before is None:
                            text = f"{a.first} and {b.first} begin an affair behind {' and '.join(wronged)}'s back."
                        else:
                            text = f"{a.first} and {b.first} can't stay apart, and start meeting in secret again."
                            self.cooldown[("restarts", pair)] = 1
                        eid = self.ev("affair", [a, b], text, [before], secret=True)
                        self.affairs[pair] = eid
                        self.cooldown[("lover", a.id)] = self.cooldown[("lover", b.id)] = pair
                        self.add_secret({"eid": eid, "kind": "affair", "keepers": {a.id, b.id},
                                             "doer": a.id, "victim": None, "open": True})

        for pair, eid in list(self.affairs.items()):
            a, b = (self.P(i) for i in sorted(pair))
            if not (a.here and b.here):
                self.affairs.pop(pair)
                continue
            for x, y in ((a, b), (b, a)):
                if x.spouse is None or x.spouse == y.id:
                    continue
                s = self.P(x.spouse)
                if s.here and rng.random() < 0.02:
                    cid = self.ev("caught", [s, x, y], f"{s.first} catches {x.first} with {y.first}.", [eid])
                    self.close_secret(eid)
                    self.affairs.pop(pair, None)
                    self.cooldown[("caught", pair)] = cid
                    self.hurt(s, x, 60, cid)
                    self.hurt(s, y, 70, cid)
                    self.maybe_drink(s, cid)
                    self.maybe_feud(s, y, cid)
                    if s.has("hot-headed") and rng.random() < 0.6:
                        fid = self.ev("fight", [s, y], f"{s.first} goes after {y.first} in the street.", [cid])
                        self.hurt(y, s, 25, fid)
                    elif s.has("sly") and rng.random() < 0.6:
                        rid = self.ev("rumor", [s, y], f"{s.first} makes sure the whole town knows what {y.first} did.", [cid])
                        for q in self.here():
                            if q not in (s, x, y):
                                self.like[q.id, y.id] -= 8
                    if self.like[s.id, x.id] < -40 and (s.has("proud") or s.has("hot-headed") or rng.random() < 0.5):
                        s.spouse = x.spouse = None
                        self.move_house(x, self.new_house())
                        self.flags.add(("affairs", x.id))
                        self.ev("separation", [s, x], f"{s.first} throws {x.first} out of the house.", [cid])
                    break

    def heartbreak(self, c, x, y, mid):
        """c loved x, who just married y."""
        rng = self.rng
        options = [("cold", 3)] if self.allowed("jealousy") else [("bless", 2)]
        if c.has("shy"):
            options.append(("pine", 6))
        if (c.has("jealous") or c.has("sly")) and self.allowed("rumor"):
            options.append(("rumor", 5))
        if c.has("hot-headed") and self.allowed("fight"):
            options.append(("fight", 4))
        if not (c.has("kind") or c.has("forgiving")) and self.allowed("drink"):
            options.append(("drink", 2))
        if c.spouse is None and not self.kids_home(c):
            options.append(("leave", 1))
        if c.has("kind") or c.has("forgiving"):
            options.append(("bless", 5))
        pick = rng.choices([o for o, _ in options], [wt for _, wt in options])[0]
        if pick == "cold":
            self.ev("jealousy", [c, y], f"{c.first} had hoped to marry {x.first}, and turns cold on {y.first}.", [mid])
            self.hurt(c, y, 35, mid)
        elif pick == "pine":
            eid = self.ev("unrequited", [c, x], f"{c.first} still loves {x.first}, and tells no one.", [mid], secret=True)
            self.add_secret({"eid": eid, "kind": "love", "keepers": {c.id}, "doer": c.id, "victim": x.id, "open": True})
        elif pick == "rumor":
            eid = self.ev("rumor", [c, y], f"Bitter over the match, {c.first} spreads lies about {y.first}.", [mid])
            self.hurt(y, c, 30, eid)
            for q in self.here():
                if q is not c and q is not y and self.like[q.id, c.id] > 20 and self.rng.random() < 0.3:
                    self.like[q.id, y.id] -= 15
        elif pick == "fight":
            eid = self.ev("fight", [c, y], f"{c.first} picks a fight with {y.first} at the wedding.", [mid])
            self.hurt(c, y, 30, eid)
            self.hurt(y, c, 30, eid)
        elif pick == "drink":
            c.drink = True
            self.ev("drink", [c], f"{c.first} takes to drink after losing {x.first}.", [mid])
        elif pick == "leave":
            self.leave_town(c)
            self.ev("leaves", [c, x], f"Heartbroken, {c.first} leaves town.", [mid])
            self.after_leaving(c)
        else:
            self.ev("peace", [c, x], f"{c.first} loved {x.first}, but wishes the couple well.", [mid])

    def check_forbid(self, a, b, c):
        if not self.allowed("forbids"):
            return
        for x, y in ((a, b), (b, a)):
            for pid in x.parents:
                pa = self.P(pid)
                if not pa.here:
                    continue
                feud = self.feud_between(pa, y)
                if self.like[pa.id, y.id] < -30 or feud is not None:
                    why = feud if feud is not None else self.grudge.get((pa.id, y.id))
                    fid = self.ev("forbids", [pa, x, y], f"{pa.first} forbids {x.first} to see {y.first}.", [c["eid"], why])
                    c["forbid"] = (fid, pa.id, x.id)
                    return
                poor = y.wp is None or y.money < -10 or (y.wp is not None and self.wps[y.wp].owner != y.id and pa.wp is not None and self.wps[pa.wp].owner == pa.id)
                if pa.has("proud") and poor and self.rng.random() < 0.5:
                    fid = self.ev("forbids", [pa, x, y], f"{pa.first} forbids {x.first} to see {y.first}: no {pa.surname} marries beneath them.", [c["eid"]])
                    c["forbid"] = (fid, pa.id, x.id)
                    return

    def marry(self, a, b, c, people):
        rng = self.rng
        forbid = c.get("forbid")
        if forbid and not self.P(forbid[1]).here:
            fid, pa_id, _ = forbid
            self.wed(a, b)
            mid = self.ev("marriage", [a, b], f"With {self.P(pa_id).first} gone, {a.first} and {b.first} marry at last.",
                          [c["eid"], fid, self.P(pa_id).exit_eid])
            forbid = None
        elif forbid:
            fid, pa_id, child_id = forbid
            pa = self.P(pa_id)
            if rng.random() < 0.4 or not self.allowed("elope"):
                self.wed(a, b)
                family = [k for p in (a, b) for k in self.kids_home(p)]
                self.leave_town(a, b, *family)
                self.hurt(pa, self.P(child_id), 40, fid)
                self.ev("runaway", [a, b, pa], f"Rather than give each other up, {a.first} and {b.first} run off together, defying {pa.first}.", [fid])
                self.after_leaving(a, b, *family)
                return
            self.wed(a, b)
            mid = self.ev("elope", [a, b, pa], f"{a.first} and {b.first} marry in secret, against {pa.first}'s wishes.", [fid])
            self.hurt(pa, self.P(child_id), 30, mid)
            feud = self.feud_between(a, b)
            if feud is not None and (pa.has("forgiving") or pa.has("kind") or rng.random() < 0.3):
                key = frozenset((a.surname, b.surname))
                self.feuds.pop(key, None)
                self.ev("feud_end", [a, b, pa], f"The match ends the feud between the {a.surname}s and the {b.surname}s.", [mid, feud])
        elif c.get("forbid") is None:
            self.wed(a, b)
            mid = self.ev("marriage", [a, b], f"{a.first} marries {b.first}.", [c["eid"], self.affairs.pop(frozenset((a.id, b.id)), None)])
        broken = 0
        for cpe in sorted([q for q in people if q not in (a, b)], key=lambda q: -max(self.love[q.id, a.id], self.love[q.id, b.id])):
            if cpe in (a, b) or not cpe.here or not self.adult(cpe) or broken >= 2:
                continue
            for x, y in sorted(((a, b), (b, a)), key=lambda xy: -self.love[cpe.id, xy[0].id]):
                if self.love[cpe.id, x.id] > 70 and ("jealous", cpe.id) not in self.flags:
                    self.flags.add(("jealous", cpe.id))
                    self.heartbreak(cpe, x, y, mid)
                    broken += 1
                    break

    def family(self, people):
        rng = self.rng
        n_here = len(people)
        for w in people:
            if w.sex != "F" or w.spouse is None:
                continue
            h = self.P(w.spouse)
            if not h.here or h.sex != "M" or not (18 <= self.age(w) <= 42) or len(w.children) >= 5:
                continue
            chance = 0.011 * (0.3 if n_here >= self.target + 6 else 1) * (0.5 if len(w.children) >= 3 else 1)
            if rng.random() > chance:
                continue
            lover = None
            for pair in self.affairs:
                if w.id in pair:
                    m = self.P(next(i for i in pair if i != w.id))
                    if m.sex == "M" and rng.random() < 0.5:
                        lover = m
            k = self.add_person(rng.choice("FM"), h.surname, birth_t=self.t, parents=(w, h))
            k.house = w.house
            word = "son" if k.sex == "M" else "daughter"
            bid = self.ev("birth", [w, h, k], f"{w.first} and {h.first} have a {word}, {k.first}.")
            if lover:
                knows = rng.random() < 0.5
                sid = self.ev("parentage", [w, lover, k], f"{k.first}'s real father is {lover.first}, not {h.first}.",
                              [bid, self.affairs.get(frozenset((w.id, lover.id)))], secret=True)
                self.add_secret({"eid": sid, "kind": "parentage", "keepers": {w.id} | ({lover.id} if knows else set()),
                                     "doer": w.id, "victim": h.id, "father": lover.id, "child": k.id, "open": True})
        for p in people:
            if not p.worked and self.age(p) >= 16:
                self.come_of_age(p)

    def come_of_age(self, p):
        rng = self.rng
        p.worked = True
        if p.wp is not None:
            return  # already inherited a place, the month they turned 16
        p.money = rng.randint(0, 10)
        family_shops = [self.wps[self.P(i).wp] for i in p.parents
                        if self.P(i).here and self.P(i).wp is not None and self.wps[self.P(i).wp].owner == i]
        if family_shops and rng.random() < 0.6 and len(family_shops[0].workers) < 3:
            self.join(p, family_shops[0])
            return
        masters = [w for w in self.wps if w.open and w.owner is not None and len(w.workers) < 3
                   and w.owner not in p.parents and w.owner != p.id and self.P(w.owner).here]
        if masters and rng.random() < 0.75:
            w = max(masters, key=lambda w: self.like[p.id, w.owner] + rng.uniform(-15, 15))
            m = self.P(w.owner)
            self.join(p, w)
            self.like[p.id, m.id] += 10
            self.like[m.id, p.id] += 10
            self.ev("apprentice", [p, m], f"{p.first} is apprenticed to {m.first}, the {w.trade}.")
            return
        self.give_work(p)

    def money_rules(self, people):
        rng = self.rng
        adults = [p for p in people if self.adult(p)]
        for p in adults:
            if (p.money < -15 and not self.open_debt(borrower=p)
                    and self.t - self.cooldown.get(("borrowed", p.id), -999) > 72):
                lenders = [l for l in adults if l is not p and l.money > 50 and self.like[l.id, p.id] > -10
                           and l.spouse != p.id and self.t - self.cooldown.get(("asked", p.id, l.id), -999) > 24]
                lenders.sort(key=lambda l: l.money + 2 * self.like[l.id, p.id], reverse=True)
                blow = self.recent(p.last_blow, 24)
                refuser = None
                if lenders:
                    l = lenders[0]
                    yes = 0.9 if l.has("kind") else (0.45 + self.like[l.id, p.id] / 100) * min(1.3, self.mood["money"])
                    if l.has("greedy"):
                        yes = 0.95
                    if rng.random() < yes:
                        amt = int(round((-p.money + 20) / 10.0)) * 10
                        amt = max(20, min(amt, 100, int(l.money * 0.6) // 10 * 10))
                        owed = int(amt * 1.5) if l.has("greedy") else amt
                        l.money -= amt
                        p.money += amt
                        extra = f", and must pay back {owed}" if owed > amt else ""
                        eid = self.ev("borrow", [p, l], f"{p.first} borrows {amt} silver from {l.first}{extra}.", [blow])
                        self.cooldown[("borrowed", p.id)] = self.t
                        self.debts.append({"l": l.id, "b": p.id, "owed": owed, "eid": eid, "t": self.t,
                                           "called": None, "called_t": None, "open": True})
                        continue
                    refuser = l
                    self.cooldown[("asked", p.id, l.id)] = self.t
                if self.t - p.last_hardtimes > 30:
                    p.last_hardtimes = self.t
                    why = f"; {refuser.first} won't lend" if refuser else "; nobody can lend"
                    how = "falls behind, working too little" if (p.has("lazy") and blow is None) else "falls on hard times"
                    if p.drink and blow is None:
                        how = "drinks away the takings"
                    eid = self.ev("hardtimes", [p] + ([refuser] if refuser else []), f"{p.first} {how}{why}.", [blow])
                    p.desperate = (eid, self.t)
                    if refuser:
                        self.hurt(p, refuser, 20, eid)

        for d in self.debts:
            if not d["open"]:
                continue
            l, b = self.P(d["l"]), self.P(d["b"])
            if not (l.here and b.here):
                continue
            age = self.t - d["t"]
            if (b.money > d["owed"] + 20 and not b.has("greedy")) or b.money > d["owed"] + 80:
                b.money -= d["owed"]
                l.money += d["owed"]
                d["open"] = False
                self.ev("repay", [b, l], f"{b.first} pays {l.first} back in full.", [d["called"] or d["eid"]])
                self.like[l.id, b.id] += 10
                continue
            blow = self.recent(b.last_blow, 8)
            if l.has("kind") and blow is not None and age > 6 and rng.random() < 0.05:
                d["open"] = False
                self.ev("forgive_debt", [l, b], f"{l.first} tells {b.first} to forget the {d['owed']} silver.", [d["eid"], blow])
                self.like[b.id, l.id] += 30
                continue
            if d["called"] is None and self.allowed("callin") and age >= 24 / self.mood["money"] and (l.money < 20 or (l.has("greedy") and age >= 36) or self.like[l.id, b.id] < -30):
                lent = f" {self.P(d['first_lender']).first} lent" if d.get("first_lender") is not None else ""
                cid = self.ev("callin", [l, b], f"{l.first} calls in the debt{lent}. {b.first} owes {d['owed']} and can't pay.",
                              [d["eid"], self.recent(l.last_blow, 18)])
                d["called"], d["called_t"] = cid, self.t
                b.desperate = (cid, self.t)
                b.last_blow = (cid, self.t)
                self.hurt(l, b, 25, cid)
                self.hurt(b, l, 15, cid)
            elif (d["called"] is not None and self.t - d["called_t"] >= 12 and (l.has("ambitious") or l.has("greedy"))
                  and b.wp is not None and self.wps[b.wp].owner == b.id and ("tookover", l.id) not in self.flags and self.allowed("takeover")):
                self.flags.add(("tookover", l.id))
                d["open"] = False
                w = self.wps[b.wp]
                place = self.wpname(w)
                w.owner = l.id
                w.workers.add(b.id)
                tid = self.ev("takeover", [l, b], f"{l.first} takes {place} to settle the debt. {b.first} now works it for {l.first}.", [d["called"]])
                self.hurt(b, l, 40, tid)
                b.last_blow = (tid, self.t)
                self.maybe_drink(b, tid)
                self.maybe_feud(b, l, tid)
            elif d["called"] is None and age > 48:
                self.like[l.id, b.id] -= 0.4

    def business(self, people):
        rng = self.rng
        for trade in TRADES:
            shops = self.owners_of(trade)
            for i in range(len(shops)):
                for j in range(i + 1, len(shops)):
                    a, b = self.P(shops[i].owner), self.P(shops[j].owner)
                    pair = frozenset((a.id, b.id))
                    if (a is b or pair in self.rivals or not (a.here and b.here) or self.kin(a, b) or a.spouse == b.id
                            or pair in self.courting or min(self.like[a.id, b.id], self.like[b.id, a.id]) > 40):
                        continue
                    pushy = [p for p in (a, b) if p.has("greedy") or p.has("ambitious") or p.has("proud")]
                    if pushy and self.allowed("rivalry") and rng.random() < 0.05 * self.boost("rivalry"):
                        x = pushy[0]
                        y = b if x is a else a
                        self.rivals.add(pair)
                        rid = self.ev("rivalry", [x, y], f"{x.first} undercuts {y.first}'s prices, and the two {trade}s become rivals.")
                        self.hurt(x, y, 20, rid)
                        self.hurt(y, x, 30, rid)
        for w in self.wps:
            if not w.open or w.owner is None:
                continue
            o = self.P(w.owner)
            if not o.here:
                continue
            if o.money < -90:
                w.open = False
                cause = self.recent(o.last_blow, 36) or self.recent(o.desperate, 36)
                cid = self.ev("closes", [o], f"{o.first} shuts the {w.place} for good.", [cause])
                for i in sorted(w.workers):
                    self.leave_wp(self.P(i))
                if o.wp == w.id:
                    self.leave_wp(o)
                o.last_blow = (cid, self.t)
                self.maybe_drink(o, cid)
                continue
            if o.has("ambitious") and o.money > 150 and len(w.workers) < 3:
                failing = [x for x in self.wps if x.open and x.owner is not None and x is not w
                           and self.P(x.owner).here and self.P(x.owner).money < -50 and not self.kin(o, self.P(x.owner))]
                if failing and self.allowed("buys") and rng.random() < 0.3:
                    x = failing[0]
                    seller = self.P(x.owner)
                    place = self.wpname(x)
                    x.owner = o.id
                    if seller.wp == x.id:
                        x.workers.add(seller.id)
                    o.money -= 80
                    seller.money += 80
                    bid = self.ev("buys", [o, seller], f"{o.first} buys {place}, which is failing. {seller.first} stays on to work it.",
                                  [self.recent(seller.last_blow, 36)])
                    self.hurt(seller, o, 15, bid)
                    continue
                idle = [p for p in people if self.adult(p) and p.worked and p.wp is None and p is not o]
                if idle and rng.random() < 0.3:
                    p = max(idle, key=lambda p: self.like[o.id, p.id])
                    self.join(p, w)
                    self.like[p.id, o.id] += 15
                    self.ev("hire", [o, p], f"{o.first} takes on {p.first} at the {w.place}.", [self.recent(p.last_blow, 36)])

    def crime(self, people):
        rng = self.rng
        adults = [p for p in people if self.adult(p)]
        for p in adults:
            if self.t - p.last_theft < 60:
                continue
            desperate = self.recent(p.desperate, 12)
            chance = (0.002 if p.has("greedy") else 0) + (0.0015 if p.has("sly") else 0) + (0.02 if desperate is not None else 0)
            chance += 0.002 if p.drink else 0
            chance *= 0.1 if p.has("honest") else 1
            chance *= self.mood["crime"] * THEFT_BASE * self.boost("theft")
            if not self.allowed("theft") or rng.random() > chance:
                continue
            targets = [x for x in adults if x is not p and x.id != p.spouse and x.money > 30
                       and ("robbed", p.id, x.id) not in self.flags and (not self.kin(p, x) or self.like[p.id, x.id] < 0)]
            if not targets:
                continue
            weights = [x.money * (1 + max(0, -self.like[p.id, x.id]) / 30) for x in targets]
            v = rng.choices(targets, weights)[0]
            amt = max(15, min(80, int(v.money * 0.35)))
            v.money -= amt
            p.money += amt
            p.last_theft = self.t
            self.flags.add(("robbed", p.id, v.id))
            if v.wp is not None and self.wps[v.wp].owner == v.id:
                where = self.wpname(self.wps[v.wp])
            elif v.wp is not None:
                where = f"{v.first} at {self.wpname(self.wps[v.wp])}"
            else:
                where = f"{v.first}'s house"
            tid = self.ev("theft", [p, v], f"{p.first} steals {amt} silver from {where}.", [desperate], secret=True)
            v.last_blow = (tid, self.t)
            self.witness(p, v, tid, people, "theft")

    def witness(self, doer, victim, eid, people, kind):
        """Someone may have seen it."""
        rng = self.rng
        seen = None
        for w in people:
            if w in (doer, victim) or not w.here:
                continue
            if w.house == doer.house:
                chance = 0.3
            elif victim.wp is not None and w.wp == victim.wp:
                chance = 0.12
            else:
                chance = 0.006
            if rng.random() < chance:
                seen = w
                break
        if seen:
            w = seen
            child = not self.adult(w)
            if w.id == doer.spouse or doer.id in w.parents:
                tells = self.like[w.id, doer.id] < -20 and not child
            else:
                tells = ((w.has("honest") and self.like[w.id, doer.id] < 60) or self.like[w.id, doer.id] < 0
                         or (self.like[w.id, victim.id] > 50 and self.like[w.id, doer.id] < 30))
            if tells:
                if kind == "killing":
                    xid = self.ev("exposed", [w, doer, victim], f"{w.first} saw {doer.first} kill {victim.first}, and tells everyone.", [eid])
                    self.leave_town(doer)
                    self.ev("exiled", [doer], f"{doer.first} is driven out of town for killing {victim.first}.", [xid])
                    self.after_leaving(doer)
                else:
                    xid = self.ev("exposed", [w, doer, victim], f"{w.first} saw it and tells {victim.first}." +
                                  (f" {doer.first} has to give it back." if kind == "theft" else f" {doer.first} has to pay for the damage."), [eid])
                    self.hurt(victim, doer, 50, xid)
                    self.hurt(doer, w, 40, xid)
                    self.maybe_feud(victim, doer, xid)
                return xid
            age = f" (only {int(self.age(w))})" if child else ""
            sid = self.ev("silence", [w, doer], f"{w.first}{age} saw {doer.first} do it, and says nothing.", [eid], secret=True)
            self.add_secret({"eid": eid, "kind": kind, "keepers": {doer.id, w.id}, "doer": doer.id,
                                 "victim": victim.id, "open": True, "witness": w.id, "witness_eid": sid})
        else:
            self.add_secret({"eid": eid, "kind": kind, "keepers": {doer.id}, "doer": doer.id, "victim": victim.id, "open": True})
        self.blame(victim, doer, eid, people, kind)
        return None

    def blame(self, victim, doer, eid, people, kind):
        rng = self.rng
        holder = victim
        if not victim.here:  # killed: the family blames someone
            kin = [self.P(i) for i in ([victim.spouse] if victim.spouse is not None else []) + victim.children + victim.parents]
            kin = [k for k in kin if k.here and self.adult(k) and k is not doer]
            if not kin:
                return
            holder = kin[0]
        suspects = [x for x in people if x.here and x is not holder and x is not victim and self.adult(x)
                    and x.id != holder.spouse and not self.kin(holder, x)]
        if not suspects:
            return
        s = min(suspects, key=lambda x: self.like[holder.id, x.id] + rng.uniform(-12, 12))
        what = {"theft": "for the missing silver", "sabotage": "for the damage", "killing": f"for {victim.first}'s death"}[kind]
        bid = self.ev("blame", [holder, s], f"{holder.first} blames {s.first} {what}.", [eid])
        self.beliefs.append({"holder": holder.id, "about": eid, "kind": kind, "suspect": s.id, "doer": doer.id,
                             "victim": victim.id, "wrong": s is not doer, "eid": bid, "open": True})
        self.hurt(holder, s, 35 if kind != "killing" else 70, bid)
        if s is not doer and s.has("hot-headed") and rng.random() < 0.5:
            fid = self.ev("fight", [s, holder], f"{s.first} won't stand for being called a thief, and hits {holder.first}.", [bid])
            self.hurt(holder, s, 20, fid)
        elif s is not doer and s.has("proud") and rng.random() < 0.5:
            self.maybe_feud(s, holder, bid, 1.0)
        if kind == "killing":
            self.maybe_feud(holder, s, bid, 0.8)
        if s is not doer:
            self.hurt(s, holder, 25, bid)

    def add_secret(self, sec):
        sec["knew"] = sorted(sec["keepers"])  # who knew it when it happened; keepers shrinks as they die or leave
        self.secrets.append(sec)

    def close_secret(self, eid):
        for s in self.secrets:
            if s["eid"] == eid:
                s["open"] = False

    def reveal(self, sec, eid):
        self.close_secret(sec["eid"])
        doer = self.P(sec["doer"])
        if sec["kind"] in ("theft", "sabotage", "killing"):
            v = self.P(sec["victim"])
            for b in self.beliefs:
                if b["open"] and b["about"] == sec["eid"]:
                    b["open"] = False
                    h = self.P(b["holder"])
                    if h.here and h is not doer:
                        self.hurt(h, doer, 50, eid)
                        self.maybe_feud(h, doer, eid, 0.25)
                        if b["wrong"]:
                            s = self.P(b["suspect"])
                            self.like[h.id, s.id] += 35
                            self.grudge.pop((h.id, s.id), None)
                            if s.here:
                                self.ev("peace", [h, s], f"{h.first} realises {s.first} was innocent all along.", [eid, b["eid"]])
            if v.here:
                self.hurt(v, doer, 50, eid)
            if sec["kind"] == "killing" and doer.here:
                self.leave_town(doer)
                self.ev("exiled", [doer], f"{doer.first} is driven out of town for killing {v.first}.", [eid])
                self.after_leaving(doer)
        elif sec["kind"] == "parentage":
            h, m = self.P(sec["victim"]), self.P(sec["father"])
            if h.here:
                self.hurt(h, doer, 60, eid)
                self.hurt(h, m, 70, eid)
                self.maybe_drink(h, eid)
                self.maybe_feud(h, m, eid, 0.6)

    def secrets_rules(self, people):
        rng = self.rng
        for sec in self.secrets:
            if not sec["open"]:
                continue
            doer = self.P(sec["doer"])
            for kid in sorted(sec["keepers"]):
                k = self.P(kid)
                if not k.here:
                    continue
                if k is not doer and sec["kind"] in ("theft", "sabotage", "killing", "parentage"):
                    friendly = self.like[k.id, doer.id] > 40
                    chance = 0.003 * (6 if k.has("gossipy") else 1) * (0.3 if friendly else 1) * (4 if self.like[k.id, doer.id] < -30 else 1)
                    if rng.random() < chance:
                        eid = self.ev("slip", [k, doer] + ([self.P(sec["victim"])] if sec.get("victim") is not None else []),
                                      self.slip_text(k, doer, sec), [sec.get("witness_eid"), sec["eid"]])
                        self.hurt(doer, k, 40, eid)
                        self.reveal(sec, eid)
                        break
                    if ((k.has("greedy") or k.has("sly")) and self.adult(k) and doer.here
                            and ("blackmail", k.id) not in self.flags and self.allowed("blackmail") and rng.random() < 0.01 * self.boost("blackmail")):
                        self.flags.add(("blackmail", k.id))
                        bid = self.ev("blackmail", [k, doer], f"{k.first} makes {doer.first} pay to keep quiet.",
                                      [sec.get("witness_eid") or sec["eid"]], secret=True)
                        self.blackmails.append({"x": k.id, "y": doer.id, "eid": bid, "sec": sec, "open": True})
                elif k is doer and sec["kind"] == "theft" and (k.has("honest") or k.has("kind")) and rng.random() < 0.003:
                    v = self.P(sec["victim"])
                    if v.here:
                        eid = self.ev("confess", [k, v], f"Guilt wins. {k.first} confesses to {v.first} about the stolen silver.", [sec["eid"]])
                        self.reveal(sec, eid)
                        self.like[v.id, k.id] += 25
                        break
        for bm in self.blackmails:
            if not bm["open"]:
                continue
            x, y = self.P(bm["x"]), self.P(bm["y"])
            if not (x.here and y.here) or not bm["sec"]["open"]:
                bm["open"] = False
                continue
            y.money -= 4
            x.money += 4
            self.like[y.id, x.id] -= 1.5
            if y.money < -40 and rng.random() < 0.05 and not (y.has("hot-headed") or y.has("proud")):
                bm["open"] = False
                eid = self.ev("slip", [x, y], f"{y.first} stops paying, and {x.first} tells the town what {y.first} did.", [bm["eid"], bm["sec"]["eid"]])
                self.reveal(bm["sec"], eid)

    def slip_text(self, k, doer, sec):
        friend = "Though they're friends, " if doer.id in k.friends else ""
        who = f"{friend}{k.first}"
        if sec["kind"] == "parentage":
            return f"{who} lets slip that {self.P(sec['father']).first} is {self.P(sec['child']).first}'s real father."
        v = self.P(sec["victim"])
        what = {"theft": f"robbed {v.first}", "sabotage": f"wrecked {v.first}'s place", "killing": f"killed {v.first}"}[sec["kind"]]
        return f"{who} lets slip that {doer.first} {what}."

    def conflict(self, people, quarter):
        rng = self.rng
        adults = [p for p in people if self.adult(p) and p.here]
        for a in adults:
            if not a.here:
                continue
            for b in adults:
                if a is b or not b.here:
                    continue
                lk = self.like[a.id, b.id]
                if lk > -50:
                    continue
                if (a.has("hot-headed") or a.has("proud") or a.drink or lk < -70) and self.allowed("fight"):
                    key = ("fights", min(a.id, b.id), max(a.id, b.id))
                    if self.cooldown.get(key, 0) < 2 and rng.random() < 0.015 * self.mood["temper"] * self.boost("fight") and self.ready(("fight",) + key[1:], 48):
                        self.cooldown[key] = self.cooldown.get(key, 0) + 1
                        place = rng.choice(["at the tavern", "in the market", "by the well", "in the street"])
                        eid = self.ev("fight", [a, b], f"{a.first} and {b.first} come to blows {place}.", [self.grudge.get((a.id, b.id))])
                        self.hurt(a, b, 10, eid)
                        self.hurt(b, a, 10, eid)
                if (lk < -60 and (a.has("sly") or a.has("hot-headed")) and b.wp is not None and self.wps[b.wp].owner == b.id
                        and self.t - self.cooldown.get(("sabotage", a.id), -999) > 72 and self.allowed("sabotage") and rng.random() < 0.01 * self.boost("sabotage")):
                    self.cooldown[("sabotage", a.id)] = self.t
                    w = self.wps[b.wp]
                    sid = self.ev("sabotage", [a, b], f"{a.first} wrecks {self.wpname(w)} in the night.", [self.grudge.get((a.id, b.id))], secret=True)
                    b.money -= 40
                    b.last_blow = (sid, self.t)
                    self.witness(a, b, sid, self.here(), "sabotage")
                    continue
                blackmailed = any(bm["open"] and bm["x"] == b.id and bm["y"] == a.id for bm in self.blackmails)
                if (lk < -85 and (a.has("hot-headed") or a.drink or blackmailed) and "killing" not in self.flags
                        and rng.random() < 0.004):
                    self.flags.add("killing")
                    place = rng.choice(["on the river path", "behind the tavern", "in the woods", "on the road out of town"])
                    why = [self.grudge.get((a.id, b.id))] + [bm["eid"] for bm in self.blackmails if bm["x"] == b.id and bm["y"] == a.id]
                    kid = self.ev("killing", [a, b], f"{a.first} kills {b.first} {place}.", why, secret=True)
                    self.die(b, f"is found dead {place}", [kid], kind="found")
                    self.witness(a, b, kid, self.here(), "killing")
        if quarter:
            pairs = {}
            for a in adults:
                for b in adults:
                    if a.surname < b.surname and self.like[a.id, b.id] < -50 and self.like[b.id, a.id] < -50:
                        pairs.setdefault((a.surname, b.surname), []).append((a, b))
            for (x, y), lst in pairs.items():
                key = frozenset((x, y))
                kin_here = all(any(q.here and q is not p and (self.kin(p, q) or q.spouse == p.id) for q in self.people)
                               for p in lst[0])
                if (len(lst) >= 2 or (kin_here and rng.random() < 0.15 * self.boost("feud"))) and key not in self.feuds and ("feud", key) not in self.flags and self.allowed("feud"):
                    self.flags.add(("feud", key))
                    causes = [self.grudge.get((a.id, b.id)) or self.grudge.get((b.id, a.id)) for a, b in lst]
                    actors = [p for ab in lst for p in ab]
                    self.feuds[key] = self.ev("feud", actors, f"Bad blood between the {x}s and the {y}s: the two families stop speaking.", causes)

    def maybe_drink(self, p, cause):
        if not p.here or p.drink or p.has("kind") or p.has("forgiving") or not self.adult(p) or not self.allowed("drink"):
            return
        if self.rng.random() < min(0.9, 0.25 * self.boost("drink")):
            p.drink = True
            self.ev("drink", [p], f"{p.first} takes to drink.", [cause])

    def die(self, p, how, causes, kind="death"):
        p.alive = False
        p.died = self.t
        text = f"{p.first} {how}"
        mourner = None
        if p.spouse is not None:
            s = self.P(p.spouse)
            text += f", leaving {s.first} {'a widow' if s.sex == 'F' else 'a widower'}"
            mourner = s
            s.spouse = None
        buried = self.settle(p, "died")
        if buried:
            text += ", and takes " + ("a secret" if len(buried) == 1 else f"{len(buried)} secrets") + " to the grave"
            causes = list(causes) + buried
        did = self.ev(kind, [p], text + ".", causes)
        p.exit_eid = did
        for q in [mourner] + [self.P(i) for i in p.parents + p.children]:
            if q is not None:
                self.maybe_drink(q, did)
        for d in self.debts:
            if not d["open"] or p.id not in (d["b"], d["l"]):
                continue
            heir = self.heir(p)
            other = self.P(d["l"] if d["b"] == p.id else d["b"])
            if heir and heir is not other and other.here:
                if d["b"] == p.id:
                    d["b"] = heir.id
                    self.ev("inherit", [heir, other], f"{heir.first} inherits {p.first}'s debt of {d['owed']} to {other.first}.", [did, d["eid"]])
                else:
                    d.setdefault("first_lender", p.id)
                    d["l"] = heir.id
            else:
                d["open"] = False
                d["ended"] = "died"
        self.hand_on(p, did)
        self.place_children(self.house_kids(p), p, did)

    def heir(self, p):
        kids = [self.P(i) for i in p.children if self.P(i).here and self.adult(self.P(i))]
        if kids:
            return kids[0]
        for q in self.here():
            if frozenset((p.id, q.id)) in self.siblings:
                return q
        for q in self.here():
            if q.house == p.house and q.id != p.id and self.adult(q):
                return q
        return None

    def mortality(self, people):
        rng = self.rng
        for p in people:
            if not p.here:
                continue
            a = self.age(p)
            sick = self.t < p.sick_until
            chance = 0.00008 if a < 16 else 0.00012 + max(0.0, a - 45) * 0.00035
            if sick:
                chance += 0.05 if a < 10 else 0.03
            if p.drink:
                chance += 0.0004
            if rng.random() > chance:
                continue
            if sick:
                how = "dies of the fever"
            elif a < 16:
                how = rng.choice(["drowns in the river", "dies of a winter cough"])
            elif a > 55:
                how = rng.choice([f"dies in {'his' if p.sex == 'M' else 'her'} sleep", "dies after a long cough", "dies of a bad heart"])
            elif p.drink:
                how = f"drinks {'himself' if p.sex == 'M' else 'herself'} to death"
            else:
                how = rng.choice(["dies of a wound gone bad", "dies in a fall", "drowns in the river"])
            self.die(p, how, [p.sick_cause if sick else None])

    def hand_on(self, p, did=None):
        """p is dead or gone: every place they own passes to an heir or shuts."""
        for w in [w for w in self.wps if w.open and w.owner == p.id]:
            place = self.wpname(w)
            mourner = self.P(p.spouse) if p.spouse is not None else None
            kids = [self.P(i) for i in p.children if self.P(i).here and self.adult(self.P(i))]
            cands = ([k for k in kids if k.wp == w.id] + ([mourner] if mourner and mourner.here and mourner.wp == w.id else [])
                     + [self.P(i) for i in sorted(w.workers) if self.P(i).here and self.P(i) is not p]
                     + (kids if did is not None else []))
            w.owner = None
            if cands:
                h = cands[0]
                self.own(h, w)
                self.ev("inherit_wp", [h, p], f"{h.first} takes over {place}.", [did if did is not None else p.exit_eid])
            else:
                w.open = False
                for i in sorted(w.workers):
                    self.leave_wp(self.P(i))
                self.ev("closes", [p], f"With {p.first} gone, the {w.place} shuts.", [did if did is not None else p.exit_eid])
        self.leave_wp(p)

    def settle(self, p, how):
        """Loose ends when p dies or leaves: secrets they kept, beliefs they held, affairs and courtships."""
        buried = []
        for sec in self.secrets:
            if sec["open"] and p.id in sec["keepers"]:
                sec["keepers"].discard(p.id)
                if not sec["keepers"]:
                    sec["open"] = False
                    sec["ended"] = how
                    buried.append(sec["eid"])
        for b in self.beliefs:
            if b["open"] and b["holder"] == p.id:
                b["open"] = False
        for pair in list(self.affairs):
            if p.id in pair:
                self.affairs.pop(pair)
        for pair in list(self.courting):
            if p.id in pair:
                self.courting.pop(pair)
        return buried

    def leave_town(self, *ps):
        """ps leave together. Anyone they leave behind is dealt with once they're all gone."""
        for p in ps:
            p.gone = True
            p.left = self.t
            p.exit_eid = len(self.events)  # the leaving event comes next
        for p in ps:
            self.settle(p, "left")
            for d in self.debts:
                if d["open"] and p.id in (d["b"], d["l"]):
                    d["open"] = False
                    d["ended"] = "left"
                    other = self.P(d["l"] if d["b"] == p.id else d["b"])
                    if d["b"] == p.id and other.here:
                        self.hurt(other, p, 30, d["eid"])
            if p.spouse is not None and self.P(p.spouse).here:
                self.P(p.spouse).spouse = None

    def after_leaving(self, *ps):
        """Call once the leaving event is written: their shops pass on, and children left with no grown-up get placed."""
        for p in ps:
            self.hand_on(p)
        for p in ps:
            self.place_children(self.house_kids(p), p, p.exit_eid)

    def house_kids(self, p):
        """p's own children under 16, and any other child under 16 in p's house."""
        out = [self.P(c) for c in p.children if self.P(c).here and not self.adult(self.P(c))]
        out += [k for k in self.people if k.here and not self.adult(k) and k.house == p.house and k not in out]
        return out

    def place_children(self, kids, p, cause):
        """Children under 16 whose house has no grown-up left go to the other parent, a grown sibling,
        or someone who cares about the family. If nobody can, they're sent to kin in another town."""
        kids = [k for k in kids if k.here and not any(
            q.here and self.adult(q) and q.house == k.house for q in self.people)]
        for k in list(kids):
            other = [self.P(i) for i in k.parents if self.P(i).here and self.adult(self.P(i))]
            if other:
                k.house = other[0].house
                kids.remove(k)
        if not kids:
            return
        sibs = [self.P(i) for i in p.children if self.P(i).here and self.adult(self.P(i))]
        carers = sibs or [q for q in self.here() if self.adult(q) and (q.has("kind") or self.like[q.id, p.id] > 40)]
        verb = "orphaned" if not p.alive else "abandoned"
        if carers:
            c = max(carers, key=lambda q: self.like[q.id, p.id])
            for k in kids:
                k.house = c.house
            self.ev("adopt", [c] + kids, f"{c.first} takes in {p.first}'s {verb} {'child' if len(kids) == 1 else 'children'}, {self.names(kids)}.", [cause])
        else:
            for k in kids:
                k.gone = True
                k.left = self.t
                k.exit_eid = len(self.events)
                self.settle(k, "left")
            self.ev("leaves", kids, f"With nobody to take them in, {self.names(kids)} {'is' if len(kids) == 1 else 'are'} sent to kin in another town.", [cause])

    def moving(self, people):
        rng = self.rng
        adults = [p for p in people if self.adult(p) and p.here]
        for p in adults:
            if not p.here:
                continue
            enemies = [x for x in adults if x is not p and x.here and self.like[x.id, p.id] < -40]
            boss = None
            if p.wp is not None and self.wps[p.wp].owner not in (None, p.id):
                boss = self.P(self.wps[p.wp].owner)
            if (len(enemies) >= 3 or (boss and self.like[p.id, boss.id] < -50)) and rng.random() < 0.025:
                d = self.open_debt(borrower=p)
                text = f"{p.first} packs up and leaves town"
                causes = [self.grudge.get((x.id, p.id)) for x in enemies[:3]]
                if boss:
                    causes.append(self.grudge.get((p.id, boss.id)))
                actors = [p]
                if d:
                    l = self.P(d["l"])
                    text += f", still owing {l.first} {d['owed']}"
                    d["open"] = False
                    self.hurt(l, p, 30, None)
                    actors.append(l)
                family = []
                if p.spouse is not None:
                    s = self.P(p.spouse)
                    if self.like[s.id, p.id] > 0:
                        family.append(s)
                    else:
                        text += f", leaving {s.first} behind"
                        actors.append(s)
                        s.spouse = p.spouse = None
                family += self.kids_home(p)
                if family:
                    text += f", taking {self.names(family)}"
                self.leave_town(p, *family)
                self.ev("leaves", actors + family, text + ".", causes)
                self.after_leaving(p, *family)
        here = self.here()
        grown = [p for p in here if self.adult(p)]
        if (len(grown) < self.target * 0.6 or len(here) < self.target * 0.85) and rng.random() < 0.35:
            sn = self.surname()
            if rng.random() < 0.6:
                a = self.add_person(rng.choice("FM"), sn, rng.randint(18, 38))
                a.house = self.new_house()
                a.money = rng.randint(10, 40)
                a.arrived = self.t
                self.give_work(a)
                self.ev("arrival", [a], f"{a.first} {sn}, a {a.trade or 'labourer'}, moves to town.")
            else:
                h = self.add_person("M", sn, rng.randint(22, 40))
                w = self.add_person("F", sn, max(18, self.age(h) + rng.randint(-6, 3)))
                self.wed(h, w)
                for p in (h, w):
                    p.money = rng.randint(10, 40)
                    p.arrived = self.t
                self.give_work(h)
                w.worked = True
                self.ev("arrival", [h, w], f"{h.first} and {w.first} {sn} move to town. {h.first} is a {h.trade or 'labourer'}.")

    # ---------- the day the player arrives ----------
    def present(self):
        out = []
        for p in self.people:
            w = self.wps[p.wp] if p.wp is not None else None
            role = ("owner" if w.owner == p.id else "worker") if w else None
            out.append({
                "id": p.id, "name": p.first if p.first != p.given else f"{p.given} {p.surname}", "first": p.first, "surname": p.surname, "sex": p.sex,
                "traits": p.traits, "born": p.birth_t, "age": int(self.age(p)),
                "status": "alive" if p.here else ("left town" if p.gone else "dead"),
                "died_year": (p.died // 12 + 1) if p.died is not None else None,
                "left_year": (p.left // 12 + 1) if p.left is not None else None,
                "arrived_year": (p.arrived // 12 + 1) if p.arrived is not None else None,
                "parents": p.parents, "children": p.children, "spouse": p.spouse, "house": p.house,
                "job": (w.trade if w else ("labourer" if self.adult(p) else "child")) if p.here else (p.trade or ""),
                "workplace": self.wpname(w) if w else None, "role": role, "drink": p.drink, "money": int(p.money),
                "goal": self.goal(p) if p.here else None,
                "hides": list(dict.fromkeys(self.hides(p))) if p.here else [],
                "believes": [self.belief_text(b) for b in self.beliefs if b["open"] and b["holder"] == p.id] if p.here else [],
            })
        return out

    def belief_text(self, b):
        s = self.P(b["suspect"])
        what = {"theft": "stole from them", "sabotage": "wrecked their place",
                "killing": f"killed {self.P(b['victim']).first}"}[b["kind"]]
        if b["wrong"]:
            return f"Is sure {s.first} {what}. Wrong: it was {self.P(b['doer']).first}."
        return f"Is sure {s.first} {what}, and is right, but can't prove it."

    def hides(self, p):
        out = []
        for sec in self.secrets:
            if not sec["open"] or p.id not in sec["keepers"]:
                continue
            doer = self.P(sec["doer"])
            v = self.P(sec["victim"]) if sec.get("victim") is not None else None
            if sec["kind"] in ("theft", "sabotage", "killing"):
                verb = {"theft": "robbed", "sabotage": "wrecked the place of", "killing": "killed"}[sec["kind"]]
                seen = {"theft": "rob", "sabotage": "wreck the place of", "killing": "kill"}[sec["kind"]]
                out.append(f"{cap(verb)} {v.first}." if doer is p else f"Saw {doer.first} {seen} {v.first}, and never told.")
            elif sec["kind"] == "affair":
                other = [self.P(i) for i in self.events[sec["eid"]]["actors"] if i != p.id]
                if other:
                    out.append(f"An affair with {other[0].first}.")
            elif sec["kind"] == "love":
                out.append(f"Loves {v.first}." if v.here else f"Loved {v.first}, who {'died' if not v.alive else 'left'} never knowing.")
            elif sec["kind"] == "parentage":
                c, m = self.P(sec["child"]), self.P(sec["father"])
                out.append(f"Is {c.first}'s real father." if p.id == m.id else f"{m.first} is {c.first}'s real father.")
        for bm in self.blackmails:
            if bm["open"] and bm["x"] == p.id:
                out.append(f"Blackmails {self.P(bm['y']).first}.")
            if bm["open"] and bm["y"] == p.id:
                out.append(f"Pays {self.P(bm['x']).first} to keep quiet.")
        return out

    def goal(self, p):
        if not self.adult(p):
            return "Grow up."
        d = self.open_debt(borrower=p)
        if d and d["called"]:
            return f"Find {d['owed']} silver before {self.P(d['l']).first} takes everything."
        for bm in self.blackmails:
            if bm["open"] and bm["y"] == p.id:
                return f"Get free of {self.P(bm['x']).first}'s blackmail."
        for b in self.beliefs:
            if b["open"] and b["holder"] == p.id and b["kind"] == "killing":
                return f"Make {self.P(b['suspect']).first} pay for {self.P(b['victim']).first}'s death."
        if d:
            return f"Pay back the {d['owed']} owed to {self.P(d['l']).first}."
        for pair in self.affairs:
            if p.id in pair:
                return f"Keep the affair with {self.P(next(i for i in pair if i != p.id)).first} hidden."
        for sec in self.secrets:
            if (sec["open"] and p.id in sec["keepers"] and sec["doer"] != p.id and sec.get("victim") is not None
                    and sec["kind"] != "love" and self.P(sec["victim"]).here):
                return f"Decide whether to tell {self.P(sec['victim']).first} what {self.P(sec['doer']).first} did."
        for b in self.beliefs:
            if b["open"] and b["holder"] == p.id:
                return f"Prove {self.P(b['suspect']).first} is guilty."
        if p.wp is not None and self.wps[p.wp].owner not in (None, p.id) and self.like[p.id, self.wps[p.wp].owner] < -30:
            return f"Win back the {self.wps[p.wp].place} from {self.P(self.wps[p.wp].owner).first}."
        for pair, c in self.courting.items():
            if p.id in pair and c.get("forbid"):
                return f"Marry {self.P(next(i for i in pair if i != p.id)).first}, whatever {self.P(c['forbid'][1]).first} says."
        here = [q for q in self.here() if q is not p]
        loved = [q for q in here if self.love[p.id, q.id] >= 60 and p.spouse != q.id and self.adult(q)]
        if loved:
            q = max(loved, key=lambda q: self.love[p.id, q.id])
            return f"Win {q.first}" + (f" away from {self.P(q.spouse).first}." if q.spouse is not None else ".")
        hated = [q for q in here if self.like[p.id, q.id] < -45 and self.adult(q)]
        if hated:
            return f"Get even with {min(hated, key=lambda q: self.like[p.id, q.id]).first}."
        if p.drink:
            return "Get through the day."
        if any(sec["kind"] in ("theft", "sabotage") and sec["doer"] == p.id and sec["open"] for sec in self.secrets):
            return "Keep the past buried."
        if p.has("ambitious"):
            return "Build the best business in town."
        if p.has("greedy"):
            return "Get richer than anyone in town."
        if self.kids_home(p):
            return f"See {self.names(self.kids_home(p))} grow up well."
        return "A quiet life."

    def temperament(self):
        common = [t for t, w in self.trait_w.items() if w >= 3]
        rare = [t for t, w in self.trait_w.items() if w <= 0.25]
        loud = [k for k, v in self.mood.items() if v > 2]
        quiet = [k for k, v in self.mood.items() if v < 0.5]
        return {"common": common, "rare": rare, "loud": loud, "quiet": quiet, "off": sorted(self.off),
                "featured": sorted(self.featured)}

    def stories(self):
        """Connected cause chains, biggest first: what a player could stumble into."""
        parent = {e["id"]: e["id"] for e in self.events}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for e in self.events:
            for c in e["causes"]:
                if self.events[c]["kind"] in ("harvest", "fever"):
                    continue  # town-wide bad luck shouldn't glue unrelated stories together
                parent[find(e["id"])] = find(c)
        groups = {}
        for e in self.events:
            groups.setdefault(find(e["id"]), []).append(e["id"])
        out = []
        for ids in groups.values():
            if len(ids) < 4:
                continue
            idset = set(ids)
            people = sorted({a for i in ids for a in self.events[i]["actors"]})
            open_n = (sum(1 for s in self.secrets if s["open"] and (s["eid"] in idset or s.get("witness_eid") in idset))
                      + sum(1 for b in self.beliefs if b["open"] and b["eid"] in idset))
            counts = {}
            for i in ids:
                counts[self.events[i]["kind"]] = counts.get(self.events[i]["kind"], 0) + 1
            out.append({"events": sorted(ids), "people": people, "open": open_n,
                        "kinds": sorted(counts, key=lambda k: -counts[k])[:5]})
        out.sort(key=lambda s: -(len(s["events"]) + 3 * s["open"]))
        return out

    def score(self):
        tensions = (2 * sum(1 for s in self.secrets if s["open"])
                    + sum(1 for d in self.debts if d["open"])
                    + 2 * sum(1 for b in self.beliefs if b["open"] and b["wrong"])
                    + sum(1 for bm in self.blackmails if bm["open"]) + len(self.feuds))
        involved = set()
        for e in self.events:
            if len(e["actors"]) >= 2 and e["group"] != "hardship" and e["kind"] not in ("birth", "family"):
                involved.update(e["actors"])
        grown = [p for p in self.people if (min(self.t, p.died if p.died is not None else self.t) - p.birth_t) >= 192]
        depth = {}
        for e in self.events:
            depth[e["id"]] = 1 + max((depth[c] for c in e["causes"]), default=0)
        kinds = {}
        for e in self.events:
            if e["kind"] not in ("birth", "family"):
                kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        story_events = sum(kinds.values())
        return {
            "events": len(self.events), "story_events": story_events, "tensions": tensions,
            "involved": round(len(involved & {p.id for p in grown}) / max(1, len(grown)), 2),
            "longest_chain": max(depth.values(), default=0), "groups": len({e["group"] for e in self.events}),
            "kinds_used": len(kinds), "top_kind_share": round(max(kinds.values(), default=0) / max(1, story_events), 2),
            "people_ever": len(self.people), "people_now": len(self.here()),
        }


def cap(s):
    return s[:1].upper() + s[1:]


def good(sc):
    return (sc["tensions"] >= 10 and sc["involved"] >= 0.55 and sc["longest_chain"] >= 5
            and sc["groups"] >= 7 and sc["top_kind_share"] <= 0.16 and sc["kinds_used"] >= 22)


def closeness(sc):
    """How near a town comes to passing: the number of checks it passes, then its tensions."""
    checks = [sc["tensions"] >= 10, sc["involved"] >= 0.55, sc["longest_chain"] >= 5,
              sc["groups"] >= 7, sc["top_kind_share"] <= 0.16, sc["kinds_used"] >= 22]
    return (sum(checks), sc["tensions"])


def run_world(seed, n=40, years=25, each_month=None):
    w = World(seed, n, years)
    for _ in range(years * 12):
        w.step()
        if each_month:
            each_month(w)
    return w


def build(seed, n=40, years=25, max_tries=60):
    best = None
    for attempt in range(max_tries):
        w = run_world(seed * 1000 + attempt, n, years)
        sc = w.score()
        if good(sc):
            return w, attempt
        if best is None or closeness(sc) > closeness(best[0].score()):
            best = (w, attempt)
    return best[0], max_tries


def chronicle(w):
    lines = []
    for e in w.events:
        why = ""
        if e["causes"]:
            why = "  <- " + "; ".join(w.events[c]["text"].rstrip(".") for c in e["causes"])
        mark = " [secret]" if e["secret"] else ""
        lines.append(f"Y{e['year']:>2} {e['season'][:3]}: {e['text']}{mark}{why}")
    return lines


def sameness_steps(out):
    """The measurement history for the page: earlier steps plus the final run, if present."""
    steps = []
    try:
        with open(os.path.join(out, "sameness_steps.json"), encoding="utf-8") as f:
            steps = json.load(f)
        with open(os.path.join(out, "sameness_final.json"), encoding="utf-8") as f:
            fin = json.load(f)
        steps.append({"label": "A director for each town, final rules", "note": "a third of story types switched off; the checks' fixes",
                      **{k: fin[k] for k in ("keep_rate", "shapes_per_town", "overlap")}, "top": fin["top"]})
    except OSError:
        return None
    return steps


def remembers(w, m, p, n=4):
    """A person's top few memories, worded for the page."""
    out = []
    for x in m.memories_of(p)[:n]:
        e = m.events[x.eid]
        if x.partial:
            out.append(f"Year {e['year']}: " + {"theft": "was robbed, and doesn't know who did it.",
                                                "sabotage": "had their place wrecked, and doesn't know who did it."}.get(e["kind"], e["text"]))
        elif x.how in ("did", "was there"):
            out.append(f"Year {e['year']}: {e['text']}")
        elif x.how == "saw":
            out.append(f"Saw it, year {e['year']}: {e['text']}")
        elif x.how == "victim":
            out.append(f"Year {e['year']}: {e['text']}")
        elif x.src is not None:
            out.append(f"Heard from {w.P(x.src).first}: {e['text']}")
        else:
            out.append(f"Heard: {e['text']}")
    return out


def robust_summary(out):
    """What the checks, stress tests and gossip test found, for the page."""
    def load(name):
        try:
            with open(os.path.join(out, name), encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return None
    return {"check": load("check_1000.json"), "stress": load("stress.json"), "minds": load("minds.json"),
            "same": load("sameness_final.json")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--people", type=int, default=40)
    ap.add_argument("--years", type=int, default=25)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    args = ap.parse_args()
    import minds as M
    towns = []
    for seed in args.seeds:
        w, rerolls = build(seed, args.people, args.years)
        sc = w.score()
        m = M.Minds(w, seed)
        m.replay()
        print(f"\n=== Town seed {seed} (re-rolled {rerolls}) {sc}")
        if not args.quiet:
            for line in chronicle(w):
                print("  " + line)
        people = w.present()
        for row, p in zip(people, w.people):
            row["remembers"] = remembers(w, m, p) if p.here else []
        towns.append({"seed": seed, "rerolls": rerolls, "score": sc, "years": args.years,
                      "people": people, "events": w.events, "stories": w.stories(), "temperament": w.temperament()})
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "towns40.json"), "w", encoding="utf-8") as f:
        json.dump(towns, f)
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page_template.html")
    if os.path.exists(tpl):
        with open(tpl, encoding="utf-8") as f:
            html = (f.read().replace("/*TOWNS*/null", json.dumps(towns))
                    .replace("/*SAME*/null", json.dumps(sameness_steps(args.out)))
                    .replace("/*ROBUST*/null", json.dumps(robust_summary(args.out))))
        with open(os.path.join(args.out, "town40.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nWrote {os.path.join(args.out, 'town40.html')}")


if __name__ == "__main__":
    main()
