# 🚀 Valence YPT Discord Study Bot

A feature-rich, production-ready Discord bot designed to track study sessions, motivate partners, enforce daily discipline, and gamify study routines. Built using `discord.py` and fully integrated with **Google Cloud Firestore (Firebase)** for persistent data storage.

---

## ✨ Core Features

### 1. 📚 Gamified Milestone Roles
The bot automatically tracks weekly study time and awards milestone roles. Only the highest earned tier is kept, and roles reset every Monday at 12:00 AM IST.
*   **🥉 Bronze Scholar** — 5 hours/week
*   **🥈 Silver Grinder** — 15 hours/week
*   **🥇 Gold Grinder** — 30 hours/week
*   **💎 Diamond Grindmaster** — 50 hours/week
*   **👑 Legendary Studier** — 70 hours/week

### 2. 🧠 Doubt Session Roles
Awarded based on weekly study time logged inside designated **Doubt channels**:
*   **🟢 Doubt Beginner** — 1 hour/week
*   **🧠 Doubt Explorer** — 3 hours/week
*   **💡 Doubt Master** — 5 hours/week
*   **🎓 Doubt Professor** — 10 hours/week
*   **🧿 Never Had a Doubt** — 15 hours/week

### 3. 🛡️ Enforced slacker discipline
Enforces daily study targets (default: 1.5 hours/day) with a strike system:
*   **Strike warning**: Slacker DMs and group channel warnings.
*   **Strike reset**: Automatically clears strikes on days you meet the goal.
*   **Auto-Kick**: At 4 consecutive slacker strikes, the bot issues a permanent server invite link to the slacker, logs the action, and **kicks them** from the server.

### 4. ⏰ Hourly Absence Nags
Pings users who haven't studied yet today.
*   **Schedule**: Runs hourly between **2:00 PM and 10:00 PM IST** on Wednesday, Saturday, and Sunday.
*   **Visual Urgency**: Escalates color-coded embed warnings from **Green** (2 PM) to **Dark Red** (10 PM).

### 5. ♟️ Chess (Lichess) Integration
*   Automatically polls Lichess every 5 minutes for head-to-head matches between Valence and Ujjwal.
*   Logs wins/losses and announces game completions in a designated Discord channel.
*   Link Lichess profiles using `/chess link`.

---

## 🛠️ Slash Commands

| Command | Description |
|---|---|
| `/stats [user]` | Displays comprehensive study stats (today, weekly, all-time, subjects). |
| `/history [user]` | Shows a log of the last 10 study sessions. |
| `/compare [user]` | Head-to-head stats comparison between two users. |
| `/whowon` | Live weekly duel standings (who studied more this week). |
| `/flex [user]` | Generates a dramatic showcase card highlighting your best stats. |
| `/predict [user]` | Predicts end-of-week study hours based on current session pace. |
| `/countdown` | Configure and check countdowns for exams. |
| `/motivate` | Sends a random curated motivational quote. |
| `/pomodoro start` | Launches a background Pomodoro timer (DM alerts on phase changes). |
| `/pomodoro status` | Displays active clocks for group and personal Pomodoros. |
| `/chess link` | Links your Chess.com/Lichess account. |
| `/serverstats` | Shows aggregate server-wide study statistics. |

---

## 🚀 Deployment Guide (Render)

This bot is configured to run 24/7 on **Render (Free Tier)** without sleeping by leveraging a keep-alive server on port `8080` coupled with UptimeRobot.

### 1. Render Configuration
*   **Runtime**: `Python`
*   **Build Command**: `pip install -r requirements.txt`
*   **Start Command**: `python bot.py`

### 2. Environment Variables Required
Configure the following in the Render **Environment** tab:
| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Discord developer portal bot token. |
| `LEADERBOARD_CHANNEL_ID` | Channel ID where weekly summaries are posted. |
| `LOG_CHANNEL_ID` | Channel ID for session and audit logs. |
| `CELEBRATION_CHANNEL_ID` | Channel ID where milestones are announced. |
| `FIREBASE_CREDENTIALS` | The raw text contents of your Firebase service account key JSON file. |

### 3. Prevent Sleeping (UptimeRobot)
Create a free monitor on **UptimeRobot** pointing to your Render service URL (e.g., `https://your-service.onrender.com`) running on a **5-minute** interval.
