import discord
import requests
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import os
import sys

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
        print("=== Pobieram stronę patchnotów ===", file=sys.stderr)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print("\n=== Pierwsze 1000 znaków strony ===", file=sys.stderr)
        print(response.text[:1000], file=sys.stderr)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        print("\n=== Sformatowany HTML (pierwsze 1000 znaków) ===", file=sys.stderr)
        print(soup.prettify()[:1000], file=sys.stderr)
        
        return soup
    except Exception as e:
        print(f"Błąd podczas debugowania strony: {e}", file=sys.stderr)
        return None

def extract_patch_summary(patch_url):
    """Ulepszona funkcja do wyciągania zmian z patchnotów (2025)"""
    try:
        print(f"\n=== Przetwarzam: {patch_url} ===", file=sys.stderr)
        soup = debug_website(patch_url)
        if not soup:
            return "Could not fetch patch details."

        summary = []
        
        # Szukamy sekcji championów
        champion_section = None
        
        # Metoda 1: Szukamy po nagłówkach
        for h2 in soup.find_all(['h2', 'h3']):
            if 'champion' in h2.get_text().lower():
                champion_section = h2
                break
        
        # Metoda 2: Szukamy po klasach
        if not champion_section:
            for div in soup.find_all('div', class_=True):
                if 'champion' in ' '.join(div['class']).lower():
                    champion_section = div
                    break
        
        if champion_section:
            print(f"Znaleziono sekcję championów: {champion_section.get_text()}", file=sys.stderr)
            summary.append(f"\n**{champion_section.get_text(strip=True)}**")
            
            # Znajdź wszystkie zmiany w sekcji
            current = champion_section.find_next()
            changes_count = 0
            
            while current and changes_count < 15:  # Limit 15 zmian
                if current.name in ['h4', 'h5']:
                    # Nazwa championa lub umiejętności
                    champ_name = current.get_text(strip=True)
                    if len(champ_name) < 50:  # Filtruj zbyt długie teksty
                        summary.append(f"\n__{champ_name}__")
                        changes_count += 1
                elif current.name in ['p', 'li']:
                    # Szczegóły zmian
                    text = current.get_text(' ', strip=True)
                    if 10 < len(text) < 150:  # Filtruj zbyt krótkie/długie
                        summary.append(f"- {text}")
                        changes_count += 1
                elif current.name == 'div' and current.get('class'):
                    # Zmiany w divach
                    text = current.get_text(' ', strip=True)
                    if 'change' in ' '.join(current['class']).lower() and 10 < len(text) < 150:
                        summary.append(f"- {text}")
                        changes_count += 1
                
                current = current.find_next()
        
        # Jeśli nie znaleziono sekcji championów, spróbuj alternatywnej metody
        if not summary:
            print("Próbuję alternatywnej metody parsowania...", file=sys.stderr)
            for item in soup.find_all(['h4', 'h5', 'li', 'p']):
                text = item.get_text(' ', strip=True)
                if any(word in text.lower() for word in ['buff', 'nerf', 'change', 'adjust', 'update']) and 10 < len(text) < 150:
                    summary.append(f"- {text}")
                    if len(summary) >= 10:  # Limit 10 zmian
                        break
        
        return '\n'.join(summary) if summary else "No detailed champion changes found."

    except Exception as e:
        print(f"Błąd w extract_patch_summary: {e}", file=sys.stderr)
        return "Error parsing changes"

@tasks.loop(hours=24)
async def fetch_patch_notes():
    global last_posted_patch
    print("\n=== Sprawdzam nowe patchnoty ===", file=sys.stderr)
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
        print(f"Znaleziono patch: {patch_title} ({patch_url})", file=sys.stderr)
        
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
        print("Nie znaleziono linku do patchnotów!", file=sys.stderr)

@bot.event
async def on_ready():
    print(f"Bot zalogowany jako {bot.user}", file=sys.stderr)
    fetch_patch_notes.start()

@bot.command()
async def patch(ctx):
    """Ręczne sprawdzenie najnowszych patchnotów"""
    print(f"\n=== Żądanie patchnotów od {ctx.author} ===", file=sys.stderr)
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
        print("Struktura HTML strony:", file=sys.stderr)
        print(soup.prettify()[:1000], file=sys.stderr)

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