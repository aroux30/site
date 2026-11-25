import sys, base64
chunk = sys.argv[1]
text = base64.b64decode(chunk).decode('utf-8')
with open('C:/Users/Administrator/Desktop/site/.claude/worktrees/busy-antonelli-be626e/.arena/run-20261125-190622-s622418/r0/a001.md', 'a', encoding='utf-8') as out:
    out.write(text)
print('OK:', len(text))
