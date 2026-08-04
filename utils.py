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
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "1514186382237503570"))
SERVER_INVITE_LINK = os.getenv("SERVER_INVITE_LINK", "")
POKE_TEXT_CHANNEL_ID = int(os.getenv("POKE_TEXT_CHANNEL_ID", "1514667734355542188"))
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


def generate_ai_stats_chart(stats_data: dict) -> BytesIO:
    """
    Generates a modern Matplotlib double-panel dashboard chart showing:
    - Left: Successes vs Errors per API Key
    - Right: Specific Error Type Breakdown (429, 503, Timeout, 403, Other)
    """
    key_stats = stats_data.get("key_stats", [])
    if not key_stats:
        # Fallback empty chart
        fig = Figure(figsize=(8, 4), dpi=150)
        fig.patch.set_facecolor('#2B2D31')
        buf = BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        return buf

    labels = [f"Key #{k['key_idx']}\n({k['masked_key']})" for k in key_stats]
    successes = [k["success_count"] for k in key_stats]
    errors = [k["error_count"] for k in key_stats]
    
    q429 = [k["quota_429_count"] for k in key_stats]
    o503 = [k["overload_503_count"] for k in key_stats]
    timeouts = [k["timeout_count"] for k in key_stats]
    a403 = [k["auth_403_count"] for k in key_stats]
    other = [k["other_error_count"] for k in key_stats]

    fig = Figure(figsize=(10, 4.5), dpi=150)
    fig.patch.set_facecolor('#2B2D31')  # Discord gray
    
    ax1, ax2 = fig.subplots(1, 2)
    ax1.set_facecolor('#1E1F22')
    ax2.set_facecolor('#1E1F22')

    import numpy as np
    x = np.arange(len(labels))
    width = 0.35

    # Subplot 1: Success vs Error Calls
    b1 = ax1.bar(x - width/2, successes, width, label='Success', color='#10B981', edgecolor='none')
    b2 = ax1.bar(x + width/2, errors, width, label='Errors', color='#EF4444', edgecolor='none')
    
    ax1.set_title('API Calls: Success vs Error', color='white', fontsize=11, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, color='#B5BAC1', fontsize=8)
    ax1.tick_params(axis='y', colors='#B5BAC1', labelsize=8)
    ax1.legend(facecolor='#2B2D31', edgecolor='#4F545C', labelcolor='white', fontsize=8)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.spines['bottom'].set_color('#4F545C')
    ax1.yaxis.grid(True, color='#2F3136', linestyle='--', alpha=0.5)

    # Subplot 2: Error Type Breakdown (Stacked Bar)
    ax2.bar(x, q429, width=0.5, label='429 Quota', color='#F59E0B')
    ax2.bar(x, o503, width=0.5, bottom=q429, label='503 Overload', color='#EC4899')
    bottom_tout = np.array(q429) + np.array(o503)
    ax2.bar(x, timeouts, width=0.5, bottom=bottom_tout, label='Timeout', color='#3B82F6')
    bottom_403 = bottom_tout + np.array(timeouts)
    ax2.bar(x, a403, width=0.5, bottom=bottom_403, label='403 Auth', color='#DC2626')
    bottom_other = bottom_403 + np.array(a403)
    ax2.bar(x, other, width=0.5, bottom=bottom_other, label='Other', color='#6B7280')

    ax2.set_title('Error Breakdown by Type', color='white', fontsize=11, fontweight='bold', pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, color='#B5BAC1', fontsize=8)
    ax2.tick_params(axis='y', colors='#B5BAC1', labelsize=8)
    ax2.legend(facecolor='#2B2D31', edgecolor='#4F545C', labelcolor='white', fontsize=8)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['bottom'].set_color('#4F545C')
    ax2.yaxis.grid(True, color='#2F3136', linestyle='--', alpha=0.5)

    fig.suptitle(
        f"Gemini AI Key Usage & Error Breakdown (Success Rate: {stats_data.get('success_rate', 100)}%)",
        color='white', fontsize=12, fontweight='bold', y=0.98
    )

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    return buf


# ============================================================
# UNICODE MATH CONVERTER — Rich fallback for Discord text
# ============================================================
_UNICODE_MATH_MAP = {
    # Greek letters
    '\\alpha': 'α', '\\beta': 'β', '\\gamma': 'γ', '\\delta': 'δ',
    '\\epsilon': 'ε', '\\varepsilon': 'ε', '\\zeta': 'ζ', '\\eta': 'η',
    '\\theta': 'θ', '\\vartheta': 'ϑ', '\\iota': 'ι', '\\kappa': 'κ',
    '\\lambda': 'λ', '\\mu': 'μ', '\\nu': 'ν', '\\xi': 'ξ',
    '\\pi': 'π', '\\rho': 'ρ', '\\sigma': 'σ', '\\tau': 'τ',
    '\\upsilon': 'υ', '\\phi': 'φ', '\\varphi': 'φ', '\\chi': 'χ',
    '\\psi': 'ψ', '\\omega': 'ω',
    '\\Gamma': 'Γ', '\\Delta': 'Δ', '\\Theta': 'Θ', '\\Lambda': 'Λ',
    '\\Xi': 'Ξ', '\\Pi': 'Π', '\\Sigma': 'Σ', '\\Phi': 'Φ',
    '\\Psi': 'Ψ', '\\Omega': 'Ω',
    # Operators & symbols
    '\\times': '×', '\\div': '÷', '\\cdot': '·', '\\pm': '±', '\\mp': '∓',
    '\\leq': '≤', '\\geq': '≥', '\\neq': '≠', '\\approx': '≈',
    '\\equiv': '≡', '\\sim': '∼', '\\propto': '∝',
    '\\infty': '∞', '\\partial': '∂', '\\nabla': '∇',
    '\\forall': '∀', '\\exists': '∃', '\\in': '∈', '\\notin': '∉',
    '\\subset': '⊂', '\\supset': '⊃', '\\subseteq': '⊆', '\\supseteq': '⊇',
    '\\cup': '∪', '\\cap': '∩', '\\emptyset': '∅',
    '\\int': '∫', '\\iint': '∬', '\\iiint': '∭', '\\oint': '∮',
    '\\sum': '∑', '\\prod': '∏',
    '\\rightarrow': '→', '\\leftarrow': '←', '\\leftrightarrow': '↔',
    '\\Rightarrow': '⇒', '\\Leftarrow': '⇐', '\\Leftrightarrow': '⇔',
    '\\to': '→', '\\mapsto': '↦',
    '\\langle': '⟨', '\\rangle': '⟩',
    '\\dots': '…', '\\cdots': '⋯', '\\ldots': '…', '\\vdots': '⋮',
    '\\perp': '⊥', '\\parallel': '∥', '\\angle': '∠',
    '\\triangle': '△', '\\square': '□', '\\star': '★',
    '\\hbar': 'ℏ', '\\ell': 'ℓ',
}

