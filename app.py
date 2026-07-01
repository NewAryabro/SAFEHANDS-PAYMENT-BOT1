import asyncio
import sys
import types
import time
import sqlite3
import re
import urllib.parse
from datetime import datetime, timezone, timedelta

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

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import UserIsBlocked, InputUserDeactivated

# ==========================================
# ⚙️ SECURE CONFIGURATION CONFIG
# ==========================================
API_ID = 34042874                   
API_HASH = "494b9f740bc2f8f0e1a17c1c9f27ed9c"          
BOT_TOKEN = "8492099684:AAH2lszBjqcZj5bmr_ouvzWKNi32FOUnuWc"        
ADMIN_ID = 2066626554               
TARGET_CHANNEL_ID = -1001522411163  
LOG_CHANNEL_ID = -1001639319995     

# 💳 Payment Gateway Configurations
UPI_ID = "safehands@ibl"
MERCHANT_NAME = "Premium Access"

# 🗓️ Subscription Plans Context Map
PLANS = {
    "standard": {"name": "Basic Standard Plan", "price": 99, "days": 30},
    "premium": {"name": "Ultimate Premium Plan", "price": 299, "days": 365}
}

bot = Client("simple_pay_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🗄️ EXTENDED FINANCIAL DATABANK HANDLER
# ==========================================
class Database:
    def __init__(self):
        self.db_path = "bot_data.db"
        self.setup()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        return conn, conn.cursor()

    def setup(self):
        conn, cursor = self._get_conn()
        # Payments Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utr TEXT UNIQUE,
                user_id INTEGER,
                amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING',
                timestamp INTEGER,
                log_msg_id INTEGER
            )
        ''')
        # Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_date INTEGER,
                is_banned INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()

    def check_user_exists(self, user_id):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return True if res else False

    def is_user_banned(self, user_id):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return True if res and res[0] == 1 else False

    def add_user(self, user_id, username, first_name):
        conn, cursor = self._get_conn()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, is_banned) VALUES (?, ?, ?, ?, 0)",
                (user_id, username, first_name, int(time.time()))
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            conn.close()

    def set_ban_status(self, user_id, ban_status):
        conn, cursor = self._get_conn()
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (ban_status, user_id))
        conn.commit()
        conn.close()

    def fetch_all_users(self):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def remove_user(self, user_id):
        conn, cursor = self._get_conn()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def get_financial_analytics(self):
        conn, cursor = self._get_conn()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT TOTAL(amount) FROM payments WHERE status = 'APPROVED'")
        lifetime_revenue = cursor.fetchone()[0]
        
        now = datetime.now(timezone.utc)
        month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        cursor.execute("SELECT TOTAL(amount) FROM payments WHERE status = 'APPROVED' AND timestamp >= ?", (month_start,))
        month_revenue = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'PENDING'")
        pending_queue = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'APPROVED'")
        approved_count = cursor.fetchone()[0]

        conn.close()
        return {
            "total_users": total_users,
            "lifetime_revenue": int(lifetime_revenue),
            "month_revenue": int(month_revenue),
            "pending_queue": pending_queue,
            "approved_count": approved_count
        }

    def check_utr(self, utr):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT status FROM payments WHERE utr = ?", (utr,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def add_payment_intent(self, utr, user_id, amount):
        conn, cursor = self._get_conn()
        try:
            cursor.execute(
                "INSERT INTO payments (utr, user_id, amount, timestamp) VALUES (?, ?, ?, ?)", 
                (utr, user_id, amount, int(time.time()))
            )
            conn.commit()
            last_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            last_id = None
        finally:
            conn.close()
        return last_id

    def update_log_message_id(self, row_id, log_msg_id):
        conn, cursor = self._get_conn()
        cursor.execute("UPDATE payments SET log_msg_id = ? WHERE id = ?", (log_msg_id, row_id))
        conn.commit()
        conn.close()

    def fetch_record_by_id(self, row_id):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT utr, user_id, amount, status FROM payments WHERE id = ?", (row_id,))
        res = cursor.fetchone()
        conn.close()
        return {"utr": res[0], "user_id": res[1], "amount": res[2], "status": res[3]} if res else None

    def fetch_user_by_log_msg(self, log_msg_id):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT user_id FROM payments WHERE log_msg_id = ?", (log_msg_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def update_status_by_id(self, row_id, status):
        conn, cursor = self._get_conn()
        cursor.execute("UPDATE payments SET status = ? WHERE id = ?", (status, row_id))
        conn.commit()
        conn.close()

    def remove_record_by_id(self, row_id):
        conn, cursor = self._get_conn()
        cursor.execute("DELETE FROM payments WHERE id = ?", (row_id,))
        conn.commit()
        conn.close()

db = Database()
user_billing_state = {}

# ==========================================
# Helper Modules (Dynamic QR Code Generation Engine)
# ==========================================
def generate_upi_qr_url(amount: int) -> str:
    payload = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(MERCHANT_NAME)}&am={amount}&cu=INR"
    return f"https://chart.googleapis.com/chart?chs=300x300&cht=qr&chl={urllib.parse.quote(payload)}"

# ==========================================
# 🤖 BOT INTERFACE LOGIC FLOWS
# ==========================================

async def check_banned_middleware(message: Message):
    if db.is_user_banned(message.from_user.id):
        await message.reply_text("🚫 **Access Denied:** Your profile has been blacklisted by the Administrator.")
        return True
    return False

@bot.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    if await check_banned_middleware(message): return
    user_id = message.from_user.id
    user_billing_state.pop(user_id, None)
    
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    if not db.check_user_exists(user_id):
        db.add_user(user_id, message.from_user.username, message.from_user.first_name)
        new_user_log = (
            f"🆕 **New User Started the Bot!**\n\n"
            f"👤 **Name:** {message.from_user.first_name}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"🌐 **Handle:** {username_ref}"
        )
        try: await bot.send_message(chat_id=LOG_CHANNEL_ID, text=new_user_log)
        except Exception: pass
            
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ Standard Access (₹99)", callback_data="select_standard")],
        [InlineKeyboardButton("🚀 Premium Full Year (₹299)", callback_data="select_premium")],
        [InlineKeyboardButton("📞 Support Desk", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await message.reply_text(
        "👋 **Welcome to Premium Channels Gateway Portal**\n\n⚡ Select your preferred access subscription plan below to generate a secure transaction session:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex(r"^select_(standard|premium)$"))
async def plan_selection_handler(client: Client, callback: CallbackQuery):
    if db.is_user_banned(callback.from_user.id): return
    plan_key = callback.data.split("_")[1]
    selected_plan = PLANS[plan_key]
    
    user_billing_state[callback.from_user.id] = {
        "status": "INITIATED", "plan": plan_key, "price": selected_plan["price"], "utr": None, "photo": None
    }
    
    qr_image_url = generate_upi_qr_url(selected_plan["price"])
    intent_url = f"upi://pay?pa={UPI_ID}&pn={urllib.parse.quote(MERCHANT_NAME)}&am={selected_plan['price']}&cu=INR"
    
    # ✅ FIX: Native Callback payload execution paths ONLY inside keyboards prevents raw schema url errors
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Proceed to Verify Payment", callback_data="confirm_paid")]
    ])
    
    caption_text = (
        f"🤖 **Payment Session Invoice Generated**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 **Selected Plan:** `{selected_plan['name']}`\n"
        f"💳 **Fixed Amount:** `₹{selected_plan['price']}`\n"
        f"📌 **UPI ID Ref:** `{UPI_ID}`\n\n"
        f"📱 **Mobile Users:** [👉 Click Here to Pay Instantly]({intent_url})\n\n"
        f"📸 **Desktop Users:** Scan the QR code image above using PhonePe, GPay, or Paytm.\n\n"
        f"💸 _Pay standard rates, take a screenshot, and click the button below to verify._"
    )
    
    await callback.message.reply_photo(
        photo=qr_image_url,
        caption=caption_text,
        reply_markup=keyboard
    )
    await callback.message.delete()
    await callback.answer()

@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    if db.is_user_banned(callback.from_user.id): return
    state = user_billing_state.get(callback.from_user.id)
    if not state:
        await callback.message.reply_text("❌ Session expired. Please send `/start` to select a plan again.")
        await callback.answer()
        return
        
    state["status"] = "AWAITING_DATA"
    await callback.message.reply_text(
        "📝 **Verification Requirements:**\n\n1️⃣ Send your **12-digit UTR / Reference Number** in text.\n2️⃣ Send the **Screenshot image** right after."
    )
    await callback.answer()

# 📊 FINANCIAL DASHBOARD COMMAND
@bot.on_message(filters.command("status") & filters.user(ADMIN_ID) & filters.private)
async def status_dashboard_handler(client: Client, message: Message):
    stats = db.get_financial_analytics()
    report = (
        "📊 **Premium Payments & Financial Ledger Status**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 **Total Registered Users:** `{stats['total_users']}`\n"
        f"📈 **Total Paid Transactions:** `{stats['approved_count']}`\n"
        f"⏳ **Pending Verification Queue:** `{stats['pending_queue']}`\n\n"
        f"💵 **This Month Gross Revenue:** `₹{stats['month_revenue']}`\n"
        f"💰 **Lifetime Net Revenue Assets:** `₹{stats['lifetime_revenue']}`\n\n"
        f"🕒 **Server Sync Zone:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`"
    )
    await message.reply_text(report)

# 🔨 BAN USER COMMAND
@bot.on_message(filters.command("ban") & filters.user(ADMIN_ID) & filters.private)
async def ban_user_handler(client: Client, message: Message):
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    db.set_ban_status(target_id, 1)
    await message.reply_text(f"✅ User `{target_id}` has been **Blacklisted**.")
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"🔨 **Admin Ban Action:** User `{target_id}` banned.")
        await bot.send_message(chat_id=target_id, text="🚫 Your account has been banned from using this bot.")
    except Exception: pass

# 🔓 UNBAN USER COMMAND
@bot.on_message(filters.command("unban") & filters.user(ADMIN_ID) & filters.private)
async def unban_user_handler(client: Client, message: Message):
    if len(message.command) < 2: return
    target_id_str = message.command[1]
    if not target_id_str.isdigit(): return
    target_id = int(target_id_str)
    db.set_ban_status(target_id, 0)
    await message.reply_text(f"✅ User `{target_id}` has been **Whitelisted**.")
    try:
        await bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"🔓 **Admin Unban Action:** User `{target_id}` unbanned.")
        await bot.send_message(chat_id=target_id, text="🎉 Your account has been unbanned!")
    except Exception: pass

# 📢 ADMIN BROADCAST LOGIC
@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_ID) & filters.private)
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message: return
    broadcast_msg = message.reply_to_message
    all_users = db.fetch_all_users()
    status_update_msg = await message.reply_text(f"⏳ **Starting Broadcast Blast...** Target: `{len(all_users)}` users.")
    success_count, blocked_count, failed_count = 0, 0, 0
    for idx, user_id in enumerate(all_users):
        try:
            await broadcast_msg.copy(chat_id=user_id)
            success_count += 1
        except (UserIsBlocked, InputUserDeactivated):
            blocked_count += 1
            db.remove_user(user_id)
        except Exception: failed_count += 1
        if idx % 15 == 0:
            try: await status_update_msg.edit_text(f"⏳ Processing: `{idx}/{len(all_users)}` finished...")
            except Exception: pass
        await asyncio.sleep(0.05)
    await status_update_msg.edit_text("✅ Broadcast complete.")
    await bot.send_message(chat_id=LOG_CHANNEL_ID, text=f"📢 **Broadcast Report Finished!**\n\n✅ Success: `{success_count}`\n🚫 Blocked: `{blocked_count}`")

# 📥 LIVEGRAM REPLY ENGINE
@bot.on_message(filters.chat(LOG_CHANNEL_ID) & filters.reply)
async def livegram_reply_routing_handler(client: Client, message: Message):
    if message.text and message.text.startswith("/"): return
    target_user_id = db.fetch_user_by_log_msg(message.reply_to_message_id)
    if not target_user_id: return

    try:
        await message.copy(chat_id=target_user_id)
        await message.reply_text(f"🚀 **Livegram Reply Dispatched Successfully to User:** `{target_user_id}`")
    except Exception as e:
        await message.reply_text(f"❌ **Delivery Failed:** `{e}`")

@bot.on_message((filters.text | filters.photo) & filters.private & ~filters.command(["start", "help", "broadcast", "status", "ban", "unban"]))
async def forward_to_admin_manual_check(client: Client, message: Message):
    if await check_banned_middleware(message): return
    user_id = message.from_user.id
    if user_id == ADMIN_ID: return 

    state = user_billing_state.get(user_id)
    if not state or state["status"] not in ["AWAITING_DATA", "COLLECTING"]:
        await message.reply_text("👋 Hello! Please send `/start` and select a subscription plan.")
        return

    content = message.text if message.text else message.caption
    if content:
        utr_match = re.search(r"\b[A-Za-z0-9]{8,22}\b", content)
        if utr_match:
            detected_utr = utr_match.group(0).upper()
            utr_status = db.check_utr(detected_utr)
            if utr_status in ["PENDING", "APPROVED"]:
                await message.reply_text("🚫 **Security Alert:** This Transaction Ref/UTR has already been submitted.")
                return
            state["utr"] = detected_utr

    if message.photo:
        if isinstance(message.photo, list): state["photo"] = message.photo[-1].file_id
        elif hasattr(message.photo, "file_id"): state["photo"] = message.photo.file_id

    if not state["utr"] or not state["photo"]:
        state["status"] = "COLLECTING"
        if not state["utr"]:
            await message.reply_text("⏳ Please provide your text message listing the Transaction ID / UTR Number accurately.")
        else:
            await message.reply_text("⏳ UTR captured! Please dispatch your validation Image attachment capture right after.")
        return

    inserted_row_id = db.add_payment_intent(state["utr"], user_id, state["price"])
    if not inserted_row_id:
        await message.reply_text("🚫 **Conflict Alert:** Transaction verification pipeline drops identical entries.")
        return

    plan_name = PLANS[state["plan"]]["name"]
    amount_paid = state["price"]
    user_billing_state.pop(user_id, None)
    
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access", callback_data=f"appv_{inserted_row_id}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"rejc_{inserted_row_id}")]
    ])

    admin_caption = (
        f"💰 **New Payment Verification Pending!**\n\n"
        f"👤 **User:** {message.from_user.first_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"📦 **Plan:** {plan_name}\n"
        f"💵 **Value:** `₹{amount_paid}`\n"
        f"🔢 **UTR Ref:** `{state['utr']}`"
    )

    log_message_node = await bot.send_photo(
        chat_id=LOG_CHANNEL_ID,
        photo=state["photo"],
        caption=admin_caption,
        reply_markup=admin_keyboard
    )
    db.update_log_message_id(inserted_row_id, log_message_node.id)
    await message.reply_text("⏳ **Submission Forwarded!** Admin verification team is checking details in logs channel.")

@bot.on_callback_query(filters.regex(r"^(appv|rejc)_\d+$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    action, row_id_str = callback.data.split("_")
    db_row_id = int(row_id_str)
    
    payment_record = db.fetch_record_by_id(db_row_id)
    if not payment_record:
        await callback.message.edit_caption(caption="❌ **Error:** Target database reference trace logs lost.")
        await callback.answer()
        return

    target_user_id = payment_record["user_id"]

    if action == "appv":
        try:
            expire_datetime_obj = datetime.now(timezone.utc) + timedelta(days=1)
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=TARGET_CHANNEL_ID,
                member_limit=1,
                expire_date=expire_datetime_obj
            )
            db.update_status_by_id(db_row_id, "APPROVED")
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Payment Verified!**\n\nClick link below to access channel:\n👉 {invite_link_payload.invite_link}\n\n⚠️ _Expires in 24 hours._"
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🟢 **STATUS:** APPROVED TRACK LOG")
        except Exception as dynamic_failure_exception:
            await callback.message.reply_text(f"❌ **Link Error:** `{dynamic_failure_exception}`")

    elif action == "rejc":
        try:
            db.remove_record_by_id(db_row_id)
            await bot.send_message(
                chat_id=target_user_id,
                text="❌ **Payment Rejected!** Please try again with valid proof parameters logs."
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🔴 **STATUS:** REJECTED TRACK LOG")
        except Exception as e: 
            print(f"Failed to reply: {e}")
    await callback.answer()

async def main():
    print("🔥 Secure Production Bot Online with Dynamic UPI QR & Financial Analytics Engines Active.")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
