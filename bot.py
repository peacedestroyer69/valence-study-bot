# ============================================================
# YPT DISCORD STUDY BOT — CONFIGURATION
# ============================================================
# UPTIME SETUP FOR FREE CLOUD HOSTING (Render / Replit):
# 1. Deploy this script. It will start an HTTP server on port 8080.
# 2. Go to uptimerobot.com and create a free account.
# 3. Add a new "HTTP(s)" monitor pointing to your deployed app URL.
# 4. Set check interval to every 5 minutes.
# 5. The bot will now stay awake indefinitely on free-tier hosts.
# ============================================================

import calendar
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiohttp.web
import asyncio
import json
import datetime
import time
import os
import logging
import random

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# --- Firebase Init ---
try:
    cred_json = os.getenv("FIREBASE_CREDENTIALS")
    if cred_json:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        # Avoid double initialization during hot reloads
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logging.info("Firebase initialized successfully from ENV.")
    else:
        db = None
        logging.warning("FIREBASE_CREDENTIALS not found. Falling back to local JSON.")
except Exception as e:
    db = None
    logging.error(f"Failed to initialize Firebase: {e}")

# --- Secrets from .env ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
CELEBRATION_CHANNEL_ID = int(os.getenv("CELEBRATION_CHANNEL_ID", "0"))

# --- Hardcoded Configuration ---

# Maps total WEEKLY hours (int) -> Discord Role ID (int)
# Roles reset every Monday — only the HIGHEST is kept.
# Thresholds are for a single week (168h max).
MILESTONE_ROLES = {
    5:   1514208595737182338,  # 🥉 Bronze Scholar     — 5h/week (~45 min/day)
    15:  1514208694051672195,  # 🥈 Silver Grinder     — 15h/week (~2h/day)
    30:  1514210766256082954,  # 🥇 Gold Grinder       — 30h/week (~4.3h/day)
    50:  1514208770887127192,  # 💎 Diamond Grindmaster — 50h/week (~7h/day)
    70:  1514208898406416505,  # 👑 Legendary Studier   — 70h/week (~10h/day beast mode)
}

# Doubt milestone roles — awarded based on WEEKLY doubt session hours
# Reset every Monday, only highest kept.
DOUBT_MILESTONE_ROLES = {
    1:   1514228187352268830,  # 🟢 Doubt Beginner     — 1h/week
    3:   1514238409449930752,  # 🧠 Doubt Explorer     — 3h/week
    5:   1514238834559291563,  # 💡 Doubt Master       — 5h/week
    10:  1514238964008226988,  # 🎓 Doubt Professor    — 10h/week
    15:  1514254737372090438,  # 🧿 Never Had a Doubt  — 15h/week (2h/day doubting)
}

# Minimum session length in seconds to count (prevents AFK abuse)
MIN_SESSION_SECONDS = 60

# Daily study goal in seconds (1.5 hours = 5400)
DAILY_GOAL_SECONDS = 5400

# Weekly reset day: 0 = Monday, 6 = Sunday
WEEKLY_RESET_DAY = 0

# Custom accent colors per Discord User ID (hex int)
USER_COLORS = {
    856485470171299891:  0x5865F2,  # Valence -> Discord Blurple
    1403716456025165864: 0xEB459E,  # Ujjwal  -> Discord Pink
}
DEFAULT_COLOR = 0x2B2D31

# --- Voice Channel Categories ---
# Study channels: full tracking, milestones, leaderboard, streaks
STUDY_CHANNELS = {1514208313452007514, 1514596473629708298}  # Study Room, Group Study

# Doubt channels: tracked separately, tagged with subject, no milestones
DOUBT_CHANNELS = {
    1514222394628112536,  # Test Discussion stuff
    1514186752301076510,  # Doubt #1
    1514221019005714462,  # Doubt #2
    1514221629864149084,  # Doubt #3
}

# Discussion channels: logged only, no achievements
DISCUSSION_CHANNELS = {1514187630374289418}  # General

# Text study channels: messages are counted for a text activity leaderboard
STUDY_TEXT_CHANNELS = {1514241642415001610}  # Study Discussion

# Text activity milestone roles — based on WEEKLY messages, reset every Monday
TEXT_MILESTONE_ROLES = {
    10:  1514254760386236496,  # 📝 Active Learner (10 msgs/week)
    30:  1514255291578056714,  # 💬 Discussion Pro (30 msgs/week)
    75:  1514255438093484083,  # 🗣️ Knowledge Sharer (75 msgs/week)
    150: 1514255518288576672,  # 📖 Study Sage (150 msgs/week)
}


# --- Pomodoro Configuration ---
POMODORO_CHANNEL_ID = 1514244606827561171  # Group Pomodoro voice channel
POMODORO_STUDY_SECONDS = 60 * 60  # 60 minutes study
POMODORO_BREAK_SECONDS = 10 * 60  # 10 minutes break
POMODORO_CYCLE_SECONDS = POMODORO_STUDY_SECONDS + POMODORO_BREAK_SECONDS  # 70 min total

# In-memory storage for individual pomodoros (user_id -> dict)
active_pomodoros = {}

# Subject tags auto-suggested for doubt sessions
DOUBT_TAGS = [
    "🧪 Physics", "⚗️ Chemistry", "📐 Maths",
    "🧬 Biology", "💻 CS", "🌍 General",
]

# Doubt-specific motivational quotes
DOUBT_QUOTES = [
    "Doubts are the stepping stones to clarity. 🧠",
    "The only stupid question is the one you didn't ask.",
    "Understanding > Memorizing. Always.",
    "Every doubt cleared is a concept mastered. 💡",
    "Asking questions is a sign of strength, not weakness.",
    "Confusion today, clarity tomorrow. Keep asking.",
]

# Rotating motivational quotes shown in session log embeds
MOTIVATIONAL_QUOTES = [
    "The grind never lies. 📚",
    "Every hour compounds. Keep going.",
    "Discipline > Motivation. Always.",
    "Your future self is watching. Don't disappoint.",
    "JEE doesn't care about excuses. Neither should you.",
    "One more hour. That's the gap between you and them.",
    "Consistency beats intensity every single time.",
    "The pain of discipline is lighter than the pain of regret.",
]

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Use a writable data directory (AppData on Windows, script dir on Linux/cloud)
_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA", _SCRIPT_DIR), "YPTStudyBot") if os.name == "nt" else _SCRIPT_DIR
os.makedirs(_DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(_DATA_DIR, "study_data.json")
data_lock = asyncio.Lock()

# Global variable to track current leaderboard view mode
current_view_mode = "alltime"


# ============================================================
# SECTION 2: JSON DATABASE
# ============================================================

def _default_data() -> dict:
    """Returns the default empty data structure."""
    today_str = datetime.date.today().isoformat()
    return {
        "users": {},
        "meta": {
            "leaderboard_message_id": None,
            "last_weekly_reset": today_str,
        },
    }


def _default_user(username: str) -> dict:
    """Returns the default user entry."""
    today_str = datetime.date.today().isoformat()
    return {
        "username": username,
        "total_seconds_alltime": 0,
        "total_seconds_weekly": 0,
        "total_seconds_today": 0,
        "session_start_timestamp": None,
        "session_count": 0,
        "longest_session_seconds": 0,
        "best_day_seconds": 0,
        "current_streak_days": 0,
        "longest_streak_days": 0,
        "last_study_date": None,
        "weekly_reset_date": today_str,
        "leaderboard_message_id": None,
        "daily_goal_seconds": DAILY_GOAL_SECONDS,
        # Doubt tracking
        "total_seconds_doubt": 0,
        "total_seconds_doubt_weekly": 0,
        "doubt_session_count": 0,
        # Discussion tracking
        "total_seconds_discussion": 0,
        "discussion_session_count": 0,
        # Text activity tracking
        "total_messages": 0,
        "messages_today": 0,
        "messages_weekly": 0,
        # Daily study history for heatmap (date_str -> seconds)
        "daily_history": {},
        # Subject tag tracking
        "subject_hours": {},
        # Study Enforcer tracking
        "consecutive_missed_days": 0,
        "last_enforcer_warning": None,
    }


def get_channel_type(channel_id: int) -> str:
    """Returns the channel category: 'study', 'doubt', or 'discussion'."""
    if channel_id in DOUBT_CHANNELS:
        return "doubt"
    if channel_id in DISCUSSION_CHANNELS:
        return "discussion"
    return "study"


# ============================================================
# SECTION 2b: POMODORO HELPERS
# ============================================================

def get_pomodoro_phase() -> tuple:
    """Returns (phase, seconds_remaining, seconds_into_phase) based on absolute clock.
    phase is 'study' or 'break'.
    Uses epoch time modulo so the clock is absolute and independent of bot restarts."""
    cycle_pos = int(time.time()) % POMODORO_CYCLE_SECONDS
    if cycle_pos < POMODORO_STUDY_SECONDS:
        return ("study", POMODORO_STUDY_SECONDS - cycle_pos, cycle_pos)
    else:
        return ("break", POMODORO_CYCLE_SECONDS - cycle_pos, cycle_pos - POMODORO_STUDY_SECONDS)


def calculate_pomodoro_study_seconds(start_time: int, end_time: int) -> int:
    """Calculate actual study seconds between start and end, excluding break periods.
    Uses the absolute pomodoro clock."""
    total_study = 0
    current = start_time
    while current < end_time:
        cycle_pos = current % POMODORO_CYCLE_SECONDS
        if cycle_pos < POMODORO_STUDY_SECONDS:
            # In study phase
            study_remaining = POMODORO_STUDY_SECONDS - cycle_pos
            chunk = min(study_remaining, end_time - current)
            total_study += chunk
            current += chunk
        else:
            # In break phase
            break_remaining = POMODORO_CYCLE_SECONDS - cycle_pos
            current += min(break_remaining, end_time - current)
    return total_study


def format_mm_ss(seconds: int) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"


async def load_data() -> dict:
    """Reads and returns the JSON data from Firestore, falls back to local JSON if missing."""
    if db:
        try:
            # Using to_thread for synchronous firestore calls to avoid blocking event loop
            def fetch_doc():
                doc_ref = db.collection('bot_data').document('main')
                doc = doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
                else:
                    data = _default_data()
                    doc_ref.set(data)
                    return data
            return await asyncio.to_thread(fetch_doc)
        except Exception as e:
            logging.error(f"Firestore read error: {e}. Falling back to local.")
            
    try:
        async with data_lock:
            if not os.path.exists(DATA_FILE):
                data = _default_data()
                os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                logging.info("Initialized new study_data.json")
                return data

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to load data file: {e}. Reinitializing.")
        data = _default_data()
        async with data_lock:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        return data


async def save_data(data: dict):
    """Saves data to Firestore and local JSON file."""
    if db:
        try:
            def push_doc():
                db.collection('bot_data').document('main').set(data)
            await asyncio.to_thread(push_doc)
        except Exception as e:
            logging.error(f"Firestore write error: {e}")
            
    async with data_lock:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError) as e:
            logging.error(f"Failed to save data file: {e}")


