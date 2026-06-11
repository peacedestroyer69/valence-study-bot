# --- WRITTEN BY GEMINI ---
# Discipline Extension: Daily punishment system for missed study days.
# This is an isolated cog. Delete this file to remove all discipline features
# without affecting the main bot.py.

import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import logging
import json
import os

DATA_FILE = "study_data.json"


def load_data_sync():
    """Synchronous load for the discipline cog."""
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}


def save_data_sync(data):
    """Synchronous save for the discipline cog."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"[DISCIPLINE] Failed to save data: {e}")


# Hardcoded user IDs for this 2-person server
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"

# General voice channel (used to fetch guild object)
GENERAL_CHANNEL_ID = 1514187630374289418

# How many consecutive zero-study days before kick
STRIKES_TO_WARN = 3
STRIKES_TO_KICK = 4

# Rotating toxic DM messages so they feel different each time
TOXIC_MESSAGES = [
    "You studied for **0 hours** yesterday.\n\nMeanwhile, **{other_name}** ground out **{other_hours:.1f} hours**.\n\nAre you even trying anymore? This is embarrassing. Get back to work.",
    "**0 hours.** Zero. Nothing. Nada.\n\n**{other_name}** put in **{other_hours:.1f} hours** while you were doing... what exactly?\n\nDo better. Seriously.",
    "Another day wasted. **0 hours** studied.\n\n**{other_name}** managed **{other_hours:.1f} hours**. You couldn't even do 1 minute?\n\nThis is a pattern. Fix it.",
    "Imagine having goals and then studying **0 hours**.\n\n**{other_name}** clocked **{other_hours:.1f} hours**. The gap is growing.\n\nYou're falling behind. Wake up.",
]


class DisciplineCog(commands.Cog):
    """Daily punishment system: toxic DMs, public warnings, and auto-kicks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._toxic_index = 0
        self.daily_discipline_check.start()

    def cog_unload(self):
        self.daily_discipline_check.cancel()

    @tasks.loop(minutes=10)
    async def daily_discipline_check(self):
        """Runs every 10 minutes. Fires punishment logic at midnight IST."""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset

        # Only trigger in the 00:00-00:09 window
        if now_ist.hour == 0 and now_ist.minute < 10:
            logging.info("[DISCIPLINE] Running daily midnight discipline check...")
            await self.execute_punishments()
            # Sleep 12 hours to prevent re-firing in the same window
            await asyncio.sleep(3600 * 12)

    @daily_discipline_check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def execute_punishments(self):
        """Check each user's yesterday study hours and apply punishments."""
        data = load_data_sync()
        users = data.get("users", {})

        general_channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if not general_channel:
            logging.error("[DISCIPLINE] Could not find General channel.")
            return

        guild = general_channel.guild

        for uid_str in [VALENCE_ID, UJJWAL_ID]:
            if uid_str not in users:
                continue

            other_uid_str = UJJWAL_ID if uid_str == VALENCE_ID else VALENCE_ID
            other_user_data = users.get(other_uid_str, {})

            my_data = users[uid_str]

            # Calculate yesterday's date in IST
            now_ist = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                hours=5, minutes=30
            )
            yesterday = (now_ist - datetime.timedelta(days=1)).date().isoformat()

            my_seconds = my_data.get("daily_history", {}).get(yesterday, 0)
            other_seconds = other_user_data.get("daily_history", {}).get(yesterday, 0)

            strikes = my_data.get("discipline_strikes", 0)

            if my_seconds == 0:
                # ---- SLACKER DETECTED ----
                strikes += 1
                my_data["discipline_strikes"] = strikes
                save_data_sync(data)

                member = guild.get_member(int(uid_str))
                other_name = other_user_data.get("username", "your partner")
                other_hours = other_seconds / 3600

                # 1. TOXIC DM
                if member:
                    try:
                        msg_template = TOXIC_MESSAGES[
                            self._toxic_index % len(TOXIC_MESSAGES)
                        ]
                        self._toxic_index += 1

                        embed = discord.Embed(
                            title="\U0001f480 Zero Hours Recorded. Pathetic.",
                            description=msg_template.format(
                                other_name=other_name, other_hours=other_hours
                            ),
                            color=0xFF0000,
                        )
                        embed.set_footer(
                            text=f"Strike {strikes}/{STRIKES_TO_KICK} \u2014 {STRIKES_TO_KICK} strikes = Auto-Kick"
                        )
                        await member.send(embed=embed)
                        logging.info(
                            f"[DISCIPLINE] Sent toxic DM to {my_data.get('username', uid_str)} (strike {strikes})"
                        )
                    except discord.Forbidden:
                        logging.warning(
                            f"[DISCIPLINE] Cannot DM {uid_str} (DMs disabled)"
                        )

                # 2. PUBLIC WARNING at strike 3
                if strikes == STRIKES_TO_WARN:
                    await general_channel.send(
                        f"\u26a0\ufe0f <@{uid_str}> **WARNING!** You have missed "
                        f"{STRIKES_TO_WARN} consecutive days of studying. "
                        f"If you do not study today, you will be **KICKED** "
                        f"from the server tonight."
                    )

                # 3. AUTO-KICK at strike 4+
                elif strikes >= STRIKES_TO_KICK:
                    if member:
                        try:
                            await member.kick(
                                reason=f"Missed {strikes} consecutive days of study."
                            )
                            await general_channel.send(
                                f"\U0001f528 <@{uid_str}> has been **kicked** from the server "
                                f"for missing {strikes} consecutive days of study."
                            )
                            logging.info(
                                f"[DISCIPLINE] Kicked {my_data.get('username', uid_str)}"
                            )
                        except discord.Forbidden:
                            await general_channel.send(
                                f"\u274c I tried to kick <@{uid_str}> for missing "
                                f"{strikes} days, but I lack the permissions!"
                            )
            else:
                # ---- STUDIED: Reset strikes ----
                if strikes > 0:
                    my_data["discipline_strikes"] = 0
                    save_data_sync(data)
                    logging.info(
                        f"[DISCIPLINE] Reset strikes for {my_data.get('username', uid_str)} "
                        f"(studied {my_seconds/3600:.1f}h yesterday)"
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(DisciplineCog(bot))
    logging.info("[DISCIPLINE] Loaded Discipline Extension")
