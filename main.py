# Enhanced Telegram Userbot with translation, user search, and auto-reply features
# New features:
# - ".tn [language] [text]": Translates text to specified language
# - ".tn" as reply: Translates the replied message to Ukrainian
# - ".find_user [username]": Searches username across databases using maigret
# - Auto-reply: Responds automatically from 11 PM to 8 AM to private users only
# - Sends notifications to separate notification bot during sleep time
# - Improved AI responses: shorter and without markdown

import json
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
import google.generativeai as genai
import requests

# Load environment variables from .env file
load_dotenv()

# Get values from .env
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
gemini_api_key = os.getenv('GEMINI_API_KEY')
user_info_chat_id = int(os.getenv('USER_INFO_CHAT_ID'))
notification_bot_url = os.getenv('NOTIFICATION_BOT_URL', 'http://localhost:5000')  # URL notification bot API

# Prepared text for ".me"
PREPARED_TEXT = "This is the prepared text that will be sent instead of '.me'."

# Auto-reply messages
AUTO_REPLY_UK = "Вибачте, зараз я сплю. Відповім пізніше! 😴"
AUTO_REPLY_EN = "Sorry, I'm sleeping right now. I'll reply later! 😴"

# Track users who already received auto-reply to avoid spam
auto_reply_sent = {}

# Configure Gemini
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# Create the client with a session name
app = Client("my_userbot", api_id=api_id, api_hash=api_hash)


# Helper function to detect Ukrainian language
def is_ukrainian(text):
    """Detects if text contains Ukrainian characters"""
    ukrainian_chars = set('абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ')
    return any(char in ukrainian_chars for char in text)


# Helper function to check if it's sleep time (11 PM - 8 AM)
def is_sleep_time():
    """Check if current time is between 11 PM and 8 AM"""
    current_hour = datetime.now().hour
    return current_hour >= 23 or current_hour < 8


