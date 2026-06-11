# Yeolpumta (YPT) Discord Study Bot Context

## Project Overview
This project is a complete, production-ready Discord bot written in Python that replicates the core functionality of the **Yeolpumta (YPT) mobile study tracker app** entirely within a private Discord server (for two users: Valence and Ujjwal). 

The bot is designed to run 24/7 on a cloud platform (e.g., Render, Replit) and features an embedded keep-alive web server to avoid sleeping. All study tracking data is saved persistently in a local `study_data.json` file.

## Architecture
The bot uses a **cog-based modular architecture**. The main bot logic lives in `bot.py`, while new feature modules are loaded as Discord.py extensions (cogs) from the `cogs/` directory via `setup_hook`.

### File Structure
```
valence-study-bot/
├── bot.py                  # Main bot script (core tracking, commands, events)
├── cogs/
│   ├── discipline.py       # Discipline enforcement module (Gemini)
│   └── gaming.py           # Gaming/chess tracking module (Gemini)
├── study_data.json         # Persistent data store
├── requirements.txt        # Python dependencies
├── render.yaml             # Render deployment config
├── runtime.txt             # Python runtime version
├── context.md              # This file
├── .env                    # Environment variables (BOT_TOKEN, channel IDs)
├── .env.example            # Env template
├── .gitignore              # Git ignore rules
└── start_bot.bat           # Windows startup script
```

## Detailed Changes and Features Implemented
The bot has been extensively iterated upon. Here is the full breakdown of features:

### 1. Channel Types and Tracking Mechanics
- **Study Voice Channels (`STUDY_CHANNELS`):** Tracks total time spent. Counts towards all-time, weekly, and daily study statistics. Triggers streak updates. Includes both "Study Room" (1514208313452007514) and "Group Study" (1514596473629708298).
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

## Cog Modules (Gemini Extensions)

### 7. Discipline Cog (`cogs/discipline.py`)
A daily discipline enforcement system that runs automatically at midnight IST.

- **Daily Check Loop:** Runs every 10 minutes. At midnight IST, it checks each user's study time for the previous day.
- **Zero-Hour Punishment:** If a user studied 0 hours the previous day:
  - They receive a harsh DM embed showing their 0 hours vs. their partner's hours.
  - A "discipline strike" is added to their record.
- **Strike System:**
  - **Strike 1-2:** DM warning with strike count.
  - **Strike 3:** Public warning posted in General channel that the user will be kicked if they don't study today.
  - **Strike 4:** Auto-kick from the server with a public announcement.
- **Strike Reset:** If a user studies any amount on a given day, their strikes reset to 0.
- **Target Users:** Valence (856485470171299891) and Ujjwal (1403716456025165864).

### 8. Gaming Cog (`cogs/gaming.py`)
A competitive gaming tracker for board game breaks between study sessions.

- **`/link_chess`**: Links a user's Lichess or Chess.com account for auto-tracking.
- **`/game_match`**: Manually starts a game match between two users (any game/format).
- **`/game_result`**: Manually records the winner/loser of a game. Updates win/loss stats in `study_data.json`.
- **Voice Channel Listener:** When a user joins a game voice channel (Chess, Shogi, GO, Checkers), the bot sends a message prompting them to use `/game_match`.
- **Lichess Auto-Poll (`chess_poll_loop`):** Every 5 minutes, polls the Lichess API for the latest game between the two linked users. If a new game is found, it auto-resolves the result and posts an announcement. Maintains a list of processed game IDs to avoid duplicates.
- **Game Channels Tracked:**
  - Chess (1514624613743857775)
  - Shogi (1514624657935044738)
  - GO (1514624725102628945)
  - Checkers (1514624781692178683)
