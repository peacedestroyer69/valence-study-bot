import os
import re

kick_templates = [
    "{username}, {hours_today}h today? That's how you prepare for JEE? Your {hours_alltime}h all-time is laughing at your {streak}-day streak. You've missed {missed_days} days. Get back to work.",
    "Is this a joke, {username}? {hours_today}h today won't even get you through the gate. {hours_alltime}h all-time means nothing if you drop your {streak}-day streak and miss {missed_days} days.",
    "Wake up, {username}. {hours_today}h is unacceptable. You have {hours_alltime}h all-time and a {streak}-day streak, yet you missed {missed_days} days. Stop slacking.",
    "You call yourself an aspirant, {username}? {hours_today}h today is pathetic. Don't let your {hours_alltime}h all-time go to waste over a {streak}-day streak and {missed_days} missed days.",
    "Excuses don't clear JEE, {username}. {hours_today}h today? Your {hours_alltime}h all-time, {streak}-day streak, and {missed_days} missed days show you're not serious.",
    "Top rankers don't sleep on {hours_today}h, {username}. With {hours_alltime}h all-time and a {streak}-day streak, missing {missed_days} days is a disgrace.",
    "{username}, {hours_today}h is a warm-up, not a day's work. You have {hours_alltime}h all-time, a {streak}-day streak, but {missed_days} missed days? Do better.",
    "This is why competition beats you, {username}. {hours_today}h today. {hours_alltime}h all-time. A {streak}-day streak ruined by {missed_days} missed days. Fix it.",
    "Do you want to fail, {username}? Because {hours_today}h today is how you fail. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Prove you belong here.",
    "{username}, you're embarrassing yourself. {hours_today}h today? Remember your {hours_alltime}h all-time and {streak}-day streak. Missing {missed_days} days is unacceptable.",
    "Is {hours_today}h your limit, {username}? Because JEE demands more. Your {hours_alltime}h all-time and {streak}-day streak are overshadowed by {missed_days} missed days.",
    "Stop pretending to study, {username}. {hours_today}h today is fake effort. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Get serious.",
    "{username}, {hours_today}h today is an insult to your goals. You've built {hours_alltime}h all-time and a {streak}-day streak. Don't let {missed_days} missed days destroy it.",
    "You're falling behind, {username}. {hours_today}h today won't cut it. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Start working.",
    "{username}, JEE doesn't care about your {hours_today}h. It cares about results. Your {hours_alltime}h all-time and {streak}-day streak mean nothing with {missed_days} missed days.",
    "You think {hours_today}h is enough, {username}? You're delusional. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Wake up.",
    "{username}, your competition studied double your {hours_today}h today. Your {hours_alltime}h all-time and {streak}-day streak can't save you from {missed_days} missed days.",
    "This is mediocrity, {username}. {hours_today}h today? With {hours_alltime}h all-time and a {streak}-day streak, missing {missed_days} days is pathetic.",
    "{username}, {hours_today}h is the bare minimum. You have {hours_alltime}h all-time and a {streak}-day streak. Don't throw it away on {missed_days} missed days.",
    "Are you even trying, {username}? {hours_today}h today. {hours_alltime}h all-time. {streak}-day streak. {missed_days} missed days. Do you want this or not?",
    "{username}, {hours_today}h today is a joke. Your {hours_alltime}h all-time and {streak}-day streak demand respect. Missing {missed_days} days is disrespecting yourself.",
    "You're wasting time, {username}. {hours_today}h today. {hours_alltime}h all-time. {streak}-day streak. {missed_days} missed days. Get to the desk.",
    "{username}, {hours_today}h today is a ticket to failure. You have {hours_alltime}h all-time and a {streak}-day streak. Don't let {missed_days} missed days define you.",
    "Is this your best, {username}? {hours_today}h today? Your {hours_alltime}h all-time and {streak}-day streak say otherwise. {missed_days} missed days is unacceptable.",
    "{username}, {hours_today}h today? You're playing games with your future. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Stop playing."
]

