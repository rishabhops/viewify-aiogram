import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Text
import aiosqlite
from functions import addBalance, isExists
from config import admin_user_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
BONUS_COOLDOWN = 72000  # 20 hours in seconds
BONUS_AMOUNT = 100  # Coins awarded for daily bonus

async def init_bonus_claims_db():
    """Initialize bonus_claims table in SQLite."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS bonus_claims (
                                user_id INTEGER PRIMARY KEY,
                                last_claim_time REAL
                                )''')
            await db.commit()
        logger.info("Initialized bonus_claims table")
    except Exception as e:
        logger.error(f"Error initializing bonus_claims table: {e}")

async def is_eligible_for_bonus(user_id: int) -> bool:
    """Check if the user is eligible for a daily bonus."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute(
                "SELECT last_claim_time FROM bonus_claims WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            current_time = asyncio.get_event_loop().time()
            
            if row is None or (current_time - row[0]) > BONUS_COOLDOWN:
                return True
            return False
    except Exception as e:
        logger.error(f"Error checking bonus eligibility for user {user_id}: {e}")
        return False

async def get_remaining_time(user_id: int) -> float:
    """Get remaining time for next bonus in seconds."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute(
                "SELECT last_claim_time FROM bonus_claims WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            current_time = asyncio.get_event_loop().time()
            
            if row is None:
                return 0
            
            elapsed_time = current_time - row[0]
            remaining_time = BONUS_COOLDOWN - elapsed_time
            return max(0, remaining_time)
    except Exception as e:
        logger.error(f"Error getting remaining time for user {user_id}: {e}")
        return BONUS_COOLDOWN

async def update_bonus_claim_time(user_id: int) -> bool:
    """Update the bonus claim time for the user."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            await db.execute(
                '''INSERT OR REPLACE INTO bonus_claims (user_id, last_claim_time)
                   VALUES (?, ?)''',
                (user_id, asyncio.get_event_loop().time())
            )
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating bonus claim time for user {user_id}: {e}")
        return False

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register daily bonus handler with the aiogram Dispatcher."""
    # Initialize bonus_claims table on plugin load
    dp.startup.register(init_bonus_claims_db)

    @dp.message(Text(equals="🎁daily bonus", ignore_case=True))
    async def daily_bonus(message: types.Message):
        user_id = message.from_user.id

        if not await isExists(user_id):
            await message.reply("You need to register first. Use /start to begin.")
            return

        if await is_eligible_for_bonus(user_id):
            if await addBalance(user_id, BONUS_AMOUNT):
                if await update_bonus_claim_time(user_id):
                    await message.reply(
                        "You have received 100 coins as your daily bonus! Please join @thanos_pro"
                    )
                else:
                    await message.reply(
                        "There was an error processing your bonus. Please try again later."
                    )
            else:
                await message.reply(
                    "There was an error adding coins to your balance. Please try again later."
                )
        else:
            remaining_time = await get_remaining_time(user_id)
            hours, remainder = divmod(remaining_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            await message.reply(
                f"You have already claimed your daily bonus. Please try again in "
                f"{int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds."
            )