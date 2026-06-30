import asyncio
import sys
import types
import time
import sqlite3
import re  # <--- Idigo ఇక్కడే ఉంది, మన అనలైజర్ చూడలేదు! 😂

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
TARGET_CHANNEL_ID = -1002255752986  

bot = Client("simple_pay_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🗄️ PERSISTENT DATABASE MANAGEMENT
# ==========================================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect("bot_data.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                utr TEXT PRIMARY KEY,
                user_id INTEGER,
                status TEXT DEFAULT 'PENDING'
            )
        '''); self.conn.commit()

    def check_utr(self, utr):
        self.cursor.execute("SELECT status FROM payments WHERE utr = ?", (utr,))
        res = self.cursor.fetchone()
        return res[0] if res else None

    def add_utr(self, utr, user_id):
        try:
            self.cursor.execute("INSERT INTO payments (utr, user_id) VALUES (?, ?)", (utr, user_id))
            self.conn.commit(); return True
        except sqlite3.IntegrityError: return False

    def update_status(self, user_id, status):
        self.cursor.execute("UPDATE payments SET status = ? WHERE user_id = ? AND status = 'PENDING'", (status, user_id))
        self.conn.commit()

    def remove_failed_utr(self, user_id):
        self.cursor.execute("DELETE FROM payments WHERE user_id = ? AND status = 'PENDING'", (user_id,))
        self.conn.commit()

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
        "🤖 **Payment Details Gateway Ledger**:\n\n▫️ **UPI ID:** `telugumovies8985-1@oksbi`\n▫️ **Amount:** `₹99`",
        reply_markup=keyboard
    )
    await callback.answer()

@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    user_billing_state[callback.from_user.id] = {"status": "AWAITING_DATA", "utr": None, "photo": None}
    await callback.message.reply_text(
        "📝 **Verification Requirements:**\n\n1️⃣ Send your **UTR Number** (12 Digits) in text.\n2️⃣ Send the **Screenshot image** right after."
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
        # FIX 3 & 5: Tightened Regex specifically for Standard Indian Banking UTR/Ref Formats (12 Digits)
        utr_match = re.search(r"\b\d{12}\b", content)
        if utr_match:
            detected_utr = utr_match.group(0)
            utr_status = db.check_utr(detected_utr)
            if utr_status in ["PENDING", "APPROVED"]:
                await message.reply_text("🚫 **Security Alert:** This UTR has already been submitted.")
                return
            state["utr"] = detected_utr
            db.add_utr(detected_utr, user_id)

    # FIX 4: Pyrogram Photo Object handler using high-res index marker [-1] safely
    if message.photo:
        state["photo"] = message.photo.file_id

    if not state["utr"] or not state["photo"]:
        state["status"] = "COLLECTING"
        await message.reply_text("⏳ Received part of data. Please provide the missing part (UTR text or Screenshot image).")
        return

    user_billing_state.pop(user_id, None)
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access (Approve)", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{user_id}")]
    ])

    # FIX 2: Admin text values injected cleanly right into the photo caption log layout
    admin_caption = (
        f"💰 **New Verification Request!**\n\n"
        f"👤 **User:** {message.from_user.first_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"🌐 **Handle:** {username_ref}\n"
        f"🔢 **UTR:** `{state['utr']}`"
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=state["photo"],
        caption=admin_caption,
        reply_markup=admin_keyboard
    )
    await message.reply_text("⏳ **Submission Forwarded!** Admin is checking your details.")

@bot.on_callback_query(filters.regex(r"^(approve|reject)_\d+$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    action, target_user_str = callback.data.split("_", 1)
    target_user_id = int(target_user_str)

    if action == "approve":
        try:
            # FIX 1: Strict Native Unix timestamp epoch time calculation
            expire_timestamp = int(time.time()) + 86400
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=TARGET_CHANNEL_ID,
                member_limit=1,
                expire_date=expire_timestamp
            )
            db.update_status(target_user_id, "APPROVED")
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Payment Verified!**\n\nClick link below to access channel:\n👉 {invite_link_payload.invite_link}\n\n⚠️ _Expires in 24 hours._"
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ **APPROVED**")
        except Exception as dynamic_failure_exception:
            await callback.message.reply_text(f"❌ **Link Error:** `{dynamic_failure_exception}`")

    elif action == "reject":
        try:
            db.remove_failed_utr(target_user_id)
            await bot.send_message(
                chat_id=target_user_id,
                text="❌ **Payment Rejected!** Please try again with valid proof."
            )
            await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ **REJECTED**")
        except Exception as e: print(f"Failed to reply: {e}")
    await callback.answer()

async def main():
    print("🔥 Bot Started Successfully!")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
