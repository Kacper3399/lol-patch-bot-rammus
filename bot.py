import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
DATA_DRAGON_URL = "https://ddragon.leagueoflegends.com"

# Dodano message_content intent
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_patch_version = None

class RiotAPI:
    @staticmethod
    def get_latest_patch():
        try:
            versions = requests.get(f"{DATA_DRAGON_URL}/api/versions.json").json()
            return versions[0]
        except Exception as e:
            print(f"Error fetching latest patch: {e}")
            return None

    @staticmethod
    def get_patch_data(version):
        try:
            return requests.get(
                f"{DATA_DRAGON_URL}/patchnotes/{version}.json",
                headers={"X-Riot-Token": RIOT_API_KEY}
            ).json()
        except Exception as e:
            print(f"Error fetching patch data: {e}")
            return None

@tasks.loop(hours=24)
async def check_patches():
    global last_patch_version
    version = RiotAPI.get_latest_patch()
    if version and version != last_patch_version:
        data = RiotAPI.get_patch_data(version)
        if data:
            last_patch_version = version
            message = f"**Patch {version}**\n\n"
            if 'champions' in data:
                message += "**CHANGES:**\n" + "\n".join(
                    f"{champ['name']}: {change['description']}" 
                    for champ in data['champions'] 
                    for change in champ['changes']
                )
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(message[:2000])

@bot.event
async def on_ready():
    if not check_patches.is_running():
        check_patches.start()

# ✅ Komenda !ping
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# ✅ Komenda !patch
@bot.command()
async def patch(ctx):
    version = RiotAPI.get_latest_patch()
    if not version:
        await ctx.send("Nie udało się pobrać wersji patcha.")
        return
    data = RiotAPI.get_patch_data(version)
    if not data:
        await ctx.send("Nie udało się pobrać danych patcha.")
        return
    message = f"**Patch {version}**\n\n"
    if 'champions' in data:
        message += "**CHANGES:**\n" + "\n".join(
            f"{champ['name']}: {change['description']}" 
            for champ in data['champions'] 
            for change in champ['changes']
        )
    await ctx.send(message[:2000])

# Flask keep-alive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot running"

if __name__ == '__main__':
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.run(TOKEN)
