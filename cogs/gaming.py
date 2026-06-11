# --- WRITTEN BY GEMINI ---
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import logging
import json
import os
from typing import Optional

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

class GamingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chess_poll_loop.start()

    def cog_unload(self):
        self.chess_poll_loop.cancel()

    @app_commands.command(name="link_chess", description="Link your Lichess or Chess.com account for auto-tracking.")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Lichess", value="lichess"),
        app_commands.Choice(name="Chess.com", value="chesscom")
    ])
    async def link_chess(self, interaction: discord.Interaction, platform: app_commands.Choice[str], username: str):
        data = load_data()
        uid = str(interaction.user.id)
        if uid not in data["users"]:
            data["users"][uid] = {}
            
        if "chess_accounts" not in data["users"][uid]:
            data["users"][uid]["chess_accounts"] = {}
            
        data["users"][uid]["chess_accounts"][platform.value] = username
        save_data(data)
        
        await interaction.response.send_message(f"\u2705 Successfully linked **{platform.name}** account: `{username}`", ephemeral=True)

    @app_commands.command(name="game_match", description="Manually start a game match.")
    async def game_match(self, interaction: discord.Interaction, game: str, format: str, opponent: discord.Member):
        await interaction.response.send_message(
            f"\U0001f3ae **NEW MATCH STARTED** \U0001f3ae\n"
            f"**{interaction.user.mention}** vs **{opponent.mention}**\n"
            f"Game: `{game}` | Format: `{format}`\n\n"
            f"*Good luck! May the best brain win.*"
        )

    @app_commands.command(name="game_result", description="Manually record the winner of a game.")
    async def game_result(self, interaction: discord.Interaction, winner: discord.Member, loser: discord.Member):
        data = load_data()
        uid = str(winner.id)
        loser_id = str(loser.id)
        
        for u in [uid, loser_id]:
            if u not in data["users"]: data["users"][u] = {}
            if "gaming_wins" not in data["users"][u]: data["users"][u]["gaming_wins"] = 0
            if "gaming_losses" not in data["users"][u]: data["users"][u]["gaming_losses"] = 0
            
        data["users"][uid]["gaming_wins"] += 1
        data["users"][loser_id]["gaming_losses"] += 1
        save_data(data)
        
        await interaction.response.send_message(f"\U0001f3c6 **{winner.mention}** just crushed **{loser.mention}**! A monumental victory.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        GAME_CHANNELS = {
            1514624613743857775,  # Chess
            1514624657935044738,  # Shogi
            1514624725102628945,  # GO
            1514624781692178683   # Checkers
        }
        if after.channel and after.channel.id in GAME_CHANNELS and (not before.channel or before.channel.id not in GAME_CHANNELS):
            await asyncio.sleep(5)
            text_channel = self.bot.get_channel(1514241642415001610)
            if text_channel:
                game_name = after.channel.name if hasattr(after.channel, 'name') else "a board game"
                await text_channel.send(f"\U0001f440 Yo {member.mention}, taking a break with {game_name}? Start a match with `/game_match` so I can track it!")

    @tasks.loop(minutes=5)
    async def chess_poll_loop(self):
        """Polls Lichess for auto-resolved matches between the two specific users."""
        data = load_data()
        users = data.get("users", {})
        
        VALENCE_ID = "856485470171299891"
        UJJWAL_ID = "1403716456025165864"
        
        val_data = users.get(VALENCE_ID, {})
        ujj_data = users.get(UJJWAL_ID, {})
        
        val_lichess = val_data.get("chess_accounts", {}).get("lichess")
        ujj_lichess = ujj_data.get("chess_accounts", {}).get("lichess")
        
        if val_lichess and ujj_lichess:
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {"Accept": "application/x-ndjson"}
                    url = f"https://lichess.org/api/games/user/{val_lichess}?vs={ujj_lichess}&max=1"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            game_data_raw = await resp.text()
                            if game_data_raw.strip():
                                game_data = json.loads(game_data_raw.split("\n")[0])
                                game_id = game_data.get("id")
                                
                                processed_games = data.get("processed_chess_games", [])
                                if game_id not in processed_games:
                                    winner_color = game_data.get("winner")
                                    if winner_color:
                                        winner_username = game_data.get("players", {}).get(winner_color, {}).get("user", {}).get("name")
                                        if winner_username.lower() == val_lichess.lower():
                                            winner_discord = f"<@{VALENCE_ID}>"
                                            loser_discord = f"<@{UJJWAL_ID}>"
                                        else:
                                            winner_discord = f"<@{UJJWAL_ID}>"
                                            loser_discord = f"<@{VALENCE_ID}>"
                                            
                                        channel = self.bot.get_channel(1514187630374289418) or self.bot.get_channel(1514241642415001610)
                                        if channel:
                                            await channel.send(f"\U0001f916 **AUTO-RESOLVED CHESS MATCH:** \U0001f916\n{winner_discord} destroyed {loser_discord} on Lichess! The game has been recorded.")
                                            
                                        processed_games.append(game_id)
                                        data["processed_chess_games"] = processed_games[-50:]
                                        save_data(data)
            except Exception as e:
                logging.error(f"Error polling Lichess: {e}")

    @chess_poll_loop.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(GamingCog(bot))
    logging.info("Loaded Gaming Extension")
