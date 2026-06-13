# --- COOL FEATURES EXTENSION ---
# Features (all as a cog, not touching bot.py):
#   1. Weekly Duel: Every Sunday 9 PM IST, compare Valence vs Ujjwal, announce winner
#   2. Touch Grass Alert: If someone studies 8+ hours in a day, bot pings them to take a break
#   3. Break Reminder: After 2h continuous study, gentle "take a break" DM
#   4. /motivate command: Random motivational quote with beautiful embed
#   5. /serverstats command: Total server study time, sessions, most active day
#   6. /history command: Show last 10 sessions with timestamps
#   7. /countdown command: Set and check exam countdown
#
# Delete this file to remove all bonus features without affecting bot.py.

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
import logging
import json
import os
import random
import time
import firebase_admin
from firebase_admin import credentials, firestore

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
_DATA_DIR = os.path.join(os.getenv("LOCALAPPDATA", _PROJECT_DIR), "YPTStudyBot") if os.name == "nt" else _PROJECT_DIR
DATA_FILE = os.path.join(_DATA_DIR, "study_data.json")

# ---- Channel & User IDs ----
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"
CELEBRATION_CHANNEL_ID = 1514208252760424591
LEADERBOARD_CHANNEL_ID = 1514208164071870514
STUDY_TEXT_CHANNEL_ID = 1514241642415001610

# Study voice channels (for break reminder check)
STUDY_VOICE_CHANNELS = {1514208313452007514, 1514596473629708298, 1514244606827561171}

# User accent colors
USER_COLORS = {
    856485470171299891:  0x5865F2,
    1403716456025165864: 0xEB459E,
}
DEFAULT_COLOR = 0x2B2D31


def load_data_sync():
    if firebase_admin._apps:
        try:
            db = firestore.client()
            doc_ref = db.collection('bot_data').document('main')
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logging.error(f"[BONUS] Firestore load error: {e}")

    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}


def save_data_sync(data):
    if firebase_admin._apps:
        try:
            db = firestore.client()
            db.collection('bot_data').document('main').set(data)
        except Exception as e:
            logging.error(f"[BONUS] Firestore save error: {e}")

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"[BONUS] Failed to save data: {e}")


# ============================================================
# MOTIVATIONAL QUOTES (curated, not generic)
# ============================================================
MOTIVATIONAL_QUOTES = [
    ("The grind never lies. 📚", "— YPT Philosophy"),
    ("Every hour compounds. Keep going.", "— Compound Effect"),
    ("Discipline > Motivation. Always.", "— Jocko Willink"),
    ("Your future self is watching. Don't disappoint.", "— Unknown"),
    ("JEE doesn't care about excuses. Neither should you.", "— Reality"),
    ("One more hour. That's the gap between you and them.", "— Compete"),
    ("Consistency beats intensity every single time.", "— James Clear"),
    ("The pain of discipline is lighter than the pain of regret.", "— Jim Rohn"),
    ("Study like your rank depends on it. Because it does.", "— Facts"),
    ("While you're sleeping, someone else is studying.", "— Truth"),
    ("Don't wish it were easier. Wish you were better.", "— Jim Rohn"),
    ("The only way to do great work is to love what you do.", "— Steve Jobs"),
    ("Success is the sum of small efforts repeated daily.", "— Robert Collier"),
    ("Hard work beats talent when talent doesn't work hard.", "— Tim Notke"),
    ("You don't have to be great to start, but you have to start to be great.", "— Zig Ziglar"),
    ("The expert in anything was once a beginner.", "— Helen Hayes"),
    ("It's not about having time. It's about making time.", "— Grind"),
    ("Your comfort zone is a beautiful place, but nothing grows there.", "— Growth"),
    ("Fall seven times, stand up eight.", "— Japanese Proverb"),
    ("You are one study session away from a breakthrough.", "— Keep Going"),
]

# ============================================================
# TOUCH GRASS MESSAGES (sent when 8+ hours in a day)
# ============================================================
TOUCH_GRASS_MESSAGES = [
    "🌿 **Bro you've been studying for {hours:.1f} hours today.** Go outside for 5 minutes. Touch some grass. See the sun. Then come back and keep grinding.",
    "🌳 **{hours:.1f} HOURS?!** Your brain needs oxygen. Step outside, stretch, drink water. Then come back stronger.",
    "☀️ **{hours:.1f}h today!** Legend status. But legends also take breaks. Go walk for 10 min. Your brain will thank you.",
    "🏃 **{hours:.1f} hours in.** At this rate you're going to merge with your chair. Take a real break — go outside!",
    "💪 **{hours:.1f}h beast mode!** You earned a 10-min break. Walk around, look at the sky. You've earned it.",
]


