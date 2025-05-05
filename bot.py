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
            return versions[0]  # przykład: "14.9.1"
        except Exception as e:
            print(f"Błąd pobierania wersji patcha: {e}")
            return None

    @staticmethod
    def get_patch_data(version):
        # Konwersja np. "14.9.1" -> "25-09"
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

        soup = BeautifulSoup(response.text, 'lxml')
        result = []

        # Champions
        champions_section = soup.find('h2', string=lambda s: s and "champion" in s.lower())
        if champions_section:
            result.append("**🧙‍♂️ Champion Changes:**")
            for tag in champions_section.find_all_next(['h3', 'p']):
                if tag.name == 'h2':
                    break
                if tag.name == 'h3':
                    result.append(f"\n**{tag.get_text(strip=True)}**")
                elif tag.name == 'p':
                    text = tag.get_text(strip=True)
                    if text:
                        result.append(f"> {text}")

        # Items
        items_section_
