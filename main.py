import os
import discord
import openai

from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from dotenv import load_dotenv
from keep_alive import keep_alive

# .env の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 各種ID（マスターの環境に合わせて編集済）
TEXT_CHANNEL_ID       = 1381934417571876885
VC_CREATOR_CHANNEL_ID = 1351181915800997952
VC_CATEGORY_ID        = 1351181913880133684

# インテント設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states    = True
intents.guilds          = True
intents.members         = True

bot = commands.Bot(command_prefix="!", intents=intents)
temporary_voice_channels = {}

# ゆのんちゃん設定
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

# ── モーダル類 ──
class RenameModal(Modal, title="部屋名の変更"):
    name = TextInput(label="新しい部屋名", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        await self.channel.edit(name=self.name.value)
        await interaction.response.send_message(f"✅ 部屋名を「{self.name.value}」に変更しました。", ephemeral=True)

class LimitModal(Modal, title="人数制限の設定"):
    limit = TextInput(label="最大人数 (1〜99)", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        try:
            count = int(self.limit.value)
            if 1 <= count <= 99:
                await self.channel.edit(user_limit=count)
                await interaction.response.send_message(f"✅ 人数制限を {count} 人に設定しました。", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 1〜99で指定してください。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("⚠️ 数字を入力してください。", ephemeral=True)

class BitrateModal(Modal, title="ビットレートの設定"):
    bitrate = TextInput(label="ビットレート (kbps)", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        try:
            rate = int(self.bitrate.value) * 1000
            if 8000 <= rate <= 384000:
                await self.channel.edit(bitrate=rate)
                await interaction.response.send_message(f"✅ ビットレートを {self.bitrate.value} kbps に設定しました。", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 8〜384の範囲で指定してください。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("⚠️ 数字を入力してください。", ephemeral=True)

# ── 管理UI ──
class VCManageView(View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="部屋名変更", style=discord.ButtonStyle.primary)
    async def rename(self, interaction, button):
        await interaction.response.send_modal(RenameModal(self.channel))

    @discord.ui.button(label="人数制限設定", style=discord.ButtonStyle.primary)
    async def limit(self, interaction, button):
        await interaction.response.send_modal(LimitModal(self.channel))

    @discord.ui.button(label="ビットレート設定", style=discord.ButtonStyle.primary)
    async def bitrate(self, interaction, button):
        await interaction.response.send_modal(BitrateModal(self.channel))

    @discord.ui.button(label="ロック/解除", style=discord.ButtonStyle.secondary)
    async def lock(self, interaction, button):
        ow = self.channel.overwrites_for(interaction.guild.default_role)
        ow.connect = not ow.connect if ow.connect is not None else False
        await self.channel.set_permissions(interaction.guild.default_role, overwrite=ow)
        status = "🔒 ロック" if not ow.connect else "🔓 解除"
        await interaction.response.send_message(status, ephemeral=True)

    @discord.ui.button(label="全員ミュート/解除", style=discord.ButtonStyle.secondary)
    async def mute(self, interaction, button):
        for m in self.channel.members:
            if not m.bot:
                await m.edit(mute=not m.voice.mute)
        await interaction.response.send_message("🔇 ミュート切替", ephemeral=True)

# ── イベント関連 ──
@bot.event
async def on_ready():
    print(f"✅ ゆのんちゃん 起動完了：{bot.user}")

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
        text_channel = discord.utils.get(guild.text_channels, id=TEXT_CHANNEL_ID)
        if text_channel:
            await text_channel.send("🔧 VC管理メニューはこちら：", view=VCManageView(new_vc))

    # 自動削除
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
            await message.channel.send("⚠️ VCに参加していません。")

    elif message.channel.id == TEXT_CHANNEL_ID:
        prompt = message.content.strip()
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            reply = response.choices[0].message.content
            await message.channel.send(reply)
        except Exception as e:
            await message.channel.send(f"⚠️ エラー：{str(e)}")

    await bot.process_commands(message)

# --- 起動 ---
keep_alive()
bot.run(DISCORD_TOKEN)

