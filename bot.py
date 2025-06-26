import asyncio
import logging
import re
import os
import importlib.util
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ParseMode, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
import aiohttp
from config import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=bot_token, parse_mode=ParseMode.HTML)
dp = Dispatcher()
bot_username = None  # Will be set in startup

# SQLite database setup
async def init_db():
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            balance REAL DEFAULT 0.0,
                            ref_by TEXT DEFAULT 'none',
                            referred INTEGER DEFAULT 0,
                            welcome_bonus INTEGER DEFAULT 0,
                            total_refs INTEGER DEFAULT 0
                            )''')
        await db.commit()

# FSM for view order process
class OrderStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_link = State()

# Load plugins dynamically (async-compatible)
async def load_plugins():
    plugin_folder = 'plugins'
    for filename in os.listdir(plugin_folder):
        if filename.endswith('.py'):
            plugin_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(plugin_name, os.path.join(plugin_folder, filename))
            plugin_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_module)
            if hasattr(plugin_module, 'register_plugin'):
                plugin_module.register_plugin(bot, dp)  # Pass dp for async handlers

# Check if user is a member of required channels
async def is_member_of_channel(user_id: int) -> bool:
    for channel in required_channels:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking channel membership for {user_id}: {e}")
            return False
    return True

# Get user data from SQLite
async def get_user_data(user_id: int) -> dict:
    async with aiosqlite.connect("bot_data.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "user_id": str(row[0]),
                "username": row[1],
                "balance": row[2],
                "ref_by": row[3],
                "referred": row[4],
                "welcome_bonus": row[5],
                "total_refs": row[6]
            }
        return None

# Insert or update user in SQLite
async def insert_user(user_id: int, data: dict):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute('''INSERT OR REPLACE INTO users 
                            (user_id, username, balance, ref_by, referred, welcome_bonus, total_refs)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (int(data["user_id"]), data.get("username", "Unknown"), data["balance"],
                          data["ref_by"], data["referred"], data["welcome_bonus"], data["total_refs"]))
        await db.commit()

# Add balance to user
async def add_balance(user_id: int, amount: float):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# Cut balance from user
async def cut_balance(user_id: int, amount: float):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# Set welcome bonus status
async def set_welcome_status(user_id: int):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("UPDATE users SET welcome_bonus = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

# Set referred status
async def set_referred_status(user_id: int):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("UPDATE users SET referred = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

# Add referral count
async def add_ref_count(ref_by: str):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("UPDATE users SET total_refs = total_refs + 1 WHERE user_id = ?", (int(ref_by),))
        await db.commit()

# Check if user exists
async def is_exists(user_id: int) -> bool:
    async with aiosqlite.connect("bot_data.db") as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

# Check if ref_by exists
async def track_exists(ref_by: str) -> bool:
    async with aiosqlite.connect("bot_data.db") as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (int(ref_by),))
        return await cursor.fetchone() is not None

# Create main menu markup
def get_main_menu() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🛒order"), KeyboardButton("🎁daily bonus"))
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("💳 buy coins"))
    markup.add(KeyboardButton("🗣 reffer"), KeyboardButton("📜 Help"))
    return markup

# Start command handler
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    global bot_username
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name
    ref_by = message.text.split()[1] if len(message.text.split()) > 1 and message.text.split()[1].isdigit() else None

    # Initialize bot username if not set
    if bot_username is None:
        me = await bot.get_me()
        bot_username = f"@{me.username}"

    # Handle referral
    if ref_by and int(ref_by) != user_id and await track_exists(ref_by):
        if not await is_exists(user_id):
            initial_data = {
                "user_id": str(user_id),
                "username": username,
                "balance": 0.0,
                "ref_by": ref_by,
                "referred": 0,
                "welcome_bonus": 0,
                "total_refs": 0
            }
            await insert_user(user_id, initial_data)
            await add_ref_count(ref_by)

    # Insert new user if not exists
    if not await is_exists(user_id):
        initial_data = {
            "user_id": str(user_id),
            "username": username,
            "balance": 0.0,
            "ref_by": "none",
            "referred": 0,
            "welcome_bonus": 0,
            "total_refs": 0
        }
        await insert_user(user_id, initial_data)

    # Check channel membership
    if not await is_member_of_channel(user_id):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("✩TP✩✩", url="https://t.me/THANOS_PRO"),
             InlineKeyboardButton("✩viewify✩", url="https://t.me/xviewify")]
        ])
        await bot.send_photo(
            user_id,
            photo=logo_url,
            caption="You need to join the following channels before continuing:\n\nafter join channel send again /start",
            reply_markup=markup
        )
        return

    # Handle welcome bonus
    user_data = await get_user_data(user_id)
    if user_data["welcome_bonus"] == 0:
        await bot.send_message(user_id, f"🎉 +{welcome_bonus} coins as welcome bonus!")
        await add_balance(user_id, welcome_bonus)
        await set_welcome_status(user_id)

    # Handle referral bonus
    if user_data["ref_by"] != "none" and user_data["referred"] == 0:
        await bot.send_message(user_data["ref_by"], f"You referred {first_name} +{ref_bonus}")
        await add_balance(int(user_data["ref_by"]), ref_bonus)
        await set_referred_status(user_id)

    # Send welcome message with main menu
    await bot.send_photo(
        user_id,
        photo=logo_url,
        caption="""Hi, welcome to Viewify! ✋️\n\n
        🤗 With Viewify it's just a few taps to increase views of your Telegram posts. 💓\n\n
        👇 To continue choose an item below""",
        reply_markup=get_main_menu()
    )

