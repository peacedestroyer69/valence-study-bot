# ============================================================
# PUZZLE OF THE DAY & WEEKLY MEGA COG — YPT Study Bot
# ============================================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
import logging
import random
import os

from utils import (
    get_ist_now, get_ist_date, IST_TZ,
    PUZZLE_CHANNEL_ID, GENERAL_CHANNEL_ID, VALENCE_ID, UJJWAL_ID, STUDY_CHANNELS,
    DAILY_GOAL_SECONDS
)
from cogs.gemini_brain import generate_puzzle, _LOGIC_VERIFICATION_PUZZLES

PUZZLE_SOLVED_ROLE_ID = int(os.getenv("PUZZLE_SOLVED_ROLE_ID", "0"))
SERVER_INVITE_LINK = os.getenv("SERVER_INVITE_LINK", "")

# Puzzle topic rotation: cycles through these each day
PUZZLE_TOPICS = ["jee", "logic", "jee", "mixed", "logic", "jee", "mixed"]

# How many archived puzzles must be solved to re-enter after kick
VERIFY_PUZZLES_REQUIRED = 3
# Hours between re-verify attempts after failure
VERIFY_COOLDOWN_HOURS = 24


# ============================================================
# DAILY ANSWER BUTTON VIEW
# ============================================================

class PuzzleAnswerView(discord.ui.View):
    """Persistent view with A/B/C/D buttons for the daily puzzle."""

    def __init__(self, cog: "PuzzleCog"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _handle_answer(self, interaction: discord.Interaction, chosen: str):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        now_ist = get_ist_now()
        today_str = now_ist.date().isoformat()

        # --- Acquire lock briefly: load, check, save if correct ---
        async with self.cog.bot.db_write_lock:
            data = await self.cog.bot.load_data()
            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            today_puzzle = puzzle_data.get(today_str)

            if not today_puzzle:
                _reply = ("no_puzzle", None, None)
            elif uid in today_puzzle.get("solved_users", []):
                _reply = ("already_solved", None, None)
            else:
                correct_answer = today_puzzle.get("answer", "A")
                explanation = today_puzzle.get("explanation", "")
                options = today_puzzle.get("options", {})

                if chosen == correct_answer:
                    if "solved_users" not in today_puzzle:
                        today_puzzle["solved_users"] = []
                    today_puzzle["solved_users"].append(uid)
                    data["meta"]["puzzle_of_day"][today_str] = today_puzzle
                    await self.cog.bot.save_data(data)
                    _reply = ("correct", explanation, None)
                else:
                    _reply = ("wrong", None, options)
        # --- Lock released ---

        if _reply[0] == "no_puzzle":
            await interaction.followup.send("❌ No puzzle found for today. Check back later!", ephemeral=True)
            return

        if _reply[0] == "already_solved":
            await interaction.followup.send(
                "✅ You already solved today's puzzle! Come back tomorrow for a new one.",
                ephemeral=True,
            )
            return

        if _reply[0] == "correct":
            explanation = _reply[1]
            # Award solved role
            if PUZZLE_SOLVED_ROLE_ID:
                try:
                    guild = interaction.guild or (self.cog.bot.guilds[0] if self.cog.bot.guilds else None)
                    if guild:
                        member = guild.get_member(interaction.user.id)
                        if not member:
                            member = await guild.fetch_member(interaction.user.id)
                        if member:
                            role = guild.get_role(PUZZLE_SOLVED_ROLE_ID)
                            if role:
                                await member.add_roles(role, reason="Puzzle of the Day solved")
                except Exception as e:
                    logging.warning(f"[PUZZLE] Could not add solved role: {e}")

            embed = discord.Embed(
                title="🎉 Correct! Well Done!",
                description=f"You answered **{chosen}** — that's right!\n\n📖 **Explanation:**\n{explanation}",
                color=0x57F287,
            )
            embed.set_footer(text=f"YPT Study Bot • Puzzle of the Day • {today_str}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logging.info(f"[PUZZLE] {interaction.user.display_name} solved today's puzzle")
            return

        # Wrong answer
        options = _reply[2]
        chosen_text = options.get(chosen, "")
        embed = discord.Embed(
            title=f"❌ Wrong — You chose {chosen}",
            description=f"**You answered:** {chosen}. {chosen_text}\n\nThat's not right. Try again!\n\n💡 *Hint: Think step by step.*",
            color=0xED4245,
        )
        embed.set_footer(text="You have unlimited attempts. Try again!")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary, custom_id="puzzle_answer_A")
    async def answer_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary, custom_id="puzzle_answer_B")
    async def answer_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary, custom_id="puzzle_answer_C")
    async def answer_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary, custom_id="puzzle_answer_D")
    async def answer_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "D")


# ============================================================
# WEEKLY ANSWER BUTTON VIEW
# ============================================================

