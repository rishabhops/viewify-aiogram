import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import aiosqlite

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FSM for canceling autoview
class CancelAutoviewStates(StatesGroup):
    waiting_for_channel_link = State()

def get_main_menu() -> ReplyKeyboardMarkup:
    """Create main menu markup."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒order"), KeyboardButton("🎁daily bonus"))
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("💳 buy coins"))
    markup.add(KeyboardButton("🗣 reffer"), KeyboardButton("📜 Help"))
    return markup

def extract_channel_username(post_link: str) -> str:
    """Extract the channel username from the post link."""
    try:
        return post_link.split('/')[3]
    except IndexError as e:
        logger.error(f"Error extracting channel username from {post_link}: {e}")
        raise ValueError("Invalid channel link format")

async def cancel_autoview_entry(user_id: int, channel_username: str) -> bool:
    """Delete autoview entry for the user and channel from SQLite."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute(
                "SELECT post_link FROM autoviews WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            if not rows:
                return False
            
            # Check if any entry matches the channel username
            found = False
            for row in rows:
                post_link = row[0]
                if extract_channel_username(post_link) == channel_username:
                    found = True
                    break
            
            if found:
                await db.execute(
                    "DELETE FROM autoviews WHERE user_id = ? AND post_link LIKE ?",
                    (user_id, f"https://t.me/{channel_username}%")
                )
                await db.commit()
                logger.info(f"Auto view entry removed for user {user_id} and channel {channel_username}")
                return True
            else:
                logger.info(f"No auto view found for user {user_id} and channel {channel_username}")
                return False
    except Exception as e:
        logger.error(f"Error canceling autoview for user {user_id}: {e}")
        return False

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register cancel autoview handlers with the aiogram Dispatcher."""
    
    @dp.message(Text(equals="💔 cancel autoview", ignore_case=True))
    async def cancel_autoview(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        logger.info(f"User {user_id} requested to cancel autoview.")
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("❌ Cancel"))
        await message.reply(
            "Please send the link to your Telegram channel.",
            reply_markup=markup
        )
        await state.set_state(CancelAutoviewStates.waiting_for_channel_link)

    @dp.message(CancelAutoviewStates.waiting_for_channel_link)
    async def get_channel_link(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if message.text == "❌ Cancel":
            await message.reply("Operation canceled.", reply_markup=get_main_menu())
            await state.clear()
            return

        channel_link = message.text
        logger.info(f"User {user_id} provided channel link: {channel_link}")

        try:
            channel_username = extract_channel_username(channel_link)
            logger.info(f"Extracted channel username: {channel_username}")
            success = await cancel_autoview_entry(user_id, channel_username)
            if success:
                await message.reply(
                    f"Auto view canceled for channel: {channel_link}",
                    reply_markup=get_main_menu()
                )
            else:
                await message.reply(
                    f"No auto view found for your user ID and the specified channel: {channel_link}",
                    reply_markup=get_main_menu()
                )
        except ValueError:
            await message.reply(
                "Invalid channel link. Please try again.",
                reply_markup=get_main_menu()
            )
        except Exception as e:
            logger.error(f"Unexpected error for user {user_id}: {e}")
            await message.reply(
                "An error occurred. Please try again.",
                reply_markup=get_main_menu()
            )
        
        await state.clear()