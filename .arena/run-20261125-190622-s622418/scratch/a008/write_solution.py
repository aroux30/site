import sys
import os

target = ".arena/run-20261125-190622-s622418/r0/a008.md"

with open(target, "r", encoding="utf-8") as f:
    current = f.read()

print("Current file lines:", len(current.splitlines()))
