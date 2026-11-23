"""Memory and gossip, history and play. Throwaway spike tool.

Tests the "Mind and memory" part of the plan on generated towns:

  1. Replay a town's 25-year history month by month. Everyone involved in an
     event remembers it; secrets stay with the people who keep them until
     something gives them away; big public news reaches the whole town; the
     rest travels by gossip along family, friends, work and chance meetings.
     Memories fade, and each person keeps only their most important few dozen.
  2. Play a month in days after the player arrives, with things the player
     does (a theft someone sees, a theft nobody sees, a killing someone sees,
     a kindness), and measure how fast word spreads and what people then
     think of the player.
  3. Write the town save: everything the game would load on the day the
     player arrives (people, places, memories, secrets, debts, feelings).

    python minds.py --towns 100            # out/minds.json, out/town_save_example.json
"""
import argparse
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import gen_lives as G

PLAYER = -1
CAP = 40                 # memories each person keeps
TOWN_NEWS = {"flood", "fire", "harvest", "fever", "death", "found", "exiled", "arrival", "runaway", "feud",
             "closes", "takeover", "buys", "inherit_wp", "elope", "marriage"}
# how much a kind of event matters, before it's about you or yours
WEIGHT = {"killing": 10, "found": 9, "exiled": 8, "exposed": 7, "caught": 7, "parentage": 8, "affair": 7,
          "theft": 6, "sabotage": 6, "blackmail": 7, "slip": 6, "confess": 6, "blame": 5, "fight": 4,
          "feud": 6, "feud_end": 5, "runaway": 6, "elope": 5, "forbids": 4, "separation": 6, "death": 5,
          "marriage": 4, "birth": 3, "takeover": 5, "callin": 4, "closes": 4, "buys": 3, "rivalry": 3,
          "rumor": 4, "jealousy": 3, "unrequited": 3, "drink": 3, "sober": 2, "leaves": 3, "arrival": 2,
          "flood": 5, "fire": 5, "harvest": 3, "fever": 4, "accident": 3, "gift": 2, "forgive_debt": 3,
          "peace": 2, "friends": 1, "courting": 2, "breakup": 2, "borrow": 2, "repay": 1, "hardtimes": 2,
          "hire": 1, "apprentice": 1, "inherit": 2, "inherit_wp": 2, "adopt": 3, "silence": 0, "family": 1,
          "player_theft": 6, "player_kill": 10, "player_gift": 3}
NEVER_FADE = 8           # memories this heavy, about you or yours, never fade
HALF_LIFE_MONTHS = 30    # hearsay halves in strength this often
LIVED_HALF_LIFE = 240    # things that happened to you fade far slower
# what each kind of event says about the doer, for opinions of the player
VALENCE = {"player_theft": -30, "player_kill": -90, "player_gift": 20}


class Memory:
    __slots__ = ("eid", "how", "src", "strength", "learned", "partial")

    def __init__(self, eid, how, src, strength, learned, partial=False):
        self.eid, self.how, self.src, self.strength, self.learned, self.partial = eid, how, src, strength, learned, partial


