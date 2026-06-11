# How to Deploy the Valence Bot to Render (Step-by-Step)

## The Problem
Running the bot from `start_bot.bat` on your laptop means it dies when your PC sleeps or shuts down. You need to deploy it to Render so it runs 24/7.

---

## Step 1: Create a Render Account
1. Go to https://render.com
2. Sign up with your GitHub account (the one that owns this repo)

## Step 2: Create a New Web Service
1. Click **"New +"** > **"Web Service"**
2. Connect your GitHub account if prompted
3. Select the repository: **`valence-study-bot`**
4. Configure these settings:
   - **Name:** `valence-study-bot`
   - **Region:** Singapore (closest to India)
   - **Branch:** `main`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** **Free**

## Step 3: Add Environment Variables
In the Render dashboard, go to the **"Environment"** tab and add:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | Your Discord bot token (starts with `MTUx...`) |
| `LEADERBOARD_CHANNEL_ID` | `1514208164071870514` |
| `LOG_CHANNEL_ID` | `1514208220946763807` |
| `CELEBRATION_CHANNEL_ID` | `1514208252760424591` |

## Step 4: Deploy
1. Click **"Create Web Service"**
2. Wait for the build to finish
3. You should see `Valence Bot -- Online` in the Render logs

## Step 5: Set Up UptimeRobot
Render free tier sleeps after 15 min of no traffic. The bot has a built-in keep-alive server. Ping it:
1. Go to https://uptimerobot.com > create a free account
2. Click **"Add New Monitor"**
3. Type: **HTTP(s)**
4. Name: `Valence Bot`
5. URL: Your Render URL (e.g. `https://valence-study-bot.onrender.com`)
6. Interval: **5 minutes**
7. Click **"Create Monitor"**

## Step 6: Verify
- Bot shows **Online** in Discord with green dot
- Type `/stats` in Discord - should respond
- Join a Study voice channel - bot tracks your time
- Check Render logs for: `Loaded Discipline Extension` and `Loaded Gaming Extension`

## Step 7: Stop the Local Bot
Once Render is running, **close `start_bot.bat`** on your laptop. You cannot run two instances of the same bot token.

---

## Discord Role Hierarchy (IMPORTANT)
For the bot to assign milestone roles (Bronze Scholar, Silver Grinder, etc.), the bot's role in Discord must be **ABOVE** all milestone roles.

1. Go to Discord > Server Settings > Roles
2. Find the bot's role (usually named after the bot)
3. **Drag it above** Bronze Scholar, Silver Grinder, Gold Grinder, Diamond Grindmaster, and Legendary Studier
4. Also drag it above all Doubt roles and Text Activity roles
5. Click Save

Without this, Discord blocks the bot from assigning ANY roles.

---

## Common Issues
- **Bot shows offline:** Check Render logs. Most likely `BOT_TOKEN` is wrong.
- **Slash commands missing:** Wait 1-2 min after first boot for Discord to sync.
- **Roles not assigned:** Fix the role hierarchy (see above).
- **Two bots online:** You're running both Render AND `start_bot.bat`. Stop one.
