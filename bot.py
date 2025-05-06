import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import os
from datetime import datetime
from bs4 import BeautifulSoup
import re

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
            return versions[0]  # np. "14.9.1"
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

        soup = BeautifulSoup(response.text, 'html.parser')
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
                            # Wyciąganie liczb z tekstu zmiany
                            changes = extract_changes(text)
                            if changes:
                                entries.append(f"> {changes}")

            return entries

        def extract_changes(text):
            # Szukamy liczb (np. "Q damage increased by 20", "W mana cost reduced by 10")
            pattern = r"(\w+ damage|\w+ mana cost|\w+ attack speed)\s*(increased|decreased)\s*by\s*(\d+)"
            matches = re.findall(pattern, text)
            changes = []
            for match in matches:
                ability, direction, value = match
                changes.append(f"{ability}: {direction.title()} by {value}")
            return '\n'.join(changes) if changes else None

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


@tasks.loop(hours=24)
async def check_patches():
    global last_patch_version
    version = RiotAPI.get_latest_patch()
    if version and version != last_patch_version:
        data = RiotAPI.get_patch_data(version)
        if data:
            last_patch_version = version
            message = f"**Patch {version}**\n\n{data}"
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
    message = f"**Patch {version}**\n\n{data}"
    await ctx.send(message[:2000])

# Flask keep-alive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot running"

if __name__ == '__main__':
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.run(TOKEN)