class Minds:
    """Everyone's memories over a World's events, plus events the player adds in play."""

    def __init__(self, w, seed):
        self.w = w
        self.rng = G.Rng(seed)
        self.events = list(w.events)
        self.mem = {p.id: {} for p in w.people}
        self.shareable = set()         # secret events that have come out
        self.knew = {}                 # secret event -> who knew it when it happened
        for s in w.secrets:
            self.knew[s["eid"]] = set(s.get("knew", s["keepers"]))
        self.ties = self.build_ties()
        self.tells = Counter()         # conversations that passed something on
        self.silenced = set()          # people who can't talk any more (killed in play)

    # ---------- who talks to whom ----------
    def build_ties(self):
        w = self.w
        partners = set()
        for e in w.events:
            if e["kind"] in ("marriage", "elope", "runaway") and len(e["actors"]) >= 2:
                partners.add(frozenset(e["actors"][:2]))
        ties = {p.id: set() for p in w.people}
        for a in w.people:
            for b in w.people:
                if a is b:
                    continue
                if (w.kin(a, b) or frozenset((a.id, b.id)) in partners or b.id in a.friends
                        or (a.wp is not None and a.wp == b.wp) or (a.house is not None and a.house == b.house)):
                    ties[a.id].add(b.id)
        return {k: sorted(v) for k, v in ties.items()}  # sorted, so picks are the same in any port

    def present(self, t):
        out = []
        for p in self.w.people:
            end = p.died if p.died is not None else p.left
            if p.birth_t <= t and (end is None or end >= t) and t - p.birth_t >= 8 * 12:
                out.append(p)
        return out

    # ---------- remembering ----------
    def importance(self, pid, eid):
        e = self.events[eid]
        wt = WEIGHT.get(e["kind"], 2)
        if pid in e["actors"]:
            return wt * 3
        if pid >= 0:
            p = self.w.P(pid)
            near = [a for a in e["actors"] if a >= 0]
            if any(self.w.kin(p, self.w.P(a)) or self.w.P(a).spouse == pid for a in near):
                return wt * 2
            if any(a in p.friends for a in near):
                return wt * 1.5
        return wt

    def learn(self, pid, eid, how, src, strength, t, partial=False):
        if pid < 0:
            return False
        m = self.mem[pid]
        old = m.get(eid)
        if old is not None:
            if old.partial and not partial:
                old.partial, old.how, old.src = False, how, src
            old.strength = max(old.strength, strength)
            return False
        m[eid] = Memory(eid, how, src, strength, t, partial)
        if len(m) > CAP:
            worst = min(m.values(), key=lambda x: self.importance(pid, x.eid) * x.strength)
            del m[worst.eid]
        return True

    def fade(self, months):
        heard = 0.5 ** (months / HALF_LIFE_MONTHS)
        lived = 0.5 ** (months / LIVED_HALF_LIFE)
        for pid, m in self.mem.items():
            for x in m.values():
                if self.importance(pid, x.eid) >= NEVER_FADE * 2:
                    continue
                x.strength *= lived if x.how in ("did", "was there", "victim", "saw") else heard

    def secret_out(self, eid):
        """Does this event reveal a secret? Then the secret can travel."""
        e = self.events[eid]
        if e["kind"] in ("slip", "exposed", "confess", "caught"):
            for c in e["causes"]:
                c_e = self.events[c]
                if c_e["secret"]:
                    self.shareable.add(c)
                    if c_e["kind"] == "silence":
                        self.shareable.update(c_e["causes"])

    def witness_event(self, e, t):
        """Put one event into the heads of the people it happened to."""
        eid = e["id"]
        self.secret_out(eid)
        if e["secret"]:
            knowers = self.knew.get(eid, set(e["actors"][:1]))
            for pid in sorted(knowers):
                self.learn(pid, eid, "did" if pid in e["actors"] else "saw", None, 1.0, t)
            # victims of a crime know it happened, not who did it
            if e["kind"] in ("theft", "sabotage", "player_theft") and len(e["actors"]) > 1:
                self.learn(e["actors"][1], eid, "victim", None, 1.0, t, partial=e["actors"][1] not in knowers)
            if e["kind"] == "silence" and len(e["actors"]) > 0:
                self.learn(e["actors"][0], eid, "did", None, 1.0, t)
            return
        for i, pid in enumerate(e["actors"]):
            self.learn(pid, eid, "did" if i == 0 else "was there", None, 1.0, t)
        if e["kind"] in TOWN_NEWS:
            for p in self.present(t):
                self.learn(p.id, eid, "heard", None, 0.8, t)
        if e["kind"] in ("slip", "exposed", "confess", "caught"):
            for c in e["causes"]:
                if self.events[c]["kind"] == "silence":
                    continue
                for pid in e["actors"]:
                    self.learn(pid, c, "heard", e["actors"][0], 0.9, t)

    # ---------- gossip ----------
    def can_share(self, eid):
        e = self.events[eid]
        return (not e["secret"] or eid in self.shareable) and e["kind"] not in ("silence", "family")

    def chat(self, a, b, t, chance):
        """a may tell b the juiciest thing a knows that b doesn't. Big news is more likely to come up."""
        if a.id in self.silenced or b.id in self.silenced:
            return False
        mb = self.mem[b.id]
        best, score = None, 0.0
        for x in self.mem[a.id].values():
            if x.partial or not self.can_share(x.eid):
                continue
            had = mb.get(x.eid)
            if had is not None and not had.partial:
                continue
            e = self.events[x.eid]
            if b.id in e["actors"] and had is None:
                continue
            fresh = 1.0 / (1.0 + max(0, t - x.learned) / 3.0)
            s = WEIGHT.get(e["kind"], 2) * x.strength * fresh
            if s > score:
                best, score = x, s
        if best is None or score < 0.5:
            return False
        urgency = min(3.0, max(0.3, score / 4.0))
        if self.rng.random() > chance * urgency:
            return False
        self.learn(b.id, best.eid, "heard", a.id, best.strength * 0.7, t)
        self.tells[self.events[best.eid]["kind"]] += 1
        return True

    def talk_rate(self, p):
        return 0.35 * (2.2 if p.has("gossipy") else 1) * (0.35 if p.has("shy") else 1)

    def month_of_gossip(self, t):
        people = self.present(t)
        here = {p.id for p in people}
        for a in people:
            ties = [i for i in self.ties[a.id] if i in here]
            for _ in range(6):
                if ties and self.rng.random() < 0.7:
                    b = self.w.P(self.rng.choice(ties))
                else:
                    b = self.rng.choice(people)
                if b is not a:
                    self.chat(a, b, t, self.talk_rate(a))

    def replay(self):
        by_t = {}
        for e in self.events:
            by_t.setdefault(e["t"], []).append(e)
        for t in range(self.w.t):
            for e in by_t.get(t, []):
                self.witness_event(e, t)
            self.month_of_gossip(t)
            self.fade(1)

    # ---------- play: days after the player arrives ----------
    def add_player_event(self, kind, victim, text, t, secret, witness=None):
        e = {"id": len(self.events), "t": t, "year": t // 12 + 1, "season": "", "kind": kind, "group": "player",
             "actors": [PLAYER] + ([victim.id] if victim else []), "text": text, "causes": [], "secret": secret}
        self.events.append(e)
        if victim:
            self.learn(victim.id, e["id"], "victim", None, 1.0, t, partial=secret and witness is not victim)
        if witness:
            self.learn(witness.id, e["id"], "saw", None, 1.0, t)
        return e["id"]

    def witness_decides(self, witness, victim, eid, t):
        """The same choice a witness makes in the town's history: tell, or keep quiet.
        Honest people tell; so does anyone fond of the victim; gossips can't help it.
        A killing is harder to sit on than a theft."""
        w = self.w
        kill = self.events[eid]["kind"] == "player_kill"
        fond = w.like[witness.id, victim.id] > (0 if kill else 30)
        tells = witness.has("honest") or witness.has("gossipy") or fond or (kill and not witness.has("sly"))
        if tells:
            self.shareable.add(eid)
            if not kill:
                self.learn(victim.id, eid, "heard", witness.id, 0.9, t)
            else:  # a witness to a killing goes straight to the family
                for q in w.here():
                    if q is not victim and (w.kin(q, victim) or q.spouse == victim.id):
                        self.learn(q.id, eid, "heard", witness.id, 0.9, t)
        return tells

    def maybe_slip(self, witness, eid):
        """A witness keeping quiet may still let it slip, a little more likely each day for gossips."""
        if eid in self.shareable:
            return
        if self.rng.random() < (0.08 if witness.has("gossipy") else 0.02):
            self.shareable.add(eid)

    def day_of_life(self, day):
        """One day: home in the evening, work by day, and the market or tavern for some."""
        w, rng = self.w, self.rng
        t = w.t + day / 30.0
        people = [p for p in w.here() if w.age(p) >= 8]
        rate_day = 0.6  # talk rates above are per meeting in a month of six; a day's meetings are fewer and shorter
        houses, works = {}, {}
        for p in people:
            houses.setdefault(p.house, []).append(p)
            if p.wp is not None and w.adult(p):
                works.setdefault(p.wp, []).append(p)
        for group in list(houses.values()) + (list(works.values()) if day % 7 != 6 else []):
            for a in group:
                for b in group:
                    if a is not b:
                        self.chat(a, b, t, self.talk_rate(a) * rate_day)
        out = [p for p in people if w.adult(p) and rng.random() < 0.45]
        for a in out:
            for _ in range(3):
                b = rng.choice(out)
                if b is not a:
                    self.chat(a, b, t, self.talk_rate(a) * rate_day)

    def opinion(self, p):
        v = 0.0
        for x in self.mem[p.id].values():
            e = self.events[x.eid]
            if PLAYER in e["actors"] and not x.partial:
                k = VALENCE.get(e["kind"], 0)
                if k < 0 and p.has("honest"):
                    k *= 1.5
                if k < 0 and p.has("forgiving"):
                    k *= 0.6
                if len(e["actors"]) > 1 and e["actors"][1] == p.id:
                    k *= 2
                v += k * x.strength
        return v

    def knows(self, eid, full=True):
        adults = [p for p in self.w.here() if self.w.adult(p)]
        n = sum(1 for p in adults if eid in self.mem[p.id] and not (full and self.mem[p.id][eid].partial))
        return n / max(1, len(adults))

    def memories_of(self, p):
        return sorted(self.mem[p.id].values(), key=lambda x: -self.importance(p.id, x.eid) * x.strength)