# Text message handler
@dp.message(Text(equals=["👤 My Account", "🖗️", "🗣 reffer", "ref", "📜 Help", "💳 buy coins", "👁‍🗺️ Order View", "🛒order"]))
async def handle_text(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name

    if message.text == "👤 My Account":
        user_data = await get_user_data(user_id)
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        msg = f"""<b><u>My Account</u></b>
🆔 User id: {user_id}
👤 Username: @{username}
🗣 Invited users: {user_data['total_refs']}
🔗 Referral link: {referral_link}

👁‍🗨 Balance: <code>{user_data['balance']}</code> Views
"""
        await message.reply(msg)

    elif message.text == "🗣 reffer":
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        user_data = await get_user_data(user_id)
        await message.reply(
            f"<b>Referral link:</b> {referral_link}\n\n<b><u>Share it with friends and get {ref_bonus} coins for each referral</u></b>"
        )

    elif message.text == "📜 Help":
        msg = f"""<b><u>❓ Frequently Asked Questions</u></b>
    
<b><u>• Are the views real?</u></b>
No, the views are completely fake and no real observations are made.

<b><u>• What is the minimum and maximum views order for a single post?</u></b>
The minimum and maximum views order for a post is {min_view} and {max_view} views, respectively.

<b><u>• How to increase your credit?</u></b>
1- Invite your friends to Bot, for each invitation, {ref_bonus} free views will be added to your account and {welcome_bonus} to your invited user.
2- Buy one of the views packages. We accept Paytm, WebMoney, Perfect Money, Payeer, Bitcoin, Tether and other Cryptocurrencies.

<b><u>• Is it possible to transfer balance to other users?</u></b>
Yes, if your balance is more than 5k and you want to transfer all of them, you can send a request to support @thanosceo here you can request coin transfer.
🆘 In case you have any problem, contact @thanosceo"""
        await message.reply(msg)

    elif message.text == "💳 buy coins":
        msg = f"""<b><u>💎 Pricing 💎</u></b>
<i>👉 Choose one of the views packages and pay its cost via provided payment methods.</i>
<b><u>📜 Packages:</u></b>
<b> 🪙1k coins for 3 India rupees
🪙 10k coins for 30 inr
🪙 20k views for 60inr
</b>

💰 Pay with Bitcoin, USDT, BSC, BUSD, ... 👉🏻 @thanosceo
available payment methods Paytm, phone pe, binance, ... 👉🏻 @thanosceo

<b>🆔 Your id:</b> <code>{user_id}</code>
"""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💲 binance", url="https://t.me/thanosceo"),
             InlineKeyboardButton("gpay", url="https://t.me/thanosceo")],
            [InlineKeyboardButton("💸 Paytm", url="https://t.me/thanosceo"),
             InlineKeyboardButton("💰 phone pe", url="https://t.me/thanosceo")]
        ])
        await message.reply(msg, reply_markup=markup)

    elif message.text in ["🛒order", "👁‍🗨 Order View"]:
        user_data = await get_user_data(user_id)
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("✘ Cancel"))
        msg = f"""👉 Enter number of Views in range ({min_view}, {max_view}) 👇🏻
👁‍🗨 Your balance: {user_data['balance']} views 
"""
        await message.reply(msg, reply_markup=markup)
        await state.set_state(OrderStates.waiting_for_amount)

