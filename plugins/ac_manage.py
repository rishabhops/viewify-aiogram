import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from functions import isExists, addBalance, cutBalance, getData
from config import admin_user_id

# Configure logging
logger = logging.getLogger(__name__)

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register admin command handlers with the aiogram Dispatcher."""
    
    @dp.message(Command("cut"))
    async def cut_coins(message: types.Message):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this command.")
            return

        try:
            command_parts = message.text.split()

            # Handle reply to user
            if message.reply_to_message:
                if len(command_parts) != 2:
                    raise ValueError("When replying to a user, use format: /cut amount")
                user_id = str(message.reply_to_message.from_user.id)
                amount = float(command_parts[1])
            # Handle direct command
            else:
                if len(command_parts) != 3:
                    raise ValueError("When not replying, use format: /cut userid amount")
                user_id = command_parts[1]
                amount = float(command_parts[2])

            # Check if the user exists
            if not await isExists(user_id):
                await message.reply("User does not exist.")
                return

            # Cut balance
            if amount > 0:
                if await cutBalance(user_id, amount):
                    # Get username for notification
                    try:
                        chat = await bot.get_chat(user_id)
                        user_mention = f"@{chat.username}" if chat.username else f"User {user_id}"
                    except Exception as e:
                        logger.error(f"Error fetching username for user {user_id}: {e}")
                        user_mention = f"User {user_id}"

                    await message.reply(f"{amount} coins deducted from {user_mention}'s balance.")
                    await bot.send_message(user_id, f"{amount} coins have been deducted from your balance.")
                else:
                    await message.reply("User doesn't have enough balance for this deduction.")
            else:
                await message.reply("Amount should be a positive value.")

        except ValueError as ve:
            await message.reply(str(ve))
        except Exception as e:
            logger.error(f"Error in /cut command: {e}")
            await message.reply("An error occurred. Please check the format and try again.")

    @dp.message(Command("add"))
    async def add_coins(message: types.Message):
        if message.from_user.id != admin_user_id:
            await message.reply("You are not authorized to use this command.")
            return

        try:
            command_parts = message.text.split()

            # Handle reply to user
            if message.reply_to_message:
                if len(command_parts) != 2:
                    raise ValueError("When replying to a user, use format: /add amount")
                user_id = str(message.reply_to_message.from_user.id)
                amount = float(command_parts[1])
            # Handle direct command
            else:
                if len(command_parts) != 3:
                    raise ValueError("When not replying, use format: /add userid amount")
                user_id = command_parts[1]
                amount = float(command_parts[2])

            # Check if the user exists
            if not await isExists(user_id):
                await message.reply("User does not exist.")
                return

            # Add or cut balance
            if amount > 0:
                if await addBalance(user_id, amount):
                    # Get username for notification
                    try:
                        chat = await bot.get_chat(user_id)
                        user_mention = f"@{chat.username}" if chat.username else f"User {user_id}"
                    except Exception as e:
                        logger.error(f"Error fetching username for user {user_id}: {e}")
                        user_mention = f"User {user_id}"

                    await message.reply(f"{amount} coins added to {user_mention}'s balance.")
                    await bot.send_message(user_id, f"{amount} coins have been added to your balance.")
            elif amount < 0:
                current_balance = float((await getData(user_id))['balance'])
                if current_balance + amount < 0:
                    await message.reply("The user's balance cannot go negative.")
                    return
                if await cutBalance(user_id, abs(amount)):
                    # Get username for notification
                    try:
                        chat = await bot.get_chat(user_id)
                        user_mention = f"@{chat.username}" if chat.username else f"User {user_id}"
                    except Exception as e:
                        logger.error(f"Error fetching username for user {user_id}: {e}")
                        user_mention = f"User {user_id}"

                    await message.reply(f"{abs(amount)} coins deducted from {user_mention}'s balance.")
                    await bot.send_message(user_id, f"{abs(amount)} coins have been deducted from your balance.")
            else:
                await message.reply("Amount should be a non-zero value.")

        except ValueError as ve:
            await message.reply(str(ve))
        except Exception as e:
            logger.error(f"Error in /add command: {e}")
            await message.reply("An error occurred. Please check the format and try again.")