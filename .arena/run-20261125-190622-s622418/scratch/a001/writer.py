import base64
def append_b64(b64_str):
    text = base64.b64decode(b64_str).decode('utf-8')
    with open('C:/Users/Administrator/Desktop/site/.claude/worktrees/busy-antonelli-be626e/.arena/run-20261125-190622-s622418/r0/a001.md', 'a', encoding='utf-8') as out:
        out.write(text)
    print('Appended:', len(text), 'chars')
