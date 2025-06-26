import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import aiosqlite
import aiohttp
from functions import getData, cutBalance
from config import viewsapi, viewsserviceid, viewsapiurl, payment_channel

# Define constants
MIN_VIEWS = 100
MAX_VIEWS = 10000

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FSM for autoview setup
class AutoviewStates(StatesGroup):
    waiting_for_post_link = State()
    waiting_for_quantity = State()

# Initialize autoviews table
async def init_autoviews_db():
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS autoviews (
                            user_id INTEGER PRIMARY KEY,
                            post_link TEXT,
                            quantity INTEGER
                            )''')
        await db.commit()

def get_main_menu() -> ReplyKeyboardMarkup:
    """Create main menu markup."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒order"), KeyboardButton("🎁daily bonus"))
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("💳 buy coins"))
    markup.add(KeyboardButton("🗣 reffer"), KeyboardButton("📜 Help"))
    return markup

def validate_post_link(post_link: str) -> bool:
    """Validate the Telegram post link format."""
    if post_link is None:
        return False
    return post_link.startswith("https://t.me/") and post_link.count('/') >= 4

def extract_channel_username(post_link: str) -> str:
    """Extract the channel username from the post link."""
    if post_link is None:
        return None
    return post_link.split('/')[3]

async def save_user_details(user_id: int, post_link: str, quantity: int):
    """Save user autoview details in SQLite."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            await db.execute('''INSERT OR REPLACE INTO autoviews 
                               (user_id, post_link, quantity) 
                               VALUES (?, ?, ?)''',
                            (user_id, post_link, quantity))
            await db.commit()
        logger.info(f"Saved autoview details: user_id={user_id}, post_link={post_link}, quantity={quantity}")
    except Exception as e:
        logger.error(f"Error saving autoview details for user {user_id}: {e}")

async def get_autoview_settings() -> list:
    """Retrieve all autoview settings from SQLite."""
    try:
        async with aiosqlite.connect("bot_data.db") as db:
            cursor = await db.execute("SELECT user_id, post_link, quantity FROM autoviews")
            rows = await cursor.fetchall()
            return [{"user_id": row[0], "post_link": row[1], "quantity": row[2]} for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving autoview settings: {e}")
        return []

async def place_view_order(bot: Bot, user_id: int, post_link: str, quantity: int, c_username: str, posted: int):
    """Place an autoview order via the SMM panel."""
    fast_view_cost_per_100 = 150  # Cost per 100 views
    cost = (fast_view_cost_per_100 / 100) * quantity

    user_data = user_data = await getData(user_id)
    balance = float(user_data['balance'])

    if cost > balance:
        await bot.send_message(user_id, f"Insufficient balance. You need {cost} coins, but you only have {balance} coins.")
        return

    # Send API request to SMM panel
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(viewsapiurl, data={
                'key': viewsapi,
                'action': 'add',
                'service': f'{viewsserviceid}',
                'link': f'{post_link}',
                'quantity': quantity
            }) as response:
                response_json = await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            await bot.send_message(user_id, f"Error placing order: {e}")
            return
        except ValueError as e:
            logger.error(f"JSON decode error: {e}")
            await bot.send_message(user_id, "Error: Invalid response from API")
            return

        if response_json.get('error'):
            await bot.send_message(user_id, f"Error: {response_json['error']}")
        else:
            await cutBalance(user_id, cost)
            await bot.send_message(user_id, 
                f"Autoviews have been placed for your post: {post_link}\n\n"
                f"Order Details:\n\n"
                f"Views Ordered: {quantity}\n"
                f"Coins Deducted: {cost}\n"                                      
                f"User ID: {user_id}\n\n"
                f"Remaining Balance: {balance - cost}"
            )
            await bot.send_message(payment_channel, 
                f"Autoviews have been placed for the post: {post_link}\n\n"
                f"Order Details:\n\n"
                f"Views Ordered: {quantity}\n"
                f"Coins Deducted: {cost}\n"
                f"User ID: {user_id}\n\n"
                f"Remaining Balance: {balance - cost}"
            )

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register autoview handlers with the aiogram Dispatcher."""
    # Initialize autoviews table on plugin load
    dp.startup.register(init_autoviews_db)

    @dp.message(Text(equals="👁‍🗨 set autoview"))
    async def order_views(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("❌ Cancel"))
        await message.reply(
            "Follow the steps 🪜\n\n1. Make this bot (@Viewify_Bot) an admin in your channel.\n\n2. Send the link to your Telegram post.",
            reply_markup=markup
        )
        await state.set_state(AutoviewStates.waiting_for_post_link)

    @dp.message(AutoviewStates.waiting_for_post_link)
    async def get_post_link(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if message.text == "❌ Cancel":
            await message.reply("Operation canceled.", reply_markup=get_main_menu())
            await state.clear()
            return
        post_link = message.text
        if not validate_post_link(post_link):
            await message.reply("Invalid post link. Please send a correct Telegram post link.")
            return
        await state.update_data(post_link=post_link)
        await message.reply(
            f"150 coins = 100 auto views\n\nHow many auto views do you want per post? (Min: {MIN_VIEWS}, Max: {MAX_VIEWS})",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ Cancel"))
        )
        await state.set_state(AutoviewStates.waiting_for_quantity)

    @dp.message(AutoviewStates.waiting_for_quantity)
    async def get_order_quantity(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if message.text == "❌ Cancel":
            await message.reply("Operation canceled.", reply_markup=get_main_menu())
            await state.clear()
            return
        try:
            quantity = int(message.text)
            if quantity < MIN_VIEWS or quantity > MAX_VIEWS:
                await message.reply(
                    f"Invalid quantity. Please enter a number between {MIN_VIEWS} and {MAX_VIEWS}.",
                    reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ Cancel"))
                )
                return
            data = await state.get_data()
            post_link = data['post_link']
            await save_user_details(user_id, post_link, quantity)
            await message.reply(
                "Your details have been saved for automatic views.\n\nMake sure you make this bot (@Viewify_Bot) an admin in your channel, else auto view will not work.",
                reply_markup=get_main_menu()
            )
            await state.clear()
        except ValueError:
            await message.reply(
                "Invalid quantity. Please enter a number.",
                reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("❌ Cancel"))
            )

    @dp.channel_post()
    async def handle_channel_post(message: types.ChannelPost, bot: Bot):
        channel_username = message.chat.username
        logger.info(f"New post in channel: {channel_username}")
        autoview_settings = await get_autoview_settings()
        for user_details in autoview_settings:
            logger.info(f"Checking user details: {user_details}")
            if extract_channel_username(user_details['post_link']) == channel_username:
                user_id = user_details['user_id']
                post_link = f"https://t.me/{channel_username}/{message.message_id}"
                quantity = user_details['quantity']
                logger.info(f"Placing order for user {user_id} on post {post_link} with quantity {quantity}")
                await place_view_order(bot, user_id, post_link, quantity, channel_username, message.message_id)