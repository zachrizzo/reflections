"""Consistency checks for generated towns. Throwaway spike tool.

Two kinds of check:
  - every event: its causes come first, and nobody in it is unborn, dead or gone
    (with a few deliberate exceptions, such as a slip naming a dead thief);
  - every month: the town's state makes sense (spouses agree, no child lives
    alone, open shops have an owner in town, open debts and secrets have
    people in town to carry them, and so on).

    python check.py --towns 1000 --jobs 14
    python check.py --seed 1234          # one raw world, with details

A clean run prints zero problems. Any problem prints the seed, month and event.
"""
import argparse
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import gen_lives as G

# kinds where everyone named must be at least 16
ADULT_KINDS = {"courting", "marriage", "affair", "caught", "separation", "jealousy", "breakup", "forbids",
               "elope", "runaway", "friends", "gift", "borrow", "repay", "callin", "takeover", "inherit",
               "hardtimes", "hire", "buys", "closes", "inherit_wp", "theft", "blame", "confess", "blackmail",
               "sabotage", "killing", "fight", "rumor", "rivalry", "drink", "sober", "unrequited",
               "forgive_debt", "apprentice"}
# kinds where actors after the first may already be dead or gone: they are talked about, not acting
ABOUT_KINDS = {"slip", "exposed", "inherit_wp", "closes", "adopt", "leaves"}
# kinds whose text needn't name every actor
UNNAMED_OK = {"flood", "fire", "harvest", "feud", "feud_end", "slip", "parentage", "leaves", "caught"}


def event_problems(w):
    out = []
    P = w.people
    for e in w.events:
        t, eid = e["t"], e["id"]
        for c in e["causes"]:
            if c >= eid:
                out.append(("cause after event", eid, e["text"]))
            elif w.events[c]["t"] > t:
                out.append(("cause later in time", eid, e["text"]))
        for i, pid in enumerate(e["actors"]):
            p = P[pid]
            if p.birth_t > t:
                out.append(("unborn actor", eid, f"{p.first}: {e['text']}"))
            if p.exit_eid is not None and eid > p.exit_eid:
                lenient = e["kind"] in ABOUT_KINDS and (i >= 1 or e["kind"] == "closes") and e["t"] == w.events[p.exit_eid]["t"]
                talked_about = e["kind"] in ("slip", "exposed") and i >= 1
                if not (lenient or talked_about):
                    out.append(("actor after death or leaving", eid, f"{p.first} ({w.events[p.exit_eid]['kind']} at {p.exit_eid}): {e['text']}"))
            if e["kind"] in ADULT_KINDS and (t - p.birth_t) < 16 * 12:
                if not (e["kind"] in ("closes", "inherit_wp") and i >= 1):
                    out.append(("child in an adult event", eid, f"{p.first} aged {(t - p.birth_t) // 12}: {e['text']}"))
            if e["kind"] not in UNNAMED_OK and p.first not in e["text"]:
                out.append(("actor not named in text", eid, f"{p.first}: {e['text']}"))
        if e["kind"] in ("marriage", "elope", "runaway", "courting"):
            a, b = P[e["actors"][0]], P[e["actors"][1]]
            if w.kin(a, b):
                out.append(("kin marry", eid, e["text"]))
    return out


def state_problems(w):
    out = []
    t = w.t
    here = w.here()
    for p in here:
        a = w.age(p)
        if a > 100:
            out.append(("older than 100", t, p.first))
        if p.spouse is not None:
            s = w.P(p.spouse)
            if not s.here:
                out.append(("married to someone dead or gone", t, f"{p.first} -> {s.first}"))
            elif s.spouse != p.id:
                out.append(("one-sided marriage", t, f"{p.first} -> {s.first} -> {s.spouse}"))
            elif w.kin(p, s):
                out.append(("married to kin", t, f"{p.first} + {s.first}"))
            elif a < 16:
                out.append(("married child", t, p.first))
        if a < 16 and not any(q.here and w.adult(q) and q.house == p.house for q in w.people):
            out.append(("child with no grown-up at home", t, f"{p.first} aged {int(a)}"))
        if p.wp is not None:
            wp = w.wps[p.wp]
            if not wp.open:
                out.append(("works at a shut place", t, f"{p.first} at {wp.place}"))
            elif wp.owner != p.id and p.id not in wp.workers:
                out.append(("works somewhere without being on its books", t, f"{p.first} at {wp.place}"))
        for q in p.parents:
            if w.P(q).birth_t + 16 * 12 > p.birth_t:
                out.append(("parent under 16 at the birth", t, f"{w.P(q).first} -> {p.first}"))
    for wp in w.wps:
        if not wp.open:
            if wp.workers:
                out.append(("shut place still has workers", t, wp.place))
            continue
        if wp.owner is None:
            out.append(("open place with no owner", t, wp.place))
        elif not w.P(wp.owner).here:
            out.append(("open place owned by someone dead or gone", t, f"{wp.place}: {w.P(wp.owner).first}"))
        for i in wp.workers:
            q = w.P(i)
            if not q.here:
                out.append(("dead or gone worker on the books", t, f"{wp.place}: {q.first}"))
            elif q.wp != wp.id:
                out.append(("worker on two books", t, f"{wp.place}: {q.first}"))
    for d in w.debts:
        if d["open"]:
            if not (w.P(d["l"]).here and w.P(d["b"]).here):
                out.append(("open debt with someone dead or gone", t, f"{w.P(d['b']).first} owes {w.P(d['l']).first}"))
            if d["l"] == d["b"]:
                out.append(("owes themself", t, w.P(d["l"]).first))
    for s in w.secrets:
        if s["open"] and not any(w.P(k).here for k in s["keepers"]):
            out.append(("open secret nobody in town keeps", t, w.events[s["eid"]]["text"]))
    for b in w.beliefs:
        if b["open"] and not w.P(b["holder"]).here:
            out.append(("open belief held by someone dead or gone", t, w.P(b["holder"]).first))
    for pair in w.courting:
        if not all(w.P(i).here for i in pair):
            out.append(("courting someone dead or gone", t, str(sorted(pair))))
    for pair in w.affairs:
        if not all(w.P(i).here for i in pair):
            out.append(("affair with someone dead or gone", t, str(sorted(pair))))
    firsts = Counter(p.first for p in here)
    for name, n in firsts.items():
        if n > 1:
            out.append(("two living people share a first name", t, name))
    for p in here:
        if p.money < -400 or p.money > 5000:
            out.append(("money out of range", t, f"{p.first}: {int(p.money)}"))
    return out


