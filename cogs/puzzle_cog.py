# ============================================================
# PUZZLE OF THE DAY COG — YPT Study Bot
# ============================================================
# Features:
#   1. Daily puzzle posted at 8 AM IST in PUZZLE_CHANNEL_ID
#   2. All members get the SAME puzzle each day (Gemini-generated)
#   3. Interactive A/B/C/D buttons — unlimited attempts, DM feedback
#   4. Midnight check: anyone who didn't solve it gets KICKED
#   5. /verify command: kicked users must solve 3 archived puzzles to rejoin
#   6. Puzzle archive stored in bot data (last 30 days)
# ============================================================

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import datetime
import logging
import random
import os
from bot import get_ist_now, get_ist_date, IST_TZ

# Import Gemini brain (falls back gracefully if not configured)
from cogs.gemini_brain import generate_puzzle

# ---- Channel & Role Config ----
PUZZLE_CHANNEL_ID = int(os.getenv("PUZZLE_CHANNEL_ID", "1514208252760424591"))
# Role given to users who solved today's puzzle (optional — set 0 to disable)
PUZZLE_SOLVED_ROLE_ID = int(os.getenv("PUZZLE_SOLVED_ROLE_ID", "0"))
# General channel ID (for kick notices)
GENERAL_CHANNEL_ID = int(os.getenv("GENERAL_CHANNEL_ID", "1514186491673985138"))
SERVER_INVITE_LINK = os.getenv("SERVER_INVITE_LINK", "")

# Puzzle topic rotation: cycles through these each day
PUZZLE_TOPICS = ["jee", "logic", "jee", "mixed", "logic", "jee", "mixed"]

# How many archived puzzles must be solved to re-enter after kick
VERIFY_PUZZLES_REQUIRED = 3
# Hours between re-verify attempts after failure
VERIFY_COOLDOWN_HOURS = 24


# ============================================================
# ANSWER BUTTON VIEW
# ============================================================

