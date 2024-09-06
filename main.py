import math
import os
import asyncio
import random
import discord
from discord.ext import commands
from discord import Intents
from dotenv import load_dotenv
import aiosqlite

load_dotenv()

def get_badwords():
    with open('badwords.txt', 'r', encoding='utf-8') as f:
        words = f.read().split(",")
        words_list = []
        for word in words:
            words_list.append(word.strip())
        
        return words_list

censored_words = get_badwords()  # Add your censored words here
spam_limit = 5
spam_time_frame = 10
user_messages = {}
levels = {}
user_warns = {}
mute_time = 60  # Time to mute (in seconds) after 3 warnings
max_warnings = 3

bot = discord.Bot(intents=Intents.all())

@bot.event
async def on_ready():
    await setup_db()
    print(f'Logged in as {bot.user}')

async def setup_db():
    async with aiosqlite.connect("db/levels.db") as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS user_levels (user_id INTEGER PRIMARY KEY, level INTEGER, xp INTEGER)"
        )
        await db.commit()

    async with aiosqlite.connect("db/warns.db") as db:      
        await db.execute(
            "CREATE TABLE IF NOT EXISTS user_warns (user_id INTEGER PRIMARY KEY, warns INTEGER)"

        )
        await db.commit()

# Kick a member
@bot.slash_command(name="kick", description="Kick a member.")
@commands.has_permissions(kick_members=True)

@discord.option("member", description="The member to kick", type=discord.Member)
@discord.option("reason", description="The reason for kicking", type=str)

