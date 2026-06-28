# --- DISCIPLINE EXTENSION ---
# Features:
#   1. Midnight punishment: toxic DMs for 0-hour days, comparing to partner's stats
#   2. Hourly nagging from 2 PM to 10 PM IST (regular days) / 6 AM to 10 PM (off days)
#      — state-aware: skips CURRENTLY_STUDYING and DONE_ENOUGH users
#   3. study_gap_reminder_loop: every 30 minutes, 8 AM–11 PM IST
#      — sends DROPPED_OFF or NOT_STARTED DMs, with 25-min per-user cooldown
#   4. Auto-kick after 4 consecutive missed days with harsh DM + permanent invite
#   5. Daily mention in study text channel for absent users
#   6. Strike system: 3 = public warning, 4 = kicked
#
# Delete this file to remove all discipline features without affecting bot.py.

import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import logging
import random

from bot import get_ist_now, get_ist_date, IST_TZ, DAILY_GOAL_SECONDS
from cogs import gemini_brain  # Gemini AI for personalized messages (graceful fallback if no key)

# ---- Channel & User IDs ----
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"
GENERAL_CHANNEL_ID = 1514241642415001610  # #study-discussion text channel
STUDY_TEXT_CHANNEL_ID = 1514241642415001610  # #study-discussion for public callouts

# Study voice channels (used to check if someone is currently studying)
STUDY_VOICE_CHANNELS = {1514208313452007514, 1514596473629708298, 1514244606827561171}

# ---- Strike Config ----
STRIKES_TO_WARN = 3
STRIKES_TO_KICK = 4

# ---- Permanent invite link ----
SERVER_INVITE_LINK = None  # Will be set dynamically

# ---- Study state constants ----
STATE_CURRENTLY_STUDYING = "CURRENTLY_STUDYING"
STATE_DONE_ENOUGH        = "DONE_ENOUGH"
STATE_DROPPED_OFF        = "DROPPED_OFF"
STATE_NOT_STARTED        = "NOT_STARTED"

# "Done enough" = user has crossed their daily goal (imported from bot.py, default 1.5h = 5400s)
DONE_ENOUGH_SECONDS = DAILY_GOAL_SECONDS

# ---- Off-day weekdays ----
OFF_DAYS = {2, 5, 6}  # Wednesday=2, Saturday=5, Sunday=6


# ============================================================
# TOXIC MIDNIGHT MESSAGES (rotating, ego-destroying)
# ============================================================
TOXIC_MESSAGES = [
    "You studied for **0 hours** yesterday.\n\nMeanwhile, **{other_name}** ground out **{other_hours:.1f} hours**.\n\nAre you even trying anymore? This is embarrassing. Get back to work.",
    "**0 hours.** Zero. Nothing. Nada.\n\n**{other_name}** put in **{other_hours:.1f} hours** while you were doing... what exactly?\n\nDo better. Seriously.",
    "Another day wasted. **0 hours** studied.\n\n**{other_name}** managed **{other_hours:.1f} hours**. You couldn't even do 1 minute?\n\nThis is a pattern. Fix it.",
    "Imagine having goals and then studying **0 hours**.\n\n**{other_name}** clocked **{other_hours:.1f} hours**. The gap is growing.\n\nYou're falling behind. Wake up.",
    "You know what **0 hours** gets you? Nothing. No rank. No progress. No future.\n\n**{other_name}** studied **{other_hours:.1f} hours**. They're moving. You're not.",
    "Bro really logged **0 hours** and went to sleep thinking everything's fine \U0001f480\n\n**{other_name}**: **{other_hours:.1f} hours**. You: **0**. Do the math.",
]

# ============================================================
# HOURLY NAGGING MESSAGES (2 PM to 10 PM IST, escalating)
# Used on REGULAR days (Mon, Tue, Thu, Fri)
# ============================================================
HOURLY_NAG_MESSAGES = {
    14: "\U0001f4d6 It's 2 PM. Afternoon's here \u2014 perfect time to start a study session. Don't waste it.",
    15: "\u23f3 3 PM already. Have you started studying yet? **{other_name}** has **{other_today:.1f}h** logged today. Clock's ticking.",
    16: "\U0001f4da 4 PM. The day is slipping away. **{other_name}** is at **{other_today:.1f}h**. You: **{my_today:.1f}h**. Get moving.",
    17: "\u23f0 5 PM. Still not in a study channel? **{other_name}** has already put in **{other_today:.1f}h** today. What's your excuse?",
    18: "\U0001f525 6 PM already. Half the evening is GONE. Get in a voice channel and start grinding. NOW.",
    19: "\U0001f624 It's 7 PM and you're STILL not studying?! **{other_name}** is at **{other_today:.1f}h** today. You have **{my_today:.1f}h**. Embarrassing.",
    20: "\U0001f480 8 PM. You've wasted the ENTIRE afternoon. If you don't start RIGHT NOW, today is a total L. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**.",
    21: "\U0001f6a8 **9 PM.** This is your LAST WARNING before the day is over. Get your ass in a study channel or accept that you're a failure today. **{other_name}** did **{other_today:.1f}h**. You did **{my_today:.1f}h**. PATHETIC.",
    22: "\u2620\ufe0f **10 PM. The day is basically over.** You had 18 hours to study and you chose to waste them. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**. Tomorrow better be different or you're getting KICKED.",
}

