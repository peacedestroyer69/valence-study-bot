# --- DISCIPLINE EXTENSION ---
# Features:
#   1. Midnight punishment: toxic DMs for 0-hour days, comparing to partner's stats
#   2. Hourly nagging from 2 PM to 10 PM IST if not currently studying
#   3. Auto-kick after 4 consecutive missed days with harsh DM + permanent invite
#   4. Daily mention in study text channel for absent users
#   5. Strike system: 3 = public warning, 4 = kicked
#
# Delete this file to remove all discipline features without affecting bot.py.

import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import logging
import json
import os

import firebase_admin
from firebase_admin import firestore

# DATA_FILE removed, cogs use self.bot database methods

# ---- Channel & User IDs ----
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"
GENERAL_CHANNEL_ID = 1514241642415001610  # #study-discussion text channel (was General meet voice channel)
STUDY_TEXT_CHANNEL_ID = 1514241642415001610  # #study-discussion for public callouts

# Study voice channels (used to check if someone is currently studying)
STUDY_VOICE_CHANNELS = {1514208313452007514, 1514596473629708298, 1514244606827561171}

# ---- Strike Config ----
STRIKES_TO_WARN = 3
STRIKES_TO_KICK = 4

# ---- Permanent invite link (set by the bot or hardcoded) ----
# The bot will try to create one on startup. Fallback to this:
SERVER_INVITE_LINK = None  # Will be set dynamically in cog_load


# Synchronous file load/save functions removed. Using self.bot.load_data() and self.bot.save_data() instead.


# ============================================================
# TOXIC MIDNIGHT MESSAGES (rotating, ego-destroying)
# ============================================================
TOXIC_MESSAGES = [
    "You studied for **0 hours** yesterday.\n\nMeanwhile, **{other_name}** ground out **{other_hours:.1f} hours**.\n\nAre you even trying anymore? This is embarrassing. Get back to work.",
    "**0 hours.** Zero. Nothing. Nada.\n\n**{other_name}** put in **{other_hours:.1f} hours** while you were doing... what exactly?\n\nDo better. Seriously.",
    "Another day wasted. **0 hours** studied.\n\n**{other_name}** managed **{other_hours:.1f} hours**. You couldn't even do 1 minute?\n\nThis is a pattern. Fix it.",
    "Imagine having goals and then studying **0 hours**.\n\n**{other_name}** clocked **{other_hours:.1f} hours**. The gap is growing.\n\nYou're falling behind. Wake up.",
    "You know what **0 hours** gets you? Nothing. No rank. No progress. No future.\n\n**{other_name}** studied **{other_hours:.1f} hours**. They're moving. You're not.",
    "Bro really logged **0 hours** and went to sleep thinking everything's fine 💀\n\n**{other_name}**: **{other_hours:.1f} hours**. You: **0**. Do the math.",
]

# ============================================================
# HOURLY NAGGING MESSAGES (2 PM to 10 PM IST, escalating)
# Used on REGULAR days (Mon, Tue, Thu, Fri)
# ============================================================
HOURLY_NAG_MESSAGES = {
    14: "📖 It's 2 PM. Afternoon's here — perfect time to start a study session. Don't waste it.",
    15: "⏳ 3 PM already. Have you started studying yet? **{other_name}** has **{other_today:.1f}h** logged today. Clock's ticking.",
    16: "📚 4 PM. The day is slipping away. **{other_name}** is at **{other_today:.1f}h**. You: **{my_today:.1f}h**. Get moving.",
    17: "⏰ 5 PM. Still not in a study channel? **{other_name}** has already put in **{other_today:.1f}h** today. What's your excuse?",
    18: "🔥 6 PM already. Half the evening is GONE. Get in a voice channel and start grinding. NOW.",
    19: "😤 It's 7 PM and you're STILL not studying?! **{other_name}** is at **{other_today:.1f}h** today. You have **{my_today:.1f}h**. Embarrassing.",
    20: "💀 8 PM. You've wasted the ENTIRE afternoon. If you don't start RIGHT NOW, today is a total L. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**.",
    21: "🚨 **9 PM.** This is your LAST WARNING before the day is over. Get your ass in a study channel or accept that you're a failure today. **{other_name}** did **{other_today:.1f}h**. You did **{my_today:.1f}h**. PATHETIC.",
    22: "☠️ **10 PM. The day is basically over.** You had 18 hours to study and you chose to waste them. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**. Tomorrow better be different or you're getting KICKED.",
}

