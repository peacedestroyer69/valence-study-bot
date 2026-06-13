# Yeolpumta (YPT) Discord Study Bot — Ultimate Detailed Context

This document is the absolute ground-truth reference for the YPT Discord Study Bot built for the private 2-person server. It details every single ID, configuration, mechanic, and command implemented.

---

## 1. Environment & Project Files

The bot runs 24/7 on Python using `discord.py` and `aiohttp`. It avoids falling asleep on free cloud hosting by running a background keep-alive web server on port 8080.
- **Main Bot Script:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\bot.py`
- **Dependencies List:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\requirements.txt`
  - `discord.py>=2.0`, `aiohttp>=3.8`, `python-dotenv>=1.0`, `matplotlib>=3.7`
- **Database (JSON):** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\study_data.json`
- **Environment Variables:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\.env`
  - Requires `BOT_TOKEN`, `LEADERBOARD_CHANNEL_ID`, `LOG_CHANNEL_ID`, `CELEBRATION_CHANNEL_ID`

---

## 2. Hardcoded Discord IDs

### A. Users
- **Valence (`856485470171299891`)** — Custom Color: Discord Blurple (`#5865F2`)
- **Ujjwal (`1403716456025165864`)** — Custom Color: Discord Pink (`#EB459E`)

### B. Gamified Milestone Roles
Roles are awarded automatically when thresholds are passed. A celebration embed is sent to the Celebration Channel.

**1. Pure Study Roles (Awarded for total focused study hours)**
These roles represent your overall dedication to studying. They are awarded based on raw hours spent in the Study Room or Group Pomodoro.
- **5 hours:** `1514208595737182338` (🥉 Bronze Scholar) — *Context: You've taken the first steps. The journey has just begun.*
- **25 hours:** `1514208694051672195` (🥈 Silver Grinder) — *Context: You're starting to build a solid habit. Consistency is key.*
- **50 hours:** `1514210766256082954` (🥇 Gold Grinder) — *Context: A true milestone. You've proven your dedication to the grind.*
- **100 hours:** `1514208770887127192` (💎 Diamond Grindmaster) — *Context: Elite tier. Few make it this far. You are a master of focus.*
- **200 hours:** `1514208898406416505` (👑 Legendary Studier) — *Context: The absolute pinnacle. You are a legend of the server.*

**2. Doubt Roles (Awarded for total doubt session hours)**
These roles represent your collaborative effort in asking questions and solving problems with others in Doubt channels.
- **2 hours:** `1514228187352268830` (🔰 Doubt Beginner) — *Context: You're starting to engage and ask the right questions.*
- **5 hours:** `1514238409449930752` (🧠 Doubt Explorer) — *Context: You're actively exploring complex topics with your peers.*
- **10 hours:** `1514238834559291563` (💡 Doubt Master) — *Context: You've mastered the art of collaborative problem-solving.*
- **25 hours:** `1514238964008226988` (🎓 Doubt Professor) — *Context: You're essentially teaching the material at this point.*
- **50 hours:** `1514254737372090438` (🧿 Never Had a Doubt in Life) — *Context: You transcend confusion. You are the ultimate academic authority.*

**3. Text Activity Roles (Awarded for messages sent in `Study Discussion`)**
These roles represent your active participation in text-based study discussions.
- **50 messages:** `1514254760386236496` (📝 Active Learner) — *Context: You're participating and making your voice heard.*
- **200 messages:** `1514255291578056714` (💬 Discussion Pro) — *Context: A regular contributor. You keep the academic conversation flowing.*
- **500 messages:** `1514255438093484083` (🗣️ Knowledge Sharer) — *Context: A pillar of the community. Always there to share insights.*
- **1000 messages:** `1514255518288576672` (📖 Study Sage) — *Context: The wise elder of the text channels. Your word is law.*

---

## 3. Channel Mapping & Functionality

### A. Study Channels
- **`1514208313452007514` (Study Room)**
  - Full tracking. Counts toward all study milestones, daily goals, streaks, heatmaps, and leaderboard.
  - Automatically updates the bot's Rich Presence (e.g., "Watching Valence study").

