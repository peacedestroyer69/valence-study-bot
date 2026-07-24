import sys

with open('cogs/puzzle_cog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if 'app_commands.command(name="post_puzzle_now"' in line:
        start_idx = i
    if start_idx is not None and i > start_idx and 'async def setup(' in line:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print(f"ERROR: could not locate block. start={start_idx} end={end_idx}")
    sys.exit(1)

print(f"Replacing lines {start_idx+1} to {end_idx}")

new_block = """\
    @app_commands.command(name="post_puzzle_now", description="Force post today's daily puzzle instantly (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_puzzle_now(self, interaction: discord.Interaction):
        # Immediately defer - prevents Discord 3-second interaction timeout
        await interaction.response.defer(ephemeral=True)
        now_ist = get_ist_now()

        # Post a live status embed we will edit once the slow Gemini pipeline finishes
        status_msg = await interaction.followup.send(
            "\u23f3 **Generating puzzle via Gemini brainstorm pipeline...**\\n"
            "Stages: Brainstorm 3 options \u2192 Select best \u2192 Verify \u00d72 \u2192 DM all members\\n"
            "_Allow up to 90 seconds._",
            ephemeral=True,
            wait=True,
        )

        async def _bg():
            try:
                success = await self._post_daily_puzzle(now_ist, force=True)
                if success:
                    await status_msg.edit(content=(
                        "\u2705 **Puzzle posted!** Brainstormed, best selected, "
                        "logic verified twice, and DMed to all members. \U0001f9e9"
                    ))
                else:
                    await status_msg.edit(content=(
                        "\u274c **Failed to post puzzle.**\\n"
                        "\u2022 Puzzle channel not found? Check `PUZZLE_CHANNEL_ID` env var\\n"
                        "\u2022 Gemini pipeline error? Check bot logs for full traceback."
                    ))
            except Exception as err:
                logging.error(f"[PUZZLE] post_puzzle_now bg task error: {err}", exc_info=True)
                try:
                    await status_msg.edit(content=f"\u274c **Crashed:** `{err}`\\nSee bot logs.")
                except Exception:
                    pass

        asyncio.create_task(_bg())


"""

new_lines = [line + '\n' for line in new_block.split('\n')]
# Remove trailing extra newlines from split, replace block
lines[start_idx:end_idx] = [new_block]

with open('cogs/puzzle_cog_patched.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("SUCCESS: written to cogs/puzzle_cog_patched.py")
