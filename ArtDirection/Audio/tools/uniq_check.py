"""Uniqueness check across ALL baked speech: no two speakers may say the same sentence (user rule, 2026-11-14).

Normalisation: lowercase, curly quotes folded, inline tags removed (<sigh>), punctuation removed, whitespace collapsed,
"Lant-horn" folded to "lanthorne".
- EXACT duplicate across different speakers  -> FAIL (exit 1)
- exact duplicate within one speaker         -> FAIL too (a voice shouldn't repeat itself)
- NEAR duplicate across speakers             -> flagged: difflib ratio >= 0.88, or same first 4 words with token
                                                Jaccard >= 0.8, or the same set of words in a different order
Sources: voice/script/conversations.json, voice_lines.json (remarks, replies), barks.json (per-voice barks, possessed
mutters, fillers), and the shipped OpenAI single-character lines (Tarnish, narrator). The legacy OpenAI 6-slot barks are
included with --with-slot-barks.
    python uniq_check.py [--with-slot-barks] [--report path.json] [--quiet]
"""
import sys, os, json, re, difflib
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "voice", "script")
STOP = set("a an the and or but so to of in on at it its it's is are was be i i'm you your we our they them their he she "
           "his her my me this that there here what who for with not no do don't can't just get got oh ah well now then "
           "up out all".split())


def norm(t):
    t = t.lower().replace("’", "'").replace("‘", "'").replace("lant-horn", "lanthorne")
    t = re.sub(r"<[^>]*>", " ", t)
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    t = re.sub(r"(^| )'+|'+( |$)", " ", t)
    return " ".join(t.split())


_VOCAL = re.compile(r"^(?:a+r*g+h*|a+h+|a+|o+h+|o+|u+g+h+|u+h+|u+|n+g+h*|n+n+h*|h+n+g*h*|o+f+|o+w+|a+c?k+|g+a+h+|g+n+h*|"
                    r"h+u+p+|h+a+h*|h+e+h+|h+o+h*|e+r+g+h*|e+h+|e+|m+m+|h+m+|w+h+o+a+|g+r+r*|g+r+a+h+|r+a+h+|y+a+h+|"
                    r"e+e+k+|h+r+k+|k+h+|p+f+t*|f+f+|h+u+h+|h+i+|g+u+h+|w+a+h+|a+i+e+|h+n+n+g+h*|m+p+h+|h+m+p+h+|"
                    r"y+a+|a+h+a+|h+a+a+|o+o+f+|u+n+h+|g+a+|a+g+h+)$")


_WORDS = []


def _corpus_words():
    """Every token used as a word anywhere in the worded script (the wordless group itself left out)."""
    if not _WORDS:
        ws = set()
        for lid, _spk, text in collect():
            if not lid.startswith("B_React_Effort_"):
                ws.update(norm(text.replace("-", " ")).split())
        _WORDS.append(ws - {t for t in ws if _VOCAL.match(t)})
    return _WORDS[0]


def is_wordless(text):
    """True for a line made only of vocal sounds (Hnngh!, Oof!, HUK!, Ah-ah-AH!). These carry no phrase, so the
    no-shared-phrase rule does not apply to them (user rule: no two PHRASES the same across characters).
    A token is a sound if it matches the common vocal shapes, or is short and never used as a word in the script."""
    toks = norm(text.replace("-", " ")).split()
    if not toks:
        return False
    if all(_VOCAL.match(t) for t in toks):
        return True
    words = _corpus_words()
    return all(_VOCAL.match(t) or (t.isalpha() and len(t) <= 6 and t not in words) for t in toks)


