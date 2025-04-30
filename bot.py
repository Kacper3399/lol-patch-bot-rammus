import discord
import requests
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
PATCH_URL = 'https://www.leagueoflegends.com/en-us/news/tags/patch-notes/'

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
last_posted_patch = None

def debug_website(url):
    """Funkcja do debugowania - pokazuje zawartość strony"""
    try:
        print("=== Pobieram stronę patchnotów ===")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print("\n=== Pierwsze 1000 znaków strony ===")
        print(response.text[:1000])
        
        soup = BeautifulSoup(response.text, 'html.parser')
        print("\n=== Sformatowany HTML (pierwsze 1000 znaków) ===")
        print(soup.prettify()[:1000])
        
        return soup
    except Exception as e:
        print(f"Błąd podczas debugowania strony: {e}")
        return None

def extract_patch_summary(patch_url):
    """Wyciąga podsumowanie zmian z patchnotów"""
    print(f"\n=== Próbuję przetworzyć: {patch_url} ===")
    soup = debug_website(patch_url)  # Używamy naszej funkcji debugującej
    if not soup:
        return "Could not fetch patch details."
    
    # Próbujemy znaleźć zmiany na kilka sposobów
    summary = []
    
    # Metoda 1: Szukamy sekcji Champion Changes
    changes_section = soup.find('h2', string='Champion Changes')
    if changes_section:
        print("Znaleziono sekcję Champion Changes")
        for sibling in changes_section.find_next_siblings():
            if sibling.name == 'h2':
                break
            if sibling.get_text(strip=True):
                summary.append(sibling.get_text(strip=True))
    
    # Metoda 2: Szukamy po klasach (może się zmieniać!)
    if not summary:
        print("Próbuję alternatywnej metody wyszukiwania...")
        changes = soup.select('.change-detail, .patch-change, .content-block')
        for change in changes[:10]:  # Ograniczamy do 10 zmian
            text = change.get_text(strip=True)
            if text and len(text) < 150:  # Pomijamy zbyt długie fragmenty
                summary.append(text)
    
    return '\n'.join(summary[:15]) if summary else "No detailed changes found."

@tasks.loop(hours=24)
async def fetch_patch_notes():
    global last_posted_patch
    print("\n=== Sprawdzam nowe patchnoty ===")
    soup = debug_website(PATCH_URL)
    if not soup:
        return
    
    # Szukamy linku do najnowszego patcha
    patch_link = None
    
    # Metoda 1: Szukamy po tekście "Patch"
    patch_link = soup.find('a', string=lambda s: s and 'Patch' in str(s))
    
    # Metoda 2: Szukamy po href
    if not patch_link:
        patch_link = soup.find('a', href=lambda href: href and '/patch-' in str(href))
    
    # Metoda 3: Szukamy w sekcji artykułów
    if not patch_link:
        articles = soup.find_all('article', limit=3)
        for article in articles:
            patch_link = article.find('a', href=True)
            if patch_link:
                break
    
    if patch_link:
        patch_url = patch_link.get('href')
        if not patch_url.startswith('http'):
            patch_url = 'https://www.leagueoflegends.com' + patch_url
        
        patch_title = patch_link.get_text(strip=True)
        print(f"Znaleziono patch: {patch_title} ({patch_url})")
        
        if patch_url != last_posted_patch:
            last_posted_patch = patch_url
            summary = extract_patch_summary(patch_url)
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                message = f"**New LoL Patch Notes:** {patch_title}\n{patch_url}\n{summary}"
                if len(message) > 2000:
                    message = message[:1990] + "..."
                await channel.send(message)
    else:
        print("Nie znaleziono linku do patchnotów!")

@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}")
    fetch_patch_notes.start()

@bot.command()
async def patch(ctx):
    """Ręczne sprawdzenie najnowszych patchnotów"""
    print(f"\n=== Żądanie patchnotów od {ctx.author} ===")
    await ctx.send("Sprawdzam najnowsze patchnoty...")
    
    soup = debug_website(PATCH_URL)
    if not soup:
        await ctx.send("Nie udało się pobrać strony z patchnotami.")
        return
    
    patch_link = soup.find('a', string=lambda s: s and 'Patch' in str(s))
    if not patch_link:
        patch_link = soup.find('a', href=lambda href: href and '/patch-' in str(href))
    
    if patch_link:
        patch_url = patch_link.get('href')
        if not patch_url.startswith('http'):
            patch_url = 'https://www.leagueoflegends.com' + patch_url
        
        patch_title = patch_link.get_text(strip=True)
        summary = extract_patch_summary(patch_url)
        
        message = f"**Latest Patch:** {patch_title}\n{patch_url}\n{summary}"
        if len(message) > 2000:
            message = message[:1990] + "..."
        
        await ctx.send(message)
    else:
        await ctx.send("Nie znaleziono najnowszych patchnotów. Struktura strony mogła ulec zmianie.")
        print("Struktura HTML strony:")
        print(soup.prettify()[:1000])

# Serwer pingujący
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot działa!", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot.run(TOKEN)