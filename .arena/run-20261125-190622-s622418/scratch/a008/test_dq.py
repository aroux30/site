import sys
# In double-quoted EOF, $ and ` are not expanded!
s = "`test` $var"
print("Result:", s)
