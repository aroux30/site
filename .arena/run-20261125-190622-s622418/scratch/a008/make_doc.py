# generator
OUT = '.arena/run-20261125-190622-s622418/r0/a008.md'
with open(OUT, 'w', encoding='utf-8') as out:
    out.write('')
def append(text):
    with open(OUT, 'a', encoding='utf-8') as out:
        out.write(text)
