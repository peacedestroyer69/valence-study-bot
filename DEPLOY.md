# 🚀 How to Deploy the Valence Bot to Render (Step-by-Step)

## The Problem
Pushing code to GitHub does NOT automatically make the bot run. You need to connect your GitHub repo to a cloud hosting service like Render so it runs 24/7.

---

## Step-by-Step: Deploy to Render (Free Tier)

### Step 1: Create a Render Account
1. Go to https://render.com
2. Sign up with your GitHub account (the one that owns `peacedestroyer69/valence-study-bot`)

### Step 2: Create a New Web Service
1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub account if prompted
3. Select the repository: **`peacedestroyer69/valence-study-bot`**
4. Configure these settings:
   - **Name:** `valence-study-bot` (or your preferred service name)
   - **Region:** Pick the closest to India (Singapore)
   - **Branch:** `main`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** **Free**

### Step 3: Add Environment Variables
In the Render dashboard, go to the **"Environment"** tab and add these:
| Key | Value |
|-----|-------|
| `BOT_TOKEN` | Your Discord bot token (the long string starting with `MTUx...`) |
| `LEADERBOARD_CHANNEL_ID` | `1514208164071870514` |
| `LOG_CHANNEL_ID` | `1514208220946763807` |
| `CELEBRATION_CHANNEL_ID` | `1514208252760424591` |
| `FIREBASE_CREDENTIALS` | Paste the entire JSON content of your Google Cloud Firebase service account key file (e.g. from `C:\Users\ROG\Downloads\valence-study-bot-firebase-adminsdk-fbsvc-20109ed3a1.json`) |

### Step 4: Deploy
1. Click **"Create Web Service"**
2. Render will build and start the bot
3. You should see `Valence Bot -- Online` in the Render logs

### Step 5: Set Up UptimeRobot (Keeps Bot Awake)
Render's free tier sleeps after 15 minutes of no HTTP traffic. The bot has a built-in keep-alive server on port 8080. You need to ping it:
1. Go to https://uptimerobot.com and create a free account
2. Click **"Add New Monitor"**
3. Monitor Type: **HTTP(s)**
4. Friendly Name: `Valence Bot`
5. URL: `https://<your-service-name>.onrender.com` (your actual Render URL, e.g., `https://ypt-study-bot.onrender.com` or `https://valence-study-bot.onrender.com`)
6. Monitoring Interval: **5 minutes**
7. Click **"Create Monitor"**

### Step 6: Verify
1. Go to your Discord server
2. The bot should show as **Online**
3. Type `/stats` — should respond
4. Join a Study voice channel — the bot should track your time
5. Check the Render logs for: `Loaded Discipline Extension` and `Loaded Gaming Extension`

---

## How to Know if It's Working
- **Render Dashboard:** Shows "Live" status and real-time logs
- **UptimeRobot:** Shows uptime percentage and alerts you if the bot goes down
- **Discord:** The bot shows as Online with a green dot
- **Study Logs Channel:** When you join/leave a study voice channel, the bot posts a session summary

## Common Issues
- **Bot shows offline:** Check Render logs for errors. Most likely the `BOT_TOKEN` or `FIREBASE_CREDENTIALS` environment variables are wrong or missing.
- **Slash commands don't show:** Wait 1-2 minutes after first boot for Discord to sync commands globally.
- **Roles not being assigned:** Make sure the bot's role in Discord is ABOVE the milestone roles in the role hierarchy (Server Settings → Roles → drag the bot role to the top).
