import asyncio
import sys
import types
import time
import re
import os
import logging
import urllib.parse
import uuid
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

from pyrogram import Client, filters, enums
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8492099684:AAH2lszBjqcZj5bmr_ouvzWKNi32FOUnuWc")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 2066626554))
TARGET_CHANNEL_ID = int(os.environ.get("TARGET_CHANNEL_ID", -1001522411163))
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", -1001639319995))

MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://MarvelAndDc:MarvelAndDc@cluster0.z0uow.mongodb.net/?retryWrites=true&w=majority")

# 💳 Payment Configs
UPI_ID = "Telugumovies8985-1@oksbi"
MERCHANT_NAME = "Premium Access"

PLANS = {
    "standard": {"name": "Basic Standard Plan", "price": 99},
    "premium": {"name": "Ultimate Premium Plan", "price": 299}
}

bot = Client(
    "simple_pay_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.MARKDOWN
)

# ==========================================
# 🗄️ ASYNCHRONOUS MONGODB CLOUD DATABASE PIPELINE
# ==========================================
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
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {"username": username, "first_name": first_name, "join_date": int(time.time()), "is_banned": 0}},
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
    async def add_payment_intent(utr, user_id, amount):
        try:
            row_id = uuid.uuid4().hex[:16]
            await payments_col.insert_one({
                "id": row_id, "utr": utr, "user_id": user_id, "amount": amount,
                "status": "PENDING", "timestamp": int(time.time()), "log_msg_id": 0
            })
            return row_id
        except Exception:
            logging.exception("Failed to insert unique payment transaction mapping profile.")
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
        # Restored function for explicit deletion constraints if invoked (Fix 2)
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

# ==========================================
# 🎰 LOCAL DYNAMIC QR COMPILER MECHANISM
# ==========================================
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

# ==========================================
# 🤖 MIDDLEWARE AND ACTION SECURITY ROUTERS
# ==========================================
async def check_banned_middleware(message: Message):
    if await DBManager.is_user_banned(message.from_user.id):
        await message.reply_text("🚫 **Access Denied:** Your profile has been blacklisted.")
        return True
    return False