wakeup_templates = [
    "Good morning {username}. You did {yesterday_hours}h yesterday. Your streak is {streak}. Today's goal is {goal_hours}h. Let's conquer.",
    "Wake up {username}! {yesterday_hours}h yesterday was just the start. Keep your {streak}-day streak alive. Hit {goal_hours}h today.",
    "The sun is up, {username}. You logged {yesterday_hours}h yesterday with a {streak}-day streak. Time to aim for {goal_hours}h today.",
    "{username}, morning! {yesterday_hours}h yesterday is history. Your {streak}-day streak needs {goal_hours}h today to survive.",
    "Rise and grind {username}. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal for today is waiting.",
    "Time to work {username}. You hit {yesterday_hours}h yesterday and hold a {streak}-day streak. Get that {goal_hours}h today.",
    "{username}, the competition is already awake. {yesterday_hours}h yesterday, {streak}-day streak. Achieve {goal_hours}h today.",
    "Morning {username}. {yesterday_hours}h yesterday is in the past. Focus on your {streak}-day streak and {goal_hours}h goal today.",
    "Wakey wakey {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's smash the {goal_hours}h target today.",
    "{username}, time to study. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal won't achieve itself.",
    "Good morning {username}. Building on {yesterday_hours}h yesterday and a {streak}-day streak. Target: {goal_hours}h today.",
    "Rise {username}. {yesterday_hours}h yesterday, {streak}-day streak. Make today count with {goal_hours}h.",
    "{username}, start strong. {yesterday_hours}h yesterday, {streak}-day streak. Focus on your {goal_hours}h goal.",
    "Morning {username}! {yesterday_hours}h yesterday, {streak}-day streak. Let's get to {goal_hours}h today.",
    "Wake up {username}. {yesterday_hours}h yesterday, {streak}-day streak. Time to conquer {goal_hours}h today.",
    "{username}, the grind starts now. {yesterday_hours}h yesterday, {streak}-day streak. Aim for {goal_hours}h.",
    "Morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Today's mission: {goal_hours}h.",
    "Rise and shine {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's hit {goal_hours}h today.",
    "{username}, time to focus. {yesterday_hours}h yesterday, {streak}-day streak. Target: {goal_hours}h.",
    "Good morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal awaits.",
    "Wake up {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's achieve {goal_hours}h today.",
    "{username}, morning! {yesterday_hours}h yesterday, {streak}-day streak. Time to work for {goal_hours}h.",
    "Rise {username}. {yesterday_hours}h yesterday, {streak}-day streak. Focus on {goal_hours}h today.",
    "{username}, start your day. {yesterday_hours}h yesterday, {streak}-day streak. Target: {goal_hours}h.",
    "Morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's smash {goal_hours}h today."
]

dropped_off_templates = [
    "{username}, you did {hours_today}h but you're {gap}h short of your {goal_hours}h goal. You have {hours_left}h left at {time_str}. Get back to work.",
    "Why stop now, {username}? {hours_today}h is good, but you need {gap}h more for your {goal_hours}h goal. {hours_left}h left ({time_str}).",
    "{username}, don't quit early. {hours_today}h done, {gap}h to go for {goal_hours}h. It's {time_str}, you have {hours_left}h left.",
    "You're not done, {username}. {hours_today}h is a start. Close the {gap}h gap to {goal_hours}h. {hours_left}h left at {time_str}.",
    "{username}, get back in there. {hours_today}h done, {gap}h left for your {goal_hours}h goal. {hours_left}h remaining ({time_str}).",
    "Don't lose momentum, {username}. {hours_today}h done, {gap}h to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you left early. {hours_today}h done, {gap}h remaining for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Finish what you started, {username}. {hours_today}h done, {gap}h to go for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, the day isn't over. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).",
    "Keep going, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you're almost there. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't stop, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, get back to it. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).",
    "Stay focused, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you can do more. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't give up, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, push through. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).",
    "Keep pushing, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you're close. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't let up, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, stay strong. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).",
    "Keep working, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you've got this. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't stop now, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, finish strong. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str})."
]

not_started_templates = [
    "{username}, it's {time_str} and you have 0 hours. You have {hours_left}h left to hit your {goal_hours}h goal. Start now.",
    "Zero hours, {username}? At {time_str}? You have {hours_left}h left for your {goal_hours}h goal. Get moving.",
    "{username}, 0 hours at {time_str} is unacceptable. {hours_left}h left to reach {goal_hours}h. Work.",
    "What are you doing, {username}? 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Start studying.",
    "{username}, it's {time_str} and you haven't started. {hours_left}h left to hit {goal_hours}h. Go.",
    "0 hours logged, {username}. It's {time_str}. You have {hours_left}h left for your {goal_hours}h goal. Begin.",
    "{username}, stop wasting time. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h. Study.",
    "Unacceptable, {username}. 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Get to work.",
    "{username}, you're falling behind. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h. Start.",
    "0 hours, {username}. Seriously? It's {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    "{username}, it's {time_str} and you have 0 hours. {hours_left}h left to reach {goal_hours}h. Work now.",
    "Stop procrastinating, {username}. 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Study.",
    "{username}, 0 hours at {time_str} is a joke. {hours_left}h left to hit {goal_hours}h. Start.",
    "What's your excuse, {username}? 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    "{username}, get to work. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h.",
    "0 hours, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Start studying.",
    "{username}, you're wasting the day. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h.",
    "Unbelievable, {username}. 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    "{username}, start now. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h.",
    "0 hours logged, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Work.",
    "{username}, stop stalling. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h.",
    "This is bad, {username}. 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    "{username}, it's {time_str} and 0 hours. {hours_left}h left to reach {goal_hours}h. Study.",
    "0 hours, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Get moving.",
    "{username}, start working. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h."
]