def ensure_user(data: dict, member: discord.Member) -> dict:
    """Ensures a user entry exists in data and returns it."""
    uid = str(member.id)
    if uid not in data["users"]:
        data["users"][uid] = _default_user(member.display_name)
    else:
        data["users"][uid]["username"] = member.display_name
    return data["users"][uid]


# ============================================================
# SECTION 3: BOT INITIALIZATION
# ============================================================

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.load_data = load_data
bot.save_data = save_data
bot.data_lock = data_lock

async def setup_hook():
    for cog_name in ["cogs.discipline", "cogs.bonus_features"]:
        try:
            await bot.load_extension(cog_name)
            logging.info(f"Loaded {cog_name}")
        except Exception as e:
            logging.error(f"Failed to load {cog_name}: {e}")

bot.setup_hook = setup_hook


# ============================================================
# SECTION 5: LEADERBOARD HELPERS
# ============================================================

def format_time(seconds: int) -> str:
    """Converts raw seconds into human-readable format."""
    if seconds < 60:
        return "< 1m"
    minutes = seconds // 60
    if seconds < 3600:
        return f"{minutes}m"
    hours = seconds // 3600
    remaining_minutes = (seconds % 3600) // 60
    if seconds < 86400:
        return f"{hours}h {remaining_minutes:02d}m"
    days = seconds // 86400
    remaining_hours = (seconds % 86400) // 3600
    remaining_minutes = (seconds % 3600) // 60
    return f"{days}d {remaining_hours}h {remaining_minutes:02d}m"


