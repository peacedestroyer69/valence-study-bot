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
import signal

# --- Timezone Unification to IST ---
IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now() -> datetime.datetime:
    """Returns the current datetime in Indian Standard Time (IST)."""
    return datetime.datetime.now(IST_TZ)

def get_ist_date() -> datetime.date:
    """Returns the current date in Indian Standard Time (IST)."""
    return get_ist_now().date()

# --- Logging Helper Functions ---
def log_info(tag: str, message: str, member: discord.Member | None = None):
    """Log an info-level event with a standard tag format."""
    prefix = f"[{member.display_name}] " if member else ""
    logging.info(f"[{tag}] {prefix}{message}")

def log_warning(tag: str, message: str, member: discord.Member | None = None):
    """Log a warning-level event with a standard tag format."""
    prefix = f"[{member.display_name}] " if member else ""
    logging.warning(f"[{tag}] {prefix}{message}")

def log_error(tag: str, message: str, member: discord.Member | None = None, exc: Exception | None = None):
    """Log an error-level event with optional exception info."""
    prefix = f"[{member.display_name}] " if member else ""
    err_suffix = f" -- Error: {exc}" if exc else ""
    logging.error(f"[{tag}] {prefix}{message}{err_suffix}", exc_info=bool(exc))

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
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "1514208164071870514"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1514208220946763807"))
CELEBRATION_CHANNEL_ID = int(os.getenv("CELEBRATION_CHANNEL_ID", "1514208252760424591"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Google Gemini AI key — add to Render env vars
PUZZLE_CHANNEL_ID = int(os.getenv("PUZZLE_CHANNEL_ID", "1514208252760424591"))  # Channel for daily puzzle

# --- Hardcoded Configuration ---

# Maps total focused study hours (all-time) (int) -> Discord Role ID (int)
# Only the HIGHEST is kept.
MILESTONE_ROLES = {
    5:   1514208595737182338,  # 🥉 Bronze Scholar     — 5 hours
    25:  1514208694051672195,  # 🥈 Silver Grinder     — 25 hours
    50:  1514210766256082954,  # 🥇 Gold Grinder       — 50 hours
    100: 1514208770887127192,  # 💎 Diamond Grindmaster — 100 hours
    200: 1514208898406416505,  # 👑 Legendary Studier   — 200 hours
}

# Doubt milestone roles — awarded based on total doubt session hours (all-time)
# Only the HIGHEST is kept.
DOUBT_MILESTONE_ROLES = {
    2:   1514228187352268830,  # 🔰 Doubt Beginner     — 2 hours
    5:   1514238409449930752,  # 🧠 Doubt Explorer     — 5 hours
    10:  1514238834559291563,  # 💡 Doubt Master       — 10 hours
    25:  1514238964008226988,  # 🎓 Doubt Professor    — 25 hours
    50:  1514254737372090438,  # 🧿 Never Had a Doubt in Life — 50 hours
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

# Text activity milestone roles — based on total messages (all-time) sent in Study Discussion
# Only the HIGHEST is kept.
TEXT_MILESTONE_ROLES = {
    50:   1514254760386236496,  # 📝 Active Learner (50 msgs)
    200:  1514255291578056714,  # 💬 Discussion Pro (200 msgs)
    500:  1514255438093484083,  # 🗣️ Knowledge Sharer (500 msgs)
    1000: 1514255518288576672,  # 📖 Study Sage (1000 msgs)
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

# Leaderboard view mode is stored on the bot object (set in Section 3)


# ============================================================
# SECTION 2: JSON DATABASE
# ============================================================

def _default_data() -> dict:
    """Returns the default empty data structure."""
    today_str = get_ist_date().isoformat()
    return {
        "users": {},
        "meta": {
            "leaderboard_message_id": None,
            "last_weekly_reset": today_str,
            "last_daily_reset": today_str,
            "last_weekly_graph_send": today_str,
        },
    }


def _default_user(username: str) -> dict:
    """Returns the default user entry."""
    today = get_ist_date()
    today_str = today.isoformat()
    current_monday = today - datetime.timedelta(days=today.weekday())
    current_monday_str = current_monday.isoformat()
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
        "last_daily_reset": today_str,
        "last_weekly_reset": current_monday_str,
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
    """Returns the channel category: 'study', 'doubt', 'discussion', or 'untracked'."""
    if channel_id in DOUBT_CHANNELS:
        return "doubt"
    if channel_id in DISCUSSION_CHANNELS:
        return "discussion"
    if channel_id in STUDY_CHANNELS or channel_id == POMODORO_CHANNEL_ID:
        return "study"
    return "untracked"


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
    """Reads and returns the JSON data from Firestore, falls back to local JSON if missing.
    NOTE: This function does NOT acquire any lock. Callers that need to
    read-modify-write must wrap the entire sequence in `bot.db_write_lock`."""
    if db:
        try:
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

    # Local JSON fallback — no lock here; db_write_lock guards writes.
    try:
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
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data


async def save_data(data: dict):
    """Saves data to Firestore and local JSON file.
    Callers MUST hold `bot.db_write_lock` before calling this."""
    if db:
        try:
            def push_doc():
                db.collection('bot_data').document('main').set(data)
            await asyncio.to_thread(push_doc)
        except Exception as e:
            logging.error(f"Firestore write error: {e}")

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except (IOError, OSError) as e:
        logging.error(f"Failed to save data file: {e}")


def enforce_user_resets(udata: dict) -> bool:
    """Enforces daily and weekly resets on user data based on IST dates.
    Returns True if any changes were made."""
    today = get_ist_date()
    today_str = today.isoformat()
    current_monday = today - datetime.timedelta(days=today.weekday())
    current_monday_str = current_monday.isoformat()
    
    changed = False
    
    # 1. Daily Reset Check
    last_daily = udata.get("last_daily_reset")
    if not last_daily:
        last_daily = udata.get("last_study_date") or today_str
        udata["last_daily_reset"] = last_daily
        changed = True
        
    if last_daily != today_str:
        udata["total_seconds_today"] = 0
        udata["messages_today"] = 0
        udata["last_daily_reset"] = today_str
        changed = True

    # 2. Weekly Reset Check
    last_weekly = udata.get("last_weekly_reset")
    if not last_weekly:
        last_weekly = udata.get("weekly_reset_date") or current_monday_str
        udata["last_weekly_reset"] = last_weekly
        changed = True

    if last_weekly != current_monday_str:
        udata["last_week_total_seconds"] = udata.get("total_seconds_weekly", 0)
        udata["total_seconds_weekly"] = 0
        udata["total_seconds_doubt_weekly"] = 0
        udata["messages_weekly"] = 0
        udata["last_weekly_reset"] = current_monday_str
        changed = True
        
    # 3. Streak Decay Check
    last_study = udata.get("last_study_date")
    if last_study:
        try:
            last_date = datetime.date.fromisoformat(last_study)
            if (today - last_date).days > 1:
                if udata.get("current_streak_days", 0) > 0:
                    udata["current_streak_days"] = 0
                    changed = True
        except ValueError:
            pass
            
    return changed


def ensure_user(data: dict, member: discord.Member) -> dict:
    """Ensures a user entry exists in data and returns it."""
    uid = str(member.id)
    if uid not in data["users"]:
        data["users"][uid] = _default_user(member.display_name)
    else:
        data["users"][uid]["username"] = member.display_name
    enforce_user_resets(data["users"][uid])
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
bot.db_write_lock = asyncio.Lock()
bot._message_buffer = {}
bot._message_buffer_lock = asyncio.Lock()
bot.current_view_mode = "alltime"  # Leaderboard view state
bot._http_session = None  # Shared aiohttp session (created in on_ready)

async def get_or_fetch_channel(channel_id: int):
    """Retrieves a channel from cache, or fetches it via the API if not cached."""
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.Forbidden as e:
            logging.warning(
                f"Permission denied (Forbidden) when attempting to fetch channel {channel_id}. "
                f"Ensure the bot has the necessary view and read permissions for this channel. Error: {e}"
            )
        except Exception as e:
            logging.error(f"Failed to fetch channel {channel_id}: {e}")
    return channel

bot.get_or_fetch_channel = get_or_fetch_channel

async def setup_hook():
    for cog_name in ["cogs.discipline", "cogs.bonus_features", "cogs.gaming", "cogs.puzzle_cog"]:
        if cog_name in bot.extensions:
            continue
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


def generate_milestone_progress(total_hours: float) -> str:
    """Generates progress bar and text for the next milestone role."""
    milestones = [5, 25, 50, 100, 200]
    next_m = None
    next_role_name = ""
    role_names = {
        5: "Bronze Scholar (5h)",
        25: "Silver Grinder (25h)",
        50: "Gold Grinder (50h)",
        100: "Diamond Grindmaster (100h)",
        200: "Legendary Studier (200h)"
    }
    for m in milestones:
        if total_hours < m:
            next_m = m
            next_role_name = role_names[m]
            break
            
    if next_m is None:
        return "👑 **Max Milestone Reached!** (Legendary Studier)"
        
    # Generate bar: 10 blocks
    progress = total_hours / next_m
    filled_blocks = int(progress * 10)
    filled_blocks = max(0, min(10, filled_blocks))
    empty_blocks = 10 - filled_blocks
    bar = "🟩" * filled_blocks + "⬜" * empty_blocks
    return f"{bar} {total_hours:.1f}/{next_m}h to **{next_role_name}** ({progress*100:.1f}%)"


def build_leaderboard_embed(data: dict, mode: str) -> discord.Embed:
    """Builds the full leaderboard embed for alltime, weekly, or doubt mode."""
    if mode == "weekly":
        title = "📅 Weekly Standings"
        sort_key = "total_seconds_weekly"
        embed_color = 0x5865F2
    elif mode == "daily":
        title = "📊 Daily Standings"
        sort_key = "total_seconds_today"
        embed_color = 0xEB459E
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
    for uid, udata in users.items():
        enforce_user_resets(udata)
        
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
    bot.current_view_mode = mode
    try:
        async with bot.db_write_lock:
            data = await load_data()
            channel = await get_or_fetch_channel(LEADERBOARD_CHANNEL_ID)
            if channel is None:
                logging.error(f"Leaderboard channel {LEADERBOARD_CHANNEL_ID} not found.")
                return

            db_changed = False
            for uid, udata in data.get("users", {}).items():
                if enforce_user_resets(udata):
                    db_changed = True

            embed = build_leaderboard_embed(data, mode)
            view = LeaderboardView(mode)
            msg_id = data["meta"].get("leaderboard_message_id")

            if msg_id is not None:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(embed=embed, view=view)
                    if db_changed:
                        await save_data(data)
                    return
                except (discord.NotFound, discord.HTTPException):
                    logging.warning("Previous leaderboard message not found. Sending new one.")

            msg = await channel.send(embed=embed, view=view)
            data["meta"]["leaderboard_message_id"] = msg.id
            await save_data(data)
    except Exception as e:
        logging.error(f"Failed to update leaderboard embed: {e}")


class LeaderboardView(discord.ui.View):
    """Persistent view attached to the leaderboard message with buttons to toggle views."""

    def __init__(self, initial_mode: str = "alltime"):
        super().__init__(timeout=None)
        self.current_mode = initial_mode
        
        # Highlight current button
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id:
                if child.custom_id == f"ypt_btn_{initial_mode}":
                    child.style = discord.ButtonStyle.primary
                elif child.custom_id.startswith("ypt_btn_") and child.custom_id != "ypt_btn_refresh":
                    child.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="🏆 All-Time", style=discord.ButtonStyle.secondary, custom_id="ypt_btn_alltime", row=0)
    async def alltime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_mode(interaction, "alltime")

    @discord.ui.button(label="📅 Weekly", style=discord.ButtonStyle.secondary, custom_id="ypt_btn_weekly", row=0)
    async def weekly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_mode(interaction, "weekly")

    @discord.ui.button(label="📊 Daily", style=discord.ButtonStyle.secondary, custom_id="ypt_btn_daily", row=0)
    async def daily_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_mode(interaction, "daily")

    @discord.ui.button(label="❓ Doubts", style=discord.ButtonStyle.secondary, custom_id="ypt_btn_doubt", row=0)
    async def doubt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_mode(interaction, "doubt")

    @discord.ui.button(label="💬 Messages", style=discord.ButtonStyle.secondary, custom_id="ypt_btn_messages", row=0)
    async def messages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_mode(interaction, "messages")

    @discord.ui.button(label="🔄 Refresh Stats", style=discord.ButtonStyle.primary, custom_id="ypt_btn_refresh", row=1)
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

    async def _switch_mode(self, interaction: discord.Interaction, mode: str):
        try:
            self.current_mode = mode
            await interaction.response.defer()
            await update_leaderboard_embed(mode)
        except Exception as e:
            logging.error(f"Switch mode error: {e}")


# ============================================================
# SECTION 6: SESSION LOG EMBED
# ============================================================

async def send_session_log(member: discord.Member, session_seconds: int, data: dict, is_new_pb: bool = False):
    """Sends a detailed session completion embed to the log channel."""
    try:
        channel = await get_or_fetch_channel(LOG_CHANNEL_ID)
        if channel is None:
            logging.error(f"Log channel {LOG_CHANNEL_ID} not found.")
            return

        uid = str(member.id)
        udata = data["users"].get(uid, {})
        quote = random.choice(MOTIVATIONAL_QUOTES)

        daily_total = udata.get("total_seconds_today", 0)
        alltime_total = udata.get("total_seconds_alltime", 0)
        session_count = udata.get("session_count", 0)
        longest_session = udata.get("longest_session_seconds", 0)
        daily_goal = udata.get("daily_goal_seconds", DAILY_GOAL_SECONDS)

        unix_end = int(time.time())

        # Compute richer stats for the embed
        session_hours = session_seconds / 3600
        session_grade = 'S' if session_hours >= 4 else ('A' if session_hours >= 2 else ('B' if session_hours >= 1 else 'C'))
        grade_emoji = {'S': '⭐⭐⭐', 'A': '⭐⭐', 'B': '⭐', 'C': '📗'}[session_grade]
        session_color = (0x9B59B6 if session_hours >= 6 else (0xFFD700 if session_hours >= 3 else (0x57F287 if session_hours >= 1 else 0x3498DB)))

        # Progress bar for daily goal
        daily_goal_h = daily_goal / 3600
        today_hours = daily_total / 3600
        filled = min(int(today_hours / daily_goal_h * 12), 12) if daily_goal_h > 0 else 0
        progress_bar_str = '█' * filled + '░' * (12 - filled)

        # JEE reality check
        jee_min = 6.0
        jee_remaining = max(0, jee_min - today_hours)
        jee_status = '✅ JEE minimum reached!' if today_hours >= jee_min else f'⚡ {jee_remaining:.1f}h to JEE minimum (6h)'

        embed = discord.Embed(color=session_color)
        embed.set_author(
            name=f"{member.display_name} — Study Session Complete [{session_grade}] {grade_emoji}",
            icon_url=member.display_avatar.url if member.display_avatar else None,
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="⏱️ Duration", value=format_time_precise(session_seconds), inline=True)
        embed.add_field(name="📅 Date", value=f"<t:{unix_end}:D>", inline=True)
        embed.add_field(name="⌚ Finished", value=f"<t:{unix_end}:R>", inline=True)

        embed.add_field(
            name="📊 Today's Total",
            value=f"{format_time(daily_total)}\n`{progress_bar_str}` {today_hours:.1f}/{daily_goal_h:.0f}h",
            inline=False,
        )
        embed.add_field(name="🏆 All-Time Total", value=format_time(alltime_total), inline=True)
        embed.add_field(name="⚡ Sessions Today", value=str(session_count), inline=True)

        embed.add_field(
            name="🎯 JEE Reality Check",
            value=jee_status,
            inline=False,
        )

        # Check if this session was a new personal best (passed from caller)
        if is_new_pb:
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
            async with bot.db_write_lock:
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
        log_channel = await get_or_fetch_channel(LOG_CHANNEL_ID)
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
        log_channel = await get_or_fetch_channel(LOG_CHANNEL_ID)
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
        channel = await get_or_fetch_channel(LOG_CHANNEL_ID)
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

        # Reuse the shared aiohttp session (created in on_ready)
        session = bot._http_session
        if session is None or session.closed:
            bot._http_session = aiohttp.ClientSession()
            session = bot._http_session
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


async def flush_message_buffer_loop():
    """Periodically flushes the buffered messages in-memory counter to Firestore."""
    while True:
        try:
            await asyncio.sleep(30)
            async with bot._message_buffer_lock:
                if not bot._message_buffer:
                    continue
                buffer_copy = bot._message_buffer.copy()
                bot._message_buffer.clear()

            async with bot.db_write_lock:
                data = await load_data()
                for uid_str, increment in buffer_copy.items():
                    if uid_str not in data.setdefault("users", {}):
                        username = uid_str
                        for guild in bot.guilds:
                            member = guild.get_member(int(uid_str))
                            if member:
                                username = member.display_name
                                break
                        data["users"][uid_str] = {
                            "username": username,
                            "total_messages": 0,
                            "messages_today": 0,
                            "messages_weekly": 0,
                        }
                    udata = data["users"][uid_str]
                    udata["total_messages"] = udata.get("total_messages", 0) + increment
                    udata["messages_today"] = udata.get("messages_today", 0) + increment
                    udata["messages_weekly"] = udata.get("messages_weekly", 0) + increment
                await save_data(data)

            # Check milestones for active users
            for uid_str in buffer_copy.keys():
                try:
                    uid_int = int(uid_str)
                    for guild in bot.guilds:
                        member = guild.get_member(uid_int)
                        if member:
                            udata = data["users"][uid_str]
                            total_msgs = udata.get("total_messages", 0)
                            earned_threshold = None
                            earned_role_id = None
                            for threshold in sorted(TEXT_MILESTONE_ROLES.keys()):
                                if total_msgs >= threshold:
                                    earned_threshold = threshold
                                    earned_role_id = TEXT_MILESTONE_ROLES[threshold]

                            already_has = (member.get_role(earned_role_id) is not None) if earned_role_id else False

                            if not already_has:
                                all_text_role_ids = set(TEXT_MILESTONE_ROLES.values())
                                roles_to_remove = [r for r in member.roles if r.id in all_text_role_ids and r.id != earned_role_id]
                                if roles_to_remove:
                                    try:
                                        await member.remove_roles(*roles_to_remove, reason="Text milestone update — removing lower/incorrect tiers")
                                    except Exception as e:
                                        logging.error(f"Failed to remove old text milestone roles: {e}")

                                if earned_role_id:
                                    role = guild.get_role(earned_role_id)
                                    if role:
                                        try:
                                            await member.add_roles(role, reason=f"Text milestone: {earned_threshold} messages")
                                            channel = await get_or_fetch_channel(CELEBRATION_CHANNEL_ID)
                                            if channel:
                                                embed = discord.Embed(
                                                    title="📝 TEXT MILESTONE UNLOCKED!",
                                                    description=(
                                                        f"{member.mention} just crossed **{earned_threshold} messages** in study discussion! 💬\n"
                                                        f"Role **{role.name}** has been awarded!"
                                                    ),
                                                    color=0x3498DB,
                                                    timestamp=datetime.datetime.now(datetime.UTC),
                                                )
                                                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                                                await channel.send(embed=embed)
                                        except Exception as r_err:
                                            logging.error(f"Failed to award text milestone role: {r_err}")
                except Exception as member_err:
                    logging.error(f"Error checking milestone for user {uid_str}: {member_err}")

            logging.info(f"[BATCH MESSAGE] Flushed {len(buffer_copy)} user message increments to DB.")
        except Exception as e:
            logging.error(f"[BATCH MESSAGE] Error flushing message buffer: {e}", exc_info=True)


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
    today_str = get_ist_date().isoformat()
    last_study = user_data.get("last_study_date")

    if last_study is None:
        user_data["current_streak_days"] = 1
    else:
        try:
            last_date = datetime.date.fromisoformat(last_study)
            today_date = get_ist_date()
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
    """Background task that checks frequently for weekly and daily resets."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            today = get_ist_date()
            today_str = today.isoformat()
            
            changed = False
            do_weekly_announcement = False
            winner_uid = None
            winner_seconds = 0
            winner_name = "Unknown"
            
            async with bot.db_write_lock:
                data = await load_data()
                if "meta" not in data:
                    data["meta"] = {}
                meta = data["meta"]

                # Check Daily Reset
                last_daily = meta.get("last_daily_reset")
                if last_daily != today_str:
                    for uid, udata in data.get("users", {}).items():
                        enforce_user_resets(udata)
                    meta["last_daily_reset"] = today_str
                    changed = True
                    logging.info(f"Global daily reset performed for {today_str}.")

                # Check Weekly Reset (Monday)
                if today.weekday() == WEEKLY_RESET_DAY:
                    last_weekly = meta.get("last_weekly_reset")
                    if last_weekly != today_str:
                        # Find this week's winner BEFORE resetting
                        for uid, udata in data.get("users", {}).items():
                            if udata.get("last_weekly_reset") == today_str:
                                weekly = udata.get("last_week_total_seconds", 0)
                            else:
                                weekly = udata.get("total_seconds_weekly", 0)

                            if weekly > winner_seconds:
                                winner_seconds = weekly
                                winner_uid = uid
                                winner_name = udata.get("username", "Unknown")

                        # Run enforce_user_resets on all users
                        for uid, udata in data.get("users", {}).items():
                            enforce_user_resets(udata)

                        meta["last_weekly_reset"] = today_str
                        changed = True
                        do_weekly_announcement = True
                        logging.info(f"Global weekly reset performed for {today_str}.")
                
                if changed:
                    await save_data(data)
                    await update_leaderboard_embed("alltime")

            if do_weekly_announcement and winner_uid is not None and winner_seconds > 0:
                try:
                    channel = await get_or_fetch_channel(CELEBRATION_CHANNEL_ID)
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

        except Exception as e:
            logging.error(f"Weekly reset check error: {e}", exc_info=True)
            
        await asyncio.sleep(30)


# ============================================================
# SECTION 9: MILESTONE ROLE SYSTEM
# ============================================================

async def check_and_award_milestones(member: discord.Member, data: dict):
    """Awards the HIGHEST earned study role and removes all lower ones.
    Uses all-time hours for milestones."""
    try:
        uid = str(member.id)
        udata = data["users"].get(uid)
        if udata is None:
            return

        total_hours = udata.get("total_seconds_alltime", 0) / 3600
        guild = member.guild

        # Find the highest milestone the user qualifies for
        earned_threshold = None
        earned_role_id = None
        for hours_threshold in sorted(MILESTONE_ROLES.keys()):
            if total_hours >= hours_threshold:
                earned_threshold = hours_threshold
                earned_role_id = MILESTONE_ROLES[hours_threshold]

        # Determine which roles to remove
        all_milestone_role_ids = set(MILESTONE_ROLES.values())
        roles_to_remove = [r for r in member.roles if r.id in all_milestone_role_ids and r.id != earned_role_id]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Milestone role update — removing lower tiers")
            except (discord.Forbidden, discord.HTTPException) as e:
                logging.error(f"Failed to remove old milestone roles: {e}")

        # Award the highest earned role
        if earned_role_id:
            already_has = discord.utils.get(member.roles, id=earned_role_id)
            if not already_has:
                role = guild.get_role(earned_role_id)
                if role is None:
                    logging.warning(f"Milestone role {earned_role_id} not found in guild.")
                    return

                try:
                    await member.add_roles(role, reason=f"YPT milestone: {earned_threshold} hours")
                except discord.Forbidden:
                    logging.error(f"No permission to assign role {role.name} to {member.display_name}")
                    return
                except discord.HTTPException as e:
                    logging.error(f"Failed to assign milestone role: {e}")
                    return

                try:
                    channel = await get_or_fetch_channel(CELEBRATION_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            title="🎉 MILESTONE UNLOCKED!",
                            description=(
                                f"{member.mention} just crossed **{earned_threshold} hours**! 🔥\n"
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
    Uses all-time doubt hours."""
    try:
        uid = str(member.id)
        udata = data["users"].get(uid)
        if udata is None:
            return

        total_hours = udata.get("total_seconds_doubt", 0) / 3600
        guild = member.guild

        # Find the highest doubt milestone the user qualifies for
        earned_threshold = None
        earned_role_id = None
        for hours_threshold in sorted(DOUBT_MILESTONE_ROLES.keys()):
            if total_hours >= hours_threshold:
                earned_threshold = hours_threshold
                earned_role_id = DOUBT_MILESTONE_ROLES[hours_threshold]

        # Determine which doubt roles to remove
        all_doubt_role_ids = set(DOUBT_MILESTONE_ROLES.values())
        roles_to_remove = [r for r in member.roles if r.id in all_doubt_role_ids and r.id != earned_role_id]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Doubt role update — removing incorrect tiers")
            except (discord.Forbidden, discord.HTTPException) as e:
                logging.error(f"Failed to remove old doubt roles: {e}")

        # Award the highest earned role
        if earned_role_id:
            already_has = discord.utils.get(member.roles, id=earned_role_id)
            if not already_has:
                role = guild.get_role(earned_role_id)
                if role is None:
                    logging.warning(f"Doubt role {earned_role_id} not found in guild.")
                    return

                try:
                    await member.add_roles(role, reason=f"YPT doubt milestone: {earned_threshold} hours")
                except discord.Forbidden:
                    logging.error(f"No permission to assign role {role.name} to {member.display_name}")
                    return
                except discord.HTTPException as e:
                    logging.error(f"Failed to assign doubt role: {e}")
                    return

                try:
                    channel = await get_or_fetch_channel(CELEBRATION_CHANNEL_ID)
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
        ch_type = get_channel_type(channel.id)
        if ch_type == "untracked":
            return

        # If user joins group pomodoro channel, cancel their individual pomodoro
        if channel.id == POMODORO_CHANNEL_ID and member.id in active_pomodoros:
            pomo = active_pomodoros.get(member.id)
            if pomo:
                if pomo.get("current_phase") == "study":
                    phase_elapsed = int(time.time()) - (pomo["phase_end"] - pomo["study_seconds"])
                    added = max(0, min(phase_elapsed, pomo["study_seconds"]))
                    pomo["total_study_seconds"] = pomo.get("total_study_seconds", 0) + added
                    pomo["current_phase"] = "break"
                task = pomo.get("task")
                if task:
                    task.cancel()
            try:
                await member.send("\U0001f504 Your individual Pomodoro was cancelled because you joined the group Pomodoro channel.")
            except Exception:
                pass

        async with bot.db_write_lock:
            data = await load_data()
            udata = ensure_user(data, member)
            udata["session_start_timestamp"] = int(time.time())
            udata["session_channel_id"] = channel.id
            await save_data(data)
        log_info("SESSION START", f"joined #{channel.name}", member)
        # Don't override pomodoro channel status — it has its own status loop
        if channel.id != POMODORO_CHANNEL_ID:
            await update_voice_channel_status(channel, member)
        await update_bot_presence(data)
    except Exception as e:
        logging.error(f"Error handling voice join for {member.display_name}: {e}")


async def _handle_leave(member: discord.Member, channel: discord.VoiceChannel):
    """Processes a voice channel leave event."""
    try:
        ch_type = get_channel_type(channel.id)
        if ch_type == "untracked":
            return

        async with bot.db_write_lock:
            data = await load_data()
            uid = str(member.id)
            udata = ensure_user(data, member)

            start_ts = udata.get("session_start_timestamp")
            if start_ts is None:
                log_warning("SESSION END", "left but had no active session", member)
                if channel.id != POMODORO_CHANNEL_ID:
                    await update_voice_channel_status(channel, None)
                return

            session_seconds = int(time.time()) - start_ts

            if session_seconds < MIN_SESSION_SECONDS:
                log_info("SESSION DISCARD", f"{session_seconds}s (below {MIN_SESSION_SECONDS}s minimum)", member)
                udata["session_start_timestamp"] = None
                udata["session_channel_id"] = None
                await save_data(data)
                if channel.id != POMODORO_CHANNEL_ID:
                    await update_voice_channel_status(channel, None)
                await update_bot_presence(data)
                return

            real_start_ts = start_ts  # Save BEFORE clearing
            udata["session_start_timestamp"] = None
            udata["session_channel_id"] = None

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
                    today_str = get_ist_date().isoformat()
                    if "daily_history" not in udata:
                        udata["daily_history"] = {}
                    udata["daily_history"][today_str] = udata.get("total_seconds_today", 0)

                    update_streak(udata)
                    await save_data(data)

                    total_time_in_channel = int(time.time()) - real_start_ts
                    break_secs = total_time_in_channel - study_secs

                    log_info("POMODORO END", f"{format_time_precise(study_secs)} study ({format_time_precise(break_secs)} break) in #{channel.name}", member)

                    await send_pomodoro_session_log(member, study_secs, break_secs, total_time_in_channel, data)
                    await check_and_award_milestones(member, data)
                    await update_leaderboard_embed(bot.current_view_mode)
                else:
                    log_info("POMODORO DISCARD", f"{study_secs}s study (below minimum)", member)
                    await save_data(data)

                # Keep status updates handled by the background status loop for Group Pomodoro
                if channel.id != POMODORO_CHANNEL_ID:
                    await update_voice_channel_status(channel, None)
                await update_bot_presence(data)
            elif ch_type == "study":
                # --- STUDY SESSION: full tracking ---
                # Capture old PB BEFORE updating for new-PB detection in session log
                old_longest_session = udata.get("longest_session_seconds", 0)
                is_new_pb = session_seconds > old_longest_session

                udata["total_seconds_alltime"] = udata.get("total_seconds_alltime", 0) + session_seconds
                udata["total_seconds_weekly"] = udata.get("total_seconds_weekly", 0) + session_seconds
                udata["total_seconds_today"] = udata.get("total_seconds_today", 0) + session_seconds
                udata["session_count"] = udata.get("session_count", 0) + 1

                if is_new_pb:
                    udata["longest_session_seconds"] = session_seconds
                if udata["total_seconds_today"] > udata.get("best_day_seconds", 0):
                    udata["best_day_seconds"] = udata["total_seconds_today"]

                # Record daily history for heatmap
                today_str = get_ist_date().isoformat()
                if "daily_history" not in udata:
                    udata["daily_history"] = {}
                udata["daily_history"][today_str] = udata.get("total_seconds_today", 0)

                update_streak(udata)
                await save_data(data)

                log_info("STUDY END", f"{format_time_precise(session_seconds)} in #{channel.name}", member)

                await send_session_log(member, session_seconds, data, is_new_pb=is_new_pb)
                await check_and_award_milestones(member, data)
                await update_leaderboard_embed(bot.current_view_mode)

                # Post-leave DM based on session length
                try:
                    session_minutes = session_seconds // 60
                    today_hours = udata.get('total_seconds_today', 0) / 3600
                    ist_now = get_ist_now()

                    if session_minutes < 30:
                        # Short session — come back nudge
                        msg = discord.Embed(
                            title="💨 Short Session Detected",
                            description=f"Only **{session_minutes}m** this session. Breaks are fine — but come back within **10 minutes** and keep the momentum going!",
                            color=0xFFA500
                        )
                        msg.add_field(name="⏱️ Session Length", value=f"{session_minutes}m", inline=True)
                        msg.add_field(name="📊 Today's Total", value=f"{today_hours:.1f}h", inline=True)
                        msg.add_field(name="💡 Tip", value="Even 25-minute Pomodoro sessions add up massively over a day!", inline=False)
                        msg.set_footer(text="YPT Study Bot • Come back soon!")
                    elif today_hours >= 6.0:
                        # Champion territory
                        msg = discord.Embed(
                            title="🏆 Outstanding Session!",
                            description=f"**{format_time_precise(session_seconds)}** session logged. And you're at **{today_hours:.1f}h** today — that's JEE champion territory!",
                            color=0xFFD700
                        )
                        msg.add_field(name="🔥 Today's Total", value=f"{today_hours:.1f}h", inline=True)
                        msg.add_field(name="🎯 JEE Target", value="6h+ ✅", inline=True)
                        msg.add_field(name="💬 Reality Check", value="Top rankers put in days like this consistently. You're building the habit. Keep it up!", inline=False)
                        msg.set_footer(text="YPT Study Bot • You're on the right track!")
                    elif today_hours >= 3.0:
                        # Good but need more
                        msg = discord.Embed(
                            title="✅ Good Session! Keep It Going",
                            description=f"**{format_time_precise(session_seconds)}** banked. You're at **{today_hours:.1f}h** today — solid progress, but JEE minimum is 6h. You've got **{6-today_hours:.1f}h** to go!",
                            color=0x57F287
                        )
                        msg.add_field(name="📊 Today So Far", value=f"{today_hours:.1f}h", inline=True)
                        msg.add_field(name="🎯 6h Target", value=f"{6-today_hours:.1f}h remaining", inline=True)
                        msg.add_field(name="⚡ Don't Stop", value="The gap between good and great is that extra session. Come back in 15 minutes!", inline=False)
                        msg.set_footer(text="YPT Study Bot • Push for 6h!")
                    else:
                        # Under 3h — needs to come back urgently
                        msg = discord.Embed(
                            title="⚡ Come Back Soon!",
                            description=f"**{format_time_precise(session_seconds)}** session done. You're at **{today_hours:.1f}h** today. JEE needs **6h minimum** — you're still **{6-today_hours:.1f}h short**. Rest briefly and get back in!",
                            color=0xEB459E
                        )
                        msg.add_field(name="📊 Today", value=f"{today_hours:.1f}h / 6h target", inline=True)
                        msg.add_field(name="⏰ Remaining", value=f"{6-today_hours:.1f}h needed", inline=True)
                        msg.set_footer(text="YPT Study Bot • Take a short break and return!")

                    dm_user = bot.get_user(member.id) or await bot.fetch_user(member.id)
                    if dm_user:
                        await dm_user.send(embed=msg)
                except Exception as dm_err:
                    logging.warning(f"Could not send post-leave DM to {member.display_name}: {dm_err}")

                await update_voice_channel_status(channel, None)
                await update_bot_presence(data)

            elif ch_type == "doubt":
                # --- DOUBT SESSION: tracked separately, no milestones ---
                udata["total_seconds_doubt"] = udata.get("total_seconds_doubt", 0) + session_seconds
                udata["total_seconds_doubt_weekly"] = udata.get("total_seconds_doubt_weekly", 0) + session_seconds
                udata["doubt_session_count"] = udata.get("doubt_session_count", 0) + 1
                await save_data(data)

                log_info("DOUBT END", f"{format_time_precise(session_seconds)} in #{channel.name}", member)

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
            uid_str = str(message.author.id)
            async with bot._message_buffer_lock:
                bot._message_buffer[uid_str] = bot._message_buffer.get(uid_str, 0) + 1
        except Exception as e:
            logging.error(f"Error buffering message from {message.author.display_name}: {e}")

    # Allow prefix commands to still work
    await bot.process_commands(message)


# ============================================================
# SECTION 9b: GROUP POMODORO BACKGROUND TASKS
# ============================================================

async def notify_members_deafen_undeafen(channel: discord.VoiceChannel):
    """Temporarily server-deafens and undeafens members in the channel to play the notification sound."""
    async def deafen_undeafen(member: discord.Member):
        try:
            if member.voice and member.voice.channel:
                await member.edit(deafen=True)
                await asyncio.sleep(1.0)
                await member.edit(deafen=False)
        except Exception as e:
            logging.warning(f"Failed to deafen/undeafen {member.display_name}: {e}")

    tasks = [asyncio.create_task(deafen_undeafen(m)) for m in channel.members if not m.bot]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def pomodoro_status_loop():
    """Updates the pomodoro voice channel status every 30 seconds."""
    await bot.wait_until_ready()
    last_phase = None
    while not bot.is_closed():
        try:
            channel = await get_or_fetch_channel(POMODORO_CHANNEL_ID)
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
                # Deaf/undeaf notification sound for group pomodoro channel
                asyncio.create_task(notify_members_deafen_undeafen(channel))
            last_phase = phase


        except Exception as e:
            logging.error(f"Pomodoro status loop error: {e}")
            await asyncio.sleep(30)
            continue

        # Sleep for up to 30s, or exactly when the phase transitions
        sleep_time = min(30, remaining)
        if sleep_time <= 0:
            sleep_time = 1
        await asyncio.sleep(sleep_time)


async def send_pomodoro_alert(channel: discord.VoiceChannel, new_phase: str):
    """Sends a phase transition alert to the log channel."""
    try:
        log_channel = await get_or_fetch_channel(LOG_CHANNEL_ID)
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
            embed.set_footer(text="Relax. Rest. Rehydrate.")

        await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Pomodoro alert error: {e}")


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
                        title=f"\U0001f504 Pomodoro #{cycle_num} \u2014 Study Time!",
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

            # Disconnect user from study voice channels on break transition
            try:
                for guild in bot.guilds:
                    member = guild.get_member(user_id)
                    if member and member.voice and member.voice.channel:
                        if member.voice.channel.id != POMODORO_CHANNEL_ID:
                            await member.move_to(None)
                            logging.info(f"[POMODORO] Disconnected {member.display_name} from voice for break.")
            except Exception as e:
                logging.warning(f"Failed to disconnect user {user_id} on individual break transition: {e}")

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
        pomo = active_pomodoros.pop(user_id, None)
        if pomo:
            total_study = pomo.get("total_study_seconds", 0)
            cycles = pomo.get("cycle", 0)
            if total_study > 0:
                try:
                    member = None
                    for guild in bot.guilds:
                        member = guild.get_member(user_id)
                        if member:
                            break
                    if not member:
                        try:
                            member = await bot.fetch_user(user_id)
                        except Exception:
                            pass

                    if member:
                        log_ch = await get_or_fetch_channel(LOG_CHANNEL_ID)
                        if log_ch:
                            accent = USER_COLORS.get(user_id, DEFAULT_COLOR)
                            embed = discord.Embed(color=accent)
                            embed.set_author(
                                name=f"{member.display_name} — Personal Pomodoro Complete",
                                icon_url=member.display_avatar.url if (hasattr(member, 'display_avatar') and member.display_avatar) else None,
                            )
                            if hasattr(member, 'display_avatar') and member.display_avatar:
                                embed.set_thumbnail(url=member.display_avatar.url)
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
                    logging.error(f"Error logging personal pomodoro session completion: {log_err}")


# ============================================================
# SECTION 9c: WEEKLY GRAPH DM
# ============================================================

async def weekly_graph_dm_loop():
    """Background task that checks frequently to send weekly study graphs on Sunday at 9 PM IST."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now_ist = get_ist_now()
            if now_ist.weekday() == 6 and now_ist.hour >= 21:
                today_str = now_ist.date().isoformat()
                
                async with bot.db_write_lock:
                    data = await load_data()
                    if "meta" not in data:
                        data["meta"] = {}
                    last_send = data["meta"].get("last_weekly_graph_send")
                    
                if last_send != today_str:
                    logging.info("[WEEKLY GRAPH] Sunday 9 PM IST reached. Generating and sending weekly study graphs...")
                    await send_weekly_graphs()
                    
                    async with bot.db_write_lock:
                        data = await load_data()
                        if "meta" not in data:
                            data["meta"] = {}
                        data["meta"]["last_weekly_graph_send"] = today_str
                        await save_data(data)
                    logging.info("[WEEKLY GRAPH] Weekly study graphs sent successfully.")
        except Exception as e:
            logging.error(f"Error in weekly_graph_dm_loop: {e}", exc_info=True)
            
        await asyncio.sleep(30)


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
    today = get_ist_date()

    # Get the last 7 days
    days = []
    for i in range(6, -1, -1):
        days.append(today - datetime.timedelta(days=i))

    day_labels = [d.strftime("%a\n%d") for d in days]
    day_strs = [d.isoformat() for d in days]

    for uid, udata in data.get("users", {}).items():
        try:
            user = bot.get_user(int(uid))
            if user is None:
                try:
                    user = await bot.fetch_user(int(uid))
                except Exception as fe:
                    logging.error(f"Failed to fetch user {uid}: {fe}")
                    continue
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
        lb_channel = await get_or_fetch_channel(LEADERBOARD_CHANNEL_ID)
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


_keepalive_runner = None
_keepalive_started = False

async def start_keepalive_server():
    """Starts the aiohttp web server for uptime monitoring."""
    global _keepalive_runner, _keepalive_started
    if _keepalive_started:
        return
    _keepalive_started = True
    app = aiohttp.web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    _keepalive_runner = aiohttp.web.AppRunner(app)
    await _keepalive_runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = aiohttp.web.TCPSite(_keepalive_runner, host="0.0.0.0", port=port)
    await site.start()
    logging.info(f"Keep-alive web server started on port {port}")


# ============================================================
# SECTION 11: ON_READY EVENT
# ============================================================

_bg_tasks_started = False

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

    # Scan guilds for active voice sessions to prevent orphan wipe and track current states
    active_member_vc = {}
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    active_member_vc[str(member.id)] = vc

    # Load data and check active and orphaned sessions (crash recovery)
    data = await load_data()

    # Ensure all server members (excluding bots) are registered in the database
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                ensure_user(data, member)

    now_ts = int(time.time())
    for uid, udata in list(data.get("users", {}).items()):
        is_active = uid in active_member_vc
        has_session = udata.get("session_start_timestamp") is not None
        
        if has_session and not is_active:
            # Orphaned session - user left while bot was offline
            username = udata.get("username", uid)
            logging.warning(
                f"[CRASH RECOVERY] Found orphaned session for {username} "
                f"(started at {udata['session_start_timestamp']}). Clearing."
            )
            udata["session_start_timestamp"] = None
            udata["session_channel_id"] = None
        elif is_active and not has_session:
            # User is in channel but has no session (e.g. joined while bot was offline)
            current_vc = active_member_vc[uid]
            ch_type = get_channel_type(current_vc.id)
            if ch_type != "untracked":
                username = udata.get("username", uid)
                logging.info(
                    f"[CRASH RECOVERY] User {username} is in #{current_vc.name} "
                    f"but has no active session. Starting session now."
                )
                udata["session_start_timestamp"] = now_ts
                udata["session_channel_id"] = current_vc.id
        elif is_active and has_session:
            # User is active and already has session start time
            prev_channel_id = udata.get("session_channel_id")
            current_vc = active_member_vc[uid]
            if prev_channel_id == current_vc.id:
                # Same channel, preserve!
                logging.info(f"[CRASH RECOVERY] Preserving active session for {udata.get('username', uid)} in #{current_vc.name}")
            else:
                # Channel changed while bot was offline
                ch_type = get_channel_type(current_vc.id)
                if ch_type != "untracked":
                    logging.warning(f"[CRASH RECOVERY] User {udata.get('username', uid)} channel changed from {prev_channel_id} to #{current_vc.name} offline. Starting new session.")
                    udata["session_start_timestamp"] = now_ts
                    udata["session_channel_id"] = current_vc.id
                else:
                    logging.warning(f"[CRASH RECOVERY] User {udata.get('username', uid)} moved to untracked channel #{current_vc.name} offline. Clearing session.")
                    udata["session_start_timestamp"] = None
                    udata["session_channel_id"] = None
    await save_data(data)

    # Start background tasks
    global _bg_tasks_started
    if not _bg_tasks_started:
        _bg_tasks_started = True
        asyncio.create_task(presence_rotation_loop())
        asyncio.create_task(check_weekly_reset(data))
        asyncio.create_task(pomodoro_status_loop())
        asyncio.create_task(weekly_graph_dm_loop())
        asyncio.create_task(flush_message_buffer_loop())
        # Keepalive server is started in main() — don't start it again here

    # Initialize shared aiohttp session for voice status updates etc.
    if bot._http_session is None or bot._http_session.closed:
        bot._http_session = aiohttp.ClientSession()

    # Restore persistent view for leaderboard buttons
    bot.add_view(LeaderboardView("alltime"))

    # Restore/create leaderboard embed
    await update_leaderboard_embed("alltime")

    # Sync slash commands globally — also sync to each guild for instant registration
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} global slash command(s) successfully.")
        # Also sync to each connected guild for instant availability
        for guild in bot.guilds:
            try:
                await bot.tree.sync(guild=guild)
                logging.info(f"Synced commands to guild: {guild.name} ({guild.id})")
            except Exception as ge:
                logging.warning(f"Guild sync failed for {guild.name}: {ge}")
    except Exception as e:
        logging.error(f"Error during slash command synchronization: {e}", exc_info=True)


    logging.info("Bot ready. All systems operational.")


@bot.event
async def on_member_join(member: discord.Member):
    """Automatically registers new members in the database as soon as they join."""
    if member.bot:
        return
    try:
        async with bot.db_write_lock:
            data = await load_data()
            ensure_user(data, member)
            # Reset strikes on rejoin to prevent persistent kick loop
            uid = str(member.id)
            if uid in data["users"]:
                data["users"][uid]["discipline_strikes"] = 0
            await save_data(data)
        logging.info(f"[MEMBER JOIN] Registered new member: {member.display_name} ({member.id})")
    except Exception as e:
        logging.error(f"Failed to register new member {member.display_name} on join: {e}")


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
        if enforce_user_resets(udata):
            async with bot.db_write_lock:
                await save_data(data)
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

        # Next Milestone section
        milestone_display = generate_milestone_progress(total_hours)
        embed.add_field(
            name="🏆 Next Milestone Progress",
            value=milestone_display,
            inline=False,
        )

        # Subject hours breakdown
        subject_hours_dict = udata.get("subject_hours", {})
        if subject_hours_dict:
            sub_labels = {
                "physics": "🧪 Physics",
                "chemistry": "⚗️ Chemistry",
                "maths": "📐 Maths",
                "biology": "🧬 Biology",
                "cs": "💻 CS",
                "general": "🌍 General"
            }
            breakdown_parts = []
            for sub_key, label in sub_labels.items():
                secs = subject_hours_dict.get(sub_key, 0)
                if secs > 0:
                    breakdown_parts.append(f"{label}: **{format_time(secs)}**")
            
            if breakdown_parts:
                embed.add_field(
                    name="📚 Subject Breakdown",
                    value=" • ".join(breakdown_parts),
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

        async with bot.db_write_lock:
            data = await load_data()
            uid = str(interaction.user.id)
            if uid not in data["users"]:
                data["users"][uid] = _default_user(interaction.user.display_name)
            udata = data["users"][uid]
            enforce_user_resets(udata)

            goal_seconds = int(hours * 3600)
            udata["daily_goal_seconds"] = goal_seconds
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
        await update_leaderboard_embed(bot.current_view_mode)
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
    app_commands.Choice(name="Daily", value="daily"),
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
        async with bot.db_write_lock:
            data = await load_data()
            caller_uid = str(caller.id)
            target_uid = str(user.id)

            if caller_uid not in data["users"] and target_uid not in data["users"]:
                await interaction.response.send_message("📭 Neither of you have study data yet!", ephemeral=True)
                return

            c_changed = False
            t_changed = False
            if caller_uid in data["users"]:
                c_changed = enforce_user_resets(data["users"][caller_uid])
            if target_uid in data["users"]:
                t_changed = enforce_user_resets(data["users"][target_uid])

            if c_changed or t_changed:
                await save_data(data)

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
        
        # Force the user to be in one of the study voice channels to start
        member = interaction.user
        if not (isinstance(member, discord.Member) and member.voice and member.voice.channel and member.voice.channel.id in STUDY_CHANNELS):
            await interaction.response.send_message(
                "❌ You must be in one of the study voice channels (Study Room or Group Study) to start a personal Pomodoro!",
                ephemeral=True,
            )
            return
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
        pomo = active_pomodoros.get(uid)
        if pomo is None:
            await interaction.response.send_message(
                "\U0001f645 You don't have an active Pomodoro.",
                ephemeral=True,
            )
            return

        # Calculate partial study time if currently in study phase
        if pomo.get("current_phase") == "study":
            phase_elapsed = int(time.time()) - (pomo["phase_end"] - pomo["study_seconds"])
            added = max(0, min(phase_elapsed, pomo["study_seconds"]))
            pomo["total_study_seconds"] = pomo.get("total_study_seconds", 0) + added
            pomo["current_phase"] = "break"

        total_study = pomo.get("total_study_seconds", 0)
        cycles = pomo.get("cycle", 0)

        # Cancel the task. The task's finally block will handle saving & logging.
        task = pomo.get("task")
        if task:
            task.cancel()

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

        async with bot.db_write_lock:
            data = await load_data()
            uid = str(interaction.user.id)

            if uid not in data["users"]:
                await interaction.followup.send("\U0001f4ed No study data found yet!", ephemeral=True)
                return

            udata = data["users"][uid]
            if enforce_user_resets(udata):
                await save_data(data)
        today = get_ist_date()

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
        if enforce_user_resets(udata):
            async with bot.db_write_lock:
                await save_data(data)
        today = get_ist_date()
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
# SECTION 12d: PACE, CHECKIN, AND REMIND COMMANDS
# ============================================================

@bot.tree.command(name='pace', description='See your study pace and JEE target projection for today')
async def pace_command(interaction: discord.Interaction):
    """Shows today's pace, projected hours, and JEE target status."""
    await interaction.response.defer(ephemeral=True)
    try:
        data = await load_data()
        uid = str(interaction.user.id)
        udata = data.get('users', {}).get(uid)
        if not udata:
            await interaction.followup.send('❌ No study data found. Join a study voice channel to get started!', ephemeral=True)
            return

        enforce_user_resets(udata)
        now_ist = get_ist_now()
        seconds_today = udata.get('total_seconds_today', 0)

        # If currently in session, add live seconds
        start_ts = udata.get('session_start_timestamp')
        if start_ts:
            seconds_today += int(time.time()) - start_ts

        hours_today = seconds_today / 3600

        # Calculate pace: hours elapsed since midnight IST
        hours_elapsed = now_ist.hour + now_ist.minute / 60
        hours_remaining = 24 - hours_elapsed

        if hours_elapsed > 0 and hours_today > 0:
            pace = hours_today / hours_elapsed  # hours per hour
            projected = hours_today + pace * hours_remaining
        else:
            pace = 0
            projected = 0

        # JEE targets
        jee_min = 6.0  # minimum hours/day
        jee_target = 8.0  # recommended hours/day
        on_track_min = projected >= jee_min
        on_track_target = projected >= jee_target

        # Progress bar
        def progress_bar(current, target, width=12):
            filled = min(int(current / target * width), width) if target > 0 else 0
            return '█' * filled + '░' * (width - filled)

        status_emoji = '🏆' if on_track_target else ('⚠️' if on_track_min else '🚨')
        status_text = 'On Target!' if on_track_target else ('Borderline' if on_track_min else 'Falling Behind')

        user_color = USER_COLORS.get(interaction.user.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f'📈 Study Pace — {interaction.user.display_name}',
            color=user_color
        )
        embed.add_field(
            name='⏱️ Today So Far',
            value=f'**{hours_today:.1f}h** ({seconds_today//60}m)\n`{progress_bar(hours_today, jee_target)}` {hours_today:.1f}/{jee_target:.0f}h',
            inline=False
        )
        embed.add_field(name='⚡ Current Pace', value=f'{pace:.2f}h/hr', inline=True)
        embed.add_field(name='🔮 Projected by Midnight', value=f'**{projected:.1f}h**', inline=True)
        embed.add_field(
            name=f'{status_emoji} JEE Status: {status_text}',
            value=f'Minimum (6h): {"✅" if on_track_min else "❌ Need " + str(round(jee_min - projected, 1)) + "h more"}\nTarget (8h): {"✅" if on_track_target else "❌ Need " + str(round(jee_target - projected, 1)) + "h more"}',
            inline=False
        )
        embed.set_footer(text=f'Updated at {now_ist.strftime("%H:%M")} IST • Keep grinding!')
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logging.error(f'Error in /pace: {e}', exc_info=True)
        await interaction.followup.send('❌ Something went wrong.', ephemeral=True)


@bot.tree.command(name='checkin', description='Check in with your study plan for today')
@app_commands.describe(plan='What are you planning to study today?')
async def checkin_command(interaction: discord.Interaction, plan: str):
    """Daily check-in with study plan."""
    await interaction.response.defer()
    try:
        data = await load_data()
        uid = str(interaction.user.id)
        udata = ensure_user(data, interaction.user)
        now_ist = get_ist_now()
        today_str = now_ist.date().isoformat()

        # Check if already checked in today
        last_checkin = udata.get('last_checkin_date')
        if last_checkin == today_str:
            await interaction.followup.send('✅ You already checked in today! Get back to studying.', ephemeral=True)
            return

        checkin_streak = udata.get('checkin_streak', 0)
        last_checkin_date_prev = udata.get('last_checkin_date_prev')

        # Check streak
        if last_checkin_date_prev:
            try:
                prev = datetime.date.fromisoformat(last_checkin_date_prev)
                if (now_ist.date() - prev).days == 1:
                    checkin_streak += 1
                else:
                    checkin_streak = 1
            except Exception:
                checkin_streak = 1
        else:
            checkin_streak = 1

        udata['last_checkin_date'] = today_str
        udata['checkin_plan'] = plan
        udata['checkin_streak'] = checkin_streak
        udata['last_checkin_date_prev'] = today_str

        async with bot.db_write_lock:
            await save_data(data)

        user_color = USER_COLORS.get(interaction.user.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f'✅ Check-In Confirmed — {interaction.user.display_name}',
            description=f'Your study plan for today has been logged. Now go execute it!',
            color=user_color
        )
        embed.add_field(name="📋 Today's Plan", value=plan, inline=False)
        embed.add_field(name='🔥 Check-in Streak', value=f'{checkin_streak} day{"s" if checkin_streak != 1 else ""} in a row!', inline=True)
        embed.add_field(name='⏰ Time', value=now_ist.strftime('%H:%M IST'), inline=True)

        checkin_quotes = [
            'Planning is half the battle. Now execute flawlessly.',
            'The plan is set. Time to make it happen.',
            'Commitment starts with showing up. You showed up. Now deliver.',
            'Great plans are nothing without execution. Go grind.',
            "Today's plan logged. Make sure tonight's report is just as good.",
        ]
        embed.add_field(name='💬', value=random.choice(checkin_quotes), inline=False)
        embed.set_footer(text='YPT Study Bot • Daily Check-In System')
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logging.error(f'Error in /checkin: {e}', exc_info=True)
        await interaction.followup.send('❌ Something went wrong.', ephemeral=True)


@bot.tree.command(name='remind', description='Set a personal study reminder')
@app_commands.describe(minutes='Minutes until reminder', message='Reminder message (optional)')
async def remind_command(interaction: discord.Interaction, minutes: int, message: str = 'Time to study!'):
    """Sets a personal study reminder."""
    if minutes < 1 or minutes > 180:
        await interaction.response.send_message('⏰ Minutes must be between 1 and 180.', ephemeral=True)
        return

    await interaction.response.send_message(
        f'✅ Got it! I\'ll remind you in **{minutes} minute{"s" if minutes != 1 else ""}**.',
        ephemeral=True
    )

    async def run_reminder(user, mins, msg):
        await asyncio.sleep(mins * 60)
        try:
            embed = discord.Embed(
                title='⏰ Study Reminder!',
                description=msg,
                color=USER_COLORS.get(user.id, DEFAULT_COLOR)
            )
            embed.set_footer(text=f'Reminder set {mins} minute{"s" if mins != 1 else ""} ago • YPT Study Bot')
            await user.send(embed=embed)
        except Exception:
            pass

    asyncio.create_task(run_reminder(interaction.user, minutes, message))


# ============================================================
# SECTION 13: ENTRY POINT
# ============================================================

async def shutdown(sig=None):
    if sig:
        logging.info(f"Received exit signal {sig}...")
    else:
        logging.info("Shutting down...")
    
    # 1. Close the bot
    if not bot.is_closed():
        await bot.close()
        logging.info("Discord bot client closed.")
        
    # 2. Close shared aiohttp session
    if bot._http_session and not bot._http_session.closed:
        await bot._http_session.close()
        logging.info("Shared aiohttp session closed.")

    # 3. Clean up keep-alive runner
    global _keepalive_runner
    if _keepalive_runner:
        try:
            await _keepalive_runner.cleanup()
            logging.info("Keep-alive runner cleaned up successfully.")
        except Exception as e:
            logging.error(f"Error cleaning up keep-alive runner: {e}")

    # 3. Save database
    try:
        data = await load_data()
        await save_data(data)
        logging.info("Cached database saved successfully.")
    except Exception as e:
        logging.error(f"Error saving database on shutdown: {e}")

    # 4. Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in tasks:
        t.cancel()
    logging.info(f"Cancelling {len(tasks)} outstanding tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("Shutdown complete.")

async def main():
    await start_keepalive_server()
    
    token = os.getenv("BOT_TOKEN")
    if not token:
        logging.critical("BOT_TOKEN is not set in environment variables. Exiting.")
        return

    retry_delay = 5  # Initial backoff delay in seconds
    max_delay = 300  # Maximum backoff delay (5 minutes)

    loop = asyncio.get_running_loop()
    
    def handle_signal(sig):
        asyncio.create_task(shutdown(sig))
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        except NotImplementedError:
            signal.signal(sig, lambda s, f: asyncio.run_coroutine_threadsafe(shutdown(s), loop))

    try:
        async with bot:
            while True:
                try:
                    logging.info("Attempting to connect bot to Discord gateway...")
                    await bot.start(token)
                    if bot.is_closed():
                        break
                except (discord.HTTPException, aiohttp.ClientResponseError) as e:
                    status = getattr(e, "status", None)
                    if status == 429 or "429" in str(e) or "1015" in str(e):
                        logging.warning(
                            f"Discord gateway rate limit hit (HTTP 429 / Error 1015). "
                            f"Retrying in {retry_delay} seconds... Error: {e}"
                        )
                    else:
                        logging.warning(
                            f"Discord connection failed with HTTP exception: {e}. "
                            f"Retrying in {retry_delay} seconds..."
                        )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)
                except Exception as e:
                    logging.warning(
                        f"Unexpected connection/network error in bot main: {e}. "
                        f"Retrying in {retry_delay} seconds...",
                        exc_info=True
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)
    except asyncio.CancelledError:
        logging.info("Main loop cancelled.")
    finally:
        await shutdown()

if __name__ == "__main__":
    # Ensure stdout/stderr logs use IST timezone for %(asctime)s
    def ist_converter(*args):
        return get_ist_now().timetuple()
    logging.Formatter.converter = ist_converter

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())


