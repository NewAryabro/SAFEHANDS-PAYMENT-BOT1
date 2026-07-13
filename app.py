import asyncio
import sys
import types
import time
import re
import os
import logging
import urllib.parse
import uuid
import html
from io import BytesIO
from datetime import datetime, timezone, timedelta

# ==========================================
# 📊 PRODUCTION LOGGING ENGINE SET UP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ==========================================
# 🛑 CORE PYTHON 3.14 EVENT LOOP & PYROGRAM SYNC HOTFIX
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

if "pyrogram.sync" not in sys.modules:
    mock_sync_module = types.ModuleType("pyrogram.sync")
    mock_sync_module.async_to_sync = lambda source, name=None: source
    mock_sync_module.idle = lambda: None
    mock_sync_module.compose = lambda: None
    sys.modules["pyrogram.sync"] = mock_sync_module

from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import UserIsBlocked, InputUserDeactivated, FloodWait

# ASYNCHRONOUS MONGODB ENGINE INJECTIONS
from motor.motor_asyncio import AsyncIOMotorClient
import qrcode

# ==========================================
# ⚙️ SECURE ENVIRONMENT CONFIG VARS
# ==========================================
API_ID = int(os.environ.get("API_ID", 34042874))
API_HASH = os.environ.get("API_HASH", "494b9f740bc2f8f0e1a17c1c9f27ed9c")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8304614884:AAHQnlLGTui3lZZ6An8cxZRiBi2ZZYn3RLc")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 2066626554))
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1001639319995))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://MarvelAndDc:MarvelAndDc@cluster0.z0uow.mongodb.net/?retryWrites=true&w=majority")

# 💳 Fiat UPI Configurations
UPI_ID = "Telugumovies8985-1@oksbi"
MERCHANT_NAME = "Premium Access"

# 🪙 Secure Crypto Wallet Destinations
USDT_TRC20 = "TM318UtCJYArRW3h2nyoeGug4PvVWSipbg"      
USDT_BEP20 = "0x7961231FA0de4C70B65BFfe877696858DC2cC7EB"  
USDT_POLYGON = "0x7961231FA0de4C70B65BFfe877696858DC2cC7EB" 

# ==========================================
# 🎯 MULTI-TARGET CHANNELS VAULT CONFIG
# ==========================================
CH1_GAME = -1001522411163
CH2_HOT = -1001515841046
#CH3_EDITABLE = -1001888888888
#CH4_EDITABLE = -1001777777777
#CH5_EDITABLE = -1001666666666
#CH6_EDITABLE = -1001555555555
#CH7_EDITABLE = -1001444444444

CHANNELS_REGISTRY = {
    "game_comp": {"name": "GAME COMPETITION 🎮", "price_inr": 30, "price_usd": 0.31, "target_id": CH1_GAME},
    "hot_stuff": {"name": "Hot & Heroine Stuff 🥵", "price_inr": 50, "price_usd": 0.52, "target_id": CH2_HOT},
   # "slot_3": {"name": "Premium Slots 3 ✨", "price_inr": 149, "price_usd": 1.80, "target_id": CH3_EDITABLE},
   # "slot_4": {"name": "Premium Slots 4 🚀", "price_inr": 299, "price_usd": 3.60, "target_id": CH4_EDITABLE},
   # "slot_5": {"name": "Premium Slots 5 🎬", "price_inr": 399, "price_usd": 4.80, "target_id": CH5_EDITABLE},
   # "slot_6": {"name": "Premium Slots 6 💎", "price_inr": 499, "price_usd": 6.00, "target_id": CH6_EDITABLE},
   # "slot_7": {"name": "Premium Slots 7 🔥", "price_inr": 599, "price_usd": 7.20, "target_id": CH7_EDITABLE}
}