def format_time_precise(seconds: int) -> str:
    """Precise format including seconds, for session logs."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def generate_progress_bar(value: int, maximum: int, length: int = 10) -> str:
    """Generates a visual progress bar using block emojis."""
    if maximum > 0:
        ratio = min(value / maximum, 1.0)
        filled = round(ratio * length)
    else:
        filled = 0
        ratio = 0.0
    empty = length - filled
    bar = "🟩" * filled + "⬛" * empty
    percent = int(ratio * 100)
    return f"{bar} {percent}%"


def get_rank_emblem(hours: float) -> str:
    """Returns an emoji rank badge based on total hours."""
    if hours >= 200:
        return "👑"
    if hours >= 100:
        return "💎"
    if hours >= 50:
        return "🥇"
    if hours >= 25:
        return "🥈"
    if hours >= 5:
        return "🥉"
    return "📖"


def get_streak_display(streak: int) -> str:
    """Returns a formatted streak display string."""
    if streak <= 0:
        return "—"
    if streak <= 2:
        return f"🔥 {streak} day streak"
    if streak <= 6:
        return f"🔥🔥 {streak} day streak"
    if streak <= 13:
        return f"🔥🔥🔥 {streak} day streak"
    return f"⚡🔥 {streak} day streak — ELITE"


def build_leaderboard_embed(data: dict, mode: str) -> discord.Embed:
    """Builds the full leaderboard embed for alltime, weekly, or doubt mode."""
    if mode == "weekly":
        title = "📅 Weekly Standings"
        sort_key = "total_seconds_weekly"
        embed_color = 0x5865F2
    elif mode == "doubt":
        title = "❓ Doubt Session Leaderboard"
        sort_key = "total_seconds_doubt"
        embed_color = 0xFFA500  # Amber
    elif mode == "messages":
        title = "💬 Text Activity Leaderboard"
        sort_key = "total_messages"
        embed_color = 0x57F287  # Green
    else:
        title = "📊 YPT Study Leaderboard"
        sort_key = "total_seconds_alltime"
        embed_color = 0x5865F2

    embed = discord.Embed(title=title, color=embed_color)

    users = data.get("users", {})
    sorted_users = sorted(
        users.items(),
        key=lambda item: item[1].get(sort_key, 0),
        reverse=True,
    )

    # Filter out users with 0 time in the selected mode
    sorted_users = [(uid, ud) for uid, ud in sorted_users if ud.get(sort_key, 0) > 0]

    now_unix = int(time.time())

    if not sorted_users:
        embed.description = "No sessions recorded yet. Join a voice channel to get started!"
        embed.set_footer(text=f"Last updated: <t:{now_unix}:R>")
        embed.timestamp = datetime.datetime.now(datetime.UTC)
        return embed

    for rank, (uid, udata) in enumerate(sorted_users[:5], start=1):
        total_secs = udata.get(sort_key, 0)
        username = udata.get("username", "Unknown")

        if mode == "doubt":
            # Doubt-specific display
            doubt_count = udata.get("doubt_session_count", 0)
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank - 1] if rank <= 5 else "📖"

            field_value = (
                f"🕒 {format_time(total_secs)}  |  📋 {doubt_count} sessions\n"
                f"Avg session: {format_time(total_secs // doubt_count if doubt_count > 0 else 0)}"
            )
            embed.add_field(
                name=f"#{rank} {rank_emoji} {username}",
                value=field_value,
                inline=False,
            )
        elif mode == "messages":
            # Text activity display
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank - 1] if rank <= 5 else "📖"
            msg_total = udata.get("total_messages", 0)
            msg_today = udata.get("messages_today", 0)
            msg_weekly = udata.get("messages_weekly", 0)

            field_value = (
                f"💬 Total: **{msg_total}**  |  📅 Today: **{msg_today}**\n"
                f"📆 This week: **{msg_weekly}**"
            )
            embed.add_field(
                name=f"#{rank} {rank_emoji} {username}",
                value=field_value,
                inline=False,
            )
        else:
            # Study / weekly display (original)
            total_hours = udata.get("total_seconds_alltime", 0) / 3600
            emblem = get_rank_emblem(total_hours)
            streak = udata.get("current_streak_days", 0)
            streak_display = get_streak_display(streak)
            sessions = udata.get("session_count", 0)
            best_day = udata.get("best_day_seconds", 0)
            best_session = udata.get("longest_session_seconds", 0)

            live_prefix = ""
            if udata.get("session_start_timestamp") is not None:
                live_prefix = "⏱️ LIVE — In session now! "

            time_display = format_time(total_secs)
            daily_goal = udata.get("daily_goal_seconds", DAILY_GOAL_SECONDS)
            today_secs = udata.get("total_seconds_today", 0)
            progress = generate_progress_bar(today_secs, daily_goal)

            field_value = (
                f"{live_prefix}🕐 {time_display}  |  {streak_display}\n"
                f"{progress}\n"
                f"📌 Sessions: {sessions}  |  🏆 Best day: {format_time(best_day)}  |  ⚡ Best session: {format_time(best_session)}"
            )

            embed.add_field(
                name=f"#{rank} {emblem} {username}",
                value=field_value,
                inline=False,
            )

    # Separator
    embed.add_field(name="\u200b", value="─" * 30, inline=False)

    if mode == "doubt":
        # Doubt leaderboard footer stats
        total_doubt_all = sum(ud.get("total_seconds_doubt", 0) for _, ud in sorted_users)
        total_doubt_sessions = sum(ud.get("doubt_session_count", 0) for _, ud in sorted_users)
        embed.add_field(
            name="📊 Server Doubt Stats",
            value=(
                f"🕒 Total doubt time: **{format_time(total_doubt_all)}**\n"
                f"📋 Total sessions: **{total_doubt_sessions}**\n"
                f"❓ Every doubt cleared = one step closer"
            ),
            inline=False,
        )
    elif mode == "messages":
        # Text activity footer stats
        total_msgs_all = sum(ud.get("total_messages", 0) for _, ud in sorted_users)
        embed.add_field(
            name="📊 Server Text Stats",
            value=(
                f"💬 Total messages: **{total_msgs_all}**\n"
                f"📝 Keep the discussions going!"
            ),
            inline=False,
        )
    else:
        # Personal Records section (top user) for study modes
        if sorted_users:
            top_uid, top_udata = sorted_users[0]
            best_session_all = top_udata.get("longest_session_seconds", 0)
            best_day_all = top_udata.get("best_day_seconds", 0)
            longest_streak = top_udata.get("longest_streak_days", 0)
            embed.add_field(
                name="📈 Personal Records",
                value=(
                    f"⚡ Longest session: **{format_time(best_session_all)}**\n"
                    f"🏆 Best single day: **{format_time(best_day_all)}**\n"
                    f"🔥 Longest streak: **{longest_streak} days**"
                ),
                inline=False,
            )

    embed.set_footer(text=f"Last updated: <t:{now_unix}:R>")
    embed.timestamp = datetime.datetime.now(datetime.UTC)

    return embed


async def update_leaderboard_embed(mode: str = "alltime"):
    """Updates or creates the persistent leaderboard message."""
    global current_view_mode
    current_view_mode = mode
    try:
        data = await load_data()
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if channel is None:
            logging.error(f"Leaderboard channel {LEADERBOARD_CHANNEL_ID} not found.")
            return

        embed = build_leaderboard_embed(data, mode)
        view = LeaderboardView(mode)
        msg_id = data["meta"].get("leaderboard_message_id")

        if msg_id is not None:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                logging.warning("Previous leaderboard message not found. Sending new one.")

        msg = await channel.send(embed=embed, view=view)
        data["meta"]["leaderboard_message_id"] = msg.id
        await save_data(data)
    except Exception as e:
        logging.error(f"Failed to update leaderboard embed: {e}")


class LeaderboardView(discord.ui.View):
    """Persistent view attached to the leaderboard message with refresh button and view selector."""

    def __init__(self, initial_mode: str = "alltime"):
        super().__init__(timeout=None)
        self.current_mode = initial_mode

    @discord.ui.button(label="🔄 Refresh Stats", style=discord.ButtonStyle.primary, custom_id="ypt_refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refreshes the leaderboard stats in-place."""
        try:
            await interaction.response.defer(ephemeral=True)
            await update_leaderboard_embed(self.current_mode)
            msg = await interaction.followup.send("✅ Stats refreshed!", ephemeral=True)
            await asyncio.sleep(3)
            try:
                await msg.delete()
            except discord.HTTPException:
                pass
        except Exception as e:
            logging.error(f"Refresh button error: {e}")

    @discord.ui.select(
        placeholder="📊 Switch View...",
        custom_id="ypt_view_selector",
        options=[
            discord.SelectOption(
                label="All-Time Records",
                value="alltime",
                emoji="🏆",
                description="Total hours since the beginning",
            ),
            discord.SelectOption(
                label="Weekly Standings",
                value="weekly",
                emoji="📅",
                description="This week's grind only",
            ),
            discord.SelectOption(
                label="Doubt Standings",
                value="doubt",
                emoji="❓",
                description="Who's clearing the most doubts?",
            ),
            discord.SelectOption(
                label="Text Activity",
                value="messages",
                emoji="💬",
                description="Who's most active in study discussions?",
            ),
        ],
    )
    async def view_selector(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Switches between all-time and weekly leaderboard views."""
        try:
            self.current_mode = select.values[0]
            await interaction.response.defer()
            await update_leaderboard_embed(self.current_mode)
        except Exception as e:
            logging.error(f"View selector error: {e}")


# ============================================================
# SECTION 6: SESSION LOG EMBED
# ============================================================

async def send_session_log(member: discord.Member, session_seconds: int, data: dict):
    """Sends a detailed session completion embed to the log channel."""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            logging.error(f"Log channel {LOG_CHANNEL_ID} not found.")
            return

        uid = str(member.id)
        udata = data["users"].get(uid, {})
        accent_color = USER_COLORS.get(member.id, DEFAULT_COLOR)
        quote = random.choice(MOTIVATIONAL_QUOTES)

        daily_total = udata.get("total_seconds_today", 0)
        alltime_total = udata.get("total_seconds_alltime", 0)
        session_count = udata.get("session_count", 0)
        longest_session = udata.get("longest_session_seconds", 0)
        daily_goal = udata.get("daily_goal_seconds", DAILY_GOAL_SECONDS)

        is_new_pb = session_seconds >= longest_session and session_seconds == longest_session

        unix_end = int(time.time())

        embed = discord.Embed(color=accent_color)
        embed.set_author(
            name=f"{member.display_name} — Study Session Complete",
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="⏱️ Duration", value=format_time_precise(session_seconds), inline=True)
        embed.add_field(name="📅 Date", value=f"<t:{unix_end}:D>", inline=True)
        embed.add_field(name="⌚ Finished", value=f"<t:{unix_end}:R>", inline=True)

        daily_bar = generate_progress_bar(daily_total, daily_goal)
        embed.add_field(
            name="📊 Today's Total",
            value=f"{format_time(daily_total)}\n{daily_bar}",
            inline=True,
        )
        embed.add_field(name="🏆 All-Time Total", value=format_time(alltime_total), inline=True)
        embed.add_field(name="⚡ Sessions Today", value=str(session_count), inline=True)

        # Check if this session was a new personal best
        # We compare against what the longest was BEFORE this session updated it
        if session_seconds == longest_session and session_count > 0:
            embed.add_field(
                name="🎯 NEW PERSONAL BEST!",
                value=f"Longest session ever: **{format_time_precise(session_seconds)}** 🔥",
                inline=False,
            )
            embed.color = 0x57F287  # Green for new PB

        embed.set_footer(text=quote)
        embed.timestamp = datetime.datetime.now(datetime.UTC)

        await channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send session log: {e}")


# ============================================================
# SECTION 6b: DOUBT SESSION LOG EMBED
# ============================================================

class SubjectTagView(discord.ui.View):
    """Dropdown for tagging a doubt session with a subject."""
    def __init__(self, user_id: str, session_seconds: int):
        super().__init__(timeout=300)  # 5 minutes to pick
        self.user_id = user_id
        self.session_seconds = session_seconds

    @discord.ui.select(
        placeholder="\U0001f3f7\ufe0f Tag this session with a subject...",
        options=[
            discord.SelectOption(label="Physics", value="physics", emoji="\U0001f9ea"),
            discord.SelectOption(label="Chemistry", value="chemistry", emoji="\u2697\ufe0f"),
            discord.SelectOption(label="Maths", value="maths", emoji="\U0001f4d0"),
            discord.SelectOption(label="Biology", value="biology", emoji="\U0001f9ec"),
            discord.SelectOption(label="CS", value="cs", emoji="\U0001f4bb"),
            discord.SelectOption(label="General", value="general", emoji="\U0001f30d"),
        ],
    )
    async def tag_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Records the subject tag for this doubt session."""
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your session to tag!", ephemeral=True)
            return
        try:
            tag = select.values[0]
            data = await load_data()
            udata = data["users"].get(self.user_id, {})
            # Track subject hours
            if "subject_hours" not in udata:
                udata["subject_hours"] = {}
            udata["subject_hours"][tag] = udata["subject_hours"].get(tag, 0) + self.session_seconds
            await save_data(data)

            tag_emoji = {"physics": "\U0001f9ea", "chemistry": "\u2697\ufe0f", "maths": "\U0001f4d0", "biology": "\U0001f9ec", "cs": "\U0001f4bb", "general": "\U0001f30d"}
            await interaction.response.send_message(
                f"{tag_emoji.get(tag, '')} Tagged as **{tag.capitalize()}**! ({format_time_precise(self.session_seconds)})",
                ephemeral=True,
            )
            self.stop()
        except Exception as e:
            logging.error(f"Subject tag error: {e}")


async def send_doubt_log(member: discord.Member, session_seconds: int, data: dict, channel: discord.VoiceChannel):
    """Sends a doubt session completion embed to the log channel."""
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            logging.error(f"Log channel {LOG_CHANNEL_ID} not found.")
            return

        uid = str(member.id)
        udata = data["users"].get(uid, {})
        quote = random.choice(DOUBT_QUOTES)
        unix_end = int(time.time())
        total_doubt = udata.get("total_seconds_doubt", 0)
        doubt_count = udata.get("doubt_session_count", 0)

        # Auto-detect tag from channel name
        ch_name = channel.name.lower()
        tag_line = " | ".join(DOUBT_TAGS)

        embed = discord.Embed(color=0xFFA500)  # Amber/Orange for doubts
        embed.set_author(
            name=f"{member.display_name} -- Doubt Session Complete",
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="\u2753 Type", value="Doubt / Discussion", inline=True)
        embed.add_field(name="\U0001f4cd Channel", value=f"#{channel.name}", inline=True)
        embed.add_field(name="\u23f1\ufe0f Duration", value=format_time_precise(session_seconds), inline=True)
        embed.add_field(name="\U0001f4c5 Date", value=f"<t:{unix_end}:D>", inline=True)
        embed.add_field(name="\u231a Finished", value=f"<t:{unix_end}:R>", inline=True)
        embed.add_field(name="\U0001f4cb Total Doubt Sessions", value=str(doubt_count), inline=True)
        embed.add_field(
            name="\U0001f550 Total Doubt Time",
            value=format_time(total_doubt),
            inline=True,
        )

        # Subject tags suggestion
        embed.add_field(
            name="\U0001f3f7\ufe0f Subject Tags",
            value=tag_line,
            inline=False,
        )

        embed.set_footer(text=quote)
        embed.timestamp = datetime.datetime.now(datetime.UTC)

        tag_view = SubjectTagView(uid, session_seconds)
        await log_channel.send(embed=embed, view=tag_view)
    except Exception as e:
        logging.error(f"Failed to send doubt log: {e}")


# ============================================================
# SECTION 6c: DISCUSSION SESSION LOG EMBED
# ============================================================

async def send_discussion_log(member: discord.Member, session_seconds: int, data: dict, channel: discord.VoiceChannel):
    """Sends a discussion session log embed — lightweight, no achievements."""
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            logging.error(f"Log channel {LOG_CHANNEL_ID} not found.")
            return

        uid = str(member.id)
        udata = data["users"].get(uid, {})
        unix_end = int(time.time())
        total_disc = udata.get("total_seconds_discussion", 0)
        disc_count = udata.get("discussion_session_count", 0)

        embed = discord.Embed(color=0x99AAB5)  # Gray for discussion
        embed.set_author(
            name=f"{member.display_name} -- Discussion Session",
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )

        embed.add_field(name="\U0001f4ac Type", value="General Discussion", inline=True)
        embed.add_field(name="\U0001f4cd Channel", value=f"#{channel.name}", inline=True)
        embed.add_field(name="\u23f1\ufe0f Duration", value=format_time_precise(session_seconds), inline=True)
        embed.add_field(name="\u231a Finished", value=f"<t:{unix_end}:R>", inline=True)
        embed.add_field(name="\U0001f4cb Total Discussions", value=str(disc_count), inline=True)
        embed.add_field(name="\U0001f550 Total Discussion Time", value=format_time(total_disc), inline=True)

        embed.set_footer(text="Not everything has to be study. Chill is valid too.")
        embed.timestamp = datetime.datetime.now(datetime.UTC)

        await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send discussion log: {e}")


# ============================================================
# SECTION 6d: POMODORO SESSION LOG EMBED
# ============================================================

async def send_pomodoro_session_log(member: discord.Member, study_seconds: int, break_seconds: int, total_seconds: int, data: dict):
    """Sends a pomodoro session completion embed to the log channel."""
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            return

        uid = str(member.id)
        udata = data["users"].get(uid, {})
        accent_color = USER_COLORS.get(member.id, DEFAULT_COLOR)
        quote = random.choice(MOTIVATIONAL_QUOTES)
        unix_end = int(time.time())

        embed = discord.Embed(color=accent_color)
        embed.set_author(
            name=f"{member.display_name} \u2014 Pomodoro Session Complete",
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="\U0001f345 Type", value="Group Pomodoro", inline=True)
        embed.add_field(name="\u23f1\ufe0f Study Time", value=format_time_precise(study_seconds), inline=True)
        embed.add_field(name="\U0001f7e2 Break Time", value=format_time_precise(break_seconds), inline=True)
        embed.add_field(name="\U0001f570\ufe0f Total in Channel", value=format_time_precise(total_seconds), inline=True)
        embed.add_field(name="\U0001f4c5 Date", value=f"<t:{unix_end}:D>", inline=True)
        embed.add_field(name="\u231a Finished", value=f"<t:{unix_end}:R>", inline=True)

        embed.set_footer(text=quote)
        embed.timestamp = datetime.datetime.now(datetime.UTC)

        await channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send pomodoro session log: {e}")


# ============================================================
# SECTION 7: LIVE VOICE CHANNEL STATUS & BOT PRESENCE
# ============================================================

async def update_voice_channel_status(channel: discord.VoiceChannel, active_member: discord.Member | None):
    """Sets or clears the voice channel status text via the Discord API."""
    try:
        voice_members = [m for m in channel.members if not m.bot]
        member_count = len(voice_members)

        if member_count == 0 and active_member is None:
            status_text = ""
        elif member_count > 1:
            status_text = f"📚 {member_count} scholars grinding! 🔥"
        elif active_member is not None:
            status_text = f"📚 {active_member.display_name} is grinding! 💪"
        elif member_count == 1:
            status_text = f"📚 {voice_members[0].display_name} is grinding! 💪"
        else:
            status_text = ""

        url = f"https://discord.com/api/v10/channels/{channel.id}/voice-status"
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {"status": status_text}

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    logging.warning(f"Voice status update returned {resp.status}: {body}")
    except Exception as e:
        logging.error(f"Failed to update voice channel status: {e}")


async def update_bot_presence(data: dict):
    """Sets bot presence based on active sessions."""
    try:
        users = data.get("users", {})
        for uid, udata in users.items():
            if udata.get("session_start_timestamp") is not None:
                username = udata.get("username", "someone")
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{username} grinding 📚",
                )
                await bot.change_presence(activity=activity)
                return

        # No active sessions — use default
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="the leaderboard 👀",
        )
        await bot.change_presence(activity=activity)
    except Exception as e:
        logging.error(f"Failed to update bot presence: {e}")


