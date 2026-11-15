"""Re-match every named person to the current audio roster (side + sex required; then age band, archetype, role words)."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import people_src as S
ROOT = r"C:\Users\zachc\Documents\Unreal Projects\reflections"
roster = json.load(open(os.path.join(ROOT, r"ArtDirection\Audio\data\voice_roster.json"), encoding="utf-8"))
FIXED = {"edie_bramley": "V012", "hester_quaile": "V020", "ada_pollard": "V011", "winnie_cobb": "V003", "bet_crawley": "V017",
         "agnes_moth": "V018", "ivy_harker": "V013", "walter_dunmore": "V072", "horace_pratt": "V064", "sid_kettle": "V074",
         "ned_lusk": "V068", "frank_dunning": "V075",
         "aldric_mayne": "V095", "bram_tolley": "V082", "cosmo_fennick": "V089", "damaris_hobb": "V036", "emeric_dunstan": "V083",
         "marjory_fennick": "V039"}
ORDER = ["ilse_varrow", "jory_pell", "goldie_fairweather", "maud_kettering", "pim_ashgrove", "kit_marrow", "fen_lowry",
         "sela_brask", "ros_thrale", "nell_bramley", "hal_fairweather", "petra_lisle", "lucan_marlowe", "corin_ashby",
         "tobias_quell", "barnaby_thrale", "odette_vane", "dov_merriman", "amos_saffery", "tobin_lark", "hollis_greave",
         "sorrel_vey", "mother_rook", "tilly_frane", "gunnar_skarre", "greta_holm", "brenna_cold", "marta_quarry", "dagny_thorn", "eskil_varn"]
band = lambda a: "young" if a < 30 else "adult" if a < 45 else "middle" if a < 65 else "older"
BANDS = ["young", "adult", "middle", "older"]
arch = {"Civilian": "civilian", "Caster": "civilian", "Guard": "guard", "Soldier": "soldier"}
voice_side = {p["id"]: p["side"] for p in S.PEOPLE}
taken = set(FIXED.values()); out = dict(FIXED)
people = {p["id"]: p for p in S.PEOPLE}
for pid in ORDER:
    p = people[pid]
    words = set(re.findall(r"[a-z]+", p["job"].lower()))
    best = None
    for v in roster:
        if v["VoiceId"] in taken or v["Side"] != p["side"] or v["Sex"] != p["sex"]: continue
        s = 0
        s -= 3 * abs(BANDS.index(v["AgeBand"]) - BANDS.index(band(p["age"])))
        s += 4 if v["Archetype"] == arch[p["look_role"]] else 0
        s += 3 * len(words & set(re.findall(r"[a-z]+", v["Role"].lower())))
        if best is None or s > best[0]: best = (s, v)
    out[pid] = best[1]["VoiceId"]; taken.add(best[1]["VoiceId"])
assert set(out) == set(people), set(people) - set(out)
for pid, vid in out.items():
    v = next(x for x in roster if x["VoiceId"] == vid)
    print(f"{pid:20} {people[pid]['age']:>2} {people[pid]['job'][:34]:34} -> {vid} {v['AgeBand']:6} {v['Archetype']:8} {v['Role']} | {v['Attitude']}")
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_map.json"), "w"), indent=1)
