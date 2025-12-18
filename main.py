# Enhanced Telegram Userbot
# Commands:
# - .me - Send prepared text
# - .save_chat - Save last 100 messages to JSON
# - .ai [query] - Ask Gemini AI (short responses, no markdown)
# - .tn [language] [text] - Translate text to specified language
# - .tn (as reply) - Translate replied message to Ukrainian
# - .find_user [username] - Search username across databases
# - .user - Get user info (sends to Saved Messages)
# Auto-reply: 11 PM - 8 AM (private users only, sends notifications to bot)

import json
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
import google.generativeai as genai
import requests

load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
gemini_api_key = os.getenv('GEMINI_API_KEY')
notification_bot_url = os.getenv('NOTIFICATION_BOT_URL', 'http://localhost:5000')

PREPARED_TEXT = "This is the prepared text that will be sent instead of '.me'."
AUTO_REPLY_UK = "Вибачте, зараз я сплю. Відповім пізніше! 😴"
AUTO_REPLY_EN = "Sorry, I'm sleeping right now. I'll reply later! 😴"

auto_reply_sent = {}

genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

app = Client("my_userbot", api_id=api_id, api_hash=api_hash)


def is_ukrainian(text):
    ukrainian_chars = set('абвгґдеєжзиіїйклмнопрстуфхцчшщьюяАБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ')
    return any(char in ukrainian_chars for char in text)


def is_sleep_time():
    current_hour = datetime.now().hour
    return current_hour >= 23 or current_hour < 8


def send_notification_to_bot(user_id, user_name, username, message_text, message_id):
    try:
        data = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'message_text': message_text,
            'message_id': message_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        response = requests.post(f"{notification_bot_url}/notify", json=data, timeout=5)
        if response.status_code == 200:
            print(f"✅ Notification sent for user {user_id}")
        else:
            print(f"⚠️ Notification failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Notification error: {e}")


@app.on_message(filters.outgoing & filters.regex(r'^\.me$'))
async def handle_me_command(client, message):
    await message.delete()
    await client.send_message(message.chat.id, PREPARED_TEXT)


@app.on_message(filters.outgoing & filters.regex(r'^\.save_chat$'))
async def handle_save_chat(client, message):
    await message.delete()
    chat_id = message.chat.id
    messages = []
    async for msg in client.get_chat_history(chat_id, limit=100):
        msg_data = {
            "id": msg.id,
            "date": str(msg.date),
            "from_user": msg.from_user.id if msg.from_user else None,
            "text": msg.text if msg.text else None,
        }
        messages.append(msg_data)
    file_name = f"chat_{chat_id}.json"
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)
    await client.send_message(chat_id, f"Chat saved to {file_name}")


@app.on_message(filters.outgoing & filters.regex(r'^\.ai (.+)$'))
async def handle_ai_query(client, message):
    await message.delete()
    query = message.matches[0].group(1)
    chat_id = message.chat.id
    enhanced_query = f"{query}\n\nВідповідай коротко та по суті, без форматування markdown, без зірочок, без жирного тексту. Максимум 2-3 речення."
    try:
        response = await model.generate_content_async(enhanced_query)
        ai_text = response.text if response else "No response from AI."
        ai_text = ai_text.replace('**', '').replace('*', '').replace('`', '')
        await client.send_message(chat_id, ai_text)
    except Exception as e:
        await client.send_message(chat_id, f"Error: {str(e)}")


@app.on_message(filters.outgoing & filters.regex(r'^\.tn'))
async def handle_translate(client, message):
    await message.delete()
    chat_id = message.chat.id
    try:
        if message.reply_to_message and message.reply_to_message.text:
            text_to_translate = message.reply_to_message.text
            target_lang = "українською"
            prompt = f"Переклади наступний текст {target_lang} мовою. Дай тільки переклад без пояснень:\n\n{text_to_translate}"
            response = await model.generate_content_async(prompt)
            translated_text = response.text if response else "Translation failed."
            translated_text = translated_text.replace('**', '').replace('*', '').replace('`', '')
            await client.send_message(chat_id, f"Переклад: {translated_text}")
        else:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                await client.send_message(chat_id, "❌ Використання:\n.tn [мова] [текст]\nабо відповідь на повідомлення з .tn")
                return
            target_lang = parts[1]
            text_to_translate = parts[2]
            prompt = f"Переклади наступний текст {target_lang} мовою. Дай тільки переклад без пояснень:\n\n{text_to_translate}"
            response = await model.generate_content_async(prompt)
            translated_text = response.text if response else "Translation failed."
            translated_text = translated_text.replace('**', '').replace('*', '').replace('`', '')
            await client.send_message(chat_id, translated_text)
    except Exception as e:
        await client.send_message(chat_id, f"Translation error: {str(e)}")


