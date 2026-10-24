import os
import re
import sys
import json
import time
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import logging
import requests
import subprocess
from urllib.parse import quote, urlparse

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception:
    pass

import core as helper
import database as db
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, WEBHOOK, PORT, OWNER_ID, ADMINS, FREE_LIMIT, is_admin
from aiohttp import ClientSession, web
from pyromod import listen
from subprocess import getstatusoutput

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    CallbackQuery
)
from pyrogram.errors import FloodWait
from style import Ashu
from classplus import is_classplus_url, sign_classplus_url, extract_content_id
from classx import is_classx_url, resolve_classx_url, get_classx_ytdlp_args, get_classx_headers
import cp_extractor
import yt_manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("main")

# Initialize the bot
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Telegram Bot Command definitions
USER_BOT_COMMANDS = [
    BotCommand("start", "Start the bot & check status"),
    BotCommand("cookie", "Set/Upload YouTube cookies.txt"),
    BotCommand("ytdl", "Download YouTube video using cookies"),
    BotCommand("extractcptxt", "Extract Classplus course to .txt (Free & Unlimited)"),
    BotCommand("myplan", "Check subscription & free quota"),
    BotCommand("dl", "Download single video/stream URL"),
    BotCommand("upload", "Batch download from .txt file"),
    BotCommand("cp", "Classplus DRM downloader"),
    BotCommand("classx", "ClassX Google Edge stream downloader"),
    BotCommand("help", "Help guide & supported sites"),
]

ADMIN_BOT_COMMANDS = [
    BotCommand("start", "Start bot & control panel"),
    BotCommand("cookie", "Set/Upload YouTube cookies.txt"),
    BotCommand("ytdl", "Download YouTube video using cookies"),
    BotCommand("extractcptxt", "Extract CP course to .txt (Free & Unlimited)"),
    BotCommand("addpaid", "Add paid user: /addpaid <id> [days]"),
    BotCommand("rempaid", "Remove paid user: /rempaid <id>"),
    BotCommand("resetlimit", "Reset download limit: /resetlimit <id>"),
    BotCommand("status", "Inspect user details: /status <id>"),
    BotCommand("paidusers", "List all active paid members"),
    BotCommand("stop", "Restart bot process"),
    BotCommand("myplan", "Check account plan"),
    BotCommand("dl", "Download single video/stream"),
    BotCommand("upload", "Batch download from .txt"),
    BotCommand("cp", "Classplus DRM downloader"),
    BotCommand("classx", "ClassX Google Edge stream downloader"),
    BotCommand("help", "Help guide & instructions"),
]


async def setup_bot_commands():
    """Configures Telegram Bot Command Menu prompt: User commands for regular users, All commands for admins."""
    try:
        await bot.set_bot_commands(USER_BOT_COMMANDS, scope=BotCommandScopeDefault())
        logger.info("[Commands] Default user commands configured.")
    except Exception as e:
        logger.warning(f"Could not set default user commands: {e}")

    for admin_id in ADMINS:
        if admin_id:
            try:
                await bot.set_bot_commands(ADMIN_BOT_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
                logger.info(f"[Commands] Admin commands configured for ID {admin_id}")
            except Exception as e:
                logger.debug(f"Could not set admin commands for {admin_id}: {e}")


# Define aiohttp routes for 24/7 web service & Render health check
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({
        "status": "online",
        "bot": "Ultimate Video Downloader Bot",
        "message": "Bot is running 24/7"
    })

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app


# =========================================================================
# User Info & Membership Commands
# =========================================================================

@bot.on_message(filters.command(["start"]))
async def start_handler(bot: Client, m: Message):
    user_id = m.from_user.id
    is_adm = is_admin(user_id)

    # Register/update user in database
    db.get_user(
        user_id=user_id,
        first_name=m.from_user.first_name or "",
        username=m.from_user.username or ""
    )

    if is_adm:
        # Dynamically set admin menu for this admin chat in case they just launched bot
        try:
            await bot.set_bot_commands(ADMIN_BOT_COMMANDS, scope=BotCommandScopeChat(chat_id=user_id))
        except Exception:
            pass

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ Classplus (/cp)", callback_data="cp_help"),
                InlineKeyboardButton("📑 Batch (.txt)", callback_data="batch_help")
            ],
            [
                InlineKeyboardButton("💎 My Plan (/myplan)", callback_data="my_plan"),
                InlineKeyboardButton("📖 Help & Guide", callback_data="full_help")
            ],
            [
                InlineKeyboardButton("👑 Paid Members (/paidusers)", callback_data="admin_paidusers"),
                InlineKeyboardButton("🛡️ Admin Commands", callback_data="admin_help")
            ]
        ])
        await m.reply_text(Ashu.ADMIN_START_TEXT, reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ Classplus (/cp)", callback_data="cp_help"),
                InlineKeyboardButton("📑 Batch (.txt)", callback_data="batch_help")
            ],
            [
                InlineKeyboardButton("💎 My Plan (/myplan)", callback_data="my_plan"),
                InlineKeyboardButton("📖 Help & Guide", callback_data="full_help")
            ]
        ])
        await m.reply_text(Ashu.START_TEXT, reply_markup=keyboard)


@bot.on_message(filters.command(["help"]))
async def help_handler(bot: Client, m: Message):
    if is_admin(m.from_user.id):
        await m.reply_text(Ashu.ADMIN_HELP_TEXT)
    else:
        await m.reply_text(Ashu.USER_HELP_TEXT)


