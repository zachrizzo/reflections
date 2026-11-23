"""Stress tests for the generator. Throwaway spike tool.

  1. Determinism: the same seed builds the same town in two separate processes
     with different Python hash seeds.
  2. Golden file: digests of ten towns and the first numbers from the random
     generator, for checking a C++ port against this reference.
  3. Sizes: towns of 20, 40, 80 and 160 people, all run through check.py,
     with time per town and how busy the town is per person.

    python stress.py            # writes out/stress.json and out/golden.json
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import check
import gen_lives as G

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def digest(w):
    blob = json.dumps(w.events, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def digests_in_child(hashseed, seeds):
    code = ("import json, gen_lives as G, stress as S; "
            f"print(json.dumps([S.digest(G.run_world(s)) for s in {list(seeds)}]))")
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def golden():
    towns = []
    for s in range(1, 11):
        w = G.run_world(s)
        towns.append({"seed": s, "events": len(w.events), "people_ever": len(w.people), "sha256": digest(w),
                      "first_events": [e["text"] for e in w.events[:8]], "last_event": w.events[-1]["text"],
                      **({"all_events": w.events} if s <= 3 else {})})
    r = G.Rng(1)
    rng = {"seed": 1, "u64": [str(r.u64()) for _ in range(5)],
           "random_after": [G.Rng(1).random()], "randint_1_6": [G.Rng(7).randint(1, 6) for _ in range(1)]}
    return {"note": "Reference output of gen_lives.py run_world(seed), 40 people, 25 years. "
                    "sha256 is over json.dumps(events, sort_keys=True, ensure_ascii=False).",
            "rng": rng, "towns": towns}


def sizes(jobs):
    plan = [(20, 196), (40, 196), (80, 56), (160, 14)]
    rows = []
    with ProcessPoolExecutor(jobs) as ex:
        for n, count in plan:
            t0 = time.perf_counter()
            res = list(ex.map(check.check_one, [(700001 + i, n, 25) for i in range(count)]))
            kinds = Counter()
            for r in res:
                kinds.update(r["kinds"])
            person_years = sum(r["people_ever"] for r in res) * 25
            rows.append({
                "people": n, "towns": count, "problems": sum(len(r["problems"]) for r in res),
                "secs_per_town": round(sum(r["secs"] for r in res) / count, 2),
                "pass_rate": round(sum(r["good"] for r in res) / count, 2),
                "events_per_person_year": round(sum(r["events"] for r in res) / person_years, 3),
                "people_now_vs_target": round(sum(r["people_now"] for r in res) / (count * n), 2),
                "killings_per_town": round(kinds["killing"] / count, 2),
                "thefts_per_100_people": round(100 * kinds["theft"] / (count * n), 1),
                "marriages_per_100_people": round(100 * (kinds["marriage"] + kinds["elope"] + kinds["runaway"]) / (count * n), 1),
                "wall_secs": round(time.perf_counter() - t0, 1),
            })
            print(rows[-1], flush=True)
    return rows


def main():
    jobs = max(1, (os.cpu_count() or 2) - 2)
    a = digests_in_child(1, range(1, 6))
    b = digests_in_child(98765, range(1, 6))
    same = a == b
    print("deterministic across processes:", same)
    gold = golden()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "golden.json"), "w", encoding="utf-8") as f:
        json.dump(gold, f, indent=1, ensure_ascii=False)
    same_in_process = all(t["sha256"] == d for t, d in zip(gold["towns"], a))
    print("golden matches the child runs:", same_in_process)
    rows = sizes(jobs)
    with open(os.path.join(OUT, "stress.json"), "w", encoding="utf-8") as f:
        json.dump({"deterministic": same and same_in_process, "sizes": rows}, f, indent=1)
    sys.exit(0 if same and same_in_process and not any(r["problems"] for r in rows) else 1)


if __name__ == "__main__":
    main()
