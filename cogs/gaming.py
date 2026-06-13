# --- WRITTEN BY GEMINI ---
# Gaming Extension: Chess/Lichess auto-tracking, match commands, voice channel poking.
# This is an isolated cog. Delete this file to remove all gaming features without
# affecting the main bot.py.

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import logging
import json
import os

import firebase_admin
from firebase_admin import firestore

DATA_FILE = "study_data.json"


def load_data_sync():
    """Synchronous load for the gaming cog from Firestore."""
    if firebase_admin._apps:
        try:
            db = firestore.client()
            doc_ref = db.collection('bot_data').document('main')
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            logging.error(f"[GAMING] Firestore load error: {e}")

    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}


def save_data_sync(data):
    """Synchronous save for the gaming cog to Firestore."""
    if firebase_admin._apps:
        try:
            db = firestore.client()
            db.collection('bot_data').document('main').set(data)
        except Exception as e:
            logging.error(f"[GAMING] Firestore save error: {e}")

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"[GAMING] Failed to save data: {e}")


# Game voice channel IDs
GAME_CHANNELS = {
    1514624613743857775,  # Chess
    1514624657935044738,  # Shogi
    1514624725102628945,  # GO
    1514624781692178683,  # Checkers
}

# Text channel to send poke messages and match announcements
CHESS_TEXT_CHANNEL_ID = 1514667734355542188  # Chess Text
POKE_TEXT_CHANNEL_ID = 1514667734355542188   # Chess Text (poke goes here too)

# General channel (fallback for announcements)
GENERAL_CHANNEL_ID = 1514187630374289418

# User IDs
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"