async def kick(ctx: discord.ApplicationContext, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.respond(f'**{member.name}** has been kicked for **{reason}**.', delete_after=3.0)

# Ban a member
@bot.slash_command(name="ban", description="Ban a member.")
@commands.has_permissions(ban_members=True)

@discord.option("member", description="The member to ban", type=discord.Member)
@discord.option("reason", description="The reason for banning", type=str)

async def ban(ctx: discord.ApplicationContext, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.respond(f'**{member.name}** has been banned for **{reason}**.', delete_after=3.0)

# Unban a member
@bot.slash_command(name="unban", description="Unban a member.")
@commands.has_permissions(ban_members=True)

@discord.option("member_name", description="The name of the member to unban", type=str)

async def unban(ctx: discord.ApplicationContext, *, member_name: str):
    banned_users = await ctx.guild.bans()
    for ban_entry in banned_users:
        user = ban_entry.user
        if user.name == member_name:
            await ctx.guild.unban(user)
            await ctx.respond(f'**{user.name}** has been unbanned.', delete_after=3.0)
            return

    await ctx.respond(f'**{member_name}** was not found in the banned list.', delete_after=3.0)

# Mute a member
@bot.slash_command(name="mute", description="Mute a member.")
@commands.has_permissions(manage_roles=True)

@discord.option("member", description="The member to mute", type=discord.Member)
@discord.option("duration", description="The duration of the mute", type=int)
@discord.option("reason", description="The reason for muting", type=str)

async def mute(ctx: discord.ApplicationContext, member: discord.Member, *, reason="No reason", duration=None):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")

        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False)

    await member.add_roles(muted_role, reason=reason)
    await ctx.respond(f'**{member.name}** has been muted for **{reason}**.', delete_after=3.0)

    if duration:
        await asyncio.sleep(duration * 60)
        await member.remove_roles(muted_role)
        await ctx.respond(f'**{member.name}** has been unmuted after **{duration}** minutes.', delete_after=3.0)


# Unmute a member
@bot.slash_command(name="unmute", description="Unmute a member.")
@commands.has_permissions(manage_roles=True)

@discord.option("member", description="The member to unmute", type=discord.Member)

async def unmute(ctx: discord.ApplicationContext, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.respond(f'**{member.name}** has been unmuted.', delete_after=3.0)

@bot.event
async def on_message(message: discord.Message):

    if message.author.bot:
        return

    # Check for censored words
    if any(word in message.content.lower() for word in censored_words):
        await message.delete()
        await warn_user(message.author, message.channel, reason="Inappropriate language")
        return

    # Spam detection
    if message.author.id not in user_messages:
        user_messages[message.author.id] = []

    user_messages[message.author.id].append(message.created_at)

    # Remove messages older than the spam_time_frame
    user_messages[message.author.id] = [
        msg_time for msg_time in user_messages[message.author.id]
        if (message.created_at - msg_time).seconds <= spam_time_frame
    ]

    if len(user_messages[message.author.id]) > spam_limit:
        await warn_user(message.author, message.channel, reason="Spamming")
        return

    # Handle leveling system
    await add_xp(message.author)


async def warn_user(user: discord.User, channel: discord.TextChannel, reason="Violation"):
    async with aiosqlite.connect("db/warns.db") as db:
        cursor = await db.execute("SELECT warns FROM user_warns WHERE user_id = ?", (user.id,))
        data = await cursor.fetchone()

        if data:
            warns = data[0] + 1
        else:
            warns = 1
        # If the user exceeds the maximum warnings, mute or ban
        if warns >= max_warnings:
            await mute_user(user, channel)
        else:
            user_warns[user.id] = warns
            await channel.send(f"{user.mention}, you have been warned for: {reason}. Warning {warns}/{max_warnings}", delete_after=3.0)

        # Save the updated warnings
        await db.execute(
            "INSERT OR REPLACE INTO user_warns (user_id, warns) VALUES (?, ?)",
            (user.id, warns),
        )
        await db.commit()



async def mute_user(user: discord.User, channel: discord.TextChannel):
    guild = channel.guild
    muted_role = discord.utils.get(guild.roles, name="Muted")

    if not muted_role:
        # Create a "Muted" role if it doesn't exist
        muted_role = await guild.create_role(name="Muted")

        for channel in guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False)

    # Apply the mute
    await user.add_roles(muted_role)
    await channel.send(f"{user.mention} has been muted for {mute_time} seconds.", delete_after=3.0)

    # Unmute after the specified time
    await asyncio.sleep(mute_time)
    await user.remove_roles(muted_role)
    await channel.send(f"{user.mention} has been unmuted.", delete_after=3.0)

async def add_xp(user: discord.User):
    async with aiosqlite.connect("db/levels.db") as db:
        cursor = await db.execute("SELECT level, xp FROM user_levels WHERE user_id = ?", (user.id,))
        data = await cursor.fetchone()

        if data:
            level, xp = data
            xp += random.randint(10, 45)
        else:
            level, xp = 1, 0

        # Level up
        if xp >= (level * 100) + random.randint((level * 100) / 5, (level * 100) - 20):
            xp = 0
            level += 1
            await user.send(f"Congrats {user.mention}, you leveled up to **{level}**!")

        await db.execute(
            "INSERT OR REPLACE INTO user_levels (user_id, level, xp) VALUES (?, ?, ?)",
            (user.id, level, xp),
        )
        await db.commit()

# Get level command
@bot.slash_command(name="level", description="Get your current level.")
async def level(ctx: discord.ApplicationContext):

    if ctx.channel.name != "check-your-level":
        await ctx.respond(f"You can only check your level in the {ctx.guild.get_channel(1281689795919089756).mention} channel.") 
    else:      
        async with aiosqlite.connect("db/levels.db") as db:
            cursor = await db.execute("SELECT level, xp FROM user_levels WHERE user_id = ?", (ctx.author.id,))
            data = await cursor.fetchone()

            if data:
                level, xp = data
                await ctx.send(f"{ctx.author.mention}, you are level **{level}** with **{xp}**/{math.floor(level * 100)} XP.")
            else:
                await ctx.send(f"{ctx.author.mention}, you have no level yet.")

# Run the bot with token
bot.run(os.getenv("TOKEN"))