async def presence_rotation_loop():
    """Cycles through rotating statuses when no one is studying."""
    statuses = [
        discord.Activity(type=discord.ActivityType.watching, name="the leaderboard 👀"),
        discord.Game(name="YPT Tracker 📊"),
        discord.Activity(type=discord.ActivityType.listening, name="study lofi ☕"),
    ]
    idx = 0
    while True:
        try:
            await asyncio.sleep(60)
            data = await load_data()
            users = data.get("users", {})
            any_active = any(
                udata.get("session_start_timestamp") is not None
                for udata in users.values()
            )
            if any_active:
                await update_bot_presence(data)
            else:
                await bot.change_presence(activity=statuses[idx % len(statuses)])
                idx += 1
        except Exception as e:
            logging.error(f"Presence rotation error: {e}")
            await asyncio.sleep(60)


# ============================================================
# SECTION 8: STREAK SYSTEM
# ============================================================

def update_streak(user_data: dict):
    """Updates the user's study streak based on consecutive day logic."""
    today_str = datetime.date.today().isoformat()
    last_study = user_data.get("last_study_date")

    if last_study is None:
        user_data["current_streak_days"] = 1
    else:
        try:
            last_date = datetime.date.fromisoformat(last_study)
            today_date = datetime.date.today()
            delta = (today_date - last_date).days

            if delta == 0:
                # Same day — no streak change
                pass
            elif delta == 1:
                # Consecutive day — increment
                user_data["current_streak_days"] = user_data.get("current_streak_days", 0) + 1
            else:
                # Gap — reset to 1
                user_data["current_streak_days"] = 1
        except ValueError:
            user_data["current_streak_days"] = 1

    # Update longest streak
    current = user_data.get("current_streak_days", 0)
    longest = user_data.get("longest_streak_days", 0)
    if current > longest:
        user_data["longest_streak_days"] = current

    user_data["last_study_date"] = today_str


async def check_weekly_reset(data: dict):
    """Background task that checks once per hour for weekly and daily resets."""
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour
            data = await load_data()
            today = datetime.date.today()
            today_str = today.isoformat()

            # NOTE: Enforcer logic (DMs, warnings, kicks) is handled by
            # cogs/discipline.py to avoid duplication. Removed from bot.py.

            # --- Daily reset for total_seconds_today and messages_today ---
            for uid, udata in data["users"].items():
                last_study = udata.get("last_study_date")
                if last_study and last_study != today_str:
                    udata["total_seconds_today"] = 0
                    udata["messages_today"] = 0

            # --- Weekly reset ---
            if today.weekday() == WEEKLY_RESET_DAY:
                last_reset = data["meta"].get("last_weekly_reset")
                if last_reset != today_str:
                    # Find this week's winner BEFORE resetting
                    winner_uid = None
                    winner_seconds = 0
                    winner_name = "Unknown"
                    for uid, udata in data["users"].items():
                        weekly = udata.get("total_seconds_weekly", 0)
                        if weekly > winner_seconds:
                            winner_seconds = weekly
                            winner_uid = uid
                            winner_name = udata.get("username", "Unknown")

                    # Reset weekly and daily totals
                    for uid, udata in data["users"].items():
                        udata["total_seconds_weekly"] = 0
                        udata["total_seconds_today"] = 0
                        udata["total_seconds_doubt_weekly"] = 0
                        udata["messages_weekly"] = 0
                        udata["messages_today"] = 0

                    data["meta"]["last_weekly_reset"] = today_str
                    await save_data(data)

                    # --- Strip ALL milestone roles from everyone (weekly reset) ---
                    all_role_ids = set(MILESTONE_ROLES.values()) | set(DOUBT_MILESTONE_ROLES.values()) | set(TEXT_MILESTONE_ROLES.values())
                    for guild in bot.guilds:
                        for member in guild.members:
                            if member.bot:
                                continue
                            roles_to_strip = [r for r in member.roles if r.id in all_role_ids]
                            if roles_to_strip:
                                try:
                                    await member.remove_roles(*roles_to_strip, reason="Weekly reset — all milestone roles cleared")
                                    logging.info(f"[WEEKLY RESET] Stripped {len(roles_to_strip)} roles from {member.display_name}")
                                except Exception as e:
                                    logging.error(f"Failed to strip roles from {member.display_name}: {e}")

                    # Send weekly winner announcement
                    if winner_uid is not None and winner_seconds > 0:
                        try:
                            channel = bot.get_channel(CELEBRATION_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="🏆 Weekly Winner!",
                                    description=(
                                        f"Congratulations to **{winner_name}** (<@{winner_uid}>) "
                                        f"for topping this week's leaderboard with "
                                        f"**{format_time(winner_seconds)}** of study! 🔥🎉"
                                    ),
                                    color=0xFFD700,
                                    timestamp=datetime.datetime.now(datetime.UTC),
                                )
                                embed.set_footer(text="A new week begins. The grind resets. Go again. 💪")
                                await channel.send(embed=embed)
                        except Exception as e:
                            logging.error(f"Failed to send weekly winner announcement: {e}")

                    logging.info("Weekly reset completed.")
                else:
                    await save_data(data)
            else:
                await save_data(data)

        except Exception as e:
            logging.error(f"Weekly reset check error: {e}")
            await asyncio.sleep(3600)


# ============================================================
# SECTION 9: MILESTONE ROLE SYSTEM
# ============================================================

async def check_and_award_milestones(member: discord.Member, data: dict):
    """Awards the HIGHEST earned study role and removes all lower ones.
    Uses WEEKLY hours so roles reset every Monday."""
    try:
        uid = str(member.id)
        udata = data["users"].get(uid)
        if udata is None:
            return

        total_hours = udata.get("total_seconds_weekly", 0) / 3600
        guild = member.guild

        # Find the highest milestone the user qualifies for
        earned_threshold = None
        earned_role_id = None
        for hours_threshold in sorted(MILESTONE_ROLES.keys()):
            if total_hours >= hours_threshold:
                earned_threshold = hours_threshold
                earned_role_id = MILESTONE_ROLES[hours_threshold]

        # Remove ALL milestone roles first, then add only the highest
        all_milestone_role_ids = set(MILESTONE_ROLES.values())
        already_has = discord.utils.get(member.roles, id=earned_role_id) if earned_role_id else None
        roles_to_remove = [r for r in member.roles if r.id in all_milestone_role_ids]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Milestone role update — removing lower tiers")
            except (discord.Forbidden, discord.HTTPException) as e:
                logging.error(f"Failed to remove old milestone roles: {e}")

        # Award the highest earned role
        if earned_role_id:
            role = guild.get_role(earned_role_id)
            if role is None:
                logging.warning(f"Milestone role {earned_role_id} not found in guild.")
                return

            try:
                await member.add_roles(role, reason=f"YPT milestone: {earned_threshold}h this week")
            except discord.Forbidden:
                logging.error(f"No permission to assign role {role.name} to {member.display_name}")
                return
            except discord.HTTPException as e:
                logging.error(f"Failed to assign milestone role: {e}")
                return

            # Only celebrate if they didn't already have this exact role
            if not already_has:
                try:
                    channel = bot.get_channel(CELEBRATION_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            title="🎉 MILESTONE UNLOCKED!",
                            description=(
                                f"{member.mention} just crossed **{earned_threshold} hours** this week! 🔥\n"
                                f"Role **{role.name}** has been awarded!"
                            ),
                            color=0xFFD700,
                            timestamp=datetime.datetime.now(datetime.UTC),
                        )
                        if member.display_avatar:
                            embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text="Keep grinding. The next milestone awaits.")
                        await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send milestone celebration: {e}")
    except Exception as e:
        logging.error(f"Milestone check error: {e}")


async def check_and_award_doubt_milestones(member: discord.Member, data: dict):
    """Awards the HIGHEST earned doubt role and removes all lower ones.
    Uses WEEKLY doubt hours so roles reset every Monday."""
    try:
        uid = str(member.id)
        udata = data["users"].get(uid)
        if udata is None:
            return

        total_hours = udata.get("total_seconds_doubt_weekly", 0) / 3600
        guild = member.guild

        # Find the highest doubt milestone the user qualifies for
        earned_threshold = None
        earned_role_id = None
        for hours_threshold in sorted(DOUBT_MILESTONE_ROLES.keys()):
            if total_hours >= hours_threshold:
                earned_threshold = hours_threshold
                earned_role_id = DOUBT_MILESTONE_ROLES[hours_threshold]

        # Remove ALL doubt milestone roles first
        all_doubt_role_ids = set(DOUBT_MILESTONE_ROLES.values())
        already_has = discord.utils.get(member.roles, id=earned_role_id) if earned_role_id else None
        roles_to_remove = [r for r in member.roles if r.id in all_doubt_role_ids]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Doubt role update — removing lower tiers")
            except (discord.Forbidden, discord.HTTPException) as e:
                logging.error(f"Failed to remove old doubt roles: {e}")

        # Award the highest earned role
        if earned_role_id:
            role = guild.get_role(earned_role_id)
            if role is None:
                logging.warning(f"Doubt role {earned_role_id} not found in guild.")
                return

            try:
                await member.add_roles(role, reason=f"YPT doubt milestone: {earned_threshold}h")
            except discord.Forbidden:
                logging.error(f"No permission to assign role {role.name} to {member.display_name}")
                return
            except discord.HTTPException as e:
                logging.error(f"Failed to assign doubt role: {e}")
                return

            if not already_has:
                try:
                    channel = bot.get_channel(CELEBRATION_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            title="🧠 DOUBT MILESTONE UNLOCKED!",
                            description=(
                                f"{member.mention} just crossed **{earned_threshold} hours** of doubt sessions! 🔥\n"
                                f"Role **{role.name}** has been awarded!"
                            ),
                            color=0xFFA500,
                            timestamp=datetime.datetime.now(datetime.UTC),
                        )
                        if member.display_avatar:
                            embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text="Every doubt cleared is a concept mastered. Keep asking.")
                        await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send doubt milestone celebration: {e}")
    except Exception as e:
        logging.error(f"Doubt milestone check error: {e}")