bot = Client(
    "simple_pay_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["premium_payment_bot"]

users_col = db["users"]
payments_col = db["payments"]
states_col = db["states"]
class DBManager:
    @staticmethod
    async def check_user_exists(user_id):
        user = await users_col.find_one({"user_id": user_id})
        return True if user else False

    @staticmethod
    async def is_user_banned(user_id):
        user = await users_col.find_one({"user_id": user_id})
        return True if user and user.get("is_banned") == 1 else False

    @staticmethod
    async def add_user(user_id, username, first_name):
        safe_name = html.escape(first_name or "User")
        safe_user = html.escape(username or "No Username")
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"username": safe_user, "first_name": safe_name, "join_date": int(time.time()), "is_banned": 0}},
            upsert=True
        )

    @staticmethod
    async def set_ban_status(user_id, ban_status):
        await users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": ban_status}})

    @staticmethod
    async def fetch_all_users():
        cursor = users_col.find({"is_banned": 0})
        return [doc["user_id"] async for doc in cursor]

    @staticmethod
    async def remove_user(user_id):
        await users_col.delete_one({"user_id": user_id})

    @staticmethod
    async def get_financial_analytics():
        total_users = await users_col.count_documents({})
        pending_queue = await payments_col.count_documents({"status": "PENDING"})
        approved_count = await payments_col.count_documents({"status": "APPROVED"})
        
        lifetime_pipeline = [{"$match": {"status": "APPROVED"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        lifetime_res = await payments_col.aggregate(lifetime_pipeline).to_list(1)
        lifetime_revenue = lifetime_res[0]["total"] if lifetime_res else 0
        
        now = datetime.now(timezone.utc)
        month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        month_pipeline = [{"$match": {"status": "APPROVED", "timestamp": {"$gte": month_start}}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
        month_res = await payments_col.aggregate(month_pipeline).to_list(1)
        month_revenue = month_res[0]["total"] if month_res else 0
        
        return {
            "total_users": total_users, "lifetime_revenue": int(lifetime_revenue),
            "month_revenue": int(month_revenue), "pending_queue": pending_queue, "approved_count": approved_count
        }

    @staticmethod
    async def check_utr(utr):
        res = await payments_col.find_one({"utr": utr})
        return res["status"] if res else None

    @staticmethod
    async def add_payment_intent(utr, user_id, amount, channel_key):
        try:
            row_id = uuid.uuid4().hex[:16]
            await payments_col.insert_one({
                "id": row_id, "utr": utr, "user_id": user_id, "amount": amount,
                "channel_key": channel_key, "status": "PENDING", "timestamp": int(time.time()), "log_msg_id": 0
            })
            return row_id
        except Exception as e:
            logging.exception(f"MongoDB Intent Insertion Exception: {e}")
            return None

    @staticmethod
    async def update_log_message_id(row_id, log_msg_id):
        await payments_col.update_one({"id": row_id}, {"$set": {"log_msg_id": log_msg_id}})

    @staticmethod
    async def fetch_record_by_id(row_id):
        return await payments_col.find_one({"id": row_id})

    @staticmethod
    async def fetch_user_by_log_msg(log_msg_id):
        res = await payments_col.find_one({"log_msg_id": log_msg_id})
        return res["user_id"] if res else None

    @staticmethod
    async def update_status_by_id(row_id, status):
        await payments_col.update_one({"id": row_id}, {"$set": {"status": status}})

    @staticmethod
    async def remove_record_by_id(row_id):
        await payments_col.delete_one({"id": row_id})

    @staticmethod
    async def get_user_state(user_id):
        return await states_col.find_one({"user_id": user_id})

    @staticmethod
    async def set_user_state(user_id, state_dict):
        await states_col.update_one({"user_id": user_id}, {"$set": state_dict}, upsert=True)

    @staticmethod
    async def clear_user_state(user_id):
        await states_col.delete_one({"user_id": user_id})


def get_local_upi_qr(amount: int) -> BytesIO:
    payload = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(MERCHANT_NAME)}&am={amount}&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.name = "payment_qr.png"
    bio.seek(0)
    return bio
async def check_banned_middleware(message: Message):
    if not message.from_user: return True
    if await DBManager.is_user_banned(message.from_user.id):
        await message.reply_text("<b>🚫 Access Denied:</b> Your profile has been blacklisted.")
        return True
    return False

@bot.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    if not message.from_user: return
    if await check_banned_middleware(message): return
    user_id = message.from_user.id
    await DBManager.clear_user_state(user_id)
    
    safe_first_name = html.escape(message.from_user.first_name or "User")
    username_ref = f"@{html.escape(message.from_user.username)}" if message.from_user.username else "No Username"
    
    if not await DBManager.check_user_exists(user_id):
        await DBManager.add_user(user_id, message.from_user.username, message.from_user.first_name)
        new_user_log = (
            f"🆕 <b>New User Started Bot!</b>\n\n👤 <b>Name:</b> {safe_first_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n🌐 <b>Handle:</b> {username_ref}"
        )
        try: await bot.send_message(chat_id=LOG_CHANNEL_ID, text=new_user_log)
        except Exception as e: logging.exception(f"Failed to log user startup: {e}")
            
    buttons_list = []
    for key, info in CHANNELS_REGISTRY.items():
        btn_text = f"🔗 {info['name']} - ₹{info['price_inr']} (${info['price_usd']:.2f})"
        buttons_list.append([InlineKeyboardButton(btn_text, callback_data=f"select_{key}")])
    buttons_list.append([InlineKeyboardButton("📞 Support Desk", url=f"tg://user?id={ADMIN_ID}")])
    
    keyboard = InlineKeyboardMarkup(buttons_list)
    # ✅ FIX: Highly clean, sharp and prominent text layout alignment (No loose blockquotes)
    await message.reply_text(
        f"👋 <b>Hello {safe_first_name},</b>\n\n"
        f"Welcome to Premium Channels Gateway Portal.\n\n"
        f"⚡ <b>Select the specific channel below to purchase your private invite access link:</b>",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex(r"^select_"))
async def plan_selection_handler(client: Client, callback: CallbackQuery):
    if await DBManager.is_user_banned(callback.from_user.id): 
        await callback.answer("🚫 Account Banned.", show_alert=True)
        return
        
    channel_key = callback.data.split("_", 1)[1]
    selected_channel = CHANNELS_REGISTRY.get(channel_key)
    if not selected_channel:
        await callback.answer("❌ Config trace empty.", show_alert=True)
        return
        
    safe_channel_name = html.escape(selected_channel["name"])
    
    await DBManager.set_user_state(callback.from_user.id, {
        "status": "INITIATED", "channel_key": channel_key, "price": selected_channel["price_inr"], "method": "FIAT", "utr": None, "photo": None
    })
    
    try:
        qr_stream = get_local_upi_qr(selected_channel["price_inr"])
        
        # ✅ FIX: Replaced broad choices. Dynamic isolated verification path buttons only (Hides editable slots matrix)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Pay in USDT (Crypto)", callback_data=f"cryptolink_{channel_key}")],
            [InlineKeyboardButton("✅ Proceed to Verify Payment", callback_data="confirm_paid")]
        ])
        
        await callback.message.reply_photo(photo=qr_stream)
        
        invoice_text = (
            f"<b>🤖 Payment Session Invoice Generated</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>Target Channel:</b> <code>{safe_channel_name}</code>\n"
            f"💳 <b>Fixed Amount:</b> <code>₹{selected_channel['price_inr']} (${selected_channel['price_usd']:.2f})</code>\n"
            f"📌 <b>UPI ID Ref:</b> <code>{UPI_ID}</code>\n\n"
            f"👉 Complete your transfer, capture a screenshot confirmation dashboard, then click verify button down below."
        )
        await callback.message.reply_text(invoice_text, reply_markup=keyboard)
        
        try: await callback.message.delete()
        except Exception: pass
            
    except Exception as e:
        logging.exception(f"Invoice crash log: {e}")
        await callback.message.reply_text("❌ <b>Invoice Engine Failure.</b> Please try again.")
    finally:
        await callback.answer()

@bot.on_callback_query(filters.regex(r"^cryptolink_"))
async def crypto_link_alert_handler(client: Client, callback: CallbackQuery):
    if await DBManager.is_user_banned(callback.from_user.id):
        await callback.answer("🚫 Account Banned.", show_alert=True)
        return
        
    channel_key = callback.data.split("_", 1)[1]
    selected_channel = CHANNELS_REGISTRY.get(channel_key)
    if not selected_channel:
        await callback.answer("❌ Channel trace lost.", show_alert=True)
        return
        
    safe_channel_name = html.escape(selected_channel["name"])
    
    state = await DBManager.get_user_state(callback.from_user.id)
    if not state:
        await callback.answer("❌ Session Invalid.", show_alert=True)
        return
        
    state["method"] = "CRYPTO"
    await DBManager.set_user_state(callback.from_user.id, state)
    
    # ✅ FIX: Pristine dynamic absolute text visualization maps
    crypto_text = (
        f"<b>🪙 USDT Secure Invoicing Layer Assets</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Target Channel:</b> <code>{safe_channel_name}</code>\n"
        f"💵 <b>Amount Due:</b> <code>${selected_channel['price_usd']:.2f} USDT</code>\n\n"
        f"👇 <b>Tap any wallet address to copy instantly:</b>\n\n"
        f"🌐 <b>TRC20 Network Address:</b>\n<code>{USDT_TRC20}</code>\n\n"
        f"⚡ <b>BEP20 Network Address:</b>\n<code>{USDT_BEP20}</code>\n\n"
        f"💜 <b>Polygon POS Network Address:</b>\n<code>{USDT_POLYGON}</code>\n\n"
        f"👉 Complete transfer on selected network, capture transaction hash screen view, then click verify below."
    )
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Proceed to Verify Payment", callback_data="confirm_paid")]])
    await callback.message.reply_text(crypto_text, reply_markup=keyboard)
    
    try: await callback.message.delete()
    except Exception: pass
    await callback.answer()
@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    if await DBManager.is_user_banned(callback.from_user.id):
        await callback.answer("🚫 Account Banned.", show_alert=True)
        return
        
    state = await DBManager.get_user_state(callback.from_user.id)
    if not state:
        await callback.answer("❌ Verification Session Expired.", show_alert=True)
        return
        
    state["status"] = "AWAITING_DATA"
    await DBManager.set_user_state(callback.from_user.id, state)
    
    if state.get("method") == "CRYPTO":
        prompt_text = (
            "<b>📝 Verification Requirements (USDT Crypto)</b>\n\n"
            "1️⃣ Send your <b>64-character Transaction Hash / TxID string</b> in text format.\n"
            "2️⃣ Send the transaction confirmation <b>Screenshot image</b> right after."
        )
    else:
        prompt_text = (
            "<b>📝 Verification Requirements (UPI Fiat)</b>\n\n"
            "1️⃣ Send your <b>12-digit numeric UTR / Reference Number</b> in text format.\n"
            "2️⃣ Send the bank receipt <b>Screenshot image</b> right after."
        )
        
    await callback.message.reply_text(prompt_text)
    await callback.answer()

@bot.on_message(filters.command("status") & filters.private)
async def status_dashboard_handler(client: Client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID: return
    stats = await DBManager.get_financial_analytics()
    
    month_usd = stats['month_revenue'] / 83.33
    lifetime_usd = stats['lifetime_revenue'] / 83.33
    
    report = (
        f"<b>📊 Premium Payments & Financial Ledger Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>Total Registered Users:</b> <code>{stats['total_users']}</code>\n"
        f"📈 <b>Total Paid Transactions:</b> <code>{stats['approved_count']}</code>\n"
        f"⏳ <b>Pending Verification Queue:</b> <code>{stats['pending_queue']}</code>\n\n"
        f"💵 <b>This Month Gross Revenue:</b> <code>Rupees: ₹{stats['month_revenue']} (${month_usd:.2f})</code>\n"
        f"💰 <b>Lifetime Net Revenue Assets:</b> <code>Rupees: ₹{stats['lifetime_revenue']} (${lifetime_usd:.2f})</code>\n\n"
        f"🕒 <b>Server Sync Zone:</b> <code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</code>"
    )
    await message.reply_text(report)

@bot.on_message(filters.command("ban") & filters.private)
async def ban_user_handler(client: Client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID: return
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    
    await DBManager.set_ban_status(target_id, 1)
    await message.reply_text(f"✅ User <code>{target_id}</code> Blacklisted.")
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"🔨 <b>Admin Ban:</b> User <code>{target_id}</code> banned.")
        await bot.send_message(chat_id=target_id, text="🚫 Your account has been blacklisted by the Administrator.")
    except Exception as e: logging.exception(f"Ban notification error: {e}")

@bot.on_message(filters.command("unban") & filters.private)
async def unban_user_handler(client: Client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID: return
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    
    await DBManager.set_ban_status(target_id, 0)
    await message.reply_text(f"✅ User <code>{target_id}</code> Whitelisted.")
    try: await bot.send_message(chat_id=target_id, text="🎉 Your account has been unbanned!")
    except Exception as e: logging.exception(f"Unban notification error: {e}")

async def send_single_broadcast(broadcast_msg: Message, user_id: int):
    try:
        await broadcast_msg.copy(chat_id=user_id)
        return "SUCCESS"
    except FloodWait as fw:
        await asyncio.sleep(fw.value + 1)
        try:
            await broadcast_msg.copy(chat_id=user_id)
            return "SUCCESS"
        except Exception:
            return "FAILED"
    except (UserIsBlocked, InputUserDeactivated):
        await DBManager.remove_user(user_id)
        return "BLOCKED"
    except Exception as e:
        logging.exception(f"Broadcast generic track: {e}")
        return "FAILED"

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return
    
    broadcast_msg = message.reply_to_message
    all_users = await DBManager.fetch_all_users()
    status_update_msg = await message.reply_text(f"⏳ <b>Starting Parallel Broadcast Blast...</b> Target: <code>{len(all_users)}</code> users.")
    
    success_count, blocked_count, failed_count = 0, 0, 0
    batch_size = 30
    
    for i in range(0, len(all_users), batch_size):
        batch = all_users[i:i + batch_size]
        tasks = [send_single_broadcast(broadcast_msg, user_id) for user_id in batch]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res == "SUCCESS": success_count += 1
            elif res == "BLOCKED": blocked_count += 1
            elif res == "FAILED": failed_count += 1
            
        try: await status_update_msg.edit_text(f"⏳ Progress: <code>{min(i + batch_size, len(all_users))}/{len(all_users)}</code> processed...")
        except Exception: pass
        await asyncio.sleep(0.2)
        
    await status_update_msg.edit_text("✅ Parallel broadcast complete.")
    await bot.send_message(
        chat_id=LOG_CHANNEL_ID, 
        text=f"📢 <b>Broadcast Matrix Report:</b>\n\n✅ Success: <code>{success_count}</code>\n🚫 Blocked/Removed: <code>{blocked_count}</code>\n⚠️ Failed: <code>{failed_count}</code>"
    )

@bot.on_message(filters.chat(LOG_CHANNEL_ID) & filters.reply)
async def livegram_reply_routing_handler(client: Client, message: Message):
    if message.text and message.text.startswith("/"): return
    target_user_id = await DBManager.fetch_user_by_log_msg(message.reply_to_message_id)
    if not target_user_id: return

    try:
        await message.copy(chat_id=target_user_id)
        await message.reply_text(f"🚀 <b>Livegram Reply Dispatched to User:</b> <code>{target_user_id}</code>")
    except Exception as e:
        logging.exception(f"Livegram message delivery routing fatal: {e}")
        await message.reply_text(f"❌ <b>Delivery Exception Failure:</b> <code>{html.escape(str(e))}</code>")

# ✅ FIXED INTAKE DATA PIPELINE (Proper step-by-step guidance for TxID and Photo)
@bot.on_message(filters.private & ~filters.command(["start", "help", "broadcast", "status", "ban", "unban"]))
async def forward_to_admin_manual_check(client: Client, message: Message):
    if await check_banned_middleware(message): return
    user_id = message.from_user.id
    if user_id == ADMIN_ID: return 

    state = await DBManager.get_user_state(user_id)
    if not state or state.get("status") not in ["AWAITING_DATA", "COLLECTING"]:
        await message.reply_text("👋 Hello! Please send `/start` and select a subscription plan.")
        return

    content = message.text if message.text else message.caption
    if content:
        detected_utr = None
        upi_match = re.search(r"\b\d{12}\b", content)
        crypto_match = re.search(r"\b(0X)?[A-Fa-f0-9]{64}\b", content.upper())
        
        if upi_match:
            detected_utr = upi_match.group(0)
        elif crypto_match:
            detected_utr = crypto_match.group(0)
            
        if detected_utr:
            utr_status = await DBManager.check_utr(detected_utr)
            if utr_status in ["PENDING", "APPROVED"]:
                await message.reply_text("🚫 <b>Security Alert:</b> This Transaction Reference / TxID has already been submitted.")
                return
            state["utr"] = detected_utr
            await DBManager.set_user_state(user_id, state)

    if message.photo:
        photo_id = message.photo.file_id
        state["photo"] = photo_id
        await DBManager.set_user_state(user_id, state)

    # ✅ FIXED STEP LOGIC: Checking parameters cleanly and routing correct helper texts
    if not state.get("utr") or not state.get("photo"):
        state["status"] = "COLLECTING"
        await DBManager.set_user_state(user_id, state)
        
        if not state.get("utr"):
            await message.reply_text("⏳ Please provide your Reference / UTR / TxID string accurately.")
        elif not state.get("photo"):
            await message.reply_text("⏳ Reference captured! Please dispatch your validation Screenshot image right after.")
        return

    inserted_row_id = await DBManager.add_payment_intent(state["utr"], user_id, state["price"], state["channel_key"])
    if not inserted_row_id:
        await message.reply_text("🚫 <b>Security Exception:</b> This exact TxID/UTR database trace token already exists inside our verification pipelines.")
        return

    selected_channel = CHANNELS_REGISTRY[state["channel_key"]]
    channel_name = html.escape(selected_channel["name"])
    method_used = html.escape(state.get("method", "FIAT"))
    await DBManager.clear_user_state(user_id)
    
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access", callback_data=f"appv_{inserted_row_id}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"rejc_{inserted_row_id}")]
    ])

    safe_admin_name = html.escape(message.from_user.first_name or "User")
    admin_caption = (
        f"💰 <b>New Payment Verification Pending!</b>\n\n"
        f"👤 <b>User:</b> {safe_admin_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📦 <b>Target Channel:</b> {channel_name}\n"
        f"💳 <b>Gate:</b> {method_used}\n"
        f"🔢 <b>Ref/TxID:</b> <code>{state['utr']}</code>"
    )

    log_message_node = await bot.send_photo(
        chat_id=LOG_CHANNEL_ID, photo=state["photo"], caption=admin_caption, reply_markup=admin_keyboard
    )
    await DBManager.update_log_message_id(inserted_row_id, log_message_node.id)
    await message.reply_text("⏳ <b>Submission Forwarded!</b> Admin verification team is checking details.")