# ============================================================
# OFF-DAY MORNING NAG MESSAGES (6 AM to 1 PM IST)
# Used ONLY on off days (Wed, Sat, Sun) — PW schedule
# Focused on waking up and getting started early
# ============================================================
OFF_DAYS = {2, 5, 6}  # Wednesday=2, Saturday=5, Sunday=6

OFF_DAY_MORNING_MESSAGES = {
    6:  "🌅 **6 AM. It's your OFF DAY.** The best students use off days to get AHEAD. Wake up. Get out of bed. Start before everyone else.",
    7:  "⏰ **7 AM — WAKE UP.** You're burning daylight. Off day doesn't mean lazy day. **{other_name}** might already be up. Don't fall behind.",
    8:  "☀️ **8 AM.** Still in bed? That's 2 hours of potential study GONE. Your competitors are already at their desks. **GET. UP. NOW.**",
    9:  "😤 **9 AM and you haven't started?!** That's 3 hours wasted. Off day = BONUS study time, not sleep-all-day time. **{other_name}** has **{other_today:.1f}h** already.",
    10: "🔥 **10 AM.** If you're not studying by now, you're choosing to lose. It's your OFF DAY — you have NO excuses today. Zero. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**.",
    11: "💀 **11 AM — HALF THE MORNING IS GONE.** Every hour you sleep in is an hour **{other_name}** uses to get ahead. They have **{other_today:.1f}h** today. You have **{my_today:.1f}h**. Disgusting.",
    12: "🚨 **IT'S NOON.** You've wasted the ENTIRE morning of your off day. 6 hours of potential study — GONE. **{other_name}**: **{other_today:.1f}h**. You: **{my_today:.1f}h**. What are you even doing?",
    13: "☠️ **1 PM on your OFF DAY and you've done {my_today:.1f}h.** That's pathetic. **{other_name}** has **{other_today:.1f}h**. You had since 6 AM. The afternoon is your LAST CHANCE to salvage today.",
}


# ============================================================
# KICK DM MESSAGE (sent right before kicking)
# ============================================================
KICK_DM_TEMPLATE = (
    "# 🔨 YOU'VE BEEN KICKED\n\n"
    "You missed **{strikes} consecutive days** of studying. That's unacceptable.\n\n"
    "This server is for people who are **SERIOUS** about their goals. "
    "If you're not going to put in the work, don't waste a spot.\n\n"
    "**If you actually want to change**, here's the invite link. "
    "But only rejoin if you're ready to GRIND:\n{invite_link}\n\n"
    "*This is your wake-up call. Next time, there won't be one.*"
)


