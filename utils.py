import nextcord
import aiosqlite
import asyncio
from easy_pil import Canvas, Editor, Font, load_image_async
import os

# Example function to generate level card
async def generate_level_card(ctx: nextcord.Interaction, user_data):
    await ctx.response.defer()
    background = Editor(Canvas((800, 240), color="#23272A"))
    
    # Get the user's profile picture
    profile_image = await load_image_async(str(ctx.user.display_avatar.url))
    profile = Editor(profile_image).resize((200, 200)).circle_image()

    # Font setup
    font_25 = Font.poppins(size=25)
    font_40_bold = Font.poppins(size=40, variant="bold")

    # Add profile picture
    background.paste(profile, (20, 20))

    # Add text
    background.text((240, 20), user_data["name"], font=font_40_bold, color="white")
    background.text((250, 170), "Level", font=font_25, color="white")
    background.text((330, 160), user_data["level"], font=font_40_bold, color="white")

    # Add XP bar
    background.rectangle((390, 170), 360, 25, outline="white", stroke_width=2)
    background.bar(
        (394, 174),
        352,
        17,
        percentage=user_data["percentage"],
        fill="white",
        stroke_width=2,
    )

    # Additional text
    background.text((750, 135), f"XP : {user_data['xp']}", font=font_25, color="white", align="right")

    # Save and send the image
    background_image = background.image_bytes
    file = nextcord.File(fp=background_image, filename="level_card.png")
    await ctx.followup.send(file=file)



async def setup_lvl_db():

    async with aiosqlite.connect("db/levels.db") as db:
        await db.execute('''
                        CREATE TABLE IF NOT EXISTS user_levels
                        (id INTEGER PRIMARY KEY, level INTEGER, xp INTEGER)
                        ''')
        await db.commit()

async def setup_warns_db():
    async with aiosqlite.connect("db/warnings.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER PRIMARY KEY,
                count INTEGER
            )
        """)
        await db.commit()

# Function to add a warning to the database
async def add_warning(user_id):
    async with aiosqlite.connect("db/warnings.db") as db:
        cursor = await db.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT INTO warnings (user_id, count) VALUES (?, ?)", (user_id, 1))
        else:
            count = row[0] + 1
            await db.execute("UPDATE warnings SET count = ? WHERE user_id = ?", (count, user_id))
        await db.commit()

# Function to get the number of warnings
async def get_warnings(user_id):
    async with aiosqlite.connect("db/warnings.db") as db:
        cursor = await db.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

# Function to clear warnings
async def clear_warnings(user_id):
    async with aiosqlite.connect("db/warnings.db") as db:
        await db.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
        await db.commit()

# Function to mute a user
async def mute_user(channel: nextcord.TextChannel, member: nextcord.Member, duration):
    guild = channel.guild
    role = nextcord.utils.get(guild.roles, name="Muted")
    
    if not role:
        # Create the Muted role if it doesn't exist
        role = await guild.create_role(name="Muted")
        for channel in guild.channels:
            await channel.set_permissions(role, send_messages=False, speak=False)

    # Assign the Muted role to the user
    await member.add_roles(role)
    await channel.send(f"{member.mention} has been muted for {duration} seconds.")

    # Wait for the mute duration, then remove the role
    await asyncio.sleep(duration * 60)
    await member.remove_roles(role)
    await channel.send(f"{member.mention} has been unmuted.")

# Function to get or initialize a user's level and xp
async def get_user_level_data(user_id):
    async with aiosqlite.connect("db/levels.db") as db:
        cursor = await db.execute("SELECT xp, level FROM user_levels WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row is None:
            # Initialize user with level 1 and 0 XP
            await db.execute("INSERT INTO user_levels (id, xp, level) VALUES (?, ?, ?)", (user_id, 0, 1))
            await db.commit()
            return 0, 1
        return row
    

async def add_xp(user, xp_to_add=10):
    async with aiosqlite.connect("db/levels.db") as db:
        cursor = await db.execute("SELECT level, xp FROM user_levels WHERE id = ?", (user.id,))
        data = await cursor.fetchone()

        if data:
            level, xp = data
            xp += xp_to_add
        else:
            level, xp = 1, xp_to_add

        if xp >= level * 100:
            xp = 0
            level += 1
            await user.send(f"Congrats {user.mention}, you leveled up to **{level}**!")

        await db.execute(
            "INSERT OR REPLACE INTO user_levels (id, level, xp) VALUES (?, ?, ?)",
            (user.id, level, xp),
        )
        await db.commit()

async def init_db():
    os.makedirs("db", exist_ok=True)
    await setup_lvl_db()
    await setup_warns_db()