@app.on_message(filters.outgoing & filters.regex(r'^\.find_user (.+)$'))
async def handle_find_user(client, message):
    await message.delete()
    username = message.matches[0].group(1).replace('@', '')
    chat_id = message.chat.id
    status_msg = await client.send_message(chat_id, f"🔍 Searching for @{username}...")
    try:
        process = await asyncio.create_subprocess_exec(
            'maigret', username, '--timeout', '10', '--folderoutput', 'searches', '--json', 'simple',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode('utf-8', errors='ignore')
        lines = output.split('\n')
        found_sites = []
        for line in lines:
            if 'http' in line.lower() and ('✓' in line or '[+]' in line):
                clean_line = line
                clean_line = clean_line.replace('|', '')
                clean_line = clean_line.replace('▁', '')
                clean_line = clean_line.replace('▂', '')
                clean_line = clean_line.replace('▃', '')
                clean_line = clean_line.replace('▄', '')
                clean_line = clean_line.replace('▅', '')
                clean_line = clean_line.replace('▆', '')
                clean_line = clean_line.replace('▇', '')
                clean_line = clean_line.replace('█', '')
                clean_line = clean_line.replace('▏', '')
                clean_line = clean_line.replace('▎', '')
                clean_line = clean_line.replace('▍', '')
                clean_line = clean_line.replace('[', '')
                clean_line = clean_line.replace(']', '')
                clean_line = clean_line.replace('%', '')
                clean_line = clean_line.replace('Searching', '')
                clean_line = ' '.join(clean_line.split())
                if clean_line and 'http' in clean_line:
                    found_sites.append(clean_line)
        if found_sites:
            report_filename = f"search_results_{username}.txt"
            report_content = f"🔍 Search Results for @{username}\n"
            report_content += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report_content += f"📊 Total found: {len(found_sites)} sites\n"
            report_content += "=" * 50 + "\n\n"
            for i, site in enumerate(found_sites, 1):
                report_content += f"{i}. {site}\n"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(report_content)
            short_result = f"✅ Found @{username} on {len(found_sites)} sites!\n\n"
            short_result += "Top 5 results:\n"
            for i, site in enumerate(found_sites[:5], 1):
                short_result += f"{i}. {site}\n"
            if len(found_sites) > 5:
                short_result += f"\n... and {len(found_sites) - 5} more sites."
            short_result += "\n\n📄 Full report sent as file"
            await status_msg.edit(short_result)
            await client.send_document(
                chat_id=chat_id,
                document=report_filename,
                caption=f"📋 Complete search results for @{username}"
            )
            try:
                os.remove(report_filename)
            except:
                pass
        else:
            result = f"❌ No results found for @{username}"
            await status_msg.edit(result)
    except FileNotFoundError:
        await status_msg.edit("❌ Maigret not installed!\n\nInstall: pip install maigret")
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")


@app.on_message(filters.outgoing & filters.private & filters.regex(r'^\.user$'))
async def handle_user_info(client, message):
    await message.delete()
    chat_id = message.chat.id
    try:
        user = await client.get_users(chat_id)
        chat = await client.get_chat(chat_id)
        has_premium_status = getattr(user, 'has_premium', 'N/A')
        user_info = (
            f"👤 User Info:\n\n"
            f"ID: {user.id}\n"
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
        await client.send_message("me", user_info)
        await client.send_message(message.chat.id, "✅ User info sent to Saved Messages")
    except Exception as e:
        await client.send_message(message.chat.id, f"❌ Error: {str(e)}")


@app.on_message(filters.private & filters.incoming & ~filters.bot & ~filters.me)
async def handle_auto_reply(client, message):
    if not is_sleep_time():
        return
    user_id = message.from_user.id
    current_time = datetime.now()
    user = message.from_user
    user_name = user.first_name
    username = user.username if user.username else "No username"
    message_text = message.text if message.text else "[Медіа або інший контент]"
    send_notification_to_bot(user_id, user_name, username, message_text, message.id)
    if user_id in auto_reply_sent:
        time_diff = (current_time - auto_reply_sent[user_id]).total_seconds() / 3600
        if time_diff < 8:
            return
    if message.text and is_ukrainian(message.text):
        await message.reply(AUTO_REPLY_UK)
    else:
        await message.reply(AUTO_REPLY_EN)
    auto_reply_sent[user_id] = current_time


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