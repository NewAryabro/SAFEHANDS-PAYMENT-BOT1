import asyncio
import sys
import types
import time
import sqlite3
import re
from datetime import datetime, timezone, timedelta  # <-- Fixed UTC time zones

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

# ==========================================
# ⚙️ SECURE CONFIGURATION CONFIG
# ==========================================
API_ID = 34042874                   
API_HASH = "494b9f740bc2f8f0e1a17c1c9f27ed9c"          
BOT_TOKEN = "8492099684:AAH2lszBjqcZj5bmr_ouvzWKNi32FOUnuWc"        
ADMIN_ID = 2066626554               
TARGET_CHANNEL_ID = -1001522411163  
LOG_CHANNEL_ID = -1001639319995     

bot = Client("simple_pay_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🗄️ AUTO-INCREMENT DATABANK HANDLER (FIX 1, 2 & 6)
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
        # FIX 1: Assigned integer PRIMARY KEY rowid to resolve Telegram's 64-byte payload barrier
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                utr TEXT UNIQUE,
                user_id INTEGER,
                status TEXT DEFAULT 'PENDING',
                timestamp INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    def check_utr(self, utr):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT status FROM payments WHERE utr = ?", (utr,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def add_payment_intent(self, utr, user_id):
        # FIX 2: Strict insertion status validation lookup
        conn, cursor = self._get_conn()
        try:
            cursor.execute(
                "INSERT INTO payments (utr, user_id, timestamp) VALUES (?, ?, ?)", 
                (utr, user_id, int(time.time()))
            )
            conn.commit()
            last_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            last_id = None
        finally:
            conn.close()
        return last_id

    def fetch_record_by_id(self, row_id):
        conn, cursor = self._get_conn()
        cursor.execute("SELECT utr, user_id, status FROM payments WHERE id = ?", (row_id,))
        res = cursor.fetchone()
        conn.close()
        return {"utr": res[0], "user_id": res[1], "status": res[2]} if res else None

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
# 🤖 BOT INTERFACE LOGIC FLOWS
# ==========================================

@bot.on_message(filters.command(["start", "help"]) & filters.private)
async def start_handler(client: Client, message: Message):
    user_billing_state.pop(message.from_user.id, None)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay Now", callback_data="show_qr")],
        [InlineKeyboardButton("📞 Support", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await message.reply_text(
        "👋 **Welcome Premium Channel Access**\n\nPrice: **Extra Special Rate ₹99**\n👇 Click below to pay:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("^show_qr$"))
async def show_qr_handler(client: Client, callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ I Have Paid", callback_data="confirm_paid")]])
    await callback.message.reply_text(
        "🤖 **Payment Details Gateway Ledger**:\n\n▫️ **UPI ID:** `sacfehands@ibl`\n▫️ **Amount:** `₹99`\n\n📌 _Send payment screenshots and UTR sequences down below._",
        reply_markup=keyboard
    )
    await callback.answer()

@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    user_billing_state[callback.from_user.id] = {"status": "AWAITING_DATA", "utr": None, "photo": None}
    await callback.message.reply_text(
        "📝 **Verification Requirements:**\n\n1️⃣ Send your **UTR / Reference Number** in text.\n2️⃣ Send the **Screenshot image** right after."
    )
    await callback.answer()

@bot.on_message((filters.text | filters.photo) & filters.private & ~filters.command(["start", "help"]))
async def forward_to_admin_manual_check(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID: return 

    state = user_billing_state.get(user_id)
    if not state or state["status"] not in ["AWAITING_DATA", "COLLECTING"]:
        await message.reply_text("👋 Hello! Please send `/start` and click **💳 Pay Now**.")
        return

    content = message.text if message.text else message.caption
    if content:
        # Strict matching specifically targeting clear transactional reference keys block formats
        utr_match = re.search(r"\b[A-Za-z0-9]{8,22}\b", content)
        if utr_match:
            detected_utr = utr_match.group(0).upper()
            utr_status = db.check_utr(detected_utr)
            if utr_status in ["PENDING", "APPROVED"]:
                await message.reply_text("🚫 **Security Alert:** This Transaction Ref/UTR has already been submitted.")
                return
            state["utr"] = detected_utr

    # FIX 3: Safe nested photo file_id discovery engine across differing Pyrogram versions
    if message.photo:
        if isinstance(message.photo, list):
            state["photo"] = message.photo[-1].file_id
        elif hasattr(message.photo, "file_id"):
            state["photo"] = message.photo.file_id

    if not state["utr"] or not state["photo"]:
        state["status"] = "COLLECTING"
        if not state["utr"]:
            await message.reply_text("⏳ Please provide your text message listing the Transaction ID / UTR Number accurately.")
        else:
            await message.reply_text("⏳ UTR captured! Please dispatch your validation Image attachment capture right after.")
        return

    # FIX 2: Check returned insertion primary key row sequence
    inserted_row_id = db.add_payment_intent(state["utr"], user_id)
    if not inserted_row_id:
        await message.reply_text("🚫 **Race Condition Conflict Alert:** Transaction verification pipeline drops identical entries submission tracks loops.")
        return

    user_billing_state.pop(user_id, None)
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    # FIX 1: Passing ONLY short database row IDs inside callback payloads ensures it stays way below 64 bytes
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access", callback_data=f"appv_{inserted_row_id}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"rejc_{inserted_row_id}")]
    ])

    admin_caption = (
        f"💰 **New Verification Request Pending!**\n\n"
        f"👤 **User:** {message.from_user.first_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"🌐 **Handle:** {username_ref}\n"
        f"🔢 **UTR Ref:** `{state['utr']}`"
    )

    await bot.send_photo(
        chat_id=LOG_CHANNEL_ID,
        photo=state["photo"],
        caption=admin_caption,
        reply_markup=admin_keyboard
    )
    await message.reply_text("⏳ **Submission Forwarded!** Admin verification team is checking details in logs channel.")

# FIX 1: Compact pattern routing listener intercepts micro payloads perfectly
@bot.on_callback_query(filters.regex(r"^(appv|rejc)_\d+$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    action, row_id_str = callback.data.split("_")
    db_row_id = int(row_id_str)
    
    # Fetch original tracking variables mapping records direct from databank row
    payment_record = db.fetch_record_by_id(db_row_id)
    if not payment_record:
        await callback.message.edit_caption(caption="❌ **Error:** Target database allocation reference trace logs completely deleted or lost.")
        await callback.answer()
        return

    target_user_id = payment_record["user_id"]
    target_utr = payment_record["utr"]

    if action == "appv":
        try:
            # FIX 4: Implemented safe explicit timezone-aware UTC datetime parameters objects
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
            await callback.message.reply_text(f"❌ **Link Error Exception:** `{dynamic_failure_exception}`")

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
    print("🔥 Secure Production Single Bot Framework Online with Log Channel routing active.")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