@bot.on_callback_query()
async def callback_handler(bot: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    is_adm = is_admin(user_id)

    if data == "cp_help":
        await query.answer()
        await query.message.reply_text(
            "⚡ **Classplus Video Downloader (/cp)**\n\n"
            "• Use `/cp` command to launch the Classplus downloader.\n"
            "• Enter your `x-access-token` (or send `no` if course/video is public).\n"
            "• Provide any Classplus video link or `contentHashId`.\n"
            "• The bot decrypts Widevine DRM automatically and uploads the video!"
        )
    elif data == "batch_help":
        await query.answer()
        await query.message.reply_text(
            "📑 **Batch .txt Downloader (/upload)**\n\n"
            "• Use `/upload` or directly send a `.txt` file into this chat.\n"
            "• Supported line formats in your `.txt` file:\n"
            "  `Title 1 : https://link1.m3u8`\n"
            "  `Title 2 : https://link2.mpd`\n"
            "  `https://link3.mp4`\n"
            "• Bot will sequentially download and upload every video to Telegram!"
        )
    elif data == "my_plan":
        await query.answer()
        u = db.get_user(user_id)
        is_pd = u.get("is_paid", False)
        used = int(u.get("downloads_used", 0))
        if is_adm:
            txt = "👑 **Plan:** Admin / Owner (Unlimited Access)\n⏳ **Validity:** Permanent (Lifetime)"
        elif is_pd:
            _, exp_t, _ = db.get_expiry_info(u.get("expiry_date", ""))
            txt = f"⭐ **Plan:** Paid / Premium Member\n⏳ **Validity:** {exp_t}\n📊 **Downloads:** Unlimited"
        else:
            rem = max(0, FREE_LIMIT - used)
            txt = f"🆓 **Plan:** Free Tier\n📊 **Used:** `{used} / {FREE_LIMIT}` ({rem} free downloads left)\n💳 Contact Admin for Unlimited Membership!"
        await query.message.reply_text(f"👤 **Account Status**\n\n🆔 User ID: `{user_id}`\n{txt}")
    elif data == "full_help":
        await query.answer()
        if is_adm:
            await query.message.reply_text(Ashu.ADMIN_HELP_TEXT)
        else:
            await query.message.reply_text(Ashu.USER_HELP_TEXT)
    elif data == "admin_paidusers":
        if not is_adm:
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        await query.answer()
        users = db.get_all_paid_users()
        if not users:
            await query.message.reply_text("📋 **No active paid users in database.**")
            return
        lines = ["👑 **Active Paid Members:**\n"]
        for u in users:
            _, exp_t, _ = db.get_expiry_info(u.get("expiry_date", ""))
            lines.append(f"• `{u['user_id']}` (@{u.get('username') or 'N/A'}) - {exp_t}")
        await query.message.reply_text("\n".join(lines))
    elif data == "admin_help":
        if not is_adm:
            await query.answer("⛔ Admin only!", show_alert=True)
            return
        await query.answer()
        await query.message.reply_text(
            "👑 **Admin Control Commands:**\n\n"
            "• `/addpaid <user_id> [days]` - Grant paid membership (e.g. `/addpaid 123456789 30`)\n"
            "• `/rempaid <user_id>` - Remove paid membership\n"
            "• `/resetlimit <user_id>` - Reset user download counter back to 0\n"
            "• `/status <user_id>` - Inspect user stats & expiry date\n"
            "• `/paidusers` - View all active paid members\n"
            "• `/stop` - Restart the bot process\n\n"
            "💡 *Tip: You can also reply to any user's message with `/addpaid 30` or `/status`!*"
        )
    else:
        await query.answer()


@bot.on_message(filters.command(["myplan", "plan"]))
async def myplan_handler(bot: Client, m: Message):
    """Displays current subscription status, downloads used, and remaining free quota."""
    user_id = m.from_user.id
    is_adm = is_admin(user_id)
    u = db.get_user(user_id, m.from_user.first_name or "", m.from_user.username or "")
    is_pd = u.get("is_paid", False)
    used = int(u.get("downloads_used", 0))

    if is_adm:
        plan_name = "👑 **Admin / Owner** (Unlimited Access)"
        validity_text = "♾️ **Permanent (Lifetime)**"
        quota_text = "♾️ **Unlimited**"
    elif is_pd:
        plan_name = "⭐ **Paid / Premium Member**"
        _, exp_text, _ = db.get_expiry_info(u.get("expiry_date", ""))
        validity_text = exp_text
        quota_text = "♾️ **Unlimited**"
    else:
        plan_name = "🆓 **Free Plan**"
        validity_text = "N/A"
        remaining = max(0, FREE_LIMIT - used)
        quota_text = f"`{used} / {FREE_LIMIT}` ({remaining} free downloads remaining)"

    msg = (
        f"👤 **Account Subscription Details**\n\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"📛 **Name:** {m.from_user.first_name}\n"
        f"💎 **Plan:** {plan_name}\n"
        f"⏳ **Validity:** {validity_text}\n"
        f"📊 **Downloads:** {quota_text}\n"
    )

    if not (is_adm or is_pd):
        msg += (
            f"\n⚠️ *Free limit is {FREE_LIMIT} videos.*\n"
            f"💳 **Want Unlimited Downloads?** Contact Admin to purchase Paid Membership!"
        )

    await m.reply_text(msg)


# =========================================================================
# Admin Management Commands
# =========================================================================

def clean_num_arg(val: str) -> str:
    """Strips brackets, braces, and non-digit wrappers like {123}, (30), <123>, @username, 30days."""
    if not val:
        return ""
    cleaned = val.strip().strip("{}()[]<>,@:; \t\n")
    for suffix in ["days", "day", "d"]:
        if cleaned.lower().endswith(suffix) and len(cleaned) > len(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
            break
    return cleaned


@bot.on_message(filters.command(["addpaid", "addpremium", "add"]))
async def add_paid_handler(bot: Client, m: Message):
    """Admin command: /addpaid {user tg id} (days count numeric) or reply to user with /addpaid [days]"""
    if not is_admin(m.from_user.id):
        await m.reply_text("⛔ **You are not authorized to use admin commands.**")
        return

    parts = m.text.split()
    target_id = None
    days = 30

    if m.reply_to_message and m.reply_to_message.from_user:
        target_id = m.reply_to_message.from_user.id
        if len(parts) >= 2:
            clean_days = clean_num_arg(parts[1])
            if clean_days.isdigit():
                days = int(clean_days)
    else:
        if len(parts) >= 2:
            clean_id = clean_num_arg(parts[1])
            if clean_id.isdigit():
                target_id = int(clean_id)
            if len(parts) >= 3:
                clean_days = clean_num_arg(parts[2])
                if clean_days.isdigit():
                    days = int(clean_days)

    if not target_id:
        await m.reply_text(
            "⚠️ **Usage:** `/addpaid {user tg id} (days count numeric)`\n\n"
            "📌 **Examples:**\n"
            "• `/addpaid 123456789 30` *(For 30 Days)*\n"
            "• `/addpaid 123456789 7` *(For 7 Days)*\n"
            "• `/addpaid 123456789 365` *(For 1 Year)*\n"
            "• `/addpaid 123456789` *(Default: 30 Days)*\n"
            "• Or **reply to any user's message:** `/addpaid 30`"
        )
        return

    days = max(1, days)
    success, expiry_str = db.add_paid_user(target_id, days=days)
    if success:
        await m.reply_text(
            f"✅ **Paid Membership Activated!**\n\n"
            f"👤 **User ID:** `{target_id}`\n"
            f"⏳ **Duration Added:** `{days} Days`\n"
            f"📅 **Expiry Date:** `{expiry_str} UTC`\n"
            f"⚡ **Status:** Unlimited Downloads Allowed"
        )

        # Notify the user directly if possible
        try:
            await bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎉 **Congratulations! Your account has been upgraded to Paid Membership!**\n\n"
                    f"⏳ **Validity Added:** `{days} Days`\n"
                    f"📅 **Valid Until:** `{expiry_str} UTC`\n"
                    f"⚡ You now have **Unlimited Video & Batch Downloads**!"
                )
            )
        except Exception:
            pass
    else:
        await m.reply_text("❌ **Failed to update user status.**")


@bot.on_message(filters.command(["rempaid", "rempremium", "remove"]))
async def rem_paid_handler(bot: Client, m: Message):
    """Admin command: /rempaid <user_id> removes paid membership."""
    if not is_admin(m.from_user.id):
        await m.reply_text("⛔ **You are not authorized to use admin commands.**")
        return

    parts = m.text.split()
    target_id = None
    if m.reply_to_message and m.reply_to_message.from_user:
        target_id = m.reply_to_message.from_user.id
    elif len(parts) >= 2:
        clean_id = clean_num_arg(parts[1])
        if clean_id.isdigit():
            target_id = int(clean_id)

    if not target_id:
        await m.reply_text("⚠️ **Usage:** `/rempaid <user_id>`\nExample: `/rempaid 123456789` (or reply with `/rempaid`)")
        return

    db.remove_paid_user(target_id)
    await m.reply_text(f"❌ **User `{target_id}` has been removed from Paid Membership.**")


@bot.on_message(filters.command(["resetlimit", "reset"]))
async def reset_limit_handler(bot: Client, m: Message):
    """Admin command: /resetlimit <user_id> resets download count to 0."""
    if not is_admin(m.from_user.id):
        await m.reply_text("⛔ **You are not authorized to use admin commands.**")
        return

    parts = m.text.split()
    target_id = None
    if m.reply_to_message and m.reply_to_message.from_user:
        target_id = m.reply_to_message.from_user.id
    elif len(parts) >= 2:
        clean_id = clean_num_arg(parts[1])
        if clean_id.isdigit():
            target_id = int(clean_id)

    if not target_id:
        await m.reply_text("⚠️ **Usage:** `/resetlimit <user_id>`\nExample: `/resetlimit 123456789` (or reply with `/resetlimit`)")
        return

    db.reset_user_limit(target_id)
    await m.reply_text(f"🔄 **User `{target_id}` download count has been reset to 0.**")