_UNICODE_SUP = str.maketrans('0123456789+-=()aeiounx', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵉⁱᵒᵘⁿˣ')
_UNICODE_SUB = str.maketrans('0123456789+-=()aeiounx', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑᵢₒᵤₙₓ')


def latex_to_unicode(latex_str: str) -> str:
    """Convert LaTeX math notation to rich Unicode text for Discord.
    
    Produces readable math using Unicode superscripts, subscripts,
    Greek letters, and math operators instead of stripping to plaintext.
    
    Examples:
        \\frac{a}{b}  →  a⁄b
        \\sqrt{x}     →  √x
        x^{2}         →  x²
        \\int_0^\\infty →  ∫₀^∞
        \\alpha        →  α
        \\sum_{i=1}^{n} → ∑ᵢ₌₁ⁿ
    """
    import re as _re
    text = latex_str.strip()
    
    # Strip math delimiters
    text = _re.sub(r'^\s*\\\[|\s*\\\]\s*$', '', text)
    text = _re.sub(r'^\s*\\\(\s*|\s*\\\)\s*$', '', text)
    text = _re.sub(r'^\s*\$\$|\$\$\s*$', '', text)
    text = _re.sub(r'^\s*\$|\$\s*$', '', text)
    
    # Step 1: Convert Greek letters and symbols FIRST (before super/sub processing)
    for latex_cmd, unicode_char in sorted(_UNICODE_MATH_MAP.items(), key=lambda x: -len(x[0])):
        text = text.replace(latex_cmd, unicode_char)
    
    # Step 2: \\vec{x} → x⃗, \\hat{x} → x̂, \\bar{x} → x̄, \\tilde{x} → x̃
    text = _re.sub(r'\\vec\{([^}]*)\}', r'\1⃗', text)
    text = _re.sub(r'\\hat\{([^}]*)\}', r'\1̂', text)
    text = _re.sub(r'\\bar\{([^}]*)\}', r'\1̄', text)
    text = _re.sub(r'\\tilde\{([^}]*)\}', r'\1̃', text)
    
    # Step 3: \\frac{...}{...} → ...⁄... (depth-aware brace matching)
    def _extract_braced(s, pos):
        """Extract content from {braced} group starting at pos, handling nesting."""
        if pos >= len(s) or s[pos] != '{':
            return None, pos
        depth = 1
        start = pos + 1
        curr = start
        while curr < len(s) and depth > 0:
            if s[curr] == '{': depth += 1
            elif s[curr] == '}': depth -= 1
            curr += 1
        return s[start:curr-1], curr
    
    while '\\frac' in text:
        idx = text.find('\\frac')
        after = idx + 5
        # Skip optional whitespace
        while after < len(text) and text[after] == ' ':
            after += 1
        numer, after = _extract_braced(text, after)
        if numer is None:
            break
        while after < len(text) and text[after] == ' ':
            after += 1
        denom, after = _extract_braced(text, after)
        if denom is None:
            break
        text = text[:idx] + f'({numer})⁄({denom})' + text[after:]
    
    # Step 4: \\sqrt{x} → √x   \\sqrt[n]{x} → ⁿ√x
    text = _re.sub(r'\\sqrt\[([^\]]*)\]\{([^}]*)\}', lambda m: m.group(1).translate(_UNICODE_SUP) + '√' + m.group(2), text)
    text = _re.sub(r'\\sqrt\{([^}]*)\}', r'√\1', text)
    
    # Step 5: Superscripts: x^{2n} → x²ⁿ   x^2 → x²
    def _sup_replace(m):
        content = m.group(1)
        return content.translate(_UNICODE_SUP)
    text = _re.sub(r'\^\{([^}]*)\}', _sup_replace, text)
    text = _re.sub(r'\^([0-9a-zA-Z∞αβγδεζηθικλμνξπρστυφχψω])', lambda m: m.group(1).translate(_UNICODE_SUP), text)
    
    # Step 6: Subscripts: x_{i} → xᵢ   x_0 → x₀
    def _sub_replace(m):
        content = m.group(1)
        return content.translate(_UNICODE_SUB)
    text = _re.sub(r'_\{([^}]*)\}', _sub_replace, text)
    text = _re.sub(r'_([0-9a-zA-Z])', lambda m: m.group(1).translate(_UNICODE_SUB), text)
    
    # Step 7: \\left / \\right delimiters → just the delimiter
    text = _re.sub(r'\\left\s*', '', text)
    text = _re.sub(r'\\right\s*', '', text)
    
    # Step 8: \\begin{...} / \\end{...} → remove
    text = _re.sub(r'\\(?:begin|end)\{[^}]*\}', '', text)
    
    # Step 9: Trig/math functions  \\sin → sin, etc.
    text = _re.sub(r'\\(sin|cos|tan|log|ln|exp|lim|max|min|det|gcd|sec|csc|cot)\b', r'\1', text)
    
    # Step 10: Any remaining \\command → just the command name
    text = _re.sub(r'\\([a-zA-Z]+)', r'\1', text)
    
    # Clean up braces and whitespace
    text = text.replace('{', '').replace('}', '')
    text = _re.sub(r'  +', ' ', text).strip()
    
    return text


def render_latex_image(formula_text: str, title: str = "Mathematical Puzzle Formula") -> BytesIO:
    """
    Renders LaTeX formula into a crisp dark-mode PNG image.
    Uses matplotlib's mathtext engine with Computer Modern fonts for authentic LaTeX look.
    Supports multi-line equations (split on \\\\).
    Provides a rich Unicode fallback instead of stripped plaintext.
    """
    import re as _re
    import textwrap as _textwrap
    import matplotlib as _mpl
    
    # Use Computer Modern fonts for authentic LaTeX look
    _mpl.rcParams['mathtext.fontset'] = 'cm'

    # 1. Clean delimiters and normalize unsupported TeX constructs
    raw_cleaned = formula_text.strip()
    
    # Strip display and inline math delimiters: \[\], \(\), $$, $
    raw_cleaned = _re.sub(r'^\s*\\\[|\s*\\\]\s*$', '', raw_cleaned)
    raw_cleaned = _re.sub(r'^\s*\\\(\s*|\s*\\\)\s*$', '', raw_cleaned)
    raw_cleaned = _re.sub(r'^\s*\$\$|\$\$\s*$', '', raw_cleaned)
    raw_cleaned = _re.sub(r'^\s*\$|\$\s*$', '', raw_cleaned)
    
    # Normalize TeX macros for Matplotlib's mathtext parser
    mathtext_str = raw_cleaned

    # Helper to strip \substack with proper nested-brace matching
    while '\\substack' in mathtext_str:
        idx = mathtext_str.find('\\substack')
        start = mathtext_str.find('{', idx)
        if start == -1:
            break
        depth = 1
        curr = start + 1
        while curr < len(mathtext_str) and depth > 0:
            if mathtext_str[curr] == '{':
                depth += 1
            elif mathtext_str[curr] == '}':
                depth -= 1
            curr += 1
        content = mathtext_str[start + 1:curr - 1].replace('\\\\', ' ')
        mathtext_str = mathtext_str[:idx] + content + mathtext_str[curr:]

    mathtext_str = _re.sub(r'\\mathfrak', r'\\mathbf', mathtext_str)
    mathtext_str = _re.sub(r'\\isPartOf', r'\\in', mathtext_str)
    mathtext_str = _re.sub(r'\\mathbb', r'\\mathbf', mathtext_str)
    mathtext_str = _re.sub(r'\\text', r'\\mathrm', mathtext_str)
    mathtext_str = _re.sub(r'\\exp\b', r'\\mathrm{exp}', mathtext_str)
    mathtext_str = _re.sub(r'\\ltimes\b', r'\\times', mathtext_str)
    mathtext_str = _re.sub(r'\\rtimes\b', r'\\times', mathtext_str)
    mathtext_str = _re.sub(r'\\varnothing\b', r'\\emptyset', mathtext_str)
    mathtext_str = _re.sub(r'\\bar\{([^}]*)\}', r'\\overline{\1}', mathtext_str)
    mathtext_str = _re.sub(r'\\!\s*', ' ', mathtext_str)
    mathtext_str = _re.sub(r'\\left\s*\\\{', r'\\{', mathtext_str)
    mathtext_str = _re.sub(r'\\right\s*\\\}', r'\\}', mathtext_str)
    mathtext_str = _re.sub(r'\\left\s*([(\[|])', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\right\s*([)\]|])', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\cdots\b', r'\\dots', mathtext_str)
    # Additional macro normalizations
    mathtext_str = _re.sub(r'\\binom\{([^}]*)\}\{([^}]*)\}', r'\\frac{\1}{\2}', mathtext_str)
    mathtext_str = _re.sub(r'\\boxed\{([^}]*)\}', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\cancel\{([^}]*)\}', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\underbrace\{([^}]*)\}', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\overbrace\{([^}]*)\}', r'\1', mathtext_str)
    mathtext_str = _re.sub(r'\\xleftarrow\{([^}]*)\}', r'\\leftarrow', mathtext_str)
    mathtext_str = _re.sub(r'\\xrightarrow\{([^}]*)\}', r'\\rightarrow', mathtext_str)
    mathtext_str = _re.sub(r'\n+', ' ', mathtext_str)
    mathtext_str = _re.sub(r'  +', ' ', mathtext_str)

    # 2. Detect multi-line equations (split on \\\\ or \\newline)
    lines = _re.split(r'\s*\\\\\s*|\s*\\newline\s*', mathtext_str)
    lines = [l.strip() for l in lines if l.strip()]
    is_multiline = len(lines) > 1
    
    # Wrap each line with $ delimiters
    formatted_lines = []
    for line in lines:
        if not line.startswith('$'):
            formatted_lines.append(f'${line}$')
        else:
            formatted_lines.append(line)

    # Calculate figure dimensions
    max_char_len = max(len(l) for l in formatted_lines)
    fig_width = max(7.0, min(14.0, max_char_len * 0.08))
    fig_height = max(2.2, min(10.0, len(formatted_lines) * 1.2 + 1.0))

    # Attempt primary Mathtext render pass
    try:
        fig = Figure(figsize=(fig_width, fig_height), dpi=180)
        fig.patch.set_facecolor('#2B2D31')
        ax = fig.subplots()
        ax.set_facecolor('#1E1F22')
        ax.axis('off')

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#4F545C')
            spine.set_linewidth(0.5)

        if title:
            ax.set_title(title, color='#B5BAC1', fontsize=10, pad=8, fontweight='bold')

        if is_multiline:
            # Multi-line: render each line at evenly spaced y positions
            n = len(formatted_lines)
            for i, line in enumerate(formatted_lines):
                y_pos = 1.0 - (i + 0.5) / n  # Evenly distribute from top to bottom
                fontsize_calc = max(10, min(16, int(200 / max(10, min(80, len(line))))))
                ax.text(
                    0.5, y_pos, line,
                    color='white', fontsize=fontsize_calc,
                    ha='center', va='center', transform=ax.transAxes
                )
        else:
            # Single line
            fontsize_calc = max(11, min(18, int(220 / max(10, min(80, max_char_len)))))
            ax.text(
                0.5, 0.5, formatted_lines[0],
                color='white', fontsize=fontsize_calc,
                ha='center', va='center', fontweight='bold',
                transform=ax.transAxes
            )
        fig.tight_layout(pad=0.2)
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight', pad_inches=0.2)
        buf.seek(0)
        return buf
    except Exception as parse_err:
        logging.warning(f"[LATEX RENDER] Primary render error: {parse_err}. Switching to Unicode fallback.")

        # Rich Unicode fallback (V2) — converts LaTeX to beautiful Unicode instead of stripping
        fallback_text = latex_to_unicode(raw_cleaned)
        wrapped_fallback = _textwrap.fill(fallback_text, width=65)

        fig = Figure(figsize=(8.0, 3.0), dpi=180)
        fig.patch.set_facecolor('#2B2D31')
        ax = fig.subplots()
        ax.set_facecolor('#1E1F22')
        ax.axis('off')

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#4F545C')
            spine.set_linewidth(0.5)

        if title:
            ax.set_title(title, color='#B5BAC1', fontsize=10, pad=8, fontweight='bold')

        ax.text(
            0.5, 0.5,
            wrapped_fallback,
            color='#5865F2',
            fontsize=12,
            ha='center',
            va='center',
            fontfamily='DejaVu Sans',
            transform=ax.transAxes,
            wrap=True
        )
        fig.tight_layout(pad=0.2)
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight', pad_inches=0.2)
        buf.seek(0)
        return buf


