import discord
import requests
from discord.ext import commands, tasks
from bs4 import BeautifulSoup

TOKEN = 'TWOJ_DISCORD_TOKEN'  # ← Wklej swój token
CHANNEL_ID = 123456789012345678  # ← Wklej swój ID kanału
PATCH_URL = 'https://www.leagueoflegends.com/pl-pl/news/tags/patch-notes/'

intents = discord.Intents.default()
intents.message_content = True  # ← TO JEST NAJWAŻNIEJSZE
bot = commands.Bot(command_prefix='!', intents=intents)

last_posted_patch = None

def extract_patch_summary(patch_url):
    try:
        response = requests.get(patch_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text(separator='\n')
        relevant_lines = []
        for line in content.splitlines():
            if any(kw in line.lower() for kw in ['przedmiot', 'postać', 'bohater', 'run']):
                relevant_lines.append(line.strip())
        summary = '\n'.join(relevant_lines[:10])  # ograniczamy do 10 linijek
        return summary or "(Brak skrótu zmian)"
    except:
        return "(Nie udało się pobrać skrótu patcha)"

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
                await channel.send(f'**Nowe notki patcha LoL:** {patch_title}\n{patch_url}\n{summary}')

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

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user}')
    fetch_patch_notes.start()

bot.run(TOKEN)
