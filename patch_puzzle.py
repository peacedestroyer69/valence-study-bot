
with open('cogs/puzzle_cog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line numbers for the post_puzzle_now command block
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '@app_commands.command(name="post_puzzle_now"' in line:
        start_idx = i
    if start_idx and i > start_idx and line.strip().startswith('async def setup('):
        end_idx = i
        break

print(f"Block found: lines {start_idx+1} to {end_idx}")

new_block = [
    '    @app_commands.command(name="post_puzzle_now", description="Force post today\'s daily puzzle instantly (Admin only)")\n',
    '    @app_commands.default_permissions(administrator=True)\n',
    '    async def post_puzzle_now(self, interaction: discord.Interaction):\n',
    '        # Immediately defer to prevent Discord 3-second timeout\n',
    '        await interaction.response.defer(ephemeral=True)\n',
    '        now_ist = get_ist_now()\n',
    '\n',
    '        # Send a live status message we can edit when done\n',
    '        status_msg = await interaction.followup.send(\n',
    '            "\u23f3 **Generating puzzle via Gemini pipeline...**\\n"\n',
    '            "Brainstorm \u2192 Select Best \u2192 Verify \u00d72 \u2192 DM all members. Allow up to 90s.",\n',
    '            ephemeral=True,\n',
    '            wait=True,\n',
    '        )\n',
    '\n',
    '        async def _run_in_background():\n',
    '            try:\n',
    '                success = await self._post_daily_puzzle(now_ist, force=True)\n',
    '                if success:\n',
    '                    await status_msg.edit(content=(\n',
    '                        "\u2705 **Puzzle posted!** Gemini brainstormed, selected the best, "\n',
    '                        "double-verified the logic, and DMed it to all members. \U0001f9e9"\n',
    '                    ))\n',
    '                else:\n',
    '                    await status_msg.edit(content=(\n',
    '                        "\u274c **Failed to post puzzle.**\\n"\n',
    '                        "\u2022 Puzzle channel not found \u2014 check `PUZZLE_CHANNEL_ID` env var\\n"\n',
    '                        "\u2022 Gemini pipeline crashed \u2014 check bot logs for full traceback"\n',
    '                    ))\n',
    '            except Exception as err:\n',
    '                logging.error(f"[PUZZLE] post_puzzle_now bg task crashed: {err}", exc_info=True)\n',
    '                try:\n',
    '                    await status_msg.edit(content=f"\u274c **Error:** `{err}`\\nSee bot logs.")\n',
    '                except Exception:\n',
    '                    pass\n',
    '\n',
    '        asyncio.create_task(_run_in_background())\n',
    '\n',
    '\n',
]

lines[start_idx:end_idx] = new_block

with open('cogs/puzzle_cog.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("SUCCESS! post_puzzle_now patched.")
