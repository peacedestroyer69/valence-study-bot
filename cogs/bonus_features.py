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
from utils import (
    get_ist_date, get_ist_now, IST_TZ,
    VALENCE_ID, UJJWAL_ID, CELEBRATION_CHANNEL_ID, LEADERBOARD_CHANNEL_ID,
    STUDY_TEXT_CHANNEL_ID, STUDY_CHANNELS, DOUBT_CHANNELS, USER_COLORS, DEFAULT_COLOR
)

# DATA_FILE removed, cogs use self.bot database methods

# Configuration imported from utils.py


# Synchronous file load/save functions removed. Using self.bot.load_data() and self.bot.save_data() instead.


# ============================================================
# MOTIVATIONAL QUOTES (curated, not generic)
# ============================================================
MOTIVATIONAL_QUOTES = [
    # --- Core grind mindset ---
    ("The grind never lies.", "YPT Philosophy"),
    ("Every hour compounds. Keep going.", "Compound Effect"),
    ("Discipline > Motivation. Always.", "Jocko Willink"),
    ("Your future self is watching. Don't disappoint.", "Unknown"),
    ("JEE doesn't care about excuses. Neither should you.", "Reality"),
    ("One more hour. That's the gap between you and them.", "Compete"),
    ("Consistency beats intensity every single time.", "James Clear"),
    ("The pain of discipline is lighter than the pain of regret.", "Jim Rohn"),
    ("Study like your rank depends on it. Because it does.", "Facts"),
    ("While you're sleeping, someone else is studying.", "Truth"),
    # --- Classic quotes ---
    ("Don't wish it were easier. Wish you were better.", "Jim Rohn"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Success is the sum of small efforts repeated daily.", "Robert Collier"),
    ("Hard work beats talent when talent doesn't work hard.", "Tim Notke"),
    ("You don't have to be great to start, but you have to start to be great.", "Zig Ziglar"),
    ("The expert in anything was once a beginner.", "Helen Hayes"),
    ("It's not about having time. It's about making time.", "Grind"),
    ("Your comfort zone is a beautiful place, but nothing grows there.", "Growth"),
    ("Fall seven times, stand up eight.", "Japanese Proverb"),
    ("You are one study session away from a breakthrough.", "Keep Going"),
    # --- JEE / competitive exam specific ---
    ("AIR 1 didn't take days off. Will you?", "Compete"),
    ("Every NCERT line you skip is a mark lost in JEE.", "Strategy"),
    ("Toppers don't have more hours in the day. They waste fewer.", "Efficiency"),
    ("Your rank is decided now, not on exam day.", "JEE Reality"),
    ("The student who masters basics beats the one who skips to advanced.", "Foundation"),
    ("PYQs don't lie. Solve them daily.", "JEE Prep"),
    ("Revision is not optional. It's the whole game.", "Memory"),
    ("One PYQ solved = one less surprise on exam day.", "Prep"),
    ("You're not tired. You're just not interested enough. Find a reason.", "Mindset"),
    ("The gap between AIR 1 and AIR 1000 is mostly consistency.", "JEE Stats"),
    # --- Physics/Math/Chem motivation ---
    ("Physics is not hard. You're just not spending enough time with it.", "Physics"),
    ("Mathematics is the language of the universe. Learn it.", "Gauss"),
    ("Chemistry rewards patience. Don't rush the reaction.", "Chemistry"),
    ("Every formula you memorize is a weapon you carry into battle.", "Exam Day"),
    ("Calculus felt impossible once. Now it's your weapon. Keep going.", "Progress"),
    # --- Mental strength ---
    ("Champions train when they don't feel like it. That's what makes them champions.", "Champions"),
    ("Your brain is a muscle. Study is the gym. Skip sessions, lose strength.", "Neuroscience"),
    ("Pressure makes diamonds. You're being compressed right now.", "Resilience"),
    ("The nights you study while others sleep are the nights your rank improves.", "Night Grind"),
    ("You will not regret studying hard. You WILL regret not studying hard.", "No Regrets"),
    ("Don't count the hours. Make the hours count.", "Quality"),
    ("Motivation gets you started. Habit keeps you going.", "Systems"),
    ("The best time to start was yesterday. The second best time is right now.", "Now"),
    ("Small progress is still progress. Show up every day.", "Incremental Growth"),
    ("Doubt kills more dreams than failure ever will.", "Mindset"),
    # --- Competitor framing ---
    ("Someone is studying right now who wants your rank. Fight for it.", "Competition"),
    ("The student who sits down to study when they don't want to always wins.", "Discipline"),
    ("Your competition is not resting. Are you?", "Urgency"),
    ("Every hour of studying today is an investment that pays on exam day.", "Investment"),
    ("Success is not given. It is taken. So take it.", "Ownership"),
    # --- New additions ---
    ("The difference between a 99 percentile and 95 percentile is one extra hour every single day.", "JEE Math"),
    ("Your parents didn't sacrifice everything for you to scroll reels at 2 AM.", "Wake Up Call"),
    ("IIT Bombay CS doesn't care about your mood. It cares about your marks.", "Harsh Truth"),
    ("The syllabus won't finish itself. Open the book. Start the chapter. NOW.", "Action"),
    ("You're not competing with 20 lakh students. You're competing with yesterday's version of you.", "Self-Competition"),
    ("Sleep is earned, not given. Did you earn it today?", "Discipline"),
    ("Kota toppers aren't smarter. They're just more consistent.", "Consistency"),
    ("That 'one more episode' costs you 3 marks in JEE. Is it worth it?", "Opportunity Cost"),
    ("The formula sheet you make today is the weapon you carry into the exam hall.", "Preparation"),
    ("Every unsolved PYQ is a question that WILL appear again. Solve it now or regret it later.", "PYQ Strategy"),
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
        """Sends a Gemini-personalized motivational quote embed, with a rich static fallback bank."""
        await interaction.response.defer()

        # Try to get a Gemini-generated quote first
        ai_quote = None
        ai_author = None
        try:
            from cogs.gemini_brain import _call_gemini
            uid = str(interaction.user.id)
            data = await self.bot.load_data()
            udata = data.get("users", {}).get(uid, {})
            hours_today = round(udata.get("total_seconds_today", 0) / 3600, 1)
            hours_alltime = round(udata.get("total_seconds_alltime", 0) / 3600, 1)
            streak = udata.get("current_streak_days", 0)
            username = interaction.user.display_name

            prompt = (
                f"Generate a single powerful, original motivational quote for a JEE aspirant named {username}.\n"
                f"Context: {username} has studied {hours_today}h today, {hours_alltime}h all-time, "
                f"and has a {streak}-day study streak.\n"
                f"Rules:\n"
                f"- ONE quote only, max 2 sentences\n"
                f"- Brutally honest, JEE-specific, call out their specific stats\n"
                f"- Do NOT use generic cliches like 'believe in yourself' or 'you can do it'\n"
                f"- Make it hit hard, specific, urgent\n"
                f"- Format: just the quote text, no quotation marks, no attribution"
            )
            result = await _call_gemini(prompt, fallback="", timeout=8.0,
                                        model_preference=["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"])
            if result and len(result) > 20:
                ai_quote = result.strip()
                ai_author = f"Gemini AI for {username}"
        except Exception as e:
            logging.warning(f"[MOTIVATE] Gemini quote generation failed: {e}")

        # Use AI quote or fall back to curated static bank
        if ai_quote:
            quote = ai_quote
            author = ai_author
        else:
            quote, author = random.choice(MOTIVATIONAL_QUOTES)

        embed = discord.Embed(
            title="Study Motivation",
            description=f'"{quote}"',
            color=random.choice([0x5865F2, 0x57F287, 0xFEE75C, 0xEB459E, 0xED4245]),
            timestamp=get_ist_now(),
        )
        embed.set_footer(text=f"— {author}")
        await interaction.followup.send(embed=embed)

    # ==================================================================
    # COMMAND: /serverstats
    # ==================================================================
    @app_commands.command(name="serverstats", description="View total server study statistics.")
    async def serverstats_command(self, interaction: discord.Interaction):
        """Shows aggregate server study stats."""
        await interaction.response.defer(ephemeral=False)
        data = await self.bot.load_data()
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
            timestamp=get_ist_now(),
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
        await interaction.followup.send(embed=embed)

    # ==================================================================
    # COMMAND: /history
    # ==================================================================
    @app_commands.command(name="history", description="View your last 10 study sessions.")
    @app_commands.describe(user="The user to check (defaults to you)")
    async def history_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Shows the last 10 days of study activity."""
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        data = await self.bot.load_data()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.followup.send(
                f"📭 No data for **{target.display_name}**."
            )
            return

        udata = data["users"][uid]
        history = udata.get("daily_history", {})

        # Sort by date, most recent first
        sorted_days = sorted(history.items(), key=lambda x: x[0], reverse=True)[:10]

        if not sorted_days:
            await interaction.followup.send(
                f"📭 No study history for **{target.display_name}** yet."
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
            timestamp=get_ist_now(),
        )
        embed.set_footer(text="Last 10 days of activity")
        await interaction.followup.send(embed=embed)

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
        await interaction.response.defer(ephemeral=False)
        data = await self.bot.load_data()

        if exam_name and exam_date:
            # Enforce admin permission for setting countdowns
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ Only server administrators can set new countdowns!", ephemeral=True)
                return

            if len(exam_name) > 50:
                await interaction.followup.send("❌ Exam name cannot exceed 50 characters!", ephemeral=True)
                return

            try:
                target_date = datetime.date.fromisoformat(exam_date)
            except ValueError:
                await interaction.followup.send(
                    "❌ Invalid date format. Use `YYYY-MM-DD` (e.g., `2025-01-22`)."
                )
                return

            days_left = (target_date - get_ist_date()).days
            if days_left < 0:
                await interaction.followup.send("❌ That date is in the past!")
                return

            # Check total count limit (max 10 active countdowns)
            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                countdowns = data.get("countdowns", {})
                if len(countdowns) >= 10 and exam_name not in countdowns:
                    limit_reached = True
                else:
                    limit_reached = False
                    if "countdowns" not in data:
                        data["countdowns"] = {}
                    data["countdowns"][exam_name] = exam_date
                    await self.bot.save_data(data)

            if limit_reached:
                await interaction.followup.send("❌ Limit of 10 active countdowns reached! Delete an existing countdown before setting a new one.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"⏳ Countdown Set: {exam_name}",
                description=(
                    f"📅 **{target_date.strftime('%B %d, %Y')}**\n"
                    f"⏰ **{days_left} days** remaining\n\n"
                    f"{'🔴 CRUNCH TIME!' if days_left <= 30 else '📚 Keep grinding!'}"
                ),
                color=0xFF0000 if days_left <= 30 else 0x57F287,
                timestamp=get_ist_now(),
            )
            await interaction.followup.send(embed=embed)
        else:
            # Show existing countdowns
            countdowns = data.get("countdowns", {})
            if not countdowns:
                await interaction.followup.send(
                    "📭 No countdowns set. Ask a server admin to set one."
                )
                return

            lines = []
            for name, date_str in sorted(countdowns.items(), key=lambda x: x[1]):
                try:
                    target_date = datetime.date.fromisoformat(date_str)
                    days_left = (target_date - get_ist_date()).days
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

            description_text = "\n".join(lines)
            if len(description_text) > 4000:
                description_text = description_text[:3997] + "..."

            embed = discord.Embed(
                title="⏳ Exam Countdowns",
                description=description_text,
                color=0x5865F2,
                timestamp=get_ist_now(),
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="delete_countdown", description="Delete an exam countdown (Admin only).")
    @app_commands.describe(exam_name="Name of the countdown to delete")
    @app_commands.default_permissions(administrator=True)
    async def delete_countdown(self, interaction: discord.Interaction, exam_name: str):
        await interaction.response.defer(ephemeral=True)
        deleted = False
        async with self.bot.db_write_lock:
            data = await self.bot.load_data()
            countdowns = data.get("countdowns", {})
            if exam_name in countdowns:
                del countdowns[exam_name]
                await self.bot.save_data(data)
                deleted = True

        if deleted:
            await interaction.followup.send(f"✅ Successfully deleted countdown for **{exam_name}**.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ No countdown found with the name **{exam_name}**.", ephemeral=True)

    # ==================================================================
    # TASK: WEEKLY DUEL (Every Sunday 9 PM IST)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def weekly_duel_check(self):
        """Every Sunday at 9 PM IST, announces who won the week."""
        try:
            now_ist = get_ist_now()

            # Sunday = 6, 9 PM
            if now_ist.weekday() != 6 or now_ist.hour != 21:
                return

            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
                today_str = now_ist.date().isoformat()
                if loop_state.get("last_weekly_duel") == today_str:
                    return

                # Sort specific users (Valence and Ujjwal) by weekly hours
                users = data.get("users", {})
                valence_uid = str(VALENCE_ID)
                ujjwal_uid = str(UJJWAL_ID)
                
                v_data = users.get(valence_uid, {})
                u_data = users.get(ujjwal_uid, {})
                
                v_hours = v_data.get("total_seconds_weekly", 0) / 3600
                u_hours = u_data.get("total_seconds_weekly", 0) / 3600
                
                v_name = v_data.get("username", "Valence")
                u_name = u_data.get("username", "Ujjwal")
                
                weekly_hours_list = [
                    (valence_uid, v_name, v_hours),
                    (ujjwal_uid, u_name, u_hours)
                ]
                weekly_hours_list.sort(key=lambda x: x[2], reverse=True)

                winner_id, winner_name, winner_hours = weekly_hours_list[0]
                loser_id, loser_name, loser_hours = weekly_hours_list[1]

                if winner_hours == 0 and loser_hours == 0:
                    logging.info("[DUEL] Skipping weekly duel announcement: both users have 0 hours.")
                    return

                # Mark as done in DB
                loop_state["last_weekly_duel"] = today_str
                await self.bot.save_data(data)

            channel = await self.bot.get_or_fetch_channel(CELEBRATION_CHANNEL_ID)
            if not channel:
                return

            if winner_hours == loser_hours:
                # TIE
                embed = discord.Embed(
                    title="⚔️ WEEKLY DUEL — IT'S A TIE!",
                    description=(
                        f"Both warriors studied **{winner_hours:.1f} hours** this week!\n\n"
                        f"🤝 **{winner_name}**: {winner_hours:.1f}h\n"
                        f"🤝 **{loser_name}**: {loser_hours:.1f}h\n\n"
                        f"*Neither one backed down. Respect.*"
                    ),
                    color=0xFEE75C,
                    timestamp=get_ist_now(),
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
                    timestamp=get_ist_now(),
                )

            embed.set_footer(text="Weekly duel resets Monday. The grind continues. ⚔️")

            try:
                await channel.send(embed=embed)
                logging.info(f"[DUEL] Weekly duel announced: {winner_name or 'TIE'}")
            except Exception as e:
                logging.error(f"[DUEL] Failed to send: {e}")
        except Exception as e:
            logging.error(f"[DUEL] Error in weekly_duel_check loop: {e}", exc_info=True)

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
        try:
            data = await self.bot.load_data()
            users = data.get("users", {})
            now_ts = int(time.time())

            for uid_str in list(users.keys()):
                udata = users.get(uid_str, {})
                start_ts = udata.get("session_start_timestamp")
                if start_ts is None:
                    continue

                elapsed = now_ts - start_ts
                # Only fire at 2h mark or above, guarded by a state attribute
                if elapsed >= 7200:
                    flag = f"_break_reminder_{uid_str}_{start_ts}"
                    if getattr(self, flag, False):
                        continue
                    setattr(self, flag, True)

                    for guild in self.bot.guilds:
                        member = guild.get_member(int(uid_str))
                        if not member:
                            try:
                                member = await guild.fetch_member(int(uid_str))
                            except Exception:
                                member = None
                        if member:
                            in_study_channel = False
                            if member.voice and member.voice.channel:
                                channel_id = member.voice.channel.id
                                if channel_id in STUDY_CHANNELS or channel_id in DOUBT_CHANNELS:
                                    in_study_channel = True
                            
                            if not in_study_channel:
                                continue
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
                                    timestamp=get_ist_now(),
                                )
                                await member.send(embed=embed)
                                logging.info(f"[BREAK] Sent 2h reminder to {udata.get('username', uid_str)}")
                            except discord.Forbidden:
                                pass
                            except Exception as e:
                                logging.error(f"[BREAK] Error for {uid_str}: {e}")
                            break
        except Exception as e:
            logging.error(f"[BREAK] Error in break_reminder_check loop: {e}", exc_info=True)

    @break_reminder_check.before_loop
    async def before_break(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK: TOUCH GRASS ALERT (every 15 min check)
    # ==================================================================
    @tasks.loop(minutes=15)
    async def touch_grass_check(self):
        """If someone studied 8+ hours today, sends a 'touch grass' message."""
        try:
            data = await self.bot.load_data()
            users = data.get("users", {})
            today_str = get_ist_date().isoformat()

            for uid_str in list(users.keys()):
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
                    if not member:
                        try:
                            member = await guild.fetch_member(int(uid_str))
                        except Exception:
                            member = None
                    if member:
                        try:
                            msg = random.choice(TOUCH_GRASS_MESSAGES).format(hours=today_hours)
                            embed = discord.Embed(
                                title="🌿 TOUCH GRASS ALERT",
                                description=msg,
                                color=0x57F287,
                                timestamp=get_ist_now(),
                            )
                            embed.set_footer(text=f"Today's total: {today_hours:.1f}h | You're a machine 🤖")
                            await member.send(embed=embed)
                            logging.info(f"[TOUCH GRASS] Sent to {udata.get('username', uid_str)} ({today_hours:.1f}h)")
                        except Exception as e:
                            logging.error(f"[TOUCH GRASS] Error for {uid_str}: {e}")
                        break
        except Exception as e:
            logging.error(f"[TOUCH GRASS] Error in touch_grass_check loop: {e}", exc_info=True)

    @touch_grass_check.before_loop
    async def before_touch_grass(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # COMMAND: /whowon — Live weekly duel status
    # ==================================================================
    @app_commands.command(name="whowon", description="See who's winning the weekly duel right now!")
    async def whowon_command(self, interaction: discord.Interaction):
        """Shows the live weekly duel standings."""
        await interaction.response.defer(ephemeral=False)
        data = await self.bot.load_data()
        users = data.get("users", {})

        # Sort users by weekly hours
        weekly_hours_list = []
        for u_id, u_data in users.items():
            hours = u_data.get("total_seconds_weekly", 0) / 3600
            name = u_data.get("username", "Unknown")
            weekly_hours_list.append((u_id, name, hours))
        
        weekly_hours_list.sort(key=lambda x: x[2], reverse=True)

        if len(weekly_hours_list) < 2:
            await interaction.followup.send("📭 Need at least two players with study data to have a duel!")
            return

        winner_id, winner_name, winner_hours = weekly_hours_list[0]
        loser_id, loser_name, loser_hours = weekly_hours_list[1]

        total = winner_hours + loser_hours
        if total > 0:
            w_pct = winner_hours / total * 100
            l_pct = loser_hours / total * 100
        else:
            w_pct = l_pct = 50

        # Visual bar
        bar_len = 20
        w_bar = int(w_pct / 100 * bar_len)
        l_bar = bar_len - w_bar
        bar = "🟦" * w_bar + "🟪" * l_bar

        if winner_hours > loser_hours:
            status = f"🏆 **{winner_name}** is WINNING by **{winner_hours - loser_hours:.1f}h**!"
            color = 0x5865F2
        else:
            status = f"⚔️ It's a **TIE** between **{winner_name}** and **{loser_name}**!"
            color = 0xFEE75C

        # Days left in the week
        now = get_ist_date()
        days_left = (7 - now.weekday()) % 7
        if days_left == 0:
            days_left = 7

        embed = discord.Embed(
            title="⚔️ Weekly Duel — LIVE",
            description=(
                f"{status}\n\n"
                f"🟦 **{winner_name}**: **{winner_hours:.1f}h** ({w_pct:.0f}%)\n"
                f"🟪 **{loser_name}**: **{loser_hours:.1f}h** ({l_pct:.0f}%)\n\n"
                f"{bar}\n\n"
                f"📅 **{days_left} day(s)** left this week"
            ),
            color=color,
            timestamp=get_ist_now(),
        )
        embed.set_footer(text="Resets every Monday. May the grind be with you. ⚔️")
        await interaction.followup.send(embed=embed)

    # ==================================================================
    # COMMAND: /flex — Dramatic stats flex
    # ==================================================================
    @app_commands.command(name="flex", description="Show off your study stats dramatically!")
    @app_commands.describe(user="Who's flexing? (defaults to you)")
    async def flex_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Dramatic flex of your best stats."""
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        data = await self.bot.load_data()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.followup.send("📭 No data to flex. Study first!")
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
            timestamp=get_ist_now(),
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
        await interaction.followup.send(embed=embed)

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
            timestamp=get_ist_now(),
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
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        data = await self.bot.load_data()
        uid = str(target.id)

        if uid not in data["users"]:
            await interaction.followup.send("📭 No data yet!")
            return

        udata = data["users"][uid]
        weekly_secs = udata.get("total_seconds_weekly", 0)
        weekly_hours = weekly_secs / 3600

        now = get_ist_date()
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
            timestamp=get_ist_now(),
        )
        embed.set_footer(text=f"{days_left} day(s) left to change your fate. ⏳")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BonusFeaturesCog(bot))
