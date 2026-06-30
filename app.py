import asyncio
import sys

# ==========================================
# 🛑 CORE HOTFIX FOR PYTHON 3.14 LOOP ISSUES
# ==========================================
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Prevent pyrogram from loading internal crashing sync logic engines
sys.modules["pyrogram.sync"] = None 

import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ==========================================
# ⚙️ CONFIGURATION SETTINGS PIPELINE (INJECTED)
# ==========================================
API_ID = 34042874                   
API_HASH = "494b9f740bc2f8f0e1a17c1c9f27ed9c"          
BOT_TOKEN = "8492099684:AAH2lszBjqcZj5bmr_ouvzWKNi32FOUnuWc"        
ADMIN_ID = 2066626554               
TARGET_CHANNEL_ID = -1003880366972  

bot = Client("simple_pay_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

pending_requests = {}

# ==========================================
# 🤖 BOT INTERFACE LOGIC FLOWS
# ==========================================

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay Now", callback_data="show_qr")],
        [InlineKeyboardButton("📞 Support", url=f"tg://user?id={ADMIN_ID}")]
    ])
    await message.reply_text(
        "👋 **Welcome Premium Channel Access**\n\n"
        "Price: **Extra Special Rate ₹99**\n"
        "👇 Click below to pay and unlock instantly:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("^show_qr$"))
async def show_qr_handler(client: Client, callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I Have Paid", callback_data="confirm_paid")]
    ])
    await callback.message.reply_text(
        "🤖 **Payment Details Gateway Ledger**:\n\n"
        "▫️ **UPI ID:** `safehands@ibl`\n"
        "▫️ **Amount:** `₹99`\n\n"
        "📌 _Please pay using the transaction details code target mentioned above. Once payment processing updates complete successfully, click verification indicators down below._",
        reply_markup=keyboard
    )
    await callback.answer()

@bot.on_callback_query(filters.regex("^confirm_paid$"))
async def instruct_user_inputs(client: Client, callback: CallbackQuery):
    await callback.message.reply_text(
        "📝 **Verification Blueprint Inputs Details Requirements:**\n\n"
        "Please type and reply to this message directly providing details using this simple format:\n\n"
        "`AMOUNT: 99\nUTR: 1234XXXXXXXX\nUPI Used: buyer@okaxis`\n\n"
        "📷 **And ALSO send the payment confirmation screenshot image right after!**"
    )
    await callback.answer()

# FIX: Added ~filters.command to prevent /start or other commands from being forwarded
@bot.on_message((filters.text | filters.photo) & filters.private & ~filters.command)
async def forward_to_admin_manual_check(client: Client, message: Message):
    if message.from_user.id == ADMIN_ID:
        return 

    user_ref = message.from_user.id
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    pending_requests[user_ref] = {
        "user_id": user_ref,
        "username": username_ref
    }

    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access (Approve)", callback_data=f"approve_{user_ref}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{user_ref}")]
    ])

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 **New Manual Verification Request Pending!**\n\n"
             f"👤 **User Name:** {message.from_user.first_name}\n"
             f"🆔 **User Index ID:** `{user_ref}`\n"
             f"🌐 **Handle Profile:** {username_ref}\n\n"
             f"👇 Review data submission payloads images logs trace parameters matching criteria. Trigger operational status down below:",
        reply_markup=admin_keyboard
    )
    await message.forward(chat_id=ADMIN_ID)
    await message.reply_text("⏳ **Submission Forwarded Successfully!** Admin pipeline verification checks entries records data. Please hold tracking state.")

@bot.on_callback_query(filters.regex(r"^(approve|reject)_\d+$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    action, target_user_str = callback.data.split("_")
    target_user_id = int(target_user_str)

    if action == "approve":
        try:
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=TARGET_CHANNEL_ID,
                member_limit=1
            )
            
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Payment Verified Successfully!**\n\n"
                     f"Welcome ❤️ Click the link below to access premium spaces:\n\n"
                     f"👉 {invite_link_payload.invite_link}\n\n"
                     f"⚠️ _Note: This URL works for 1 single person join execution loop parameter check._"
            )
            await callback.message.edit_text(f"✅ Verified User Context `{target_user_id}` Access Clearance. Link issued.")
        except Exception as dynamic_failure_exception:
            await callback.message.edit_text(f"❌ **Link Execution Exception Error:** {dynamic_failure_exception}")

    elif action == "reject":
        await bot.send_message(
            chat_id=target_user_id,
            text="❌ **Payment Rejected!**\n\nReason profile mapping fails verification matching bounds standards check parameters. Please support connection options to check tracking layout variables."
        )
        await callback.message.edit_text(f"❌ Rejected Transaction Registration Logs for User: `{target_user_id}`")
        
    await callback.answer()

# ==========================================
# 🚀 LIFECYCLE MANAGEMENT BOOTSTRAPPER
# ==========================================
async def main():
    print("🔥 Single Bot Manual Approvals Infrastructure Booting Context System States...")
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