# ============================================================
# SECTION 4: VOICE STATE TRACKING
# ============================================================

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Handles voice channel join, leave, and switch events for study tracking."""
    if member.bot:
        return

    joined = before.channel is None and after.channel is not None
    left = before.channel is not None and after.channel is None
    switched = (
        before.channel is not None
        and after.channel is not None
        and before.channel.id != after.channel.id
    )

    if switched:
        # Treat as LEAVE from before.channel + JOIN to after.channel
        await _handle_leave(member, before.channel)
        await _handle_join(member, after.channel)
    elif joined:
        await _handle_join(member, after.channel)
    elif left:
        await _handle_leave(member, before.channel)


async def _handle_join(member: discord.Member, channel: discord.VoiceChannel):
    """Processes a voice channel join event."""
    try:
        # If user joins group pomodoro channel, cancel their individual pomodoro
        if channel.id == POMODORO_CHANNEL_ID and member.id in active_pomodoros:
            task = active_pomodoros[member.id].get("task")
            if task:
                task.cancel()
            active_pomodoros.pop(member.id, None)
            try:
                await member.send("\U0001f504 Your individual Pomodoro was cancelled because you joined the group Pomodoro channel.")
            except Exception:
                pass

        data = await load_data()
        udata = ensure_user(data, member)
        udata["session_start_timestamp"] = int(time.time())
        await save_data(data)
        logging.info(f"[SESSION START] {member.display_name} joined #{channel.name}")
        # Don't override pomodoro channel status — it has its own status loop
        if channel.id != POMODORO_CHANNEL_ID:
            await update_voice_channel_status(channel, member)
        await update_bot_presence(data)
    except Exception as e:
        logging.error(f"Error handling voice join for {member.display_name}: {e}")


async def _handle_leave(member: discord.Member, channel: discord.VoiceChannel):
    """Processes a voice channel leave event."""
    try:
        data = await load_data()
        uid = str(member.id)
        udata = ensure_user(data, member)

        start_ts = udata.get("session_start_timestamp")
        if start_ts is None:
            logging.warning(f"[SESSION END] {member.display_name} left but had no active session.")
            await update_voice_channel_status(channel, None)
            return

        session_seconds = int(time.time()) - start_ts

        if session_seconds < MIN_SESSION_SECONDS:
            logging.info(
                f"[SESSION DISCARD] {member.display_name} -- {session_seconds}s "
                f"(below {MIN_SESSION_SECONDS}s minimum)"
            )
            udata["session_start_timestamp"] = None
            await save_data(data)
            await update_voice_channel_status(channel, None)
            await update_bot_presence(data)
            return

        ch_type = get_channel_type(channel.id)
        real_start_ts = start_ts  # Save BEFORE clearing
        udata["session_start_timestamp"] = None

        if channel.id == POMODORO_CHANNEL_ID:
            # --- GROUP POMODORO: calculate study time excluding breaks ---
            study_secs = calculate_pomodoro_study_seconds(real_start_ts, int(time.time()))

            if study_secs >= MIN_SESSION_SECONDS:
                udata["total_seconds_alltime"] = udata.get("total_seconds_alltime", 0) + study_secs
                udata["total_seconds_weekly"] = udata.get("total_seconds_weekly", 0) + study_secs
                udata["total_seconds_today"] = udata.get("total_seconds_today", 0) + study_secs
                udata["session_count"] = udata.get("session_count", 0) + 1

                if study_secs > udata.get("longest_session_seconds", 0):
                    udata["longest_session_seconds"] = study_secs
                if udata["total_seconds_today"] > udata.get("best_day_seconds", 0):
                    udata["best_day_seconds"] = udata["total_seconds_today"]

                # Record daily history for heatmap
                today_str = datetime.date.today().isoformat()
                if "daily_history" not in udata:
                    udata["daily_history"] = {}
                udata["daily_history"][today_str] = udata.get("total_seconds_today", 0)

                update_streak(udata)
                await save_data(data)

                total_time_in_channel = int(time.time()) - real_start_ts
                break_secs = total_time_in_channel - study_secs

                logging.info(f"[POMODORO END] {member.display_name} -- {format_time_precise(study_secs)} study ({format_time_precise(break_secs)} break) in #{channel.name}")

                await send_pomodoro_session_log(member, study_secs, break_secs, total_time_in_channel, data)
                await check_and_award_milestones(member, data)
                await update_leaderboard_embed(current_view_mode)
            else:
                logging.info(f"[POMODORO DISCARD] {member.display_name} -- {study_secs}s study (below minimum)")
                await save_data(data)

            await update_voice_channel_status(channel, None)
            await update_bot_presence(data)
        elif ch_type == "study":
            # --- STUDY SESSION: full tracking ---
            udata["total_seconds_alltime"] = udata.get("total_seconds_alltime", 0) + session_seconds
            udata["total_seconds_weekly"] = udata.get("total_seconds_weekly", 0) + session_seconds
            udata["total_seconds_today"] = udata.get("total_seconds_today", 0) + session_seconds
            udata["session_count"] = udata.get("session_count", 0) + 1

            if session_seconds > udata.get("longest_session_seconds", 0):
                udata["longest_session_seconds"] = session_seconds
            if udata["total_seconds_today"] > udata.get("best_day_seconds", 0):
                udata["best_day_seconds"] = udata["total_seconds_today"]

            # Record daily history for heatmap
            today_str = datetime.date.today().isoformat()
            if "daily_history" not in udata:
                udata["daily_history"] = {}
            udata["daily_history"][today_str] = udata.get("total_seconds_today", 0)

            update_streak(udata)
            await save_data(data)

            logging.info(f"[STUDY END] {member.display_name} -- {format_time_precise(session_seconds)} in #{channel.name}")

            await send_session_log(member, session_seconds, data)
            await check_and_award_milestones(member, data)
            await update_leaderboard_embed(current_view_mode)

            await update_voice_channel_status(channel, None)
            await update_bot_presence(data)

        elif ch_type == "doubt":
            # --- DOUBT SESSION: tracked separately, no milestones ---
            udata["total_seconds_doubt"] = udata.get("total_seconds_doubt", 0) + session_seconds
            udata["total_seconds_doubt_weekly"] = udata.get("total_seconds_doubt_weekly", 0) + session_seconds
            udata["doubt_session_count"] = udata.get("doubt_session_count", 0) + 1
            await save_data(data)

            logging.info(f"[DOUBT END] {member.display_name} -- {format_time_precise(session_seconds)} in #{channel.name}")

            await send_doubt_log(member, session_seconds, data, channel)
            await check_and_award_doubt_milestones(member, data)

            await update_voice_channel_status(channel, None)
            await update_bot_presence(data)

        elif ch_type == "discussion":
            # --- DISCUSSION SESSION: log only, no achievements ---
            udata["total_seconds_discussion"] = udata.get("total_seconds_discussion", 0) + session_seconds
            udata["discussion_session_count"] = udata.get("discussion_session_count", 0) + 1
            await save_data(data)

            logging.info(f"[DISCUSSION END] {member.display_name} -- {format_time_precise(session_seconds)} in #{channel.name}")

            await send_discussion_log(member, session_seconds, data, channel)

            await update_voice_channel_status(channel, None)
            await update_bot_presence(data)
    except Exception as e:
        logging.error(f"Error handling voice leave for {member.display_name}: {e}")


# ============================================================
# SECTION 4b: TEXT MESSAGE TRACKING
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    """Tracks messages in study text channels for the text activity leaderboard."""
    if message.author.bot:
        return

    # Track messages in study text channels
    if message.channel.id in STUDY_TEXT_CHANNELS:
        try:
            data = await load_data()
            udata = ensure_user(data, message.author)
            udata["total_messages"] = udata.get("total_messages", 0) + 1
            udata["messages_today"] = udata.get("messages_today", 0) + 1
            udata["messages_weekly"] = udata.get("messages_weekly", 0) + 1
            await save_data(data)

            # Award text milestone roles (only highest, remove lower)
            total_msgs = udata.get("messages_weekly", 0)
            guild = message.guild
            if guild:
                member = guild.get_member(message.author.id)
                if member:
                    earned_role_id = None
                    for threshold in sorted(TEXT_MILESTONE_ROLES.keys()):
                        if total_msgs >= threshold:
                            earned_role_id = TEXT_MILESTONE_ROLES[threshold]

                    # Check BEFORE removal to avoid celebration spam
                    already_has = discord.utils.get(member.roles, id=earned_role_id) if earned_role_id else None

                    # Remove all text milestone roles, then add highest
                    all_text_role_ids = set(TEXT_MILESTONE_ROLES.values())
                    roles_to_remove = [r for r in member.roles if r.id in all_text_role_ids]
                    if roles_to_remove:
                        try:
                            await member.remove_roles(*roles_to_remove, reason="Text milestone update")
                        except Exception:
                            pass

                    if earned_role_id:
                        role = guild.get_role(earned_role_id)
                        if role:
                            try:
                                await member.add_roles(role, reason=f"Text milestone: {total_msgs} msgs/week")
                            except Exception:
                                pass
        except Exception as e:
            logging.error(f"Error tracking message from {message.author.display_name}: {e}")

    # Allow prefix commands to still work
    await bot.process_commands(message)


# ============================================================
# SECTION 9b: GROUP POMODORO BACKGROUND TASKS
# ============================================================

async def pomodoro_status_loop():
    """Updates the pomodoro voice channel status every 30 seconds."""
    await bot.wait_until_ready()
    last_phase = None
    while not bot.is_closed():
        try:
            channel = bot.get_channel(POMODORO_CHANNEL_ID)
            if channel is None:
                await asyncio.sleep(30)
                continue

            phase, remaining, _ = get_pomodoro_phase()
            time_str = format_mm_ss(remaining)

            if phase == "study":
                status_text = f"\U0001f534 Study Time \u2014 {time_str} left"
            else:
                status_text = f"\U0001f7e2 Break Time \u2014 {time_str} left"

            # Update channel status via API
            try:
                headers = {
                    "Authorization": f"Bot {os.getenv('BOT_TOKEN')}",
                    "Content-Type": "application/json",
                }
                async with aiohttp.ClientSession() as session:
                    await session.put(
                        f"https://discord.com/api/v10/channels/{POMODORO_CHANNEL_ID}/voice-status",
                        headers=headers,
                        json={"status": status_text},
                    )
            except Exception as e:
                logging.debug(f"Could not update pomodoro channel status: {e}")

            # Send alert on phase transition
            if last_phase is not None and last_phase != phase:
                await send_pomodoro_alert(channel, phase)
            last_phase = phase

        except Exception as e:
            logging.error(f"Pomodoro status loop error: {e}")
        await asyncio.sleep(30)


async def send_pomodoro_alert(channel: discord.VoiceChannel, new_phase: str):
    """Sends a phase transition alert to the log channel."""
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel is None:
            return

        # Get members currently in the pomodoro channel
        members_in_channel = [m for m in channel.members if not m.bot]
        if not members_in_channel:
            return  # Don't send alerts if nobody's there

        mentions = " ".join(m.mention for m in members_in_channel)

        if new_phase == "study":
            embed = discord.Embed(
                title="\U0001f534 STUDY TIME STARTED!",
                description=(
                    f"Break's over! Time to focus for **{POMODORO_STUDY_SECONDS // 60} minutes**.\n\n"
                    f"Currently in Pomodoro: {mentions}"
                ),
                color=0xED4245,  # Red
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.set_footer(text="Heads down. Phones away. Let's go.")
        else:
            embed = discord.Embed(
                title="\U0001f7e2 BREAK TIME!",
                description=(
                    f"Great work! Take a **{POMODORO_BREAK_SECONDS // 60} minute** break.\n\n"
                    f"Currently in Pomodoro: {mentions}"
                ),
                color=0x57F287,  # Green
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.set_footer(text="Stretch, hydrate, breathe. You earned it. \U0001f331")

        await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send pomodoro alert: {e}")


async def individual_pomodoro_loop(user_id: int):
    """Background task for an individual pomodoro session."""
    try:
        while user_id in active_pomodoros:
            pomo = active_pomodoros[user_id]
            study_secs = pomo["study_seconds"]
            break_secs = pomo["break_seconds"]
            cycle_num = pomo.get("cycle", 0) + 1
            pomo["cycle"] = cycle_num
            pomo["current_phase"] = "study"
            pomo["phase_end"] = int(time.time()) + study_secs

            # Notify study start
            try:
                user = bot.get_user(user_id)
                if user:
                    embed = discord.Embed(
                        title=f"\U0001f534 Pomodoro #{cycle_num} \u2014 Study Time!",
                        description=f"Focus for **{study_secs // 60} minutes**. Go!",
                        color=0xED4245,
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                    await user.send(embed=embed)
            except Exception:
                pass

            # Wait for study period
            await asyncio.sleep(study_secs)
            if user_id not in active_pomodoros:
                break

            pomo["current_phase"] = "break"
            pomo["phase_end"] = int(time.time()) + break_secs
            pomo["total_study_seconds"] = pomo.get("total_study_seconds", 0) + study_secs

            # Notify break start
            try:
                user = bot.get_user(user_id)
                if user:
                    embed = discord.Embed(
                        title=f"\U0001f7e2 Pomodoro #{cycle_num} \u2014 Break Time!",
                        description=f"Nice work! Rest for **{break_secs // 60} minutes**.",
                        color=0x57F287,
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                    await user.send(embed=embed)
            except Exception:
                pass

            # Wait for break period
            await asyncio.sleep(break_secs)
            if user_id not in active_pomodoros:
                break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Individual pomodoro error for {user_id}: {e}")
    finally:
        # Send session summary to study-logs channel
        pomo = active_pomodoros.get(user_id, {})
        total_study = pomo.get("total_study_seconds", 0)
        cycles = pomo.get("cycle", 0)
        if total_study > 0:
            try:
                log_ch = bot.get_channel(LOG_CHANNEL_ID)
                user = bot.get_user(user_id)
                if log_ch and user:
                    accent = USER_COLORS.get(user_id, DEFAULT_COLOR)
                    embed = discord.Embed(color=accent)
                    embed.set_author(
                        name=f"{user.display_name} — Personal Pomodoro Complete",
                        icon_url=user.display_avatar.url if user.display_avatar else None,
                    )
                    if user.display_avatar:
                        embed.set_thumbnail(url=user.display_avatar.url)
                    embed.add_field(name="🍅 Type", value="Personal Pomodoro", inline=True)
                    embed.add_field(name="🔄 Cycles", value=str(cycles), inline=True)
                    embed.add_field(name="📚 Study Time", value=format_time(total_study), inline=True)
                    study_min = pomo.get("study_seconds", 0) // 60
                    break_min = pomo.get("break_seconds", 0) // 60
                    embed.add_field(name="⚙️ Settings", value=f"{study_min}m study / {break_min}m break", inline=True)
                    embed.add_field(name="📅 Date", value=f"<t:{int(time.time())}:D>", inline=True)
                    embed.add_field(name="⌚ Finished", value=f"<t:{int(time.time())}:R>", inline=True)
                    embed.set_footer(text=random.choice(MOTIVATIONAL_QUOTES))
                    embed.timestamp = datetime.datetime.now(datetime.UTC)
                    await log_ch.send(embed=embed)
            except Exception as log_err:
                logging.error(f"Failed to log individual pomo session: {log_err}")
        active_pomodoros.pop(user_id, None)


# ============================================================
# SECTION 9c: WEEKLY GRAPH DM
# ============================================================

async def weekly_graph_dm_loop():
    """Every Sunday at 9 PM IST (UTC+5:30), sends a weekly study graph DM to all tracked users."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Check every 10 minutes if it's Sunday 9 PM IST
            now_utc = datetime.datetime.now(datetime.UTC)
            ist_offset = datetime.timedelta(hours=5, minutes=30)
            now_ist = now_utc + ist_offset

            if now_ist.weekday() == 6 and now_ist.hour == 21 and now_ist.minute < 10:
                logging.info("[WEEKLY GRAPH] Generating weekly study graphs...")
                await send_weekly_graphs()
                # Sleep until next day to avoid duplicate sends
                await asyncio.sleep(3600 * 12)
            else:
                await asyncio.sleep(600)  # Check every 10 minutes
        except Exception as e:
            logging.error(f"Weekly graph loop error: {e}")
            await asyncio.sleep(600)


