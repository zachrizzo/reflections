"""Throwaway spike: generate a tiny town's history and show how lives intertwine.

NOT game code. The rules and numbers are placeholders, made to judge whether
rule-driven histories read like stories (ArtDirection/NpcBehavior/Plan.md,
"how the history is generated"). Names are placeholders until the setting
is known.

    python gen_lives.py                      # 3 towns, 5 people, 25 years
    python gen_lives.py --seeds 7 8 --people 5 --years 25

Writes out/towns.json and out/lives.html, and prints each chronicle.
"""
import argparse
import json
import os
import random

SEASONS = ["winter", "winter", "spring", "spring", "spring", "summer",
           "summer", "summer", "autumn", "autumn", "autumn", "winter"]

FIRST = {
    "F": ["Edda", "Lise", "Mara", "Agnes", "Ysolde", "Bette", "Wenna", "Hild", "Joan", "Maud", "Tilda", "Rosa"],
    "M": ["Harl", "Oswin", "Wat", "Tobin", "Aldric", "Bram", "Piers", "Godric", "Hob", "Simon", "Ned", "Corin"],
}
SURNAMES = ["Fenn", "Cobb", "Pike", "Thorne", "Ashby", "Marsh", "Crane", "Hale", "Brook", "Tull"]

# job, workplace, monthly income (living costs about 6 a month)
JOBS = [
    ("miller", "mill", 9), ("carter", "carter's yard", 6), ("tavern keeper", "tavern", 8),
    ("smith", "forge", 8), ("baker", "bakery", 7), ("weaver", "weaving shed", 6),
    ("herbalist", "herb garden", 5), ("fisher", "jetty", 5),
]
RIVER_JOBS = {"miller", "fisher", "weaver"}

TRAITS = ["kind", "greedy", "proud", "jealous", "honest", "gossipy",
          "hot-headed", "forgiving", "sly", "ambitious", "lazy", "shy"]
CLASH = [{"kind", "greedy"}, {"honest", "sly"}, {"forgiving", "hot-headed"},
         {"ambitious", "lazy"}, {"gossipy", "shy"}, {"forgiving", "jealous"}]

# colour groups the page uses
GROUP = {
    "courting": "love", "marriage": "love", "unrequited": "love", "affair": "love",
    "caught": "love", "separation": "love", "jealousy": "love", "breakup": "love",
    "borrow": "money", "repay": "money", "callin": "money", "gift": "money",
    "takeover": "money", "inherit": "money", "hardtimes": "money", "paid": "money",
    "theft": "crime", "exposed": "crime", "silence": "crime", "blame": "crime",
    "slip": "crime", "confess": "crime",
    "fight": "conflict", "peace": "conflict",
    "flood": "hardship", "fire": "hardship", "harvest": "hardship", "fever": "hardship",
    "death": "life", "leaves": "life", "family": "life",
}


class Person:
    def __init__(self, pid, first, surname, sex, age, job, place, income, traits, money, attracted):
        self.id, self.first, self.surname, self.sex = pid, first, surname, sex
        self.age, self.age0 = age, age
        self.job, self.place, self.income = job, place, income
        self.traits, self.money, self.attracted = traits, money, attracted
        self.alive, self.gone = True, False
        self.spouse = None
        self.sick_until = -1
        self.sick_cause = None
        self.last_blow = None      # (event id, month)
        self.desperate = None      # (event id, month)
        self.last_theft = -999
        self.last_hardtimes = -999
        self.works_for = None
        self.died = None

    def has(self, t):
        return t in self.traits

    @property
    def here(self):
        return self.alive and not self.gone