class BonusFeaturesCog(commands.Cog):
    """Bonus features: duels, break reminders, motivate, serverstats, history, countdown."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._touch_grass_sent_today = {}  # uid -> date to prevent spam
        self.weekly_duel_check.start()
        self.break_reminder_check.start()
        self.touch_grass_check.start()

    def cog_unload(self):
        self.weekly_duel_check.cancel()
        self.break_reminder_check.cancel()
        self.touch_grass_check.cancel()

    # ==================================================================
    # COMMAND: /motivate
    # ==================================================================
    @app_commands.command(name="motivate", description="Get a random motivational study quote.")
    async def motivate_command(self, interaction: discord.Interaction):
        """Sends a beautiful motivational quote embed."""
        quote, author = random.choice(MOTIVATIONAL_QUOTES)

        embed = discord.Embed(
            title="💭 Study Motivation",
            description=f"*\"{quote}\"*",
            color=random.choice([0x5865F2, 0x57F287, 0xFEE75C, 0xEB459E, 0xED4245]),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text=author)
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /serverstats
    # ==================================================================
    @app_commands.command(name="serverstats", description="View total server study statistics.")
    async def serverstats_command(self, interaction: discord.Interaction):
        """Shows aggregate server study stats."""
        data = load_data_sync()
        users = data.get("users", {})

        total_alltime = 0
        total_sessions = 0
        total_messages = 0
        total_doubt = 0
        best_day_ever = 0
        best_day_user = "Unknown"
        total_streak = 0
        longest_streak = 0
        longest_streak_user = "Unknown"

        for uid, udata in users.items():
            total_alltime += udata.get("total_seconds_alltime", 0)
            total_sessions += udata.get("session_count", 0)
            total_messages += udata.get("total_messages", 0)
            total_doubt += udata.get("total_seconds_doubt", 0)

            user_best = udata.get("best_day_seconds", 0)
            if user_best > best_day_ever:
                best_day_ever = user_best
                best_day_user = udata.get("username", "Unknown")

            user_streak = udata.get("longest_streak_days", 0)
            if user_streak > longest_streak:
                longest_streak = user_streak
                longest_streak_user = udata.get("username", "Unknown")

        total_hours = total_alltime / 3600
        doubt_hours = total_doubt / 3600
        best_day_hours = best_day_ever / 3600

        # Find most active day of the week
        day_counts = {i: 0 for i in range(7)}
        for uid, udata in users.items():
            for date_str, secs in udata.get("daily_history", {}).items():
                try:
                    d = datetime.date.fromisoformat(date_str)
                    day_counts[d.weekday()] += secs
                except ValueError:
                    pass

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        most_active_day_idx = max(day_counts, key=day_counts.get)
        most_active_day = day_names[most_active_day_idx]

        embed = discord.Embed(
            title="📊 Study Boi — Server Stats",
            color=0x5865F2,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(
            name="📚 Total Study Time",
            value=f"**{total_hours:.1f} hours** across **{total_sessions}** sessions",
            inline=False,
        )
        embed.add_field(name="❓ Total Doubt Time", value=f"**{doubt_hours:.1f} hours**", inline=True)
        embed.add_field(name="💬 Total Messages", value=f"**{total_messages:,}**", inline=True)
        embed.add_field(name="📅 Most Active Day", value=f"**{most_active_day}**", inline=True)
        embed.add_field(
            name="🏆 Best Single Day",
            value=f"**{best_day_hours:.1f}h** by {best_day_user}",
            inline=True,
        )
        embed.add_field(
            name="🔥 Longest Streak",
            value=f"**{longest_streak} days** by {longest_streak_user}",
            inline=True,
        )
        embed.add_field(
            name="👥 Tracked Users",
            value=f"**{len(users)}**",
            inline=True,
        )
        embed.set_footer(text="The grind never lies. 📈")
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /history
    # ==================================================================
    @app_commands.command(name="history", description="View your last 10 study sessions.")
    @app_commands.describe(user="The user to check (defaults to you)")
    async def history_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Shows the last 10 days of study activity."""
        target = user or interaction.user
        data = load_data_sync()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.response.send_message(
                f"📭 No data for **{target.display_name}**.", ephemeral=True
            )
            return

        udata = data["users"][uid]
        history = udata.get("daily_history", {})

        # Sort by date, most recent first
        sorted_days = sorted(history.items(), key=lambda x: x[0], reverse=True)[:10]

        if not sorted_days:
            await interaction.response.send_message(
                f"📭 No study history for **{target.display_name}** yet.", ephemeral=True
            )
            return

        lines = []
        for date_str, secs in sorted_days:
            hours = secs / 3600
            try:
                d = datetime.date.fromisoformat(date_str)
                day_name = d.strftime("%a %b %d")
            except ValueError:
                day_name = date_str

            # Visual indicator
            if hours >= 3:
                emoji = "💚"
            elif hours >= 1:
                emoji = "🟩"
            elif hours > 0:
                emoji = "🟨"
            else:
                emoji = "⬛"

            bar_filled = min(int(hours / 0.5), 20)  # Each block = 30 min
            bar = "█" * bar_filled + "░" * (20 - bar_filled)

            lines.append(f"{emoji} `{day_name}` {bar} **{hours:.1f}h**")

        accent_color = USER_COLORS.get(target.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f"📖 {target.display_name}'s Recent Study History",
            description="\n".join(lines),
            color=accent_color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text="Last 10 days of activity")
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /countdown
    # ==================================================================
    @app_commands.command(name="countdown", description="Set or check exam countdown.")
    @app_commands.describe(exam_name="Name of the exam (e.g., JEE Mains)", exam_date="Date in YYYY-MM-DD format")
    async def countdown_command(
        self, interaction: discord.Interaction,
        exam_name: str | None = None,
        exam_date: str | None = None,
    ):
        """Sets or displays an exam countdown."""
        data = load_data_sync()

        if exam_name and exam_date:
            # Setting a new countdown
            try:
                target_date = datetime.date.fromisoformat(exam_date)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid date format. Use `YYYY-MM-DD` (e.g., `2025-01-22`).", ephemeral=True
                )
                return

            days_left = (target_date - datetime.date.today()).days
            if days_left < 0:
                await interaction.response.send_message("❌ That date is in the past!", ephemeral=True)
                return

            # Save to meta
            if "countdowns" not in data:
                data["countdowns"] = {}
            data["countdowns"][exam_name] = exam_date
            save_data_sync(data)

            embed = discord.Embed(
                title=f"⏳ Countdown Set: {exam_name}",
                description=(
                    f"📅 **{target_date.strftime('%B %d, %Y')}**\n"
                    f"⏰ **{days_left} days** remaining\n\n"
                    f"{'🔴 CRUNCH TIME!' if days_left <= 30 else '📚 Keep grinding!'}"
                ),
                color=0xFF0000 if days_left <= 30 else 0x57F287,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            await interaction.response.send_message(embed=embed)
        else:
            # Show existing countdowns
            countdowns = data.get("countdowns", {})
            if not countdowns:
                await interaction.response.send_message(
                    "📭 No countdowns set. Use `/countdown exam_name:\"JEE\" exam_date:\"2025-01-22\"` to set one.",
                    ephemeral=True,
                )
                return

            lines = []
            for name, date_str in sorted(countdowns.items(), key=lambda x: x[1]):
                try:
                    target_date = datetime.date.fromisoformat(date_str)
                    days_left = (target_date - datetime.date.today()).days
                    if days_left < 0:
                        lines.append(f"~~{name}~~ — **PAST** ({target_date.strftime('%b %d')})")
                    elif days_left <= 7:
                        lines.append(f"🔴 **{name}** — **{days_left} DAYS!** ({target_date.strftime('%b %d')})")
                    elif days_left <= 30:
                        lines.append(f"🟡 **{name}** — **{days_left} days** ({target_date.strftime('%b %d')})")
                    else:
                        lines.append(f"🟢 **{name}** — **{days_left} days** ({target_date.strftime('%b %d')})")
                except ValueError:
                    lines.append(f"**{name}** — Invalid date")

            embed = discord.Embed(
                title="⏳ Exam Countdowns",
                description="\n".join(lines),
                color=0x5865F2,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            await interaction.response.send_message(embed=embed)

    # ==================================================================
    # TASK: WEEKLY DUEL (Every Sunday 9 PM IST)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def weekly_duel_check(self):
        """Every Sunday at 9 PM IST, announces who won the week."""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        # Sunday = 6, 9 PM, first 10 minutes
        if now_ist.weekday() != 6 or now_ist.hour != 21 or now_ist.minute >= 10:
            return

        # Prevent double fire
        flag = f"_duel_{now_ist.date().isoformat()}"
        if getattr(self, flag, False):
            return
        setattr(self, flag, True)

        data = load_data_sync()
        users = data.get("users", {})

        v_data = users.get(VALENCE_ID, {})
        u_data = users.get(UJJWAL_ID, {})

        v_hours = v_data.get("total_seconds_weekly", 0) / 3600
        u_hours = u_data.get("total_seconds_weekly", 0) / 3600
        v_name = v_data.get("username", "Valence")
        u_name = u_data.get("username", "Ujjwal")

        if v_hours > u_hours:
            winner_name, winner_hours = v_name, v_hours
            loser_name, loser_hours = u_name, u_hours
            winner_id = VALENCE_ID
        elif u_hours > v_hours:
            winner_name, winner_hours = u_name, u_hours
            loser_name, loser_hours = v_name, v_hours
            winner_id = UJJWAL_ID
        else:
            # Tie
            winner_name, winner_hours = None, v_hours
            loser_name, loser_hours = None, u_hours
            winner_id = None

        channel = self.bot.get_channel(CELEBRATION_CHANNEL_ID)
        if not channel:
            return

        if winner_id is None:
            # TIE
            embed = discord.Embed(
                title="⚔️ WEEKLY DUEL — IT'S A TIE!",
                description=(
                    f"Both warriors studied **{v_hours:.1f} hours** this week!\n\n"
                    f"🤝 **{v_name}**: {v_hours:.1f}h\n"
                    f"🤝 **{u_name}**: {u_hours:.1f}h\n\n"
                    f"*Neither one backed down. Respect.*"
                ),
                color=0xFEE75C,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
        else:
            diff = winner_hours - loser_hours
            embed = discord.Embed(
                title="⚔️ WEEKLY DUEL — WE HAVE A WINNER!",
                description=(
                    f"# 🏆 {winner_name} WINS!\n\n"
                    f"🥇 **{winner_name}**: **{winner_hours:.1f}h**\n"
                    f"🥈 **{loser_name}**: **{loser_hours:.1f}h**\n\n"
                    f"💀 Gap: **{diff:.1f} hours**\n\n"
                    f"*{loser_name}, you got outworked. Step it up next week.*"
                ),
                color=0x57F287,
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        embed.set_footer(text="Weekly duel resets Monday. The grind continues. ⚔️")

        try:
            await channel.send(embed=embed)
            logging.info(f"[DUEL] Weekly duel announced: {winner_name or 'TIE'}")
        except Exception as e:
            logging.error(f"[DUEL] Failed to send: {e}")

    @weekly_duel_check.before_loop
    async def before_duel(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK: BREAK REMINDER (every 5 min check)
    # ==================================================================
    @tasks.loop(minutes=5)
    async def break_reminder_check(self):
        """If someone has been in a study voice channel for 2+ hours continuously,
        sends them a gentle break reminder DM (once per session)."""
        data = load_data_sync()
        users = data.get("users", {})
        now_ts = int(time.time())

        for uid_str in [VALENCE_ID, UJJWAL_ID]:
            udata = users.get(uid_str, {})
            start_ts = udata.get("session_start_timestamp")
            if start_ts is None:
                continue

            elapsed = now_ts - start_ts
            # Only fire at 2h mark (7200-7500s window to avoid repeat)
            if 7200 <= elapsed < 7500:
                flag = f"_break_reminder_{uid_str}_{start_ts}"
                if getattr(self, flag, False):
                    continue
                setattr(self, flag, True)

                for guild in self.bot.guilds:
                    member = guild.get_member(int(uid_str))
                    if member:
                        try:
                            embed = discord.Embed(
                                title="☕ 2-Hour Break Reminder",
                                description=(
                                    f"You've been studying for **{elapsed // 3600}h {(elapsed % 3600) // 60}m** straight!\n\n"
                                    f"🧠 Your brain needs a 10-minute break to consolidate what you've learned.\n"
                                    f"💧 Drink water. Stretch. Look away from the screen.\n\n"
                                    f"*Then come back and keep destroying it.* 💪"
                                ),
                                color=0x57F287,
                                timestamp=datetime.datetime.now(datetime.UTC),
                            )
                            await member.send(embed=embed)
                            logging.info(f"[BREAK] Sent 2h reminder to {udata.get('username', uid_str)}")
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            logging.error(f"[BREAK] Error for {uid_str}: {e}")
                        break

    @break_reminder_check.before_loop
    async def before_break(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK: TOUCH GRASS ALERT (every 15 min check)
    # ==================================================================
    @tasks.loop(minutes=15)
    async def touch_grass_check(self):
        """If someone studied 8+ hours today, sends a 'touch grass' message."""
        data = load_data_sync()
        users = data.get("users", {})
        today_str = datetime.date.today().isoformat()

        for uid_str in [VALENCE_ID, UJJWAL_ID]:
            udata = users.get(uid_str, {})
            today_secs = udata.get("daily_history", {}).get(today_str, 0)
            today_hours = today_secs / 3600

            if today_hours < 8:
                continue

            # Only send once per day per user
            last_sent = self._touch_grass_sent_today.get(uid_str)
            if last_sent == today_str:
                continue
            self._touch_grass_sent_today[uid_str] = today_str

            for guild in self.bot.guilds:
                member = guild.get_member(int(uid_str))
                if member:
                    try:
                        msg = random.choice(TOUCH_GRASS_MESSAGES).format(hours=today_hours)
                        embed = discord.Embed(
                            title="🌿 TOUCH GRASS ALERT",
                            description=msg,
                            color=0x57F287,
                            timestamp=datetime.datetime.now(datetime.UTC),
                        )
                        embed.set_footer(text=f"Today's total: {today_hours:.1f}h | You're a machine 🤖")
                        await member.send(embed=embed)
                        logging.info(f"[TOUCH GRASS] Sent to {udata.get('username', uid_str)} ({today_hours:.1f}h)")
                    except Exception as e:
                        logging.error(f"[TOUCH GRASS] Error for {uid_str}: {e}")
                    break

    @touch_grass_check.before_loop
    async def before_touch_grass(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # COMMAND: /whowon — Live weekly duel status
    # ==================================================================
    @app_commands.command(name="whowon", description="See who's winning the weekly duel right now!")
    async def whowon_command(self, interaction: discord.Interaction):
        """Shows the live weekly duel standings."""
        data = load_data_sync()
        users = data.get("users", {})

        v_data = users.get(VALENCE_ID, {})
        u_data = users.get(UJJWAL_ID, {})
        v_hours = v_data.get("total_seconds_weekly", 0) / 3600
        u_hours = u_data.get("total_seconds_weekly", 0) / 3600
        v_name = v_data.get("username", "Valence")
        u_name = u_data.get("username", "Ujjwal")

        total = v_hours + u_hours
        if total > 0:
            v_pct = v_hours / total * 100
            u_pct = u_hours / total * 100
        else:
            v_pct = u_pct = 50

        # Visual bar
        bar_len = 20
        v_bar = int(v_pct / 100 * bar_len)
        u_bar = bar_len - v_bar
        bar = "🟦" * v_bar + "🟪" * u_bar

        if v_hours > u_hours:
            status = f"🏆 **{v_name}** is WINNING by **{v_hours - u_hours:.1f}h**!"
            color = 0x5865F2
        elif u_hours > v_hours:
            status = f"🏆 **{u_name}** is WINNING by **{u_hours - v_hours:.1f}h**!"
            color = 0xEB459E
        else:
            status = "⚔️ It's a **TIE**! Who breaks it first?"
            color = 0xFEE75C

        # Days left in the week
        now = datetime.date.today()
        days_left = (7 - now.weekday()) % 7
        if days_left == 0:
            days_left = 7

        embed = discord.Embed(
            title="⚔️ Weekly Duel — LIVE",
            description=(
                f"{status}\n\n"
                f"🟦 **{v_name}**: **{v_hours:.1f}h** ({v_pct:.0f}%)\n"
                f"🟪 **{u_name}**: **{u_hours:.1f}h** ({u_pct:.0f}%)\n\n"
                f"{bar}\n\n"
                f"📅 **{days_left} day(s)** left this week"
            ),
            color=color,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text="Resets every Monday. May the grind be with you. ⚔️")
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /flex — Dramatic stats flex
    # ==================================================================
    @app_commands.command(name="flex", description="Show off your study stats dramatically!")
    @app_commands.describe(user="Who's flexing? (defaults to you)")
    async def flex_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Dramatic flex of your best stats."""
        target = user or interaction.user
        data = load_data_sync()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.response.send_message("📭 No data to flex. Study first!", ephemeral=True)
            return

        udata = data["users"][uid]
        total_hours = udata.get("total_seconds_alltime", 0) / 3600
        sessions = udata.get("session_count", 0)
        best_day = udata.get("best_day_seconds", 0) / 3600
        longest_session = udata.get("longest_session_seconds", 0) / 3600
        streak = udata.get("longest_streak_days", 0)
        weekly_hours = udata.get("total_seconds_weekly", 0) / 3600
        msgs = udata.get("total_messages", 0)

        # Generate flex tier
        if total_hours >= 200:
            tier = "👑 LEGENDARY"
            tier_msg = "You're not even human anymore. You're a MACHINE."
        elif total_hours >= 100:
            tier = "💎 DIAMOND"
            tier_msg = "Most people WISH they had your discipline."
        elif total_hours >= 50:
            tier = "🥇 GOLD"
            tier_msg = "You're in the top tier. Keep pushing."
        elif total_hours >= 25:
            tier = "🥈 SILVER"
            tier_msg = "Solid grinder. The next milestone awaits."
        elif total_hours >= 5:
            tier = "🥉 BRONZE"
            tier_msg = "You've started. Now don't stop."
        else:
            tier = "📖 BEGINNER"
            tier_msg = "Everyone starts somewhere. Keep going."

        accent = USER_COLORS.get(target.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f"💪 {target.display_name}'s FLEX",
            description=f"## {tier}\n*{tier_msg}*",
            color=accent,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="📚 Total Study", value=f"**{total_hours:.1f}h**", inline=True)
        embed.add_field(name="📅 This Week", value=f"**{weekly_hours:.1f}h**", inline=True)
        embed.add_field(name="🎯 Sessions", value=f"**{sessions}**", inline=True)
        embed.add_field(name="🏆 Best Day", value=f"**{best_day:.1f}h**", inline=True)
        embed.add_field(name="⚡ Longest Session", value=f"**{longest_session:.1f}h**", inline=True)
        embed.add_field(name="🔥 Best Streak", value=f"**{streak} days**", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{msgs:,}**", inline=True)

        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Numbers don't lie. The grind speaks for itself. 💪")
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /studytip — Science-backed study techniques
    # ==================================================================
    STUDY_TIPS = [
        ("🧠 Active Recall", "Don't just re-read notes. Close the book and try to recall everything from memory. Studies show this is 3x more effective than passive reading.", "Karpicke & Blunt, 2011"),
        ("📅 Spaced Repetition", "Review material at increasing intervals: 1 day, 3 days, 1 week, 2 weeks. Your brain consolidates memories better with gaps between reviews.", "Ebbinghaus Forgetting Curve"),
        ("🎯 Pomodoro Technique", "Study in 25-50 min focused blocks with 5-10 min breaks. Your brain can only maintain deep focus for ~45 min before it needs a reset.", "Francesco Cirillo"),
        ("✍️ Feynman Technique", "Explain the concept as if teaching a 5-year-old. If you can't explain it simply, you don't understand it well enough.", "Richard Feynman"),
        ("🔗 Interleaving", "Mix up different subjects/topics in one session instead of doing one subject for hours. This builds stronger neural connections.", "Rohrer & Taylor, 2007"),
        ("😴 Sleep on It", "Your brain consolidates learning DURING sleep. Study hard, then get 7-8 hours. An all-nighter destroys more than it builds.", "Walker, 'Why We Sleep'"),
        ("🏃 Exercise Before Study", "20 minutes of cardio before studying increases BDNF (brain-derived neurotrophic factor) — literally grows new brain cells.", "Ratey, 'Spark'"),
        ("📝 Dual Coding", "Combine words AND visuals. Draw diagrams, mind maps, or flowcharts alongside your notes. Two encoding paths = stronger memory.", "Paivio, 1986"),
        ("🎵 Binaural Beats", "Listen to 40Hz gamma binaural beats while studying. Research shows it can enhance focus and memory consolidation.", "Colzato et al., 2017"),
        ("💧 Stay Hydrated", "Even 2% dehydration reduces cognitive performance by 20%. Keep a water bottle on your desk and drink every 30 minutes.", "Adan, 2012"),
        ("🧘 2-Minute Meditation", "Before a study session, close your eyes and breathe for 2 minutes. This activates your prefrontal cortex (focus center).", "Mindfulness Research"),
        ("📱 Phone in Another Room", "The mere PRESENCE of your phone on your desk reduces cognitive capacity by 10%, even when it's off.", "Ward et al., 2017"),
        ("✅ Eat the Frog", "Do the hardest/most boring subject FIRST when your willpower is highest. Willpower depletes throughout the day.", "Brian Tracy"),
        ("🔄 Practice Testing", "Take practice tests and solve problems WITHOUT looking at solutions first. Struggling to retrieve = stronger learning.", "Dunlosky et al., 2013"),
    ]

    @app_commands.command(name="studytip", description="Get a science-backed study technique tip.")
    async def studytip_command(self, interaction: discord.Interaction):
        """Random study tip with scientific backing."""
        title, description, source = random.choice(self.STUDY_TIPS)
        embed = discord.Embed(
            title=f"{title}",
            description=f"{description}\n\n📎 *Source: {source}*",
            color=random.choice([0x5865F2, 0x57F287, 0xFEE75C, 0xEB459E]),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text="Study smarter, not just harder. 🧠")
        await interaction.response.send_message(embed=embed)

    # ==================================================================
    # COMMAND: /predict — Weekly pace prediction
    # ==================================================================
    @app_commands.command(name="predict", description="Predict your end-of-week study hours at current pace.")
    @app_commands.describe(user="Who to predict for (defaults to you)")
    async def predict_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Predicts end-of-week hours based on current pace."""
        target = user or interaction.user
        data = load_data_sync()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.response.send_message("📭 No data yet!", ephemeral=True)
            return

        udata = data["users"][uid]
        weekly_secs = udata.get("total_seconds_weekly", 0)
        weekly_hours = weekly_secs / 3600

        now = datetime.date.today()
        day_of_week = now.weekday()  # 0=Mon
        days_passed = day_of_week + 1  # How many days since Monday
        days_left = 7 - days_passed

        if days_passed > 0:
            daily_avg = weekly_hours / days_passed
            predicted = weekly_hours + (daily_avg * days_left)
        else:
            daily_avg = 0
            predicted = 0

        # Determine which milestone they'd hit
        milestones = {5: "🥉 Bronze", 15: "🥈 Silver", 30: "🥇 Gold", 50: "💎 Diamond", 70: "👑 Legendary"}
        predicted_role = "📖 None yet"
        for threshold, name in sorted(milestones.items()):
            if predicted >= threshold:
                predicted_role = name

        # Motivational verdict
        if predicted >= 70:
            verdict = "🔥 You're on track for LEGENDARY. Don't slow down!"
        elif predicted >= 50:
            verdict = "💎 Diamond pace! Push harder for Legendary!"
        elif predicted >= 30:
            verdict = "🥇 Solid Gold pace. Can you go higher?"
        elif predicted >= 15:
            verdict = "🥈 Silver territory. You can do better."
        elif predicted >= 5:
            verdict = "🥉 Bronze pace. Step it up this week."
        else:
            verdict = "⚠️ At this rate you won't even get Bronze. GRIND HARDER."

        accent = USER_COLORS.get(target.id, DEFAULT_COLOR)
        embed = discord.Embed(
            title=f"🔮 {target.display_name}'s Weekly Prediction",
            description=(
                f"📊 **Current**: {weekly_hours:.1f}h in {days_passed} day(s)\n"
                f"📈 **Daily avg**: {daily_avg:.1f}h/day\n"
                f"🔮 **Predicted by Sunday**: **{predicted:.1f}h**\n"
                f"🎯 **Predicted role**: {predicted_role}\n\n"
                f"{verdict}"
            ),
            color=accent,
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_footer(text=f"{days_left} day(s) left to change your fate. ⏳")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BonusFeaturesCog(bot))
