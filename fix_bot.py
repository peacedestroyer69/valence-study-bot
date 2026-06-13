import pathlib
import os

bot_path = pathlib.Path("bot.py")

if not bot_path.exists():
    print("Error: bot.py not found in the current directory.")
    exit(1)

lines = bot_path.read_text(encoding="utf-8").splitlines(keepends=True)

# Find the FIRST occurrence of bot.run()
cut_idx = None
for i, line in enumerate(lines):
    if 'bot.run(os.getenv("BOT_TOKEN"))' in line:
        cut_idx = i + 1  # keep this line
        break

if cut_idx:
    kept = lines[:cut_idx]
    kept.append("\n")
    try:
        bot_path.write_text("".join(kept), encoding="utf-8")
        print(f"SUCCESS: Cleaned up bot.py! Truncated from {len(lines)} lines to {cut_idx} lines.")
    except Exception as e:
        print(f"FAILED to write to bot.py: {e}")
        print("Please ensure bot.py is not running or open in an editor, and try again.")
else:
    print("ERROR: Could not find bot.run(os.getenv(\"BOT_TOKEN\")) in bot.py")