@bot.on_message(filters.command(["status", "user"]))
async def status_user_handler(bot: Client, m: Message):
    """Admin command: /status <user_id> checks details and validity of any user."""
    if not is_admin(m.from_user.id):
        await m.reply_text("⛔ **You are not authorized to use admin commands.**")
        return

    parts = m.text.split()
    target_id = None
    if m.reply_to_message and m.reply_to_message.from_user:
        target_id = m.reply_to_message.from_user.id
    elif len(parts) >= 2:
        clean_id = clean_num_arg(parts[1])
        if clean_id.isdigit():
            target_id = int(clean_id)

    if not target_id:
        await m.reply_text("⚠️ **Usage:** `/status <user_id>` (or reply to user with `/status`)")
        return

    u = db.get_user(target_id)
    is_pd = u.get("is_paid", False)
    used = u.get("downloads_used", 0)
    status_str = "⭐ Paid Member" if is_pd else "🆓 Free User"

    if is_pd:
        _, exp_text, _ = db.get_expiry_info(u.get("expiry_date", ""))
        validity_line = f"⏳ **Validity:** {exp_text}\n"
    else:
        validity_line = "⏳ **Validity:** Free Tier\n"

    await m.reply_text(
        f"📊 **User Details for `{target_id}`:**\n\n"
        f"📛 **Name:** {u.get('first_name', 'N/A')}\n"
        f"🔗 **Username:** @{u.get('username', 'N/A')}\n"
        f"💎 **Plan:** {status_str}\n"
        f"{validity_line}"
        f"📥 **Downloads Used:** `{used} / {FREE_LIMIT}`\n"
        f"🕒 **Last Active:** `{u.get('updated_at', 'N/A')}`"
    )


@bot.on_message(filters.command(["paidusers", "users"]))
async def list_paid_users_handler(bot: Client, m: Message):
    """Admin command: /paidusers lists all active paid members with expiry."""
    if not is_admin(m.from_user.id):
        await m.reply_text("⛔ **You are not authorized to use admin commands.**")
        return

    users = db.get_all_paid_users()
    if not users:
        await m.reply_text("📋 **No active paid users found in the database.**")
        return

    msg = f"🌟 **Total Active Paid Members ({len(users)}):**\n\n"
    for idx, u in enumerate(users, 1):
        name = u.get("first_name") or "User"
        user_id = u["user_id"]
        used = u["downloads_used"]
        _, exp_text, days_left = db.get_expiry_info(u.get("expiry_date", ""))
        msg += f"{idx}. `{user_id}` — {name} | DLs: `{used}` | Left: `{days_left}d`\n"
    await m.reply_text(msg)


@bot.on_message(filters.command("stop"))
async def restart_handler(_, m: Message):
    await m.reply_text("♦ **Bot is restarting...**", quote=True)
    os.execl(sys.executable, sys.executable, *sys.argv)


# =========================================================================
# Core Downloader & Video Processor
# =========================================================================