class World:
    def __init__(self, seed, n, years):
        self.seed, self.years = seed, years
        self.rng = rng = random.Random(seed)
        self.t = 0
        self.events = []
        self.people = []
        self.like, self.love, self.spark = {}, {}, {}
        self.grudge = {}           # (a, b) -> event id behind a's grudge against b
        self.debts, self.secrets, self.beliefs = [], [], []
        self.courting, self.affairs = {}, {}
        self.siblings = set()
        self.cooldown = {}
        self.flags = set()

        jobs = rng.sample(JOBS, n)
        used = set()
        sibling_pair = rng.sample(range(n), 2) if rng.random() < 0.45 else None
        for i in range(n):
            sex = rng.choice("FM")
            first = rng.choice([f for f in FIRST[sex] if f not in used])
            used.add(first)
            surname = rng.choice([s for s in SURNAMES if s not in {p.surname for p in self.people}])
            traits = self.pick_traits()
            opposite = "M" if sex == "F" else "F"
            r = rng.random()
            attracted = {opposite} if r < 0.86 else ({sex} if r < 0.93 else {"F", "M"})
            job, place, income = jobs[i]
            self.people.append(Person(i, first, surname, sex, rng.randint(18, 34), job, place,
                                      income, traits, rng.randint(10, 45), attracted))
        self.affinity = {}
        for a in self.people:
            for b in self.people:
                if a.id < b.id:
                    pair = frozenset((a.id, b.id))
                    self.spark[pair] = rng.random()
                    self.affinity[pair] = rng.uniform(-15, 30)
        if sibling_pair:
            a, b = (self.people[i] for i in sibling_pair)
            b.surname = a.surname
            b.age = max(18, min(40, a.age + rng.randint(-5, 5)))
            b.age0 = b.age
            self.siblings.add(frozenset((a.id, b.id)))
            word = {("F", "F"): "sisters", ("M", "M"): "brothers"}.get((a.sex, b.sex), "brother and sister")
            self.ev("family", [a, b], f"{a.first} and {b.first} {a.surname} are {word}: the {a.job} and the {b.job}.")
        couple = None
        if rng.random() < 0.5:
            options = [(a, b) for a in self.people for b in self.people
                       if a.id < b.id and not self.sib(a, b) and b.sex in a.attracted and a.sex in b.attracted]
            if options:
                couple = rng.choice(options)
                a, b = couple
                a.spouse, b.spouse = b.id, a.id
                self.ev("marriage", [a, b], f"{a.first} and {b.first} are newly married.")

        for a in self.people:
            for b in self.people:
                if a is b:
                    continue
                self.like[a.id, b.id] = self.natural(a, b) + rng.uniform(-10, 10)
                self.love[a.id, b.id] = 70.0 if a.spouse == b.id else 0.0

    # ---------- helpers ----------
    def pick_traits(self):
        while True:
            t = self.rng.sample(TRAITS, 2)
            if set(t) not in CLASH:
                return t

    def natural(self, a, b):
        """Where a's feeling for b settles if nothing happens."""
        v = 8.0 + self.affinity[frozenset((a.id, b.id))]
        if self.sib(a, b):
            v += 40
        if a.spouse == b.id:
            v += 40
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
        return v

    def sib(self, a, b):
        return frozenset((a.id, b.id)) in self.siblings

    def here(self):
        return [p for p in self.people if p.here]

    def P(self, pid):
        return self.people[pid]

    def ev(self, kind, actors, text, causes=(), secret=False):
        e = {
            "id": len(self.events), "t": self.t, "year": self.t // 12 + 1,
            "season": SEASONS[self.t % 12], "kind": kind, "group": GROUP[kind],
            "actors": [p.id for p in actors], "text": text,
            "causes": sorted({c for c in causes if c is not None}), "secret": secret,
        }
        self.events.append(e)
        return e["id"]

    def recent(self, mark, months):
        if mark and self.t - mark[1] <= months:
            return mark[0]
        return None

    def hurt(self, a, b, amount, cause):
        """a now feels worse about b, because of event `cause`."""
        self.like[a.id, b.id] -= amount
        if self.like[a.id, b.id] < -30 and cause is not None:
            self.grudge.setdefault((a.id, b.id), cause)

    def ready(self, key, months):
        if self.t - self.cooldown.get(key, -9999) < months:
            return False
        self.cooldown[key] = self.t
        return True

    def heir(self, p):
        if p.spouse is not None and self.P(p.spouse).here:
            return self.P(p.spouse)
        for q in self.here():
            if self.sib(p, q):
                return q
        return None

    def open_debt(self, borrower=None, lender=None):
        for d in self.debts:
            if d["open"] and (borrower is None or d["b"] == borrower.id) and (lender is None or d["l"] == lender.id):
                return d
        return None

    def widow_word(self, p):
        return "a widow" if p.sex == "F" else "a widower"

    # ---------- monthly rules ----------
    def step(self):
        people = self.here()
        for p in people:
            p.age += 1 / 12
        self.economy(people)
        self.town_events(people)
        self.feelings(people)
        self.romance(people)
        self.money_rules(people)
        self.crime(people)
        self.conflict(people)
        self.secrets_leak(people)
        self.mortality(people)
        self.leaving(people)
        self.t += 1

    def economy(self, people):
        rng = self.rng
        for p in people:
            income = p.income * (0.7 if p.has("lazy") else 1) * (1.2 if p.has("ambitious") else 1)
            income += rng.uniform(-2, 2)
            if self.t < p.sick_until:
                income = 0
            if p.works_for is not None:
                boss = self.P(p.works_for)
                if boss.here:
                    boss.money += income * 0.2
                income *= 0.8
            spend = 5 if p.spouse is not None else 6
            if p.has("greedy"):
                spend -= 0.8
            if p.money < 0:
                spend = min(spend, 4.2)   # people go without when they're broke
            p.money += income - spend

    def town_events(self, people):
        rng = self.rng
        if rng.random() > 0.011 or not people:
            return
        kind = rng.choice(["flood", "fire", "harvest", "fever"])
        if kind == "flood":
            hit = [p for p in people if p.job in RIVER_JOBS] or [rng.choice(people)]
            places = " and the ".join(p.place for p in hit)
            eid = self.ev("flood", hit, f"The river floods and wrecks the {places}.")
            for p in hit:
                p.money -= rng.randint(35, 70)
        elif kind == "fire":
            hit = [rng.choice(people)]
            eid = self.ev("fire", hit, f"Fire guts {hit[0].first}'s {hit[0].place}.")
            hit[0].money -= rng.randint(45, 90)
        elif kind == "harvest":
            hit = list(people)
            eid = self.ev("harvest", hit, "The harvest fails, and everyone goes short that winter.")
            for p in hit:
                p.money -= rng.randint(10, 22)
        else:
            hit = rng.sample(people, min(len(people), rng.choice([1, 1, 2])))
            names = " and ".join(p.first for p in hit)
            eid = self.ev("fever", hit, f"Fever comes to town. {names} {'falls' if len(hit) == 1 else 'fall'} sick.")
            for p in hit:
                p.sick_until = self.t + rng.randint(2, 5)
                p.sick_cause = eid
        for p in hit:
            p.last_blow = (eid, self.t)
        if kind in ("flood", "fire"):
            offers = [(k, p) for p in hit for k in people if k is not p and k not in hit and k.money > 60 and k.spouse != p.id
                      and (k.has("kind") or self.like[k.id, p.id] > 45)]
            if offers and rng.random() < 0.6:
                k, p = max(offers, key=lambda kp: self.like[kp[0].id, kp[1].id])
                amt = rng.choice([20, 30, 40])
                k.money -= amt
                p.money += amt
                self.ev("gift", [k, p], f"{k.first} gives {p.first} {amt} silver to rebuild, and asks nothing back.", [eid])
                self.like[p.id, k.id] += 30

    def feelings(self, people):
        for a in people:
            for b in people:
                if a is b:
                    continue
                rate = 0.01
                if a.has("forgiving") or a.has("kind"):
                    rate = 0.03
                if a.has("jealous") or a.has("proud") or a.has("hot-headed"):
                    rate = 0.004
                key = (a.id, b.id)
                before = self.like[key]
                self.like[key] += (self.natural(a, b) - before) * rate
                if key in self.grudge and self.like[key] > -8:
                    cause = self.grudge.pop(key)
                    if self.ready(("peace", a.id, b.id), 24):
                        self.ev("peace", [a, b], f"{a.first} finally forgives {b.first}.", [cause])

    def romance(self, people):
        rng = self.rng
        for a in people:
            for b in people:
                if a is b or self.sib(a, b) or b.sex not in a.attracted:
                    continue
                spark = self.spark[frozenset((a.id, b.id))]
                if spark < 0.5 or self.like[a.id, b.id] < 15:
                    continue
                grow = 1.2 * spark + rng.uniform(0, 1)
                if a.spouse is not None and a.spouse != b.id:
                    grow *= 1.2 if self.like[a.id, a.spouse] < 0 else 0.5
                self.love[a.id, b.id] = min(100, self.love[a.id, b.id] + grow)

        for a in people:
            for b in people:
                if a.id >= b.id or self.sib(a, b):
                    continue
                pair = frozenset((a.id, b.id))
                lab, lba = self.love[a.id, b.id], self.love[b.id, a.id]
                free = a.spouse is None and b.spouse is None
                busy = any((a.id in pr or b.id in pr) for pr in self.courting if pr != pair)
                if free and not busy and pair not in self.courting and lab >= 45 and lba >= 45:
                    self.courting[pair] = (self.ev("courting", [a, b], f"{a.first} and {b.first} start courting."), self.t)
                elif pair in self.courting:
                    cid, since = self.courting[pair]
                    if not free:
                        self.courting.pop(pair)
                    elif min(lab, lba) < 30:
                        self.courting.pop(pair)
                        self.ev("breakup", [a, b], f"{a.first} and {b.first} break it off.", [cid])
                    elif self.t - since >= 6 and min(lab, lba) >= 60 and rng.random() < 0.08:
                        self.courting.pop(pair)
                        a.spouse, b.spouse = b.id, a.id
                        prior = self.affairs.pop(pair, None)
                        mid = self.ev("marriage", [a, b], f"{a.first} marries {b.first}.", [cid, prior])
                        for c in people:
                            if c in (a, b):
                                continue
                            for x, y in sorted(((a, b), (b, a)), key=lambda xy: -self.love[c.id, xy[0].id]):
                                if self.love[c.id, x.id] > 50:
                                    self.ev("jealousy", [c, y], f"{c.first} had hoped to marry {x.first}, and turns cold on {y.first}.", [mid])
                                    self.hurt(c, y, 35, mid)
                                    break
                for x, y in ((a, b), (b, a)):
                    if (self.love[x.id, y.id] >= 70 and self.love[y.id, x.id] < 15
                            and ("unreq", x.id) not in self.flags and x.spouse != y.id):
                        self.flags.add(("unreq", x.id))
                        hidden = x.has("shy") or x.spouse is not None
                        eid = self.ev("unrequited", [x, y],
                                      f"{x.first} falls for {y.first}, who doesn't feel the same" + (". It stays a secret." if hidden else "."),
                                      secret=hidden)
                        if hidden:
                            self.secrets.append({"eid": eid, "kind": "love", "keepers": {x.id}, "doer": x.id,
                                                 "victim": y.id, "open": True})
                married = [p for p in (a, b) if p.spouse is not None]
                if (married and a.spouse != b.id and pair not in self.affairs
                        and lab >= 60 and lba >= 50):
                    chance = 0.02 * (2 if (a.has("sly") or b.has("sly")) else 1) * (0.2 if (a.has("honest") or b.has("honest")) else 1)
                    before = self.cooldown.get(("caught", pair))
                    if before is not None:
                        chance *= 0.3 if self.cooldown.get(("restarts", pair), 0) < 1 else 0
                    if rng.random() < chance:
                        wronged = [self.P(p.spouse).first for p in married]
                        if before is None:
                            text = f"{a.first} and {b.first} begin an affair behind {' and '.join(wronged)}'s back."
                        else:
                            text = f"{a.first} and {b.first} can't stay apart, and start meeting in secret again."
                            self.cooldown[("restarts", pair)] = self.cooldown.get(("restarts", pair), 0) + 1
                        eid = self.ev("affair", [a, b], text, [before], secret=True)
                        self.affairs[pair] = eid
                        self.secrets.append({"eid": eid, "kind": "affair", "keepers": {a.id, b.id},
                                             "doer": a.id, "victim": None, "open": True})

        for pair, eid in list(self.affairs.items()):
            a, b = (self.P(i) for i in pair)
            if not (a.here and b.here):
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
                    if self.like[s.id, x.id] < -40 and (s.has("proud") or s.has("hot-headed") or rng.random() < 0.5):
                        s.spouse = x.spouse = None
                        self.ev("separation", [s, x], f"{s.first} throws {x.first} out of the house.", [cid])
                    break

    def money_rules(self, people):
        rng = self.rng
        for p in people:
            if p.money < -5 and not self.open_debt(borrower=p) and self.t - self.cooldown.get(("borrowed", p.id), -999) > 48:
                lenders = [l for l in people if l is not p and l.money > 50 and self.like[l.id, p.id] > -10
                           and self.t - self.cooldown.get(("asked", p.id, l.id), -999) > 24]
                lenders.sort(key=lambda l: l.money + 2 * self.like[l.id, p.id], reverse=True)
                blow = self.recent(p.last_blow, 24)
                if lenders:
                    l = lenders[0]
                    yes = 0.9 if l.has("kind") else 0.45 + self.like[l.id, p.id] / 100
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
                else:
                    refuser = None
                if self.t - p.last_hardtimes > 30:
                    p.last_hardtimes = self.t
                    why = f"; {refuser.first} won't lend" if refuser else "; nobody can lend"
                    how = "falls behind, working too little" if (p.has("lazy") and blow is None) else "falls on hard times"
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
            if b.money > d["owed"] + 20 and not b.has("greedy") or b.money > d["owed"] + 80:
                b.money -= d["owed"]
                l.money += d["owed"]
                d["open"] = False
                self.ev("repay", [b, l], f"{b.first} pays {l.first} back in full.", [d["called"] or d["eid"]])
                self.like[l.id, b.id] += 10
                if d["called"]:
                    self.like[b.id, l.id] -= 5
                continue
            if d["called"] is None and age >= 24 and (l.money < 20 or (l.has("greedy") and age >= 36)
                                                      or self.like[l.id, b.id] < -30):
                cause = [d["eid"], self.recent(l.last_blow, 18)]
                cid = self.ev("callin", [l, b], f"{l.first} calls in the debt. {b.first} owes {d['owed']} and can't pay.", cause)
                d["called"], d["called_t"] = cid, self.t
                b.desperate = (cid, self.t)
                b.last_blow = (cid, self.t)
                self.hurt(l, b, 25, cid)
                self.hurt(b, l, 15, cid)
            elif (d["called"] is not None and self.t - d["called_t"] >= 12 and b.works_for is None
                  and (l.has("ambitious") or l.has("greedy")) and ("tookover", l.id) not in self.flags):
                self.flags.add(("tookover", l.id))
                d["open"] = False
                b.works_for = l.id
                tid = self.ev("takeover", [l, b], f"{l.first} takes {b.first}'s {b.place} to settle the debt. {b.first} now works it for {l.first}.", [d["called"]])
                self.hurt(b, l, 40, tid)
                b.last_blow = (tid, self.t)
            elif d["called"] is None and age > 48:
                self.like[l.id, b.id] -= 0.4

    def crime(self, people):
        rng = self.rng
        for p in people:
            if self.t - p.last_theft < 60:
                continue
            desperate = self.recent(p.desperate, 12)
            chance = 0.0
            if p.has("greedy"):
                chance += 0.002
            if p.has("sly"):
                chance += 0.0015
            if desperate is not None:
                chance += 0.02
            chance *= 0.1 if p.has("honest") else 1
            if rng.random() > chance:
                continue
            targets = [x for x in people if x is not p and x.id != p.spouse and x.money > 30
                       and ("robbed", p.id, x.id) not in self.flags
                       and (not self.sib(p, x) or self.like[p.id, x.id] < 0)]
            if not targets:
                continue
            weights = [x.money * (1 + max(0, -self.like[p.id, x.id]) / 30) for x in targets]
            v = rng.choices(targets, weights)[0]
            amt = max(15, min(80, int(v.money * 0.35)))
            v.money -= amt
            p.money += amt
            p.last_theft = self.t
            self.flags.add(("robbed", p.id, v.id))
            tid = self.ev("theft", [p, v], f"{p.first} steals {amt} silver from {v.first}'s {v.place}.", [desperate], secret=True)
            v.last_blow = (tid, self.t)
            witness = None
            for w in people:
                if w in (p, v):
                    continue
                if rng.random() < (0.45 if w.id == p.spouse else 0.12):
                    witness = w
                    break
            if witness:
                w = witness
                if w.id == p.spouse:
                    tells = self.like[w.id, p.id] < -20
                else:
                    tells = ((w.has("honest") and self.like[w.id, p.id] < 60) or self.like[w.id, p.id] < 0
                             or (self.like[w.id, v.id] > 50 and self.like[w.id, p.id] < 30))
                if tells:
                    back = min(amt, max(0, int(p.money)))
                    p.money -= back
                    v.money += back
                    eid = self.ev("exposed", [w, p, v], f"{w.first} saw it and tells {v.first}. {p.first} has to give it back.", [tid])
                    self.hurt(v, p, 50, eid)
                    self.hurt(p, w, 40, eid)
                    continue
                eid = self.ev("silence", [w, p], f"{w.first} saw {p.first} do it, and says nothing.", [tid], secret=True)
                self.secrets.append({"eid": tid, "kind": "theft", "keepers": {p.id, w.id}, "doer": p.id,
                                     "victim": v.id, "open": True, "witness_eid": eid})
                self.like[p.id, w.id] += 5
            else:
                self.secrets.append({"eid": tid, "kind": "theft", "keepers": {p.id}, "doer": p.id,
                                     "victim": v.id, "open": True})
            suspects = [x for x in people if x is not v and x.id != v.spouse and not self.sib(v, x)]
            if not suspects:
                continue
            s = min(suspects, key=lambda x: self.like[v.id, x.id] + rng.uniform(-12, 12))
            bid = self.ev("blame", [v, s], f"{v.first} blames {s.first} for the missing silver.", [tid])
            self.beliefs.append({"holder": v.id, "theft": tid, "suspect": s.id, "thief": p.id,
                                 "wrong": s is not p, "eid": bid, "open": True})
            self.hurt(v, s, 35, bid)
            if s is not p:
                self.hurt(s, v, 25, bid)

    def conflict(self, people):
        rng = self.rng
        for a in people:
            for b in people:
                if a is b:
                    continue
                lk = self.like[a.id, b.id]
                if lk < -50 and (a.has("hot-headed") or a.has("proud") or lk < -70):
                    key = ("fights", min(a.id, b.id), max(a.id, b.id))
                    if self.cooldown.get(key, 0) < 2 and rng.random() < 0.03 and self.ready(("fight",) + key[1:], 48):
                        self.cooldown[key] = self.cooldown.get(key, 0) + 1
                        place = rng.choice(["at the tavern", "in the market", "by the well", f"at the {b.place}"])
                        eid = self.ev("fight", [a, b], f"{a.first} and {b.first} come to blows {place}.", [self.grudge.get((a.id, b.id))])
                        self.hurt(a, b, 10, eid)
                        self.hurt(b, a, 10, eid)

    def close_secret(self, eid):
        for s in self.secrets:
            if s["eid"] == eid:
                s["open"] = False

    def reveal_theft(self, sec, eid):
        v, thief = self.P(sec["victim"]), self.P(sec["doer"])
        self.close_secret(sec["eid"])
        if v.here:
            self.hurt(v, thief, 50, eid)
            for b in self.beliefs:
                if b["open"] and b["theft"] == sec["eid"]:
                    b["open"] = False
                    if b["wrong"]:
                        s = self.P(b["suspect"])
                        self.like[v.id, s.id] += 35
                        self.grudge.pop((v.id, s.id), None)
                        self.ev("peace", [v, s], f"{v.first} realises {s.first} was innocent all along.", [eid, b["eid"]])

    def secrets_leak(self, people):
        rng = self.rng
        for sec in self.secrets:
            if not sec["open"]:
                continue
            doer = self.P(sec["doer"])
            for k in list(sec["keepers"]):
                k = self.P(k)
                if not k.here:
                    continue
                if sec["kind"] == "theft" and k is not doer:
                    chance = 0.004 * (6 if k.has("gossipy") else 1) * (0.3 if self.like[k.id, doer.id] > 40 else 1)
                    if self.like[k.id, doer.id] < -30:
                        chance *= 4
                    if rng.random() < chance:
                        v = self.P(sec["victim"])
                        eid = self.ev("slip", [k, doer, v], f"{k.first} lets slip that {doer.first} was the one who robbed {v.first}.",
                                      [sec.get("witness_eid"), sec["eid"]])
                        self.hurt(doer, k, 40, eid)
                        self.reveal_theft(sec, eid)
                        break
                elif sec["kind"] == "theft" and k is doer and (k.has("honest") or k.has("kind")):
                    if rng.random() < 0.003:
                        v = self.P(sec["victim"])
                        eid = self.ev("confess", [k, v], f"Guilt wins. {k.first} confesses to {v.first} about the stolen silver.", [sec["eid"]])
                        self.reveal_theft(sec, eid)
                        self.like[v.id, k.id] += 25
                        break

    def mortality(self, people):
        rng = self.rng
        for p in people:
            sick = self.t < p.sick_until
            chance = 0.00015 + max(0.0, p.age - 45) * 0.0003 + (0.05 if sick else 0)
            if rng.random() > chance:
                continue
            p.alive = False
            p.died = self.t
            if sick:
                how = " of the fever"
            elif p.age > 50:
                how = rng.choice([" in their sleep", " after a long cough", " of a bad heart"])
            elif p.job in RIVER_JOBS:
                how = rng.choice([" in the river", " in an accident at the " + p.place])
            else:
                how = rng.choice([" in an accident at the " + p.place, " of a wound gone bad", " in a fall"])
            text = f"{p.first} drowns" if how == " in the river" else f"{p.first} dies{how}"
            causes = [p.sick_cause if sick else None]
            if p.spouse is not None:
                s = self.P(p.spouse)
                text += f", leaving {s.first} {self.widow_word(s)}"
                s.spouse = None
            kept = [sec for sec in self.secrets if sec["open"] and p.id in sec["keepers"]]
            for sec in kept:
                sec["keepers"].discard(p.id)
                if not sec["keepers"]:
                    sec["open"] = False
                    sec["grave"] = True
                    text += ", and takes a secret to the grave"
                    causes.append(sec["eid"])
            did = self.ev("death", [p], text + ".", causes)
            for d in self.debts:
                if not d["open"]:
                    continue
                if d["b"] == p.id:
                    h = self.heir(p)
                    l = self.P(d["l"])
                    if h and h is not l:
                        d["b"] = h.id
                        self.ev("inherit", [h, l], f"{h.first} inherits {p.first}'s debt of {d['owed']} to {l.first}.", [did, d["eid"]])
                    else:
                        d["open"] = False
                elif d["l"] == p.id:
                    h = self.heir(p)
                    b = self.P(d["b"])
                    if h and h is not b:
                        d["l"] = h.id
                        self.ev("inherit", [h, b], f"{h.first} inherits what {b.first} owed {p.first}: {d['owed']} silver.", [did, d["eid"]])
                    else:
                        d["open"] = False
            for pair in list(self.affairs):
                if p.id in pair:
                    self.affairs.pop(pair)

    def leaving(self, people):
        rng = self.rng
        for p in people:
            enemies = [x for x in people if x is not p and self.like[x.id, p.id] < -40]
            boss = self.P(p.works_for) if p.works_for is not None else None
            if len(enemies) >= 2 or (boss and self.like[p.id, boss.id] < -50):
                if rng.random() < 0.008:
                    p.gone = True
                    d = self.open_debt(borrower=p)
                    text = f"{p.first} packs up and leaves town"
                    causes = [self.grudge.get((x.id, p.id)) for x in enemies]
                    if boss:
                        causes.append(self.grudge.get((p.id, boss.id)))
                    if d:
                        l = self.P(d["l"])
                        text += f", still owing {l.first} {d['owed']}"
                        d["open"] = False
                        self.hurt(l, p, 30, None)
                    actors = [p]
                    if p.spouse is not None:
                        s = self.P(p.spouse)
                        text += f", leaving {s.first} behind"
                        actors.append(s)
                        s.spouse = None
                        p.spouse = None
                    self.ev("leaves", actors, text + ".", causes)

    # ---------- the day the player arrives ----------
    def present(self):
        out = []
        for p in self.people:
            out.append({
                "id": p.id, "name": f"{p.first} {p.surname}", "first": p.first, "sex": p.sex,
                "job": p.job, "place": p.place, "traits": p.traits,
                "age0": p.age0, "age": int(p.age),
                "status": "alive" if p.here else ("left town" if p.gone else "dead"),
                "died_year": (p.died // 12 + 1) if p.died is not None else None,
                "spouse": p.spouse, "works_for": p.works_for, "money": int(p.money),
                "sibling": next((q.id for q in self.people if q is not p and self.sib(p, q)), None),
                "goal": self.goal(p) if p.here else None,
                "hides": list(dict.fromkeys(self.hides(p))) if p.here else [],
                "believes": [self.belief_text(b) for b in self.beliefs if b["open"] and b["holder"] == p.id and p.here],
            })
        return out

    def belief_text(self, b):
        s, v = self.P(b["suspect"]), self.P(b["holder"])
        if b["wrong"]:
            return f"Is sure {s.first} stole from them. Wrong: it was {self.P(b['thief']).first}."
        return f"Is sure {s.first} stole from them, and is right, but can't prove it."

    def hides(self, p):
        out = []
        for sec in self.secrets:
            if not sec["open"] or p.id not in sec["keepers"]:
                continue
            doer = self.P(sec["doer"])
            if sec["kind"] == "theft":
                v = self.P(sec["victim"])
                out.append(f"Stole from {v.first}." if doer is p else f"Saw {doer.first} rob {v.first}, and never told.")
            elif sec["kind"] == "affair":
                other = [self.P(i) for i in self.affair_pair(sec["eid"]) if i != p.id]
                if other:
                    out.append(f"An affair with {other[0].first}.")
            elif sec["kind"] == "love":
                y = self.P(sec["victim"])
                out.append(f"Loves {y.first}." if y.here else f"Loved {y.first}, who {'died' if not y.alive else 'left'} never knowing.")
        return out

    def affair_pair(self, eid):
        return self.events[eid]["actors"]

    def goal(self, p):
        d = self.open_debt(borrower=p)
        if d and d["called"]:
            return f"Find {d['owed']} silver before {self.P(d['l']).first} takes everything."
        if d:
            return f"Pay back the {d['owed']} owed to {self.P(d['l']).first}."
        for pair in self.affairs:
            if p.id in pair:
                other = self.P(next(i for i in pair if i != p.id))
                return f"Keep the affair with {other.first} hidden."
        for sec in self.secrets:
            if sec["open"] and p.id in sec["keepers"] and sec["kind"] == "theft" and sec["doer"] != p.id:
                return f"Decide whether to tell {self.P(sec['victim']).first} what {self.P(sec['doer']).first} did."
        for b in self.beliefs:
            if b["open"] and b["holder"] == p.id:
                return f"Prove that {self.P(b['suspect']).first} is a thief."
        if p.works_for is not None:
            return f"Win back the {p.place} from {self.P(p.works_for).first}."
        here = [q for q in self.here() if q is not p]
        loved = [q for q in here if self.love[p.id, q.id] >= 60 and p.spouse != q.id]
        if loved:
            q = max(loved, key=lambda q: self.love[p.id, q.id])
            return f"Win {q.first}" + (f" away from {self.P(q.spouse).first}." if q.spouse is not None else ".")
        hated = [q for q in here if self.like[p.id, q.id] < -45]
        if hated:
            return f"Get even with {min(hated, key=lambda q: self.like[p.id, q.id]).first}."
        if p.spouse is None and any(e["kind"] == "death" and self.P(e["actors"][0]).spouse is None and
                                    f"leaving {p.first}" in e["text"] for e in self.events):
            return "Make a new start after losing a spouse."
        if any(sec["kind"] == "theft" and sec["doer"] == p.id and sec["open"] for sec in self.secrets):
            return "Keep the theft buried."
        if p.has("ambitious"):
            return f"Grow the {p.place} into the best in town."
        if p.has("greedy"):
            return "Get richer than anyone in town."
        return "A quiet life."

    def ties(self):
        """Labels for every pair, for the web on the page."""
        out = []
        for a in self.people:
            for b in self.people:
                if a.id >= b.id:
                    continue
                labels = []
                if a.spouse == b.id:
                    labels.append(("married", "love"))
                if self.sib(a, b):
                    labels.append(("siblings", "family"))
                pair = frozenset((a.id, b.id))
                if pair in self.affairs:
                    labels.append(("secret affair", "love"))
                if pair in self.courting:
                    labels.append(("courting", "love"))
                for x, y in ((a, b), (b, a)):
                    if not x.here:
                        continue
                    lk = self.like[x.id, y.id]
                    if y.here and self.love[x.id, y.id] >= 60 and x.spouse != y.id and pair not in self.affairs and pair not in self.courting:
                        labels.append((f"{x.first} loves {y.first}", "love"))
                    if lk < -45:
                        labels.append((f"{x.first} hates {y.first}", "conflict"))
                    elif lk < -20:
                        labels.append((f"{x.first} resents {y.first}", "conflict"))
                    elif lk > 55 and a.spouse != b.id and not self.sib(a, b):
                        labels.append((f"{x.first} is fond of {y.first}", "warm"))
                for d in self.debts:
                    if d["open"] and {d["l"], d["b"]} == {a.id, b.id}:
                        labels.append((f"{self.P(d['b']).first} owes {self.P(d['l']).first} {d['owed']}", "money"))
                if a.works_for == b.id or b.works_for == a.id:
                    w, boss = (a, b) if a.works_for == b.id else (b, a)
                    labels.append((f"{w.first} works for {boss.first}", "money"))
                for bl in self.beliefs:
                    if bl["open"] and {bl["holder"], bl["suspect"]} == {a.id, b.id}:
                        h, s = self.P(bl["holder"]), self.P(bl["suspect"])
                        labels.append((f"{h.first} blames {s.first}" + (" (wrongly)" if bl["wrong"] else ""), "crime"))
                for sec in self.secrets:
                    if sec["open"] and sec["kind"] == "theft" and {sec["doer"], sec["victim"]} == {a.id, b.id}:
                        labels.append((f"{self.P(sec['doer']).first} robbed {self.P(sec['victim']).first} (secret)", "crime"))
                if labels:
                    out.append({"a": a.id, "b": b.id, "labels": [{"text": t, "group": g} for t, g in labels]})
        return out

    def score(self):
        tensions = (2 * sum(1 for s in self.secrets if s["open"])
                    + sum(1 for d in self.debts if d["open"])
                    + 2 * sum(1 for b in self.beliefs if b["open"] and b["wrong"])
                    + sum(1 for p in self.here() if p.works_for is not None)
                    + sum(1 for (a, b), v in self.like.items() if v < -45 and self.P(a).here and self.P(b).here))
        linked = set()
        for e in self.events:
            if e["group"] == "hardship":
                continue
            for i in e["actors"]:
                for j in e["actors"]:
                    if i < j:
                        linked.add((i, j))
        depth = {}
        for e in self.events:
            depth[e["id"]] = 1 + max((depth[c] for c in e["causes"]), default=0)
        n = len(self.people)
        kinds = {}
        for e in self.events:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        return {
            "groups": len({e["group"] for e in self.events}),
            "most_repeated": max(kinds.values(), default=0),
            "love": sum(1 for e in self.events if e["group"] == "love" and e["t"] > 0),
            "events": len(self.events), "tensions": tensions, "pairs_linked": len(linked),
            "pairs_total": n * (n - 1) // 2, "longest_chain": max(depth.values(), default=0),
        }


def good(sc):
    return (12 <= sc["events"] <= 32 and sc["tensions"] >= 5
            and sc["pairs_linked"] >= 0.7 * sc["pairs_total"] and sc["longest_chain"] >= 4
            and sc["groups"] >= 5 and sc["most_repeated"] <= 4 and sc["love"] >= 1)


def build(seed, n, years, max_tries=200):
    for attempt in range(max_tries):
        w = World(seed * 1000 + attempt, n, years)
        for _ in range(years * 12):
            w.step()
        sc = w.score()
        if good(sc):
            return w, attempt
    return w, attempt


def chronicle(w):
    lines = []
    for e in w.events:
        why = ""
        if e["causes"]:
            why = "  <- because " + "; ".join(w.events[c]["text"].rstrip(".") for c in e["causes"])
        mark = " [secret]" if e["secret"] else ""
        lines.append(f"Year {e['year']:>2}, {e['season']}: {e['text']}{mark}{why}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--people", type=int, default=5)
    ap.add_argument("--years", type=int, default=25)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    args = ap.parse_args()

    towns = []
    for seed in args.seeds:
        w, rerolls = build(seed, args.people, args.years)
        sc = w.score()
        print(f"\n=== Town seed {seed} (re-rolled {rerolls} dull towns) {sc}")
        for p in w.people:
            print(f"  {p.first} {p.surname}, {p.age0}, {p.job}, {', '.join(p.traits)}")
        for line in chronicle(w):
            print("  " + line)
        print("  --- the day the player arrives ---")
        pres = w.present()
        for p in pres:
            if p["status"] != "alive":
                print(f"  {p['first']}: {p['status']}")
                continue
            print(f"  {p['first']} ({p['age']}): wants to {p['goal']} hides {p['hides']} believes {p['believes']}")
        towns.append({"seed": seed, "rerolls": rerolls, "score": sc, "years": args.years,
                      "people": pres, "events": w.events, "ties": w.ties()})

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "towns.json"), "w", encoding="utf-8") as f:
        json.dump(towns, f, indent=1)
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page_template_v1.html")
    if os.path.exists(tpl):
        with open(tpl, encoding="utf-8") as f:
            html = f.read().replace("/*TOWNS*/null", json.dumps(towns))
        with open(os.path.join(args.out, "lives.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nWrote {os.path.join(args.out, 'lives.html')}")


if __name__ == "__main__":
    main()
