import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DATA_DRAGON_URL = "https://ddragon.leagueoflegends.com"

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_patch_version = None

# --- Riot API i Scraper ---
class RiotAPI:
    @staticmethod
    def get_latest_patch():
        try:
            versions = requests.get(f"{DATA_DRAGON_URL}/api/versions.json").json()
            return versions[0]
        except Exception as e:
            print(f"Błąd pobierania wersji patcha: {e}")
            return None

    @staticmethod
    def get_patch_data(version):
        patch_url = f"https://www.leagueoflegends.com/en-us/news/game-updates/patch-{version.replace('.', '-')}-notes/"
        try:
            response = requests.get(patch_url)
            response.raise_for_status()
        except Exception as e:
            print(f"Błąd pobierania patcha: {e}")
            return None

        soup = BeautifulSoup(response.text, 'lxml')

        result = []

        # Champions section
        champions_section = soup.find('h2', string=lambda s: s and "champion" in s.lower())
        if champions_section:
            result.append("**🧙‍♂️ Champion Changes:**")
            for tag in champions_section.find_all_next(['h3', 'p']):
                if tag.name == 'h2':
                    break
                if tag.name == 'h3':
                    result.append(f"\n**{tag.get_text(strip=True)}**")
                elif tag.name == 'p':
                    text = tag.get_text(strip=True)
                    if text:
                        result.append(f"> {text}")

        # Items section
        items_section = soup.find('h2', string=lambda s: s and "item" in s.lower())
        if items_section:
            result.append("\n\n**🛡️ Item Changes:**")
            for tag in items_section.find_all_next(['h3', 'p']):
                if tag.name == 'h2':
                    break
                if tag.name == 'h3':
                    result.append(f"\n**{tag.get_text(strip=True)}**")
                elif tag.name == 'p':
                    text = tag.get_text(strip=True)
                    if text:
                        result.append(f"> {text}")

        return "\n".join(result) if result else None

# --- Discord Events i Commands ---
@tasks.loop(hours=24)
async def check_patches():
    global last_patch_version
    version = RiotAPI.get_latest_patch()
    if version and version != last_patch_version:
        data = RiotAPI.get_patch_data(version)
        if data:
            last_patch_version = version
            message = f"**Patch {version} Detected!**\n\n{data[:1900]}"
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(message)

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    if not check_patches.is_running():
        check_patches.start()

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def patch(ctx):
    version = RiotAPI.get_latest_patch()
    if not version:
        await ctx.send("❌ Nie udało się pobrać wersji patcha.")
        return
    data = RiotAPI.get_patch_data(version)
    if not data:
        await ctx.send("❌ Nie udało się pobrać danych patcha.")
        return
    await ctx.send(f"**Patch {version}**\n{data[:1900]}")

# --- Flask Keep-alive ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot running"

if __name__ == '__main__':
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.run(TOKEN)
