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

        soup = BeautifulSoup(response.text, 'html.parser')
        patch_data = []

        # Znajdź wszystkie sekcje championów
        champion_sections = soup.find_all('div', class_='champion-change')
        
        for section in champion_sections:
            # Pobierz nazwę championa
            champion_name = section.find('h3', class_='change-title')
            if not champion_name:
                continue
                
            champion_name = champion_name.get_text(strip=True).split('@')[0].strip()
            if not champion_name:
                continue

            changes = []
            
            # Znajdź zmiany umiejętności
            abilities = section.find_all('h4', class_='change-detail-title')
            for ability in abilities:
                ability_name = ability.get_text(strip=True).replace(' - ', '').strip()
                ability_changes = []
                
                # Znajdź wszystkie zmiany dla tej umiejętności
                change_list = ability.find_next('ul')
                if change_list:
                    for change in change_list.find_all('li'):
                        change_text = change.get_text(strip=True)
                        if '⇒' in change_text:
                            before, after = change_text.split('⇒', 1)
                            ability_changes.append(f"**{before.strip()}** ⇒ **{after.strip()}**")
                        else:
                            ability_changes.append(f"**{change_text}**")
                
                if ability_changes:
                    changes.append(f"**{ability_name}:**\n" + "\n".join(ability_changes))
            
            if changes:
                patch_data.append(f"**{champion_name}**\n" + "\n\n".join(changes))

        return "\n\n".join(patch_data) if patch_data else None

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
                await channel.send(f"📢 **Nowy patch {version} dostępny!**\n\n@everyone\n\n**Zmiany championów:**")
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

    await ctx.send(f"📢 **Nowy patch {version} dostępny!**\n\n@everyone\n\n**Zmiany championów:**")
    chunks = [data[i:i+2000] for i in range(0, len(data), 2000)]
    for chunk in chunks:
        await ctx.send(chunk)

# --- Keep-alive server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    bot.run(TOKEN)