goal_congrats_templates = [
    "Awesome job {username}! You hit {hours_today}h today, crushing your {goal_hours}h goal.",
    "Congratulations {username}! {hours_today}h logged today. Your {goal_hours}h goal is done.",
    "{username}, you did it! {hours_today}h today, beating your {goal_hours}h goal. Great work.",
    "Way to go {username}! {hours_today}h today. You smashed your {goal_hours}h goal.",
    "Excellent work {username}! {hours_today}h logged. Your {goal_hours}h goal is history.",
    "{username}, fantastic job! {hours_today}h today, surpassing your {goal_hours}h goal.",
    "Brilliant {username}! {hours_today}h today. You crushed your {goal_hours}h goal.",
    "Great effort {username}! {hours_today}h logged today, beating your {goal_hours}h goal.",
    "{username}, superb work! {hours_today}h today. You smashed your {goal_hours}h goal.",
    "Outstanding {username}! {hours_today}h today, crushing your {goal_hours}h goal.",
    "Phenomenal {username}! {hours_today}h logged. Your {goal_hours}h goal is done.",
    "{username}, incredible job! {hours_today}h today, beating your {goal_hours}h goal.",
    "Amazing {username}! {hours_today}h today. You smashed your {goal_hours}h goal.",
    "Top notch {username}! {hours_today}h logged today, surpassing your {goal_hours}h goal.",
    "{username}, stellar work! {hours_today}h today. You crushed your {goal_hours}h goal.",
    "Fantastic {username}! {hours_today}h today, beating your {goal_hours}h goal.",
    "Superb {username}! {hours_today}h logged. Your {goal_hours}h goal is history.",
    "{username}, excellent job! {hours_today}h today, smashing your {goal_hours}h goal.",
    "Brilliant effort {username}! {hours_today}h today. You crushed your {goal_hours}h goal.",
    "Great job {username}! {hours_today}h logged today, surpassing your {goal_hours}h goal.",
    "{username}, awesome work! {hours_today}h today. You smashed your {goal_hours}h goal.",
    "Outstanding effort {username}! {hours_today}h today, beating your {goal_hours}h goal.",
    "Phenomenal work {username}! {hours_today}h logged. Your {goal_hours}h goal is done.",
    "{username}, incredible effort! {hours_today}h today, surpassing your {goal_hours}h goal.",
    "Amazing job {username}! {hours_today}h today. You crushed your {goal_hours}h goal."
]

push_past_limit_templates = [
    "{username}, you hit {hours_today}h and your {goal_hours}h goal, but you have {hours_left}h left. Push for {extra_target}h.",
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. With {hours_left}h left, aim for {extra_target}h.",
    "{username}, {hours_today}h is good, but your {goal_hours}h goal is just a milestone. {hours_left}h left. Hit {extra_target}h.",
    "You reached {goal_hours}h, {username}. Currently at {hours_today}h. {hours_left}h remaining. Go for {extra_target}h.",
    "{username}, {hours_today}h logged. {goal_hours}h achieved. You have {hours_left}h left. Can you reach {extra_target}h?",
    "Don't stop at {goal_hours}h, {username}. {hours_today}h done, {hours_left}h left. Push to {extra_target}h.",
    "{username}, you beat your {goal_hours}h goal with {hours_today}h. With {hours_left}h left, target {extra_target}h.",
    "Good work on {goal_hours}h, {username}. {hours_today}h done. {hours_left}h remaining. Aim for {extra_target}h.",
    "{username}, {hours_today}h logged. {goal_hours}h crushed. You have {hours_left}h left. Hit {extra_target}h.",
    "Keep going, {username}. {goal_hours}h done, currently at {hours_today}h. {hours_left}h left. Go for {extra_target}h.",
    "{username}, you hit {hours_today}h and your {goal_hours}h goal. With {hours_left}h left, push for {extra_target}h.",
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. {hours_left}h remaining. Aim for {extra_target}h.",
    "{username}, {hours_today}h is good, but your {goal_hours}h goal is done. {hours_left}h left. Hit {extra_target}h.",
    "You reached {goal_hours}h, {username}. Currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.",
    "{username}, {hours_today}h logged. {goal_hours}h achieved. {hours_left}h remaining. Can you reach {extra_target}h?",
    "Don't stop at {goal_hours}h, {username}. {hours_today}h done, {hours_left}h left. Push to {extra_target}h.",
    "{username}, you beat your {goal_hours}h goal with {hours_today}h. {hours_left}h remaining. Target {extra_target}h.",
    "Good work on {goal_hours}h, {username}. {hours_today}h done. With {hours_left}h left, aim for {extra_target}h.",
    "{username}, {hours_today}h logged. {goal_hours}h crushed. {hours_left}h remaining. Hit {extra_target}h.",
    "Keep going, {username}. {goal_hours}h done, currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.",
    "{username}, you hit {hours_today}h and your {goal_hours}h goal. {hours_left}h remaining. Push for {extra_target}h.",
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. With {hours_left}h left, aim for {extra_target}h.",
    "{username}, {hours_today}h is good, but your {goal_hours}h goal is done. {hours_left}h remaining. Hit {extra_target}h.",
    "You reached {goal_hours}h, {username}. Currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.",
    "{username}, {hours_today}h logged. {goal_hours}h achieved. {hours_left}h remaining. Can you reach {extra_target}h?"
]

