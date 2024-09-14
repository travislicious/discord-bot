import os
import aiohttp
import time
import re
import random
import asyncio
import nextcord
from nextcord.ext import commands
from nextcord import Intents
from dotenv import load_dotenv
import utils
import webrequests
import webserver
import ai_utils
from PIL import Image

load_dotenv(override=True)

def get_badwords():
    with open('badwords.txt', 'r', encoding='utf-8') as f:
        words = f.read().split(",")
        words_list = []
        for word in words:
            words_list.append(word.strip())
        
        return words_list

censored_words = get_badwords()  # Add your censored words here
# Store user activity
user_messages = {}

# Parameters for spam detection
MESSAGE_THRESHOLD = 5
TIME_WINDOW = 10  # in seconds
MENTION_THRESHOLD = 5
WARNING_THRESHOLD = 3  # Warnings before mute
MUTE_DURATION = 10  # Mute duration in minutes
XP_PER_MESSAGE = (5, 35)

MUTED_ROLE_NAME = "Muted"

intents = Intents.all()
bot = commands.Bot(intents=intents)

@bot.event
async def on_ready():
    await utils.init_db()
    await bot.sync_all_application_commands()
    print(f'Logged in as {bot.user.name}')

async def get_or_create_muted_role(guild: nextcord.Guild):
    """Check if the muted role exists, and create it if not."""
    muted_role = nextcord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
    
    if muted_role is None:
        muted_role = await guild.create_role(
            name=MUTED_ROLE_NAME,
            permissions=nextcord.Permissions(send_messages=False, speak=False),
            reason="Creating Muted role for muting members."
        )
        
        # Modify permissions for all channels in the guild to prevent speaking
        for channel in guild.channels:
            await channel.set_permissions(muted_role, send_messages=False, speak=False)
    
    return muted_role
@bot.slash_command(name="level", description="Get your current level")
async def level(ctx: nextcord.Interaction):

    if ctx.channel.name == "check-your-level":
        user_id = ctx.user.id
        xp, level = await utils.get_user_level_data(user_id)

        # Example user data
        user_data = {
            "name": f"{ctx.user.name}#{ctx.user.discriminator}",
            "level": str(level),
            "xp": f"{xp} / {level * 100}",
            "percentage": int((xp / (level * 100)) * 100),
        }
        
        await utils.generate_level_card(ctx, user_data)
    else:
        channel = nextcord.utils.get(ctx.guild.channels, name="check-your-level")
        await ctx.send(f"This command is only available in the {channel.mention} channel.", ephemeral=True)


@bot.slash_command(name="info", description="Get your info.")
async def info(interaction: nextcord.Interaction):
    """
    Get your info.
    """
    user = interaction.user

    embed = nextcord.Embed(title=f"{user.display_name}'s Info:", description="Here is your info.")
    embed.add_field(name="**Username :** ", value=user.name, inline=False)
    embed.add_field(name="**Display Name:** ", value=user.display_name, inline=False)
    embed.add_field(name="**Discriminator:** ", value=user.discriminator, inline=False)
    human_readable_date = user.joined_at.strftime("%B %d, %Y")
    embed.add_field(name="**Joined at:** ", value=human_readable_date, inline=False)
    embed.add_field(name="**ID:** ", value=user.id, inline=False)
    embed.add_field(name="**On mobile:** ", value=user.is_on_mobile(), inline=False)
    embed.add_field(name="**Top role:** ", value=user.top_role, inline=False)
    embed.add_field(name="**Roles:** ", value="")

    for pos, role in enumerate(user.roles):
        if role.name in 'Muted':
            pass
        embed.add_field(name=f"**Role #{pos}**", value=role.name, inline=False)

    embed.set_thumbnail(url=user.display_avatar)
    await interaction.response.send_message("**Your Info**: ", embed=embed, ephemeral=True)

@bot.slash_command(name="greet", description='Greet someone.')
async def greet(interaction: nextcord.Interaction, member: nextcord.Member):
    await interaction.response.send_message(f'Hello {member.mention}!')