class PuzzleAnswerView(discord.ui.View):
    """Persistent view with A/B/C/D buttons for the daily puzzle."""

    def __init__(self, cog: "PuzzleCog"):
        super().__init__(timeout=None)  # Persistent — survives bot restarts
        self.cog = cog

    async def _handle_answer(self, interaction: discord.Interaction, chosen: str):
        """Common handler for all answer buttons."""
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        now_ist = get_ist_now()
        today_str = now_ist.date().isoformat()

        async with self.cog.bot.db_write_lock:
            data = await self.cog.bot.load_data()
            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            today_puzzle = puzzle_data.get(today_str)

            if not today_puzzle:
                await interaction.followup.send("❌ No puzzle found for today. Check back later!", ephemeral=True)
                return

            already_solved = uid in today_puzzle.get("solved_users", [])
            if already_solved:
                await interaction.followup.send(
                    "✅ You already solved today's puzzle! Come back tomorrow for a new one.",
                    ephemeral=True,
                )
                return

            correct_answer = today_puzzle.get("answer", "A")
            explanation = today_puzzle.get("explanation", "")

            if chosen == correct_answer:
                # Mark as solved
                if "solved_users" not in today_puzzle:
                    today_puzzle["solved_users"] = []
                today_puzzle["solved_users"].append(uid)
                data["meta"]["puzzle_of_day"][today_str] = today_puzzle
                await self.cog.bot.save_data(data)

                # Award solved role if configured
                if PUZZLE_SOLVED_ROLE_ID:
                    try:
                        guild = interaction.guild
                        role = guild.get_role(PUZZLE_SOLVED_ROLE_ID)
                        if role:
                            await interaction.user.add_roles(role, reason="Puzzle of the Day solved")
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

        # Wrong answer — show hint, let them try again
        options = today_puzzle.get("options", {})
        chosen_text = options.get(chosen, "")
        embed = discord.Embed(
            title=f"❌ Wrong — You chose {chosen}",
            description=f"**You answered:** {chosen}. {chosen_text}\n\nThat's not right. Read the question carefully and try again!\n\n💡 *Hint: Think step by step.*",
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
# VERIFY BUTTON VIEW (for re-entry after kick)
# ============================================================

class VerifyPuzzleView(discord.ui.View):
    """Temporary view for verification puzzle answers (sent via DM)."""

    def __init__(self, correct_answer: str, explanation: str, on_answer):
        super().__init__(timeout=300)  # 5 min timeout per puzzle
        self.correct_answer = correct_answer
        self.explanation = explanation
        self.on_answer = on_answer  # async callback(interaction, is_correct)

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
    """Puzzle of the Day system — daily challenges, kick enforcement, re-entry verification."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._today_puzzle_posted: str = ""   # date string of last posted puzzle
        self._midnight_kick_done: str = ""    # date string of last midnight kick run
        self._morning_wakeup_done: str = ""   # date string of last 6 AM wakeup run

        self.puzzle_loop.start()
        self.midnight_kick_loop.start()
        self.morning_wakeup_loop.start()

        # Register persistent view so buttons work after restart
        self.bot.add_view(PuzzleAnswerView(self))
        asyncio.create_task(self.startup_check())

    async def startup_check(self):
        """Catch-up logic on startup: post today's puzzle if it's past 8 AM and wasn't posted."""
        await self.bot.wait_until_ready()
        now_ist = get_ist_now()
        if now_ist.hour >= 8:
            today_str = now_ist.date().isoformat()
            data = await self.bot.load_data()
            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            loop_state = data.get("meta", {}).get("puzzle_loop_state", {})
            
            if today_str not in puzzle_data or loop_state.get("posted_date") != today_str:
                logging.info("[PUZZLE] Startup check: Today's puzzle is missing. Posting now...")
                await self._post_daily_puzzle(now_ist, force=True)

    def cog_unload(self):
        self.puzzle_loop.cancel()
        self.midnight_kick_loop.cancel()
        self.morning_wakeup_loop.cancel()

    # ------------------------------------------------------------------
    # TASK 1: POST DAILY PUZZLE AT 8 AM IST
    # ------------------------------------------------------------------

    async def _post_daily_puzzle(self, now_ist, force=False):
        """Generates the daily puzzle, posts alert, and DMs all members."""
        today_str = now_ist.date().isoformat()

        try:
            # Load and verify loop state from DB to prevent re-execution on restart
            data = await self.bot.load_data()
            loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})

            if not force and (self._today_puzzle_posted == today_str or loop_state.get("posted_date") == today_str):
                return False

            # Mark as in-progress BEFORE the slow Gemini call so a crash/restart
            # doesn't cause us to re-post on the next loop tick.
            self._today_puzzle_posted = today_str
            loop_state["posted_date"] = today_str
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info("[PUZZLE] Generating daily puzzle via brainstorm pipeline...")
            topic = PUZZLE_TOPICS[now_ist.weekday() % len(PUZZLE_TOPICS)]
            puzzle = await generate_puzzle(topic=topic)

            # Build and post the puzzle embed
            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)
                except Exception as e:
                    logging.error(f"[PUZZLE] Cannot find puzzle channel {PUZZLE_CHANNEL_ID}: {e}")
                    return False

            # Build puzzle embed
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

            # Post alert in channel first
            alert_msg = await channel.send(
                "\U0001f9e9 **Daily Puzzle is in your DMs!** Check your DMs and solve it before midnight or get kicked."
            )

            # DM puzzle to every member
            dm_count = 0
            view = PuzzleAnswerView(self)
            for member in channel.guild.members:
                if member.bot:
                    continue
                try:
                    await member.send(embed=embed, view=view)
                    dm_count += 1
                    await asyncio.sleep(0.5)  # Rate limit safety
                except discord.Forbidden:
                    pass  # DMs disabled for this user
                except Exception as dm_err:
                    logging.warning(f"[PUZZLE] Could not DM puzzle to {member.display_name}: {dm_err}")

            logging.info(f"[PUZZLE] DMed today's puzzle to {dm_count} members")

            # Re-load fresh data before saving puzzle (data may be stale after slow Gemini calls)
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
            # Ensure loop state is written in this final save too
            data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})["posted_date"] = today_str

            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info(f"[PUZZLE] Posted daily puzzle for {today_str} — source: {'AI-verified' if puzzle.get('question') not in [p['question'] for p in []] else 'static fallback'}")
            return True

        except Exception as e:
            logging.error(f"[PUZZLE] _post_daily_puzzle failed: {e}", exc_info=True)
            return False

    @tasks.loop(minutes=5)
    async def puzzle_loop(self):
        """Checks every 5 minutes. Posts puzzle at 8:00–8:04 AM IST."""
        try:
            now_ist = get_ist_now()
            # Only trigger at 8:00–8:04 AM IST
            if now_ist.hour != 8 or now_ist.minute >= 5:
                return
            await self._post_daily_puzzle(now_ist, force=False)
        except Exception as e:
            logging.error(f"[PUZZLE] Error in puzzle_loop: {e}", exc_info=True)

    @puzzle_loop.before_loop
    async def before_puzzle(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # TASK 2: MIDNIGHT KICK (11:55 PM IST)
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def midnight_kick_loop(self):
        """Checks every 5 minutes. Kicks unsolved members at 11:55–11:59 PM IST."""
        try:
            now_ist = get_ist_now()
            today_str = now_ist.date().isoformat()

            if now_ist.hour != 23 or now_ist.minute < 55:
                return

            data = await self.bot.load_data()
            loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
            if self._midnight_kick_done == today_str or loop_state.get("kick_date") == today_str:
                return

            self._midnight_kick_done = today_str
            loop_state["kick_date"] = today_str
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info("[PUZZLE] Running midnight puzzle kick check...")

            puzzle_data = data.get("meta", {}).get("puzzle_of_day", {})
            today_puzzle = puzzle_data.get(today_str)

            if not today_puzzle:
                logging.warning("[PUZZLE] No puzzle found for today — skipping kick check")
                return

            solved_users = set(today_puzzle.get("solved_users", []))

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(PUZZLE_CHANNEL_ID)
                except Exception:
                    logging.error("[PUZZLE] Cannot find puzzle channel for kick notice")
                    return

            guild = channel.guild
            kicked_count = 0

            for member in guild.members:
                if member.bot:
                    continue
                uid = str(member.id)
                if uid in solved_users:
                    continue  # Solved — safe!

                # Check if they have a moderator role (skip mods)
                if member.guild_permissions.kick_members:
                    continue

                # Build personalized kick DM
                udata = data.get("users", {}).get(uid, {})
                hours_today = udata.get("total_seconds_today", 0) / 3600
                hours_alltime = udata.get("total_seconds_alltime", 0) / 3600
                streak = udata.get("current_streak_days", 0)
                missed_days = udata.get("consecutive_missed_days", 0)

                # Increment puzzle kick count
                udata["puzzle_kicks"] = udata.get("puzzle_kicks", 0) + 1
                data.setdefault("users", {})[uid] = udata

                from cogs.gemini_brain import personalized_kick_msg
                ai_kick = await personalized_kick_msg(
                    username=member.display_name,
                    hours_today=hours_today,
                    hours_alltime=hours_alltime,
                    streak=streak,
                    puzzle_solved=False,
                    missed_days=udata.get("consecutive_missed_days", 0),
                )
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
                    pass  # DMs closed — still kick them

                try:
                    await member.kick(reason=f"Did not solve Puzzle of the Day ({today_str})")
                    kicked_count += 1
                    logging.info(f"[PUZZLE] Kicked {member.display_name} for unsolved puzzle")
                except discord.Forbidden:
                    logging.warning(f"[PUZZLE] Cannot kick {member.display_name} (no permission)")
                except Exception as e:
                    logging.error(f"[PUZZLE] Error kicking {member.display_name}: {e}")

                await asyncio.sleep(1)  # Rate limit safety

            # Save updated data
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

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
    # TASK 3: 6 AM WAKE-UP DM
    # ------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def morning_wakeup_loop(self):
        """Sends personalized 6 AM wake-up DMs to all server members."""
        try:
            now_ist = get_ist_now()
            today_str = now_ist.date().isoformat()

            if now_ist.hour != 6 or now_ist.minute >= 5:
                return

            data = await self.bot.load_data()
            loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
            if self._morning_wakeup_done == today_str or loop_state.get("wakeup_date") == today_str:
                return

            self._morning_wakeup_done = today_str
            loop_state["wakeup_date"] = today_str
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info("[PUZZLE] Sending 6 AM wake-up DMs...")

            channel = self.bot.get_channel(PUZZLE_CHANNEL_ID)
            if channel is None:
                logging.error("[PUZZLE] Cannot find puzzle channel for morning wakeup")
                return

            guild = channel.guild
            yesterday_str = (now_ist.date() - datetime.timedelta(days=1)).isoformat()

            from cogs.gemini_brain import personalized_wakeup_msg
            from bot import DAILY_GOAL_SECONDS

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
                    await asyncio.sleep(0.5)  # Rate limit
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
        """Re-entry verification: solve 3 past puzzles correctly."""
        await interaction.response.defer(ephemeral=True)

        try:
            uid = str(interaction.user.id)
            data = await self.bot.load_data()
            udata = data.get("users", {}).get(uid, {})

            # Check cooldown
            from bot import get_ist_now
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
                            f"⏰ You failed your last verification attempt. "
                            f"Try again in **{remaining_h:.1f} hours**.",
                            ephemeral=True,
                        )
                        return
                except Exception as e:
                    logging.warning(f"[PUZZLE] Failed parsing last verification attempt date: {e}")

            # Pull archived puzzles (need at least 3)
            puzzle_archive = data.get("meta", {}).get("puzzle_of_day", {})
            today_str = now_ist.date().isoformat()
            past_puzzles = [
                (date_str, p) for date_str, p in sorted(puzzle_archive.items(), reverse=True)
                if date_str != today_str and "question" in p
            ]

            if len(past_puzzles) < VERIFY_PUZZLES_REQUIRED:
                await interaction.followup.send(
                    f"❌ Not enough archived puzzles yet. The bot needs at least {VERIFY_PUZZLES_REQUIRED} days of puzzles. "
                    f"Please wait and try again tomorrow.",
                    ephemeral=True,
                )
                return

            # Pick 3 random past puzzles
            selected = random.sample(past_puzzles[:min(14, len(past_puzzles))], VERIFY_PUZZLES_REQUIRED)

            await interaction.followup.send(
                f"🔐 **Verification — Solve {VERIFY_PUZZLES_REQUIRED} puzzles to rejoin**\n\n"
                f"I'll send you {VERIFY_PUZZLES_REQUIRED} puzzles one at a time via DM. "
                f"Get all {VERIFY_PUZZLES_REQUIRED} correct to be re-invited. You have 5 minutes per puzzle.\n\n"
                f"Starting now...",
                ephemeral=True,
            )

            score = 0
            for i, (date_str, puzzle) in enumerate(selected, 1):
                opts = puzzle.get("options", {})
                options_str = "\n".join(f"**{k}.** {v}" for k, v in opts.items())

                embed = discord.Embed(
                    title=f"🔐 Verification Puzzle {i}/{VERIFY_PUZZLES_REQUIRED}",
                    description=f"*(From {date_str})*\n\n**{puzzle['question']}**\n\n{options_str}",
                    color=0x5865F2,
                )
                embed.set_footer(text=f"You have 5 minutes to answer. Puzzle {i} of {VERIFY_PUZZLES_REQUIRED}.")

                result_holder = {}

                async def on_answer(inter, is_correct, chosen, correct, explanation,
                                    holder=result_holder):
                    holder["correct"] = is_correct
                    holder["chosen"] = chosen
                    holder["answer"] = correct
                    holder["explanation"] = explanation

                view = VerifyPuzzleView(
                    correct_answer=puzzle["answer"],
                    explanation=puzzle.get("explanation", ""),
                    on_answer=on_answer,
                )

                dm_msg = await interaction.user.send(embed=embed, view=view)
                await view.wait()  # Wait for button press or timeout

                if not result_holder:
                    # Timed out
                    await interaction.user.send(
                        f"⏰ **Puzzle {i} timed out.** Verification failed. "
                        f"Wait {VERIFY_COOLDOWN_HOURS}h before trying again."
                    )
                    # Mark failed
                    udata["puzzle_verify_failed"] = True
                    udata["puzzle_verify_last"] = now_ist.isoformat()
                    data.setdefault("users", {})[uid] = udata
                    async with self.bot.db_write_lock:
                        await self.bot.save_data(data)
                    return

                if result_holder.get("correct"):
                    score += 1
                    if i < VERIFY_PUZZLES_REQUIRED:
                        await interaction.user.send(
                            f"✅ **Correct!** {result_holder['explanation']}\n\n"
                            f"Moving to puzzle {i+1}..."
                        )
                else:
                    chosen = result_holder.get("chosen", "?")
                    correct = result_holder.get("answer", "?")
                    expl = result_holder.get("explanation", "")
                    await interaction.user.send(
                        f"❌ **Wrong!** You chose **{chosen}**, correct was **{correct}**.\n"
                        f"📖 {expl}\n\n"
                        f"Verification failed. Wait {VERIFY_COOLDOWN_HOURS}h before trying again."
                    )
                    # Mark failed
                    udata["puzzle_verify_failed"] = True
                    udata["puzzle_verify_last"] = now_ist.isoformat()
                    data.setdefault("users", {})[uid] = udata
                    async with self.bot.db_write_lock:
                        await self.bot.save_data(data)
                    return

                await asyncio.sleep(2)

            # All 3 correct!
            udata["puzzle_verify_failed"] = False
            udata["puzzle_verify_last"] = now_ist.isoformat()
            data.setdefault("users", {})[uid] = udata
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

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
            title=f"🧩 Puzzle Status — {today_str}",
            description=f"**{'✅ You solved it!' if you_solved else '❌ You have NOT solved it yet — deadline is midnight IST!'}**",
            color=0x57F287 if you_solved else 0xFF0000,
        )
        embed.add_field(name="✅ Solved", value=f"{len(solved_users)} / {total_members} members", inline=True)
        embed.add_field(name="⏰ Deadline", value="11:59 PM IST", inline=True)
        embed.set_footer(text="YPT Study Bot • Fail to solve = kicked at midnight")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # SLASH COMMAND: /post_puzzle_now (force post daily puzzle now)
    # ------------------------------------------------------------------

    @app_commands.command(name="post_puzzle_now", description="Force post today's daily puzzle instantly (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_puzzle_now(self, interaction: discord.Interaction):
        # Immediately defer — prevents Discord's 3-second interaction timeout
        await interaction.response.defer(ephemeral=True)
        now_ist = get_ist_now()

        # Send a live status message we can edit once the slow Gemini pipeline finishes
        status_msg = await interaction.followup.send(
            "Generating puzzle via Gemini brainstorm pipeline...\n"
            "Stages: Brainstorm 3 options -> Select best -> Verify x2 -> DM all members\n"
            "Allow up to 90 seconds.",
            ephemeral=True,
            wait=True,
        )

        async def _bg():
            try:
                success = await self._post_daily_puzzle(now_ist, force=True)
                if success:
                    await status_msg.edit(content=(
                        "Puzzle posted! Brainstormed candidates, selected the best, "
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


async def setup(bot: commands.Bot):
    cog = PuzzleCog(bot)
    await bot.add_cog(cog)
    logging.info("[PUZZLE] Loaded Puzzle of the Day Extension")
