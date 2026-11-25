import sys, os

out_path = r"C:\Users\Administrator\Desktop\site\.claude\worktrees\busy-antonelli-be626e\.arena\run-20261125-190622-s622418\r0\a003.md"
chunk = sys.stdin.read()
mode = sys.argv[1] if len(sys.argv) > 1 else "a"

with open(out_path, mode, encoding="utf-8") as f:
    f.write(chunk)

print(f"Written mode={mode}, size={os.path.getsize(out_path)}")