### B. Group Pomodoro Voice Channel
- **`1514244606827561171`**
  - Uses an **absolute clock** locked to Unix epoch time to maintain a 24/7 continuous cycle of 60 minutes study followed by 10 minutes break.
  - The bot updates the channel's API voice status text every 30 seconds (e.g., "🔴 Study Time — 45:00 left").
  - The bot calculates exact study time based on when the user was present during the "study" phase, discarding all "break" phase minutes.
  - Sends Pings/Alerts into the Log channel when the phase transitions.
  - If a user joins this while running an individual `/pomodoro start`, the individual timer is auto-cancelled to enforce group sync.

### C. Doubt Channels
- **`1514222394628112536` (Test Discussion stuff)**
- **`1514186752301076510` (Doubt #1)**
- **`1514221019005714462` (Doubt #2)**
- **`1514221629864149084` (Doubt #3)**
  - Tracked separately. Adds up to `total_seconds_doubt`.
  - Upon leaving, posts a log embed featuring an **interactive Dropdown Menu** for the user to select the subject tag:
    - 🧪 Physics | ⚗️ Chemistry | 📐 Maths | 🧬 Biology | 💻 CS | 🌍 General
  - Selections permanently increment the user's `subject_hours` tracking.

### D. Discussion Channels (Voice)
- **`1514187630374289418` (General)**
  - Logs the session for the record, but does NOT grant any points, leaderboard ranking, or milestones.

### E. Text Channels (Tracking)
- **`1514241642415001610` (Study Discussion)**
  - The bot tracks the number of messages sent here.
  - Has a 3-second anti-spam cooldown limit.

---

## 4. Bot Slash Commands

1. **`/stats`**: Renders a comprehensive personal profile embed showing All-Time/Weekly/Daily study time, Doubt hours, Current Streak, Next Milestone progress bar, and Subject Breakdown hours.
2. **`/goal [minutes]`**: Set a personal daily study goal.
3. **`/lb`**: Spawns the persistent interactive Leaderboard embed. Features 5 buttons to toggle views between: `All-Time`, `Weekly`, `Daily`, `Doubts`, and `Messages`.
4. **`/leaderboard`**: Identical to `/lb`, allows summoning the leaderboard view into any text channel instantly.
5. **`/heatmap`**: Renders a GitHub-style calendar using Unicode blocks (🟩🟨⬛). The bot tracks `daily_history` internally per user to build a 52-week map of study activity intensity, perfectly replicating YPT.
6. **`/whostudying`**: Lists who is currently in a voice channel, what type of channel it is, and for how long.
7. **`/compare [user]`**: Head-to-head embed comparing your stats to the target user (e.g., Valence vs Ujjwal).
8. **`/pomodoro start [study_min] [break_min]`**: Starts a custom personal timer in the background. The bot DMs the user when phases change. 
9. **`/pomodoro stop`**: Prematurely ends the personal timer and logs the results.
10. **`/pomodoro status`**: Shows a combined view of both the Group Pomodoro absolute clock and the user's personal timer clock.
11. **`/weeklygraph`**: Immediately generates a `matplotlib` bar chart image of the last 7 days of study hours and sends it via DM.

---

## 5. Automated Background Tasks
- **`presence_rotation_loop`**: Cycles the bot's custom status message.
- **`check_weekly_reset`**: Runs every Monday to wipe `total_seconds_weekly` and `messages_weekly` so the leaderboards reset.
- **`pomodoro_status_loop`**: Updates the Group Pomodoro voice channel status every 30 seconds.
- **`weekly_graph_dm_loop`**: Every Sunday at 9 PM IST, automatically triggers `matplotlib` graph generation and sends the weekly breakdown graph directly to users' DMs.

---

## 6. Data Structure (`study_data.json`)
The bot automatically maintains this schema for every tracked user:
- `total_seconds_alltime`, `total_seconds_weekly`, `total_seconds_today`
- `total_seconds_doubt`, `total_seconds_discussion`
- `longest_session_seconds`, `best_day_seconds`, `session_count`
- `streak_current`, `streak_highest`, `last_study_date`
- `messages_alltime`, `messages_weekly`, `last_message_timestamp`
- `daily_goal`
- `daily_history` (Dictionary mapping `YYYY-MM-DD` strings to integer seconds for the Heatmap)
- `subject_hours` (Dictionary mapping subject tag strings to integer seconds)
