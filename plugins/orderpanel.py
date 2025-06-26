import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Text
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cached keyboard markups
order_menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
order_menu.add(
    KeyboardButton("👁‍🗨 Order View"),
    KeyboardButton("😊 auto views")
)

autoview_menu = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
autoview_menu.add(
    KeyboardButton("👁‍🗨 set autoview"),
    KeyboardButton("💔 cancel autoview")
)

def register_plugin(bot: Bot, dp: Dispatcher):
    """Register order handlers with the aiogram Dispatcher."""
    
    @dp.message(Text(equals="🛒order"))
    async def order_views(message: types.Message):
        user_id = message.from_user.id
        logger.info(f"User {user_id} accessed order menu")
        await message.reply(
            "Please select order type 👇.",
            reply_markup=order_menu
        )

    @dp.message(Text(equals="😊 auto views"))
    async def auto_views_menu(message: types.Message):
        user_id = message.from_user.id
        logger.info(f"User {user_id} accessed auto views menu")
        await message.reply(
            "Please select order type 👇.",
            reply_markup=autoview_menu
        )