# ============================================================
# OFF-DAY MORNING NAG MESSAGES (6 AM to 1 PM IST)
# Used ONLY on off days (Wed, Sat, Sun) — PW schedule
# ============================================================
OFF_DAY_MORNING_MESSAGES = {
    6:  "\U0001f305 **6 AM. It's your OFF DAY.** The best students use off days to get AHEAD. Wake up. Get out of bed. Start before everyone else.",
    7:  "\u23f0 **7 AM \u2014 WAKE UP.** You're burning daylight. Off day doesn't mean lazy day. **{other_name}** might already be up. Don't fall behind.",
    8:  "\u2600\ufe0f **8 AM.** Still in bed? That's 2 hours of potential study GONE. Your competitors are already at their desks. **GET. UP. NOW.**",
    9:  "\U0001f624 **9 AM and you haven't started?!** That's 3 hours wasted. Off day = BONUS study time, not sleep-all-day time. **{other_name}** has **{other_today:.1f}h** already.",
    10: "\U0001f525 **10 AM.** If you're not studying by now, you're choosing to lose. It's your OFF DAY \u2014 you have NO excuses today. Zero. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**.",
    11: "\U0001f480 **11 AM \u2014 HALF THE MORNING IS GONE.** Every hour you sleep in is an hour **{other_name}** uses to get ahead. They have **{other_today:.1f}h** today. You have **{my_today:.1f}h**. Disgusting.",
    12: "\U0001f6a8 **IT'S NOON.** You've wasted the ENTIRE morning of your off day. 6 hours of potential study \u2014 GONE. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**. What are you even doing?",
    13: "\u2620\ufe0f **1 PM on your OFF DAY and you've done {my_today:.1f}h.** That's pathetic. **{other_name}** has **{other_today:.1f}h**. You had since 6 AM. The afternoon is your LAST CHANCE to salvage today.",
}

# ============================================================
# STUDY GAP REMINDER MESSAGES — DROPPED OFF STATE
# Shown when user studied SOME but is below their daily goal and not currently studying.
# Tone: ENCOURAGING, not harsh. They showed up — reward that, push them back.
# ============================================================
DROPPED_OFF_MESSAGES = [
    "\U0001f44d **Good start with {hours_today:.1f}h!** You showed up and that counts. Now come back and keep building — your goal is just {goal_hours:.1f}h total and you're already partway there!",
    "\U0001f4a1 **{hours_today:.1f}h in the bag.** Nice. Take your break and come right back — you're {gap:.1f}h away from hitting your daily goal. You're already doing better than anyone who didn't even open a book.",
    "\u26a1 **You've got {hours_today:.1f}h logged today.** That's a solid foundation. Don't lose the momentum — hop back in the study VC and finish strong!",
    "\U0001f525 **{hours_today:.1f}h done, {gap:.1f}h left to goal.** You started — that's the hardest part. The rest is just showing up again. Come back and close it out.",
    "\U0001f4da **Great work getting {hours_today:.1f}h done.** Short break? No problem. Just make sure you're back in that VC soon — your daily goal is within reach!",
    "\u23f0 It's {time_now} and you've already put in {hours_today:.1f}h. Respect. Now give it one more session — {gap:.1f}h to goal. You can do this.",
]

# ============================================================
# STUDY GAP REMINDER MESSAGES — NOT STARTED STATE
# Only shown to people who have studied 0 seconds today.
# ============================================================
NOT_STARTED_MESSAGES = [
    "\U0001f480 **You haven't opened a single book today.** It's {time_now}. Every hour you wait is another concept you won't cover. GET IN A STUDY CHANNEL NOW.",
    "\U0001f6a8 **0 hours studied today.** You're burning daylight. What is your excuse? Get in a study channel and start.",
    "\u2620\ufe0f **Zero. Zilch. Nothing.** That's what you've done today. {other_name} already has {other_hours:.1f}h logged. Get moving.",
    "\U0001f4f5 **Still nothing as of {time_now}.** Just start. Open your notes, pick a topic, and get in a voice channel. That's it.",
    "\U0001f534 **0h studied today.** Every day you skip is a day you can't get back. Get in a study channel in the next 5 minutes.",
]

# ============================================================
# CONGRATULATIONS MESSAGES — DAILY GOAL CROSSED
# Sent ONE TIME when the user crosses their daily goal. Then silence.
# ============================================================
GOAL_CROSSED_MESSAGES = [
    "\U0001f3c6 **Daily goal crushed!** You hit **{hours_today:.1f}h** today — your target was {goal_hours:.1f}h. Take a well-earned break. You've earned it.",
    "\U0001f525 **Goal smashed! {hours_today:.1f}h studied today.** That's your daily target done and dusted. Rest up, you've done your part.",
    "\u2705 **{hours_today:.1f}h today — daily goal complete!** Consistency like this is how you go from good to great. Rest now, be back tomorrow!",
    "\U0001f31f **You did it! {hours_today:.1f}h logged today.** Daily goal: ✅. Take the rest of the evening and recharge — tomorrow we go again.",
    "\U0001f389 **Daily goal hit!** {hours_today:.1f}h in the books. You showed up and delivered. No more nagging from me today — enjoy your rest!",
]

