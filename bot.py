import discord
import requests
from discord.ext import commands, tasks
import os
import sys
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
RIOT_API_KEY = os.getenv("RIOT_API_KEY")  # Twój stały klucz API
DATA_DRAGON_URL = "https://ddragon.leagueoflegends.com"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
last_patch_version = None

class RiotAPI:
    @staticmethod
    def get_latest_patch_version():
        try:
            versions_url = f"{DATA_DRAGON_URL}/api/versions.json"
            response = requests.get(versions_url)
            return response.json()[0] if response.status_code == 200 else None
        except Exception as e:
            print(f"Error getting patch version: {e}", file=sys.stderr)
            return None

    @staticmethod
    def get_patch_notes(patch_version):
        try:
            notes_url = f"{DATA_DRAGON_URL}/patchnotes/{patch_version}.json"
            response = requests.get(notes_url, headers={"X-Riot-Token": RIOT_API_KEY})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error getting patch notes: {e}", file=sys.stderr)
            return None

def format_patch_notes(patch_data):
    if not patch_data:
        return "Brak danych o patchu."
    
    formatted = []
    
    # Nagłówek z wersją i datą
    patch_date = datetime.strptime(patch_data['date'], "%Y-%m-%d").strftime("%d.%m.%Y")
    formatted.append(f"**Patch {patch_data['version']} ({patch_date})**")
    
    # Zmiany championów
    if 'champions' in patch_data:
        formatted.append("\n**CHAMPION CHANGES**")
        for champ in patch_data['champions']:
            formatted.append(f"\n**{champ['name']}**")
            for change in champ['changes']:
                formatted.append(f"- {change['description']}")
    
    # Zmiany przedmiotów
    if 'items' in patch_data:
        formatted.append("\n**ITEM CHANGES**")
        for item in patch_data['items']:
            formatted.append(f"\n**{item['name']}**")
            for change in item['changes']:
                formatted.append(f"- {change['description']}")
    
    return "\n".join(formatted) if len(formatted) > 1 else "Brak zmian w tym patchu."

@tasks.loop(hours=24)
async def check_for_patches():
    global last_patch_version
    current_version = RiotAPI.get_latest_patch_version()
    
    if current_version and current_version != last_patch_version:
        patch_data = RiotAPI.get_patch_notes(current_version)
        if patch_data:
            last_patch_version = current_version
            notes = format_patch_notes(patch_data)
            
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                # Dzielenie długich wiadomości
                parts = [notes[i:i+2000] for i in range(0, len(notes), 2000)]
                for part in parts:
                    await channel.send(part)

@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}", file=sys.stderr)
    check_for_patches.start()

@bot.command()
async def patch(ctx):
    """Ręczne sprawdzenie najnowszych patchnotów"""
    current_version = RiotAPI.get_latest_patch_version()
    if not current_version:
        await ctx.send("❌ Nie udało się pobrać informacji o patchu.")
        return
    
    patch_data = RiotAPI.get_patch_notes(current_version)
    if not patch_data:
        await ctx.send("❌ Nie udało się pobrać szczegółów patcha.")
        return
    
    notes = format_patch_notes(patch_data)
    parts = [notes[i:i+2000] for i in range(0, len(notes), 2000)]
    for part in parts:
        await ctx.send(part)

# Serwer pingujący (zachowujemy z Twojego oryginalnego kodu)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot działa!", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot.run(TOKEN)