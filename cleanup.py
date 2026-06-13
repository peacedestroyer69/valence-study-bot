import re
import os

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# I need to fix `\"` to `"` and `\\n` to `\n` in my injected code.
content = content.replace(r'\"', '"')
content = content.replace(r'\n', '\n')

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)