def adults_here(w):
    return [p for p in w.here() if w.adult(p)]


def play_scenario(w, seed, scenario):
    """Replay the history, then run 30 days with one thing the player does on day 1."""
    m = Minds(w, seed)
    m.replay()
    rng = G.Rng(seed + 17)
    adults = adults_here(w)
    owners = [p for p in adults if p.wp is not None and w.wps[p.wp].owner == p.id]
    victim = rng.choice(owners or adults)
    others = [p for p in adults if p is not victim]
    coworkers = [p for p in others if p.wp == victim.wp] or others
    witness = rng.choice(coworkers)
    t = w.t
    tells, seen = None, None
    if scenario == "seen_theft":
        seen = witness
        eid = m.add_player_event("player_theft", victim, f"The stranger steals from {victim.first}.", t, True, witness)
        tells = m.witness_decides(witness, victim, eid, t)
    elif scenario == "unseen_theft":
        eid = m.add_player_event("player_theft", victim, f"The stranger steals from {victim.first}.", t, True, None)
    elif scenario == "seen_killing":
        seen = witness
        eid = m.add_player_event("player_kill", victim, f"The stranger kills {victim.first}.", t, True, witness)
        tells = m.witness_decides(witness, victim, eid, t)
        m.silenced.add(victim.id)
        found = {"id": len(m.events), "t": t, "year": t // 12 + 1, "season": "", "kind": "found", "group": "life",
                 "actors": [victim.id], "text": f"{victim.first} is found dead.", "causes": [eid], "secret": False}
        m.events.append(found)
        m.witness_event(found, t)   # the body is town news at once; who did it is not
        kin = [q for q in adults if q is not victim and (w.kin(q, victim) or q.spouse == victim.id)]
        if kin:
            victim = kin[0]  # whose learning we time: the next of kin
    else:
        eid = m.add_player_event("player_gift", victim, f"The stranger helps {victim.first}.", t, False, None)
    curve, victim_day = [], None
    for day in range(1, 31):
        if seen is not None:
            m.maybe_slip(seen, eid)
        m.day_of_life(day)
        if victim_day is None and eid in m.mem[victim.id] and not m.mem[victim.id][eid].partial:
            victim_day = day
        if day in (1, 2, 3, 7, 14, 30):
            curve.append((day, round(m.knows(eid), 3)))
    ops = [m.opinion(p) for p in adults_here(w) if p is not victim]
    return {"curve": curve, "victim_day": victim_day, "victim_is_owner": victim in owners, "witness_tells": tells,
            "witness_tied_to_victim": witness.id in m.ties[victim.id],
            "against": round(sum(1 for o in ops if o < -5) / max(1, len(ops)), 3),
            "for": round(sum(1 for o in ops if o > 5) / max(1, len(ops)), 3)}