@bot.on_callback_query(filters.regex(r"^(appv|rejc)_[a-f0-9]{16}$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Security Violation: Unauthorized Command Interface Dropped.", show_alert=True)
        return
        
    action, row_id_str = callback.data.split("_")
    
    payment_record = await DBManager.fetch_record_by_id(row_id_str)
    if not payment_record:
        await callback.message.edit_caption(caption="❌ <b>Error:</b> Target database reference lost.")
        await callback.answer()
        return

    if payment_record["status"] in ["APPROVED", "REJECTED"]:
        await callback.answer("⚠️ Action Blocked: Already completely handled.", show_alert=True)
        return

    target_user_id = payment_record["user_id"]
    channel_key = payment_record.get("channel_key", "game_comp")
    selected_channel = CHANNELS_REGISTRY[channel_key]

    if action == "appv":
        try:
            expire_datetime_obj = datetime.now(timezone.utc) + timedelta(days=1)
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=selected_channel["target_id"], member_limit=1, expire_date=expire_datetime_obj
            )
            await DBManager.update_status_by_id(row_id_str, "APPROVED")
            await DBManager.clear_user_state(target_user_id)
            
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 <b>Payment Verified!</b>\n\nClick link below to access your requested channel:\n👉 {invite_link_payload.invite_link}\n\n⚠️ <i>Expires in 24 hours.</i>"
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🟢 <b>STATUS: APPROVED TRACK LOG</b>")
        except Exception as e:
            logging.exception(f"Link tracking runtime fatal: {e}")
            await callback.message.reply_text(f"❌ <b>Link Creation Engine Failure:</b> <code>{html.escape(str(e))}</code>")

    elif action == "rejc":
        try:
            await DBManager.update_status_by_id(row_id_str, "REJECTED")
            await DBManager.clear_user_state(target_user_id)
            
            await bot.send_message(
                chat_id=target_user_id,
                text="❌ <b>Payment Rejected!</b> Please try again with valid screenshot parameters."
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🔴 <b>STATUS: REJECTED TRACK LOG</b>")
        except Exception as e: 
            logging.exception(f"Rejection workflow trace crash: {e}")
            
    await callback.answer()

# ==========================================
# 🚀 CORE PLATFORM STARTUP BOOTSTRAPPER
# ==========================================
async def main():
    logging.info("⚙️ Bootstrapping core framework verification components...")
    try:
        await mongo_client.admin.command("ping")
        logging.info("📶 MongoDB Atlas Cloud Connection Verified Successfully!")
    except Exception as mongo_err:
        logging.critical(f"🛑 MongoDB Connection Failed! Execution halted: {mongo_err}")
        return

    try:
        await users_col.create_index("user_id", unique=True)
        await payments_col.create_index("utr", unique=True)
        await payments_col.create_index("id", unique=True)
        await payments_col.create_index("log_msg_id")
        logging.info("🛡️ Production DB Composite Indexes compiled flawlessly.")
    except Exception as idx_err:
        logging.warning(f"⚠️ Index compilation structural notice: {idx_err}")

    logging.info("🔥 Hardened Enterprise Production Single Bot Framework Online.")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
    
                
