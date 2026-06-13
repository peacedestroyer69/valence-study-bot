import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
import os
import logging
import aiohttp
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Discord Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

class ChessBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

bot = ChessBot()

# Constants
CHESS_DATA_FILE = "chess_data.json"
VALENCE_ID = 856485470171299891
UJJWAL_ID = 1403716456025165864

CHESS_VOICE = 1514624613743857775
SHOGI_VOICE = 1514624657935044738
GO_VOICE = 1514624725102628945
CHECKERS_VOICE = 1514624781692178683
GAME_VOICE_CHANNELS = {
    CHESS_VOICE: "Chess",
    SHOGI_VOICE: "Shogi",
    GO_VOICE: "GO",
    CHECKERS_VOICE: "Checkers"
}
CHESS_TEXT_CHANNEL_ID = 1514667734355542188
GENERAL_CHANNEL_ID = 1514187630374289418

# Utility functions for data management
async def load_chess_data():
    if not os.path.exists(CHESS_DATA_FILE):
        default_data = {
            "users": {},
            "meta": {"head_to_head": {"Valence_Wins": 0, "Ujjwal_Wins": 0, "Draws": 0}}
        }
        with open(CHESS_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        return default_data
    with open(CHESS_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

async def save_chess_data(data):
    with open(CHESS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Keep-Alive Web Server on Port 8081
async def handle_ping(request):
    return web.Response(text="Chess Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle_ping)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8081)
    await site.start()
    logging.info("Chess Bot Keep-alive server started on port 8081")

@bot.event
async def on_ready():
    logging.info(f"Chess Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"Error syncing commands: {e}")
    
    await start_web_server()
    if not game_master_polling_loop.is_running():
        game_master_polling_loop.start()

# Slash Commands
@bot.tree.command(name="link_chess", description="Link your Chess.com or Lichess account")
@app_commands.describe(platform="Platform (chesscom/lichess)", username="Your username")
@app_commands.choices(platform=[
    app_commands.Choice(name="Chess.com", value="chesscom"),
    app_commands.Choice(name="Lichess", value="lichess")
])
async def link_chess(interaction: discord.Interaction, platform: str, username: str):
    try:
        data = await load_chess_data()
        uid = str(interaction.user.id)
        if uid not in data["users"]:
            data["users"][uid] = {"name": interaction.user.display_name}
        
        if platform == "chesscom":
            data["users"][uid]["chesscom_username"] = username
        elif platform == "lichess":
            data["users"][uid]["lichess_username"] = username
            
        await save_chess_data(data)
        await interaction.response.send_message(f"✅ Successfully linked your **{platform}** account to **{username}**!", ephemeral=True)
    except Exception as e:
        logging.error(f"Link error: {e}")
        await interaction.response.send_message("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="game_match", description="Announce a new match")
@app_commands.describe(opponent="Opponent", game="Game", time_control="E.g., 5|0 blitz")
@app_commands.choices(game=[
    app_commands.Choice(name="Chess", value="chess"),
    app_commands.Choice(name="Shogi", value="shogi"),
    app_commands.Choice(name="GO", value="go"),
    app_commands.Choice(name="Checkers", value="checkers"),
])
async def game_match(interaction: discord.Interaction, opponent: discord.Member, game: str, time_control: str = "Standard"):
    embed = discord.Embed(
        title=f"🎮 Break Time Match!",
        description=f"<@{interaction.user.id}> and <@{opponent.id}> are playing **{game.capitalize()}**!\n\n**Format:** {time_control}",
        color=0xE74C3C
    )
    if game == "chess":
        embed.set_footer(text="Auto-tracking enabled!")
    else:
        embed.set_footer(text="Use /game_result to log the winner!")
        
    await interaction.response.send_message(content=f"<@{opponent.id}>", embed=embed)

@bot.tree.command(name="game_result", description="Manually log the winner of a match")
async def game_result(interaction: discord.Interaction, winner: discord.Member = None):
    if interaction.user.id not in [VALENCE_ID, UJJWAL_ID]:
        await interaction.response.send_message("❌ Only Valence and Ujjwal can use head-to-head tracking.", ephemeral=True)
        return

    data = await load_chess_data()
    stats = data["meta"].setdefault("head_to_head", {"Valence_Wins": 0, "Ujjwal_Wins": 0, "Draws": 0})
    
    msg = ""
    if winner is None:
        stats["Draws"] += 1
        msg = "🤝 The match ended in a **Draw**!"
    elif winner.id == VALENCE_ID:
        stats["Valence_Wins"] += 1
        msg = "🏆 **Valence** won the match!"
    elif winner.id == UJJWAL_ID:
        stats["Ujjwal_Wins"] += 1
        msg = "🏆 **Ujjwal** won the match!"
    else:
        await interaction.response.send_message("❌ Winner must be Valence or Ujjwal.", ephemeral=True)
        return

    await save_chess_data(data)
    
    embed = discord.Embed(title="Game Result Logged", description=msg, color=0xF1C40F)
    embed.add_field(name="Head-to-Head", value=f"Valence: {stats['Valence_Wins']} | Ujjwal: {stats['Ujjwal_Wins']} | Draws: {stats['Draws']}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_stats", description="Show head-to-head scorecard")
async def gaming_stats(interaction: discord.Interaction):
    data = await load_chess_data()
    stats = data["meta"].get("head_to_head", {"Valence_Wins": 0, "Ujjwal_Wins": 0, "Draws": 0})
    
    embed = discord.Embed(title="⚔️ Head-to-Head ⚔️", color=0x9B59B6)
    embed.add_field(name="Valence Wins", value=f"**{stats.get('Valence_Wins', 0)}**")
    embed.add_field(name="Ujjwal Wins", value=f"**{stats.get('Ujjwal_Wins', 0)}**")
    embed.add_field(name="Draws", value=f"**{stats.get('Draws', 0)}**")
    
    await interaction.response.send_message(embed=embed)

# Voice Channel Event for Games
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    if after.channel and after.channel.id in GAME_VOICE_CHANNELS:
        if before.channel and before.channel.id == after.channel.id:
            return
        
        game_name = GAME_VOICE_CHANNELS[after.channel.id]
        chess_ch = bot.get_channel(CHESS_TEXT_CHANNEL_ID)
        
        embed = discord.Embed(
            title="🎮 Game Challenge!",
            description=f"**{member.display_name}** has entered the **{game_name}** voice channel!\nAre you ready for a match?",
            color=0x2ECC71
        )
        if chess_ch:
            await chess_ch.send(content=f"<@{VALENCE_ID if member.id == UJJWAL_ID else UJJWAL_ID}>", embed=embed)

# Auto-polling Task
@tasks.loop(minutes=5)
async def game_master_polling_loop():
    try:
        data = await load_chess_data()
        v_data = data["users"].get(str(VALENCE_ID), {})
        u_data = data["users"].get(str(UJJWAL_ID), {})
        
        # 1. Lichess
        v_lichess = v_data.get("lichess_username")
        u_lichess = u_data.get("lichess_username")
        
        if v_lichess and u_lichess:
            url = f"https://lichess.org/api/games/user/{v_lichess}?vs={u_lichess}&max=1"
            headers = {"Accept": "application/x-ndjson"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        ndjson_data = await resp.text()
                        if ndjson_data.strip():
                            game_data = json.loads(ndjson_data.strip().split('\n')[0])
                            game_id = game_data.get("id")
                            last_fetched = data["meta"]["head_to_head"].get("last_fetched_lichess_id")
                            
                            if game_id and game_id != last_fetched:
                                data["meta"]["head_to_head"]["last_fetched_lichess_id"] = game_id
                                winner_color = game_data.get("winner")
                                if not winner_color:
                                    data["meta"]["head_to_head"]["Draws"] += 1
                                    result_msg = "🤝 Draw!"
                                else:
                                    white_user = game_data.get("players", {}).get("white", {}).get("user", {}).get("name", "").lower()
                                    black_user = game_data.get("players", {}).get("black", {}).get("user", {}).get("name", "").lower()
                                    winning_user = white_user if winner_color == "white" else black_user
                                    
                                    if winning_user == v_lichess.lower():
                                        data["meta"]["head_to_head"]["Valence_Wins"] += 1
                                        result_msg = "🏆 **Valence** won!"
                                    elif winning_user == u_lichess.lower():
                                        data["meta"]["head_to_head"]["Ujjwal_Wins"] += 1
                                        result_msg = "🏆 **Ujjwal** won!"
                                        
                                await save_chess_data(data)
                                text_ch = bot.get_channel(CHESS_TEXT_CHANNEL_ID)
                                if text_ch:
                                    embed = discord.Embed(title="♟️ New Lichess Result!", description=result_msg, color=0x3498DB)
                                    embed.add_field(name="Link", value=f"https://lichess.org/{game_id}")
                                    await text_ch.send(embed=embed)
                                    
        # 2. Chess.com
        v_chesscom = v_data.get("chesscom_username")
        u_chesscom = u_data.get("chesscom_username")
        if v_chesscom and u_chesscom:
            url = f"https://api.chess.com/pub/player/{v_chesscom}/games/archives"
            headers = {"User-Agent": "Discord Game Master (Contact: example@example.com)"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        archives_data = await resp.json()
                        archives = archives_data.get("archives", [])
                        if archives:
                            latest = archives[-1]
                            async with session.get(latest, headers=headers) as arch_resp:
                                if arch_resp.status == 200:
                                    games_data = await arch_resp.json()
                                    for g in reversed(games_data.get("games", [])):
                                        w = g.get("white", {}).get("username", "").lower()
                                        b = g.get("black", {}).get("username", "").lower()
                                        if (w == v_chesscom.lower() and b == u_chesscom.lower()) or (w == u_chesscom.lower() and b == v_chesscom.lower()):
                                            game_url = g.get("url")
                                            last_fetched = data["meta"]["head_to_head"].get("last_fetched_chess_id")
                                            if game_url and game_url != last_fetched:
                                                data["meta"]["head_to_head"]["last_fetched_chess_id"] = game_url
                                                w_res = g.get("white", {}).get("result")
                                                b_res = g.get("black", {}).get("result")
                                                w_user = g.get("white", {}).get("username", "").lower()
                                                if w_res == "win": winning_user = w_user
                                                elif b_res == "win": winning_user = g.get("black", {}).get("username", "").lower()
                                                else: winning_user = None
                                                
                                                if winning_user is None:
                                                    data["meta"]["head_to_head"]["Draws"] += 1
                                                    result_msg = "🤝 Draw!"
                                                elif winning_user == v_chesscom.lower():
                                                    data["meta"]["head_to_head"]["Valence_Wins"] += 1
                                                    result_msg = "🏆 **Valence** won!"
                                                elif winning_user == u_chesscom.lower():
                                                    data["meta"]["head_to_head"]["Ujjwal_Wins"] += 1
                                                    result_msg = "🏆 **Ujjwal** won!"
                                                
                                                await save_chess_data(data)
                                                text_ch = bot.get_channel(CHESS_TEXT_CHANNEL_ID)
                                                if text_ch:
                                                    embed = discord.Embed(title="♟️ New Chess.com Result!", description=result_msg, color=0x3498DB)
                                                    embed.add_field(name="Link", value=f"[View Game]({game_url})")
                                                    await text_ch.send(embed=embed)
                                                break
    except Exception as e:
        logging.error(f"Polling error: {e}")

if __name__ == "__main__":
    bot.run(os.getenv("CHESS_BOT_TOKEN") or os.getenv("BOT_TOKEN"))
