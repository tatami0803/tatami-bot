import os
import asyncio
import discord
import openai

from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv

# .env の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

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
    "▼プライバシーと誠実さ...\n"
    "（以下省略しても構いませんが、必要なら全文再挿入可能です）"
)

# 以下、Modal / VCManageView クラス定義（省略せずに再利用）

# ── Botイベント ──
@bot.event
async def on_ready():
    print(f"✅ ゆのんちゃん統合Bot 起動完了：{bot.user}")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == VC_CREATOR_CHANNEL_ID:
        guild = after.channel.guild
        category = guild.get_channel(VC_CATEGORY_ID)
        new_vc = await guild.create_voice_channel(
            name=f"{member.display_name}の部屋",
            category=category,
            bitrate=128000
        )
        temporary_voice_channels[new_vc.id] = new_vc
        await member.move_to(new_vc)

        # チャット準備の待機とフォールバック処理
        await asyncio.sleep(1)
        try:
            await new_vc.send("🔧 VC管理メニューはこちら：", view=VCManageView(new_vc))
        except Exception as e:
            print(f"⚠️ VCへのメニュー送信失敗: {e}")
            fallback = guild.get_channel(TEXT_CHANNEL_ID)
            await fallback.send(f"🔧 <@{member.id}> さんのVCを作成しました：", view=VCManageView(new_vc))

    for vc_id, channel in list(temporary_voice_channels.items()):
        if len([m for m in channel.members if not m.bot]) == 0:
            await channel.delete()
            del temporary_voice_channels[vc_id]

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "メニュー":
        if message.author.voice and message.author.voice.channel:
            vc = message.author.voice.channel
            await message.channel.send("🔧 VC管理メニューはこちら：", view=VCManageView(vc))
        else:
            await message.channel.send("⚠️ VCに参加していません。ボイスチャンネルに入ってから再度お試しください。")
        return

    if message.channel.id == TEXT_CHANNEL_ID:
        prompt = message.content.strip()
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content
        await message.channel.send(reply)

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
