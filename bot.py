import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
import os
from datetime import datetime

# --- ENV ---
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DATA_DRAGON_URL = "https://ddragon.leagueoflegends.com"

# --- Discord Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_patch_version = None

# --- Riot API & Scraper ---
class RiotAPI:
    @staticmethod
    def get_latest_patch():
        try:
            versions = requests.get(f"{DATA_DRAGON_URL}/api/versions.json").json()
            return versions[0]  # przykład: "14.9.1"
        except Exception as e:
            print(f"Błąd pobierania wersji patcha: {e}")
            return None

    @staticmethod
    def get_patch_data(version):
        try:
            major, minor = version.split('.')[:2]
            season_number = datetime.now().year - 2000  # np. 2025 → 25
            patch_url = f"https://www.leagueoflegends.com/en-us/news/game-updates/patch-{season_number}-{int(minor):02d}-notes/"
        except Exception as e:
            print(f"Nieprawidłowy format wersji: {version} | {e}")
            return None

        try:
            response = requests.get(patch_url)
            if response.status_code != 200:
                print(f"Patch page returned {response.status_code}: {patch_url}")
                return None
        except Exception as e:
            print(f"Błąd pobierania patcha: {e}")
            return None

        soup = BeautifulSoup(response.text, 'lxml')
        result = []

        def extract_section(title_keywords, emoji):
            section = soup.find('h2', string=lambda s: s and any(kw in s.lower() for kw in title_keywords))
            entries = []
            if section:
                entries.append(f"**{emoji} {' '.join(title_keywords).title()} Changes:**")
                for tag in section.find_all_next(['h2', 'h3', 'p']):
                    if tag.name == 'h2':
                        break  # zakończ, jeśli trafimy na nową sekcję
                    if tag.name == 'h3':
                        entries.append(f"\n**{tag.get_text(strip=True)}**")
                    elif tag.name == 'p':
                        text = tag.get_text(strip=True)
                        if text and not text.lower().startswith("the following"):
                            entries.append(f"> {text}")
            return entries

        # Extract champions and items
        result += extract_section(['champion'], '🧙‍♂️')
        result += extract_section(['item'], '🛡️')

        # Extract skins and chromas
        skins_section = soup.find('h2', string=lambda s: s and "skins" in s.lower())
        if skins_section:
            result.append("\n**🎨 Skins:**")
            for tag in skins_section.find_all_next(['h3', 'p']):
                if tag.name == 'h2':
                    break  # stop at the next section
                if tag.name == 'h3':
                    result.append(f"\n**{tag.get_text(strip=True)}**")
                elif tag.name == 'p':
                    text = tag.get_text(strip=True)
                    if text:
                        result.append(f"> {text}")

        # Extract chromas
        chromas_section = soup.find('h2', string=lambda s: s and "chroma" in s.lower())
        if chromas_section:
            result.append("\n**🌈 Chromas:**")
            for tag in chromas_section.find_all_next(['h3', 'p']):
                if tag.name == 'h2':
                    break  # stop at the next section
                if tag.name == 'h3':
                    result.append(f"\n**{tag.get_text(strip=True)}**")
                elif tag.name == 'p':
                    text = tag.get_text(strip=True)
                    if text:
                        result.append(f"> {text}")

        # Remove empty or duplicate lines
        clean_result = []
        seen = set()
        for line in result:
            if line not in seen and line.strip():
                clean_result.append(line)
                seen.add(line)

        return "\n".join(clean_result) if clean_result else None

# --- Cykliczne sprawdzanie patcha ---
@tasks.loop(hours=24)
async def check_patches():
    global last_patch_version
    version = RiotAPI.get_latest_patch()
    if version and version != last_patch_version:
        data = RiotAPI.get_patch_data(version)
        if data:
            last_patch_version = version
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(f"📢 Nowy patch **{version}** dostępny!")
                # Split the data into chunks of 2000 characters
                chunks = [data[i:i+2000] for i in range(0, len(data), 2000)]
                for chunk in chunks:
                    await channel.send(chunk)

# --- Event: on_ready ---
@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    if not check_patches.is_running():
        check_patches.start()

# --- Komendy ---
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

    await ctx.send(f"📢 Nowy patch **{version}** dostępny!")

    # Dzielenie na segmenty po 2000 znaków
    chunks = [data[i:i+2000] for i in range(0, len(data), 2000)]
    for chunk in chunks:
        await ctx.send(chunk)

# --- Keep-alive server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive."

if __name__ == '__main__':
    # Ustawienie portu dla Render.com
    port = int(os.environ.get("PORT", 5000))
    Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    bot.run(TOKEN)