# ============================================================
# ORGANIC CHEMISTRY RENDERER
# ============================================================

# Common molecule database: name -> (SMILES-like structure def, display_name, functional_groups)
_MOLECULE_DB = {
    # Hydrocarbons
    'methane': {'formula': 'CH₄', 'type': 'alkane', 'carbons': 1, 'name': 'Methane'},
    'ethane': {'formula': 'C₂H₆', 'type': 'alkane', 'carbons': 2, 'name': 'Ethane'},
    'propane': {'formula': 'C₃H₈', 'type': 'alkane', 'carbons': 3, 'name': 'Propane'},
    'butane': {'formula': 'C₄H₁₀', 'type': 'alkane', 'carbons': 4, 'name': 'Butane'},
    'pentane': {'formula': 'C₅H₁₂', 'type': 'alkane', 'carbons': 5, 'name': 'Pentane'},
    'hexane': {'formula': 'C₆H₁₄', 'type': 'alkane', 'carbons': 6, 'name': 'Hexane'},
    'ethylene': {'formula': 'C₂H₄', 'type': 'alkene', 'carbons': 2, 'name': 'Ethylene (Ethene)'},
    'propylene': {'formula': 'C₃H₆', 'type': 'alkene', 'carbons': 3, 'name': 'Propylene (Propene)'},
    'ethene': {'formula': 'C₂H₄', 'type': 'alkene', 'carbons': 2, 'name': 'Ethene'},
    'propene': {'formula': 'C₃H₆', 'type': 'alkene', 'carbons': 3, 'name': 'Propene'},
    'acetylene': {'formula': 'C₂H₂', 'type': 'alkyne', 'carbons': 2, 'name': 'Acetylene (Ethyne)'},
    'ethyne': {'formula': 'C₂H₂', 'type': 'alkyne', 'carbons': 2, 'name': 'Ethyne'},
    # Aromatics
    'benzene': {'formula': 'C₆H₆', 'type': 'aromatic', 'carbons': 6, 'name': 'Benzene'},
    'toluene': {'formula': 'C₇H₈', 'type': 'aromatic', 'carbons': 7, 'name': 'Toluene', 'substituents': ['CH₃']},
    'phenol': {'formula': 'C₆H₅OH', 'type': 'aromatic', 'carbons': 6, 'name': 'Phenol', 'substituents': ['OH']},
    'aniline': {'formula': 'C₆H₅NH₂', 'type': 'aromatic', 'carbons': 6, 'name': 'Aniline', 'substituents': ['NH₂']},
    'nitrobenzene': {'formula': 'C₆H₅NO₂', 'type': 'aromatic', 'carbons': 6, 'name': 'Nitrobenzene', 'substituents': ['NO₂']},
    'styrene': {'formula': 'C₈H₈', 'type': 'aromatic', 'carbons': 8, 'name': 'Styrene', 'substituents': ['CH=CH₂']},
    'naphthalene': {'formula': 'C₁₀H₈', 'type': 'fused_aromatic', 'carbons': 10, 'name': 'Naphthalene'},
    # Alcohols & Ethers
    'methanol': {'formula': 'CH₃OH', 'type': 'alcohol', 'carbons': 1, 'name': 'Methanol'},
    'ethanol': {'formula': 'C₂H₅OH', 'type': 'alcohol', 'carbons': 2, 'name': 'Ethanol'},
    'propanol': {'formula': 'C₃H₇OH', 'type': 'alcohol', 'carbons': 3, 'name': 'Propanol'},
    'glycerol': {'formula': 'C₃H₅(OH)₃', 'type': 'polyol', 'carbons': 3, 'name': 'Glycerol'},
    # Aldehydes & Ketones
    'formaldehyde': {'formula': 'HCHO', 'type': 'aldehyde', 'carbons': 1, 'name': 'Formaldehyde'},
    'acetaldehyde': {'formula': 'CH₃CHO', 'type': 'aldehyde', 'carbons': 2, 'name': 'Acetaldehyde'},
    'acetone': {'formula': '(CH₃)₂CO', 'type': 'ketone', 'carbons': 3, 'name': 'Acetone'},
    # Carboxylic Acids
    'formic acid': {'formula': 'HCOOH', 'type': 'carboxylic', 'carbons': 1, 'name': 'Formic Acid'},
    'acetic acid': {'formula': 'CH₃COOH', 'type': 'carboxylic', 'carbons': 2, 'name': 'Acetic Acid'},
    'oxalic acid': {'formula': '(COOH)₂', 'type': 'dicarboxylic', 'carbons': 2, 'name': 'Oxalic Acid'},
    'benzoic acid': {'formula': 'C₆H₅COOH', 'type': 'aromatic_acid', 'carbons': 7, 'name': 'Benzoic Acid'},
    # Esters & Amides
    'ethyl acetate': {'formula': 'CH₃COOC₂H₅', 'type': 'ester', 'carbons': 4, 'name': 'Ethyl Acetate'},
    'aspirin': {'formula': 'C₉H₈O₄', 'type': 'aromatic_ester', 'carbons': 9, 'name': 'Aspirin (Acetylsalicylic Acid)'},
    # Amines
    'methylamine': {'formula': 'CH₃NH₂', 'type': 'amine', 'carbons': 1, 'name': 'Methylamine'},
    'ethylamine': {'formula': 'C₂H₅NH₂', 'type': 'amine', 'carbons': 2, 'name': 'Ethylamine'},
    # Sugars
    'glucose': {'formula': 'C₆H₁₂O₆', 'type': 'sugar', 'carbons': 6, 'name': 'Glucose'},
    'fructose': {'formula': 'C₆H₁₂O₆', 'type': 'sugar', 'carbons': 6, 'name': 'Fructose'},
    'sucrose': {'formula': 'C₁₂H₂₂O₁₁', 'type': 'disaccharide', 'carbons': 12, 'name': 'Sucrose'},
    # Amino Acids
    'glycine': {'formula': 'NH₂CH₂COOH', 'type': 'amino_acid', 'carbons': 2, 'name': 'Glycine'},
    'alanine': {'formula': 'CH₃CH(NH₂)COOH', 'type': 'amino_acid', 'carbons': 3, 'name': 'Alanine'},
}

