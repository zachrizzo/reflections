import sys
path, old_file, new_file = sys.argv[1:4]
s = open(path, encoding="utf-8").read()
old = open(old_file, encoding="utf-8").read().rstrip("\n")
new = open(new_file, encoding="utf-8").read().rstrip("\n")
assert s.count(old) == 1, s.count(old)
open(path, "w", encoding="utf-8").write(s.replace(old, new))
print("patched")
