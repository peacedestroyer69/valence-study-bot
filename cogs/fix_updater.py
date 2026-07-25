import re

with open(r"C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py", "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    ("personalized_kick_msg", "_FALLBACK_KICK_MESSAGES", "username=username, hours_today=hours_today, hours_alltime=hours_alltime, streak=streak, missed_days=missed_days"),
    ("personalized_wakeup_msg", "_FALLBACK_WAKEUP_MESSAGES", "username=username, yesterday_hours=yesterday_hours, streak=streak, goal_hours=goal_hours"),
    ("dropped_off_reminder", "_FALLBACK_DROPPED_OFF_MESSAGES", "username=username, hours_today=hours_today, gap=gap, goal_hours=goal_hours, hours_left=hours_left, time_str=time_str"),
    ("not_started_reminder", "_FALLBACK_NOT_STARTED_MESSAGES", "username=username, time_str=time_str, hours_left=hours_left, goal_hours=goal_hours"),
    ("goal_congrats_msg", "_FALLBACK_GOAL_CONGRATS_MESSAGES", "username=username, hours_today=hours_today, goal_hours=goal_hours"),
    ("push_past_limit_msg", "_FALLBACK_PUSH_PAST_LIMIT_MESSAGES", "username=username, hours_today=hours_today, goal_hours=goal_hours, hours_left=hours_left, extra_target=extra_target"),
    ("personalized_study_reminder", "_FALLBACK_STUDY_REMINDER_MESSAGES", "username=username, hours_today=hours_today, gap=gap, time_str=time_str")
]

for func, list_name, format_str in replacements:
    # Find the function definition
    func_pattern = f"(async def {func}\\b.*?\\n)(.*?)(    try:\\n        fallback = .*?\\n    except KeyError:\\n        fallback = .*?\\n)"
    replacement = f"\\1\\2    try:\n        fallback = random.choice({list_name}).format({format_str})\n    except KeyError:\n        fallback = \"Fallback error. Please check your inputs.\"\n"
    content = re.sub(func_pattern, replacement, content, count=1, flags=re.DOTALL)

with open(r"C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py", "w", encoding="utf-8") as f:
    f.write(content)