async def process_single_video(
    bot: Client,
    m: Message,
    raw_url: str,
    raw_name: str,
    raw_q: str,
    token: str = "no",
    thumb: str = "no",
    caption_extra: str = ""
):
    """
    Core downloader & uploader for any single stream or video link:
    Enforces membership & free limits, and downloads Classplus DRM, PW, YouTube, etc.
    """
    user_id = m.from_user.id

    # 1. Check membership access
    allowed, rem, msg = db.check_access(user_id, count=1)
    if not allowed:
        await m.reply_text(msg)
        return

    status_msg = await m.reply_text("🔄 **Analyzing URL and stream configuration...**")
    
    clean_url, manual_keys = helper.extract_keys_from_url_string(raw_url)
    resolved_url = clean_url
    cp_keys = list(manual_keys)
    media_type = "Direct Stream / Video"

    # 1. Google Drive handling
    if "drive.google.com" in resolved_url:
        resolved_url = resolved_url.replace("file/d/", "uc?export=download&id=").replace("/view?usp=sharing", "").replace("/view", "")
        media_type = "Google Drive"

    # 2. VisionIAS handling
    elif "visionias" in resolved_url:
        media_type = "VisionIAS Stream"
        try:
            async with ClientSession() as session:
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Referer': 'http://www.visionias.in/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                async with session.get(resolved_url, headers=headers) as resp:
                    text = await resp.text()
                    m3u8_match = re.search(r'(https://[^\s"\']+playlist\.m3u8[^\s"\']*)', text)
                    if m3u8_match:
                        resolved_url = m3u8_match.group(1)
        except Exception as e:
            logger.warning(f"VisionIAS playlist extraction error: {e}")

    # 2.5. ClassX (Google Edge Cache Signed Streams)
    elif is_classx_url(resolved_url):
        await status_msg.edit("⚡ **Resolving ClassX Google Edge Cache stream & headers...**")
        cx_res = resolve_classx_url(resolved_url, token=token, resolution=raw_q)
        if cx_res["success"]:
            resolved_url = cx_res["url"]
            media_type = cx_res.get("media_type", "ClassX Stream")

    # 3. Classplus / contentHashId handling
    elif is_classplus_url(resolved_url) or 'contenthashid' in resolved_url.lower() or 'contenthashidl' in resolved_url.lower() or extract_content_id(resolved_url):
        await status_msg.edit("🔑 **Signing Classplus URL and resolving DRM keys...**")
        sign_res = sign_classplus_url(resolved_url, token=token)
        if not sign_res["success"]:
            await status_msg.edit(f"❌ **Classplus API Signing Failed:**\n`{sign_res.get('error', 'Unknown error')}`")
            return
        resolved_url = sign_res["url"]
        cp_keys.extend(sign_res.get("keys", []))
        media_type = sign_res.get("media_type", "ClassPlus Video")

    # 4. PhysicsWallah (PW) handling
    elif any(x in resolved_url for x in ["d1d34p8vz63oiq", "sec1.pw.live", "pw.live", "penpencil"]):
        media_type = "PhysicsWallah (PW)"
        if token and token.lower() != "no":
            encoded_url = quote(resolved_url, safe='')
            resolved_url = f"https://anonymouspwplayer-907e62cf4891.herokuapp.com/pw?url={encoded_url}&token={token}"

    # 5. Careerwill handling
    elif '/master.mpd' in resolved_url and "cloudfront.net" in resolved_url:
        media_type = "Careerwill / CloudFront"
        cid = resolved_url.split("/")[-2]
        resolved_url = f"https://d26g5bnklkwsh4.cloudfront.net/{cid}/master.m3u8"

    # Format Name & Captions
    clean_name = re.sub(r'[\\/*?:"<>|]', '', raw_name).strip()[:65]
    if not clean_name:
        clean_name = "Video_Download"
    filename_base = f"001) {clean_name}"

    mr_suffix = f" {caption_extra}" if caption_extra and caption_extra.lower() != "default" else ""
    caption_video = f'**[ 🎥 ] Vid_ID:** 001.** {clean_name}{mr_suffix}.mkv\n✉️ **Title:** `{clean_name}`\n⚡ **Type:** `{media_type}`'
    caption_doc = f'**[ 📁 ] Doc_ID:** 001. {clean_name}{mr_suffix}\n✉️ **Title:** `{clean_name}`'

    # Handle direct PDFs / documents
    if ".pdf" in resolved_url.lower() or (urlparse(resolved_url).path.lower().endswith(('.pdf', '.epub', '.zip')) and "youtu" not in resolved_url):
        try:
            await status_msg.edit(f"📥 **Downloading Document:** `{clean_name}`...")
            ka = await helper.download(resolved_url, filename_base)
            await helper.send_doc(bot, m, caption_doc, ka, caption_doc, status_msg, 1, clean_name)
            await status_msg.delete(True)
            
            # Increment downloads if free user
            if not db.is_paid(user_id):
                new_used = db.increment_downloads(user_id, 1)
                rem_left = max(0, FREE_LIMIT - new_used)
                await m.reply_text(f"✅ **Document Uploaded!**\n📊 **Free Quota:** `{new_used} / {FREE_LIMIT}` used ({rem_left} free downloads left).")
            else:
                await m.reply_text("✅ **Document Downloaded & Uploaded Successfully!**")
            return
        except Exception as e:
            await status_msg.edit(f"❌ **Document download failed:**\n`{str(e)}`")
            return

    # Check quality formatting for yt-dlp & YouTube
    is_yt = yt_manager.is_youtube_url(resolved_url)
    if is_yt:
        ytf = yt_manager.build_yt_format_string(raw_q)
        extra_yt_flags = yt_manager.build_yt_dlp_flags(resolved_url)
        cmd = f'yt-dlp{extra_yt_flags} -f "{ytf}" --merge-output-format mp4 "{resolved_url}" -o "{filename_base}.mp4"'
    else:
        if raw_q and raw_q.lower() != "best" and raw_q.lower() != "un":
            ytf = f"b[height<={raw_q}]/bv[height<={raw_q}]+ba/b/bv+ba"
        else:
            ytf = "b/bv+ba"

        extra_headers = ""
        if is_classx_url(resolved_url):
            extra_headers = get_classx_ytdlp_args(resolved_url)
        elif is_classplus_url(resolved_url) or "classplusapp" in resolved_url or "media-cdn" in resolved_url or "hdnts=" in resolved_url or "hdntl=" in resolved_url:
            extra_headers = ' --add-header "Referer: https://web.classplusapp.com/" --add-header "Origin: https://web.classplusapp.com"'
            tok_m = re.search(r'[?&](hdnt[sl]=[^&]+)', resolved_url)
            if tok_m:
                extra_headers += f' --add-header "Cookie: {tok_m.group(1)}"'

        c_flag = f' --cookies "{yt_manager.get_cookies_path()}"' if yt_manager.has_cookies() else ""

        if "jw-prod" in resolved_url:
            cmd = f'yt-dlp{c_flag}{extra_headers} -o "{filename_base}.mp4" "{resolved_url}"'
        else:
            cmd = f'yt-dlp{c_flag}{extra_headers} -f "{ytf}" "{resolved_url}" -o "{filename_base}.mp4"'

    show_text = (
        f"❊⟱ **Downloading Stream** ⟱❊\n\n"
        f"📝 **Name:** `{clean_name}`\n"
        f"⌨ **Quality:** `{raw_q}`\n"
        f"🏷️ **Type:** `{media_type}`\n"
        f"🔑 **DRM Keys:** `{len(cp_keys)} keys detected`\n\n"
        f"🔗 **URL:** `{resolved_url[:120]}...`"
    )
    await status_msg.edit(show_text)

    # Use N_m3u8DL-RE for M3U8, MPD, DRM (with keys), ClassX, and Classplus/Testbook streams
    use_n_m3u8dl = (
        bool(cp_keys)
        or ".m3u8" in resolved_url.lower()
        or ".mpd" in resolved_url.lower()
        or is_classplus_url(resolved_url)
        or is_classx_url(resolved_url)
        or "classplusapp" in resolved_url.lower()
        or "classx" in resolved_url.lower()
        or "media-cdn" in resolved_url.lower()
        or "testbook" in resolved_url.lower()
        or "playlist" in resolved_url.lower()
    ) and "youtu" not in resolved_url.lower()

    try:
        if use_n_m3u8dl:
            res_file = await helper.download_drm_mpd(resolved_url, filename_base, keys=cp_keys, quality=raw_q)
        else:
            res_file = await helper.download_video(resolved_url, cmd, filename_base)

        await helper.send_vid(bot, m, caption_video, res_file, thumb, filename_base, status_msg)

        # Increment downloads count for free users
        if not db.is_paid(user_id):
            new_used = db.increment_downloads(user_id, 1)
            rem_left = max(0, FREE_LIMIT - new_used)
            await m.reply_text(
                f"✅ **Successfully Done!**\n\n"
                f"📊 **Free Quota:** `{new_used} / {FREE_LIMIT}` used ({rem_left} free downloads left).\n"
                f"💳 Upgrade to **Paid Membership** for unlimited downloads!"
            )
        else:
            await m.reply_text("✅ **Successfully Done!**")

    except Exception as e:
        await m.reply_text(
            f"⚠️ **Downloading Interrupted:**\n`{str(e)}`\n\n"
            f"📝 **Name:** `{clean_name}`\n"
            f"🔗 **Link:** `{resolved_url[:120]}`"
        )


@bot.on_message(filters.command(["cp", "classplus"]))
async def classplus_wizard_handler(bot: Client, m: Message):
    """Interactive wizard specifically for Classplus streams and contentHashId."""
    # Check permission first
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    # Step 1: Token
    editable = await m.reply_text(
        "**⚡ ᴄʟᴀssᴘʟᴜs ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ⚡**\n\n"
        "🔑 **Please send your Classplus Working Token (x-access-token):**\n\n"
        "*(If no token required or public video, send `no`)*"
    )
    input_token: Message = await bot.listen(editable.chat.id)
    raw_token = input_token.text.strip()
    await input_token.delete(True)

    # Step 2: Stream URL or contentHashId
    await editable.edit(
        "🔗 **Now please send Classplus Stream URL or contentHashId:**\n\n"
        "*(e.g., https://media-cdn.classplusapp.com/drm/... or raw contentHashId)*"
    )
    input_url: Message = await bot.listen(editable.chat.id)
    raw_url = input_url.text.strip()
    await input_url.delete(True)

    # Step 3: Video / Batch Name
    await editable.edit("📝 **Now please send your Video / Batch Name:**")
    input_name: Message = await bot.listen(editable.chat.id)
    raw_name = input_name.text.strip()
    await input_name.delete(True)

    # Step 4: Quality
    await editable.edit(Ashu.Q1_TEXT)
    input_q: Message = await bot.listen(editable.chat.id)
    raw_q = input_q.text.strip()
    await input_q.delete(True)

    # Step 5: Caption
    await editable.edit(Ashu.C1_TEXT)
    input_c: Message = await bot.listen(editable.chat.id)
    raw_c = input_c.text.strip()
    await input_c.delete(True)

    # Step 6: Thumbnail
    await editable.edit(Ashu.T1_TEXT)
    input_t: Message = await bot.listen(editable.chat.id)
    raw_t = input_t.text.strip()
    await input_t.delete(True)
    await editable.delete()

    thumb = raw_t
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    await process_single_video(
        bot=bot,
        m=m,
        raw_url=raw_url,
        raw_name=raw_name,
        raw_q=raw_q,
        token=raw_token,
        thumb=thumb,
        caption_extra=raw_c
    )