def _j(name):
    p = os.path.join(SCRIPT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def collect(with_slot_barks=False):
    """[(line_id, speaker, text)] for every baked line. Story lines (S_, SB_) are protected; P_ persona replies are not.
    Generic lines that a named person's story lines replace are left out."""
    out = []
    try:
        import story_import as ST
        story = ST.load()
        sup = ST.suppressed(story)
        out += ST.story_lines(story)
    except Exception as e:
        print("note: story lines not loaded:", e)
        sup = set()
    for cid, c in _j("conversations.json").items():
        for k, conv in enumerate(c["Conversations"], 1):
            for n, l in enumerate(conv["Lines"], 1):
                out.append((f"A_{cid}_{k}_{n}", c["Voices"][l["S"] - 1], l["Text"]))
    for vid, d in _j("voice_lines.json").items():
        for kind, k1 in (("Remarks", "Remark"), ("Replies", "Reply")):
            if (k1, vid) in sup:
                continue
            for i, x in enumerate(d.get(kind, []), 1):
                out.append((f"R_{vid}_{k1}_{i}", vid, x["Text"] if isinstance(x, dict) else x))
    for vid, groups in _j("barks.json").items():
        for group, items in groups.items():
            if (group, vid) in sup:
                continue
            for i, x in enumerate(items, 1):
                out.append((f"B_{group}_{vid}_{i}", vid, x["Text"]))
    try:
        import voice_script as VS
        for lid, grp, spk, text in VS.LINES:
            if VS.base_group(grp) in VS.NPC_GROUPS:
                if with_slot_barks:
                    out.append((lid, "slot:" + grp.rsplit("_", 1)[1], text))
                continue
            if grp == "Story_Tarnish":
                continue  # already checked as S_<LineId> (speaker Tarnish)
            out.append((lid, "Tarnish" if lid.startswith("Tarnish") else "Narrator", text))
    except Exception as e:
        print("note: OpenAI lines not loaded:", e)
    return out


def near_pairs(items):
    """items: [(normtext, first_entry)] -> [(ratio, a_entry, b_entry)] for different speakers."""
    toks = [set(k.split()) for k, _ in items]
    index = defaultdict(list)
    for i, ts in enumerate(toks):
        for t in ts - STOP:
            index[t].append(i)
    seen, out = set(), []
    for i, (a, ea) in enumerate(items):
        cand = Counter()
        for t in toks[i] - STOP:
            if len(index[t]) < 400:
                cand.update(j for j in index[t] if j > i)
        if not toks[i] - STOP:  # all-stopword lines: compare against same-length lines by prefix
            cand.update(j for j in range(i + 1, len(items)) if items[j][0].split()[:2] == a.split()[:2])
        for j in cand:
            c, ec = items[j]
            if ea[1] == ec[1] or (i, j) in seen:
                continue
            seen.add((i, j))
            sa, sc = toks[i], toks[j]
            jac = len(sa & sc) / max(1, len(sa | sc))
            if jac < 0.45:
                continue
            ratio = difflib.SequenceMatcher(None, a, c).ratio()
            if ratio >= 0.88 or (a.split()[:4] == c.split()[:4] and jac >= 0.8) or (sa == sc and len(sa) >= 2):
                out.append((round(ratio, 2), ea, ec))
    return out


def check(lines):
    by_norm = defaultdict(list)
    for lid, spk, text in lines:
        if is_wordless(text):
            continue  # vocal sounds only (grunts, gasps): not a phrase
        by_norm[norm(text)].append((lid, spk, text))
    exact_cross, exact_self = [], []
    for k, group in by_norm.items():
        if len(group) > 1:
            (exact_cross if len({g[1] for g in group}) > 1 else exact_self).append(group)
    near = near_pairs([(k, g[0]) for k, g in by_norm.items() if k])
    return exact_cross, exact_self, near


def main(argv):
    lines = collect("--with-slot-barks" in argv)
    exact_cross, exact_self, near = check(lines)
    kinds = Counter(l[0].split("_")[0] if l[0].split("_")[0] in ("A", "R", "B", "S", "SB", "P", "SC", "C") else "OpenAI" for l in lines)
    print(f"lines checked: {len(lines)} ({dict(kinds)})  speakers: {len({l[1] for l in lines})}")
    print(f"EXACT duplicates across speakers: {len(exact_cross)}  within one speaker: {len(exact_self)}  "
          f"near-duplicates: {len(near)}")
    if "--quiet" not in argv:
        for g in (exact_cross + exact_self)[:20]:
            print("  EXACT:", " | ".join(f"{x[0]}({x[1]})" for x in g), "::", g[0][2][:80])
        for r, a, b in near[:20]:
            print(f"  near {r}: {a[0]}({a[1]}) '{a[2][:50]}'  ~  {b[0]}({b[1]}) '{b[2][:50]}'")
    if "--report" in argv:
        p = argv[argv.index("--report") + 1]
        json.dump({"lines": len(lines), "exact_cross": exact_cross, "exact_self": exact_self, "near": near},
                  open(p, "w", encoding="utf-8"), indent=1)
    return 1 if (exact_cross or exact_self) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
