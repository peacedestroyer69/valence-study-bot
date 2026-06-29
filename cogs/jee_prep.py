import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import logging
import random
import os
import asyncio
import google.generativeai as genai
from utils import (
    get_ist_now, get_ist_date, IST_TZ, UIColors,
    VALENCE_ID, UJJWAL_ID, DAILY_GOAL_SECONDS
)

# JEE Chapters list for Syllabus Compare
JEE_SYLLABUS = {
    "Physics": [
        "Mechanics (Kinematics, NLM, WPE, Rotational)",
        "Thermodynamics & KTG",
        "Electromagnetism (Electrostatics, Current, EMI, AC)",
        "Optics (Wave & Ray)",
        "Modern Physics & Semiconductors"
    ],
    "Chemistry": [
        "Physical Chemistry (Atomic, Thermodynamics, Kinetics, Equilibrium)",
        "Organic Chemistry (GOC, Hydrocarbons, Carbonyls, Biomolecules)",
        "Inorganic Chemistry (Coordination, Bonding, p-block, metallurgy)"
    ],
    "Maths": [
        "Calculus (Limits, Continuity, Derivatives, Integration, Diff Eq)",
        "Coordinate Geometry (Straight Lines, Conics)",
        "Algebra (Quadratics, Complex, Matrices, PnC, Probability)",
        "Vectors & 3D Geometry",
        "Trigonometry & Sequences"
    ]
}

TIER_EMOJIS = {
    0: "🟥",  # Not Started
    1: "🟨",  # Theory Done
    2: "🟧",  # Notes Done
    3: "🟦",  # PYQs Done
    4: "🟩"   # Mastered
}

TIER_NAMES = {
    0: "Not Started",
    1: "Theory / Lecture Completed",
    2: "Notes & Formulas Summarized",
    3: "PYQs Solved (50+)",
    4: "Chapter Mastered"
}