# ============================================================
# PUSH PAST LIMIT MESSAGES — sent immediately after goal congrats
# Tone: hype them up to grind BEYOND the goal. Topper energy.
# ============================================================
PUSH_PAST_LIMIT_MESSAGES = [
    "🔥 **But why stop there?** The toppers don't clock out at {goal_hours:.1f}h. They push to **8, 9, 10 hours**. Your goal was the floor, not the ceiling. Get back in and **go further**.",
    "👑 **Goal hit. Now what?** Average students stop here. Toppers don't. AIR 1 didn't happen by hitting the minimum. You've got {hours_left:.1f}h left today — use them and put some real distance between you and the competition.",
    "⚡ **Good. Now forget the goal.** The goal was just to get you started. Real grinders treat it as a warmup. How much further can you push today? Get back in the VC and find out.",
    "🏆 **Goal done. Legacy starts now.** Every hour PAST your goal is what separates you from someone who's just 'trying'. Be the one who doesn't stop. One more session. Right now.",
    "📈 **You've done {hours_today:.1f}h. The question is — how much can you do?** Every extra hour you put in today is compound interest for your rank. Don't waste the momentum. Go again.",
    "🧠 **Goal hit. Brain still working? Then study more.** Stop when you're exhausted, not when you've hit an arbitrary number. Push to {extra_hours:.0f}h+ and make today count.",
]

# ============================================================
# KICK DM MESSAGE (sent right before kicking)
# ============================================================
KICK_DM_TEMPLATE = (
    "# \U0001f528 YOU'VE BEEN KICKED\n\n"
    "You missed **{strikes} consecutive days** of studying. That's unacceptable.\n\n"
    "This server is for people who are **SERIOUS** about their goals. "
    "If you're not going to put in the work, don't waste a spot.\n\n"
    "**If you actually want to change**, here's the invite link. "
    "But only rejoin if you're ready to GRIND:\n{invite_link}\n\n"
    "*This is your wake-up call. Next time, there won't be one.*"
)


# ============================================================
# COLOUR HELPERS
# ============================================================
def _urgency_color(hour: int) -> int:
    """Return a Discord embed color based on the hour of day (IST).
    Escalates from cool blue in the morning to deep red at night."""
    colors = {
        6:  0x3498DB, 7:  0x2980B9, 8:  0x57F287, 9:  0xA3BE8C,
        10: 0xFEE75C, 11: 0xFFA500, 12: 0xFF8C00, 13: 0xFF4500,
        14: 0x57F287, 15: 0xA3BE8C, 16: 0xFEE75C, 17: 0xFFA500,
        18: 0xFF8C00, 19: 0xFF4500, 20: 0xFF0000, 21: 0xCC0000,
        22: 0x8B0000, 23: 0x800000,
    }
    return colors.get(hour, 0xFF0000)


def _hours_left_today(now_ist: datetime.datetime) -> float:
    """Return fractional hours remaining until midnight IST."""
    midnight = now_ist.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    delta = midnight - now_ist
    return delta.total_seconds() / 3600