study_reminder_templates = [
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    "Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.",
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    "Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.",
    "{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}.",
    "Study reminder, {username}. {hours_today}h done, {gap}h to go at {time_str}.",
    "{username}, back to work. {hours_today}h logged, {gap}h gap. It's {time_str}.",
    "Keep pushing, {username}. {hours_today}h done, {gap}h remaining at {time_str}.",
    "{username}, don't stop. {hours_today}h logged, {gap}h to go. Time: {time_str}.",
    "Focus time, {username}. {hours_today}h done, {gap}h gap at {time_str}.",
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    "Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.",
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    "Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.",
    "{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}.",
    "Study reminder, {username}. {hours_today}h done, {gap}h to go at {time_str}.",
    "{username}, back to work. {hours_today}h logged, {gap}h gap. It's {time_str}.",
    "Keep pushing, {username}. {hours_today}h done, {gap}h remaining at {time_str}.",
    "{username}, don't stop. {hours_today}h logged, {gap}h to go. Time: {time_str}.",
    "Focus time, {username}. {hours_today}h done, {gap}h gap at {time_str}.",
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    "Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.",
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    "Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.",
    "{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}."
]

def format_list(name, templates):
    return f"{name} = [\n" + ",\n".join(f"    {repr(t)}" for t in templates) + "\n]\n\n"

content = ""
content += format_list("_FALLBACK_KICK_MESSAGES", kick_templates)
content += format_list("_FALLBACK_WAKEUP_MESSAGES", wakeup_templates)
content += format_list("_FALLBACK_DROPPED_OFF_MESSAGES", dropped_off_templates)
content += format_list("_FALLBACK_NOT_STARTED_MESSAGES", not_started_templates)
content += format_list("_FALLBACK_GOAL_CONGRATS_MESSAGES", goal_congrats_templates)
content += format_list("_FALLBACK_PUSH_PAST_LIMIT_MESSAGES", push_past_limit_templates)
content += format_list("_FALLBACK_STUDY_REMINDER_MESSAGES", study_reminder_templates)

with open(r"C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py", "r", encoding="utf-8") as f:
    original = f.read()

# Insert before # PERSONALIZED NOTIFICATION GENERATORS
insert_marker = "# ============================================================\n# PERSONALIZED NOTIFICATION GENERATORS"

if insert_marker in original:
    new_content = original.replace(insert_marker, content + insert_marker)
else:
    print("Marker not found")
    exit(1)

# Now update the functions to use the fallbacks wrapped in try-except

def replace_fallback(func_content, fallback_var, list_name, format_str):
    pattern = r"    fallback = \([\s\S]*?    \)"
    replacement = f'''    try:
        fallback = random.choice({list_name}).format({format_str})
    except KeyError:
        fallback = "Fallback error. Please check your inputs."'''
    return re.sub(pattern, replacement, func_content)

new_content = replace_fallback(new_content, "fallback", "_FALLBACK_KICK_MESSAGES", "username=username, hours_today=hours_today, hours_alltime=hours_alltime, streak=streak, missed_days=missed_days")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_WAKEUP_MESSAGES", "username=username, yesterday_hours=yesterday_hours, streak=streak, goal_hours=goal_hours")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_DROPPED_OFF_MESSAGES", "username=username, hours_today=hours_today, gap=gap, goal_hours=goal_hours, hours_left=hours_left, time_str=time_str")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_NOT_STARTED_MESSAGES", "username=username, time_str=time_str, hours_left=hours_left, goal_hours=goal_hours")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_GOAL_CONGRATS_MESSAGES", "username=username, hours_today=hours_today, goal_hours=goal_hours")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_PUSH_PAST_LIMIT_MESSAGES", "username=username, hours_today=hours_today, goal_hours=goal_hours, hours_left=hours_left, extra_target=extra_target")
new_content = replace_fallback(new_content, "fallback", "_FALLBACK_STUDY_REMINDER_MESSAGES", "username=username, hours_today=hours_today, gap=gap, time_str=time_str")

with open(r"C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py", "w", encoding="utf-8") as f:
    f.write(new_content)