def history_stats(w, seed):
    m = Minds(w, seed)
    t0 = time.perf_counter()
    m.replay()
    secs = time.perf_counter() - t0
    adults = adults_here(w)
    counts = [len(m.mem[p.id]) for p in adults]
    # what do people carry into the game?
    hows = Counter(x.how for p in adults for x in m.mem[p.id].values())
    kinds = Counter(m.events[x.eid]["kind"] for p in adults for x in m.mem[p.id].values())
    secrets_open = [s for s in w.secrets if s["open"]]
    leaked = sum(1 for s in secrets_open for p in adults if s["eid"] in m.mem[p.id]
                 and p.id not in s["keepers"] and not m.mem[p.id][s["eid"]].partial)
    old = sum(1 for p in adults for x in m.mem[p.id].values() if w.t - x.learned > 120)
    total = sum(counts)
    lived = sum(1 for p in adults for x in m.mem[p.id].values() if x.how in ("did", "was there", "victim", "saw"))
    stories = w.stories()
    knows_big = 0.0
    if stories:
        top = set(stories[0]["events"])
        knows_big = sum(1 for p in adults if top & set(m.mem[p.id])) / max(1, len(adults))
    topics = Counter((m.events[x.eid]["kind"], x.how) for p in adults for x in m.mem[p.id].values())
    return {"secs": secs, "mean_memories": sum(counts) / max(1, len(counts)), "max_memories": max(counts, default=0),
            "share_heard": hows["heard"] / max(1, total), "share_older_than_10y": old / max(1, total),
            "share_lived": lived / max(1, total), "knows_biggest_story": knows_big,
            "secret_leaks": leaked, "tells": sum(m.tells.values()), "kinds": kinds, "topics": topics}


