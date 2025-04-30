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
    """Funkcja do debugowania strony"""
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
    """Funkcja wyciągająca zmiany championów i przedmiotów"""
    try:
        print(f"\n=== Przetwarzam: {patch_url} ===", file=sys.stderr)
        soup = debug_website(patch_url)
        if not soup:
            return "Could not fetch patch details."

        champion_changes = []
        item_changes = []
        
        # Szukamy sekcji championów
        champion_section = None
        champion_headers = ['Champion Changes', 'Champion Updates', 'Champions']
        for header in champion_headers:
            champion_section = soup.find(lambda tag: tag.name in ['h2', 'h3'] and 
                                      header.lower() in tag.get_text().lower())
            if champion_section:
                break
        
        if champion_section:
            print(f"Znaleziono sekcję championów: {champion_section.get_text()}", file=sys.stderr)
            current = champion_section.find_next_sibling()
            
            while current and current.name not in ['h2', 'h3']:
                if current.name in ['h4', 'h5']:
                    champ_name = current.get_text(strip=True)
                    champion_changes.append(f"\n**{champ_name}**")
                elif current.name in ['p', 'li']:
                    text = current.get_text(' ', strip=True)
                    if text and not text.startswith(('http', '©')):
                        champion_changes.append(f"- {text}")
                elif current.name == 'div' and current.get('class'):
                    text = current.get_text(' ', strip=True)
                    if text and len(text) > 10:
                        champion_changes.append(f"- {text}")
                
                current = current.find_next_sibling()

        # Szukamy sekcji przedmiotów
        item_section = None
        item_headers = ['Item Changes', 'Item Updates', 'Items']
        for header in item_headers:
            item_section = soup.find(lambda tag: tag.name in ['h2', 'h3'] and 
                                  header.lower() in tag.get_text().lower())
            if item_section:
                break
        
        if item_section:
            print(f"Znaleziono sekcję przedmiotów: {item_section.get_text()}", file=sys.stderr)
            current = item_section.find_next_sibling()
            
            while current and current.name not in ['h2', 'h3']:
                if current.name in ['h4', 'h5']:
                    item_name = current.get_text(strip=True)
                    item_changes.append(f"\n**{item_name}**")
                elif current.name in ['p', 'li']:
                    text = current.get_text(' ', strip=True)
                    if text and not text.startswith(('http', '©')):
                        item_changes.append(f"- {text}")
                elif current.name == 'div' and current.get('class'):
                    text = current.get_text(' ', strip=True)
                    if text and len(text) > 10:
                        item_changes.append(f"- {text}")
                
                current = current.find_next_sibling()

        # Łączymy wyniki
        result = []
        if champion_changes:
            result.append("**CHAMPION CHANGES**")
            result.extend(champion_changes)
        
        if item_changes:
            result.append("\n**ITEM CHANGES**")
            result.extend(item_changes)

        return '\n'.join(result) if result else "No champion or item changes found."

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
                    # Dzielimy wiadomość jeśli jest zbyt długa
                    part1 = message[:2000]
                    part2 = message[2000:4000]
                    await channel.send(part1)
                    await channel.send(part2)
                else:
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
            part1 = message[:2000]
            part2 = message[2000:4000]
            await ctx.send(part1)
            await ctx.send(part2)
        else:
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