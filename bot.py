import asyncio
import base64
import logging
import os
from time import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified, UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
from pyrogram.enums import ChatMemberStatus

API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")
TOKEN = os.getenv("TOKEN", "")
DUMP_CHANNEL = os.getenv("DUMP_CHANNEL", "")
SUDO_USERS = [5244072595]
INVITE_LINK = os.getenv("INVITE_LINK", "")
INVITE_LINK2 = os.getenv("INVITE_LINK2", "")
INVITE_LINK3 = os.getenv("INVITE_LINK3", "")
FORCE_SUB_CHANNELS = [""]
channels = [int(x) for x in FORCE_SUB_CHANNELS]
MONGO_URI = os.getenv("MONGO_URI","")
DB_NAME = "bot"
COLLECTION_NAME = "users"

pbot = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TOKEN
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
users_collection = db[COLLECTION_NAME]

user_last_command_time = {}
COMMAND_INTERVAL = 3 


async def is_subscribed(message):
    user_id = message.from_user.id
    if user_id in SUDO_USERS:
        return True

    for channel in channels:
        try:
            member = await pbot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
                return False
        except UserNotParticipant:
            return False
        except Exception as e:
            logger.error(f"Error checking subscription status in channel {channel}: {e}")
            return False
    
    return True


async def save_user(user_id, first_name):
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id, "first_name": first_name})


async def decode(encoded_string):
    try:
        decoded_bytes = base64.b64decode(encoded_string)
        decoded_string = decoded_bytes.decode('utf-8')
        return int(decoded_string)
    except ValueError as e:
        logger.error(f"Decoding error: {e}")
        raise ValueError("Invalid encoded string")


async def validate_message_id(message_id):
    if message_id <= 0:
        raise ValueError("Invalid message ID")


async def copy_and_send_message(message, message_id, retries=3):
    for attempt in range(retries):
        try:
            await pbot.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=DUMP_CHANNEL,
                message_id=message_id,
                disable_notification=True,
                protect_content=True
            )
            return
        except FloodWait as e:
            logger.warning(f"FloodWait: Waiting for {e.x} seconds")
            await asyncio.sleep(e.x)
        except MessageNotModified as e:
            logger.error(f"Message not modified: {e}")
            break
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            if attempt == retries - 1:
                raise


async def generate_custom_link(message_id):
    user = await pbot.get_me()
    encoded_string = base64.b64encode(str(message_id).encode('utf-8')).decode('utf-8')
    return f"https://t.me/{user.username}?start={encoded_string}"


async def forward_and_generate_link(message):
    try:
        forwarded_message = await pbot.send_document(DUMP_CHANNEL, message.document.file_id, caption=message.caption)
        custom_link = await generate_custom_link(forwarded_message.id)
        await message.reply_text(f"Document forwarded successfully! Access link: {custom_link}",
                                 disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error forwarding document: {e}")
        await message.reply_text("Failed to forward the document. Please try again later.")


async def handle_start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    BOT_USERNAME = (await pbot.get_me()).username
    current_time = time()
    if user_id in user_last_command_time and current_time - user_last_command_time[user_id] < COMMAND_INTERVAL:
        await message.reply_text("You are sending commands too quickly. Please wait a moment.")
        return
    await save_user(user_id, first_name)

    text = message.text.strip()
    logger.info(f"Received command: {text}")

    if len(text) > 7:
        txt = text[7:].strip()
        encode_string = txt.replace(" ", "")
        print(await is_subscribed(message))
        if not await is_subscribed(message):
        
            invite_link = f"{INVITE_LINK}"
            invite_link2 = f"{INVITE_LINK2}"
            invite_link3 = f"{INVITE_LINK3}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Channel", url=invite_link)
                 ,InlineKeyboardButton("Join Channel", url=invite_link2)
                 ,InlineKeyboardButton("Join Channel", url=invite_link3)],
                [InlineKeyboardButton("Retry", url=f"https://t.me/{BOT_USERNAME}?start={encode_string}")]
            ])
            await message.reply_text("You must join the channel to use this bot.", reply_markup=keyboard)
            return
        logger.info(f"Encoded string: {encode_string}")

        try:
            decode_string = await decode(str(encode_string))
            logger.info(f"Decoded string (message ID): {decode_string}")
            await validate_message_id(decode_string)
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            await message.reply_text("Invalid Link")
            return

        try:
            await asyncio.sleep(1)
            await copy_and_send_message(message, decode_string)
        except Exception as e:
            logger.error(f"Copy and send error: {e}")
            await message.reply_text("Failed to send the message. Please check the link.")
            return
    else:
        await message.reply_text("I am alive and ready to assist!")


@pbot.on_message(filters.command("start") & filters.private)
async def start(_, message):
    await handle_start_command(message)


@pbot.on_message(filters.document & filters.private)
async def handle_document(_, message):
    if message.from_user.id not in SUDO_USERS:
        return

    await asyncio.sleep(0.5)
    await forward_and_generate_link(message)

@pbot.on_message(filters.command("stats") & filters.private)
async def stats_command(_, message):
    if message.from_user.id not in SUDO_USERS:
        return await message.reply_text("You are not allowed to use this bot.")
    total_users = users_collection.count_documents({})
    await message.reply_text(f"Total users: {total_users}")


@pbot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command(_, message):
    if message.from_user.id not in SUDO_USERS:
        return await message.reply_text("You are not allowed to use this bot.")
    
    failed = 0
    sent = 0
    
    if message.reply_to_message:
        users = users_collection.find()
        total_users = await users_collection.count_documents({})
        await message.reply_text(f"Started broadcast to {total_users} users...")
        
        for user in users:
            try:
                await pbot.forward_messages(
                    chat_id=user["user_id"],
                    from_chat_id=message.chat.id,
                    message_ids=message.reply_to_message.id
                )
                sent += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                failed += 1
                logger.error(f"Failed to forward message to {user['user_id']}: {e}")
                continue

        await message.reply_text(f"Broadcast completed:\n✅ Successful: {sent}\n❌ Failed: {failed}\n💡 Total: {total_users}")
    
    else:
        if len(message.text.split()) < 2:
            return await message.reply_text("Please provide a message to broadcast")
        
        broadcast_text = message.text.split(maxsplit=1)[1]
        users = users_collection.find()
        total_users = await users_collection.count_documents({})
        await message.reply_text(f"Started broadcast to {total_users} users...")
        
        for user in users:
            try:
                await pbot.send_message(user["user_id"], broadcast_text)
                sent += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send message to {user['user_id']}: {e}")
                continue

        await message.reply_text(f"Broadcast completed:\n✅ Successful: {sent}\n❌ Failed: {failed}\n💡 Total: {total_users}")


pbot.run()