def town_save(w, m):
    """Everything the game loads on the day the player arrives. Format 1, spike version."""
    people = []
    for p in w.people:
        wp = w.wps[p.wp] if p.wp is not None else None
        here = p.here
        feelings = []
        if here:
            others = [q for q in w.here() if q is not p]
            likes = sorted(others, key=lambda q: -w.like[p.id, q.id])
            pick = likes[:4] + likes[-4:]
            for q in dict.fromkeys(pick):
                feelings.append({"to": q.id, "like": round(w.like[p.id, q.id]), "love": round(w.love[p.id, q.id])})
            for q in others:
                if w.love[p.id, q.id] >= 40 and q not in pick:
                    feelings.append({"to": q.id, "like": round(w.like[p.id, q.id]), "love": round(w.love[p.id, q.id])})
        people.append({
            "id": p.id, "called": p.first, "given": p.given, "surname": p.surname, "sex": p.sex, "born_month": p.birth_t,
            "status": "alive" if here else ("left" if p.gone else "dead"),
            "died_month": p.died, "left_month": p.left, "arrived_month": p.arrived,
            "traits": p.traits, "parents": p.parents, "children": p.children, "spouse": p.spouse if here else None,
            "house": p.house if here else None, "workplace": wp.id if (wp and here) else None,
            "job": (wp.trade if wp else ("labourer" if w.adult(p) else "child")) if here else p.trade,
            "drink": p.drink, "money": int(p.money), "goal": w.goal(p) if here else None,
            "friends": sorted(p.friends), "feelings": feelings,
            "memories": [{"event": x.eid, "how": x.how, "from": x.src, "strength": round(x.strength, 2),
                          "learned_month": int(x.learned), "knows_who": not x.partial}
                         for x in m.memories_of(p)] if here else [],
        })
    return {
        "format": 1, "note": "Spike output: placeholder names, rules and numbers.",
        "seed": w.seed, "month": w.t, "years": w.years, "temperament": w.temperament(),
        "people": people,
        "workplaces": [{"id": x.id, "trade": x.trade, "place": x.place, "owner": x.owner, "workers": sorted(x.workers),
                        "open": x.open} for x in w.wps],
        "events": [{k: e[k] for k in ("id", "t", "kind", "actors", "causes", "secret", "text")} for e in w.events],
        "secrets": [{"event": s["eid"], "kind": s["kind"], "keepers": sorted(s["keepers"]), "doer": s["doer"],
                     "victim": s.get("victim")} for s in w.secrets if s["open"]],
        "beliefs": [{"holder": b["holder"], "about": b["about"], "suspect": b["suspect"], "wrong": b["wrong"]}
                    for b in w.beliefs if b["open"]],
        "debts": [{"lender": d["l"], "borrower": d["b"], "owed": d["owed"], "since": d["t"],
                   "called_in": d["called"] is not None} for d in w.debts if d["open"]],
        "feuds": [{"families": sorted(k), "event": v} for k, v in w.feuds.items()],
        "blackmail": [{"by": b["x"], "of": b["y"], "event": b["eid"]} for b in w.blackmails if b["open"]],
        "courting": [{"pair": sorted(k), "since": v["since"], "forbidden_by": v["forbid"][1] if v.get("forbid") else None}
                     for k, v in w.courting.items()],
        "affairs": [{"pair": sorted(k), "event": v} for k, v in w.affairs.items()],
    }


