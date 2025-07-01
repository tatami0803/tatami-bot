import os
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

# 一時的に作成したVCを追跡
temporary_voice_channels = {}

# ゆのんちゃんの system プロンプト（省略せず全量記載）
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
    "\n"
    "以上を厳守し、優しく寄り添ってください。"
)

# ── モーダル定義 ──
class RenameModal(Modal, title="部屋名の変更"):
    name = TextInput(label="新しい部屋名", placeholder="例：たたみの秘密基地", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        await self.channel.edit(name=self.name.value)
        await interaction.response.send_message(f"✅ 部屋名を「{self.name.value}」に変更しました。", ephemeral=True)

class LimitModal(Modal, title="人数制限の設定"):
    limit = TextInput(label="最大人数 (1〜99)", placeholder="例：5", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        try:
            cnt = int(self.limit.value)
            if 1 <= cnt <= 99:
                await self.channel.edit(user_limit=cnt)
                await interaction.response.send_message(f"✅ 人数制限を {cnt} 人に設定しました。", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 1〜99 の範囲で指定してください。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("⚠️ 数字を入力してください。", ephemeral=True)

class BitrateModal(Modal, title="ビットレートの設定"):
    bitrate = TextInput(label="ビットレート (kbps)", placeholder="例：128", required=True)
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
                await interaction.response.send_message("⚠️ 8〜384 kbps の範囲で指定してください。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("⚠️ 数字を入力してください。", ephemeral=True)

class BanModal(Modal, title="同室拒否するユーザー"):
    user_id = TextInput(label="メンション or ユーザーID", placeholder="例：<@123456789012345678>", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        uid = int(''.join(filter(str.isdigit, self.user_id.value)))
        member = interaction.guild.get_member(uid)
        ow = self.channel.overwrites_for(member)
        ow.connect = False
        await self.channel.set_permissions(member, overwrite=ow)
        if member and member.voice and member.voice.channel == self.channel:
            await member.move_to(None)
        await interaction.response.send_message(f"⛔ <@{uid}> を同室拒否設定しました。", ephemeral=True)

class UnbanModal(Modal, title="同室拒否を解除するユーザー"):
    user_id = TextInput(label="メンション or ユーザーID", placeholder="例：<@123456789012345678>", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        uid = int(''.join(filter(str.isdigit, self.user_id.value)))
        member = interaction.guild.get_member(uid)
        await self.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"✅ <@{uid}> の同室拒否を解除しました。", ephemeral=True)

class ListModal(Modal, title="同室拒否リスト"):
    dummy = TextInput(label="", required=False)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction):
        lst = [f"<@{target.id}>" for target, ow in self.channel.overwrites.items() if isinstance(target, discord.Member) and ow.connect is False]
        text = "\n".join(lst) or "なし"
        await interaction.response.send_message(f"🚫 同室拒否リスト：\n{text}", ephemeral=True)

# ── VC管理メニュー ──
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

    @discord.ui.button(label="同室拒否設定", style=discord.ButtonStyle.danger)
    async def ban(self, interaction, button):
        await interaction.response.send_modal(BanModal(self.channel))

    @discord.ui.button(label="同室拒否解除", style=discord.ButtonStyle.success)
    async def unban(self, interaction, button):
        await interaction.response.send_modal(UnbanModal(self.channel))

    @discord.ui.button(label="拒否リスト表示", style=discord.ButtonStyle.secondary)
    async def showlist(self, interaction, button):
        await interaction.response.send_modal(ListModal(self.channel))

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

bot.run(DISCORD_TOKEN)
