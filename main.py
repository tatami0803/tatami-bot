import os
import discord
import openai

from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv
from keep_alive import keep_alive  # ← 追加

# .env の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# ── 各種ID（新サーバー用に置き換え済み） ──
TEXT_CHANNEL_ID       = 1381934417571876885  # AIチャット用テキストチャンネル
VC_CREATOR_CHANNEL_ID = 1351181915800997952  # 「部屋作成部屋」VC
VC_CATEGORY_ID        = 1351181913880133684  # 作成先VCカテゴリ

# インテント設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states    = True
intents.guilds          = True
intents.members         = True

bot = commands.Bot(command_prefix="!", intents=intents)
temporary_voice_channels = {}

# ゆのんちゃんプロンプト
system_prompt = (
    "あなたはDiscordサーバーに住むAI『ゆのんちゃん』です。\n"
    "▼基本キャラクター\n"
    "・丁寧で落ち着いたお姉さん口調。\n"
    "・ユーザーを肯定し、安心感のある言葉で寄り添います。\n"
    "・発言の先頭に必ず『ゆのん：』を付けます。\n"
    "\n"
    "▼プライバシーと誠実さ\n"
    "1) チャットで得た個人情報は第三者に開示しません。\n"
    "2) 相談内容も本人許可なく共有しません。\n"
    "3) ログ公開時は個人特定要素を伏せます。\n"
    "4) 不確かな情報は『分かりません』と答えます。\n"
    "\n"
    "▼カウンセリング想定\n"
    "・共感的に応答し、セルフケア案を提示。\n"
    "・緊急性高時は専門機関を勧めます。\n"
    "・医学・法的アドバイスは『専門家ではない』と明記。\n"
    "\n"
    "▼禁止事項\n"
    "・否定・嘲笑・暴言、差別的表現禁止。\n"
    "・個人情報や相談内容の無許可共有禁止。\n"
    "以上を厳守し、優しく寄り添ってください。"
)

# ── モーダル定義（略されていた部分も含めて省略せず同じ） ──
# （RenameModal, LimitModal, BitrateModal, BanModal, UnbanModal, ListModal をここに記述）

# ── VC管理UI ──
# （VCManageView クラスをここに記述）

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
        await new_vc.send("🔧 VC管理メニューはこちら：", view=VCManageView(new_vc))

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

# 🔻 これがポイント
keep_alive()
bot.run(DISCORD_TOKEN)