@bot.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    if await check_banned_middleware(message): return
    user_id = message.from_user.id
    await DBManager.clear_user_state(user_id)
    
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    if not await DBManager.check_user_exists(user_id):
        await DBManager.add_user(user_id, message.from_user.username, message.from_user.first_name)
        new_user_log = (
            f"🆕 **New User Started Bot!**\n\n👤 **Name:** {message.from_user.first_name}\n"
            f"🆔 **ID:** `{user_id}`\n🌐 **Handle:** {username_ref}"
        )
        try: await bot.send_message(chat_id=LOG_CHANNEL_ID, text=new_user_log)
        except Exception as e: logging.exception(e)
            
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ Standard Access (₹99)", callback_data="select_standard")],
        [InlineKeyboardButton("🚀 Premium Full Year (₹299)", callback_data="select_premium")],
        [InlineKeyboardButton("📞 Support Desk", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await message.reply_text(
        "👋 **Welcome to Premium Channels Gateway Portal**\n\n⚡ Select your subscription plan below to generate an instant payment token:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex(r"^select_(standard|premium)$"))
async def plan_selection_handler(client: Client, callback: CallbackQuery):
    if await DBManager.is_user_banned(callback.from_user.id): return
    plan_key = callback.data.split("_")[1]
    selected_plan = PLANS[plan_key]
    
    await DBManager.set_user_state(callback.from_user.id, {
        "status": "INITIATED", "plan": plan_key, "price": selected_plan["price"], "utr": None, "photo": None
    })
    
    try:
        qr_stream = get_local_upi_qr(selected_plan["price"])
        intent_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(MERCHANT_NAME)}&am={selected_plan['price']}&cu=INR"
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Proceed to Verify Payment", callback_data="confirm_paid")]])
        
        caption_text = (
            f"🤖 **Payment Session Invoice Generated (Local QR)**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Selected Plan:** `{selected_plan['name']}`\n💳 **Fixed Amount:** `₹{selected_plan['price']}`\n📌 **UPI ID Ref:** `{UPI_ID}`\n\n"
            f"📱 **Mobile Users:** [👉 Click Here to Pay Instantly]({intent_url})\n\n"
            f"📸 **Desktop Users:** Scan the QR code image above.\n\n"
            f"💸 _Pay exact rate amount, capture screenshot confirmation, and click button below._"
        )
        
        await callback.message.reply_photo(photo=qr_stream, caption=caption_text, reply_markup=keyboard)
        await callback.message.delete()
    except Exception as e:
        logging.exception(e)
        await callback.message.reply_text("❌ **Invoice Engine Failure.** Please try again or contact support.")
    finally:
        await callback.answer()

@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    if await DBManager.is_user_banned(callback.from_user.id): return
    state = await DBManager.get_user_state(callback.from_user.id)
    if not state:
        await callback.message.reply_text("❌ Session expired. Please send `/start` again.")
        await callback.answer()
        return
        
    await DBManager.set_user_state(callback.from_user.id, {"status": "AWAITING_DATA"})
    await callback.message.reply_text(
        "📝 **Verification Requirements:**\n\n1️⃣ Send your **12-digit UTR / Reference Number** in text.\n2️⃣ Send the **Screenshot image** right after."
    )
    await callback.answer()

# 📊 FINANCIAL LEDGER STATS
@bot.on_message(filters.command("status") & filters.private)
async def status_dashboard_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    stats = await DBManager.get_financial_analytics()
    report = (
        "📊 **Premium Payments & Financial Ledger Status**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 **Total Registered Users:** `{stats['total_users']}`\n📈 **Total Paid Transactions:** `{stats['approved_count']}`\n"
        f"⏳ **Pending Verification Queue:** `{stats['pending_queue']}`\n\n💵 **This Month Gross Revenue:** `₹{stats['month_revenue']}`\n"
        f"💰 **Lifetime Net Revenue Assets:** `₹{stats['lifetime_revenue']}`\n\n🕒 **Server Sync Zone:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`"
    )
    await message.reply_text(report)

# 🔨 BAN USER COMMAND
@bot.on_message(filters.command("ban") & filters.private)
async def ban_user_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    
    await DBManager.set_ban_status(target_id, 1)
    await message.reply_text(f"✅ User `{target_id}` Blacklisted.")
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"🔨 **Admin Ban:** User `{target_id}` banned.")
        await bot.send_message(chat_id=target_id, text="🚫 Your account has been blacklisted by the Administrator.")
    except Exception as e: logging.exception(e)

# 🔓 UNBAN USER COMMAND
@bot.on_message(filters.command("unban") & filters.private)
async def unban_user_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    
    await DBManager.set_ban_status(target_id, 0)
    await message.reply_text(f"✅ User `{target_id}` Whitelisted.")
    try: await bot.send_message(chat_id=target_id, text=f"🎉 Your account has been unbanned!")
    except Exception as e: logging.exception(e)

# 📢 CONCURRENT PARALLEL BROADCAST MECHANISM WITH FLOODWAIT EXCEPTION RECOVERY (Fix 9)
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
        logging.debug(f"Failed delivery to {user_id}: {e}")
        return "FAILED"

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.reply_to_message: return
    
    broadcast_msg = message.reply_to_message
    all_users = await DBManager.fetch_all_users()
    status_update_msg = await message.reply_text(f"⏳ **Starting Parallel Broadcast Blast...** Target: `{len(all_users)}` users.")
    
    success_count, blocked_count, failed_count = 0, 0, 0
    batch_size = 30  # Optimized threshold to limit extreme floodwait blocks
    
    for i in range(0, len(all_users), batch_size):
        batch = all_users[i:i + batch_size]
        tasks = [send_single_broadcast(broadcast_msg, user_id) for user_id in batch]
        results = await asyncio.gather(*tasks)
        
        for res in results:
            if res == "SUCCESS": success_count += 1
            elif res == "BLOCKED": blocked_count += 1
            elif res == "FAILED": failed_count += 1
            
        try: await status_update_msg.edit_text(f"⏳ Progress: `{min(i + batch_size, len(all_users))}/{len(all_users)}` processed...")
        except Exception: pass
        await asyncio.sleep(0.2)
        
    await status_update_msg.edit_text("✅ Parallel broadcast deployment execution complete.")
    await bot.send_message(
        chat_id=LOG_CHANNEL_ID, 
        text=f"📢 **Broadcast Matrix Report:**\n\n✅ Success: `{success_count}`\n🚫 Blocked/Removed: `{blocked_count}`\n⚠️ Failed: `{failed_count}`"
    )

# 📥 LIVEGRAM REPLY ROUTER
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & filters.reply)
async def livegram_reply_routing_handler(client: Client, message: Message):
    if message.text and message.text.startswith("/"): return
    target_user_id = await DBManager.fetch_user_by_log_msg(message.reply_to_message_id)
    if not target_user_id: return

    try:
        await message.copy(chat_id=target_user_id)
        await message.reply_text(f"🚀 **Livegram Reply Dispatched to User:** `{target_user_id}`")
    except Exception as e:
        logging.exception(e)
        await message.reply_text(f"❌ **Delivery Exception Failure:** `{e}`")

