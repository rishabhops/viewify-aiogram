import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import admin_user_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define constants for owner commands and examples
OWNER_COMMANDS = [
    "/add userid amount - Add coins to a user's balance",
    "/cut userid amount - Deduct coins from a user's balance",
    "/users - Display a list of registered users",
    "/check - Show users data",
    "/broadcast message - Send message to all bot users",
    "/upload - Upload users data",
    "/toprefs - Display a list of top 10 highest referral users",
    "/top10 - Shows top 10 users by balance",
]

EXAMPLES = (
    "\n\nExamples:\n"
    "/add 123456 500\n"
    "/cut 123456 200\n"
    "/check 123456\n"
    "/broadcast hello\n"
)

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register owner commands handler with the aiogram Dispatcher."""
    
    @dp.message(Command("owner"))
    async def owner_commands(message: types.Message):
        if message.from_user.id != admin_user_id:
            logger.info(f"Unauthorized access attempt to /owner by user {message.from_user.id}")
            await message.reply("You are not authorized to use this command.")
            return
        
        logger.info(f"User {message.from_user.id} accessed /owner command")
        await message.reply(
            "Owner commands:\n" + "\n".join(OWNER_COMMANDS) + EXAMPLES
        )