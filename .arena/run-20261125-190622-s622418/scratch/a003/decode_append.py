import sys, base64
target = r".arena/run-20261125-190622-s622418/r0/a003.md"
data = base64.b64decode(sys.stdin.read().strip()).decode("utf-8")
with open(target, "a", encoding="utf-8") as out:
    out.write(data)
print(f"Appended {len(data)} characters")