async def send_weekly_graphs():
    """Generates and sends a study graph to each tracked user via DM."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from io import BytesIO
    except ImportError:
        logging.error("matplotlib not installed. Cannot generate weekly graphs.")
        return

    data = await load_data()
    today = datetime.date.today()

    # Get the last 7 days
    days = []
    for i in range(6, -1, -1):
        days.append(today - datetime.timedelta(days=i))

    day_labels = [d.strftime("%a\n%d") for d in days]
    day_strs = [d.isoformat() for d in days]

    for uid, udata in data.get("users", {}).items():
        try:
            user = bot.get_user(int(uid))
            if user is None or user.bot:
                continue

            history = udata.get("daily_history", {})
            hours = [history.get(ds, 0) / 3600 for ds in day_strs]
            total_week = sum(hours)

            if total_week == 0:
                continue  # Skip users with no activity this week

            # Generate the graph
            fig = Figure(figsize=(8, 4))
            fig.patch.set_facecolor('#2B2D31')
            ax = fig.subplots()
            ax.set_facecolor('#1E1F22')

            # Bar colors: gradient from dim to bright based on hours
            colors = []
            for h in hours:
                if h >= 3:
                    colors.append('#57F287')  # Green (intense)
                elif h >= 1:
                    colors.append('#5865F2')  # Blurple (good)
                elif h > 0:
                    colors.append('#FEE75C')  # Yellow (light)
                else:
                    colors.append('#4F545C')  # Gray (none)

            bars = ax.bar(day_labels, hours, color=colors, width=0.6, edgecolor='none', zorder=3)

            # Add hour labels on top of bars
            for bar, h in zip(bars, hours):
                if h > 0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.1,
                        f"{h:.1f}h",
                        ha='center', va='bottom',
                        color='white', fontsize=10, fontweight='bold',
                    )

            ax.set_ylabel('Hours', color='white', fontsize=12)
            ax.set_title(
                f"{udata.get('username', 'User')}'s Weekly Study Report",
                color='white', fontsize=14, fontweight='bold', pad=15,
            )

            # Style axes
            ax.tick_params(colors='white', labelsize=10)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#4F545C')
            ax.spines['bottom'].set_color('#4F545C')
            ax.yaxis.grid(True, color='#4F545C', alpha=0.3, zorder=0)

            # Add total label
            avg_daily = total_week / 7
            ax.text(
                0.98, 0.95,
                f"Total: {total_week:.1f}h | Avg: {avg_daily:.1f}h/day",
                transform=ax.transAxes, ha='right', va='top',
                color='#B5BAC1', fontsize=10,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#1E1F22', edgecolor='#4F545C', alpha=0.8),
            )

            fig.tight_layout()

            # Save to buffer
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)

            # Send DM
            embed = discord.Embed(
                title="\U0001f4ca Weekly Study Report",
                description=(
                    f"Here's your study breakdown for the past week!\n\n"
                    f"\U0001f4da Total: **{total_week:.1f} hours**\n"
                    f"\U0001f4c5 Best day: **{max(hours):.1f}h**\n"
                    f"\U0001f525 Study days: **{sum(1 for h in hours if h > 0)}/7**"
                ),
                color=USER_COLORS.get(int(uid), DEFAULT_COLOR),
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.set_image(url="attachment://weekly_graph.png")
            embed.set_footer(text="New week, new grind. Let's go! \U0001f4aa")

            file = discord.File(buf, filename="weekly_graph.png")
            await user.send(embed=embed, file=file)
            logging.info(f"[WEEKLY GRAPH] Sent to {udata.get('username', uid)}")

        except discord.Forbidden:
            logging.warning(f"[WEEKLY GRAPH] Cannot DM user {uid} (DMs disabled)")
        except Exception as e:
            logging.error(f"[WEEKLY GRAPH] Error for user {uid}: {e}")

    # Also post to the leaderboard channel
    try:
        lb_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if lb_channel:
            embed = discord.Embed(
                title="\U0001f4ca Weekly Reports Sent!",
                description="Check your DMs for your personalized weekly study graph! \U0001f4e9",
                color=0x5865F2,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            await lb_channel.send(embed=embed)
    except Exception:
        pass


# ============================================================
# SECTION 10: KEEP-ALIVE WEB SERVER
# ============================================================

async def handle_root(request):
    """Serves the status page for uptime checks."""
    html = """<!DOCTYPE html>
