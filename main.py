# Imports
import discord
from discord.ext import commands
import json
import os
import re
import time
from config import TOKEN, CONSOLE_CHANNEL, LEVEL_CHANNEL

# Bot Setting
WTOKEN = TOKEN

# Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Data Files
XP_FILE = "levels.json"
NICKNAME_FILE = "nicknames.json"

# XP Settings
XP_PER_MINUTE = 10
BASE_LEVEL_UP_XP = 100
EXPONENT = 1.7

# Load and Save Functions
def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# Initialize Data
user_data = load_data(XP_FILE)
nicknames = load_data(NICKNAME_FILE)
player_sessions = {}

# Required XP Calculation
def required_xp(level):
    return int(BASE_LEVEL_UP_XP * (level ** EXPONENT))

# Validate Minecraft Nickname
def is_valid_minecraft_nickname(nickname):
    return bool(re.match(r'^[a-zA-Z0-9_]{3,16}$', nickname))

# Bot Ready Event
@bot.event
async def on_ready():
    print(f'Login as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="시간 체크"))

# Command Error Handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("존재하지 않는 명령어입니다.")
    else:
        await ctx.send("알 수 없는 오류가 발생했습니다.")
        print(error)

# Detect Player Join/Leave from Console Channel
@bot.event
async def on_message(message):
    if message.channel.id == CONSOLE_CHANNEL:
        if message.author.bot and message.embeds:
            embed = message.embeds[0]
            embed_text = embed.description

            if embed_text:
                join_match = re.search(r"(.+?) 님이 서버에 접속하셨습니다.", embed_text)
                leave_match = re.search(r"(.+?) 님이 서버에서 나가셨습니다.", embed_text)

                if join_match:
                    player_name = join_match.group(1)
                    player_sessions[player_name] = time.time()

                elif leave_match:
                    player_name = leave_match.group(1)

                    if player_name in player_sessions:
                        join_time = player_sessions.pop(player_name)
                        play_time = int((time.time() - join_time) / 60)
                        if play_time < 1:
                            return
                        gained_xp = play_time * XP_PER_MINUTE

                        if player_name not in user_data:
                            user_data[player_name] = {"xp": 0, "level": 1}

                        user_data[player_name]["xp"] += gained_xp

                        level_up = False
                        while user_data[player_name]["xp"] >= required_xp(user_data[player_name]["level"]):
                            user_data[player_name]["xp"] -= required_xp(user_data[player_name]["level"])
                            user_data[player_name]["level"] += 1
                            level_up = True

                        save_data(XP_FILE, user_data)

                        if level_up:
                            level_up_channel = bot.get_channel(LEVEL_CHANNEL)
                            if level_up_channel:
                                await level_up_channel.send(f"{player_name} 님이 레벨 {user_data[player_name]['level']}로 상승했습니다! (총 플레이 {play_time}분, 획득 XP: {gained_xp})")

                        print(f"{player_name} 퇴장 감지! 플레이 시간: {play_time}분, XP 획득: {gained_xp}")

    await bot.process_commands(message)

# Command: !link <minecraft_nickname>
@bot.command()
async def link(ctx, minecraft_nickname: str):
    discord_user_id = str(ctx.author.id)

    if not is_valid_minecraft_nickname(minecraft_nickname):
        await ctx.send("유효하지 않은 마인크래프트 닉네임입니다. (3~16자의 알파벳, 숫자, 언더스코어(_)만 가능)")
        return

    if minecraft_nickname in nicknames.values():
        await ctx.send("이 마인크래프트 닉네임은 이미 등록되어 있습니다.")
        return

    nicknames[discord_user_id] = minecraft_nickname
    save_data(NICKNAME_FILE, nicknames)

    await ctx.send(f"{ctx.author.mention}님의 마인크래프트 닉네임이 `{minecraft_nickname}`로 등록되었습니다.")

# Command: !unlink
@bot.command()
async def unlink(ctx):
    discord_user_id = str(ctx.author.id)

    if discord_user_id not in nicknames:
        await ctx.send(f"{ctx.author.mention}님은 등록된 닉네임이 없습니다.")
        return

    removed_nickname = nicknames.pop(discord_user_id)
    save_data(NICKNAME_FILE, nicknames)

    await ctx.send(f"{ctx.author.mention}님의 마인크래프트 닉네임 `{removed_nickname}`이(가) 삭제되었습니다.")

# Command: !sever <nickname> (Admin Only)
@bot.command()
@commands.has_permissions(administrator=True)
async def sever(ctx, minecraft_nickname: str):
    discord_user_id = None
    for user_id, nickname in nicknames.items():
        if nickname == minecraft_nickname:
            discord_user_id = user_id
            break

    if not discord_user_id:
        await ctx.send(f"등록된 마인크래프트 닉네임 `{minecraft_nickname}`이(가) 없습니다.")
        return

    nicknames.pop(discord_user_id)
    save_data(NICKNAME_FILE, nicknames)

    discord_user = await bot.fetch_user(discord_user_id)
    await ctx.send(f"{discord_user.mention}님의 마인크래프트 닉네임 `{minecraft_nickname}`이(가) 강제 해제되었습니다.")

# Command: !ping
@bot.command()
@commands.has_permissions(administrator=True)
async def ping(ctx):
    await ctx.send(f'pong! {round(bot.latency * 1000)}ms')

# Command: !testin <player_name>
@bot.command()
@commands.has_permissions(administrator=True)
async def testin(ctx, player_name: str):
    player_sessions[player_name] = time.time()
    await ctx.send(f"{player_name} 님이 테스트 입장하였습니다.")

# Command: !testout <player_name>
@bot.command()
@commands.has_permissions(administrator=True)
async def testout(ctx, player_name: str):
    if player_name in player_sessions:
        join_time = player_sessions.pop(player_name)
        play_time = int((time.time() - join_time) / 60)
        if play_time < 1:
            await ctx.send(f"{player_name} 님의 플레이 시간이 1분 미만이라 XP가 지급되지 않습니다.")
            return
        gained_xp = play_time * XP_PER_MINUTE

        if player_name not in user_data:
            user_data[player_name] = {"xp": 0, "level": 1}

        user_data[player_name]["xp"] += gained_xp

        level_up = False
        while user_data[player_name]["xp"] >= required_xp(user_data[player_name]["level"]):
            user_data[player_name]["xp"] -= required_xp(user_data[player_name]["level"])
            user_data[player_name]["level"] += 1
            level_up = True

        save_data(XP_FILE, user_data)

        if level_up:
            level_up_channel = bot.get_channel(LEVEL_CHANNEL)
            if level_up_channel:
                await level_up_channel.send(f"{player_name} 님이 레벨 {user_data[player_name]['level']}로 상승했습니다! (총 플레이 {play_time}분, 획득 XP: {gained_xp})")

        await ctx.send(f"{player_name} 님이 테스트 퇴장하였습니다. (총 플레이 {play_time}분, 획득 XP: {gained_xp})")
    else:
        await ctx.send(f"{player_name} 님은 입장 기록이 없습니다.")

# Command: !레벨
@bot.command()
async def 레벨(ctx):
    discord_user_id = str(ctx.author.id)

    if discord_user_id in nicknames:
        player_name = nicknames[discord_user_id]
    else:
        await ctx.send(f"{ctx.author.mention}님은 마인크래프트 닉네임이 등록되지 않았습니다. `!link <닉네임>`으로 등록해주세요.")
        return

    if player_name in user_data:
        xp = user_data[player_name]["xp"]
        level = user_data[player_name]["level"]
        next_level_xp = required_xp(level)
        await ctx.send(f"{ctx.author.mention}님의 현재 레벨: {level} (XP: {xp}/{next_level_xp})")
    else:
        await ctx.send(f"{ctx.author.mention}님은 아직 경험치가 없습니다.")

# Command: !exadd <닉네임> <경험치> (Admin Only)
@bot.command()
@commands.has_permissions(administrator=True)
async def exadd(ctx, minecraft_nickname: str, amount: int):
    if minecraft_nickname not in user_data:
        user_data[minecraft_nickname] = {"xp": 0, "level": 1}

    user_data[minecraft_nickname]["xp"] += amount

    level_up = False
    while user_data[minecraft_nickname]["xp"] >= required_xp(user_data[minecraft_nickname]["level"]):
        user_data[minecraft_nickname]["xp"] -= required_xp(user_data[minecraft_nickname]["level"])
        user_data[minecraft_nickname]["level"] += 1
        level_up = True

    save_data(XP_FILE, user_data)

    await ctx.send(f"`{minecraft_nickname}` 님에게 {amount} XP를 추가했습니다. (현재 XP: {user_data[minecraft_nickname]['xp']})")

    if level_up:
        level_up_channel = bot.get_channel(LEVEL_CHANNEL)
        if level_up_channel:
            await level_up_channel.send(f"{minecraft_nickname} 님이 레벨 {user_data[minecraft_nickname]['level']}로 상승했습니다!")

# Command: !exdel <닉네임> <경험치> (Admin Only)
@bot.command()
@commands.has_permissions(administrator=True)
async def exdel(ctx, minecraft_nickname: str, amount: int):
    if minecraft_nickname not in user_data:
        await ctx.send(f"`{minecraft_nickname}` 님은 아직 경험치가 없습니다.")
        return

    user_data[minecraft_nickname]["xp"] -= amount
    if user_data[minecraft_nickname]["xp"] < 0:
        user_data[minecraft_nickname]["xp"] = 0

    save_data(XP_FILE, user_data)

    await ctx.send(f"`{minecraft_nickname}` 님에게서 {amount} XP를 제거했습니다. (현재 XP: {user_data[minecraft_nickname]['xp']})")

# Run Bot
bot.run(WTOKEN)