class DisciplineCog(commands.Cog):
    """Daily punishment system: toxic DMs, hourly nagging, gap reminders, public callouts, and auto-kicks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._toxic_index = 0
        self._invite_link = SERVER_INVITE_LINK
        # Per-user last gap-nag datetime (user_id str -> datetime)
        self._gap_nag_sent: dict = {}
        # Per-user congrats date (user_id str -> date str) — to send goal congrats only once per day
        self._congrats_sent: dict = {}
        # Per-user hourly nag tracker to prevent memory leak (key tuple -> bool)
        self._nags_sent: dict = {}

        self.daily_discipline_check.start()
        self.hourly_nag_check.start()
        self.daily_absence_callout.start()
        self.study_gap_reminder_loop.start()

    def cog_unload(self):
        self.daily_discipline_check.cancel()
        self.hourly_nag_check.cancel()
        self.daily_absence_callout.cancel()
        self.study_gap_reminder_loop.cancel()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    async def _get_invite_link(self, guild: discord.Guild) -> str:
        """Get or create a permanent invite link for the server."""
        if self._invite_link:
            return self._invite_link

        try:
            invites = await guild.invites()
            for inv in invites:
                if inv.max_age == 0 and inv.max_uses == 0:
                    self._invite_link = str(inv)
                    return self._invite_link

            general = await self.bot.get_or_fetch_channel(GENERAL_CHANNEL_ID)
            if general:
                inv = await general.create_invite(
                    max_age=0, max_uses=0,
                    reason="Discipline system \u2014 permanent invite for kicked users"
                )
                self._invite_link = str(inv)
                return self._invite_link
        except Exception as e:
            logging.error(f"[DISCIPLINE] Failed to get/create invite: {e}")

        return "*(Could not generate invite link \u2014 ask your friend to re-invite you)*"

    def _is_user_studying(self, guild: discord.Guild, user_id: int) -> bool:
        """Check if a user is currently in any study voice channel."""
        member = guild.get_member(user_id)
        if member and member.voice and member.voice.channel:
            return member.voice.channel.id in STUDY_VOICE_CHANNELS
        return False

    def _get_user_study_state(
        self,
        guild: discord.Guild,
        uid_str: str,
        udata: dict,
        now_ist: datetime.datetime,
    ) -> str:
        """
        Returns one of:
          STATE_CURRENTLY_STUDYING  -- active voice-channel session in progress
          STATE_DONE_ENOUGH         -- >= 3 h studied today (10 800 s)
          STATE_DROPPED_OFF         -- studied some today (> 0 s, < 10 800 s) but NOT currently studying
          STATE_NOT_STARTED         -- 0 s today and NOT currently studying
        """
        # 1. Check live voice presence first
        try:
            uid_int = int(uid_str)
        except ValueError:
            uid_int = None

        if uid_int is not None and self._is_user_studying(guild, uid_int):
            return STATE_CURRENTLY_STUDYING

        # 2. Also check the DB-level session flag (bot may not have cached the voice state yet)
        if udata.get("session_start_timestamp") is not None:
            return STATE_CURRENTLY_STUDYING

        # 3. Check today's accumulated seconds
        today_str = now_ist.date().isoformat()
        seconds_today = udata.get("daily_history", {}).get(today_str, 0)

        if seconds_today >= DONE_ENOUGH_SECONDS:
            return STATE_DONE_ENOUGH
        elif seconds_today > 0:
            return STATE_DROPPED_OFF
        else:
            return STATE_NOT_STARTED

    def _build_jee_reality_field(self, hours_today: float, gap: float, target_hours: float = 6.0):
        """Returns (name, value) for the JEE Reality Check embed field."""
        name = "\U0001f4ca JEE Reality Check"
        value = (
            f"\U0001f3af Daily Target: **{target_hours:.1f}h**\n"
            f"\U0001f4ca Your Today: **{hours_today:.1f}h**\n"
            f"\U0001f4c9 Gap: **{gap:.1f}h behind target**"
        )
        return name, value

    def _peer_info(self, users: dict, uid_str: str, today_str: str):
        """Returns (other_name, other_hours_today) for the top peer (excluding this user)."""
        ranked = sorted(
            ((k, v.get("daily_history", {}).get(today_str, 0)) for k, v in users.items() if k != uid_str),
            key=lambda x: x[1],
            reverse=True,
        )
        if ranked:
            other_uid, other_secs = ranked[0]
            other_name = users[other_uid].get("username", "your partner")
            return other_name, other_secs / 3600
        return "the daily goal", 1.5

    # ==================================================================
    # TASK 1: MIDNIGHT DISCIPLINE CHECK (strikes, toxic DMs, kicks)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def daily_discipline_check(self):
        """Runs every 10 minutes. Fires punishment logic at midnight IST."""
        try:
            now_ist = get_ist_now()
            today_str = now_ist.date().isoformat()

            # Only trigger in the 00:00-00:09 window
            if now_ist.hour == 0 and now_ist.minute < 10:
                # Check DB loop state to prevent re-execution on restart
                data = await self.bot.load_data()
                loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
                if loop_state.get("discipline_check_date") == today_str:
                    return

                logging.info("[DISCIPLINE] Running daily midnight discipline check...")
                loop_state["discipline_check_date"] = today_str
                async with self.bot.db_write_lock:
                    await self.bot.save_data(data)

                await self.execute_punishments()
        except Exception as e:
            logging.error(f"[DISCIPLINE] Error in daily_discipline_check: {e}", exc_info=True)

    @daily_discipline_check.before_loop
    async def before_discipline(self):
        await self.bot.wait_until_ready()

    async def execute_punishments(self):
        """Check each user's yesterday study hours and apply punishments without holding the DB lock during slow operations."""
        data = await self.bot.load_data()
        users = data.get("users", {})

        general_channel = await self.bot.get_or_fetch_channel(GENERAL_CHANNEL_ID)
        if not general_channel:
            logging.error("[DISCIPLINE] Could not find General channel.")
            return

        guild = general_channel.guild
        now_ist = get_ist_now()
        yesterday = (now_ist.date() - datetime.timedelta(days=1)).isoformat()

        # Sort users by yesterday's seconds to find comparison peers
        yesterday_ranked = sorted(
            ((uid, udata.get("daily_history", {}).get(yesterday, 0)) for uid, udata in users.items()),
            key=lambda x: x[1],
            reverse=True,
        )

        strike_updates = {}
        db_changed = False

        for uid_str in list(users.keys()):
            my_data = users[uid_str]
            my_seconds = my_data.get("daily_history", {}).get(yesterday, 0)
            strikes = my_data.get("discipline_strikes", 0)

            # Find the peer to compare against
            other_uid_str = None
            other_seconds = 0
            if len(yesterday_ranked) > 1:
                if yesterday_ranked[0][0] == uid_str:
                    other_uid_str = yesterday_ranked[1][0]
                    other_seconds = yesterday_ranked[1][1]
                else:
                    other_uid_str = yesterday_ranked[0][0]
                    other_seconds = yesterday_ranked[0][1]

            other_user_data = users.get(other_uid_str, {}) if other_uid_str else {}

            if my_seconds == 0:
                # ---- SLACKER DETECTED ----
                try:
                    uid_int = int(uid_str)
                    member = guild.get_member(uid_int)
                    if not member:
                        member = await guild.fetch_member(uid_int)
                except Exception:
                    member = None

                if not member:
                    logging.info(f"[DISCIPLINE] Skipping strike update for {uid_str} — user has left the server.")
                    continue

                strikes += 1
                strike_updates[uid_str] = strikes
                db_changed = True

                if other_uid_str:
                    other_name = other_user_data.get("username", "your partner")
                    other_hours = other_seconds / 3600
                else:
                    other_name = "the daily goal"
                    other_hours = 1.5

                # 1. TOXIC DM
                try:
                    msg_template = TOXIC_MESSAGES[self._toxic_index % len(TOXIC_MESSAGES)]
                    self._toxic_index += 1

                    my_goal_seconds = my_data.get("daily_goal_seconds", DONE_ENOUGH_SECONDS)
                    my_goal_hours = my_goal_seconds / 3600

                    embed = discord.Embed(
                        title="\U0001f480 Zero Hours Recorded \u2014 Absolutely Pathetic.",
                        description=msg_template.format(
                            other_name=other_name,
                            other_hours=other_hours,
                        ),
                        color=0xED4245,
                    )
                    embed.add_field(
                        name="\U0001f4ca JEE Reality Check",
                        value=(
                            f"\U0001f3af Daily Target: **{my_goal_hours:.1f}h/day**\n"
                            f"\U0001f4ca Your Yesterday: **0.0h**\n"
                            f"\U0001f4c9 Gap: **{my_goal_hours:.1f}h behind target**"
                        ),
                        inline=False,
                    )
                    embed.set_footer(
                        text=(
                            f"Strike {strikes}/{STRIKES_TO_KICK} \u2014 "
                            f"{STRIKES_TO_KICK} strikes = Auto-Kick  |  "
                            f"{other_name}'s yesterday: {other_hours:.1f}h  |  "
                            f"{now_ist.strftime('%H:%M')} IST"
                        )
                    )
                    await member.send(embed=embed)
                    logging.info(
                        f"[DISCIPLINE] Sent toxic DM to {my_data.get('username', uid_str)} "
                        f"(strike {strikes})"
                    )
                except discord.Forbidden:
                    logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} (DMs disabled)")
                except Exception as dm_err:
                    logging.error(f"[DISCIPLINE] Failed sending toxic DM to {uid_str}: {dm_err}")

                # 2. PUBLIC WARNING at strike 3
                if strikes == STRIKES_TO_WARN:
                    try:
                        await general_channel.send(
                            f"\u26a0\ufe0f <@{uid_str}> **WARNING!** You have missed "
                            f"{STRIKES_TO_WARN} consecutive days of studying. "
                            f"If you do not study today, you will be **KICKED** "
                            f"from the server tonight."
                        )
                    except Exception as warn_err:
                        logging.error(f"[DISCIPLINE] Failed sending warning to general channel: {warn_err}")

                # 3. AUTO-KICK at strike 4+
                elif strikes >= STRIKES_TO_KICK:
                    try:
                        invite_link = await self._get_invite_link(guild)

                        hours_alltime = my_data.get("total_seconds_alltime", 0) / 3600
                        hours_today_approx = my_data.get("total_seconds_today", 0) / 3600
                        streak = my_data.get("current_streak_days", 0)
                        
                        try:
                            ai_kick_text = await gemini_brain.personalized_kick_msg(
                                username=my_data.get("username", "Student"),
                                hours_today=hours_today_approx,
                                hours_alltime=hours_alltime,
                                streak=streak,
                                puzzle_solved=False,
                                missed_days=strikes,
                            )
                        except Exception as gem_err:
                            logging.error(f"[DISCIPLINE] Gemini personalized kick message failed: {gem_err}")
                            ai_kick_text = (
                                f"You missed the puzzle and barely showed up today. "
                                f"This server exists for serious JEE aspirants, and right now you're not acting like one. "
                                f"Use /verify to rejoin — solve 3 puzzles and prove you belong here."
                            )

                        full_kick_msg = (
                            f"{ai_kick_text}\n\n"
                            f"You missed **{strikes} consecutive days** of studying.\n"
                            f"**Rejoin link:** {invite_link}\n\n"
                            f"*This is your wake-up call. Don't waste it.*"
                        )
                        try:
                            embed = discord.Embed(
                                title="🔨 KICKED FROM STUDY BOI",
                                description=full_kick_msg,
                                color=0xED4245,
                            )
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            pass

                        await member.kick(
                            reason=f"Missed {strikes} consecutive days of study."
                        )
                        await general_channel.send(
                            f"\U0001f528 <@{uid_str}> has been **kicked** from the server "
                            f"for missing {strikes} consecutive days of study.\n"
                            f"They received a DM with an invite link to rejoin \u2014 "
                            f"**only if they're serious this time.**"
                        )
                        logging.info(f"[DISCIPLINE] Kicked {my_data.get('username', uid_str)}")
                    except discord.Forbidden:
                        try:
                            await general_channel.send(
                                f"\u274c I tried to kick <@{uid_str}> for missing "
                                f"{strikes} days, but I lack the permissions!"
                            )
                        except Exception:
                            pass
                    except Exception as kick_err:
                        logging.error(f"[DISCIPLINE] General error kicking user {uid_str}: {kick_err}")
            else:
                # ---- STUDIED: Reset strikes ----
                if strikes > 0:
                    strike_updates[uid_str] = 0
                    db_changed = True
                    logging.info(
                        f"[DISCIPLINE] Reset strikes for {my_data.get('username', uid_str)} "
                        f"(studied {my_seconds/3600:.1f}h yesterday)"
                    )

        if db_changed:
            async with self.bot.db_write_lock:
                data = await self.bot.load_data()
                for uid_str, new_strikes in strike_updates.items():
                    if uid_str in data.get("users", {}):
                        data["users"][uid_str]["discipline_strikes"] = new_strikes
                await self.bot.save_data(data)

    # ==================================================================
    # TASK 2: HOURLY NAGGING (state-aware)
    # Off days (Wed/Sat/Sun): 6 AM - 10 PM IST
    # Regular days (Mon/Tue/Thu/Fri): 2 PM - 10 PM IST
    # Skips CURRENTLY_STUDYING and DONE_ENOUGH users
    # ==================================================================
    @tasks.loop(minutes=5)
    async def hourly_nag_check(self):
        """Checks every 5 minutes. Sends nag DMs if user is not studying and hasn't hit their goal today."""
        try:
            now_ist = get_ist_now()

            # Only fire in the first 5 minutes of the hour
            if now_ist.minute >= 5:
                return

            hour = now_ist.hour
            is_off_day = now_ist.weekday() in OFF_DAYS

            # Pick the right message based on day type and hour
            if is_off_day and hour in OFF_DAY_MORNING_MESSAGES:
                msg_template = OFF_DAY_MORNING_MESSAGES[hour]
            elif hour in HOURLY_NAG_MESSAGES:
                msg_template = HOURLY_NAG_MESSAGES[hour]
            else:
                return

            # Prevent double-firing within the same hour using DB state
            data = await self.bot.load_data()
            loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
            today_hour_str = f"{now_ist.date().isoformat()}_{hour}"
            if loop_state.get("last_hourly_nag") == today_hour_str:
                return

            loop_state["last_hourly_nag"] = today_hour_str
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info(f"[DISCIPLINE] Hourly nag check at {hour}:00 IST")

            users = data.get("users", {})

            general_channel = await self.bot.get_or_fetch_channel(GENERAL_CHANNEL_ID)
            if not general_channel:
                return
            guild = general_channel.guild

            today_str = now_ist.date().isoformat()

            for uid_str in list(users.keys()):
                my_data = users[uid_str]

                # STATE CHECK: skip users who are already grinding or done for the day
                state = self._get_user_study_state(guild, uid_str, my_data, now_ist)
                if state in (STATE_CURRENTLY_STUDYING, STATE_DONE_ENOUGH):
                    logging.info(
                        f"[DISCIPLINE] Skipping hourly nag for {uid_str} — state={state}"
                    )
                    continue

                # Find peer to compare
                other_name, other_today = self._peer_info(users, uid_str, today_str)
                my_today = my_data.get("daily_history", {}).get(today_str, 0) / 3600
                goal_seconds_nag = my_data.get("daily_goal_seconds", DONE_ENOUGH_SECONDS)
                goal_hours_nag = goal_seconds_nag / 3600

                try:
                    uid_int = int(uid_str)
                    member = guild.get_member(uid_int)
                    if not member:
                        member = await guild.fetch_member(uid_int)
                except Exception:
                    member = None
                if not member:
                    continue

                try:
                    formatted_msg = await gemini_brain.personalized_study_reminder(
                        username=my_data.get("username", "Student"),
                        hours_today=my_today,
                        goal_hours=goal_hours_nag,
                        time_str=now_ist.strftime("%H:%M"),
                        peer_name=other_name,
                        peer_hours=other_today,
                    )

                    embed_color = _urgency_color(hour)

                    if hour < 10:
                        title_emoji, title_text = "\U0001f305", "WAKE UP & STUDY"
                    elif hour < 14:
                        title_emoji, title_text = "\u2600\ufe0f", "Are You Studying Yet?"
                    elif hour < 19:
                        title_emoji, title_text = "\u23f0", "Get Back to Work"
                    else:
                        title_emoji, title_text = "\U0001f6a8", "LAST CHANCE TODAY"

                    gap = max(0.0, goal_hours_nag - my_today)
                    field_name, field_value = self._build_jee_reality_field(my_today, gap, target_hours=goal_hours_nag)

                    embed = discord.Embed(
                        title=f"{title_emoji} {hour}:00 IST \u2014 {title_text}",
                        description=formatted_msg,
                        color=embed_color,
                    )
                    embed.add_field(name=field_name, value=field_value, inline=False)
                    embed.set_footer(
                        text=(
                            f"Your today: {my_today:.1f}h  |  "
                            f"{other_name}'s today: {other_today:.1f}h  |  "
                            f"{now_ist.strftime('%H:%M')} IST"
                        )
                    )
                    await member.send(embed=embed)
                    logging.info(
                        f"[DISCIPLINE] Sent {hour}:00 nag to {my_data.get('username', uid_str)} "
                        f"(state={state})"
                    )
                except discord.Forbidden:
                    logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} for hourly nag")
                except Exception as e:
                    logging.error(f"[DISCIPLINE] Hourly nag error for {uid_str}: {e}")
        except Exception as e:
            logging.error(f"[DISCIPLINE] Error in hourly_nag_check loop: {e}", exc_info=True)

    @hourly_nag_check.before_loop
    async def before_nag(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK 3: STUDY GAP REMINDER (every 30 minutes, 8 AM-11 PM IST)
    # Sends DROPPED_OFF or NOT_STARTED DMs with a 25-min per-user cooldown
    # ==================================================================
    @tasks.loop(minutes=30)
    async def study_gap_reminder_loop(self):
        """Every 30 minutes between 8 AM and 11 PM IST.
        Sends motivational/aggressive DMs to users who have dropped off or not started."""
        try:
            now_ist = get_ist_now()
            hour = now_ist.hour

            # Only run 8 AM to 11 PM IST (23:00 exclusive end)
            if not (8 <= hour < 23):
                return

            logging.info(f"[DISCIPLINE] study_gap_reminder_loop firing at {now_ist.strftime('%H:%M')} IST")

            data = await self.bot.load_data()
            users = data.get("users", {})

            general_channel = await self.bot.get_or_fetch_channel(GENERAL_CHANNEL_ID)
            if not general_channel:
                logging.warning("[DISCIPLINE] gap reminder: could not fetch general channel")
                return
            guild = general_channel.guild

            today_str = now_ist.date().isoformat()
            time_now_str = now_ist.strftime("%H:%M")
            hours_left = _hours_left_today(now_ist)

            for uid_str in list(users.keys()):
                my_data = users[uid_str]

                # STUDY STATE
                state = self._get_user_study_state(guild, uid_str, my_data, now_ist)

                # Skip if currently studying — never nag an active studier
                if state == STATE_CURRENTLY_STUDYING:
                    continue

                # Resolve member early (needed for all branches)
                try:
                    uid_int = int(uid_str)
                    member = guild.get_member(uid_int)
                    if not member:
                        member = await guild.fetch_member(uid_int)
                except Exception:
                    member = None
                if not member:
                    continue

                # Peer info and today's hours
                other_name, other_hours = self._peer_info(users, uid_str, today_str)
                seconds_today = my_data.get("daily_history", {}).get(today_str, 0)
                hours_today = seconds_today / 3600
                goal_seconds = my_data.get("daily_goal_seconds", DONE_ENOUGH_SECONDS)
                goal_hours = goal_seconds / 3600
                gap = max(0.0, goal_hours - hours_today)

                # -------------------------------------------------------
                # BRANCH 1: User crossed their daily goal → one-time congrats, then silence
                # -------------------------------------------------------
                if state == STATE_DONE_ENOUGH:
                    congrats_date = self._congrats_sent.get(uid_str)
                    if congrats_date == today_str:
                        continue  # Already sent congrats today — stay silent

                    body = await gemini_brain.goal_congrats_msg(
                        username=my_data.get("username", "Student"),
                        hours_today=hours_today,
                        goal_hours=goal_hours,
                    )

                    embed = discord.Embed(
                        title=f"🎉 Daily Goal Complete!",
                        description=body,
                        color=0x57F287,  # Green — positive achievement
                    )
                    embed.add_field(
                        name="📊 Today's Stats",
                        value=f"⏱️ Studied: **{hours_today:.1f}h**\n🎯 Goal: **{goal_hours:.1f}h** ✅\n💤 You've earned your rest.",
                        inline=False,
                    )
                    embed.set_footer(text=f"YPT Study Bot • {time_now_str} IST — No more reminders for today!")

                    try:
                        await member.send(embed=embed)
                        self._congrats_sent[uid_str] = today_str
                        logging.info(f"[DISCIPLINE] Sent goal-congrats DM to {my_data.get('username', uid_str)}")

                        # Follow up immediately with a "push past the limit" hype DM
                        extra_hours = goal_hours + 2.0  # push target = goal + 2h
                        push_body = await gemini_brain.push_past_limit_msg(
                            username=my_data.get("username", "Student"),
                            hours_today=hours_today,
                            goal_hours=goal_hours,
                            hours_left=hours_left,
                        )

                        push_embed = discord.Embed(
                            title="⚡ Now Push Past It.",
                            description=push_body,
                            color=0xFFD700,  # Gold — elite energy
                        )
                        push_embed.add_field(
                            name="🏆 Topper Target",
                            value=f"Your goal: **{goal_hours:.1f}h** ✅\nNext milestone: **{extra_hours:.0f}h**\nHours left today: **{hours_left:.1f}h**",
                            inline=False,
                        )
                        push_embed.set_footer(text="YPT Study Bot • The goal was the floor, not the ceiling.")
                        await member.send(embed=push_embed)
                        logging.info(f"[DISCIPLINE] Sent push-past-limit DM to {my_data.get('username', uid_str)}")

                    except discord.Forbidden:
                        logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} for congrats")
                    except Exception as e:
                        logging.error(f"[DISCIPLINE] Congrats DM error for {uid_str}: {e}")
                    continue

                # -------------------------------------------------------
                # BRANCH 2 & 3: Nag branches — check cooldown first
                # -------------------------------------------------------
                last_nag = self._gap_nag_sent.get(uid_str)
                if last_nag is not None:
                    elapsed = (now_ist - last_nag).total_seconds()
                    if elapsed < 25 * 60:
                        continue

                embed_color = _urgency_color(hour)

                if state == STATE_DROPPED_OFF:
                    # Gemini-generated encouraging reminder
                    body = await gemini_brain.dropped_off_reminder(
                        username=my_data.get("username", "Student"),
                        hours_today=hours_today,
                        goal_hours=goal_hours,
                        hours_left=hours_left,
                        time_str=time_now_str,
                        peer_name=other_name,
                        peer_hours=other_hours,
                    )

                    embed = discord.Embed(
                        title=f"💪 {time_now_str} IST — Keep Going!",
                        description=body,
                        color=0xFEE75C,  # Yellow — warm, encouraging
                    )
                    embed.add_field(
                        name="📊 Your Progress",
                        value=f"✅ Studied: **{hours_today:.1f}h**\n🎯 Goal: **{goal_hours:.1f}h**\n📈 Remaining: **{gap:.1f}h**",
                        inline=False,
                    )
                    embed.set_footer(
                        text=f"Your today: {hours_today:.1f}h  |  Goal: {goal_hours:.1f}h  |  {time_now_str} IST"
                    )

                elif state == STATE_NOT_STARTED:
                    # Gemini-generated harsh "you haven't started" reminder
                    body = await gemini_brain.not_started_reminder(
                        username=my_data.get("username", "Student"),
                        time_str=time_now_str,
                        goal_hours=goal_hours,
                        hours_left=hours_left,
                        peer_name=other_name,
                        peer_hours=other_hours,
                    )

                    embed = discord.Embed(
                        title=f"🔴 {time_now_str} IST — You Haven't Started.",
                        description=body,
                        color=0xFF0000,
                    )
                    embed.add_field(
                        name="⏰ Time's Running Out",
                        value=f"📅 Today's goal: **{goal_hours:.1f}h**\n⌛ Hours left today: **{hours_left:.1f}h**\n{other_name} already has **{other_hours:.1f}h** logged.",
                        inline=False,
                    )
                    embed.set_footer(
                        text=f"{other_name}'s today: {other_hours:.1f}h  |  {time_now_str} IST"
                    )
                else:
                    continue

                try:
                    await member.send(embed=embed)
                    self._gap_nag_sent[uid_str] = now_ist
                    logging.info(
                        f"[DISCIPLINE] Sent gap reminder ({state}) to {my_data.get('username', uid_str)}"
                    )
                except discord.Forbidden:
                    logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} for gap reminder")
                except Exception as e:
                    logging.error(f"[DISCIPLINE] Gap reminder error for {uid_str}: {e}")

        except Exception as e:
            logging.error(f"[DISCIPLINE] Error in study_gap_reminder_loop: {e}", exc_info=True)

    @study_gap_reminder_loop.before_loop
    async def before_gap_reminder(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK 4: DAILY ABSENCE CALLOUT (mention in study channel)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def daily_absence_callout(self):
        """At 10 AM IST, mention users in the study text channel who didn't study yesterday."""
        try:
            now_ist = get_ist_now()

            # Only trigger at 10:00-10:09 AM IST
            if now_ist.hour != 10 or now_ist.minute >= 10:
                return

            data = await self.bot.load_data()
            loop_state = data.setdefault("meta", {}).setdefault("puzzle_loop_state", {})
            if loop_state.get("absence_callout_date") == now_ist.date().isoformat():
                return

            loop_state["absence_callout_date"] = now_ist.date().isoformat()
            async with self.bot.db_write_lock:
                await self.bot.save_data(data)

            logging.info("[DISCIPLINE] Running daily absence callout...")
            users = data.get("users", {})

            study_channel = await self.bot.get_or_fetch_channel(STUDY_TEXT_CHANNEL_ID)
            if not study_channel:
                logging.error("[DISCIPLINE] Study text channel not found")
                return

            yesterday = (now_ist.date() - datetime.timedelta(days=1)).isoformat()
            absent_mentions = []

            for uid_str in list(users.keys()):
                try:
                    uid_int = int(uid_str)
                except ValueError:
                    continue

                guild = study_channel.guild
                member = guild.get_member(uid_int)
                if not member:
                    try:
                        member = await guild.fetch_member(uid_int)
                    except Exception:
                        member = None
                if not member:
                    continue

                yesterday_seconds = users[uid_str].get("daily_history", {}).get(yesterday, 0)
                if yesterday_seconds == 0:
                    absent_mentions.append(f"<@{uid_str}>")

            if absent_mentions:
                mentions_str = " ".join(absent_mentions)
                await study_channel.send(
                    f"\U0001f6a8 **ABSENT YESTERDAY:** {mentions_str}\n\n"
                    f"You studied **0 hours** yesterday. Everyone can see this.\n"
                    f"Get in a study channel TODAY or face consequences. \U0001f480"
                )
                logging.info(f"[DISCIPLINE] Called out {len(absent_mentions)} absent user(s)")
        except Exception as e:
            logging.error(f"[DISCIPLINE] Error in daily_absence_callout loop: {e}", exc_info=True)

    @daily_absence_callout.before_loop
    async def before_callout(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(DisciplineCog(bot))
    logging.info("[DISCIPLINE] Loaded Discipline Extension")