SCENARIOS = ("seen_theft", "unseen_theft", "seen_killing", "kindness")


def one_town(seed):
    w, _ = G.build(seed)
    out = {"seed": seed, "history": history_stats(w, seed)}
    for sc in SCENARIOS:
        out[sc] = play_scenario(w, seed, sc)
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns", type=int, default=100)
    ap.add_argument("--first", type=int, default=6001)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one_town, range(a.first, a.first + a.towns)))
    n = len(res)
    H = [r["history"] for r in res]
    topics = Counter()
    for h in H:
        topics.update(h["topics"])
    summary = {
        "towns": n, "wall_secs": round(time.perf_counter() - t0),
        "history": {
            "replay_secs": round(sum(h["secs"] for h in H) / n, 2),
            "mean_memories": round(sum(h["mean_memories"] for h in H) / n, 1),
            "max_memories": max(h["max_memories"] for h in H),
            "share_heard": round(sum(h["share_heard"] for h in H) / n, 2),
            "share_older_than_10y": round(sum(h["share_older_than_10y"] for h in H) / n, 2),
            "share_lived": round(sum(h["share_lived"] for h in H) / n, 2),
            "knows_biggest_story": round(sum(h["knows_biggest_story"] for h in H) / n, 2),
            "towns_with_secret_leaks": sum(1 for h in H if h["secret_leaks"]),
            "topics_in_use": len(topics),
            "top_topics": [{"kind": k, "how": hw, "share": round(c / sum(topics.values()), 3)}
                           for (k, hw), c in topics.most_common(12)],
        },
    }
    for sc in ("seen_theft", "seen_killing"):
        rows = [r[sc] for r in res]
        told = [r for r in rows if r["witness_tells"]]
        quiet = [r for r in rows if not r["witness_tells"]]
        summary[sc + "_witness"] = {
            "tells": round(len(told) / n, 2),
            "knows_by_day_when_told": {str(d): round(sum(r["curve"][i][1] for r in told) / max(1, len(told)), 3)
                                       for i, (d, _) in enumerate(rows[0]["curve"])},
            "knows_by_day_when_quiet": {str(d): round(sum(r["curve"][i][1] for r in quiet) / max(1, len(quiet)), 3)
                                        for i, (d, _) in enumerate(rows[0]["curve"])},
        }
    for sc in SCENARIOS:
        rows = [r[sc] for r in res]
        days = [d for d, _ in rows[0]["curve"]]
        summary[sc] = {
            "knows_by_day": {str(d): round(sum(r["curve"][i][1] for r in rows) / n, 3) for i, d in enumerate(days)},
            "victim_learns_median_day": median([r["victim_day"] for r in rows]),
            "victim_never_learns": round(sum(1 for r in rows if r["victim_day"] is None) / n, 2),
            "victim_learns_by_day_3": round(sum(1 for r in rows if r["victim_day"] is not None and r["victim_day"] <= 3) / n, 2),
            "against_player": round(sum(r["against"] for r in rows) / n, 3),
            "for_player": round(sum(r["for"] for r in rows) / n, 3),
        }
    print(json.dumps(summary, indent=1))
    with open(os.path.join(here, "out", "minds.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    w, _ = G.build(1)
    m = Minds(w, 1)
    m.replay()
    with open(os.path.join(here, "out", "town_save_example.json"), "w", encoding="utf-8") as f:
        json.dump(town_save(w, m), f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
