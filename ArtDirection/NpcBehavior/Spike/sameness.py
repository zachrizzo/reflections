"""How samey are generated towns? Throwaway spike tool.

A "story shape" is three events in a row along a cause chain, by kind only,
for example theft -> blame -> peace. For each town we collect its set of
shapes, then compare towns pairwise: overlap is the share of shapes two towns
have in common (Jaccard). 0% means every town tells different stories; 100%
means every town tells the same ones.

    python sameness.py --towns 1000 --people 40 --save out/sameness_final.json

Also reports how often towns share a headline: the biggest story's three
most common kinds of event, leaving out everyday life.
"""
import argparse
import itertools
import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import gen_lives

SKIP = {"family"}  # founding facts, not stories
# everyday kinds that don't make a headline on their own
EVERYDAY = {"family", "birth", "death", "marriage", "courting", "peace", "friends", "apprentice", "hire",
            "arrival", "repay", "borrow", "inherit_wp", "adopt", "found"}


def shapes(events):
    byid = {e["id"]: e for e in events}
    out = set()
    for e in events:
        if e["kind"] in SKIP:
            continue
        for c1 in e["causes"]:
            a = byid[c1]
            for c2 in a["causes"]:
                b = byid[c2]
                if b["kind"] not in SKIP and a["kind"] not in SKIP:
                    out.add((b["kind"], a["kind"], e["kind"]))
    return out


def headline(w):
    """The biggest story's signature: its three most common kinds that aren't everyday life."""
    st = w.stories()
    if not st:
        return ()
    counts = Counter(w.events[i]["kind"] for i in st[0]["events"] if w.events[i]["kind"] not in EVERYDAY)
    return tuple(sorted(k for k, _ in counts.most_common(3)))


def one(args):
    seed, people, years = args
    t0 = time.perf_counter()
    w, rerolls = gen_lives.build(seed, people, years)
    return {"tries": rerolls + 1, "shapes": shapes(w.events), "kinds": Counter(e["kind"] for e in w.events),
            "headline": headline(w), "secs": time.perf_counter() - t0, "passed": gen_lives.good(w.score())}


def run(towns, people, years, first=5001, jobs=None):
    jobs = jobs or max(1, (os.cpu_count() or 2) - 2)
    with ProcessPoolExecutor(jobs) as ex:
        res = list(ex.map(one, [(s, people, years) for s in range(first, first + towns)], chunksize=2))
    sets = [r["shapes"] for r in res]
    tries = sum(r["tries"] for r in res)
    kinds = Counter()
    for r in res:
        kinds.update(r["kinds"])
    heads = Counter(r["headline"] for r in res)
    overlaps = [len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2) if a | b]
    count = Counter(sh for s in sets for sh in s)
    top = count.most_common(8)
    return {
        "towns": towns, "people": people,
        "keep_rate": round(towns / tries, 3),
        "never_passed": sum(1 for r in res if not r["passed"]),
        "secs_per_kept_town": round(sum(r["secs"] for r in res) / towns, 2),
        "headlines_distinct": len(heads),
        "headline_most_common": {"kinds": " + ".join(heads.most_common(1)[0][0]), "share": round(heads.most_common(1)[0][1] / towns, 3)},
        "same_headline_chance": round(sum((c / towns) ** 2 for c in heads.values()), 3),
        "top_headlines": [{"kinds": " + ".join(h), "share": round(c / towns, 3)} for h, c in heads.most_common(8)],
        "kind_in_headline": {k: round(v / towns, 3) for k, v in Counter(k for r in res for k in r["headline"]).most_common(12)},
        "shapes_total": len(count),
        "shapes_per_town": round(sum(len(s) for s in sets) / towns, 1),
        "overlap": round(sum(overlaps) / max(1, len(overlaps)), 3),
        "top": [{"shape": " → ".join(sh), "towns": n / towns} for sh, n in top],
        "kinds_used": len(kinds),
        "kinds": dict(kinds.most_common()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--towns", type=int, default=100)
    ap.add_argument("--people", type=int, default=5)
    ap.add_argument("--years", type=int, default=25)
    ap.add_argument("--save")
    ap.add_argument("--first", type=int, default=5001)
    a = ap.parse_args()
    r = run(a.towns, a.people, a.years, a.first)
    print(json.dumps({k: v for k, v in r.items() if k != "kinds"}, indent=1, ensure_ascii=False))
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