<html>
<head><title>Valence Bot Status</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px;background:#2b2d31;color:#fff">
<h1>📚 Valence Bot — Active</h1>
<p>Discord study tracker is running. Uptime checks pass here.</p>
</body>
</html>"""
    return aiohttp.web.Response(text=html, content_type="text/html")


async def handle_health(request):
    """Returns a JSON health check response."""
    return aiohttp.web.Response(text='{"status":"ok"}', content_type="application/json")


async def start_keepalive_server():
    """Starts the aiohttp web server for uptime monitoring."""
    app = aiohttp.web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = aiohttp.web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logging.info(f"Keep-alive web server started on port {port}")


# ============================================================
# SECTION 11: ON_READY EVENT
# ============================================================

@bot.event
async def on_ready():
    """Fires when the bot has connected and is ready."""
    guild_count = len(bot.guilds)
    banner = (
        "\n"
        "+======================================+\n"
        "|     Valence Bot -- Online            |\n"
        f"|  Logged in as: {str(bot.user):<21s} |\n"
        f"|  Serving {guild_count} guild(s){' ' * (18 - len(str(guild_count)))}|\n"
        "|  Keep-alive server: :8080            |\n"
        "+======================================+"
    )
    logging.info(banner)

    # Load data and check for orphaned sessions (crash recovery)
    data = await load_data()
    for uid, udata in data.get("users", {}).items():
        if udata.get("session_start_timestamp") is not None:
            username = udata.get("username", uid)
            logging.warning(
                f"[CRASH RECOVERY] Found orphaned session for {username} "
                f"(started at {udata['session_start_timestamp']}). Clearing."
            )
            udata["session_start_timestamp"] = None
    await save_data(data)

    # Start background tasks
    asyncio.create_task(presence_rotation_loop())
    asyncio.create_task(check_weekly_reset(data))
    asyncio.create_task(pomodoro_status_loop())
    asyncio.create_task(weekly_graph_dm_loop())
    asyncio.create_task(start_keepalive_server())

    # Restore persistent view for leaderboard buttons
    bot.add_view(LeaderboardView("alltime"))

    # Restore/create leaderboard embed
    await update_leaderboard_embed("alltime")

    # Sync slash commands
    try:
        target_guild = discord.Object(id=1514186381348306964)
        bot.tree.copy_global_to(guild=target_guild)
        synced = await bot.tree.sync(guild=target_guild)
        logging.info(f"Successfully copied and synced {len(synced)} command(s) to target guild (ID: 1514186381348306964)")
    except Exception as e:
        logging.error(f"Error during slash command synchronization: {e}", exc_info=True)


    logging.info("Bot ready. All systems operational.")


# ============================================================
# SECTION 12: SLASH COMMANDS
# ============================================================

@bot.tree.command(name="stats", description="View detailed study statistics for yourself or another user.")
@app_commands.describe(user="The user to view stats for (defaults to yourself)")
async def stats_command(interaction: discord.Interaction, user: discord.Member | None = None):
    """Shows a detailed stats embed for the given user or the caller."""
    try:
        target = user or interaction.user
        data = await load_data()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.response.send_message(
                f"📭 No study data found for **{target.display_name}**. They need to join a voice channel first!",
                ephemeral=True,
            )
            return

        udata = data["users"][uid]
        accent_color = USER_COLORS.get(target.id, DEFAULT_COLOR)
        total_hours = udata.get("total_seconds_alltime", 0) / 3600
        emblem = get_rank_emblem(total_hours)
        streak_display = get_streak_display(udata.get("current_streak_days", 0))
        daily_goal = udata.get("daily_goal_seconds", DAILY_GOAL_SECONDS)
        today_secs = udata.get("total_seconds_today", 0)
        daily_bar = generate_progress_bar(today_secs, daily_goal)

        embed = discord.Embed(
            title=f"{emblem} {target.display_name}'s Study Profile",
            color=accent_color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        # Live session indicator
        if udata.get("session_start_timestamp") is not None:
            started = udata["session_start_timestamp"]
            embed.add_field(
                name="⏱️ LIVE SESSION",
                value=f"Started <t:{started}:R>",
                inline=False,
            )

        embed.add_field(
            name="🕐 All-Time",
            value=format_time(udata.get("total_seconds_alltime", 0)),
            inline=True,
        )
        embed.add_field(
            name="📅 This Week",
            value=format_time(udata.get("total_seconds_weekly", 0)),
            inline=True,
        )
        embed.add_field(
            name="📊 Today",
            value=f"{format_time(today_secs)}\n{daily_bar}",
            inline=True,
        )
        embed.add_field(
            name="🔥 Streak",
            value=streak_display,
            inline=True,
        )
        embed.add_field(
            name="📌 Total Sessions",
            value=str(udata.get("session_count", 0)),
            inline=True,
        )
        embed.add_field(
            name="🎯 Daily Goal",
            value=format_time(daily_goal),
            inline=True,
        )

        # Personal records section
        embed.add_field(name="\u200b", value="\u2500" * 25, inline=False)
        embed.add_field(
            name="\U0001f4c8 Personal Records",
            value=(
                f"\u26a1 Longest session: **{format_time(udata.get('longest_session_seconds', 0))}**\n"
                f"\U0001f3c6 Best single day: **{format_time(udata.get('best_day_seconds', 0))}**\n"
                f"\U0001f525 Longest streak: **{udata.get('longest_streak_days', 0)} days**"
            ),
            inline=False,
        )

        # Doubt & Discussion breakdown
        doubt_secs = udata.get("total_seconds_doubt", 0)
        doubt_count = udata.get("doubt_session_count", 0)
        disc_secs = udata.get("total_seconds_discussion", 0)
        disc_count = udata.get("discussion_session_count", 0)
        if doubt_secs > 0 or disc_secs > 0:
            breakdown_lines = []
            if doubt_secs > 0:
                breakdown_lines.append(f"\u2753 Doubt sessions: **{doubt_count}** ({format_time(doubt_secs)})")
            if disc_secs > 0:
                breakdown_lines.append(f"\U0001f4ac Discussion sessions: **{disc_count}** ({format_time(disc_secs)})")
            embed.add_field(
                name="\U0001f4cb Activity Breakdown",
                value="\n".join(breakdown_lines),
                inline=False,
            )

        embed.set_footer(text="Keep grinding. Every minute counts.")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Stats command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred fetching stats.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@bot.tree.command(name="goal", description="Set your personal daily study goal.")
@app_commands.describe(hours="Your daily goal in hours (e.g., 2.5 for 2 hours 30 minutes)")
async def goal_command(interaction: discord.Interaction, hours: float):
    """Sets the user's personal daily study goal."""
    try:
        if hours <= 0 or hours > 24:
            await interaction.response.send_message(
                "❌ Please set a goal between 0 and 24 hours.", ephemeral=True
            )
            return

        data = await load_data()
        uid = str(interaction.user.id)
        if uid not in data["users"]:
            data["users"][uid] = _default_user(interaction.user.display_name)

        goal_seconds = int(hours * 3600)
        data["users"][uid]["daily_goal_seconds"] = goal_seconds
        await save_data(data)

        accent_color = USER_COLORS.get(interaction.user.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title="🎯 Daily Goal Updated!",
            description=(
                f"Your new daily study goal is **{format_time(goal_seconds)}**.\n\n"
                f"Today's progress:\n"
                f"{generate_progress_bar(data['users'][uid].get('total_seconds_today', 0), goal_seconds)}"
            ),
            color=accent_color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text="Consistency is key. 💪")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Goal command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred setting your goal.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@bot.tree.command(name="lb", description="Manually refresh the study leaderboard.")
async def lb_command(interaction: discord.Interaction):
    """Triggers a manual leaderboard refresh."""
    try:
        await interaction.response.defer(ephemeral=True)
        await update_leaderboard_embed(current_view_mode)
        await interaction.followup.send("✅ Leaderboard refreshed!", ephemeral=True)
    except Exception as e:
        logging.error(f"Leaderboard command error: {e}")
        try:
            await interaction.followup.send("❌ An error occurred refreshing the leaderboard.", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="leaderboard", description="Show the leaderboard in this channel.")
@app_commands.describe(view="Which leaderboard to show (default: alltime)")
@app_commands.choices(view=[
    app_commands.Choice(name="All-Time", value="alltime"),
    app_commands.Choice(name="Weekly", value="weekly"),
    app_commands.Choice(name="Doubt", value="doubt"),
    app_commands.Choice(name="Text Activity", value="messages"),
])
async def leaderboard_command(interaction: discord.Interaction, view: app_commands.Choice[str] | None = None):
    """Shows the leaderboard embed in the current channel."""
    try:
        selected = view.value if view else "alltime"
        data = await load_data()
        embed = build_leaderboard_embed(data, selected)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Leaderboard command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred showing the leaderboard.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@bot.tree.command(name="whostudying", description="See who's currently in a voice channel.")
