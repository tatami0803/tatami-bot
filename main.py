import os
import discord
import openai
from dotenv import load_dotenv
from keep_alive import keep_alive
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput

# .env の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# ── 各種ID ──
TEXT_CHANNEL_ID       = 1381934417571876885
VC_CREATOR_CHANNEL_ID = 1351181915800997952
VC_CATEGORY_ID        = 1351181913880133684

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states    = True
intents.guilds          = True
intents.members         = True

bot = commands.Bot(command_prefix="!", intents=intents)
temporary_voice_channels = {}

system_prompt = (
    "あなたはDiscordサーバーに住むAI『ゆのんちゃん』です。\n"
    "▼基本キャラクター\n"
    "・丁寧で落ち着いたお姉さん口調。\n"
    "・ユーザーを肯定し、安心感のある言葉で寄り添います。\n"
    "・発言の先頭に必ず『ゆのん：』を付けます。\n"
    "...（省略なしで入力）..."
)

# モーダル・VC管理クラス・イベント類はマスターの投稿通りに続けて実装

@bot.event
async def on_ready():
    print(f"✅ ゆのんちゃん統合Bot 起動完了：{bot.user}")

keep_alive()
bot.run(DISCORD_TOKEN)