class GamingCog(commands.Cog):
    """Handles game tracking, chess API polling, and break-time poking."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.chess_poll_loop.start()

    def cog_unload(self):
        self.chess_poll_loop.cancel()

    # ------------------------------------------------------------------
    # SLASH COMMAND: /link_chess
    # ------------------------------------------------------------------
    @app_commands.command(
        name="link_chess",
        description="Link your Lichess or Chess.com account for auto-tracking.",
    )
    @app_commands.describe(
        platform="Choose Lichess or Chess.com",
        username="Your username on the platform",
    )
    @app_commands.choices(
        platform=[
            app_commands.Choice(name="Lichess", value="lichess"),
            app_commands.Choice(name="Chess.com", value="chesscom"),
        ]
    )
    async def link_chess(
        self,
        interaction: discord.Interaction,
        platform: app_commands.Choice[str],
        username: str,
    ):
        data = load_data_sync()
        uid = str(interaction.user.id)

        if uid not in data["users"]:
            data["users"][uid] = {"username": interaction.user.display_name}

        if "chess_accounts" not in data["users"][uid]:
            data["users"][uid]["chess_accounts"] = {}

        data["users"][uid]["chess_accounts"][platform.value] = username
        save_data_sync(data)

        await interaction.response.send_message(
            f"✅ Successfully linked **{platform.name}** account: `{username}`",
            ephemeral=True,
        )
        logging.info(
            f"[GAMING] {interaction.user.display_name} linked {platform.name}: {username}"
        )

    # ------------------------------------------------------------------
    # SLASH COMMAND: /game_match
    # ------------------------------------------------------------------
    @app_commands.command(
        name="game_match", description="Announce a new game match."
    )
    @app_commands.describe(
        game="The game being played (e.g. Chess, Shogi, GO, Checkers)",
        time_format="Time control or format (e.g. Blitz 5min, Standard, Fischer)",
        opponent="Who you are playing against",
    )
    async def game_match(
        self,
        interaction: discord.Interaction,
        game: str,
        time_format: str,
        opponent: discord.Member,
    ):
        embed = discord.Embed(
            title="🎮 NEW MATCH STARTED 🎮",
            description=(
                f"**{interaction.user.mention}** vs **{opponent.mention}**\n\n"
                f"🎲 Game: **{game}**\n"
                f"⏱️ Format: **{time_format}**"
            ),
            color=0x5865F2,
        )
        embed.set_footer(text="Use /game_result to record the winner!")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # SLASH COMMAND: /game_result
    # ------------------------------------------------------------------
    @app_commands.command(
        name="game_result", description="Record the winner of a game."
    )
    @app_commands.describe(
        winner="The player who won",
        loser="The player who lost",
    )
    async def game_result(
        self,
        interaction: discord.Interaction,
        winner: discord.Member,
        loser: discord.Member,
    ):
        data = load_data_sync()

        for uid in [str(winner.id), str(loser.id)]:
            if uid not in data["users"]:
                data["users"][uid] = {}
            data["users"][uid].setdefault("gaming_wins", 0)
            data["users"][uid].setdefault("gaming_losses", 0)

        data["users"][str(winner.id)]["gaming_wins"] += 1
        data["users"][str(loser.id)]["gaming_losses"] += 1
        save_data_sync(data)

        w_wins = data["users"][str(winner.id)]["gaming_wins"]
        l_wins = data["users"][str(loser.id)]["gaming_wins"]

        embed = discord.Embed(
            title="🏆 MATCH RESULT 🏆",
            description=(
                f"**{winner.mention}** defeated **{loser.mention}**!\n\n"
                f"📊 **{winner.display_name}**: {w_wins}W / {data['users'][str(winner.id)]['gaming_losses']}L\n"
                f"📊 **{loser.display_name}**: {l_wins}W / {data['users'][str(loser.id)]['gaming_losses']}L"
            ),
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # SLASH COMMAND: /gaming_stats
    # ------------------------------------------------------------------
    @app_commands.command(
        name="gaming_stats", description="View gaming win/loss stats."
    )
    @app_commands.describe(user="The user to check stats for (defaults to you)")
    async def gaming_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        target = user or interaction.user
        data = load_data_sync()
        uid = str(target.id)
        udata = data.get("users", {}).get(uid, {})

        wins = udata.get("gaming_wins", 0)
        losses = udata.get("gaming_losses", 0)
        total = wins + losses
        winrate = (wins / total * 100) if total > 0 else 0

        chess_accounts = udata.get("chess_accounts", {})
        lichess = chess_accounts.get("lichess", "Not linked")
        chesscom = chess_accounts.get("chesscom", "Not linked")

        embed = discord.Embed(
            title=f"🎮 {target.display_name}'s Gaming Stats",
            color=0x5865F2,
        )
        embed.add_field(name="🏆 Wins", value=str(wins), inline=True)
        embed.add_field(name="💀 Losses", value=str(losses), inline=True)
        embed.add_field(name="📊 Win Rate", value=f"{winrate:.0f}%", inline=True)
        embed.add_field(name="♟️ Lichess", value=f"`{lichess}`", inline=True)
        embed.add_field(name="♞ Chess.com", value=f"`{chesscom}`", inline=True)
        embed.set_footer(text=f"Total matches: {total}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # VOICE LISTENER: Poke users who join game channels
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        # Only trigger when someone JOINS a game channel (not when leaving or switching within)
        if after.channel and after.channel.id in GAME_CHANNELS:
            if not before.channel or before.channel.id not in GAME_CHANNELS:
                await asyncio.sleep(5)
                text_channel = self.bot.get_channel(POKE_TEXT_CHANNEL_ID)
                if text_channel:
                    game_name = after.channel.name
                    await text_channel.send(
                        f"👀 Yo {member.mention}, hopping into **{game_name}**? "
                        f"Start a match with `/game_match` so I can track it!"
                    )

    # ------------------------------------------------------------------
    # BACKGROUND TASK: Poll Lichess API for auto-resolved matches
    # ------------------------------------------------------------------
    @tasks.loop(minutes=5)
    async def chess_poll_loop(self):
        """Polls Lichess every 5 minutes for head-to-head matches between Valence and Ujjwal."""
        data = load_data_sync()
        users = data.get("users", {})

        val_data = users.get(VALENCE_ID, {})
        ujj_data = users.get(UJJWAL_ID, {})

        val_lichess = val_data.get("chess_accounts", {}).get("lichess")
        ujj_lichess = ujj_data.get("chess_accounts", {}).get("lichess")

        if not val_lichess or not ujj_lichess:
            return  # Both users must have linked accounts

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/x-ndjson"}
                url = f"https://lichess.org/api/games/user/{val_lichess}?vs={ujj_lichess}&max=1"

                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return

                    game_data_raw = await resp.text()
                    if not game_data_raw.strip():
                        return

                    # NDJSON: split on actual newline, take first line
                    first_line = game_data_raw.strip().split("\n")[0]
                    game_data = json.loads(first_line)
                    game_id = game_data.get("id")

                    if not game_id:
                        return

                    # Check if we already processed this game
                    processed_games = data.get("processed_chess_games", [])
                    if game_id in processed_games:
                        return

                    winner_color = game_data.get("winner")
                    if not winner_color:
                        return  # Draw or ongoing

                    # Determine who won
                    winner_username = (
                        game_data.get("players", {})
                        .get(winner_color, {})
                        .get("user", {})
                        .get("name", "")
                    )

                    if winner_username.lower() == val_lichess.lower():
                        winner_discord = f"<@{VALENCE_ID}>"
                        loser_discord = f"<@{UJJWAL_ID}>"
                        winner_id = VALENCE_ID
                        loser_id = UJJWAL_ID
                    else:
                        winner_discord = f"<@{UJJWAL_ID}>"
                        loser_discord = f"<@{VALENCE_ID}>"
                        winner_id = UJJWAL_ID
                        loser_id = VALENCE_ID

                    # Update gaming stats
                    for uid in [winner_id, loser_id]:
                        if uid not in data["users"]:
                            data["users"][uid] = {}
                        data["users"][uid].setdefault("gaming_wins", 0)
                        data["users"][uid].setdefault("gaming_losses", 0)

                    data["users"][winner_id]["gaming_wins"] += 1
                    data["users"][loser_id]["gaming_losses"] += 1

                    # Announce in chess text channel
                    speed = game_data.get("speed", "unknown")
                    channel = self.bot.get_channel(
                        CHESS_TEXT_CHANNEL_ID
                    ) or self.bot.get_channel(GENERAL_CHANNEL_ID)

                    if channel:
                        embed = discord.Embed(
                            title="🤖 AUTO-RESOLVED CHESS MATCH 🤖",
                            description=(
                                f"{winner_discord} destroyed {loser_discord} on Lichess!\n\n"
                                f"⚡ Speed: **{speed.capitalize()}**\n"
                                f"🆔 Game: `{game_id}`"
                            ),
                            color=0x57F287,
                        )
                        embed.set_footer(text="Pulled automatically from Lichess API")
                        await channel.send(embed=embed)

                    # Mark game as processed (keep last 50)
                    processed_games.append(game_id)
                    data["processed_chess_games"] = processed_games[-50:]
                    save_data_sync(data)

                    logging.info(
                        f"[GAMING] Auto-resolved Lichess game {game_id}: "
                        f"{winner_username} won ({speed})"
                    )

        except Exception as e:
            logging.error(f"[GAMING] Error polling Lichess: {e}")

    @chess_poll_loop.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GamingCog(bot))
    logging.info("[GAMING] Loaded Gaming Extension")