async def whostudying_command(interaction: discord.Interaction):
    """Shows who is currently in voice channels."""
    try:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        lines = []
        for vc in guild.voice_channels:
            members = [m for m in vc.members if not m.bot]
            if members:
                ch_type = get_channel_type(vc.id)
                type_emoji = {"study": "📚", "doubt": "❓", "discussion": "💬"}.get(ch_type, "🔊")
                member_names = ", ".join(m.display_name for m in members)
                lines.append(f"{type_emoji} **#{vc.name}** ({ch_type.title()})\n> {member_names}")

        if not lines:
            embed = discord.Embed(
                title="🔇 Voice Channels",
                description="Nobody is studying right now. Be the first!",
                color=0x99AAB5,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
        else:
            embed = discord.Embed(
                title="🔊 Currently in Voice",
                description="\n\n".join(lines),
                color=0x57F287,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            embed.set_footer(text=f"{sum(len([m for m in vc.members if not m.bot]) for vc in guild.voice_channels)} people active")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Whostudying command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@bot.tree.command(name="compare", description="Compare your stats head-to-head with another user.")
@app_commands.describe(user="The user to compare yourself against")
async def compare_command(interaction: discord.Interaction, user: discord.Member):
    """Compares the caller's stats with another user side-by-side."""
    try:
        caller = interaction.user
        data = await load_data()
        caller_uid = str(caller.id)
        target_uid = str(user.id)

        if caller_uid not in data["users"] and target_uid not in data["users"]:
            await interaction.response.send_message("📭 Neither of you have study data yet!", ephemeral=True)
            return

        c = data["users"].get(caller_uid, _default_user(caller.display_name))
        t = data["users"].get(target_uid, _default_user(user.display_name))

        def indicator(a, b):
            if a > b:
                return "◀️"
            elif b > a:
                return "▶️"
            return "🤝"

        categories = [
            ("📚 Study Time", c.get("total_seconds_alltime", 0), t.get("total_seconds_alltime", 0), True),
            ("📅 Weekly Time", c.get("total_seconds_weekly", 0), t.get("total_seconds_weekly", 0), True),
            ("📌 Sessions", c.get("session_count", 0), t.get("session_count", 0), False),
            ("🔥 Streak", c.get("current_streak_days", 0), t.get("current_streak_days", 0), False),
            ("❓ Doubt Time", c.get("total_seconds_doubt", 0), t.get("total_seconds_doubt", 0), True),
            ("💬 Discussion", c.get("total_seconds_discussion", 0), t.get("total_seconds_discussion", 0), True),
        ]

        lines = []
        for label, cv, tv, is_time in categories:
            arrow = indicator(cv, tv)
            if is_time:
                lines.append(f"{label}\n`{format_time(cv):>10}` {arrow} `{format_time(tv):<10}`")
            else:
                lines.append(f"{label}\n`{str(cv):>10}` {arrow} `{str(tv):<10}`")

        embed = discord.Embed(
            title=f"⚔️ {caller.display_name} vs {user.display_name}",
            description="\n\n".join(lines),
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text="◀️ = left leads  |  ▶️ = right leads  |  🤝 = tied")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Compare command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred comparing stats.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@bot.tree.command(name="ping", description="Check if the bot is alive.")
async def ping_command(interaction: discord.Interaction):
    """Responds with the bot's latency."""
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: **{latency_ms}ms**")


# ============================================================
# SECTION 12c: POMODORO COMMANDS
# ============================================================

pomo_group = app_commands.Group(name="pomodoro", description="Pomodoro timer commands.")

@pomo_group.command(name="start", description="Start a personal Pomodoro timer.")
@app_commands.describe(
    study_min="Study duration in minutes (default: 25)",
    break_min="Break duration in minutes (default: 5)",
)
async def pomo_start(interaction: discord.Interaction, study_min: int = 25, break_min: int = 5):
    """Starts an individual pomodoro for the user."""
    try:
        uid = interaction.user.id
        if uid in active_pomodoros:
            await interaction.response.send_message(
                "\u26a0\ufe0f You already have an active Pomodoro! Use `/pomodoro stop` first.",
                ephemeral=True,
            )
            return

        if study_min < 1 or study_min > 120 or break_min < 1 or break_min > 30:
            await interaction.response.send_message(
                "\u274c Study must be 1-120 min, break must be 1-30 min.",
                ephemeral=True,
            )
            return

        pomo_data = {
            "study_seconds": study_min * 60,
            "break_seconds": break_min * 60,
            "started_at": int(time.time()),
            "cycle": 0,
            "current_phase": "study",
            "phase_end": int(time.time()) + study_min * 60,
            "total_study_seconds": 0,
        }
        active_pomodoros[uid] = pomo_data
        task = asyncio.create_task(individual_pomodoro_loop(uid))
        pomo_data["task"] = task

        embed = discord.Embed(
            title="\U0001f345 Personal Pomodoro Started!",
            description=(
                f"\U0001f534 Study: **{study_min} min** \u2192 \U0001f7e2 Break: **{break_min} min**\n\n"
                f"I'll DM you when phases change. Use `/pomodoro stop` to end.\n"
                f"\u26a0\ufe0f This will auto-cancel if you join the group Pomodoro channel."
            ),
            color=0xED4245,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Pomo start error: {e}")
        try:
            await interaction.response.send_message("\u274c Error starting Pomodoro.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@pomo_group.command(name="stop", description="Stop your personal Pomodoro timer.")
async def pomo_stop(interaction: discord.Interaction):
    """Stops the user's individual pomodoro."""
    try:
        uid = interaction.user.id
        if uid not in active_pomodoros:
            await interaction.response.send_message(
                "\U0001f645 You don't have an active Pomodoro.",
                ephemeral=True,
            )
            return

        pomo = active_pomodoros.pop(uid)
        task = pomo.get("task")
        if task:
            task.cancel()

        total_study = pomo.get("total_study_seconds", 0)
        # Add partial study time if currently in study phase
        if pomo.get("current_phase") == "study":
            phase_elapsed = int(time.time()) - (pomo["phase_end"] - pomo["study_seconds"])
            total_study += max(0, min(phase_elapsed, pomo["study_seconds"]))

        cycles = pomo.get("cycle", 0)

        embed = discord.Embed(
            title="\U0001f6d1 Pomodoro Stopped",
            description=(
                f"\U0001f345 Completed **{cycles}** cycle(s)\n"
                f"\U0001f4da Total study time: **{format_time(total_study)}**"
            ),
            color=0xFEE75C,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Pomo stop error: {e}")
        try:
            await interaction.response.send_message("\u274c Error stopping Pomodoro.", ephemeral=True)
        except discord.InteractionResponded:
            pass


@pomo_group.command(name="status", description="Check the current Pomodoro status.")
async def pomo_status(interaction: discord.Interaction):
    """Shows the current pomodoro status (group + individual)."""
    try:
        phase, remaining, into = get_pomodoro_phase()
        time_str = format_mm_ss(remaining)

        if phase == "study":
            group_status = f"\U0001f534 **Study Time** \u2014 {time_str} remaining"
        else:
            group_status = f"\U0001f7e2 **Break Time** \u2014 {time_str} remaining"

        embed = discord.Embed(
            title="\U0001f345 Pomodoro Status",
            color=0xED4245 if phase == "study" else 0x57F287,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(
            name="\U0001f465 Group Pomodoro",
            value=(
                f"{group_status}\n"
                f"Cycle: {POMODORO_STUDY_SECONDS // 60}min study / {POMODORO_BREAK_SECONDS // 60}min break"
            ),
            inline=False,
        )

        # Individual pomodoro status
        uid = interaction.user.id
        if uid in active_pomodoros:
            pomo = active_pomodoros[uid]
            p_phase = pomo.get("current_phase", "study")
            p_remaining = max(0, pomo.get("phase_end", 0) - int(time.time()))
            p_cycles = pomo.get("cycle", 0)
            if p_phase == "study":
                ind_text = f"\U0001f534 Study \u2014 {format_mm_ss(p_remaining)} left (cycle #{p_cycles})"
            else:
                ind_text = f"\U0001f7e2 Break \u2014 {format_mm_ss(p_remaining)} left (cycle #{p_cycles})"
            embed.add_field(
                name="\U0001f9d1 Your Personal Pomodoro",
                value=ind_text,
                inline=False,
            )
        else:
            embed.add_field(
                name="\U0001f9d1 Your Personal Pomodoro",
                value="No active personal timer. Use `/pomodoro start` to begin.",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f"Pomo status error: {e}")
        try:
            await interaction.response.send_message("\u274c Error checking status.", ephemeral=True)
        except discord.InteractionResponded:
            pass


bot.tree.add_command(pomo_group)


@bot.tree.command(name="weeklygraph", description="Get your weekly study graph right now.")
async def weekly_graph_command(interaction: discord.Interaction):
    """Sends the user their weekly study graph immediately."""
    try:
        await interaction.response.defer(ephemeral=True)

        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from io import BytesIO

        data = await load_data()
        uid = str(interaction.user.id)

        if uid not in data["users"]:
            await interaction.followup.send("\U0001f4ed No study data found yet!", ephemeral=True)
            return

        udata = data["users"][uid]
        today = datetime.date.today()

        days = []
        for i in range(6, -1, -1):
            days.append(today - datetime.timedelta(days=i))

        day_labels = [d.strftime("%a\n%d") for d in days]
        day_strs = [d.isoformat() for d in days]
        history = udata.get("daily_history", {})
        hours = [history.get(ds, 0) / 3600 for ds in day_strs]
        total_week = sum(hours)

        # Generate graph
        fig = Figure(figsize=(8, 4))
        fig.patch.set_facecolor('#2B2D31')
        ax = fig.subplots()
        ax.set_facecolor('#1E1F22')

        colors = []
        for h in hours:
            if h >= 3:
                colors.append('#57F287')
            elif h >= 1:
                colors.append('#5865F2')
            elif h > 0:
                colors.append('#FEE75C')
            else:
                colors.append('#4F545C')

        bars = ax.bar(day_labels, hours, color=colors, width=0.6, edgecolor='none', zorder=3)

        for bar, h in zip(bars, hours):
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.1,
                    f"{h:.1f}h",
                    ha='center', va='bottom',
                    color='white', fontsize=10, fontweight='bold',
                )

        ax.set_ylabel('Hours', color='white', fontsize=12)
        ax.set_title(
            f"{udata.get('username', 'User')}'s Weekly Study Report",
            color='white', fontsize=14, fontweight='bold', pad=15,
        )

        ax.tick_params(colors='white', labelsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#4F545C')
        ax.spines['bottom'].set_color('#4F545C')
        ax.yaxis.grid(True, color='#4F545C', alpha=0.3, zorder=0)

        avg_daily = total_week / 7
        ax.text(
            0.98, 0.95,
            f"Total: {total_week:.1f}h | Avg: {avg_daily:.1f}h/day",
            transform=ax.transAxes, ha='right', va='top',
            color='#B5BAC1', fontsize=10,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1E1F22', edgecolor='#4F545C', alpha=0.8),
        )

        fig.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)

        embed = discord.Embed(
            title="\U0001f4ca Your Weekly Study Report",
            description=(
                f"\U0001f4da Total: **{total_week:.1f} hours**\n"
                f"\U0001f4c5 Best day: **{max(hours):.1f}h**\n"
                f"\U0001f525 Study days: **{sum(1 for h in hours if h > 0)}/7**"
            ),
            color=USER_COLORS.get(interaction.user.id, DEFAULT_COLOR),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_image(url="attachment://weekly_graph.png")
        embed.set_footer(text="Keep grinding! \U0001f4aa")

        file = discord.File(buf, filename="weekly_graph.png")
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)
    except Exception as e:
        logging.error(f"Weekly graph command error: {e}")
        try:
            await interaction.followup.send("\u274c Error generating graph.", ephemeral=True)
        except Exception:
            pass


# ============================================================
# SECTION 12b: HEATMAP COMMAND
# ============================================================

@bot.tree.command(name="heatmap", description="View your study calendar heatmap.")
@app_commands.describe(user="The user to view the heatmap for (defaults to yourself)")
async def heatmap_command(interaction: discord.Interaction, user: discord.Member | None = None):
    """Shows a calendar heatmap of study activity for the current month."""
    try:
        target = user or interaction.user
        data = await load_data()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.response.send_message(
                f"📭 No study data found for **{target.display_name}**. They need to join a voice channel first!",
                ephemeral=True,
            )
            return

        udata = data["users"][uid]
        today = datetime.date.today()
        history = udata.get("daily_history", {})
        cal = calendar.monthcalendar(today.year, today.month)
        month_name = calendar.month_name[today.month]

        lines = [f"       {month_name} {today.year}"]
        lines.append("Mo  Tu  We  Th  Fr  Sa  Su")
        for week in cal:
            row = []
            for day in week:
                if day == 0:
                    row.append("  ")
                else:
                    date_str = f"{today.year}-{today.month:02d}-{day:02d}"
                    secs = history.get(date_str, 0)
                    hours = secs / 3600
                    if hours >= 3:
                        row.append("💚")
                    elif hours >= 1:
                        row.append("🟩")
                    elif hours > 0:
                        row.append("🟨")
                    else:
                        row.append("⬛")
            lines.append("  ".join(row))

        calendar_text = "\n".join(lines)

        # Stats for the month
        study_days = 0
        total_month_secs = 0
        for day in range(1, today.day + 1):
            date_str = f"{today.year}-{today.month:02d}-{day:02d}"
            secs = history.get(date_str, 0)
            if secs > 0:
                study_days += 1
                total_month_secs += secs
        total_month_hours = total_month_secs / 3600

        legend = "⬛ No study  🟨 < 1h  🟩 1-3h  💚 3h+"

        accent_color = USER_COLORS.get(target.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f"📅 {target.display_name}'s Study Heatmap",
            description=f"{calendar_text}\n\n{legend}",
            color=accent_color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(
            name="📊 This Month",
            value=f"📆 Study days: **{study_days}**  |  🕐 Total: **{total_month_hours:.1f}h**",
            inline=False,
        )
        embed.set_footer(text="Consistency is key. Fill the calendar! 💪")

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logging.error(f"Heatmap command error: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred generating the heatmap.", ephemeral=True)
        except discord.InteractionResponded:
            pass


# ============================================================
# SECTION 13: ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    bot.run(os.getenv("BOT_TOKEN"))


