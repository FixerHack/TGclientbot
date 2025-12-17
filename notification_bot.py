# Notification Bot - receives notifications from userbot and sends them to you
# This bot runs as a separate process and receives HTTP requests from the userbot
# When userbot detects incoming message during sleep time, it sends data to this bot
# Bot then sends you a notification with inline "Read" button

import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading

# Load environment variables
load_dotenv()

# Get values from .env
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')  # Your bot token from @BotFather
your_user_id = int(os.getenv('YOUR_USER_ID'))  # Your Telegram user ID

# Create Flask app for receiving HTTP requests from userbot
app = Flask(__name__)

# Create Pyrogram bot client
bot = Client("notification_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Store message mapping for callback handling
message_mapping = {}


@app.route('/notify', methods=['POST'])
def receive_notification():
    """Receive notification from userbot via HTTP POST"""
    try:
        data = request.json
        
        user_id = data.get('user_id')
        user_name = data.get('user_name')
        username = data.get('username')
        message_text = data.get('message_text')
        message_id = data.get('message_id')
        timestamp = data.get('timestamp')
        
        # Format notification message
        notification_text = (
            f"💤 Нове повідомлення під час сну:\n\n"
            f"👤 Від: {user_name}\n"
            f"🔗 Username: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"🕐 Час: {timestamp}\n\n"
            f"📝 Повідомлення:\n{message_text}"
        )
        
        # Create inline keyboard with "Read" button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Прочитано", callback_data=f"read_{user_id}_{message_id}")]
        ])
        
        # Send notification to your user ID
        sent_message = bot.send_message(
            chat_id=your_user_id,
            text=notification_text,
            reply_markup=keyboard
        )
        
        # Store message mapping for callback
        message_mapping[f"read_{user_id}_{message_id}"] = sent_message.id
        
        return jsonify({"status": "success", "message": "Notification sent"}), 200
        
    except Exception as e:
        print(f"Error processing notification: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@bot.on_callback_query(filters.regex(r'^read_'))
async def handle_read_button(client, callback_query):
    """Handle when user presses 'Read' button"""
    try:
        callback_data = callback_query.data
        
        # Update button to show it's been read
        await callback_query.message.edit_reply_markup(
            InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Прочитано ✓", callback_data="already_read")]
            ])
        )
        
        # Answer the callback
        await callback_query.answer("✅ Позначено як прочитане", show_alert=False)
        
        # Optionally add a checkmark to the message text
        current_text = callback_query.message.text
        if not current_text.startswith("✅"):
            await callback_query.message.edit_text(
                f"✅ {current_text}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Прочитано ✓", callback_data="already_read")]
                ])
            )
        
    except Exception as e:
        await callback_query.answer(f"Error: {str(e)}", show_alert=True)


@bot.on_callback_query(filters.regex(r'^already_read$'))
async def handle_already_read(client, callback_query):
    """Handle when user presses already read button"""
    await callback_query.answer("Вже прочитано", show_alert=False)


def run_flask():
    """Run Flask server in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


def run_bot():
    """Run Telegram bot"""
    print("🤖 Notification bot started!")
    print(f"📬 Sending notifications to user ID: {your_user_id}")
    print("🌐 HTTP API listening on http://0.0.0.0:5000")
    print("✅ Ready to receive notifications!\n")
    bot.run()


if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run the bot (this will block)
    run_bot()