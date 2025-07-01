import os
import discord
import openai
from dotenv import load_dotenv
from keep_alive import keep_alive
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput

# Load .env
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready: {bot.user}")

keep_alive()
bot.run(DISCORD_TOKEN)
