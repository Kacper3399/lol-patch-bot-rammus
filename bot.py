import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import requests
from bs4 import BeautifulSoup
import re
import os

# Konfiguracja
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Flask keep-alive
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot running"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_flask).start()

# === PATCH SCRAPER ===

def extract_changes(text):
    pattern = r'([\w\s%]+):?\s*(\d+(?:/\d+)*)(?:\s*⇒\s*|\s*→\s*)(\d+(?:/\d+)*)'
    matches = re.findall(pattern, text)
    changes = []
    for stat, old, new in matches:
        changes.append(f"{stat.strip()}: {old} ⇒ {new}")
    return '\n'.join(changes) if changes else None

def extract_section(soup, title_keywords, emoji):
    section = soup.find('h2', string=lambda s: s and any(kw in s.lower() for kw in title_keywords))
    entries = []
    if section:
        entries.append(f"**{emoji} {' '.join(title_keywords).title()} Changes:**")
        for tag in section.find_all_next(['h2', 'h3', 'p', 'li', 'span', 'strong']):
            if tag.name == 'h2':
                break
            if tag.name == 'h3':
                entries.append(f"\n**{tag.get_text(strip=True)}**")
            else:
                text = tag.get_text(strip=True)
                if text:
                    changes = extract_changes(text)
                    if changes:
                        entries.append(f"> {changes}")
    return entries

def fetch_patch_notes():
    base_url = "https://www.leagueoflegends.com/en-us/news/game-updates/"
    index = requests.get(base_url)
    soup = BeautifulSoup(index.text, 'html.parser')
    patch_link = soup.find('a', href=True, string=re.compile(r'Patch \d{2}-\d{2} Notes', re.I))
    if not patch_link:
        return "❌ Nie znaleziono najnowszego patcha."

    patch_url = f"https://www.leagueoflegends.com{patch_link['href']}"
    response = requests.get(patch_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    patch_number = soup.find('h1')
    title = patch_number.get_text(strip=True) if patch_number else "Nowy patch"

    output = [f"**{title}**\n"]

    output += extract_section(soup, ["champion"], "🧙‍♂️")
    output += extract_section(soup, ["item"], "🛡️")
    output += extract_section(soup, ["skins"], "🎨")
    output += extract_section(soup, ["chroma"], "🌈")

    return "\n".join(output[:2000])  # ograniczenie Discorda

# === DISCORD EVENTS ===

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")

# Komenda !ping
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Komenda !patch
@bot.command()
async def patch(ctx):
    await ctx.send("⏳ Pobieram dane patcha...")
    try:
        result = fetch_patch_notes()
        await ctx.send(result)
    except Exception as e:
        await ctx.send("❌ Wystąpił błąd podczas pobierania patcha.")
        print(e)

# Uruchom bota
bot.run(TOKEN)
