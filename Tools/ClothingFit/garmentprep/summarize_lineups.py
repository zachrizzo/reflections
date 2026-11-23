"""Short summary of one or more lineup tables (written by lineup_report.py).

  python summarize_lineups.py <title>=<Lineup_x.json> [<title>=<Lineup_y.json> ...] [--out Report.md]
Per garment: how many bodies pass each line of the bar, and which bodies and poses do not.
"""
import json
import sys
from pathlib import Path


def summarize(title, path):
    table = json.loads(Path(path).read_text())
    rows = {k: v for k, v in table.items() if "standing" in v}
    lines = [f"### {title}", ""]
    valid = {k: v for k, v in rows.items() if v.get("skeleton_matches_body", True)}
    standing = [k for k, v in rows.items() if v["standing"]["clear"] == v["standing"]["poses"]]
    under = [k for k, v in rows.items() if not any(v[c]["under_layer_poses"] for c in ("standing", "walk", "reach") if c in v)]
    lines.append(f"- bodies tested: {len(rows)}" + (f" ({len(rows) - len(valid)} with motion not valid)" if len(valid) < len(rows) else ""))
    lines.append(f"- standing, no garment triangle crosses skin: {len(standing)}/{len(rows)}"
                 + ("" if len(standing) == len(rows) else " (not: " + ", ".join(sorted(set(rows) - set(standing))) + ")"))
    lines.append(f"- layer underneath never crossed in 51 poses: {len(under)}/{len(rows)}"
                 + ("" if len(under) == len(rows) else " (crossed on: " + ", ".join(
                     f"{k} {max(rows[k][c]['under_layer_triangles_peak'] for c in ('standing', 'walk', 'reach'))} tris" for k in sorted(set(rows) - set(under))) + ")"))
    for clip in ("walk", "reach"):
        clear = [k for k, v in valid.items() if v[clip]["clear"] == v[clip]["poses"]]
        floor = [k for k, v in valid.items() if v[clip]["at_or_under_floor"] == v[clip]["poses"]]
        most = [k for k, v in valid.items() if v[clip]["at_or_under_floor"] >= .8 * v[clip]["poses"]]
        poses = sum(v[clip]["poses"] for v in valid.values())
        at = sum(v[clip]["at_or_under_floor"] for v in valid.values())
        depth = max((v[clip]["worst_depth_mm"], k, v[clip]["worst_pose"]) for k, v in valid.items())
        lines.append(f"- {clip}: bodies with zero non-arm crossings in all 25 poses: {len(clear)}/{len(valid)}; bodies at the body's own floor in all 25 poses: "
                     f"{len(floor)}/{len(valid)} (in at least 20 of 25: {len(most)}/{len(valid)}); poses at the floor overall: {at}/{poses}; "
                     f"deepest crossing {depth[0]:.0f} mm ({depth[1]} {depth[2]})")
    over = []
    for k, v in sorted(valid.items()):
        bad = {c: v[c]["over_floor"] for c in ("walk", "reach") if v[c]["over_floor"]}
        if bad:
            n = sum(len(x) for x in bad.values())
            first = ", ".join(f"{c} {len(x)}/25 (e.g. {x[0]})" for c, x in bad.items())
            where = max((v[c] for c in ("walk", "reach")), key=lambda r: r["worst_triangles"])["worst_where"]
            over.append((n, f"  - {k}: {first}; worst pose mostly {max(where, key=where.get) if where else 'none'}"))
    if over:
        lines.append(f"- bodies with poses above the floor ({len(over)}), worst first:")
        lines += [text for _, text in sorted(over, reverse=True)]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if "=" in a]
    text = "\n".join(summarize(*a.split("=", 1)) for a in args)
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(text, encoding="utf-8")
    print(text)
