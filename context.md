# Yeolpumta (YPT) Discord Study Bot Context

## Project Overview
This project is a complete, production-ready Discord bot written in Python that replicates the core functionality of the **Yeolpumta (YPT) mobile study tracker app** entirely within a private Discord server (for two users: Valence and Ujjwal). 

The bot is designed to run 24/7 on a cloud platform (e.g., Render, Replit) and features an embedded keep-alive web server to avoid sleeping. All study tracking data is saved persistently in a local `study_data.json` file.

## Detailed Changes and Features Implemented
The bot has been extensively iterated upon. Here is the full breakdown of features added to `bot.py` in extreme detail:

### 1. Channel Types and Tracking Mechanics
- **Study Voice Channels:** Tracks total time spent. Counts towards all-time, weekly, and daily study statistics. Triggers streak updates.
- **Group Pomodoro Channel (`1514244606827561171`):** Features an **absolute clock** (60 minutes study / 10 minutes break) tied to Unix epoch time. When users join, the bot dynamically calculates their actual study time (excluding breaks). 
  - Updates the channel's status every 30 seconds (e.g., "🔴 Study Time — 45:00 left" or "🟢 Break Time — 08:00 left").
  - Sends phase transition alerts to the log channel mentioning active users.
- **Doubt Voice Channels:** Tracked separately from general study time. After a doubt session concludes, the bot posts an interactive **Subject Tag View** dropdown to the logs channel, allowing users to tag the session (Physics, Chemistry, Maths, Biology, CS, General). Time is then aggregated into `subject_hours`.
- **Discussion Voice Channels:** Only logs the time spent in the session for reference; does not count towards any study metrics or milestones.
- **Text Activity Tracking:** Tracks message counts in specific text channels (e.g., "Study Discussion"). Includes an anti-spam cooldown and message leaderboard.

### 2. Milestone and Role Gamification
- **Study Milestones:** Automatically awards standard Discord roles based on total study hours (from 10h to 2000h).
- **Doubt Milestones:** Separate roles for time spent answering/asking doubts (e.g., Doubt Beginner, Doubt Explorer... up to "Never Had a Doubt" at 50h).
- **Text Milestones:** Roles awarded based on the number of productive messages sent (e.g., Active Learner at 50 msgs to Study Sage at 1000 msgs).

### 3. Personal Pomodoro System
- Added an independent timer system for individuals using `/pomodoro start [study_min] [break_min]`. 
- Sends DMs when study and break phases toggle.
- Uses `active_pomodoros` dictionary and `asyncio.create_task()` to run in the background. 
- Auto-cancels the personal timer if the user joins the Group Pomodoro voice channel to enforce sync.
- Stopping the timer outputs a session completion embed to the logs channel with cycle counts and exact study durations.

### 4. Slash Commands and User Interface
- **`/stats`**: Displays the user's all-time, weekly, daily, and doubt stats, as well as their daily streak, next milestone progress, and tracked subject hours.
- **`/goal`**: Allows setting a personal daily study goal.
- **`/lb`**: Spawns an interactive leaderboard embed (buttons to switch between All-Time, Weekly, Daily, Doubts, and Messages).
- **`/leaderboard`**: A duplicate slash command allowing users to quickly summon the leaderboard in any channel.
- **`/heatmap`**: Renders a GitHub-style activity heatmap using Unicode blocks (🟩🟨⬛) showing study activity over the last year, replicating the YPT calendar feel.
- **`/whostudying`**: Lists who is currently in study or doubt channels and how long they've been there.
- **`/compare`**: Head-to-head comparison between two users' stats.
- **`/weeklygraph`**: Automatically generates a matplotlib bar chart (`weekly_graph.png`) of the last 7 days of study and sends it to the user.

### 5. Automated Background Tasks
- **Presence Rotation:** Cycles the bot's rich presence (e.g., "Watching Valence study", "Tracking 2 users").
- **Weekly Reset:** Clears weekly stats every Monday morning automatically.
- **Pomodoro Status Loop:** Maintains the API-driven voice channel status (Study/Break countdowns).
- **Weekly Graph DM (`weekly_graph_dm_loop`):** Set to automatically generate and send the `matplotlib` study graphs to all users via DM every Sunday at 9 PM IST.

### 6. Keep-Alive and Stability
- Contains a lightweight `aiohttp` web server running on port 8080.
- Implements **Crash Recovery**: On boot (`on_ready`), the bot checks `study_data.json` for orphaned sessions (where the bot crashed while a user was still in a voice channel) and automatically resets them to prevent corrupted 100-hour sessions.

## File Paths
Here are the absolute paths to all the files in this project to send to your friend:
- **Main Bot Script:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\bot.py`
- **Dependencies List:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\requirements.txt`
- **Database (JSON):** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\study_data.json`
- **Environment Variables:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\.env`
- **Env Template:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\.env.example`
- **Git Ignore:** `C:\Users\ROG\Documents\antigravity\serene-mendeleev\.gitignore`

*Note: Your friend will need to set up their own `.env` file with the `BOT_TOKEN` before running the bot.*