@bot.on_message(filters.command(["classx", "cx"]))
async def classx_wizard_handler(bot: Client, m: Message):
    """Interactive wizard specifically for ClassX Google Edge and transcoded streams."""
    # Check permission first
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    # Step 1: ClassX URL
    editable = await m.reply_text(
        "⚡ **ᴄʟᴀssx sᴛʀᴇᴀᴍ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ** ⚡\n\n"
        "🔗 **Please send your ClassX Stream / Master M3U8 URL:**\n\n"
        "*(Supports *.classx.co.in, transcoded-videos.classx, Google Edge Cache)*\n\n"
        "*(To cancel anytime, send `/cancel`)*"
    )
    input_url: Message = await bot.listen(editable.chat.id)
    raw_url = input_url.text.strip()
    await input_url.delete(True)

    # Step 2: Token (optional)
    await editable.edit(
        "🔑 **Please send your ClassX Authorization / Bearer Token:**\n\n"
        "*(If no token required or public stream, send `no`)*"
    )
    input_token: Message = await bot.listen(editable.chat.id)
    raw_token = input_token.text.strip()
    await input_token.delete(True)

    # Step 3: Video / Batch Name
    await editable.edit("📝 **Now please send your Video / Batch Name:**")
    input_name: Message = await bot.listen(editable.chat.id)
    raw_name = input_name.text.strip()
    await input_name.delete(True)

    # Step 4: Quality
    await editable.edit(Ashu.Q1_TEXT)
    input_q: Message = await bot.listen(editable.chat.id)
    raw_q = input_q.text.strip()
    await input_q.delete(True)

    # Step 5: Caption
    await editable.edit(Ashu.C1_TEXT)
    input_c: Message = await bot.listen(editable.chat.id)
    raw_c = input_c.text.strip()
    await input_c.delete(True)

    # Step 6: Thumbnail
    await editable.edit(Ashu.T1_TEXT)
    input_t: Message = await bot.listen(editable.chat.id)
    raw_t = input_t.text.strip()
    await input_t.delete(True)
    await editable.delete()

    thumb = raw_t
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    await process_single_video(
        bot=bot,
        m=m,
        raw_url=raw_url,
        raw_name=raw_name,
        raw_q=raw_q,
        token=raw_token,
        thumb=thumb,
        caption_extra=raw_c
    )


@bot.on_message(filters.command(["extractcptxt", "cptxt", "extractcp"]))
async def extract_cp_txt_handler(bot: Client, m: Message):
    """
    Extracts complete Classplus course into .txt file with master.m3u8 and contentHashId.
    100% Free & Unlimited for all users (does not consume free limit).
    Captures token and stores it in the database via API/Cloudflare.
    """
    editable = await m.reply_text(
        "⚡ **ᴄʟᴀssᴘʟᴜs ᴄᴏᴜʀsᴇ ᴛxᴛ ᴇxᴛʀᴀᴄᴛᴏʀ** ⚡\n\n"
        "🔑 **Please send your Classplus User Token (`x-access-token`):**\n\n"
        "*(This feature is 100% Free & Unlimited for everyone!)*\n\n"
        "*(To cancel anytime, send `/cancel`)*"
    )
    input_token: Message = await bot.listen(editable.chat.id)
    raw_token = (input_token.text or "").strip()
    await input_token.delete(True)

    if raw_token.lower() in ("/cancel", "cancel"):
        await editable.edit("❌ **Extraction cancelled.**")
        return

    if len(raw_token) < 20:
        await editable.edit("⚠️ **Invalid token!** Please provide a valid Classplus `x-access-token`.")
        return

    await editable.edit("🔍 **Validating token & fetching your courses...**")

    loop = asyncio.get_event_loop()
    try:
        courses = await loop.run_in_executor(None, cp_extractor.fetch_courses, raw_token)
    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        courses = []

    # Step 2: Store token into database via API (in background)
    cp_extractor.capture_and_store_token(raw_token, courses_count=len(courses))

    if not courses:
        await editable.edit(
            "❌ **No purchased courses or batches found!**\n\n"
            "Please ensure that:\n"
            "1. Token is correct and currently active.\n"
            "2. Your account is enrolled in at least one course/batch."
        )
        return

    # Step 3: Present course list to user
    msg_lines = [f"📚 **Found {len(courses)} Courses/Batches:**\n"]
    for idx, c in enumerate(courses[:25], 1):
        c_name = c.get("name", "Untitled")
        msg_lines.append(f"**{idx}.** {c_name} `(ID: {c.get('id')})`")

    if len(courses) > 25:
        msg_lines.append(f"\n_...and {len(courses) - 25} more._")

    msg_lines.append("\n🔢 **Send the Course Number (e.g., `1`, `2`) or Course ID to extract:**\n*(Send `/cancel` to abort)*")

    await editable.edit("\n".join(msg_lines))
    input_choice: Message = await bot.listen(editable.chat.id)
    raw_choice = (input_choice.text or "").strip()
    await input_choice.delete(True)

    if raw_choice.lower() in ("/cancel", "cancel"):
        await editable.edit("❌ **Extraction cancelled.**")
        return

    # Resolve course
    selected_course = None
    if raw_choice.isdigit():
        idx_val = int(raw_choice)
        if 1 <= idx_val <= len(courses):
            selected_course = courses[idx_val - 1]
        else:
            for c in courses:
                if str(c.get("id")) == raw_choice:
                    selected_course = c
                    break

    if not selected_course:
        await editable.edit(f"❌ **Invalid selection `{raw_choice}`.** Please run `/extractcptxt` again.")
        return

    course_id = selected_course.get("id")
    course_name = selected_course.get("name", "Course")

    await editable.edit(
        f"⏳ **Extracting Course Content...**\n\n"
        f"📚 **Batch:** `{course_name}`\n"
        f"🆔 **ID:** `{course_id}`\n\n"
        f"🔄 Traversing folders, fetching live lectures & DRM hashes...\n"
        f"*(This may take 10-30 seconds depending on size)*"
    )

    try:
        filepath, filename, stats = await loop.run_in_executor(
            None, cp_extractor.generate_course_txt, raw_token, int(course_id), course_name
        )

        if not os.path.exists(filepath) or stats.get("total", 0) == 0:
            await editable.edit(f"⚠️ **No content found in course `{course_name}`.**")
            return

        await editable.edit("📤 **Uploading your extracted TXT file to Telegram...**")

        caption = (
            f"✅ **Extracted Successfully!**\n\n"
            f"📚 **Course:** `{course_name}`\n"
            f"🆔 **Course ID:** `{course_id}`\n"
            f"🎬 **Total Videos:** `{stats['videos']}` (DRM Protected: `{stats['drm']}`)\n"
            f"📄 **PDFs / Notes:** `{stats['pdfs']}`\n\n"
            f"💡 **Tip:** You can download all videos automatically by sending this file using `/upload`!"
        )

        await bot.send_document(
            chat_id=m.chat.id,
            document=filepath,
            file_name=filename,
            caption=caption
        )
        await editable.delete()

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

    except Exception as err:
        logger.error(f"Error in extractcptxt: {err}", exc_info=True)
        await editable.edit(f"❌ **Extraction failed:** `{err}`")