# Handle view amount input
@dp.message(OrderStates.waiting_for_amount)
async def view_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "✘ Cancel":
        await message.reply("Operation successfully canceled.", reply_markup=get_main_menu())
        await state.clear()
        return

    amount = message.text
    user_data = await get_user_data(user_id)

    if not amount.isdigit():
        await message.reply("📛 Invalid value. Enter only numeric value.", reply_markup=get_main_menu())
        await state.clear()
        return

    if int(amount) < min_view:
        await message.reply(f"❌ Minimum - {min_view} Views", reply_markup=get_main_menu())
        await state.clear()
        return

    if float(amount) > float(user_data['balance']):
        await message.reply("❌ You can't purchase more views than your balance", reply_markup=get_main_menu())
        await state.clear()
        return

    await state.update_data(amount=amount)
    await message.reply("Enter link 🔗", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("✘ Cancel")))
    await state.set_state(OrderStates.waiting_for_link)

# Validate Telegram post link
def is_valid_link(link: str) -> bool:
    pattern = r'^https?://t\.me/[a-zA-Z0-9_]{5,}/\d+$'
    return re.match(pattern, link) is not None

# Send order to SMM panel
async def send_order_to_smm_panel(link: str, amount: str) -> dict:
    parts = link.split('/')
    channel = parts[-2]
    post_id = parts[-1]
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(viewsapiurl, data={
                'key': viewsapi,
                'action': 'add',
                'service': f'{viewsserviceid}',
                'link': f"{link}",
                'quantity': amount
            }) as response:
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Error sending order to SMM panel: {e}")
            return None

# Handle view link input
@dp.message(OrderStates.waiting_for_link)
async def view_link(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    link = message.text
    data = await state.get_data()
    amount = data['amount']

    if message.text == "✘ Cancel":
        await message.reply("Operation successfully canceled.", reply_markup=get_main_menu())
        await state.clear()
        return

    if not is_valid_link(link):
        await message.reply(
            "❌ Invalid link provided. Please provide a valid Telegram post link.",
            reply_markup=get_main_menu()
        )
        await state.clear()
        return

    result = await send_order_to_smm_panel(link, amount)
    if result is None or 'order' not in result or result['order'] is None:
        msg = "*🤔 Something went wrong please try again later!*"
        if result and 'error' in result:
            msg += f"\n{result['error']}"
        await message.reply(msg, parse_mode="markdown", reply_markup=get_main_menu())
        await state.clear()
        return

    oid = result['order']
    await cut_balance(user_id, float(amount))

    # Send confirmation to user
    await message.reply(
        (f"*✅ Your Order Has Been Submitted and Processing\n\n"
         f"Order Details :\n"
         f"ℹ️ Order ID :* `{oid}`\n"
         f"*🔗 Link : {link}*\n"
         f"💰 *Order Price :* `{amount} Coins`\n"
         f"👀 *Tg Post Views  :* `{amount} Views`\n\n"
         f"😊 *Thanks for ordering*"),
        parse_mode="markdown",
        reply_markup=get_main_menu(),
        disable_web_page_preview=True
    )

    # Send notification to payment channel
    await bot.send_message(
        payment_channel,
        (f"*✅ New Views Order*\n\n"
         f"*ℹ️ Order ID =* `{oid}`\n"
         f"*⚡ Status* = `Processing...`\n"
         f"*👤 User =* {message.from_user.first_name}\n"
         f"*🆔️ User ID *= `{user_id}`\n"
         f"*👀 TG Post Views =* `{amount} Views`\n"
         f"*💰 Order Price :* `{amount} Coins`\n"
         f"*🔗 Link = {link}*\n\n"
         f"*🤖 Bot = {bot_username}*"),
        parse_mode="markdown",
        disable_web_page_preview=True
    )

    await state.clear()

# Bot startup
async def on_startup():
    await init_db()
    await load_plugins()
    global bot_username
    me = await bot.get_me()
    bot_username = f"@{me.username}"
    logger.info("Bot started")

# Main function
async def main():
    dp.startup.register(on_startup)
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Polling failed: {e}")
        await bot.send_message(admin_user_id, f"Bot polling failed: {e}")
        await asyncio.sleep(10)
        await main()  # Restart polling

if __name__ == "__main__":
    asyncio.run(main())