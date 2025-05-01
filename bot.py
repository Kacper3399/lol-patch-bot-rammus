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

bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
last_patch_version = None

class RiotAPI:
    @staticmethod
    def get_latest_patch():
        try:
            versions = requests.get(f"{DATA_DRAGON_URL}/api/versions.json").json()
            return versions[0]
        except:
            return None

    @staticmethod
    def get_patch_data(version):
        try:
            return requests.get(
                f"{DATA_DRAGON_URL}/patchnotes/{version}.json",
                headers={"X-Riot-Token": RIOT_API_KEY}
            ).json()
        except:
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
            await bot.get_channel(CHANNEL_ID).send(message[:2000])

@bot.event
async def on_ready():
    check_patches.start()

app = Flask(__name__)
@app.route('/')
def home(): return "Bot running"

if __name__ == '__main__':
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.run(TOKEN)