import telebot
import requests
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from functions import getData, cutBalance
from vars import SmmPanelApi2, payment_channel

# Define the minimum and maximum values for views
MIN_VIEWS = 100
MAX_VIEWS = 10000

# Function to register the bot commands and buttons
def register_plugin(bot):
    @bot.message_handler(func=lambda message: message.text == "👁‍🗨 fast views")
    def order_views(message):
        user_id = message.from_user.id
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        button1 = KeyboardButton("✘ Cancel")
        markup.add(button1)
        bot.send_message(user_id, "Please send the link to your Telegram post.", reply_markup=markup)
        bot.register_next_step_handler(message, get_post_link)

    def get_post_link(message):
        user_id = message.from_user.id
        if message.text == "✘ Cancel":
            send_main_menu(user_id)
            return
        post_link = message.text
        bot.send_message(user_id, f"500 coins = 100 fast views \n\nHow many views would you like to order? (Min: {MIN_VIEWS}, Max: {MAX_VIEWS})")
        bot.register_next_step_handler(message, lambda msg: get_order_quantity(msg, post_link))

    def get_order_quantity(message, post_link):
        user_id = message.from_user.id
        if message.text == "✘ Cancel":
            send_main_menu(user_id)
            return
        try:
            quantity = int(message.text)
            if quantity < MIN_VIEWS or quantity > MAX_VIEWS:
                bot.send_message(user_id, f"Invalid quantity. Please enter a number between {MIN_VIEWS} and {MAX_VIEWS}.")
                bot.register_next_step_handler(message, lambda msg: get_order_quantity(msg, post_link))
            else:
                place_view_order(user_id, post_link, quantity)
        except ValueError:
            bot.send_message(user_id, "Invalid quantity. Please enter a number.")
            bot.register_next_step_handler(message, lambda msg: get_order_quantity(msg, post_link))

    def place_view_order(user_id, post_link, quantity):
        auto_view_cost_per_100 = 500
        cost = (auto_view_cost_per_100 / 100) * quantity

        user_data = getData(user_id)
        balance = float(user_data['balance'])  # Ensure balance is treated as a float

        if cost > balance:
            bot.send_message(user_id, f"Insufficient balance. You need {cost} coins, but you only have {balance} coins.")
            send_main_menu(user_id)
            return

        # Send API request to SMM panel to place AutoView order
        url = 'https://cheapestsmmpanels.com/api/v2'
        headers = {'Content-Type': 'application/json'}
        data = {
            'key': SmmPanelApi2,
            'action': 'add',
            'service': '1978',
            'link': post_link,
            'quantity': quantity
        }
        response = requests.post(url, headers=headers, json=data)
        response_json = response.json()

        if response_json.get('error'):
            bot.send_message(user_id, f"Error: {response_json['error']}")
        else:
            cutBalance(user_id, cost)
            bot.send_message(user_id, f"fast views has been placed for  post: {post_link}\n\n"
                                      f"Order Details:\n\n"
                                      f"Views Ordered: {quantity}\n"
                                      f"Coins Deducted: {cost}\n"
                                      f"User ID: {user_id}\n\n"
                                      f"Remaining Balance: {balance - cost}")
                                      
            bot.send_message(payment_channel, f"fast views has been placed for  post: {post_link}\n\n"
                                      f"Order Details:\n\n"
                                      f"Views Ordered: {quantity}\n"
                                      f"Coins Deducted: {cost}\n"
                                      f"User ID: {user_id}\n\n"
                                      f"Remaining Balance: {balance - cost}")
        send_main_menu(user_id)

    def send_main_menu(user_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        button1 = KeyboardButton("🛒order")
        button6 = KeyboardButton("🎁daily bonus")
        button2 = KeyboardButton("👤 My Account")
        button3 = KeyboardButton("💳 buy coins")
        button4 = KeyboardButton("🗣 reffer")
        button5 = KeyboardButton("📜 Help")

        markup.add(button1, button6)
        markup.add(button2, button3)
        markup.add(button4, button5)
        bot.send_message(user_id, "Main Menu:", reply_markup=markup)
        