@bot.on_message(filters.command(["cookie", "cookies", "setcookie", "ytcookie"]))
async def cookie_handler(bot: Client, m: Message):
    """View, upload, or paste YouTube cookies (cookies.txt)."""
    st = yt_manager.get_cookies_status()
    status_str = f"✅ **ACTIVE** (`{st['lines']} cookies`, `{st['size']} bytes`, updated `{st['updated_at']}`)" if st["exists"] else "❌ **NOT SET**"

    # If user provided cookie text inline with command: /cookie <text>
    parts = m.text.split(maxsplit=1)
    if len(parts) > 1:
        raw_cookie_text = parts[1].strip()
        saved = yt_manager.save_cookies_text(raw_cookie_text)
        if saved:
            new_st = yt_manager.get_cookies_status()
            await m.reply_text(
                f"🍪 **YouTube Cookies Saved Successfully!**\n\n"
                f"📊 **Active Cookies:** `{new_st['lines']}`\n"
                f"💾 **Size:** `{new_st['size']} bytes`\n\n"
                f"✨ *Now all YouTube videos sent via `/ytdl`, `/dl`, or direct link will download without bot blocks!*"
            )
            return

    editable = await m.reply_text(
        f"🍪 **ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ᴍᴀɴᴀɢᴇʀ** 🍪\n\n"
        f"📌 **Current Status:** {status_str}\n\n"
        f"📤 **Please upload your `cookies.txt` file (as a document) or paste the cookie text directly in chat:**\n\n"
        f"💡 **How to export cookies:**\n"
        f"1. Install **'Get cookies.txt locally'** extension on Chrome / Kiwi / Firefox.\n"
        f"2. Log in to `youtube.com`.\n"
        f"3. Click the extension and export `cookies.txt`.\n"
        f"4. Send that file here!\n\n"
        f"*(Send `/cancel` to abort, or `/clearcookie` to delete current cookies)*"
    )

    input_msg: Message = await bot.listen(editable.chat.id)

    if input_msg.text and input_msg.text.strip().lower() in ("/cancel", "cancel"):
        await input_msg.delete(True)
        await editable.edit("❌ **Cookies setup cancelled.**")
        return

    saved = False
    if input_msg.document:
        downloaded = await input_msg.download()
        await input_msg.delete(True)
        saved = yt_manager.save_cookies_from_file(downloaded)
        try:
            os.remove(downloaded)
        except Exception:
            pass
    elif input_msg.text:
        cookie_text = input_msg.text.strip()
        await input_msg.delete(True)
        saved = yt_manager.save_cookies_text(cookie_text)

    if saved:
        new_st = yt_manager.get_cookies_status()
        await editable.edit(
            f"✅ **YouTube Cookies Successfully Saved & Activated!**\n\n"
            f"📊 **Active Cookies:** `{new_st['lines']}`\n"
            f"💾 **Size:** `{new_st['size']} bytes`\n"
            f"🕒 **Last Updated:** `{new_st['updated_at']}`\n\n"
            f"🎯 *All YouTube videos sent via `/ytdl`, `/dl`, or direct link will now be downloaded using your cookies!*"
        )
    else:
        await editable.edit("❌ **Failed to save cookies.** Please verify your input and try again.")


@bot.on_message(filters.command(["clearcookie", "delcookie", "remcookie"]))
async def clear_cookie_handler(bot: Client, m: Message):
    """Deletes existing YouTube cookies."""
    deleted = yt_manager.delete_cookies()
    if deleted:
        await m.reply_text("🗑️ **YouTube cookies removed successfully.**")
    else:
        await m.reply_text("ℹ️ **No active cookies file found.**")


@bot.on_message(filters.command(["ytdl", "yt"]))
async def ytdl_command_handler(bot: Client, m: Message):
    """Dedicated interactive YouTube Video Downloader command."""
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    # Check if URL was passed as argument: /ytdl <url>
    parts = m.text.split(maxsplit=1)
    raw_url = parts[1].strip() if len(parts) > 1 else ""

    c_status = "🍪 **Cookies:** `Active`" if yt_manager.has_cookies() else "⚠️ **Cookies:** `Not Set (Use /cookie to add)`"

    if not raw_url or not yt_manager.is_youtube_url(raw_url):
        editable = await m.reply_text(
            f"🎬 **ʏᴏᴜᴛᴜʙᴇ ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ** 🎬\n\n"
            f"{c_status}\n\n"
            f"🔗 **Please send the YouTube Video URL:**\n\n"
            f"*(Send `/cancel` to abort)*"
        )
        input_url: Message = await bot.listen(editable.chat.id)
        raw_url = (input_url.text or "").strip()
        await input_url.delete(True)

        if raw_url.lower() in ("/cancel", "cancel"):
            await editable.edit("❌ **Download cancelled.**")
            return

        if not yt_manager.is_youtube_url(raw_url):
            await editable.edit("❌ **Invalid YouTube URL!** Please provide a valid `youtube.com` or `youtu.be` link.")
            return
    else:
        editable = await m.reply_text(f"🎯 **YouTube Link Received!**\n`{raw_url[:80]}...`")

    # Ask for Quality
    await editable.edit(
        f"🎬 **YouTube Video:** `{raw_url[:70]}...`\n\n"
        f"{c_status}\n\n"
        f"<b>❏ SELECT QUALITY:</b>\n"
        f"➤ 𝟷𝟶𝟾𝟶ᴘ - send `1080`\n"
        f"➤ 𝟽𝟸𝟶ᴘ - send `720`\n"
        f"➤ 𝟺𝟾𝟶ᴘ - send `480`\n"
        f"➤ 𝟹𝟼𝟶ᴘ - send `360`\n"
        f"➤ ʙᴇsᴛ - send `best`"
    )
    input_q: Message = await bot.listen(editable.chat.id)
    raw_q = (input_q.text or "best").strip()
    await input_q.delete(True)

    # Ask for Title
    await editable.edit("📝 **Send Video Name (or send `default` for original YouTube title):**")
    input_name: Message = await bot.listen(editable.chat.id)
    raw_name = (input_name.text or "default").strip()
    if raw_name.lower() == "default":
        raw_name = "YouTube_Video"
    await input_name.delete(True)
    await editable.delete()

    await process_single_video(
        bot=bot,
        m=m,
        raw_url=raw_url,
        raw_name=raw_name,
        raw_q=raw_q,
        token="no",
        thumb="no",
        caption_extra="🎬 YouTube Download"
    )


async def handle_direct_link(bot: Client, m: Message, raw_url: str):
    """Handles any direct URL pasted into chat automatically without command."""
    # Check permission first
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    clean_url, _ = helper.extract_keys_from_url_string(raw_url)
    
    # Check if token is required (Classplus or PW)
    token = "no"
    editable = await m.reply_text(
        f"🎯 **Link Detected!**\n`{clean_url[:90]}...`\n\n"
        f"🔑 **Enter Working Token (Classplus / PW), or send `no`:**"
    )
    input_token: Message = await bot.listen(editable.chat.id)
    token = input_token.text.strip()
    await input_token.delete(True)

    # Ask for Quality
    await editable.edit(Ashu.Q1_TEXT)
    input_q: Message = await bot.listen(editable.chat.id)
    raw_q = input_q.text.strip()
    await input_q.delete(True)

    # Ask for Video Name
    default_title = "Video"
    try:
        path = urlparse(clean_url).path
        base = os.path.basename(path)
        default_title = os.path.splitext(base)[0] or "Video"
    except Exception:
        pass

    await editable.edit(f"📝 **Send Video Name (or send `default` for `{default_title}`):**")
    input_name: Message = await bot.listen(editable.chat.id)
    raw_name = input_name.text.strip()
    if raw_name.lower() == "default":
        raw_name = default_title
    await input_name.delete(True)

    # Ask for Caption
    await editable.edit(Ashu.C1_TEXT)
    input_c: Message = await bot.listen(editable.chat.id)
    raw_c = input_c.text.strip()
    await input_c.delete(True)

    # Ask for Thumbnail
    await editable.edit(Ashu.T1_TEXT)
    input_t: Message = await bot.listen(editable.chat.id)
    raw_t = input_t.text.strip()
    await input_t.delete(True)
    await editable.delete()

    thumb = raw_t
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    await process_single_video(
        bot=bot,
        m=m,
        raw_url=raw_url,
        raw_name=raw_name,
        raw_q=raw_q,
        token=token,
        thumb=thumb,
        caption_extra=raw_c
    )


@bot.on_message(filters.command(["dl", "download"]))
async def download_command_handler(bot: Client, m: Message):
    """Command /dl or /download <url>."""
    # Check permission first
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    parts = m.text.split(None, 1)
    if len(parts) > 1:
        raw_url = parts[1].strip()
        await handle_direct_link(bot, m, raw_url)
    else:
        editable = await m.reply_text("🔗 **Please send the video/stream URL to download:**")
        input_url: Message = await bot.listen(editable.chat.id)
        raw_url = input_url.text.strip()
        await input_url.delete(True)
        await editable.delete()
        await handle_direct_link(bot, m, raw_url)


