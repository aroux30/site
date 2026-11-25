import re

out_path = r"C:\Users\Administrator\Desktop\site\.claude\worktrees\busy-antonelli-be626e\.arena\run-20261125-190622-s622418\r0\a004.md"

def append_text(txt):
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(txt)

print("builder helper ready")
