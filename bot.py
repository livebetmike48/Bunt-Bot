import os
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import mlb_api
import bunt_rules
import storage

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "20"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bunt_bot")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def et_date_str(offset_days: int = 0) -> str:
    et = datetime.now(timezone.utc) - timedelta(hours=4)
    et += timedelta(days=offset_days)
    return et.strftime("%Y-%m-%d")


def runner_description(situation: dict) -> str:
    bases = []
    if situation["first_occupied"]:
        bases.append("1st")
    if situation["second_occupied"]:
        bases.append("2nd")
    if situation["third_occupied"]:
        bases.append("3rd")
    if len(bases) == 1:
        return f"Runner on {bases[0]} base"
    return f"Runners on {' and '.join(bases)} base"


def build_alert_message(game: dict, situation: dict) -> str:
    matchup = f"{game['away_team']} @ {game['home_team']}"
    inning_str = f"{situation['half']} {situation['inning']}"
    lines = [
        f"🚨 **Bunt Alert** — {matchup} | {inning_str}",
        f"🏃 {runner_description(situation)}",
    ]
    if situation.get("batter_name"):
        lines.append(f"🏏 Up to bat: {situation['batter_name']}")
    return "\n".join(lines)


@tasks.loop(seconds=POLL_SECONDS)
async def poll_games():
    channel_id = storage.get_config("announce_channel_id")
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return

    date_str = et_date_str(0)
    try:
        games = mlb_api.get_live_games(date_str)
    except Exception as e:
        log.error("Failed to fetch schedule: %s", e)
        return

    for game in games:
        if game["abstract_state"] != "Live":
            continue
        try:
            feed = mlb_api.get_live_feed(game["game_pk"])
            situation = mlb_api.get_situation(feed)
        except Exception as e:
            log.error("Failed to fetch/parse feed for game %s: %s", game["game_pk"], e)
            continue

        if not situation:
            continue

        if storage.already_alerted(game["game_pk"], situation["at_bat_index"]):
            continue

        qualifies = bunt_rules.is_bunt_situation(
            situation["half"], situation["inning"], situation["outs"],
            situation["second_occupied"], situation["batting_score"], situation["fielding_score"],
        )
        if not qualifies:
            continue

        storage.mark_alerted(game["game_pk"], situation["at_bat_index"])
        try:
            await channel.send(build_alert_message(game, situation))
            log.info("Posted bunt alert for game %s", game["game_pk"])
        except Exception as e:
            log.error("Failed to send bunt alert for game %s: %s", game["game_pk"], e)


@poll_games.before_loop
async def before_poll():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    storage.init_db()
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash commands", len(synced))
    except Exception as e:
        log.error("Slash command sync failed: %s", e)
    if not poll_games.is_running():
        poll_games.start()
    log.info("Logged in as %s", bot.user)


@bot.tree.command(name="setchannel", description="Set this channel to receive Bunt Alerts")
@app_commands.checks.has_permissions(manage_guild=True)
async def setchannel(interaction: discord.Interaction):
    storage.set_config("announce_channel_id", str(interaction.channel_id))
    await interaction.response.send_message(f"✅ Bunt Alerts will post in {interaction.channel.mention}.")


@bot.tree.command(name="buntwatch", description="Check right now for any live games currently in a bunt situation")
async def buntwatch(interaction: discord.Interaction):
    await interaction.response.defer()
    date_str = et_date_str(0)
    try:
        games = mlb_api.get_live_games(date_str)
    except Exception as e:
        await interaction.followup.send(f"Couldn't reach the MLB API right now: {e}")
        return

    hits = []
    for game in games:
        if game["abstract_state"] != "Live":
            continue
        try:
            feed = mlb_api.get_live_feed(game["game_pk"])
            situation = mlb_api.get_situation(feed)
        except Exception:
            continue
        if not situation:
            continue
        if bunt_rules.is_bunt_situation(
            situation["half"], situation["inning"], situation["outs"],
            situation["second_occupied"], situation["batting_score"], situation["fielding_score"],
        ):
            hits.append((game, situation))

    if not hits:
        await interaction.followup.send("No live bunt situations right now.")
        return

    messages = [build_alert_message(g, s) for g, s in hits]
    await interaction.followup.send("\n\n".join(messages))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your .env file (see .env.example).")
    bot.run(TOKEN)
