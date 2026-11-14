"""fetch.py NAME GENERATION_ID URL  -> raw/NAME_tK.mp3 (+ manifest entry). Skips generation ids already fetched."""
import sys, os, json, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
MAN = os.path.join(RAW, "manifest.json")


def main(args):
    os.makedirs(RAW, exist_ok=True)
    man = json.load(open(MAN)) if os.path.exists(MAN) else {}
    for i in range(0, len(args), 3):
        name, gid, url = args[i : i + 3]
        if any(v["generation_id"] == gid for v in man.values()):
            print("have", name, gid)
            continue
        k = 1
        while f"{name}_t{k}.mp3" in man or os.path.exists(os.path.join(RAW, f"{name}_t{k}.mp3")):
            k += 1
        fn = f"{name}_t{k}.mp3"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        open(os.path.join(RAW, fn), "wb").write(data)
        man[fn] = {"name": name, "take": k, "generation_id": gid}
        print("got", fn, len(data))
    json.dump(man, open(MAN, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
