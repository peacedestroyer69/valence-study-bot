# --- WRITTEN BY GEMINI ---
import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import logging
import json
import os

DATA_FILE = "study_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class DisciplineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_discipline_check.start()
        
    def cog_unload(self):
        self.daily_discipline_check.cancel()

    @tasks.loop(minutes=10)
    async def daily_discipline_check(self):
        """Runs every 10 minutes to check if it's exactly midnight IST to run the punishment."""
        now_utc = datetime.datetime.now(datetime.UTC)
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        now_ist = now_utc + ist_offset
        
        if now_ist.hour == 0 and now_ist.minute < 10:
            logging.info("[DISCIPLINE] Running daily midnight discipline check...")
            await self.execute_punishments()
            await asyncio.sleep(3600 * 12)

    @daily_discipline_check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def execute_punishments(self):
        data = load_data()
        users = data.get("users", {})
        
        VALENCE_ID = "856485470171299891"
        UJJWAL_ID = "1403716456025165864"
        
        general_channel = self.bot.get_channel(1514187630374289418)
        if not general_channel:
            logging.error("[DISCIPLINE] Could not find General channel to fetch guild.")
            return
            
        guild = general_channel.guild
        
        for uid_str in [VALENCE_ID, UJJWAL_ID]:
            if uid_str not in users:
                continue
                
            other_uid_str = UJJWAL_ID if uid_str == VALENCE_ID else VALENCE_ID
            other_user_data = users.get(other_uid_str, {})
            
            my_data = users[uid_str]
            yesterday = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=5, minutes=30) - datetime.timedelta(days=1)).date().isoformat()
            
            my_history = my_data.get("daily_history", {})
            other_history = other_user_data.get("daily_history", {})
            
            my_seconds = my_history.get(yesterday, 0)
            other_seconds = other_history.get(yesterday, 0)
            
            strikes = my_data.get("discipline_strikes", 0)
            
            if my_seconds == 0:
                strikes += 1
                my_data["discipline_strikes"] = strikes
                save_data(data)
                
                member = guild.get_member(int(uid_str))
                other_name = other_user_data.get('username', 'your partner')
                other_hours = other_seconds / 3600
                
                if member:
                    try:
                        embed = discord.Embed(
                            title="\U0001f480 Zero Hours Recorded. Pathetic.",
                            description=f"You studied for **0 hours** yesterday.\n\nMeanwhile, **{other_name}** ground out **{other_hours:.1f} hours**.\n\nAre you even trying anymore? This is embarrassing. Get back to work.",
                            color=0xFF0000
                        )
                        embed.set_footer(text=f"Current Strike: {strikes}/4 (4 = Auto-Kick)")
                        await member.send(embed=embed)
                    except discord.Forbidden:
                        pass
                
                if strikes == 3:
                    await general_channel.send(f"\u26a0\ufe0f <@{uid_str}> **WARNING!** You have missed 3 days of studying. If you do not study today, you will be **KICKED** from the server tonight.")
                elif strikes >= 4:
                    if member:
                        try:
                            await member.kick(reason="Missed 4 days of study. Disappointing.")
                            await general_channel.send(f"\U0001f528 <@{uid_str}> has been **kicked** from the server for missing 4 consecutive days of study.")
                        except discord.Forbidden:
                            await general_channel.send(f"\u274c I tried to kick <@{uid_str}> for missing 4 days, but I lack the Permissions!")
            else:
                if strikes > 0:
                    my_data["discipline_strikes"] = 0
                    save_data(data)

async def setup(bot):
    await bot.add_cog(DisciplineCog(bot))
    logging.info("Loaded Discipline Extension")