def check_world(seed, n=40, years=25):
    found = []
    w = G.run_world(seed, n, years, each_month=lambda w: found.extend(state_problems(w)))
    found.extend(event_problems(w))
    return w, found


def check_one(args):
    seed, n, years = args
    t0 = time.perf_counter()
    try:
        w, found = check_world(seed, n, years)
    except Exception as ex:  # a crash is a problem like any other
        import traceback
        where = traceback.extract_tb(ex.__traceback__)[-1]
        return {"seed": seed, "secs": time.perf_counter() - t0, "good": False, "events": 0, "people_ever": 0,
                "people_now": 0, "kinds": Counter(),
                "problems": [(f"crash: {type(ex).__name__} {ex}", f"line {where.lineno} {where.name}", where.line)]}
    sc = w.score()
    return {"seed": seed, "secs": time.perf_counter() - t0, "problems": found, "good": G.good(sc),
            "events": len(w.events), "people_ever": len(w.people), "people_now": len(w.here()),
            "kinds": Counter(e["kind"] for e in w.events)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns", type=int, default=200)
    ap.add_argument("--people", type=int, default=40)
    ap.add_argument("--years", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--seed", type=int)
    ap.add_argument("--first", type=int, default=900001)
    ap.add_argument("--save")
    a = ap.parse_args()
    if a.seed is not None:
        w, found = check_world(a.seed, a.people, a.years)
        for f in found:
            print(f)
        print(f"{len(found)} problems, {len(w.events)} events")
        return
    jobs = [(s, a.people, a.years) for s in range(a.first, a.first + a.towns)]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(check_one, jobs, chunksize=4))
    by = Counter()
    example = {}
    for r in res:
        for kind, *rest in r["problems"]:
            by[kind] += 1
            example.setdefault(kind, (r["seed"], *rest))
    print(f"{len(res)} raw towns of {a.people} over {a.years} years in {time.perf_counter() - t0:.0f} s "
          f"({sum(r['secs'] for r in res) / len(res):.2f} s each on one core)")
    print(f"pass the interest check: {sum(r['good'] for r in res) / len(res):.0%}")
    print(f"towns with a problem: {sum(1 for r in res if r['problems'])}, problems: {sum(by.values())}")
    for kind, n in by.most_common():
        print(f"  {n:6}  {kind}   e.g. seed {example[kind]}")
    if a.save:
        import json
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump({"towns": len(res), "people": a.people, "years": a.years, "months_checked": len(res) * a.years * 12,
                       "events_checked": sum(r["events"] for r in res), "problems": sum(by.values()),
                       "towns_with_problems": sum(1 for r in res if r["problems"]),
                       "event_checks": ["causes come first", "nobody unborn, dead or gone takes part",
                                        "no child in an adult event", "everyone in an event is named in its text",
                                        "no kin marry"],
                       "monthly_checks": ["spouses agree and are alive", "no child lives without a grown-up",
                                          "open shops have an owner in town", "workers are on one shop's books",
                                          "open debts, secrets, beliefs, courtships and affairs have people in town",
                                          "parents were 16 or older", "no two living people go by the same name",
                                          "money stays between -400 and 5,000", "nobody over 100"],
                       "by_kind": dict(by)}, f, indent=1)
    sys.exit(1 if by else 0)


if __name__ == "__main__":
    main()
