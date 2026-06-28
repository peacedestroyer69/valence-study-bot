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
from bot import get_ist_now, IST_TZ

# Top-level DB file operations removed. Using self.bot.load_data() and self.bot.save_data() instead.


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
GENERAL_CHANNEL_ID = 1514241642415001610  # #study-discussion text channel

# User IDs
VALENCE_ID = "856485470171299891"
UJJWAL_ID = "1403716456025165864"


class GamingCog(commands.Cog):
    """Handles game tracking, chess API polling, and break-time poking."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session = None
        self.chess_poll_loop.start()

    def cog_unload(self):
        self.chess_poll_loop.cancel()
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())

    def get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

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
        await interaction.response.defer(ephemeral=True)
        async with self.bot.db_write_lock:
            data = await self.bot.load_data()
            uid = str(interaction.user.id)

            if uid not in data["users"]:
                data["users"][uid] = {"username": interaction.user.display_name}

            if "chess_accounts" not in data["users"][uid]:
                data["users"][uid]["chess_accounts"] = {}

            data["users"][uid]["chess_accounts"][platform.value] = username
            await self.bot.save_data(data)

        await interaction.followup.send(
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
        await interaction.response.defer(ephemeral=False)
        async with self.bot.db_write_lock:
            data = await self.bot.load_data()

            for uid in [str(winner.id), str(loser.id)]:
                if uid not in data["users"]:
                    data["users"][uid] = {}
                data["users"][uid].setdefault("gaming_wins", 0)
                data["users"][uid].setdefault("gaming_losses", 0)

            data["users"][str(winner.id)]["gaming_wins"] += 1
            data["users"][str(loser.id)]["gaming_losses"] += 1
            await self.bot.save_data(data)

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
        await interaction.followup.send(embed=embed)

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
        await interaction.response.defer(ephemeral=True)
        target = user or interaction.user
        data = await self.bot.load_data()
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
        await interaction.followup.send(embed=embed, ephemeral=True)

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
                text_channel = await self.bot.get_or_fetch_channel(POKE_TEXT_CHANNEL_ID)
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
        """Polls Lichess every 5 minutes for head-to-head matches between all linked users."""
        data = await self.bot.load_data()
        users = data.get("users", {})

        # Build a mapping of lichess_username (lowercase) -> discord_user_id
        lichess_map = {}
        for uid_str, udata in users.items():
            lichess_username = udata.get("chess_accounts", {}).get("lichess")
            if lichess_username:
                lichess_map[lichess_username.lower()] = uid_str

        if len(lichess_map) < 2:
            return

        try:
            session = self.get_session()
            headers = {"Accept": "application/x-ndjson"}
            # Poll Lichess for each user's recent games
            for lichess_username, uid_str in lichess_map.items():
                url = f"https://lichess.org/api/games/user/{lichess_username}?max=5"
                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            continue

                        game_data_raw = await resp.text()
                        if not game_data_raw.strip():
                            continue

                        # Process games line by line (NDJSON format)
                        for line in game_data_raw.strip().split("\n"):
                            if not line.strip():
                                continue
                            game_data = json.loads(line)
                            game_id = game_data.get("id")
                            if not game_id:
                                continue

                            # Check if we already processed this game
                            processed_games = data.get("processed_chess_games", [])
                            if game_id in processed_games:
                                continue

                            # Check if the opponent is also a linked user
                            white_user = game_data.get("players", {}).get("white", {}).get("user", {}).get("name", "")
                            black_user = game_data.get("players", {}).get("black", {}).get("user", {}).get("name", "")

                            if not white_user or not black_user:
                                continue

                            white_lower = white_user.lower()
                            black_lower = black_user.lower()

                            if white_lower in lichess_map and black_lower in lichess_map:
                                # This is a head-to-head match between two linked users!
                                winner_color = game_data.get("winner")
                                if not winner_color:
                                    continue  # Draw or ongoing

                                winner_lichess = white_user if winner_color == "white" else black_user
                                loser_lichess = black_user if winner_color == "white" else white_user

                                winner_id = lichess_map[winner_lichess.lower()]
                                loser_id = lichess_map[loser_lichess.lower()]

                                winner_discord = f"<@{winner_id}>"
                                loser_discord = f"<@{loser_id}>"

                                # Update gaming stats & mark game as processed inside write lock
                                async with self.bot.db_write_lock:
                                    data = await self.bot.load_data()
                                    
                                    # Recheck inside lock
                                    p_games = data.get("processed_chess_games", [])
                                    if game_id in p_games:
                                        continue

                                    for uid in [winner_id, loser_id]:
                                        if uid not in data["users"]:
                                            data["users"][uid] = {}
                                        data["users"][uid].setdefault("gaming_wins", 0)
                                        data["users"][uid].setdefault("gaming_losses", 0)

                                    data["users"][winner_id]["gaming_wins"] += 1
                                    data["users"][loser_id]["gaming_losses"] += 1

                                    p_games.append(game_id)
                                    data["processed_chess_games"] = p_games[-50:]
                                    await self.bot.save_data(data)

                                # Announce in chess text channel
                                speed = game_data.get("speed", "unknown")
                                channel = (
                                    await self.bot.get_or_fetch_channel(CHESS_TEXT_CHANNEL_ID)
                                ) or (
                                    await self.bot.get_or_fetch_channel(GENERAL_CHANNEL_ID)
                                )

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

                                logging.info(
                                    f"[GAMING] Auto-resolved Lichess game {game_id}: "
                                    f"{winner_lichess} won against {loser_lichess} ({speed})"
                                )
                except Exception as e:
                    logging.error(f"[GAMING] Error polling Lichess for {lichess_username}: {e}")
                # Small sleep between polls
                await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"[GAMING] Error in chess_poll_loop: {e}")

    @chess_poll_loop.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GamingCog(bot))
    logging.info("[GAMING] Loaded Gaming Extension")