import math as _math

def _draw_benzene_ring(ax, cx, cy, size=0.8, color='white', linewidth=2.0):
    """Draw a benzene ring (hexagon with inscribed circle) at position (cx, cy)."""
    angles = [_math.pi / 6 + i * _math.pi / 3 for i in range(6)]
    xs = [cx + size * _math.cos(a) for a in angles]
    ys = [cy + size * _math.sin(a) for a in angles]
    # Outer hexagon
    xs_closed = xs + [xs[0]]
    ys_closed = ys + [ys[0]]
    ax.plot(xs_closed, ys_closed, color=color, linewidth=linewidth, solid_capstyle='round')
    # Inner circle (aromatic)
    inner = _math.cos(_math.pi / 6) * size * 0.6
    circle = __import__('matplotlib').patches.Circle((cx, cy), inner, fill=False,
                                                      edgecolor=color, linewidth=linewidth * 0.6,
                                                      linestyle='--', alpha=0.7)
    ax.add_patch(circle)
    return list(zip(xs, ys))


def _draw_chain(ax, start_x, start_y, num_carbons, bond_type='single',
                color='white', linewidth=2.0, angle_deg=30):
    """Draw a zigzag carbon chain starting at (start_x, start_y)."""
    bond_len = 0.9
    points = [(start_x, start_y)]
    for i in range(num_carbons - 1):
        angle = _math.radians(angle_deg if i % 2 == 0 else -angle_deg)
        dx = bond_len * _math.cos(angle)
        dy = bond_len * _math.sin(angle)
        new_x = points[-1][0] + dx
        new_y = points[-1][1] + dy
        points.append((new_x, new_y))

    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if bond_type == 'double' and i == 0:
            offset = 0.06
            ax.plot([x1, x2], [y1 + offset, y2 + offset], color=color, linewidth=linewidth, solid_capstyle='round')
            ax.plot([x1, x2], [y1 - offset, y2 - offset], color=color, linewidth=linewidth, solid_capstyle='round')
        elif bond_type == 'triple' and i == 0:
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=linewidth, solid_capstyle='round')
            ax.plot([x1, x2], [y1 + 0.08, y2 + 0.08], color=color, linewidth=linewidth * 0.7, solid_capstyle='round')
            ax.plot([x1, x2], [y1 - 0.08, y2 - 0.08], color=color, linewidth=linewidth * 0.7, solid_capstyle='round')
        else:
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=linewidth, solid_capstyle='round')

    return points