class DisciplineCog(commands.Cog):
    """Daily punishment system: toxic DMs, hourly nagging, public callouts, and auto-kicks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._toxic_index = 0
        self._invite_link = SERVER_INVITE_LINK
        self.daily_discipline_check.start()
        self.hourly_nag_check.start()
        self.daily_absence_callout.start()

    def cog_unload(self):
        self.daily_discipline_check.cancel()
        self.hourly_nag_check.cancel()
        self.daily_absence_callout.cancel()

    async def _get_invite_link(self, guild: discord.Guild) -> str:
        """Get or create a permanent invite link for the server."""
        if self._invite_link:
            return self._invite_link

        try:
            # Try to find an existing permanent invite
            invites = await guild.invites()
            for inv in invites:
                if inv.max_age == 0 and inv.max_uses == 0:
                    self._invite_link = str(inv)
                    return self._invite_link

            # Create a new permanent invite
            general = self.bot.get_channel(GENERAL_CHANNEL_ID)
            if general:
                inv = await general.create_invite(max_age=0, max_uses=0, reason="Discipline system - permanent invite for kicked users")
                self._invite_link = str(inv)
                return self._invite_link
        except Exception as e:
            logging.error(f"[DISCIPLINE] Failed to get/create invite: {e}")

        return "*(Could not generate invite link — ask your friend to re-invite you)*"

    def _is_user_studying(self, guild: discord.Guild, user_id: int) -> bool:
        """Check if a user is currently in any study voice channel."""
        member = guild.get_member(user_id)
        if member and member.voice and member.voice.channel:
            return member.voice.channel.id in STUDY_VOICE_CHANNELS
        return False

    # ==================================================================
    # TASK 1: MIDNIGHT DISCIPLINE CHECK (strikes, toxic DMs, kicks)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def daily_discipline_check(self):
        """Runs every 10 minutes. Fires punishment logic at midnight IST."""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        # Only trigger in the 00:00–00:09 window
        if now_ist.hour == 0 and now_ist.minute < 10:
            logging.info("[DISCIPLINE] Running daily midnight discipline check...")
            await self.execute_punishments()
            # Sleep 12 hours to prevent re-firing
            await asyncio.sleep(3600 * 12)

    @daily_discipline_check.before_loop
    async def before_discipline(self):
        await self.bot.wait_until_ready()

    async def execute_punishments(self):
        """Check each user's yesterday study hours and apply punishments."""
        data = await self.bot.load_data()
        users = data.get("users", {})

        general_channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if not general_channel:
            logging.error("[DISCIPLINE] Could not find General channel.")
            return

        guild = general_channel.guild

        # Sort users by yesterday's seconds to find comparison peers
        now_ist = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=5, minutes=30)
        yesterday = (now_ist - datetime.timedelta(days=1)).date().isoformat()

        yesterday_seconds_list = []
        for u_id, u_data in users.items():
            sec = u_data.get("daily_history", {}).get(yesterday, 0)
            yesterday_seconds_list.append((u_id, sec))
        yesterday_seconds_list.sort(key=lambda x: x[1], reverse=True)

        for uid_str in list(users.keys()):
            # Find the other user to compare against (the top studier yesterday, or second if this user was top)
            other_uid_str = None
            other_seconds = 0
            if len(yesterday_seconds_list) > 1:
                if yesterday_seconds_list[0][0] == uid_str:
                    other_uid_str = yesterday_seconds_list[1][0]
                    other_seconds = yesterday_seconds_list[1][1]
                else:
                    other_uid_str = yesterday_seconds_list[0][0]
                    other_seconds = yesterday_seconds_list[0][1]

            other_user_data = users.get(other_uid_str, {}) if other_uid_str else {}
            my_data = users[uid_str]

            # Calculate yesterday's date in IST
            now_ist = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=5, minutes=30)
            yesterday = (now_ist - datetime.timedelta(days=1)).date().isoformat()

            my_seconds = my_data.get("daily_history", {}).get(yesterday, 0)
            other_seconds = other_user_data.get("daily_history", {}).get(yesterday, 0)
            strikes = my_data.get("discipline_strikes", 0)

            if my_seconds == 0:
                # ---- SLACKER DETECTED ----
                strikes += 1
                my_data["discipline_strikes"] = strikes
                async with self.bot.db_write_lock:
                    await self.bot.save_data(data)

                try:
                    uid_int = int(uid_str)
                    member = guild.get_member(uid_int)
                    if not member:
                        member = await guild.fetch_member(uid_int)
                except Exception:
                    member = None
                if other_uid_str:
                    other_name = other_user_data.get("username", "your partner")
                    other_hours = other_seconds / 3600
                else:
                    other_name = "the daily goal"
                    other_hours = 1.5

                # 1. TOXIC DM
                if member:
                    try:
                        msg_template = TOXIC_MESSAGES[self._toxic_index % len(TOXIC_MESSAGES)]
                        self._toxic_index += 1

                        embed = discord.Embed(
                            title="💀 Zero Hours Recorded. Pathetic.",
                            description=msg_template.format(
                                other_name=other_name, other_hours=other_hours
                            ),
                            color=0xFF0000,
                        )
                        embed.set_footer(
                            text=f"Strike {strikes}/{STRIKES_TO_KICK} — {STRIKES_TO_KICK} strikes = Auto-Kick"
                        )
                        await member.send(embed=embed)
                        logging.info(f"[DISCIPLINE] Sent toxic DM to {my_data.get('username', uid_str)} (strike {strikes})")
                    except discord.Forbidden:
                        logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} (DMs disabled)")

                # 2. PUBLIC WARNING at strike 3
                if strikes == STRIKES_TO_WARN:
                    await general_channel.send(
                        f"⚠️ <@{uid_str}> **WARNING!** You have missed "
                        f"{STRIKES_TO_WARN} consecutive days of studying. "
                        f"If you do not study today, you will be **KICKED** "
                        f"from the server tonight."
                    )

                # 3. AUTO-KICK at strike 4+
                elif strikes >= STRIKES_TO_KICK:
                    if member:
                        try:
                            # Send harsh DM with invite link BEFORE kicking
                            invite_link = await self._get_invite_link(guild)
                            kick_msg = KICK_DM_TEMPLATE.format(
                                strikes=strikes, invite_link=invite_link
                            )
                            try:
                                embed = discord.Embed(
                                    title="🔨 KICKED FROM STUDY BOI",
                                    description=kick_msg,
                                    color=0xFF0000,
                                )
                                await member.send(embed=embed)
                            except discord.Forbidden:
                                pass  # Can't DM, still kick

                            # Now kick
                            await member.kick(reason=f"Missed {strikes} consecutive days of study.")
                            await general_channel.send(
                                f"🔨 <@{uid_str}> has been **kicked** from the server "
                                f"for missing {strikes} consecutive days of study.\n"
                                f"They received a DM with an invite link to rejoin — "
                                f"**only if they're serious this time.**"
                            )
                            logging.info(f"[DISCIPLINE] Kicked {my_data.get('username', uid_str)}")
                        except discord.Forbidden:
                            await general_channel.send(
                                f"❌ I tried to kick <@{uid_str}> for missing "
                                f"{strikes} days, but I lack the permissions!"
                            )
            else:
                # ---- STUDIED: Reset strikes ----
                if strikes > 0:
                    my_data["discipline_strikes"] = 0
                    async with self.bot.db_write_lock:
                        await self.bot.save_data(data)
                    logging.info(
                        f"[DISCIPLINE] Reset strikes for {my_data.get('username', uid_str)} "
                        f"(studied {my_seconds/3600:.1f}h yesterday)"
                    )

    # ==================================================================
    # TASK 2: HOURLY NAGGING
    # Off days (Wed/Sat/Sun): 6 AM - 10 PM IST
    # Regular days (Mon/Tue/Thu/Fri): 2 PM - 10 PM IST
    # ==================================================================
    @tasks.loop(minutes=5)
    async def hourly_nag_check(self):
        """Checks every 5 minutes. Sends nag DMs based on schedule:
        - Off days (Wed/Sat/Sun): 6 AM to 10 PM IST (wake-up + study)
        - Regular days (Mon/Tue/Thu/Fri): 2 PM to 10 PM IST"""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

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

        # Prevent double-firing: use a simple attribute flag
        flag_key = f"_nag_sent_{now_ist.date().isoformat()}_{hour}"
        if getattr(self, flag_key, False):
            return
        setattr(self, flag_key, True)

        logging.info(f"[DISCIPLINE] Hourly nag check at {hour}:00 IST")

        data = await self.bot.load_data()
        users = data.get("users", {})

        general_channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if not general_channel:
            return
        guild = general_channel.guild
        # Get today's hours for all users
        today_str = now_ist.date().isoformat()
        today_seconds_list = []
        for u_id, u_data in users.items():
            sec = u_data.get("daily_history", {}).get(today_str, 0)
            today_seconds_list.append((u_id, sec))
        today_seconds_list.sort(key=lambda x: x[1], reverse=True)

        for uid_str in list(users.keys()):
            # Skip if they're currently in a study channel
            if self._is_user_studying(guild, int(uid_str)):
                logging.info(f"[DISCIPLINE] Skipping nag for {uid_str} — currently studying")
                continue

            # Find peer to compare
            other_uid_str = None
            other_today = 0.0
            if len(today_seconds_list) > 1:
                if today_seconds_list[0][0] == uid_str:
                    other_uid_str = today_seconds_list[1][0]
                    other_today = today_seconds_list[1][1] / 3600
                else:
                    other_uid_str = today_seconds_list[0][0]
                    other_today = today_seconds_list[0][1] / 3600

            other_data = users.get(other_uid_str, {}) if other_uid_str else {}
            my_data = users[uid_str]

            # Get today's hours for both users
            today_str = now_ist.date().isoformat()
            my_today = my_data.get("daily_history", {}).get(today_str, 0) / 3600
            if other_uid_str:
                other_today = other_data.get("daily_history", {}).get(today_str, 0) / 3600
                other_name = other_data.get("username", "your partner")
            else:
                other_today = 1.5
                other_name = "the daily goal"

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
                formatted_msg = msg_template.format(
                    other_name=other_name,
                    other_today=other_today,
                    my_today=my_today,
                )

                # Color escalates: morning=blue/green, afternoon=yellow, evening=red
                colors = {
                    6: 0x3498DB, 7: 0x2980B9, 8: 0x57F287, 9: 0xA3BE8C,
                    10: 0xFEE75C, 11: 0xFFA500, 12: 0xFF8C00, 13: 0xFF4500,
                    14: 0x57F287, 15: 0xA3BE8C, 16: 0xFEE75C, 17: 0xFFA500,
                    18: 0xFF8C00, 19: 0xFF4500, 20: 0xFF0000, 21: 0xCC0000, 22: 0x8B0000,
                }

                # Title changes based on time of day
                if hour < 10:
                    title_emoji = "🌅"
                    title_text = "WAKE UP & STUDY"
                elif hour < 14:
                    title_emoji = "☀️"
                    title_text = "Are You Studying Yet?"
                elif hour < 19:
                    title_emoji = "⏰"
                    title_text = "Are You Studying?"
                else:
                    title_emoji = "🚨"
                    title_text = "LAST CHANCE"

                embed = discord.Embed(
                    title=f"{title_emoji} {hour}:00 — {title_text}",
                    description=formatted_msg,
                    color=colors.get(hour, 0xFF0000),
                )
                embed.set_footer(text=f"Your today: {my_today:.1f}h | {other_name}'s today: {other_today:.1f}h")
                await member.send(embed=embed)
                logging.info(f"[DISCIPLINE] Sent {hour}:00 nag to {my_data.get('username', uid_str)}")
            except discord.Forbidden:
                logging.warning(f"[DISCIPLINE] Cannot DM {uid_str} for hourly nag")
            except Exception as e:
                logging.error(f"[DISCIPLINE] Hourly nag error for {uid_str}: {e}")

    @hourly_nag_check.before_loop
    async def before_nag(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # TASK 3: DAILY ABSENCE CALLOUT (mention in study channel)
    # ==================================================================
    @tasks.loop(minutes=10)
    async def daily_absence_callout(self):
        """At 10 AM IST, mention users in the study text channel who didn't study yesterday."""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        # Only trigger at 10:00-10:09 AM IST
        if now_ist.hour != 10 or now_ist.minute >= 10:
            return

        flag_key = f"_callout_sent_{now_ist.date().isoformat()}"
        if getattr(self, flag_key, False):
            return
        setattr(self, flag_key, True)

        logging.info("[DISCIPLINE] Running daily absence callout...")

        data = await self.bot.load_data()
        users = data.get("users", {})

        study_channel = self.bot.get_channel(STUDY_TEXT_CHANNEL_ID)
        if not study_channel:
            logging.error("[DISCIPLINE] Study text channel not found")
            return

        yesterday = (now_ist - datetime.timedelta(days=1)).date().isoformat()
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
                f"🚨 **ABSENT YESTERDAY:** {mentions_str}\n\n"
                f"You studied **0 hours** yesterday. Everyone can see this.\n"
                f"Get in a study channel TODAY or face consequences. 💀"
            )
            logging.info(f"[DISCIPLINE] Called out {len(absent_mentions)} absent user(s)")

    @daily_absence_callout.before_loop
    async def before_callout(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(DisciplineCog(bot))
    logging.info("[DISCIPLINE] Loaded Discipline Extension")
