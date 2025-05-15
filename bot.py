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
            return versions[0]
        except Exception as e:
            print(f"Błąd pobierania wersji patcha: {e}")
            return None

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

        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Poprawiona funkcja wyciągania zmian ---
        def extract_changes_with_champions(soup):
            changes = []
            sections = soup.find_all('h3', class_='change-title')
            for section in sections:
                champion_name = section.get_text(strip=True).split('@')[0].strip()
                content = []
                next_sibling = section.find_next_sibling()
                while next_sibling and next_sibling.name != 'h3':
                    if next_sibling.name == 'h4':
                        ability_name = next_sibling.get_text(strip=True)
                        ul = next_sibling.find_next_sibling('ul')
                        if ul:
                            items = ul.find_all('li')
                            for item in items:
                                change_text = item.get_text(strip=True)
                                if '⇒' in change_text:
                                    before, after = change_text.split('⇒')
                                    before = before.strip()
                                    after = after.strip()
                                    content.append(f"**{ability_name}**: {before} ⇒ {after}")
                    next_sibling = next_sibling.find_next_sibling()

                if content:
                    changes.append(f"##**{champion_name}:**")
                    changes.append("")  # pusta linia dla czytelności
                    changes.extend(content)
                    changes.append("")  # pusta linia dla czytelności
                    changes.append("")  # pusta linia dla czytelności
            return changes

        changes = extract_changes_with_champions(soup)
        return "\n".join(changes) if changes else None

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
                await channel.send(f"###New patch **{version}** !")
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
        await ctx.send("❌ Patch not found")
        return

    data = RiotAPI.get_patch_data(version)
    if not data:
        await ctx.send("❌ Patch not found")
        return

    await ctx.send(f"###New patch **{version}** !")

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