async def handle_batch_txt(bot: Client, m: Message, file_path: str):
    """Processes a batch .txt file containing links and names."""
    user_id = m.from_user.id

    # Check permission first
    allowed, rem, err = db.check_access(user_id)
    if not allowed:
        if os.path.isfile(file_path):
            os.remove(file_path)
        await m.reply_text(err)
        return

    editable = await m.reply_text("🔍 **Analyzing .txt file...**")

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
        os.remove(file_path)
    except Exception as e:
        await editable.edit(f"❌ **Invalid file or cannot read:**\n`{e}`")
        return

    items = []
    for line in lines:
        title, url = helper.parse_txt_line(line)
        if url:
            items.append((title, url))

    if not items:
        await editable.edit("❌ **No valid links found in the .txt file!**")
        return

    # Check free user quota against batch length
    is_pd = db.is_paid(user_id)
    if not is_pd:
        if len(items) > rem:
            await m.reply_text(
                f"ℹ️ **Free User Quota Notice:**\n\n"
                f"This file has **{len(items)} links**, but you have only **{rem} free downloads remaining** (out of {FREE_LIMIT}).\n"
                f"The bot will download the first **{rem} videos**.\n\n"
                f"💳 Upgrade to **Paid Membership** for unlimited downloads!"
            )
            items = items[:rem]

    # 1. Starting Index
    await editable.edit(
        f"📋 **Found {len(items)} Links to process!**\n\n"
        f"🔢 **Send the number from where you want to start downloading:**\n"
        f"*(Default is `1`)*"
    )
    input0: Message = await bot.listen(editable.chat.id)
    raw_start = input0.text.strip()
    await input0.delete(True)
    try:
        start_idx = int(raw_start)
        if start_idx < 1 or start_idx > len(items):
            start_idx = 1
    except Exception:
        start_idx = 1

    # 2. Batch Name
    await editable.edit("📝 **Please send your Batch Name:**")
    input1: Message = await bot.listen(editable.chat.id)
    batch_name = input1.text.strip()
    await input1.delete(True)

    # 3. Quality
    await editable.edit(Ashu.Q1_TEXT)
    input2: Message = await bot.listen(editable.chat.id)
    raw_q = input2.text.strip()
    await input2.delete(True)

    # 4. Caption
    await editable.edit(Ashu.C1_TEXT)
    input3: Message = await bot.listen(editable.chat.id)
    raw_c = input3.text.strip()
    await input3.delete(True)
    mr_suffix = f" {raw_c}" if raw_c and raw_c.lower() != "default" and raw_c != "Robin" else ""

    # 5. Token for Classplus / PW
    await editable.edit("🔑 **Enter Your PW/Classplus Working Token (or send `no`):**")
    input4: Message = await bot.listen(editable.chat.id)
    working_token = input4.text.strip()
    await input4.delete(True)

    # 6. Thumbnail
    await editable.edit(Ashu.T1_TEXT)
    input6: Message = await bot.listen(editable.chat.id)
    thumb_input = input6.text.strip()
    await input6.delete(True)
    await editable.delete()

    thumb = thumb_input
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = start_idx
    success_count = 0
    fail_count = 0

    for i in range(count - 1, len(items)):
        # Check quota again before each download for free users
        if not db.is_paid(user_id):
            allowed_now, rem_now, err_now = db.check_access(user_id)
            if not allowed_now:
                await m.reply_text(
                    f"⛔ **Free Limit Reached!**\n"
                    f"You have reached your free limit of {FREE_LIMIT} videos.\n"
                    f"Batch stopped. Contact Admin to purchase Paid Membership."
                )
                break

        raw_title, raw_link = items[i]
        clean_url, manual_keys = helper.extract_keys_from_url_string(raw_link)
        url = clean_url
        cp_keys = list(manual_keys)
        media_type = "Stream / Video"

        # 1. Drive
        if "drive.google.com" in url or "file/d/" in url:
            url = url.replace("file/d/", "uc?export=download&id=").replace("/view?usp=sharing", "").replace("/view", "")
            media_type = "Google Drive"

        # 2. VisionIAS
        elif "visionias" in url:
            media_type = "VisionIAS"
            try:
                async with ClientSession() as session:
                    headers = {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Referer': 'http://www.visionias.in/',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    async with session.get(url, headers=headers) as resp:
                        text = await resp.text()
                        m3u8_m = re.search(r'(https://[^\s"\']+playlist\.m3u8[^\s"\']*)', text)
                        if m3u8_m:
                            url = m3u8_m.group(1)
            except Exception as e:
                logger.warning(f"VisionIAS playlist fetch error: {e}")

        # 3. Classplus
        elif is_classplus_url(url) or 'contenthashid' in url.lower() or 'contenthashidl' in url.lower() or extract_content_id(url):
            media_type = "Classplus"
            if working_token.lower() != "no":
                sign_res = sign_classplus_url(url, token=working_token)
                if sign_res["success"]:
                    url = sign_res["url"]
                    cp_keys.extend(sign_res.get("keys", []))
                    media_type = sign_res.get("media_type", "Classplus Video")
                else:
                    await m.reply_text(f"⚠️ **Classplus Sign Error on item {count}:** `{sign_res.get('error')}`\nSkipping: `{raw_title}`")
                    fail_count += 1
                    count += 1
                    continue
            else:
                sign_res = sign_classplus_url(url, token=None)
                if sign_res["success"]:
                    url = sign_res["url"]
                    cp_keys.extend(sign_res.get("keys", []))

        # 4. PW
        elif any(x in url for x in ["d1d34p8vz63oiq", "sec1.pw.live", "pw.live", "penpencil"]):
            media_type = "PhysicsWallah"
            if working_token.lower() != "no":
                encoded_url = quote(url, safe='')
                url = f"https://anonymouspwplayer-907e62cf4891.herokuapp.com/pw?url={encoded_url}&token={working_token}"

        # 5. Careerwill
        elif '/master.mpd' in url and "cloudfront.net" in url:
            media_type = "Careerwill"
            cid = url.split("/")[-2]
            url = f"https://d26g5bnklkwsh4.cloudfront.net/{cid}/master.m3u8"

        # 6. ClassX (Google Edge Cache & Transcoded Streams)
        elif is_classx_url(url):
            media_type = "ClassX Stream"
            cx_res = resolve_classx_url(url, token=None if working_token.lower() == "no" else working_token, resolution=raw_q)
            if cx_res.get("success"):
                url = cx_res["url"]

        clean_title = re.sub(r'[\\/*?:"<>|]', '', raw_title).strip()[:65]
        if not clean_title:
            clean_title = f"Lecture_{str(count).zfill(3)}"
        name = f"{str(count).zfill(3)}) {clean_title}"

        cc = f'**[ 🎥 ] Vid_ID:** {str(count).zfill(3)}.** {clean_title}{mr_suffix}.mkv\n✉️ **Batch:** `{batch_name}`'
        cc1 = f'**[ 📁 ] Doc_ID:** {str(count).zfill(3)}. {clean_title}{mr_suffix}\n✉️ **Batch:** `{batch_name}`'

        # Handling PDFs / Docs
        if ".pdf" in url.lower() or (urlparse(url).path.lower().endswith(('.pdf', '.epub', '.zip')) and "youtu" not in url):
            try:
                ka = await helper.download(url, name)
                await bot.send_document(chat_id=m.chat.id, document=ka, caption=cc1)
                count += 1
                success_count += 1
                if not db.is_paid(user_id):
                    db.increment_downloads(user_id, 1)
                if os.path.isfile(ka):
                    os.remove(ka)
                await asyncio.sleep(1)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                await m.reply_text(f"⚠️ **Doc Download Error ({name}):** `{e}`")
                fail_count += 1
                count += 1
                continue
            continue

        # Handling Videos (including YouTube with cookies)
        if yt_manager.is_youtube_url(url):
            ytf = yt_manager.build_yt_format_string(raw_q)
            extra_yt_flags = yt_manager.build_yt_dlp_flags(url)
            cmd = f'yt-dlp{extra_yt_flags} -f "{ytf}" --merge-output-format mp4 "{url}" -o "{name}.mp4"'
        else:
            if raw_q and raw_q.lower() != "best" and raw_q.lower() != "un":
                ytf = f"b[height<={raw_q}]/bv[height<={raw_q}]+ba/b/bv+ba"
            else:
                ytf = "b/bv+ba"

            extra_headers = ""
            if is_classx_url(url):
                extra_headers = get_classx_ytdlp_args(url)
            elif is_classplus_url(url) or "classplusapp" in url or "media-cdn" in url or "hdnts=" in url or "hdntl=" in url or "testbook" in url:
                extra_headers = ' --add-header "Referer: https://web.classplusapp.com/" --add-header "Origin: https://web.classplusapp.com"'
                tok_m = re.search(r'[?&](hdnt[sl]=[^&]+)', url)
                if tok_m:
                    extra_headers += f' --add-header "Cookie: {tok_m.group(1)}"'

            c_flag = f' --cookies "{yt_manager.get_cookies_path()}"' if yt_manager.has_cookies() else ""

            if "jw-prod" in url:
                cmd = f'yt-dlp{c_flag}{extra_headers} -o "{name}.mp4" "{url}"'
            else:
                cmd = f'yt-dlp{c_flag}{extra_headers} -f "{ytf}" "{url}" -o "{name}.mp4"'

        show_text = (
            f"❊⟱ **Downloading Batch Item [{count}/{len(items)}]** ⟱❊\n\n"
            f"📝 **Name:** `{name}`\n"
            f"⌨ **Quality:** `{raw_q}`\n"
            f"🏷️ **Type:** `{media_type}`\n"
            f"🔗 **URL:** `{url[:100]}...`"
        )
        prog = await m.reply_text(show_text)

        use_n_m3u8dl = (
            bool(cp_keys)
            or ".m3u8" in url.lower()
            or ".mpd" in url.lower()
            or is_classx_url(url)
            or is_classplus_url(url)
            or "classx" in url.lower()
            or "classplusapp" in url.lower()
            or "media-cdn" in url.lower()
            or "testbook" in url.lower()
            or "playlist" in url.lower()
        ) and "youtu" not in url.lower()

        try:
            if use_n_m3u8dl:
                res_file = await helper.download_drm_mpd(url, name, keys=cp_keys, quality=raw_q)
            else:
                res_file = await helper.download_video(url, cmd, name)

            await helper.send_vid(bot, m, cc, res_file, thumb, name, prog)
            count += 1
            success_count += 1

            # Increment downloads count for free users
            if not db.is_paid(user_id):
                db.increment_downloads(user_id, 1)

            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            try:
                await prog.delete(True)
            except Exception:
                pass
            await m.reply_text(f"⚠️ **Error on {name}:**\n`{str(e)}`\n\nContinuing with next video...")
            fail_count += 1
            count += 1
            continue

    await m.reply_text(
        f"✅ **Batch Processing Completed!**\n\n"
        f"📊 **Total Processed:** `{len(items)}`\n"
        f"✨ **Successful:** `{success_count}`\n"
        f"❌ **Failed/Skipped:** `{fail_count}`"
    )


@bot.on_message(filters.command(["upload"]))
async def upload_command_handler(bot: Client, m: Message):
    """Command /upload asking user to send .txt file."""
    # Check permission first
    allowed, rem, err = db.check_access(m.from_user.id)
    if not allowed:
        await m.reply_text(err)
        return

    editable = await m.reply_text("📂 **Please send your .txt file with video links:**")
    input_file: Message = await bot.listen(editable.chat.id)
    if not input_file.document or not input_file.document.file_name.endswith(".txt"):
        await input_file.delete(True)
        await editable.edit("❌ **Invalid file! Please upload a valid `.txt` file.**")
        return

    x = await input_file.download()
    await input_file.delete(True)
    await editable.delete()
    await handle_batch_txt(bot, m, x)


@bot.on_message(filters.document)
async def auto_document_handler(bot: Client, m: Message):
    """Automatically detects when a user uploads a .txt file (batch or cookies)!"""
    if m.caption and m.caption.startswith("/"):
        return

    file_name = (m.document.file_name or "").lower()
    if file_name.endswith(".txt"):
        # Check if user uploaded a cookies file
        if "cookie" in file_name:
            downloaded = await m.download()
            saved = yt_manager.save_cookies_from_file(downloaded)
            try:
                os.remove(downloaded)
            except Exception:
                pass

            if saved:
                st = yt_manager.get_cookies_status()
                await m.reply_text(
                    f"🍪 **YouTube Cookies File Detected & Activated!**\n\n"
                    f"📊 **File Size:** `{st['size']} bytes`\n"
                    f"📄 **Active Cookie Lines:** `{st['lines']}`\n"
                    f"🕒 **Saved At:** `{st['updated_at']}`\n\n"
                    f"✨ *All YouTube videos sent via `/ytdl`, `/dl`, or direct link will now use these cookies!*"
                )
            else:
                await m.reply_text("❌ **Could not process cookies file.** Please verify it is a valid text file.")
            return

        # Otherwise standard batch .txt
        allowed, rem, err = db.check_access(m.from_user.id)
        if not allowed:
            await m.reply_text(err)
            return

        status_msg = await m.reply_text("📄 **Detected .txt batch file! Initializing batch downloader...**")
        x = await m.download()
        await status_msg.delete(True)
        await handle_batch_txt(bot, m, x)


@bot.on_message(filters.text)
async def auto_link_handler(bot: Client, m: Message):
    """Automatically detects when a user sends any stream/video URL directly in chat!"""
    if not m.text or m.text.startswith("/"):
        return
    text = m.text.strip()
    
    # Check if text contains URL or Classplus contentHashId
    has_url = "http://" in text or "https://" in text
    is_cp_hash = (
        ("contenthashid" in text.lower() or "contenthashidl" in text.lower() or extract_content_id(text))
        and len(text) > 10
    )

    if has_url or is_cp_hash:
        await handle_direct_link(bot, m, text)
    else:
        await m.reply_text(
            "👋 **Hi! Send me any Video/Stream URL or upload a `.txt` file to start downloading!**\n\n"
            "Use `/myplan` to check your membership status, or `/help` for instructions."
        )


async def main():
    if WEBHOOK:
        app = await web_server()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        print(f"[Web Server] Started HTTP server on port {PORT} for Render uptime")


if __name__ == "__main__":
    print("""
    ========================================================
       🚀 ULTIMATE VIDEO & STREAM DOWNLOADER BOT STARTED 🚀
       Supported: YouTube, Classplus DRM, PW, VisionIAS,
                  Careerwill, M3U8, MPD, MP4, Batch .txt
       Auth: Built-in 5 Free Downloads limit + Paid Tier
    ========================================================
    """)

    async def start_bot():
        await bot.start()
        print("[Telegram Bot] Connected to Telegram API successfully!")
        await setup_bot_commands()

    async def start_web():
        await main()

    loop = asyncio.get_event_loop()
    try:
        loop.create_task(start_bot())
        loop.create_task(start_web())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()
