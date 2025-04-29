import discord
import requests
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
PATCH_URL = 'https://www.leagueoflegends.com/pl-pl/news/tags/patch-notes/'

# Włączanie message_content intent
intents = discord.Intents.default()
intents.message_content = True  # <- Dodane, żeby bot miał dostęp do treści wiadomości

bot = commands.Bot(command_prefix='!', intents=intents)
last_posted_patch = None

def extract_patch_summary(patch_url):
    response = requests.get(patch_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find_all(['h2', 'h3', 'p'])

    sections = {
        'Zmiany bohaterów': '**Zmiany bohaterów:**',
        'Champion Changes': '**Champion Changes:**',
        'Zmiany przedmiotów': '**Zmiany przedmiotów:**',
        'Item Changes': '**Item Changes:**',
        'Zmiany run': '**Zmiany run:**',
        'Rune Changes': '**Rune Changes:**'
    }

    summary = []
    collecting = False
    for el in content:
        text = el.get_text(strip=True)
        if any(h in text for h in sections):
            collecting = True
            summary.append(f"\n{[v for k,v in sections.items() if k in text][0]}")
            continue
        elif el.name == 'h2':
            collecting = False
        elif collecting and text:
            summary.append(text)
        if len(''.join(summary)) > 1000:
            break
    return '\n'.join(summary)

@tasks.loop(hours=24)
async def fetch_patch_notes():
    global last_posted_patch
    response = requests.get(PATCH_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    patch_link = soup.find('a', href=True, string=lambda s: s and 'Patch' in s)
    if patch_link:
        patch_url = 'https://www.leagueoflegends.com' + patch_link['href']
        patch_title = patch_link.get_text(strip=True)
        if patch_url != last_posted_patch:
            last_posted_patch = patch_url
            summary = extract_patch_summary(patch_url)
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(f"**Nowe notki patcha LoL:** {patch_title}\n{patch_url}\n{summary}")

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    fetch_patch_notes.start()

# Serwer pingujący (by działało 24/7)
app = Flask('')

@app.route('/')
def home():
    return "Bot żyje!", 200

def run_ping():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

Thread(target=run_ping).start()

@bot.command()
async def patch(ctx):
    response = requests.get(PATCH_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    patch_link = soup.find('a', href=True, string=lambda s: s and 'Patch' in s)
    if patch_link:
        patch_url = 'https://www.leagueoflegends.com' + patch_link['href']
        patch_title = patch_link.get_text(strip=True)
        summary = extract_patch_summary(patch_url)
        await ctx.send(f"**Ostatni patch:** {patch_title}\n{patch_url}\n{summary}")
    else:
        await ctx.send("Nie udało się znaleźć najnowszego patcha.")

bot.run(TOKEN)
