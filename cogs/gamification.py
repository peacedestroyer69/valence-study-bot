import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import logging
import random
import os
import asyncio
from utils import (
    get_ist_now, get_ist_date, IST_TZ, UIColors,
    GENERAL_CHANNEL_ID, VALENCE_ID, UJJWAL_ID
)

# Level brackets and role names
RANK_BRACKETS = [
    {"min": 1, "max": 10, "name": "Aspirant", "color": discord.Color.light_gray()},
    {"min": 11, "max": 30, "name": "JEE Warrior", "color": discord.Color.blue()},
    {"min": 31, "max": 70, "name": "Concepts Master", "color": discord.Color.purple()},
    {"min": 71, "max": 120, "name": "Hardcore Topper", "color": discord.Color.orange()},
    {"min": 121, "max": 9999, "name": "AIR < 100 God", "color": discord.Color.gold()}
]

BOSS_NAMES = [
    "Thermodynamics Titan 🌋",
    "Calculus Chimera 🌀",
    "Organic Overlord 🧪",
    "Rotational Reaper ⚙️"
]

class GamificationCog(commands.Cog):
    """XP engine, leveling roles, badges, and weekly Co-Op Boss Battles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register a listener for study session updates to sync level roles
        self.boss_battle_check_loop.start()

    def cog_unload(self):
        self.boss_battle_check_loop.cancel()

    # Helper: Get Rank metadata for a level
    def get_rank_info(self, level: int):
        for bracket in RANK_BRACKETS:
            if bracket["min"] <= level <= bracket["max"]:
                return bracket
        return RANK_BRACKETS[-1]

    # Helper: Sync member level roles
    async def sync_level_roles(self, member: discord.Member, level: int):
        guild = member.guild
        target_bracket = self.get_rank_info(level)
        
        # 1. Find or create the target rank role
        target_role = discord.utils.get(guild.roles, name=target_bracket["name"])
        if not target_role:
            try:
                target_role = await guild.create_role(
                    name=target_bracket["name"],
                    color=target_bracket["color"],
                    reason="JEE Leveling Role",
                    hoist=True
                )
            except Exception as e:
                logging.error(f"Failed to create leveling role {target_bracket['name']}: {e}")
                return

        # 2. Add new role if not already assigned
        if target_role not in member.roles:
            try:
                await member.add_roles(target_role)
                # Remove other lower brackets roles
                for bracket in RANK_BRACKETS:
                    if bracket["name"] != target_bracket["name"]:
                        old_role = discord.utils.get(guild.roles, name=bracket["name"])
                        if old_role and old_role in member.roles:
                            await member.remove_roles(old_role)
                
                # Public Announcement in study discussion
                channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🎉 LEVEL UP & RANK PROMOTION! 🎉",
                        description=f"🔥 **{member.mention}** has advanced to **Level {level}**!\n"
                                    f"👑 New Rank Role Unlocked: **{target_role.mention}**",
                        color=target_role.color,
                        timestamp=datetime.datetime.now(datetime.UTC)
                    )
                    embed.set_footer(text="The grind never stops. Onwards to the next rank!")
                    await channel.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to sync roles for member {member.display_name}: {e}")

    # Listener: Listen for member update/stats save to sync levels and deal boss damage
    @commands.Cog.listener()
    async def on_study_session_ended(self, member: discord.Member, seconds_studied: int):
        """Custom event called from bot.py when a user finishes a Pomodoro/study session."""
        uid = str(member.id)
        
        # 1. Sync level roles
        data = await self.bot.load_data()
        udata = data.get("users", {}).get(uid, {})
        total_seconds = udata.get("total_seconds_alltime", 0)
        level = int(total_seconds / 3600) + 1
        await self.sync_level_roles(member, level)

        # 2. Check active weekly Co-Op Boss
        hit_info = None
        async with self.bot.db_write_lock:
            data = await self.bot.load_data()
            meta = data.setdefault("meta", {})
            boss = meta.get("active_boss")
            if boss and boss.get("hp", 0) > 0:
                damage = int(seconds_studied / 60)
                if damage > 0:
                    boss["hp"] = max(0, boss["hp"] - damage)
                    damages = boss.setdefault("damages", {})
                    damages[uid] = damages.get(uid, 0) + damage
                    await self.bot.save_data(data)
                    hit_info = {"name": boss['name'], "hp": boss['hp'], "max_hp": boss['max_hp'], "damage": damage}

        # Announce boss hit outside the lock
        if hit_info:
            channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="💥 BOSS HIT!",
                    description=f"⚔️ **{member.display_name}** dealt **{hit_info['damage']}** damage to **{hit_info['name']}**!\n"
                                f"❤️ Boss HP: **{hit_info['hp']} / {hit_info['max_hp']}**",
                    color=0xED4245 if hit_info['hp'] > 0 else 0x57F287
                )
                await channel.send(embed=embed)

    # ------------------------------------------------------------------
    # 1. CO-OP BOSS BATTLES SYSTEM
    # ------------------------------------------------------------------
    @app_commands.command(name="boss", description="View active weekly Co-Op Boss Battle details.")
    async def boss_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        data = await self.bot.load_data()
        boss = data.setdefault("meta", {}).get("active_boss")

        if not boss:
            await interaction.followup.send(
                "📭 No active weekly Boss Battle. Bosses spawn every Wednesday at 9 PM IST! 🕒"
            )
            return

        hp = boss.get("hp", 0)
        max_hp = boss.get("max_hp", 100)
        name = boss.get("name", "Unknown Boss")
        damages = boss.get("damages", {})

        # Draw a custom progress bar for Boss HP
        pct = max(0, int((hp / max_hp) * 100))
        bar_len = 15
        filled = int(pct / (100 / bar_len))
        hp_bar = "🟢" * filled + "🔴" * (bar_len - filled)

        embed = discord.Embed(
            title=f"⚔️ WEEKLY CO-OP BOSS BATTLE: {name}",
            description=f"Collaborate with your partner to defeat the Boss by studying! 1 min studied = 1 damage dealt.",
            color=0xED4245 if hp > 0 else 0x57F287,
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.add_field(
            name=f"❤️ Boss HP: {hp} / {max_hp} ({pct}%)",
            value=f"`[{hp_bar}]`",
            inline=False
        )

        contrib_lines = []
        for uid_str, dmg in damages.items():
            user = self.bot.get_user(int(uid_str))
            username = user.display_name if user else f"User {uid_str}"
            contrib_lines.append(f"• **{username}**: {dmg} damage ({round(dmg/60, 1)}h study)")

        embed.add_field(
            name="📊 Damage Contribution",
            value="\n".join(contrib_lines) if contrib_lines else "*No damage dealt yet!*",
            inline=False
        )

        if hp <= 0:
            embed.set_footer(text="🏆 Boss defeated! Great teamwork!")
        else:
            embed.set_footer(text="⚔️ Keep studying to deal damage! Battle ends Thursday 9 PM IST.")

        await interaction.followup.send(embed=embed)

    # ------------------------------------------------------------------
    # 2. BOSS BATTLE AUTOMATION LOOP
    # ------------------------------------------------------------------
    @tasks.loop(minutes=30)
    async def boss_battle_check_loop(self):
        """Spawns boss on Wednesday 9 PM IST and checks resolution on Thursday 9 PM IST."""
        await self.bot.wait_until_ready()
        try:
            now_ist = get_ist_now()
            today_str = now_ist.date().isoformat()

            # Wednesday 9 PM IST - Spawn Boss
            if now_ist.weekday() == 2 and now_ist.hour == 21:
                spawned_boss_name = None
                async with self.bot.db_write_lock:
                    data = await self.bot.load_data()
                    meta = data.setdefault("meta", {})
                    last_spawn = meta.get("last_boss_spawn_date")
                    
                    if last_spawn != today_str:
                        # Spawn new Boss
                        boss_name = random.choice(BOSS_NAMES)
                        meta["active_boss"] = {
                            "name": boss_name,
                            "max_hp": 480, # 8 hours total study required between the two
                            "hp": 480,
                            "spawn_date": today_str,
                            "damages": {}
                        }
                        meta["last_boss_spawn_date"] = today_str
                        await self.bot.save_data(data)
                        spawned_boss_name = boss_name

                # Announce outside the lock
                if spawned_boss_name:
                    channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            title="🚨 NEW BOSS SPAWNED! 🚨",
                            description=f"The **{spawned_boss_name}** has entered the server!\n"
                                        f"❤️ **HP: 480** (8 hours of combined studying required)\n"
                                        f"⚔️ Study in the VC or use Pomodoro to deal damage! 1 minute = 1 damage.",
                            color=0xED4245,
                            timestamp=datetime.datetime.now(datetime.UTC)
                        )
                        await channel.send(embed=embed)

            # Thursday 9 PM IST - Resolve Battle
            elif now_ist.weekday() == 3 and now_ist.hour == 21:
                resolve_info = None
                async with self.bot.db_write_lock:
                    data = await self.bot.load_data()
                    meta = data.setdefault("meta", {})
                    boss = meta.get("active_boss")
                    last_resolution = meta.get("last_boss_resolution_date")

                    if boss and last_resolution != today_str:
                        name = boss.get("name", "Boss")
                        hp = boss.get("hp", 0)
                        
                        if hp <= 0:
                            # Award badges
                            for uid_str in boss.get("damages", {}).keys():
                                udata = data["users"].setdefault(uid_str, {})
                                badges = udata.setdefault("unlocked_badges", [])
                                if "Boss Slayer" not in badges:
                                    badges.append("Boss Slayer")

                        meta["active_boss"] = None
                        meta["last_boss_resolution_date"] = today_str
                        await self.bot.save_data(data)
                        resolve_info = {"name": name, "hp": hp}

                # Announce outside the lock
                if resolve_info:
                    channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
                    if channel:
                        if resolve_info["hp"] <= 0:
                            # Victorious! Reward participants with "Titan Slayer" badge
                            embed = discord.Embed(
                                title="🏆 BOSS DEFEATED! VICTORY! 🏆",
                                description=f"You successfully defeated **{resolve_info['name']}**!\n"
                                            f"🎁 Every contributor has been awarded the **Boss Slayer** badge!",
                                color=0x57F287,
                                timestamp=datetime.datetime.now(datetime.UTC)
                            )
                            await channel.send(embed=embed)
                        else:
                            embed = discord.Embed(
                                title="💀 BOSS ESCAPED! DEFEAT! 💀",
                                description=f"You failed to defeat **{resolve_info['name']}** in time.\n"
                                            f"❌ Remaining HP: **{resolve_info['hp']} / 480**\n"
                                            f"Get back to studying, slackers!",
                                color=0x99AAB5,
                                timestamp=datetime.datetime.now(datetime.UTC)
                            )
                            await channel.send(embed=embed)
                        
        except Exception as e:
            logging.error(f"[BOSS BATTLE] Error in loop: {e}", exc_info=True)

    @boss_battle_check_loop.before_loop
    async def before_boss_battle(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # 3. BADGES LIST COMMAND
    # ------------------------------------------------------------------
    @app_commands.command(name="badges", description="View your earned study badges.")
    @app_commands.describe(user="The user to view badges for (defaults to yourself)")
    async def badges_command(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        uid = str(target.id)

        data = await self.bot.load_data()
        udata = data.get("users", {}).get(uid, {})
        badges = udata.get("unlocked_badges", [])

        embed = discord.Embed(
            title=f"🏅 {target.display_name}'s Earned Badges",
            color=UIColors.BRAND_PRIMARY,
            timestamp=datetime.datetime.now(datetime.UTC)
        )

        if not badges:
            embed.description = "*No badges earned yet. Complete Co-Op Boss Battles or reach study milestone to earn badges!*"
        else:
            badge_list = "\n".join(f"• 🏆 **{b}**" for b in badges)
            embed.description = f"Here are the medals of honor for your JEE prep:\n\n{badge_list}"

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamificationCog(bot))
