import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
import os
from datetime import datetime
import re

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
    def extract_changes(soup):
        # Regular expression to match changes like "Q damage: 70 / 105 / 140 / 175 / 210 (+ 80% AP) ⇒ 80 / 120 / 160 / 200 / 240 (+ 80% AP)"
        changes = []
        
        # Szukamy elementów zawierających informacje o zmianach
        ability_titles = soup.find_all('h4', class_='change-detail-title ability-title')

        for title in ability_titles:
            # Dla każdej umiejętności, spróbujemy znaleźć liściowe elementy, które zawierają zmiany
            ability_list = title.find_next('ul')
            if ability_list:
                for change_item in ability_list.find_all('li'):
                    change_text = change_item.get_text(strip=True)
                    # Dopasowujemy wzór, aby znaleźć zmiany
                    match = re.search(r'(\d+(?:/\d+)*)(?:\s*⇒\s*)(\d+(?:/\d+)*)', change_text)
                    if match:
                        old_value = match.group(1)
                        new_value = match.group(2)
                        changes.append(f"{title.get_text(strip=True)}: {old_value} ⇒ {new_value}")
        
        return '\n'.join(changes) if changes else None

    @staticmethod
    def get_patch_data(version):
        try:
            major, minor = version.split('.')[:2]
            season_number = datetime.now().year - 2000
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

        # Extract champions and abilities' changes
        changes = RiotAPI.extract_changes(soup)
        if changes:
            result.append("**Zmiany w umiejętnościach i statystykach bohaterów:**\n" + changes)

        # Skins
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

        # Chromas
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

        # Clean up empty or duplicate lines
        clean_result = []
        seen = set()
        for line in result:
            if line not in seen and line.strip():
                clean_result.append(line)
                seen.add(line)

        return "\n".join(clean_result) if clean_result else None

    @staticmethod
    def get_latest_patch():
        try:
            versions = requests.get(f"{DATA_DRAGON_URL}/api/versions.json").json()
            return versions[0]  # przykład: "14.9.1"
        except Exception as e:
            print(f"Błąd pobierania wersji patcha: {e}")
            return None

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