class JEEPrepCog(commands.Cog):
    """JEE specific tools: PYQ tracking, Syllabus tracker, Socratic AI solver, and AI performance audits."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Socratic AI contexts (user_id -> chat history list)
        self.doubt_contexts = {}
        
        # Configure Gemini
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.model = None

        self.weekly_audit_loop.start()

    def cog_unload(self):
        self.weekly_audit_loop.cancel()

    # ------------------------------------------------------------------
    # 1. PYQ TRACKING
    # ------------------------------------------------------------------
    @app_commands.command(name="pyq_log", description="Log your daily PYQ practice statistics.")
    @app_commands.describe(
        subject="Choose Physics, Chemistry, or Maths",
        chapter="Name of the chapter studied",
        questions_solved="Total number of questions attempted",
        correct_answers="Number of questions solved correctly",
        time_spent_mins="Total time spent in minutes"
    )
    @app_commands.choices(
        subject=[
            app_commands.Choice(name="Physics", value="Physics"),
            app_commands.Choice(name="Chemistry", value="Chemistry"),
            app_commands.Choice(name="Maths", value="Maths"),
        ]
    )
    async def pyq_log(
        self,
        interaction: discord.Interaction,
        subject: app_commands.Choice[str],
        chapter: str,
        questions_solved: int,
        correct_answers: int,
        time_spent_mins: int
    ):
        await interaction.response.defer(ephemeral=True)

        if questions_solved <= 0 or correct_answers < 0 or time_spent_mins <= 0:
            await interaction.followup.send("❌ Values must be positive integers!", ephemeral=True)
            return

        if correct_answers > questions_solved:
            await interaction.followup.send("❌ Correct answers cannot exceed total questions solved!", ephemeral=True)
            return

        uid = str(interaction.user.id)
        accuracy = int((correct_answers / questions_solved) * 100)
        pace = round(time_spent_mins / questions_solved, 1)

        async with self.bot.db_write_lock:
            data = await self.bot.load_data()
            udata = self.bot.ensure_user(data, interaction.user)
            
            # Initialize pyq logs
            pyq_history = udata.setdefault("pyq_history", [])
            log_entry = {
                "date": get_ist_date().isoformat(),
                "subject": subject.value,
                "chapter": chapter[:100],  # limit size
                "solved": questions_solved,
                "correct": correct_answers,
                "accuracy": accuracy,
                "minutes": time_spent_mins
            }
            pyq_history.append(log_entry)
            await self.bot.save_data(data)

        embed = discord.Embed(
            title="🎯 PYQ PRACTICE LOGGED",
            description=f"Great job practicing today, **{interaction.user.display_name}**!",
            color=UIColors.SUCCESS
        )
        embed.add_field(name="📚 Subject", value=subject.value, inline=True)
        embed.add_field(name="📖 Chapter", value=chapter[:50], inline=True)
        embed.add_field(name="📝 Solved", value=f"**{correct_answers}** / {questions_solved} correct", inline=True)
        embed.add_field(name="🎯 Accuracy", value=f"**{accuracy}%**", inline=True)
        embed.add_field(name="⏱️ Pace", value=f"**{pace} min/Q**", inline=True)
        embed.set_footer(text="Keep logging daily! Compound your accuracy.")
        await interaction.followup.send(embed=embed, ephemeral=False)

    @app_commands.command(name="pyq_dashboard", description="View your PYQ practice metrics.")
    @app_commands.describe(user="User to check metrics for (defaults to yourself)")
    async def pyq_dashboard(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        uid = str(target.id)

        data = await self.bot.load_data()
        if uid not in data.get("users", {}):
            await interaction.followup.send("📭 No statistics recorded for this user yet.", ephemeral=True)
            return

        udata = data["users"][uid]
        pyq_history = udata.get("pyq_history", [])

        if not pyq_history:
            await interaction.followup.send("📭 No PYQs logged yet! Use `/pyq_log` to start tracking.", ephemeral=True)
            return

        # Aggregate stats
        total_q = 0
        total_c = 0
        total_m = 0
        subj_stats = {"Physics": {"solved": 0, "correct": 0, "minutes": 0},
                      "Chemistry": {"solved": 0, "correct": 0, "minutes": 0},
                      "Maths": {"solved": 0, "correct": 0, "minutes": 0}}

        for entry in pyq_history:
            sub = entry.get("subject")
            solved = entry.get("solved", 0)
            correct = entry.get("correct", 0)
            minutes = entry.get("minutes", 0)

            total_q += solved
            total_c += correct
            total_m += minutes

            if sub in subj_stats:
                subj_stats[sub]["solved"] += solved
                subj_stats[sub]["correct"] += correct
                subj_stats[sub]["minutes"] += minutes

        overall_acc = int((total_c / total_q) * 100) if total_q > 0 else 0
        overall_pace = round(total_m / total_q, 1) if total_q > 0 else 0

        embed = discord.Embed(
            title=f"🎯 PYQ Performance Dashboard — {target.display_name}",
            color=UIColors.BRAND_PRIMARY,
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.description = f"📊 Total solved: **{total_q} questions**\n🎯 Overall Accuracy: **{overall_acc}%**\n⏱️ Average Pace: **{overall_pace} min/Q**"

        for sub, stats in subj_stats.items():
            solved = stats["solved"]
            correct = stats["correct"]
            mins = stats["minutes"]
            if solved > 0:
                acc = int((correct / solved) * 100)
                pace = round(mins / solved, 1)
                embed.add_field(
                    name=f"📚 {sub}",
                    value=f"• Solved: **{solved}** (Correct: **{correct}**)\n• Accuracy: **{acc}%**\n• Pace: **{pace} min/Q**",
                    inline=False
                )
            else:
                embed.add_field(name=f"📚 {sub}", value="*No questions solved yet*", inline=False)

        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # 2. SIDE-BY-SIDE SYLLABUS TRACKER
    # ------------------------------------------------------------------
    @app_commands.command(name="syllabus_mark", description="Update your progress on a JEE syllabus chapter.")
    @app_commands.describe(
        subject="Subject category",
        chapter="Name of the chapter",
        tier="Your current level of completion (0-4)"
    )
    @app_commands.choices(
        subject=[
            app_commands.Choice(name="Physics", value="Physics"),
            app_commands.Choice(name="Chemistry", value="Chemistry"),
            app_commands.Choice(name="Maths", value="Maths"),
        ],
        tier=[
            app_commands.Choice(name="0 - Not Started", value=0),
            app_commands.Choice(name="1 - Lectures Completed", value=1),
            app_commands.Choice(name="2 - Notes & Formulas Summarized", value=2),
            app_commands.Choice(name="3 - PYQs Solved (50+)", value=3),
            app_commands.Choice(name="4 - Chapter Mastered (90%+ Accuracy)", value=4),
        ]
    )
    async def syllabus_mark(
        self,
        interaction: discord.Interaction,
        subject: app_commands.Choice[str],
        chapter: str,
        tier: app_commands.Choice[int]
    ):
        await interaction.response.defer(ephemeral=True)

        uid = str(interaction.user.id)
        async with self.bot.db_write_lock:
            data = await self.bot.load_data()
            udata = self.bot.ensure_user(data, interaction.user)
            
            syllabus_progress = udata.setdefault("syllabus_progress", {})
            syllabus_progress[f"{subject.value}:{chapter}"] = tier.value
            await self.bot.save_data(data)

        embed = discord.Embed(
            title="🏁 SYLLABUS PROGRESS UPDATED",
            description=f"Updated chapter **{chapter}** for **{interaction.user.display_name}**.",
            color=UIColors.SUCCESS
        )
        embed.add_field(name="📚 Subject", value=subject.value, inline=True)
        embed.add_field(name="⚙️ Tier Level", value=f"{TIER_EMOJIS[tier.value]} **{TIER_NAMES[tier.value]}**", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="syllabus_compare", description="Compare JEE syllabus progress side-by-side.")
    async def syllabus_compare(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        # We need Valence and Ujjwal IDs
        v_id = str(VALENCE_ID)
        u_id = str(UJJWAL_ID)

        data = await self.bot.load_data()
        users = data.get("users", {})

        v_prog = (users.get(v_id, {}) or {}).get("syllabus_progress") or {}
        u_prog = (users.get(u_id, {}) or {}).get("syllabus_progress") or {}
        v_name = (users.get(v_id, {}) or {}).get("username", "Valence")
        u_name = (users.get(u_id, {}) or {}).get("username", "Ujjwal")

        embed = discord.Embed(
            title="🏁 JEE Syllabus Progress Grid",
            description=f"🟥 Not Started | 🟨 Lectures Done | 🟧 Notes Done | 🟦 PYQs Done | 🟩 Mastered\n\n**Format:** `Chapter | {v_name} | {u_name}`",
            color=UIColors.BRAND_PRIMARY,
            timestamp=datetime.datetime.now(datetime.UTC)
        )

        for sub, chapters in JEE_SYLLABUS.items():
            field_lines = []
            for ch in chapters:
                v_tier = v_prog.get(f"{sub}:{ch}", 0)
                u_tier = u_prog.get(f"{sub}:{ch}", 0)
                v_emoji = TIER_EMOJIS.get(v_tier, "🟥")
                u_emoji = TIER_EMOJIS.get(u_tier, "🟥")
                field_lines.append(f"• {ch[:35]}... \u279c {v_emoji} vs {u_emoji}")
            
            embed.add_field(
                name=f"📚 {sub}",
                value="\n".join(field_lines) if field_lines else "*No chapters defined*",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # 3. SOCRATIC AI DOUBT SOLVER
    # ------------------------------------------------------------------
    @app_commands.command(name="doubt_solve", description="Ask the Socratic AI JEE Tutor for hints and help on a problem.")
    @app_commands.describe(
        question="Type your doubt or problem text",
        image="Upload an image of the problem (optional)"
    )
    async def doubt_solve(
        self,
        interaction: discord.Interaction,
        question: str,
        image: discord.Attachment | None = None
    ):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("❌ Socratic AI Doubt Solver is currently disabled. The only active AI feature is the Daily Puzzle.", ephemeral=True)

    @app_commands.command(name="doubt_hint", description="Get the next Socratic hint for your active doubt session.")
    async def doubt_hint(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("❌ Socratic AI Doubt Solver is currently disabled.", ephemeral=True)

    # ------------------------------------------------------------------
    # 4. SUNDAY NIGHT AI PERFORMANCE AUDIT LOOP
    # ------------------------------------------------------------------
    @tasks.loop(minutes=30)
    async def weekly_audit_loop(self):
        """Weekly audit loop, runs once a week after Sunday 10 PM IST."""
        await self.bot.wait_until_ready()
        try:
            now_ist = get_ist_now()
            
            # Find the most recent Sunday
            days_since_sunday = (now_ist.weekday() + 1) % 7
            prev_sunday_date = now_ist.date() - datetime.timedelta(days=days_since_sunday)
            prev_sunday_10pm = datetime.datetime.combine(prev_sunday_date, datetime.time(22, 0), tzinfo=IST_TZ)
            
            if now_ist >= prev_sunday_10pm:
                data = await self.bot.load_data()
                meta = data.setdefault("meta", {})
                last_audit = meta.get("last_weekly_ai_audit")
                
                if last_audit != prev_sunday_date.isoformat():
                    logging.info(f"[AI AUDIT] Commencing weekly audits for {prev_sunday_date.isoformat()}...")
                    await self._run_weekly_audits(data)
                    
                    async with self.bot.db_write_lock:
                        data = await self.bot.load_data()
                        data.setdefault("meta", {})["last_weekly_ai_audit"] = prev_sunday_date.isoformat()
                        await self.bot.save_data(data)
        except Exception as e:
            logging.error(f"[AI AUDIT] Error in loop: {e}", exc_info=True)

    @weekly_audit_loop.before_loop
    async def before_weekly_audit(self):
        await self.bot.wait_until_ready()

    async def _run_weekly_audits(self, data: dict):
        users = data.get("users", {})
        for uid_str, udata in users.items():
            try:
                user_id = int(uid_str)
                user = self.bot.get_user(user_id)
                if not user:
                    user = await self.bot.fetch_user(user_id)
                if not user or user.bot:
                    continue

                # Gather user metrics
                weekly_hours = udata.get("total_seconds_weekly", 0) / 3600
                alltime_hours = udata.get("total_seconds_alltime", 0) / 3600
                doubt_hours = udata.get("total_seconds_doubt", 0) / 3600
                streak = udata.get("current_streak_days", 0)
                
                # Subject Tag breakdown
                subj_hours = udata.get("subject_hours") or {}
                subjects_str = ", ".join(f"{sub}: {round(sec/3600, 1)}h" for sub, sec in subj_hours.items())
                
                # PYQs solved
                pyqs = udata.get("pyq_history") or []
                weekly_pyq_count = 0
                weekly_pyq_correct = 0
                
                # Filter PYQs from last 7 days
                seven_days_ago = (get_ist_date() - datetime.timedelta(days=7)).isoformat()
                for entry in pyqs:
                    if entry.get("date", "") >= seven_days_ago:
                        weekly_pyq_count += entry.get("solved", 0)
                        weekly_pyq_correct += entry.get("correct", 0)

                accuracy = int((weekly_pyq_correct / weekly_pyq_count) * 100) if weekly_pyq_count > 0 else 0

                audit_report = (
                    f"## 📊 Weekly Study Report Card\n\n"
                    f"Here is your study performance breakdown for the past 7 days:\n\n"
                    f"• ⏱️ **Weekly Study Time:** {weekly_hours:.1f} hours\n"
                    f"• 🏫 **All-Time Study:** {alltime_hours:.1f} hours\n"
                    f"• 📚 **Subject Hours:** {subjects_str if subjects_str else 'None'}\n"
                    f"• 📝 **PYQs Solved:** {weekly_pyq_count} questions with **{accuracy}% accuracy**\n"
                    f"• 🔥 **Active Streak:** {streak} days\n"
                    f"• 🧠 **Doubt Clearing:** {doubt_hours:.1f} hours\n\n"
                    f"*Keep pushing, review your weak chapters, and maximize your hours next week!*"
                )

                embed = discord.Embed(
                    title="📊 WEEKLY PERFORMANCE REPORT CARD",
                    description=audit_report,
                    color=UIColors.BRAND_PRIMARY,
                    timestamp=datetime.datetime.now(datetime.UTC)
                )
                embed.set_footer(text="Consistency builds rank. Keep grinding.")
                
                await user.send(embed=embed)
                logging.info(f"[WEEKLY REPORT] Sent report card to {user.display_name}")

            except discord.Forbidden:
                logging.warning(f"[WEEKLY REPORT] Cannot DM user {uid_str} (DMs disabled)")
            except Exception as e:
                logging.error(f"[WEEKLY REPORT] Error sending report card to user {uid_str}: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(JEEPrepCog(bot))
