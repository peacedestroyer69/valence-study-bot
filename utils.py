# ============================================================
# UTILITIES AND CONFIGURATION — YPT Study Bot
# ============================================================
import datetime
import logging
import discord
import os
from dotenv import load_dotenv

# Load environment variables first so configurations load correctly
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# --- Channel & Role Config from Environment variables ---
PUZZLE_CHANNEL_ID = int(os.getenv("PUZZLE_CHANNEL_ID", "1514208252760424591"))
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "1514186491673985138"))
SERVER_INVITE_LINK = os.getenv("SERVER_INVITE_LINK", "")
POKE_TEXT_CHANNEL_ID = int(os.getenv("POKE_TEXT_CHANNEL_ID", "1514619728285749360"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID", "1514208164071870514"))
STUDY_TEXT_CHANNEL_ID = int(os.getenv("STUDY_TEXT_CHANNEL_ID", "1514241642415001610"))
CHESS_TEXT_CHANNEL_ID = int(os.getenv("CHESS_TEXT_CHANNEL_ID", "1514624613743857775"))
CELEBRATION_CHANNEL_ID = int(os.getenv("CELEBRATION_CHANNEL_ID", "1514208252760424591"))


# --- Timezone Unification to IST ---
IST_TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now() -> datetime.datetime:
    """Returns the current datetime in Indian Standard Time (IST)."""
    return datetime.datetime.now(IST_TZ)

def get_ist_date() -> datetime.date:
    """Returns the current date in Indian Standard Time (IST)."""
    return get_ist_now().date()

# --- Hardcoded Configuration ---
DAILY_GOAL_SECONDS = 5400  # Daily study goal in seconds (1.5 hours)
MIN_SESSION_SECONDS = 60   # Minimum session length to count (prevents AFK abuse)
WEEKLY_RESET_DAY = 0      # Weekly reset day (Monday)

# Maps total focused study hours (all-time) to Discord Role ID
MILESTONE_ROLES = {
    5:   1514208595737182338,  # 🥉 Bronze Scholar     — 5 hours
    25:  1514208694051672195,  # 🥈 Silver Grinder     — 25 hours
    50:  1514210766256082954,  # 🥇 Gold Grinder       — 50 hours
    100: 1514208770887127192,  # 💎 Diamond Grindmaster — 100 hours
    200: 1514208898406416505,  # 👑 Legendary Studier   — 200 hours
}

# Doubt milestone roles
DOUBT_MILESTONE_ROLES = {
    2:   1514228187352268830,  # 🔰 Doubt Beginner     — 2 hours
    5:   1514238409449930752,  # 🧠 Doubt Explorer     — 5 hours
    10:  1514238834559291563,  # 💡 Doubt Master       — 10 hours
    25:  1514238964008226988,  # 🎓 Doubt Professor    — 25 hours
    50:  1514254737372090438,  # 🧿 Never Had a Doubt in Life — 50 hours
}

# Text activity milestone roles
TEXT_MILESTONE_ROLES = {
    50:   1514254760386236496,  # 📝 Active Learner (50 msgs)
    200:  1514255291578056714,  # 💬 Discussion Pro (200 msgs)
    500:  1514255438093484083,  # 🗣️ Knowledge Sharer (500 msgs)
    1000: 1514255518288576672,  # 📖 Study Sage (1000 msgs)
}

# Voice channel configuration
STUDY_CHANNELS = {1514208313452007514, 1514596473629708298}  # Study Room, Group Study
DOUBT_CHANNELS = {
    1514222394628112536,  # Test Discussion stuff
    1514186752301076510,  # Doubt #1
    1514221019005714462,  # Doubt #2
    1514221629864149084,  # Doubt #3
}
DISCUSSION_CHANNELS = {1514187630374289418}  # General
STUDY_TEXT_CHANNELS = {1514241642415001610}  # Study Discussion

# Game voice channel IDs
GAME_CHANNELS = {
    1514624613743857775,  # Chess
    1514624657935044738,  # Shogi
    1514624725102628945,  # GO
    1514624781692178683,  # Checkers
}

# User accent colors per Discord User ID
USER_COLORS = {
    856485470171299891:  0x5865F2,  # Valence -> Discord Blurple
    1403716456025165864: 0xEB459E,  # Ujjwal  -> Discord Pink
}
DEFAULT_COLOR = 0x2B2D31

class UIColors:
    BRAND_PRIMARY = 0x5865F2      # Blurple - Default commands, info
    SUCCESS = 0x10B981            # Emerald - Completed tasks, duels won, milestones
    DANGER = 0xEF4444             # Crimson - Kicks, strikes, missed daily targets
    WARNING = 0xF59E0B            # Amber Gold - Doubt sessions, warnings
    INFO = 0x06B6D4               # Cyan - Pomodoros, status trackers
    MUTED = 0x4F545C              # Gray - Discussion logs, default fallback


# User IDs as string/int variables
VALENCE_ID = 856485470171299891
UJJWAL_ID = 1403716456025165864

# Pomodoro configuration
POMODORO_CHANNEL_ID = 1514244606827561171  # Group Pomodoro voice channel
POMODORO_STUDY_SECONDS = 60 * 60  # 60 minutes study
POMODORO_BREAK_SECONDS = 10 * 60  # 10 minutes break
POMODORO_CYCLE_SECONDS = POMODORO_STUDY_SECONDS + POMODORO_BREAK_SECONDS  # 70 min total

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
    "The difference between a 99 percentile and 95 percentile is one extra hour every single day.",
    "Your parents didn't sacrifice everything for you to scroll reels at 2 AM.",
    "IIT Bombay CS doesn't care about your mood. It cares about your marks.",
    "The syllabus won't finish itself. Open the book. Start the chapter. NOW.",
    "You're not competing with 20 lakh students. You're competing with yesterday's version of you.",
    "Sleep is earned, not given. Did you earn it today?",
    "Kota toppers aren't smarter. They're just more consistent.",
    "That 'one more episode' costs you 3 marks in JEE. Is it worth it?",
    "The formula sheet you make today is the weapon you carry into the exam hall.",
    "Every unsolved PYQ is a question that WILL appear again. Solve it now or regret it later.",
]

# --- Time and Duration Formatting ---
def format_time(seconds: int) -> str:
    """Formats seconds into a human-readable duration (e.g., '1h 30m')."""
    if seconds <= 0:
        return "0m"
    h, remainder = divmod(seconds, 3600)
    m, _ = divmod(remainder, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0 or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)

def format_time_precise(seconds: int) -> str:
    """Formats seconds into a precise duration (e.g., '1h 30m 15s')."""
    if seconds <= 0:
        return "0s"
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    if s > 0 or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)