# 📥 CORE DATA INTAKE PIPELINE
@bot.on_message((filters.text | filters.photo) & filters.private & ~filters.command(["start", "help", "broadcast", "status", "ban", "unban"]))
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
        utr_match = re.search(r"\b[0-9]{12}\b", content)
        if utr_match:
            detected_utr = utr_match.group(0)
            utr_status = await DBManager.check_utr(detected_utr)
            if utr_status in ["PENDING", "APPROVED"]:
                await message.reply_text("🚫 **Security Alert:** This UTR Number has already been submitted.")
                return
            state["utr"] = detected_utr
            await DBManager.set_user_state(user_id, {"utr": detected_utr})

    if message.photo:
        photo_id = message.photo.file_id
        state["photo"] = photo_id
        await DBManager.set_user_state(user_id, {"photo": photo_id})

    if not state.get("utr") or not state.get("photo"):
        await DBManager.set_user_state(user_id, {"status": "COLLECTING"})
        if not state.get("utr"):
            await message.reply_text("⏳ Please provide your 12-digit numeric Transaction ID / UTR Number accurately.")
        else:
            await message.reply_text("⏳ UTR captured! Please dispatch your validation Screenshot image right after.")
        return

    inserted_row_id = await DBManager.add_payment_intent(state["utr"], user_id, state["price"])
    if not inserted_row_id:
        await message.reply_text("🚫 **Conflict Error:** Duplicate transaction token mismatch dropped.")
        return

    plan_name = PLANS[state["plan"]]["name"]
    amount_paid = state["price"]
    await DBManager.clear_user_state(user_id)
    
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access", callback_data=f"appv_{inserted_row_id}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"rejc_{inserted_row_id}")]
    ])

    admin_caption = (
        f"💰 **New Payment Verification Pending!**\n\n👤 **User:** {message.from_user.first_name}\n"
        f"🆔 **ID:** `{user_id}`\n📦 **Plan:** {plan_name}\n💵 **Value:** `₹{amount_paid}`\n🔢 **UTR Ref:** `{state['utr']}`"
    )

    log_message_node = await bot.send_photo(
        chat_id=LOG_CHANNEL_ID, photo=state["photo"], caption=admin_caption, reply_markup=admin_keyboard
    )
    await DBManager.update_log_message_id(inserted_row_id, log_message_node.id)
    await message.reply_text("⏳ **Submission Forwarded!** Admin verification team is checking details.")

# 🕹️ ACTIONS ROUTING CONTROL SWITCHES - fully restored comprehensive logic blocks (Fix 1, 5, 6)
@bot.on_callback_query(filters.regex(r"^(appv|rejc)_[a-f0-9]{16}$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Security Violation: Unauthorized Command Interface Dropped.", show_alert=True)
        return
        
    action, row_id_str = callback.data.split("_")
    
    payment_record = await DBManager.fetch_record_by_id(row_id_str)
    if not payment_record:
        await callback.message.edit_caption(caption="❌ **Error:** Target database token tracing context completely lost.")
        await callback.answer()
        return

    if payment_record["status"] in ["APPROVED", "REJECTED"]:
        await callback.answer("⚠️ Action Blocked: This transaction intent has already been completely handled.", show_alert=True)
        return

    target_user_id = payment_record["user_id"]

    if action == "appv":
        try:
            expire_datetime_obj = datetime.now(timezone.utc) + timedelta(days=1)
            # Link generation routine logic completely integrated (Fix 5)
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=TARGET_CHANNEL_ID, member_limit=1, expire_date=expire_datetime_obj
            )
            await DBManager.update_status_by_id(row_id_str, "APPROVED")
            await DBManager.clear_user_state(target_user_id)
            
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Payment Verified!**\n\nClick link below to access channel:\n👉 {invite_link_payload.invite_link}\n\n⚠️ _Expires in 24 hours._"
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🟢 **STATUS:** APPROVED TRACK LOG")
        except Exception as e:
            logging.exception(e)
            await callback.message.reply_text(f"❌ **Link Creation Engine Failure:** `{e}`")

    elif action == "rejc":
        try:
            # Preservation audit trail log strategy applied without dropping rows (Fix 6)
            await DBManager.update_status_by_id(row_id_str, "REJECTED")
            await DBManager.clear_user_state(target_user_id)
            
            await bot.send_message(
                chat_id=target_user_id,
                text="❌ **Payment Rejected!** Please try again with valid screenshot parameters."
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🔴 **STATUS:** REJECTED TRACK LOG")
        except Exception as e: 
            logging.exception(e)
            
    await callback.answer()

# ==========================================
# 🚀 CORE PLATFORM STARTUP BOOTSTRAPPER (Fix 10)
# ==========================================
async def main():
    logging.info("⚙️ Bootstrapping core framework verification components...")
    
    try:
        await mongo_client.admin.command("ping")
        logging.info("📶 MongoDB Atlas Cloud Infrastructure Connection Verified Successfully!")
    except Exception as mongo_err:
        logging.critical(f"🛑 MongoDB Connection Failed! Execution halted: {mongo_err}")
        return

    # Dynamic Background Index Engine Compilation (Fix 3 & 8)
    try:
        await users_col.create_index("user_id", unique=True)
        await payments_col.create_index("utr", unique=True)
        await payments_col.create_index("id", unique=True)
        await payments_col.create_index("log_msg_id")
        logging.info("🛡️ Production DB Composite Indexes compiled flawlessly.")
    except Exception as idx_err:
        logging.warning(f"⚠️ Index compilation structural notice: {idx_err}")

    logging.info("🔥 Hardened Enterprise Production Single Bot Framework Online with Async MongoDB Engines.")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