def _draw_functional_group(ax, x, y, group, color='#5865F2', fontsize=11):
    """Draw a functional group label at position (x, y)."""
    ax.text(x, y, group, color=color, fontsize=fontsize, fontweight='bold',
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.15', facecolor='#1E1F22', edgecolor=color, alpha=0.9))


def _draw_reaction_arrow(ax, x1, y1, x2, y2, color='#5865F2', linewidth=2.0,
                          label='', reversible=False):
    """Draw a reaction arrow from (x1,y1) to (x2,y2)."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->' if not reversible else '<->',
                                color=color, lw=linewidth,
                                connectionstyle='arc3,rad=0'))
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2 + 0.15
        ax.text(mid_x, mid_y, label, color=color, fontsize=9,
                ha='center', va='bottom', fontstyle='italic')


async def fetch_pubchem_structure(molecule_name: str) -> 'BytesIO | None':
    """Fetch 2D structure PNG from PubChem REST API and invert to dark-mode.
    
    Returns a BytesIO buffer with a dark-mode PNG, or None on failure.
    Works for ANY molecule that PubChem knows about (millions of compounds).
    """
    import aiohttp
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule_name}/PNG?image_size=500x500"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    from PIL import Image, ImageOps
                    img = Image.open(BytesIO(data)).convert('RGB')
                    # Invert white-bg to dark-mode
                    img = ImageOps.invert(img)
                    buf = BytesIO()
                    img.save(buf, format='PNG')
                    buf.seek(0)
                    logging.info(f"[PUBCHEM] Fetched structure for: {molecule_name}")
                    return buf
    except Exception as e:
        logging.warning(f"[PUBCHEM] Failed to fetch {molecule_name}: {e}")
    return None


def render_chemistry_image(input_text: str, title: str = "Organic Chemistry") -> BytesIO:
    """
    Renders organic chemistry structures, reactions, and formulas as
    crisp dark-mode PNG images for Discord.

    Supports:
    - Molecule names: "benzene", "ethanol", "aspirin", etc. (35+ built-in, infinite via PubChem)
    - Chemical equations: "CH3OH + O2 -> CO2 + H2O"
    - Reaction notation with arrows: "A → B", "A ⇌ B"
    - Raw structural formulas: "CH3-CH2-OH"
    - Functional group display

    Uses pure matplotlib for built-in molecules, PubChem API as async fallback.
    """
    import re as _re
    import textwrap as _textwrap

    input_clean = input_text.strip().lower()

    # Check if it's a known molecule name
    mol_info = _MOLECULE_DB.get(input_clean)

    # Fuzzy match: only if input IS the molecule name plus extra words
    # e.g. "benzene ring" matches "benzene", but "propanoate" does NOT match "propane"
    if not mol_info:
        import re as _re_mol
        for key in _MOLECULE_DB:
            # Require word boundary match — key must appear as a whole word
            if _re_mol.search(r'\b' + _re_mol.escape(key) + r'\b', input_clean):
                mol_info = _MOLECULE_DB[key]
                break

    # Detect if it's a reaction (has arrow characters)
    is_reaction = any(arrow in input_text for arrow in ['→', '⇌', '->', '<=>', '=>', '—>'])

    try:
        fig = Figure(figsize=(9, 5), dpi=180)
        fig.patch.set_facecolor('#2B2D31')
        ax = fig.subplots()
        ax.set_facecolor('#1E1F22')
        ax.set_aspect('equal')
        ax.axis('off')

        # Border
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#4F545C')
            spine.set_linewidth(0.5)

        if title:
            ax.text(0.5, 0.98, title, color='#5865F2', fontsize=10,
                    fontweight='bold', ha='center', va='top', transform=ax.transAxes)

        if mol_info:
            # --- MOLECULE RENDERING MODE ---
            mol_type = mol_info.get('type', 'alkane')
            mol_name = mol_info.get('name', input_text)
            mol_formula = mol_info.get('formula', '')
            substituents = mol_info.get('substituents', [])
            num_c = mol_info.get('carbons', 2)

            if mol_type in ('aromatic', 'aromatic_acid', 'aromatic_ester'):
                # Draw benzene ring
                vertices = _draw_benzene_ring(ax, 0, 0, size=1.0, color='white', linewidth=2.0)
                # Draw substituents
                if substituents:
                    # Top vertex
                    vx, vy = vertices[1]
                    ax.plot([vx, vx], [vy, vy + 0.6], color='white', linewidth=2.0)
                    _draw_functional_group(ax, vx, vy + 0.85, substituents[0],
                                            color='#00D166', fontsize=12)
                if mol_type == 'aromatic_acid':
                    vx, vy = vertices[1]
                    ax.plot([vx, vx], [vy, vy + 0.6], color='white', linewidth=2.0)
                    _draw_functional_group(ax, vx, vy + 0.85, 'COOH',
                                            color='#ED4245', fontsize=12)

                ax.set_xlim(-2.5, 2.5)
                ax.set_ylim(-2.5, 2.8)

            elif mol_type == 'fused_aromatic':
                # Naphthalene — two fused benzene rings
                v1 = _draw_benzene_ring(ax, -0.87, 0, size=1.0, color='white', linewidth=2.0)
                v2 = _draw_benzene_ring(ax, 0.87, 0, size=1.0, color='white', linewidth=2.0)
                ax.set_xlim(-3, 3)
                ax.set_ylim(-2.5, 2.5)

            elif mol_type in ('alkane', 'alcohol', 'aldehyde', 'ketone', 'carboxylic',
                              'ester', 'amine', 'ether'):
                # Draw zigzag chain
                start_x = -num_c * 0.45
                points = _draw_chain(ax, start_x, 0, num_c, bond_type='single',
                                      color='white', linewidth=2.0)
                # Draw carbon labels at each vertex
                for i, (px, py) in enumerate(points):
                    ax.text(px, py - 0.2, f'C{i+1}' if num_c <= 6 else '',
                            color='#72767D', fontsize=7, ha='center', va='top')

                # Functional group at end
                last_x, last_y = points[-1]
                if mol_type == 'alcohol':
                    ax.plot([last_x, last_x + 0.5], [last_y, last_y], color='white', linewidth=2.0)
                    _draw_functional_group(ax, last_x + 0.9, last_y, 'OH',
                                            color='#ED4245', fontsize=13)
                elif mol_type == 'aldehyde':
                    ax.plot([last_x, last_x + 0.5], [last_y, last_y], color='white', linewidth=2.0)
                    _draw_functional_group(ax, last_x + 0.9, last_y, 'CHO',
                                            color='#FEE75C', fontsize=13)
                elif mol_type == 'ketone':
                    mid = len(points) // 2
                    mx, my = points[mid]
                    ax.plot([mx, mx], [my, my + 0.5], color='white', linewidth=2.0)
                    _draw_functional_group(ax, mx, my + 0.8, 'C=O',
                                            color='#FEE75C', fontsize=13)
                elif mol_type == 'carboxylic':
                    ax.plot([last_x, last_x + 0.5], [last_y, last_y], color='white', linewidth=2.0)
                    _draw_functional_group(ax, last_x + 1.0, last_y, 'COOH',
                                            color='#ED4245', fontsize=13)
                elif mol_type == 'amine':
                    ax.plot([last_x, last_x + 0.5], [last_y, last_y], color='white', linewidth=2.0)
                    _draw_functional_group(ax, last_x + 0.9, last_y, 'NH₂',
                                            color='#5865F2', fontsize=13)
                elif mol_type == 'ester':
                    ax.plot([last_x, last_x + 0.5], [last_y, last_y], color='white', linewidth=2.0)
                    _draw_functional_group(ax, last_x + 1.1, last_y, 'COO—R',
                                            color='#EB459E', fontsize=12)

                # Add H atoms to terminal carbons
                first_x, first_y = points[0]
                ax.text(first_x - 0.3, first_y + 0.25, 'H', color='#72767D',
                        fontsize=8, ha='center', va='center')

                pad = max(2.5, num_c * 0.6)
                ax.set_xlim(start_x - 1.5, last_x + 2.5)
                ax.set_ylim(-pad, pad)

            elif mol_type in ('alkene',):
                start_x = -num_c * 0.45
                points = _draw_chain(ax, start_x, 0, num_c, bond_type='double',
                                      color='white', linewidth=2.0)
                last_x, last_y = points[-1]
                ax.set_xlim(start_x - 1, last_x + 1)
                ax.set_ylim(-2.5, 2.5)

            elif mol_type in ('alkyne',):
                start_x = -num_c * 0.45
                points = _draw_chain(ax, start_x, 0, num_c, bond_type='triple',
                                      color='white', linewidth=2.0)
                last_x, last_y = points[-1]
                ax.set_xlim(start_x - 1, last_x + 1)
                ax.set_ylim(-2.5, 2.5)

            elif mol_type in ('amino_acid',):
                # Draw amino acid backbone: H2N—CH(R)—COOH
                ax.plot([-1.5, -0.5], [0, 0], color='white', linewidth=2.0)
                _draw_functional_group(ax, -2.0, 0, 'H₂N', color='#5865F2', fontsize=13)
                ax.plot([-0.5, 0.5], [0, 0], color='white', linewidth=2.0)
                ax.text(0, 0.15, 'Cα', color='#B5BAC1', fontsize=10,
                        fontweight='bold', ha='center', va='bottom')
                # R group
                ax.plot([0, 0], [0, -0.6], color='white', linewidth=2.0)
                r_label = 'H' if 'glycine' in input_clean else 'CH₃' if 'alanine' in input_clean else 'R'
                _draw_functional_group(ax, 0, -0.9, r_label, color='#00D166', fontsize=12)
                # COOH
                ax.plot([0.5, 1.5], [0, 0], color='white', linewidth=2.0)
                _draw_functional_group(ax, 2.0, 0, 'COOH', color='#ED4245', fontsize=13)
                ax.set_xlim(-3, 3.5)
                ax.set_ylim(-2.5, 2.5)

            elif mol_type in ('sugar', 'disaccharide', 'polyol'):
                # Draw Haworth-style ring (simplified pyranose)
                ring_angles = [_math.pi / 5 + i * 2 * _math.pi / 5 for i in range(5)]
                rxs = [1.2 * _math.cos(a) for a in ring_angles]
                rys = [1.2 * _math.sin(a) for a in ring_angles]
                # Close the ring with oxygen bridge
                rxs_closed = rxs + [rxs[0]]
                rys_closed = rys + [rys[0]]
                ax.plot(rxs_closed, rys_closed, color='white', linewidth=2.0)
                # Mark oxygen
                ax.text(rxs[0] + 0.15, rys[0] + 0.15, 'O', color='#ED4245',
                        fontsize=12, fontweight='bold', ha='center', va='center')
                # OH groups
                for i in range(1, 5):
                    direction = 1 if i % 2 == 0 else -1
                    ax.plot([rxs[i], rxs[i]], [rys[i], rys[i] + direction * 0.5],
                            color='white', linewidth=1.5)
                    _draw_functional_group(ax, rxs[i], rys[i] + direction * 0.75, 'OH',
                                            color='#ED4245', fontsize=8)
                ax.set_xlim(-3, 3)
                ax.set_ylim(-3, 3)
            else:
                # Generic: just show formula
                ax.text(0.5, 0.5, mol_formula, color='white', fontsize=24,
                        fontweight='bold', ha='center', va='center', transform=ax.transAxes)
                ax.set_xlim(-1, 1)
                ax.set_ylim(-1, 1)

            # Name and formula labels
            ax.text(0.5, 0.06, f'{mol_name}', color='#B5BAC1', fontsize=11,
                    fontweight='bold', ha='center', va='bottom', transform=ax.transAxes)
            ax.text(0.5, 0.01, f'{mol_formula}', color='#72767D', fontsize=9,
                    ha='center', va='bottom', transform=ax.transAxes)

        elif is_reaction:
            # --- REACTION RENDERING MODE ---
            # Parse reaction: "A + B → C + D"
            import re as _re2
            parts = _re2.split(r'\s*(?:→|⇌|->|<=>|=>|—>)\s*', input_text, maxsplit=1)
            is_reversible = any(x in input_text for x in ['⇌', '<=>'])

            if len(parts) == 2:
                reactants = parts[0].strip()
                products = parts[1].strip()
            else:
                reactants = input_text
                products = ''

            # Draw reactants on left
            ax.text(0.15, 0.5, reactants, color='white', fontsize=14,
                    fontweight='bold', ha='center', va='center', transform=ax.transAxes,
                    fontfamily='DejaVu Sans')

            # Draw arrow
            arrow_style = '↔' if is_reversible else '→'
            ax.text(0.5, 0.5, arrow_style, color='#5865F2', fontsize=28,
                    fontweight='bold', ha='center', va='center', transform=ax.transAxes)

            # Draw products on right
            if products:
                ax.text(0.85, 0.5, products, color='white', fontsize=14,
                        fontweight='bold', ha='center', va='center', transform=ax.transAxes,
                        fontfamily='DejaVu Sans')

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

        else:
            # --- FORMULA / TEXT RENDERING MODE ---
            # Render the chemical formula or structural formula as styled text
            display_text = input_text.strip()

            # Try to prettify structural formulas (CH3-CH2-OH style)
            display_text = display_text.replace('-', '—')

            ax.text(0.5, 0.5, display_text, color='white', fontsize=16,
                    fontweight='bold', ha='center', va='center', transform=ax.transAxes,
                    fontfamily='DejaVu Sans',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='#1E1F22',
                              edgecolor='#5865F2', linewidth=1.5, alpha=0.95))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

        fig.tight_layout(pad=0.3)
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight', pad_inches=0.2)
        buf.seek(0)
        logging.info(f"[CHEM RENDER] Successfully rendered: {input_text[:60]}")
        return buf

    except Exception as e:
        logging.warning(f"[CHEM RENDER] Primary render failed: {e}. Using text fallback.")
        # Fail-safe text fallback
        import textwrap as _tw
        fig = Figure(figsize=(8, 3), dpi=180)
        fig.patch.set_facecolor('#2B2D31')
        ax = fig.subplots()
        ax.set_facecolor('#1E1F22')
        ax.axis('off')

        wrapped = _tw.fill(input_text, width=55)
        ax.text(0.5, 0.5, wrapped, color='#5865F2', fontsize=12,
                ha='center', va='center', fontfamily='DejaVu Sans',
                transform=ax.transAxes)

        if title:
            ax.set_title(title, color='#B5BAC1', fontsize=10, pad=8, fontweight='bold')

        fig.tight_layout(pad=0.2)
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight', pad_inches=0.2)
        buf.seek(0)
        return buf


def generate_db_stats_chart(db_stats_data: dict, timeframe: str = "day") -> BytesIO:
    """
    Generates a dual-panel dashboard chart for Firestore Reads & Writes:
    - Left: Reads vs Writes over time (hourly/daily) with dashed free quota limit lines
    - Right: Bot-wise breakdown (YPT Study Bot vs Valence Task Bot) with distinct colors
    """
    fig = Figure(figsize=(10, 4.5), dpi=150)
    fig.patch.set_facecolor('#2B2D31')

    ax1, ax2 = fig.subplots(1, 2)
    ax1.set_facecolor('#1E1F22')
    ax2.set_facecolor('#1E1F22')

    labels = db_stats_data.get("labels", ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"])
    reads = db_stats_data.get("reads", [0] * len(labels))
    writes = db_stats_data.get("writes", [0] * len(labels))
    
    study_bot_ops = db_stats_data.get("study_bot_ops", [0] * len(labels))
    task_bot_ops = db_stats_data.get("task_bot_ops", [0] * len(labels))

    x = list(range(len(labels)))

    # Subplot 1: Reads vs Writes Line Chart with Limit Lines
    ax1.plot(x, reads, color='#10B981', marker='o', linewidth=2, label='Reads (load_data)')
    ax1.plot(x, writes, color='#F59E0B', marker='s', linewidth=2, label='Writes (save_data)')

    # Quota reference lines (Free Tier Limits)
    if timeframe == "day":
        read_limit = 2083    # 50,000 / 24h
        write_limit = 833    # 20,000 / 24h
        limit_text_r = "Hourly Read Quota (2,083)"
        limit_text_w = "Hourly Write Quota (833)"
    else:
        read_limit = 50000   # Daily Limit
        write_limit = 20000  # Daily Limit
        limit_text_r = "Daily Read Limit (50k)"
        limit_text_w = "Daily Write Limit (20k)"

    ax1.axhline(y=read_limit, color='#EF4444', linestyle='--', alpha=0.7, linewidth=1.2, label=limit_text_r)
    ax1.axhline(y=write_limit, color='#EC4899', linestyle=':', alpha=0.7, linewidth=1.2, label=limit_text_w)

    ax1.set_title('Firestore Operations (Reads vs Writes)', color='white', fontsize=11, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, color='#B5BAC1', fontsize=8, rotation=30 if len(labels) > 8 else 0)
    ax1.tick_params(axis='y', colors='#B5BAC1', labelsize=8)
    ax1.legend(facecolor='#2B2D31', edgecolor='#4F545C', labelcolor='white', fontsize=7, loc='upper left')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_visible(False)
    ax1.spines['bottom'].set_color('#4F545C')
    ax1.yaxis.grid(True, color='#2F3136', linestyle='--', alpha=0.5)

    # Subplot 2: Bot Comparison (YPT Study Bot vs Valence Task Bot)
    import numpy as np
    width = 0.35
    x_arr = np.arange(len(labels))

    ax2.bar(x_arr - width/2, study_bot_ops, width, label='YPT Study Bot', color='#5865F2')
    ax2.bar(x_arr + width/2, task_bot_ops, width, label='Valence Task Bot', color='#EB459E')

    ax2.set_title('Bot Operations Comparison', color='white', fontsize=11, fontweight='bold', pad=10)
    ax2.set_xticks(x_arr)
    ax2.set_xticklabels(labels, color='#B5BAC1', fontsize=8, rotation=30 if len(labels) > 8 else 0)
    ax2.tick_params(axis='y', colors='#B5BAC1', labelsize=8)
    ax2.legend(facecolor='#2B2D31', edgecolor='#4F545C', labelcolor='white', fontsize=8)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['bottom'].set_color('#4F545C')
    ax2.yaxis.grid(True, color='#2F3136', linestyle='--', alpha=0.5)

    fig.suptitle(
        f"Firestore Database Diagnostics ({timeframe.upper()} View)",
        color='white', fontsize=12, fontweight='bold', y=0.98
    )

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    return buf