@bot.slash_command(name="weather", description="Get weather of a country/city.")
async def weather(interaction: nextcord.Interaction, place: str):
    """
    This command retrieves information about a given country.
    
    Args:
        place: The name of the country/city to get weather.
    """
        
    await interaction.response.defer()
    url = f"http://wttr.in/{place}?format=3"
    response = webrequests.get_weather(url)
    embed = nextcord.Embed(title="**Weather Fetch**", description=f"Weather in **{place.capitalize()}**.")
    if response.status_code == 200:
        embed.add_field(name="Weather Data", value=response.text, inline=False)
        await interaction.followup.send(embed=embed)
        response.close()
    else:
        await interaction.followup.send("Failed to fetch weather.", ephemeral=True)


@bot.slash_command(name="find-country", description="Get information about a country by its name.")
async def find_country(interaction: nextcord.Interaction, country_name: str):
    """
    This command retrieves information about a given country.

    Args:
        country_name: The name of the country to get information about.
    """
    # Defer the interaction response while fetching data
    await interaction.response.defer()

    url = f"https://restcountries.com/v3.1/name/{country_name}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    await interaction.followup.send(f"No data found for '{country_name}'. Please try again with a valid country name.", ephemeral=True)
                    return

                data = await response.json()

                if len(data) == 0:
                    await interaction.followup.send(f"No data found for '{country_name}'. Please try again with a valid country name.", ephemeral=True)
                    return

                country_data = data[0]
                
                # Extracting relevant information
                name = country_data.get("name", {}).get("common", "N/A")
                capital = country_data.get("capital", ["N/A"])[0]
                region = country_data.get("region", "N/A")
                subregion = country_data.get("subregion", "N/A")
                population = country_data.get("population", "N/A")
                languages = ", ".join([lang for lang in country_data.get("languages", {}).values()])
                translations = country_data.get("translations", {})['cym']['official']
                flag = country_data.get("flags", {}).get("png", "")
                coat_of_arms = country_data.get("coatOfArms", {}).get("png", "")
                
                # Create the embed to display the information
                embed = nextcord.Embed(title=f"Information about {name}", color=nextcord.Color.blue())
                embed.add_field(name="**Capital**", value=capital, inline=False)
                embed.add_field(name="**Region**", value=region, inline=False)
                embed.add_field(name="**Subregion**", value=subregion, inline=False)
                embed.add_field(name="**Population**", value=f"{population:,}", inline=False)

                if len(languages) > 1024:
                    languages = languages[:1021] + "..."

                embed.add_field(name="**Languages**", value=languages or "N/A", inline=False)
                embed.add_field(name="**Translations**", value=translations or "N/A", inline=False)
                
                # Add Flag and Coat of Arms images
                if flag:
                    embed.set_image(url=flag)
                if coat_of_arms:
                    embed.set_thumbnail(url=coat_of_arms)
                
                await interaction.followup.send(embed=embed)
                await session.close()
        
        except aiohttp.ClientError as e:
            # Handle any aiohttp client exceptions (network issues, etc.)
            await interaction.followup.send(f"An error occurred while fetching country data: {str(e)}", ephemeral=True)

@bot.slash_command(name="unban", description="Unban a Member")
async def unban(interaction: nextcord.Interaction, member: nextcord.User):
    """
    Unban a member from the server.
    
    Args:
        member: The member to unban.
    """
    
    if interaction.user != interaction.guild.owner and not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You do not have permission to unban members.", ephemeral=True)
        return

    banned_members = await interaction.guild.bans()
    for ban_entry in banned_members:
        if ban_entry.user == member:
            await interaction.guild.unban(member)
            await interaction.response.send_message(f'{member.mention} has been unbanned.', ephemeral=True)
            return
    
    await interaction.response.send_message(f'{member.mention} is not banned.', ephemeral=True)

@bot.slash_command(name="mute", description="Mute a member.")
async def mute(interaction: nextcord.Interaction, member: nextcord.Member, duration: float = None, reason: str = "No reason."):
    """
    This command mutes a member for a specified duration with an optional reason.
    
    Args:
        member: The member to mute.
        duration: The duration of the mute in minutes (optional).
        reason: The reason for the mute (optional).
    """
    if interaction.user != interaction.guild.owner and not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You do not have permission to mute members.", ephemeral=True)
        return

    muted_role = await get_or_create_muted_role(interaction.guild)

    if member.top_role.name == "Moderator":
        await interaction.response.send_message("You cannot mute a moderator.", ephemeral=True)
        return
    
    if muted_role in member.roles:
        await interaction.response.send_message(f"{member.display_name} is already muted.", ephemeral=True)
    else:
        await member.add_roles(muted_role, reason=reason)
        await interaction.response.send_message(f"{member.display_name} has been muted.", ephemeral=True)

        
        if duration:
            await asyncio.sleep(duration * 60)
            await member.remove_roles(muted_role)
            await interaction.response.send_message(f"{member.display_name} has been unmuted after {round(duration)} minutes.", ephemeral=True)