class WeeklyPuzzleAnswerView(discord.ui.View):
    """Persistent view with A/B/C/D buttons for the weekly mega puzzle."""

    def __init__(self, cog: "PuzzleCog"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _handle_answer(self, interaction: discord.Interaction, chosen: str):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)

        # --- Acquire lock briefly: load, check, save ---
        async with self.cog.bot.db_write_lock:
            data = await self.cog.bot.load_data()
            weekly_puzzle = data.setdefault("meta", {}).setdefault("weekly_puzzle", {}).setdefault("active", {})

            if not weekly_puzzle.get("question") or weekly_puzzle.get("question") == "Generating...":
                _reply = ("no_puzzle", None, None)
            elif uid in weekly_puzzle.setdefault("solvers", {}):
                _reply = ("already_solved", None, None)
            else:
                solvers = weekly_puzzle["solvers"]
                attempts = weekly_puzzle.setdefault("attempts", {})
                correct_answer = weekly_puzzle.get("answer", "A")
                explanation = weekly_puzzle.get("explanation", "")
                options = weekly_puzzle.get("options", {})
                now_ts = datetime.datetime.now(datetime.UTC).timestamp()

                if chosen == correct_answer:
                    solvers[uid] = now_ts
                    
                    # Increment weekly solve count in user's statistics
                    udata = data.setdefault("users", {}).setdefault(uid, {})
                    udata["weekly_puzzles_solved"] = udata.get("weekly_puzzles_solved", 0) + 1
                    
                    await self.cog.bot.save_data(data)
                    _reply = ("correct", explanation, None)
                else:
                    # Incorrect attempt path
                    user_attempts = attempts.setdefault(uid, {"count": 0, "incorrect": [], "last_attempt_at": 0})
                    user_attempts["count"] += 1
                    if chosen not in user_attempts["incorrect"]:
                        user_attempts["incorrect"].append(chosen)
                    user_attempts["last_attempt_at"] = now_ts
                    await self.cog.bot.save_data(data)
                    _reply = ("wrong", None, options)
        # --- Lock released ---

        if _reply[0] == "no_puzzle":
            await interaction.followup.send("❌ No weekly puzzle active right now. Check back later!", ephemeral=True)
            return

        if _reply[0] == "already_solved":
            await interaction.followup.send(
                "✅ You already solved this week's mega puzzle! Outstanding work.",
                ephemeral=True,
            )
            return

        if _reply[0] == "correct":
            explanation = _reply[1]
            embed = discord.Embed(
                title="🧠 Outstanding! Weekly Mega Puzzle Solved!",
                description=f"You answered **{chosen}** — that's correct!\n\n📖 **Explanation:**\n{explanation}",
                color=0x2ECC71,
            )
            embed.set_footer(text="YPT Study Bot • Weekly Mega Puzzle • solved")
            await interaction.followup.send(embed=embed, ephemeral=True)
            logging.info(f"[PUZZLE] {interaction.user.display_name} solved the weekly mega puzzle")
            return

        if _reply[0] == "wrong":
            options = _reply[2]
            chosen_text = options.get(chosen, "")
            embed = discord.Embed(
                title=f"❌ Wrong — You chose {chosen}",
                description=f"**You answered:** {chosen}. {chosen_text}\n\nThat's not right. Try again!\n\n💡 *Hint: Think step by step.*",
                color=0xED4245,
            )
            embed.set_footer(text="You have unlimited attempts. Try again!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    @discord.ui.button(label="A", style=discord.ButtonStyle.success, custom_id="weekly_puzzle_answer_A")
    async def answer_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.success, custom_id="weekly_puzzle_answer_B")
    async def answer_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.success, custom_id="weekly_puzzle_answer_C")
    async def answer_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.success, custom_id="weekly_puzzle_answer_D")
    async def answer_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_answer(interaction, "D")


# ============================================================
# VERIFY BUTTON VIEW (for re-entry after kick)
# ============================================================

class VerifyPuzzleView(discord.ui.View):
    """Temporary view for verification puzzle answers (sent via DM)."""

    def __init__(self, correct_answer: str, explanation: str, on_answer):
        super().__init__(timeout=300)
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.on_answer = on_answer

    async def _handle(self, interaction: discord.Interaction, chosen: str):
        await interaction.response.defer()
        is_correct = chosen == self.correct_answer
        self.stop()
        await self.on_answer(interaction, is_correct, chosen, self.correct_answer, self.explanation)

    @discord.ui.button(label="A", style=discord.ButtonStyle.secondary, custom_id="verify_a")
    async def va(self, i, b): await self._handle(i, "A")

    @discord.ui.button(label="B", style=discord.ButtonStyle.secondary, custom_id="verify_b")
    async def vb(self, i, b): await self._handle(i, "B")

    @discord.ui.button(label="C", style=discord.ButtonStyle.secondary, custom_id="verify_c")
    async def vc(self, i, b): await self._handle(i, "C")

    @discord.ui.button(label="D", style=discord.ButtonStyle.secondary, custom_id="verify_d")
    async def vd(self, i, b): await self._handle(i, "D")


# ============================================================
# PUZZLE COG
# ============================================================

