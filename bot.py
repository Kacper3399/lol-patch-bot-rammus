import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import os
import aiohttp
from cheerio import load as cheerio_load  # Cheerio dla Python (https://github.com/cheeriojs/cheerio)

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_patch_url = None

class PatchParser:
    @staticmethod
    async def get_latest_patch_url():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.leagueoflegends.com/pl-pl/news/tags/patch-notes/") as response:
                    html = await response.text()
                    $ = cheerio_load(html)
                    
                    # Znajdź najnowszy artykuł z patch notes
                    latest_article = $('a[href*="/news/game-updates/patch-"]').first()
                    if latest_article:
                        return "https://www.leagueoflegends.com" + latest_article.attr('href')
        except Exception as e:
            print(f"Error fetching latest patch URL: {e}")
        return None

    @staticmethod
    async def parse_patch_notes(url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html = await response.text()
                    $ = cheerio_load(html)
                    
                    # Pobierz tytuł patcha
                    title = $('h1').first().text().strip()
                    
                    # Znajdź sekcje championów i przedmiotów
                    def get_section_text(section_title):
                        section = $(f'h2:contains("{section_title}")').first()
                        if not section.length:
                            return "Brak zmian w tej sekcji"
                        
                        changes = []
                        next_element = section.next()
                        
                        while next_element.length and next_element[0].name not in ['h2', 'h3']:
                            if next_element[0].name == 'h3':
                                changes.append(f"\n**{next_element.text().strip()}**")
                            elif next_element[0].name == 'p':
                                changes.append(f"- {next_element.text().strip()}")
                            elif next_element[0].name == 'ul':
                                next_element.find('li').each(lambda i, el: changes.append(f"- {$(el).text().strip()}"))
                            next_element = next_element.next()
                        
                        return "\n".join(changes) if changes else "Brak szczegółowych zmian"
                    
                    return {
                        "title": title,
                        "champions": get_section_text("CHAMPIONS") or get_section_text("Champions"),
                        "items": get_section_text("ITEMS") or get_section_text("Items"),
                        "url": url
                    }
        except Exception as e:
            print(f"Error parsing patch notes: {e}")
            return None

@tasks.loop(hours=24)
async def check_patches():
    global last_patch_url
    current_url = await PatchParser.get_latest_patch_url()
    
    if current_url and current_url != last_patch_url:
        patch_data = await PatchParser.parse_patch_notes(current_url)
        if patch_data:
            last_patch_url = current_url
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title=patch_data["title"],
                    url=patch_data["url"],
                    color=discord.Color.blue(),
                    description=f"[Pełne patch notes]({patch_data['url']})"
                )
                
                for name, value in [("Champion Changes", "champions"), ("Item Changes", "items")]:
                    content = patch_data[value]
                    embed.add_field(
                        name=name,
                        value=content[:1000] + "..." if len(content) > 1000 else content,
                        inline=False
                    )
                
                await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f'Bot zalogowany jako {bot.user}')
    if not check_patches.is_running():
        check_patches.start()

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def patch(ctx):
    current_url = await PatchParser.get_latest_patch_url()
    if not current_url:
        await ctx.send("Nie udało się znaleźć najnowszego patcha.")
        return
    
    patch_data = await PatchParser.parse_patch_notes(current_url)
    if not patch_data:
        await ctx.send("Nie udało się sparsować informacji o patchu.")
        return
    
    embed = discord.Embed(
        title=patch_data["title"],
        url=patch_data["url"],
        color=discord.Color.green(),
        description=f"[Pełne patch notes]({patch_data['url']})"
    )
    
    for name, value in [("Zmiany championów", "champions"), ("Zmiany przedmiotów", "items")]:
        content = patch_data[value]
        embed.add_field(
            name=name,
            value=content[:1000] + "..." if len(content) > 1000 else content,
            inline=False
        )
    
    await ctx.send(embed=embed)

# Flask keep-alive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot running"

if __name__ == '__main__':
    Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.run(TOKEN)