# Helper function to send notification to bot
def send_notification_to_bot(user_id, user_name, username, message_text, message_id):
    """Send notification to the notification bot via HTTP API"""
    try:
        data = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'message_text': message_text,
            'message_id': message_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        response = requests.post(
            f"{notification_bot_url}/notify",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✅ Notification sent successfully for user {user_id}")
        else:
            print(f"⚠️ Failed to send notification: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error sending notification: {e}")


# Handler for ".me" command
@app.on_message(filters.outgoing & filters.regex(r'^\.me$'))
async def handle_me_command(client, message):
    await message.delete()
    await client.send_message(message.chat.id, PREPARED_TEXT)


# Handler for ".save_chat" command
@app.on_message(filters.outgoing & filters.regex(r'^\.save_chat$'))
async def handle_save_chat(client, message):
    await message.delete()
    chat_id = message.chat.id
    messages = []

    # Fetch last 100 messages
    async for msg in client.get_chat_history(chat_id, limit=100):
        msg_data = {
            "id": msg.id,
            "date": str(msg.date),
            "from_user": msg.from_user.id if msg.from_user else None,
            "text": msg.text if msg.text else None,
        }
        messages.append(msg_data)

    # Save to JSON file
    file_name = f"chat_{chat_id}.json"
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

    await client.send_message(chat_id, f"Chat saved to {file_name}")


# Handler for ".ai [query]" command with improved formatting
@app.on_message(filters.outgoing & filters.regex(r'^\.ai (.+)$'))
async def handle_ai_query(client, message):
    await message.delete()
    query = message.matches[0].group(1)
    chat_id = message.chat.id

    # Enhanced prompt for shorter, plain text responses
    enhanced_query = f"{query}\n\nВідповідай коротко та по суті, без форматування markdown, без зірочок, без жирного тексту. Максимум 2-3 речення."

    try:
        response = await model.generate_content_async(enhanced_query)
        ai_text = response.text if response else "No response from AI."
        
        # Remove markdown formatting
        ai_text = ai_text.replace('**', '').replace('*', '').replace('`', '')
        
        await client.send_message(chat_id, ai_text)
    except Exception as e:
        await client.send_message(chat_id, f"Error: {str(e)}")


# Handler for ".tn" - Translation with two modes
@app.on_message(filters.outgoing & filters.regex(r'^\.tn'))
async def handle_translate(client, message):
    await message.delete()
    chat_id = message.chat.id

    try:
        # Mode 1: Reply to message - translate to Ukrainian
        if message.reply_to_message and message.reply_to_message.text:
            text_to_translate = message.reply_to_message.text
            target_lang = "українською"
            
            prompt = f"Переклади наступний текст {target_lang} мовою. Дай тільки переклад без пояснень:\n\n{text_to_translate}"
            response = await model.generate_content_async(prompt)
            translated_text = response.text if response else "Translation failed."
            
            # Remove markdown formatting
            translated_text = translated_text.replace('**', '').replace('*', '').replace('`', '')
            
            await client.send_message(chat_id, f"Переклад: {translated_text}")
        
        # Mode 2: .tn [language] [text] - translate text to specified language
        else:
            # Parse command
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await client.send_message(chat_id, "❌ Використання:\n.tn [мова] [текст]\nабо відповідь на повідомлення з .tn")
                return
            
            target_lang = parts[1]
            text_to_translate = parts[2]
            
            prompt = f"Переклади наступний текст {target_lang} мовою. Дай тільки переклад без пояснень:\n\n{text_to_translate}"
            response = await model.generate_content_async(prompt)
            translated_text = response.text if response else "Translation failed."
            
            # Remove markdown formatting
            translated_text = translated_text.replace('**', '').replace('*', '').replace('`', '')
            
            await client.send_message(chat_id, translated_text)
            
    except Exception as e:
        await client.send_message(chat_id, f"Translation error: {str(e)}")


# Handler for ".find_user [username]" - Search username across databases
@app.on_message(filters.outgoing & filters.regex(r'^\.find_user (.+)$'))
async def handle_find_user(client, message):
    await message.delete()
    username = message.matches[0].group(1).replace('@', '')
    chat_id = message.chat.id

    # Send initial message
    status_msg = await client.send_message(chat_id, f"🔍 Searching for @{username}...")

    try:
        # Run maigret command
        process = await asyncio.create_subprocess_exec(
            'maigret', username, '--timeout', '10', '--folderoutput', 'searches',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            output = stdout.decode('utf-8', errors='ignore')
            
            # Parse results
            lines = output.split('\n')
            found_sites = [line for line in lines if '[+]' in line or '✓' in line]
            
            if found_sites:
                result = f"✅ Found @{username} on:\n\n"
                result += '\n'.join(found_sites[:15])  # Limit to first 15 results
                
                if len(found_sites) > 15:
                    result += f"\n\n... and {len(found_sites) - 15} more sites."
                    result += f"\n\nCheck 'searches/{username}' folder for full report."
            else:
                result = f"❌ No results found for @{username}"
        else:
            result = f"⚠️ Search completed with warnings. Check 'searches/{username}' folder."
            
        await status_msg.edit(result)
        
    except FileNotFoundError:
        await status_msg.edit(
            "❌ Maigret not installed!\n\n"
            "Install it with:\n"
            "pip install maigret\n\n"
            "Or use: pip install git+https://github.com/soxoj/maigret.git"
        )
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")


# Handler for ".user" command (only in private chats)
@app.on_message(filters.outgoing & filters.private & filters.regex(r'^\.user$'))
async def handle_user_info(client, message):
    await message.delete()
    chat_id = message.chat.id

    # Get user info
    user = await client.get_users(chat_id)
    chat = await client.get_chat(chat_id)

    has_premium_status = getattr(user, 'has_premium', 'N/A')
    
    user_info = (
        f"User ID: {user.id}\n"
        f"Username: @{user.username if user.username else 'None'}\n"
        f"First Name: {user.first_name}\n"
        f"Last Name: {user.last_name if user.last_name else 'None'}\n"
        f"Status: {user.status}\n"
        f"Last Online: {user.last_online_date if user.last_online_date else 'Hidden'}\n"
        f"Bio: {chat.description if chat.description else 'None'}\n"
        f"Is Verified: {user.is_verified}\n"
        f"Is Scam: {user.is_scam}\n"
        f"Is Fake: {user.is_fake}\n"
        f"Has Premium: {has_premium_status}\n"
    )

    await client.send_message(user_info_chat_id, user_info)
    await client.send_message(message.chat.id, "User info collected and sent to the separate chat.")


# Auto-reply handler for incoming private messages during sleep time
@app.on_message(filters.private & filters.incoming & ~filters.bot & ~filters.me)
async def handle_auto_reply(client, message):
    """Auto-reply to messages during sleep time (11 PM - 8 AM) - only private users"""
    if not is_sleep_time():
        return
    
    user_id = message.from_user.id
    current_time = datetime.now()
    
    # Get user info
    user = message.from_user
    user_name = user.first_name
    username = user.username if user.username else "No username"
    message_text = message.text if message.text else "[Медіа або інший контент]"
    
    # Send notification to bot via HTTP API
    send_notification_to_bot(
        user_id=user_id,
        user_name=user_name,
        username=username,
        message_text=message_text,
        message_id=message.id
    )
    
    # Check if we already sent auto-reply to this user in the last 8 hours
    if user_id in auto_reply_sent:
        time_diff = (current_time - auto_reply_sent[user_id]).total_seconds() / 3600
        if time_diff < 8:  # Don't spam if already replied within 8 hours
            return
    
    # Determine language and send appropriate response
    if message.text and is_ukrainian(message.text):
        await message.reply(AUTO_REPLY_UK)
    else:
        await message.reply(AUTO_REPLY_EN)
    
    # Mark that we sent auto-reply to this user
    auto_reply_sent[user_id] = current_time


# Run the client
if __name__ == "__main__":
    print("🚀 Userbot started!")
    print("📋 Available commands:")
    print("   .me - Send prepared text")
    print("   .save_chat - Save last 100 messages")
    print("   .ai [query] - Ask AI")
    print("   .tn [мова] [текст] - Translate text")
    print("   .tn (as reply) - Translate replied message to Ukrainian")
    print("   .find_user [username] - Search username")
    print("   .user - Get user info")
    print("   Auto-reply: Active 11 PM - 8 AM (private users only)")
    print(f"   Notification bot URL: {notification_bot_url}")
    print("\n✅ Ready!")
    
    app.run()