class PuzzleCog(commands.Cog):
    """Puzzle of the Day and Weekly Mega Puzzle system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._today_puzzle_posted: str = ""
        self._midnight_kick_done: str = ""
        self._morning_wakeup_done: str = ""
        self._active_verifications = set()

        self.puzzle_loop.start()
        self.weekly_puzzle_loop.start()
        self.midnight_kick_loop.start()
        self.morning_wakeup_loop.start()

        # Register persistent views
        self.bot.add_view(PuzzleAnswerView(self))
        self.bot.add_view(WeeklyPuzzleAnswerView(self))
        asyncio.create_task(self.startup_check())

    def get_expected_weekly_start_date(self, now_ist: datetime.datetime) -> datetime.date:
        """Returns the Monday start date of the active weekly puzzle."""
        weekday = now_ist.weekday()
        if weekday == 0:  # Monday
            if now_ist.hour < 8:
                return now_ist.date() - datetime.timedelta(days=7)
            else:
                return now_ist.date()
        else:
            return now_ist.date() - datetime.timedelta(days=weekday)

    async def startup_check(self):
        """Startup catch-up logic to post missed daily or weekly puzzles."""
        await self.bot.wait_until_ready()
        now_ist = get_ist_now()

        # 1. Daily puzzle check
        if now_ist.hour >= 8:
            today_str = now_ist.date().isoformat()
            data = await self.bot.load_data()
            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            loop_state = data.get("meta", {}).get("puzzle_loop_state", {})
            need_daily_post = today_str not in puzzle_data or loop_state.get("posted_date") != today_str
            
            if need_daily_post:
                logging.info("[PUZZLE] Startup check: Today's daily puzzle is missing. Posting now...")
                await self._post_daily_puzzle(now_ist, force=True)

        # 2. Weekly puzzle check
        expected_start = self.get_expected_weekly_start_date(now_ist)
        expected_start_str = expected_start.isoformat()
        data = await self.bot.load_data()
        weekly_data = data.get("meta", {}).get("weekly_puzzle", {})
        active = weekly_data.get("active", {})
        need_weekly_post = active.get("week_start_date") != expected_start_str

        if need_weekly_post:
            logging.info(f"[PUZZLE] Startup check: Weekly puzzle for week of {expected_start_str} is missing. Posting now...")
            await self._post_weekly_puzzle(now_ist, force=True)

    def cog_unload(self):
        self.puzzle_loop.cancel()
        self.weekly_puzzle_loop.cancel()
        self.midnight_kick_loop.cancel()
        self.morning_wakeup_loop.cancel()

    # ------------------------------------------------------------------
    # TASK 1: POST DAILY PUZZLE AT 8 AM IST
    # ------------------------------------------------------------------

    async def _post_daily_puzzle(self, now_ist, force=False):
        today_str = now_ist.date().isoformat()

        try:
            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})

                if not force and (self._today_puzzle_posted == today_str or loop_state.get("posted_date") == today_str):
                    return False

                self._today_puzzle_posted = today_str
                loop_state["posted_date"] = today_str
                await self.bot.save_data(data)

            logging.info("[PUZZLE] Generating daily puzzle via brainstorm pipeline...")
            topic = PUZZLE_TOPICS[now_ist.weekday() % len(PUZZLE_TOPICS)]
            puzzle = await generate_puzzle(topic=topic, is_weekly=False)

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)

            opts = puzzle["options"]
            options_str = "\n".join(f"**{k}.** {v}" for k, v in opts.items())

            embed = discord.Embed(
                title=f"\U0001f9e9 Puzzle of the Day \u2014 {now_ist.strftime('%d %b %Y')}",
                description=f"**{puzzle['question']}**\n\n{options_str}",
                color=0x5865F2,
            )
            embed.add_field(
                name="\U0001f4cb Rules",
                value=(
                    "\u2022 Click A/B/C/D below with your answer\n"
                    "\u2022 Unlimited attempts \u2014 but solve it by **midnight IST**\n"
                    "\u2022 **Fail to solve \u2192 you get kicked from the server**\n"
                    "\u2022 To rejoin after kick: `/verify` and solve 3 archived puzzles"
                ),
                inline=False,
            )
            embed.set_footer(text="YPT Study Bot \u2022 Puzzle of the Day \u2022 Deadline: 11:59 PM IST")

            alert_msg = await channel.send(
                "\U0001f9e9 **Daily Puzzle is in your DMs!** Check your DMs and solve it before midnight or get kicked."
            )

            dm_count = 0
            view = PuzzleAnswerView(self)
            for member in channel.guild.members:
                if member.bot:
                    continue
                try:
                    await member.send(embed=embed, view=view)
                    dm_count += 1
                    await asyncio.sleep(0.5)
                except discord.Forbidden:
                    pass
                except Exception as dm_err:
                    logging.warning(f"[PUZZLE] Could not DM puzzle to {member.display_name}: {dm_err}")

            logging.info(f"[PUZZLE] DMed today's puzzle to {dm_count} members")

            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                data.setdefault("meta", {}).setdefault("puzzle_of_day", {})

                # Prune puzzles older than 30 days
                cutoff = (now_ist.date() - datetime.timedelta(days=30)).isoformat()
                data["meta"]["puzzle_of_day"] = {
                    k: v for k, v in data["meta"]["puzzle_of_day"].items() if k >= cutoff
                }

                data["meta"]["puzzle_of_day"][today_str] = {
                    "question": puzzle["question"],
                    "options": puzzle["options"],
                    "answer": puzzle["answer"],
                    "explanation": puzzle["explanation"],
                    "solved_users": [],
                    "message_id": alert_msg.id,
                }
                data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})["posted_date"] = today_str
                await self.bot.save_data(data)

            logging.info(f"[PUZZLE] Posted daily puzzle for {today_str}")
            return True

        except Exception as e:
            logging.error(f"[PUZZLE] _post_daily_puzzle failed: {e}", exc_info=True)
            return False

    @tasks.loop(minutes=5)
    async def puzzle_loop(self):
        try:
            now_ist = get_ist_now()
            if now_ist.hour != 8 or now_ist.minute >= 30:
                return
            await self._post_daily_puzzle(now_ist, force=False)
        except Exception as e:
            logging.error(f"[PUZZLE] Error in puzzle_loop: {e}", exc_info=True)

    @puzzle_loop.before_loop
    async def before_puzzle(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # TASK 2: POST WEEKLY MEGA PUZZLE (Monday 8 AM IST)
    # ------------------------------------------------------------------

    async def _post_weekly_puzzle(self, now_ist, force=False):
        expected_start = self.get_expected_weekly_start_date(now_ist)
        expected_start_str = expected_start.isoformat()

        try:
            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                weekly_data = data.setdefault("meta", {}).setdefault("weekly_puzzle", {})
                active = weekly_data.setdefault("active", {})

                if not force and active.get("week_start_date") == expected_start_str:
                    return False

                # Archive existing active puzzle to history
                old_start = active.get("week_start_date")
                if old_start:
                    history = weekly_data.setdefault("history", {})
                    history[old_start] = {
                        "question": active.get("question"),
                        "options": active.get("options"),
                        "answer": active.get("answer"),
                        "explanation": active.get("explanation"),
                        "solved_users": active.get("solved_users", []),
                    }

                # Reset active state before generating (locks state)
                active["week_start_date"] = expected_start_str
                active["question"] = "Generating..."
                active["options"] = {}
                active["answer"] = ""
                active["explanation"] = ""
                active["solvers"] = {}
                active["attempts"] = {}
                active["posted_at"] = datetime.datetime.now(datetime.UTC).timestamp()
                await self.bot.save_data(data)

            logging.info(f"[PUZZLE] Generating weekly mega puzzle for week starting {expected_start_str}...")
            puzzle = await generate_puzzle(topic="mixed", is_weekly=True)

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)

            opts = puzzle["options"]
            options_str = "\n".join(f"**{k}.** {v}" for k, v in opts.items())

            embed = discord.Embed(
                title=f"🧠 Weekly Mega Puzzle — Week of {expected_start.strftime('%d %b %Y')}",
                description=f"**{puzzle['question']}**\n\n{options_str}",
                color=0x9B59B6,
            )
            embed.add_field(
                name="📋 Rules",
                value=(
                    "• This is an extremely difficult conceptual challenge\n"
                    "• Solve it using `/weekly_puzzle` or by clicking the buttons below\n"
                    "• No time limit — stays active for the entire week\n"
                    "• Earn reputation and prove your intellectual dominance!"
                ),
                inline=False,
            )
            embed.set_footer(text="YPT Study Bot • Weekly Mega Puzzle")

            view = WeeklyPuzzleAnswerView(self)
            msg = await channel.send(
                content="🧠 **A new Weekly Mega Puzzle has been posted!**",
                embed=embed,
                view=view
            )

            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                weekly_data = data.setdefault("meta", {}).setdefault("weekly_puzzle", {})
                active = weekly_data.setdefault("active", {})

                active["question"] = puzzle["question"]
                active["options"] = puzzle["options"]
                active["answer"] = puzzle["answer"]
                active["explanation"] = puzzle["explanation"]
                active["solvers"] = {}
                active["attempts"] = {}
                active["posted_at"] = datetime.datetime.now(datetime.UTC).timestamp()
                active["message_id"] = msg.id
                active["week_start_date"] = expected_start_str

                await self.bot.save_data(data)

            logging.info(f"[PUZZLE] Posted weekly puzzle for {expected_start_str}")
            return True

        except Exception as e:
            logging.error(f"[PUZZLE] _post_weekly_puzzle failed: {e}", exc_info=True)
            return False

    async def _publish_weekly_leaderboard(self, now_ist, force=False):
        """Generates and posts the weekly mega puzzle shoutout & leaderboard."""
        try:
            expected_start = self.get_expected_weekly_start_date(now_ist)
            expected_start_str = expected_start.isoformat()

            if not force:
                async with self.bot.db_write_lock:
                    data = await self.bot.load_data()
                    weekly_data = data.setdefault("meta", {}).setdefault("weekly_puzzle", {})
                    if weekly_data.get("last_leaderboard_week") == expected_start_str:
                        return
                    weekly_data["last_leaderboard_week"] = expected_start_str
                    await self.bot.save_data(data)

            data = await self.bot.load_data()
            weekly_puzzle = data.get("meta", {}).get("weekly_puzzle", {}).get("active", {})
            
            if not weekly_puzzle or not weekly_puzzle.get("question") or weekly_puzzle.get("question") == "Generating...":
                return

            solvers = weekly_puzzle.get("solvers", {})
            attempts = weekly_puzzle.get("attempts", {})
            posted_at = weekly_puzzle.get("posted_at", 0)
            
            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)
            if not channel:
                return

            embed = discord.Embed(
                title="🏆 WEEKLY MEGA PUZZLE FINALE & LEADERBOARD",
                description="Here is the breakdown of who tackled this week's extreme conceptual challenge!",
                color=0x9B59B6,
                timestamp=datetime.datetime.now(datetime.UTC)
            )

            # 1. SHOUTOUTS (Solvers sorted by solve time)
            solver_list = []
            for uid_str, solved_at in solvers.items():
                try:
                    user_id = int(uid_str)
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                except Exception:
                    user = None
                
                user_name = user.mention if user else f"User {uid_str}"
                time_taken = max(0.0, solved_at - posted_at)
                
                days = int(time_taken // 86400)
                hours = int((time_taken % 86400) // 3600)
                minutes = int((time_taken % 3600) // 60)
                
                time_str = ""
                if days > 0:
                    time_str += f"{days}d "
                if hours > 0 or days > 0:
                    time_str += f"{hours}h "
                time_str += f"{minutes}m"
                
                fail_count = attempts.get(uid_str, {}).get("count", 0)
                solver_list.append((solved_at, user_name, time_str, fail_count))
            
            solver_list.sort(key=lambda x: x[0])

            if solver_list:
                shoutout_lines = []
                for idx, (_, name, t_str, fails) in enumerate(solver_list, 1):
                    medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else "✨"
                    fail_str = f" ({fails} wrong attempts)" if fails > 0 else " (first try!)"
                    shoutout_lines.append(f"{medal} {name} — solved in **{t_str}**{fail_str}")
                
                embed.add_field(
                    name="🎉 The Solvers (Shoutout!)",
                    value="\n".join(shoutout_lines),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎉 The Solvers (Shoutout!)",
                    value="*Nobody managed to crack the puzzle this week. True mega difficulty!*",
                    inline=False
                )

            # 2. INCORRECT ATTEMPTS
            incorrect_list = []
            for uid_str, att_data in attempts.items():
                if uid_str in solvers:
                    continue
                
                try:
                    user_id = int(uid_str)
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                except Exception:
                    user = None
                
                user_name = user.mention if user else f"User {uid_str}"
                incorrect_choices = ", ".join(att_data.get("incorrect", []))
                incorrect_list.append(f"• {user_name} — {att_data['count']} attempts (guessed: {incorrect_choices})")

            if incorrect_list:
                embed.add_field(
                    name="❌ Valorous Attempts (Incorrect)",
                    value="\n".join(incorrect_list),
                    inline=False
                )

            # 3. STATS
            total_unique_attempts = len(attempts) + len(solvers)
            success_rate = int((len(solvers) / total_unique_attempts) * 100) if total_unique_attempts > 0 else 0
            
            embed.add_field(
                name="📊 Puzzle Stats",
                value=(
                    f"• **Total Solvers:** {len(solvers)}\n"
                    f"• **Total Attempting Users:** {total_unique_attempts}\n"
                    f"• **Success Rate:** {success_rate}%\n"
                    f"• **Solution Answer:** **{weekly_puzzle.get('answer', 'N/A')}**\n"
                    f"• **Explanation:** {weekly_puzzle.get('explanation', 'N/A')}"
                ),
                inline=False
            )

            embed.set_footer(text="Next Weekly Mega Puzzle drops in 10 minutes!")
            await channel.send(embed=embed)
            logging.info("[WEEKLY LEADERBOARD] Published weekly mega puzzle leaderboard")

        except Exception as e:
            logging.error(f"[WEEKLY LEADERBOARD] Error publishing leaderboard: {e}", exc_info=True)

    @tasks.loop(minutes=5)
    async def weekly_puzzle_loop(self):
        try:
            now_ist = get_ist_now()
            # Trigger leaderboard on Monday 7:50 AM IST - 7:55 AM IST
            if now_ist.weekday() == 0 and now_ist.hour == 7 and 50 <= now_ist.minute < 55:
                await self._publish_weekly_leaderboard(now_ist)
                
            # Trigger puzzle on Monday 8:00 AM IST - 8:05 AM IST
            if now_ist.weekday() == 0 and now_ist.hour == 8 and now_ist.minute < 5:
                await self._post_weekly_puzzle(now_ist, force=False)
        except Exception as e:
            logging.error(f"[PUZZLE] Error in weekly_puzzle_loop: {e}", exc_info=True)

    @weekly_puzzle_loop.before_loop
    async def before_weekly_puzzle(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # TASK 3: MIDNIGHT KICK (11:55 PM IST)
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def midnight_kick_loop(self):
        try:
            now_ist = get_ist_now()

            # If after midnight, kick for the day that just ended (yesterday)
            if now_ist.hour == 0:
                kick_date = now_ist.date() - datetime.timedelta(days=1)
            else:
                kick_date = now_ist.date()
            kick_date_str = kick_date.isoformat()

            is_in_window = (now_ist.hour == 23 and now_ist.minute >= 50) or (now_ist.hour == 0 and now_ist.minute < 15)
            if not is_in_window:
                return

            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
                if self._midnight_kick_done == kick_date_str or loop_state.get("kick_date") == kick_date_str:
                    return

                self._midnight_kick_done = kick_date_str
                loop_state["kick_date"] = kick_date_str
                await self.bot.save_data(data)

            logging.info(f"[PUZZLE] Running midnight puzzle kick check for {kick_date_str}...")

            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            today_puzzle = puzzle_data.get(kick_date_str)

            if not today_puzzle:
                logging.warning(f"[PUZZLE] No puzzle found for {kick_date_str} — skipping kick check")
                return

            solved_users = set(today_puzzle.get("solved_users", []))

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)

            guild = channel.guild
            kicked_count = 0

            for member in guild.members:
                if member.bot:
                    continue
                uid = str(member.id)
                if uid in solved_users:
                    continue

                if member.guild_permissions.kick_members:
                    continue

                udata = data.get("users", {}).get(uid, {})
                hours_today = udata.get("total_seconds_today", 0) / 3600
                hours_alltime = udata.get("total_seconds_alltime", 0) / 3600
                streak = udata.get("current_streak_days", 0)

                async with self.bot.db_write_lock:
                    fresh_data = await self.bot.load_data()
                    fresh_udata = fresh_data.setdefault("users", {}).setdefault(uid, {})
                    fresh_udata["puzzle_kicks"] = fresh_udata.get("puzzle_kicks", 0) + 1
                    await self.bot.save_data(fresh_data)

                from cogs.gemini_brain import personalized_kick_msg
                try:
                    ai_kick = await personalized_kick_msg(
                        username=member.display_name,
                        hours_today=hours_today,
                        hours_alltime=hours_alltime,
                        streak=streak,
                        puzzle_solved=False,
                        missed_days=udata.get("consecutive_missed_days", 0),
                    )
                except Exception as ai_err:
                    logging.warning(f"[PUZZLE] Gemini kick message generation failed for {member.display_name}: {ai_err}")
                    ai_kick = "You failed to solve the daily puzzle. Server standards require active learning. Solve your tasks or remain kicked."
                
                invite_line = f"\n\n\U0001f517 **Rejoin:** {SERVER_INVITE_LINK}" if SERVER_INVITE_LINK else ""
                kick_msg = (
                    f"# \U0001f528 KICKED FROM YPT STUDY SERVER\n\n"
                    f"{ai_kick}\n\n"
                    f"**To rejoin:** Use `/verify` and solve {VERIFY_PUZZLES_REQUIRED} archived puzzles."
                    f"{invite_line}"
                )

                try:
                    await member.send(kick_msg)
                except discord.Forbidden:
                    pass

                try:
                    await member.kick(reason=f"Did not solve Puzzle of the Day ({kick_date_str})")
                    kicked_count += 1
                    logging.info(f"[PUZZLE] Kicked {member.display_name} for unsolved puzzle")
                except discord.Forbidden:
                    logging.warning(f"[PUZZLE] Cannot kick {member.display_name} (no permission)")
                except Exception as e:
                    logging.error(f"[PUZZLE] Error kicking {member.display_name}: {e}")

                await asyncio.sleep(1)

            if kicked_count > 0:
                await channel.send(
                    f"🔨 **Midnight Reckoning:** {kicked_count} member{'s' if kicked_count > 1 else ''} "
                    f"got kicked for not solving today's puzzle. The bar is set. Step up or step out."
                )
            else:
                await channel.send(
                    "✅ **Everyone solved today's puzzle!** Impressive. New puzzle drops at 8 AM tomorrow."
                )

            logging.info(f"[PUZZLE] Midnight kick done — kicked {kicked_count} members")

        except Exception as e:
            logging.error(f"[PUZZLE] Error in midnight_kick_loop: {e}", exc_info=True)

    @midnight_kick_loop.before_loop
    async def before_midnight(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # TASK 4: 6 AM WAKE-UP DM
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def morning_wakeup_loop(self):
        try:
            now_ist = get_ist_now()
            today_str = now_ist.date().isoformat()

            if now_ist.hour != 6 or now_ist.minute >= 30:
                return

            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
                if self._morning_wakeup_done == today_str or loop_state.get("wakeup_date") == today_str:
                    return

                self._morning_wakeup_done = today_str
                loop_state["wakeup_date"] = today_str
                await self.bot.save_data(data)

            logging.info("[PUZZLE] Sending 6 AM wake-up DMs...")

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                logging.error("[PUZZLE] Cannot find puzzle channel for morning wakeup")
                return

            guild = channel.guild
            yesterday_str = (now_ist.date() - datetime.timedelta(days=1)).isoformat()

            from cogs.gemini_brain import personalized_wakeup_msg

            for member in guild.members:
                if member.bot:
                    continue

                uid = str(member.id)
                udata = data.get("users", {}).get(uid, {})
                yesterday_secs = udata.get("daily_history", {}).get(yesterday_str, 0)
                yesterday_hours = yesterday_secs / 3600
                streak = udata.get("current_streak_days", 0)
                goal_hours = udata.get("daily_goal_seconds", DAILY_GOAL_SECONDS) / 3600

                msg_text = await personalized_wakeup_msg(
                    username=member.display_name,
                    yesterday_hours=yesterday_hours,
                    streak=streak,
                    goal_hours=goal_hours,
                )

                embed = discord.Embed(
                    title="⏰ 6 AM — New Day, New Grind",
                    description=msg_text,
                    color=0xFEE75C,
                )
                embed.add_field(
                    name="🧩 Don't Forget",
                    value="Today's puzzle drops at **8 AM**. Solve it before midnight or get kicked.",
                    inline=False,
                )
                embed.set_footer(text=f"YPT Study Bot • {now_ist.strftime('%d %b %Y')} • Rise and Grind")

                try:
                    await member.send(embed=embed)
                    await asyncio.sleep(0.5)
                except discord.Forbidden:
                    pass
                except Exception as e:
                    logging.warning(f"[PUZZLE] 6AM DM failed for {member.display_name}: {e}")

            logging.info("[PUZZLE] 6 AM wake-up DMs sent")

        except Exception as e:
            logging.error(f"[PUZZLE] Error in morning_wakeup_loop: {e}", exc_info=True)

    @morning_wakeup_loop.before_loop
    async def before_wakeup(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # SLASH COMMAND: /verify (re-entry after kick)
    # ------------------------------------------------------------------

    @app_commands.command(name="verify", description="Solve 3 puzzles to rejoin the server after being kicked")
    async def verify_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id in self._active_verifications:
            await interaction.followup.send("⚠️ You already have an active verification session in progress!", ephemeral=True)
            return

        uid = str(interaction.user.id)
        data = await self.bot.load_data()
        udata = data.get("users", {}).get(uid, {})

        now_ist = get_ist_now()
        last_attempt_str = udata.get("puzzle_verify_last")
        if last_attempt_str:
            try:
                last_attempt = datetime.datetime.fromisoformat(last_attempt_str)
                if last_attempt.tzinfo is None:
                    last_attempt = last_attempt.replace(tzinfo=IST_TZ)
                elapsed_h = (now_ist - last_attempt).total_seconds() / 3600
                if elapsed_h < VERIFY_COOLDOWN_HOURS and udata.get("puzzle_verify_failed", False):
                    remaining_h = VERIFY_COOLDOWN_HOURS - elapsed_h
                    await interaction.followup.send(
                        f"⏰ You failed your last verification attempt. Try again in **{remaining_h:.1f} hours**.",
                        ephemeral=True,
                    )
                    return
            except Exception as e:
                logging.warning(f"[PUZZLE] Failed parsing last verification attempt date: {e}")

        # Send the first status message to the user's DM to test if DMs are open
        try:
            status_msg = await interaction.user.send(
                f"🔐 **Verification Status: 0/{VERIFY_PUZZLES_REQUIRED} solved.**\n"
                f"Generating Logic Puzzle 1/{VERIFY_PUZZLES_REQUIRED}... Please wait (taking up to 30 seconds)."
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't DM you. Please enable DMs from server members and try again.",
                ephemeral=True,
            )
            return

        # Succeeded in sending DM, now we start the active verification session
        self._active_verifications.add(interaction.user.id)
        try:
            await interaction.followup.send(
                f"🔐 **Verification started.** Solve {VERIFY_PUZZLES_REQUIRED} logic puzzles to rejoin.\n"
                f"I will send them one at a time via DM. Good luck!",
                ephemeral=True,
            )

            score = 0
            for i in range(1, VERIFY_PUZZLES_REQUIRED + 1):
                if i > 1:
                    status_msg = await interaction.user.send(
                        f"🔐 **Verification Status: {score}/{VERIFY_PUZZLES_REQUIRED} solved.**\n"
                        f"Generating Logic Puzzle {i}/{VERIFY_PUZZLES_REQUIRED}... Please wait (taking up to 30 seconds)."
                    )

                # Run generation with timeout
                try:
                    from cogs.gemini_brain import generate_logic_puzzle
                    puzzle = await asyncio.wait_for(generate_logic_puzzle(), timeout=60.0)
                except Exception as gen_err:
                    logging.warning(f"[VERIFY] AI Generation failed or timed out: {gen_err}. Using curated offline bank.")
                    puzzle = random.choice(_LOGIC_VERIFICATION_PUZZLES)

                options_str = "\n".join(f"**{k}** — {v}" for k, v in puzzle["options"].items())
                embed = discord.Embed(
                    title=f"🔐 Verification Puzzle {i}/{VERIFY_PUZZLES_REQUIRED}",
                    description=f"**{puzzle['question']}**\n\n{options_str}",
                    color=0x5865F2,
                )
                embed.set_footer(text=f"You have 5 minutes to answer. Puzzle {i} of {VERIFY_PUZZLES_REQUIRED}.")

                result_holder = {}

                async def on_answer(inter, is_correct, chosen, correct, explanation, holder=result_holder):
                    holder["correct"] = is_correct
                    holder["chosen"] = chosen
                    holder["answer"] = correct
                    holder["explanation"] = explanation
                    
                    embed_msg = inter.message.embeds[0]
                    embed_msg.description += f"\n\n**Your choice:** {chosen}"
                    await inter.edit_original_response(embed=embed_msg, view=None)

                view = VerifyPuzzleView(
                    correct_answer=puzzle["answer"],
                    explanation=puzzle.get("explanation", ""),
                    on_answer=on_answer,
                )

                try:
                    await status_msg.delete()
                except Exception as del_err:
                    logging.warning(f"[VERIFY] Failed to delete status message: {del_err}")

                await interaction.user.send(embed=embed, view=view)
                await view.wait()

                if not result_holder:
                    await interaction.user.send(
                        f"⏰ **Puzzle {i} timed out.** Verification failed. "
                        f"Wait {VERIFY_COOLDOWN_HOURS}h before trying again."
                    )
                    async with self.bot.db_write_lock:
                        fresh_data = await self.bot.load_data()
                        fresh_udata = fresh_data.setdefault("users", {}).setdefault(uid, {})
                        fresh_udata["puzzle_verify_failed"] = True
                        fresh_udata["puzzle_verify_last"] = now_ist.isoformat()
                        await self.bot.save_data(fresh_data)
                    return

                if result_holder.get("correct"):
                    score += 1
                    await interaction.user.send(
                        f"✅ **Correct!** {result_holder['explanation']}"
                    )
                else:
                    chosen = result_holder.get("chosen", "?")
                    correct = result_holder.get("answer", "?")
                    expl = result_holder.get("explanation", "")
                    await interaction.user.send(
                        f"❌ **Wrong!** You chose **{chosen}**, correct was **{correct}**.\n"
                        f"📖 {expl}\n\n"
                        f"Verification failed. You solved {score}/{VERIFY_PUZZLES_REQUIRED} puzzles.\n"
                        f"Wait {VERIFY_COOLDOWN_HOURS}h before trying again."
                    )
                    async with self.bot.db_write_lock:
                        fresh_data = await self.bot.load_data()
                        fresh_udata = fresh_data.setdefault("users", {}).setdefault(uid, {})
                        fresh_udata["puzzle_verify_failed"] = True
                        fresh_udata["puzzle_verify_last"] = now_ist.isoformat()
                        await self.bot.save_data(fresh_data)
                    return

                await asyncio.sleep(2)

            async with self.bot.db_write_lock:
                fresh_data = await self.bot.load_data()
                fresh_udata = fresh_data.setdefault("users", {}).setdefault(uid, {})
                fresh_udata["puzzle_verify_failed"] = False
                fresh_udata["puzzle_verify_last"] = now_ist.isoformat()
                await self.bot.save_data(fresh_data)

            try:
                guild = interaction.guild or (self.bot.guilds[0] if self.bot.guilds else None)
                if guild:
                    member = guild.get_member(interaction.user.id)
                    if not member:
                        member = await guild.fetch_member(interaction.user.id)
                    if member:
                        unverified_role = discord.utils.get(guild.roles, name="Unverified")
                        if unverified_role and unverified_role in member.roles:
                            await member.remove_roles(unverified_role)
                            logging.info(f"[PUZZLE] Removed Unverified role from {member.display_name}")
            except Exception as role_err:
                logging.warning(f"Could not remove Unverified role: {role_err}")

            invite_msg = f"\n\n🔗 **Rejoin link:** {SERVER_INVITE_LINK}" if SERVER_INVITE_LINK else "\n\nAsk a server admin to re-invite you."
            await interaction.user.send(
                f"🎉 **Verification Passed! {score}/{VERIFY_PUZZLES_REQUIRED} correct!**\n\n"
                f"You've proven you belong here. Welcome back.\n"
                f"Don't let this happen again — solve the daily puzzle every day.{invite_msg}"
            )
            logging.info(f"[PUZZLE] {interaction.user.display_name} passed verification ({score}/{VERIFY_PUZZLES_REQUIRED})")

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I couldn't DM you. Please enable DMs from server members and try again.",
                ephemeral=True,
            )
        except Exception as e:
            logging.error(f"[PUZZLE] Error in verify_command: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred during verification. Please contact a server admin.",
                ephemeral=True,
            )
        finally:
            self._active_verifications.discard(interaction.user.id)

    # ------------------------------------------------------------------
    # SLASH COMMAND: /puzzle_status (check today's puzzle stats)
    # ------------------------------------------------------------------

    @app_commands.command(name="puzzle_status", description="See who's solved today's puzzle")
    async def puzzle_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await self.bot.load_data()
        now_ist = get_ist_now()
        today_str = now_ist.date().isoformat()

        puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
        today_puzzle = puzzle_data.get(today_str)

        if not today_puzzle:
            await interaction.followup.send("❌ No puzzle posted yet today. Check back at 8 AM IST!", ephemeral=True)
            return

        solved_users = today_puzzle.get("solved_users", [])
        uid = str(interaction.user.id)
        you_solved = uid in solved_users

        channel = self.bot.get_channel(PUZZLE_CHANNEL_ID) or await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)
        guild = channel.guild if channel else interaction.guild
        total_members = len([m for m in guild.members if not m.bot]) if guild else "?"

        embed = discord.Embed(
            title=f"🧩 Daily Puzzle Status — {today_str}",
            description=f"**{'✅ You solved it!' if you_solved else '❌ You have NOT solved it yet — deadline is midnight IST!'}**",
            color=0x57F287 if you_solved else 0xFF0000,
        )
        embed.add_field(name="✅ Solved", value=f"{len(solved_users)} / {total_members} members", inline=True)
        embed.add_field(name="⏰ Deadline", value="11:59 PM IST", inline=True)
        embed.set_footer(text="YPT Study Bot • Fail to solve = kicked at midnight")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # SLASH COMMAND: /weekly_puzzle (view & solve active weekly puzzle)
    # ------------------------------------------------------------------

    @app_commands.command(name="weekly_puzzle", description="View and solve the active Weekly Mega Puzzle")
    async def weekly_puzzle_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await self.bot.load_data()

        weekly_data = data.get("meta", {}).get("weekly_puzzle", {})
        active = weekly_data.get("active", {})

        if not active or not active.get("question") or active.get("question") == "Generating...":
            await interaction.followup.send("❌ There is no active Weekly Mega Puzzle right now.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        solvers = active.get("solvers", {})
        already_solved = uid in solvers

        opts = active["options"]
        options_str = "\n".join(f"**{k}.** {v}" for k, v in opts.items())

        if already_solved:
            embed = discord.Embed(
                title="🧠 Weekly Mega Puzzle (Solved)",
                description=f"**{active['question']}**\n\n{options_str}\n\n✅ You solved this puzzle!\n\n📖 **Explanation:**\n{active.get('explanation')}",
                color=0x2ECC71,
            )
            embed.set_footer(text="YPT Study Bot • Weekly Mega Puzzle")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="🧠 Weekly Mega Puzzle",
                description=f"**{active['question']}**\n\n{options_str}",
                color=0x9B59B6,
            )
            embed.add_field(
                name="✏️ Solve",
                value="Choose one of the option buttons below to submit your answer.",
                inline=False,
            )
            embed.set_footer(text="YPT Study Bot • Weekly Mega Puzzle")
            view = WeeklyPuzzleAnswerView(self)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # ------------------------------------------------------------------
    # SLASH COMMANDS: ADMIN FORCE COMMANDS
    # ------------------------------------------------------------------

    @app_commands.command(name="post_puzzle_now", description="Force post today's daily puzzle instantly (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_puzzle_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        now_ist = get_ist_now()

        status_msg = await interaction.followup.send(
            "Generating puzzle via Gemini brainstorm pipeline...\n"
            "Stages: Brainstorm -> Refine (3 cycles) -> Verify x2 -> DM all members\n"
            "Allow up to 90 seconds.",
            ephemeral=True,
            wait=True,
        )

        async def _bg():
            try:
                success = await self._post_daily_puzzle(now_ist, force=True)
                if success:
                    await status_msg.edit(content=(
                        "Puzzle posted! Brainstormed candidates, selected/refined the best, "
                        "logic verified twice, and DMed to all members."
                    ))
                else:
                    await status_msg.edit(content=(
                        "Failed to post puzzle.\n"
                        "- Puzzle channel not found? Check PUZZLE_CHANNEL_ID env var\n"
                        "- Gemini pipeline error? Check bot logs for full traceback."
                    ))
            except Exception as err:
                logging.error(f"[PUZZLE] post_puzzle_now bg task error: {err}", exc_info=True)
                try:
                    await status_msg.edit(content=f"Error: {err}. See bot logs.")
                except Exception:
                    pass

        asyncio.create_task(_bg())

    @app_commands.command(name="post_weekly_puzzle_now", description="Force post/reset the Weekly Mega Puzzle instantly (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_weekly_puzzle_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        now_ist = get_ist_now()

        status_msg = await interaction.followup.send(
            "Generating weekly mega puzzle via Gemini brainstorm/refine pipeline...\n"
            "Stages: Brainstorm -> Refine (3 cycles) -> Verify x2 -> Post\n"
            "Allow up to 90 seconds.",
            ephemeral=True,
            wait=True,
        )

        async def _bg():
            try:
                success = await self._post_weekly_puzzle(now_ist, force=True)
                if success:
                    await status_msg.edit(content=(
                        "Weekly Mega Puzzle posted successfully! "
                        "Brainstormed, refined through 3 cycles, logic verified twice, and posted in channel."
                    ))
                else:
                    await status_msg.edit(content=(
                        "Failed to post Weekly Mega Puzzle.\n"
                        "- Channel not found? Check PUZZLE_CHANNEL_ID env var\n"
                        "- Gemini pipeline error? Check bot logs for full traceback."
                    ))
            except Exception as err:
                logging.error(f"[PUZZLE] post_weekly_puzzle_now bg task error: {err}", exc_info=True)
                try:
                    await status_msg.edit(content=f"Error: {err}. See bot logs.")
                except Exception:
                    pass

        asyncio.create_task(_bg())

    @app_commands.command(name="post_weekly_leaderboard_now", description="Force publish the current weekly puzzle leaderboard instantly (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_weekly_leaderboard_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        now_ist = get_ist_now()
        await self._publish_weekly_leaderboard(now_ist, force=True)
        await interaction.followup.send("Weekly leaderboard published!", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = PuzzleCog(bot)
    await bot.add_cog(cog)
    logging.info("[PUZZLE] Loaded Puzzle of the Day and Weekly Mega Extension")
