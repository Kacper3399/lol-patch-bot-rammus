import discord
import requests
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
import os
from datetime import datetime

# --- ENV ---

TOKEN = os.getenv("DISCORD\_TOKEN")
CHANNEL\_ID = int(os.getenv("CHANNEL\_ID"))
DATA\_DRAGON\_URL = "[https://ddragon.leagueoflegends.com](https://ddragon.leagueoflegends.com)"

# --- Discord Setup ---

intents = discord.Intents.default()
intents.message\_content = True
bot = commands.Bot(command\_prefix='!', intents=intents)

last\_patch\_version = None

# --- Riot API & Scraper ---

class RiotAPI:
@staticmethod
def get\_latest\_patch():
try:
versions = requests.get(f"{DATA\_DRAGON\_URL}/api/versions.json").json()
return versions\[0]  # przykład: "14.9.1"
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

    # Funkcja do wyciągania zmian liczb i bohatera
    def extract_changes_with_champions(soup):
        changes = []

        # Szukamy wszystkich sekcji z informacjami o bohaterach
        for champion_section in soup.find_all('h3', class_='change-title'):
            champion_name = champion_section.get_text(strip=True).split('@')[0].strip()

            # Sprawdzamy, czy mamy nazwę bohatera
            if champion_name:
                # Zbieramy zmiany dotyczące tego bohatera
                ability_changes = []
                for ability_section in champion_section.find_all_next('h4', class_='change-detail-title ability-title'):
                    ability_name = ability_section.get_text(strip=True).replace(' - ', '')

                    list_items = ability_section.find_next('ul').find_all('li')
                    for item in list_items:
                        change_text = item.get_text(strip=True)
                        if '⇒' in change_text:  # Znaleziono zmianę
                            before, after = change_text.split('⇒')
                            before = before.strip()
                            after = after.strip()
                            ability_changes.append(f"{ability_name}: {before} ⇒ {after}")

                if ability_changes:
                    changes.append(f"Zmiany dla {champion_name}:")
                    changes.extend(ability_changes)

        return changes

    # Wyciąganie zmian
    changes = extract_changes_with_champions(soup)
    return "\n".join(changes) if changes else None


# --- Cykliczne sprawdzanie patcha ---

@tasks.loop(hours=24)
async def check\_patches():
global last\_patch\_version
version = RiotAPI.get\_latest\_patch()
if version and version != last\_patch\_version:
data = RiotAPI.get\_patch\_data(version)
if data:
last\_patch\_version = version
channel = bot.get\_channel(CHANNEL\_ID)
if channel:
await channel.send(f"📢 Nowy patch **{version}** dostępny!")
\# Split the data into chunks of 2000 characters
chunks = \[data\[i\:i+2000] for i in range(0, len(data), 2000)]
for chunk in chunks:
await channel.send(chunk)

# --- Event: on\_ready ---

@bot.event
async def on\_ready():
print(f"Zalogowano jako {bot.user}")
if not check\_patches.is\_running():
check\_patches.start()

# --- Komendy ---

@bot.command()
async def ping(ctx):
await ctx.send("Pong!")

@bot.command()
async def patch(ctx):
version = RiotAPI.get\_latest\_patch()
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

app = Flask(**name**)

@app.route('/')
def home():
return "Bot is alive."

if **name** == '**main**':
\# Ustawienie portu dla Render.com
port = int(os.environ.get("PORT", 5000))
Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
bot.run(TOKEN)