@bot.slash_command(name="unmute", description="Unmute a member.")
async def unmute(interaction: nextcord.Interaction, member: nextcord.Member):
    """
    This command unmutes a member.

    Args:
        member: The member to unmute.
    """
    if interaction.user != interaction.guild.owner and not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You do not have permission to unmute members.", ephemeral=True)
        return

    muted_role = await get_or_create_muted_role(interaction.guild)

    if muted_role not in member.roles:
        await interaction.response.send_message(f"{member.display_name} is not muted.", ephemeral=True)
    else:
        await member.remove_roles(muted_role)
        await interaction.response.send_message(f"{member.display_name} has been unmuted.", ephemeral=True)

@bot.slash_command(name="prompt-image", description="Generate an image from prompt.")
async def prompt_image(interaction: nextcord.Interaction, img_prompt: str):
    """
    This command generates an image from a prompt.
    
    Args:
        prompt: The image prompt.
    """
    await interaction.response.defer()
    image_path = await ai_utils.generate_images(img_prompt)
    await interaction.followup.send(file=nextcord.File(image_path))

@bot.slash_command(name="ask-howdy", description="Ask howdy.")
async def prompt(interaction: nextcord.Interaction, txt_prompt: str):
    """
    This command asks howdy.
    
    Args:
        prompt: The prompt.
    """
    await interaction.response.defer()
    resp = await ai_utils.generate_text(txt_prompt)
    await interaction.followup.send(resp)

@bot.event
async def on_message(message: nextcord.Message):


    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message):
        print(message.content.lower())
        resp = await ai_utils.chat(message.content.lower(), message.author.display_name)
        await message.channel.send(resp)

    
    user_id = message.author.id
    current_time = time.time()

    content = message.content.lower()
    for bad_word in censored_words:
        pattern = r'\b' + re.escape(bad_word) + r'\b'
        if re.search(pattern, content):
            await utils.add_warning(message.author.id)
            warn_count = await utils.get_warnings(message.author.id)
            await message.delete()
            await message.channel.send(f"{message.author.mention}, please avoid using inappropriate language. You now have {warn_count} warning(s).")
        
        # Issue a mute if warning threshold is met
            if warn_count >= WARNING_THRESHOLD:
                await utils.mute_user(message.channel, message.author, MUTE_DURATION)
                await utils.clear_warnings(message.author.id)
            break  # Reset warnings after mute

    # If user isn't tracked yet, initialize
    if user_id not in user_messages:
        user_messages[user_id] = []

    # Append the current message timestamp
    user_messages[user_id].append(current_time)

    # Remove old messages outside the time window
    user_messages[user_id] = [msg_time for msg_time in user_messages[user_id] if current_time - msg_time <= TIME_WINDOW]

    # Spam Detection: Message Flooding
    if len(user_messages[user_id]) > MESSAGE_THRESHOLD:
        await message.channel.send(f"{message.author.mention} is spamming! Please stop.")
        await message.delete()

    # Spam Detection: Excessive Mentions
    if len(message.mentions) > MENTION_THRESHOLD:
        await message.channel.send(f"{message.author.mention}, you are mentioning too many users!")
        await message.delete()

    xp_gained = random.randint(*XP_PER_MESSAGE)
    await utils.add_xp(message.author, xp_gained)

    # Allow commands to be processed
    await bot.process_commands(message)


@bot.event
async def on_member_join(member: nextcord.Member):
    guild = member.guild
    total_members = guild.member_count

    await member.send(f'Hey {member.mention}, Welcome in the Hemmings\'s Servers.\nLet\'s introduce yourself in the twilight room. You\'re the member **#{total_members}**')
    
webserver.keep_alive()
bot.run(os.getenv("TOKEN"))
