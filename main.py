# This is the userbot script using Pyrogram that runs on your Telegram user account.
# Features:
# - ".me": Replaces with prepared text.
# - ".save_chat": Downloads the last 100 messages from the current chat and saves them to a JSON file.
# - ".ai [query]": Sends the query to Google's Gemini AI asynchronously and replies with the response.
# - ".user": In a private chat, analyzes and collects detailed information about the interlocutor (user data like ID, username, names, status, bio, last online, etc.) and sends it to a specified separate chat (e.g., your saved messages or a private channel) for privacy.

# Requirements:
# - Python 3.11
# - Pyrogram library (install via: pip install pyrogram)
# - Google Generative AI library for Gemini (install via: pip install google-generativeai)
# - python-dotenv for loading .env (install via: pip install python-dotenv)
# - You need to obtain api_id and api_hash from https://my.telegram.org/apps
# - On first run, it will prompt for your phone number and verification code to authorize the session.
# - For Gemini: Get API key from https://aistudio.google.com/app/apikey and set in .env.
# - For .user: Set USER_INFO_CHAT_ID in .env to the chat ID where user info will be sent (for privacy).
#   This can be your own user ID for Saved Messages, or a private channel/group ID where the userbot is a member.

import json
import os
from dotenv import load_dotenv
from pyrogram import Client, filters
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Get values from .env
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
gemini_api_key = os.getenv('GEMINI_API_KEY')
user_info_chat_id = int(
    os.getenv('USER_INFO_CHAT_ID'))  # Chat ID for sending user info (e.g., your Saved Messages chat ID)

# Prepared text for ".me"
PREPARED_TEXT = "This is the prepared text that will be sent instead of '.me'."

# Configure Gemini
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')
# АБО спробуйте попередню версію:
# model = genai.GenerativeModel('gemini-2.5-pro')  # Or use 'gemini-1.5-pro' if you have access

# Create the client with a session name
app = Client("my_userbot", api_id=api_id, api_hash=api_hash)


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

    # Fetch last 100 messages (you can adjust the limit)
    async for msg in client.get_chat_history(chat_id, limit=100):
        msg_data = {
            "id": msg.id,
            "date": str(msg.date),
            "from_user": msg.from_user.id if msg.from_user else None,
            "text": msg.text if msg.text else None,
            # Add more fields if needed, e.g., media
        }
        messages.append(msg_data)

    # Save to JSON file named after chat_id
    file_name = f"chat_{chat_id}.json"
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

    await client.send_message(chat_id, f"Chat saved to {file_name}")


# Handler for ".ai [query]" command
@app.on_message(filters.outgoing & filters.regex(r'^\.ai (.+)$'))
async def handle_ai_query(client, message):
    await message.delete()
    query = message.matches[0].group(1)  # Extract the query after ".ai "
    chat_id = message.chat.id

    # Generate response from Gemini asynchronously
    response = await model.generate_content_async(query)
    ai_text = response.text if response else "No response from AI."

    await client.send_message(chat_id, ai_text)


# Handler for ".user" command (only in private chats)
@app.on_message(filters.outgoing & filters.private & filters.regex(r'^\.user$'))
async def handle_user_info(client, message):
    await message.delete()
    chat_id = message.chat.id  # In private chat, this is the user's ID

    # Get user info
    user = await client.get_users(chat_id)
    chat = await client.get_chat(chat_id) # Get chat details for bio, etc.

    has_premium_status = getattr(user, 'has_premium', 'N/A or Old Pyrogram Version')
    # Collect detailed user data
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
        # Add more if needed, e.g., common chats require get_common_chats but may need permissions
    )

    # Send to the specified separate chat for privacy
    await client.send_message(user_info_chat_id, user_info)
    # Optionally, confirm in the current chat
    await client.send_message(message.chat.id, "User info collected and sent to the separate chat.")


# Run the client
if __name__ == "__main__":
    app.run()