import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# ==========================================
# ⚙️ CONFIGURATION SETTINGS PIPELINE
# ==========================================
API_ID = 34042874                   # ⚠️ Enter your Telegram API ID
API_HASH = "494b9f740bc2f8f0e1a17c1c9f27ed9c"          # ⚠️ Enter your Telegram API Hash
BOT_TOKEN = "8492099684:AAH2lszBjqcZj5bmr_ouvzWKNi32FOUnuWc"        # ⚠️ Enter your Bot Token
ADMIN_ID = 2066626554               # ⚠️ Enter your personal Numeric Telegram ID
TARGET_CHANNEL_ID = -1003880366972  # ⚠️ Enter your Premium Channel/Group ID

bot = Client("simple_pay_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Temporary runtime storage to track current active approval sequences context maps
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
    # You can alternatively use send_photo if you want to push a specific QR image asset link directly
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

# Catching text and photo details to pipe to Admin Manual Logs Channel View Dashboard
@bot.on_message((filters.text | filters.photo) & filters.private)
async def forward_to_admin_manual_check(client: Client, message: Message):
    if message.from_user.id == ADMIN_ID:
        return # Skip processing actions if admin themselves inputs data streams 

    user_ref = message.from_user.id
    username_ref = f"@{message.from_user.username}" if message.from_user.username else "No Username"
    
    # Store request snapshot state contexts
    pending_requests[user_ref] = {
        "user_id": user_ref,
        "username": username_ref
    }

    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Give Access (Approve)", callback_data=f"approve_{user_ref}")],
        [InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{user_ref}")]
    ])

    # Dynamic log output indicators notification dispatch targeting owner space console directly
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 **New Manual Verification Request Pending!**\n\n"
             f"👤 **User Name:** {message.from_user.first_name}\n"
             f"🆔 **User Index Identification ID:** `{user_ref}`\n"
             f"🌐 **Handle Profile:** {username_ref}\n\n"
             f"👇 Review data submission payloads images logs trace parameters matching criteria. Trigger operational status down below:",
        reply_markup=admin_keyboard
    )
    # Forward the incoming transaction proof log payload directly over to administrative desk workspace interface tracking parameters
    await message.forward(chat_id=ADMIN_ID)
    await message.reply_text("⏳ **Submission Forwarded Successfully!** Admin pipeline verification team checks entries records data. Please hold tracking state indicators limits loops updates.")

@bot.on_callback_query(filters.regex(r"^(approve|reject)_\d+$"))
async def execution_routing_control_switches(client: Client, callback: CallbackQuery):
    action, target_user_str = callback.data.split("_")
    target_user_id = int(target_user_str)

    if action == "approve":
        try:
            # Dynamically auto generate single 1-time usable membership invite link that automatically caps 1 entry parameters bounds checks
            invite_link_payload = await bot.create_chat_invite_link(
                chat_id=TARGET_CHANNEL_ID,
                member_limit=1
            )
            
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 **Payment Verified Successfully!**\n\n"
                     f"Welcome ❤️ Click the authentic single use tracking confirmation profile node link below to access premium spaces:\n\n"
                     f"👉 {invite_link_payload.invite_link}\n\n"
                     f"⚠️ _Note: This URL tracks individual entry validation markers. Access links break state verification targets upon registration execution loops parameters metrics checks._"
            )
            await callback.message.edit_text(f"✅ Verified User Context `{target_user_id}` Access Clearance. Single dynamic link issued.")
        except Exception as dynamic_failure_exception:
            await callback.message.edit_text(f"❌ **Link Execution Exception Error:** {dynamic_failure_exception}")

    elif action == "reject":
        await bot.send_message(
            chat_id=target_user_id,
            text="❌ **Payment Rejected!**\n\nReason profile mapping fails verification matching bounds standards check definitions parameters. Please press Support connection options lines logs profile tracker to correct tracking variables inputs records structure instantly."
        )
        await callback.message.edit_text(f"❌ Rejected Transaction Registration Logs Track Context For User Identification: `{target_user_id}`")
        
    await callback.answer()

# ==========================================
# 🚀 INITIALIZATION EXECUTOR ENGINE KICKSTART
# ==========================================
if __name__ == "__main__":
    print("🔥 Single Bot Manual Approvals Infrastructure Booting Context System States...")
    bot.run()