def format_mm_ss(seconds: int) -> str:
    """Format seconds as MM:SS."""
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"

def generate_progress_bar(current: int, target: int) -> str:
    """Generates a visual progress bar representing completion percentage."""
    if target <= 0:
        return "`░░░░░░░░░░` 0%"
    pct = min(1.0, current / target)
    blocks = int(pct * 10)
    bar = "▰" * blocks + "▱" * (10 - blocks)
    return f"`{bar}` {int(pct * 100)}%"

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from io import BytesIO

def generate_weekly_chart(username: str, days: list, hours: list) -> BytesIO:
    """
    Generates a premium, modern Matplotlib bar chart for weekly study reports.
    Integrates seamlessly with Discord's dark mode aesthetic.
    """
    fig = Figure(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor('#2B2D31')  # Discord embed gray
    ax = fig.subplots()
    ax.set_facecolor('#1E1F22')         # Discord background dark

    day_labels = [d.strftime("%a\n%d") for d in days]
    
    # Modern premium palette based on performance
    colors = []
    for h in hours:
        if h >= 3.0:
            colors.append('#10B981')  # Emerald Green (Elite)
        elif h >= 1.0:
            colors.append('#5865F2')  # Blurple (Consistent)
        elif h > 0.0:
            colors.append('#F59E0B')  # Amber Gold (Developing)
        else:
            colors.append('#374151')  # Dark Slate (Inactive)

    # 1. Background target shadow bars (Goal reference)
    target_hours = 1.5
    ax.bar(
        day_labels, 
        [target_hours] * len(days), 
        color='#2F3136', 
        width=0.6, 
        edgecolor='none', 
        alpha=0.35, 
        zorder=2
    )

    # 2. Main study hours bars
    bars = ax.bar(
        day_labels, 
        hours, 
        color=colors, 
        width=0.6, 
        edgecolor='white', 
        linewidth=0.8,
        zorder=3
    )

    # Add hour labels on top of bars
    for bar, h in zip(bars, hours):
        if h > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.08,
                f"{h:.1f}h",
                ha='center', va='bottom',
                color='white', fontsize=9, fontweight='bold',
            )

    # Styling Axes and Grid
    ax.set_ylabel('Study Hours', color='#B5BAC1', fontsize=11, fontweight='bold', labelpad=8)
    ax.tick_params(colors='#B5BAC1', labelsize=9)
    
    # Hide top, right, and left spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#4F545C')
    ax.spines['bottom'].set_linewidth(1.2)

    # Subtle horizontal grid lines only
    ax.yaxis.grid(True, color='#2F3136', linestyle='--', alpha=0.5, zorder=1)

    # 3. Goal line annotation
    ax.axhline(y=target_hours, color='#F59E0B', linestyle=':', alpha=0.5, linewidth=1.2, zorder=2)
    ax.text(
        -0.4, target_hours + 0.05, 
        "Daily Goal (1.5h)", 
        color='#F59E0B', 
        fontsize=8, 
        fontweight='bold', 
        alpha=0.8
    )

    ax.set_title(
        f"{username}'s Weekly Study Report",
        color='white', fontsize=13, fontweight='bold', pad=15,
    )

    # Floating summary box
    total_week = sum(hours)
    avg_daily = total_week / 7
    ax.text(
        0.98, 0.95,
        f"Total: {total_week:.1f}h\nAvg: {avg_daily:.1f}h/day",
        transform=ax.transAxes, ha='right', va='top',
        color='#B5BAC1', fontsize=9, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#2B2D31', edgecolor='#4F545C', alpha=0.9, linewidth=1),
    )

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    return buf

