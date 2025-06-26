import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import admin_user_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register send message handler with the aiogram Dispatcher."""
    
    @dp.message(Command("send"))
    async def send_message_to_user(message: types.Message):
        if message.from_user.id != admin_user_id:
            logger.info(f"Unauthorized access attempt to /send by user {message.from_user.id}")
            await message.reply("You are not authorized to use this command.")
            return
        
        try:
            # Split the command and arguments
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await message.reply("Usage: /send <user_id> <message>")
                return
            
            user_id = int(parts[1])
            user_message = parts[2]
            
            # Send the message to the specified user
            await bot.send_message(user_id, user_message)
            logger.info(f"Message sent to user {user_id} by admin {admin_user_id}")
            await message.reply(f"Message sent to user {user_id}")
            
        except ValueError:
            logger.error(f"Invalid user ID provided: {parts[1]}")
            await message.reply("Invalid user ID. Please enter a valid user ID.")
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
            error_msg = str(e).lower()
            if "blocked by user" in error_msg:
                await message.reply(f"Cannot send message to user {user_id}: Bot is blocked by the user.")
            elif "chat not found" in error_msg:
                await message.reply(f"Cannot send message to user {user_id}: User not found or deactivated.")
            else:
                await message.reply(f"An error occurred: {e}")