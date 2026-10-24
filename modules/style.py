class Ashu(object):
  
    # User-facing welcome text (Only user commands)
    START_TEXT = """✨ **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴜʟᴛɪᴍᴀᴛᴇ ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ** ✨

I can download and stream almost **ANY** video or stream link, including:
🎬 **Social & Direct:** YouTube, M3U8 (HLS), MPD (DASH), Direct MP4/MKV, Google Drive
📚 **EdTech Platforms:** Classplus (DRM, NDRM & Akamai), ClassX (Google Edge Cache), PhysicsWallah (PW), Careerwill, VisionIAS, AppX
📑 **Batch Downloads:** Process 100+ links sequentially from any `.txt` file!

✦ **Available Commands:**
• `/cookie` - Set / upload YouTube `cookies.txt` (bypasses bot blocks!)
• `/ytdl` - YouTube video downloader (uses saved cookies)
• `/extractcptxt` - Extract full Classplus course to `.txt` (Free & Unlimited!)
• `/myplan` - Check subscription status & remaining downloads
• `/dl` - Single video / stream downloader
• `/upload` - Batch download wizard from `.txt`
• `/cp` - Classplus DRM/Non-DRM downloader
• `/classx` - ClassX Google Edge stream downloader
• `/help` - Complete guide & instructions

✦ **Quick Usage:**
1️⃣ **YouTube:** Use `/cookie` to save cookies once, then paste any YouTube link!
2️⃣ **Extract CP Course:** Type `/extractcptxt`, send token, and get `.txt` file!
3️⃣ **ClassX Stream:** Type `/classx` or paste ClassX link!
4️⃣ **Direct URL:** Just paste any video link into chat!
5️⃣ **Batch .txt:** Upload any text file to start downloading."""

    # Admin-facing welcome text (Shows User Commands + Full Admin Control Panel)
    ADMIN_START_TEXT = """✨ **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴜʟᴛɪᴍᴀᴛᴇ ᴠɪᴅᴇᴏ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ** ✨
👑 **Logged in as:** `ADMIN / OWNER`

I can download and stream almost **ANY** video or stream link:
🎬 **Social & Direct:** YouTube, M3U8, MPD (DASH), Direct MP4/MKV, Google Drive
📚 **EdTech Platforms:** Classplus DRM, ClassX Google Edge, PhysicsWallah, Careerwill, VisionIAS
📑 **Batch Downloads:** Process 100+ links sequentially from `.txt`!

✦ **User Commands:**
• `/cookie` - Set / view YouTube `cookies.txt`
• `/ytdl` - YouTube video downloader
• `/extractcptxt` - Extract CP courses to `.txt` (Free & Unlimited)
• `/myplan` - Subscription & download stats
• `/dl` - Single link downloader
• `/upload` - Batch `.txt` downloader
• `/cp` - Classplus DRM wizard
• `/classx` - ClassX stream downloader
• `/help` - Help guide

👑 **Admin Control Panel:**
• `/addpaid <user_id> [days]` - Grant paid membership (e.g. `/addpaid 123456789 30`)
• `/rempaid <user_id>` - Remove paid membership
• `/resetlimit <user_id>` - Reset user download count back to 0
• `/status <user_id>` - Inspect user subscription & activity
• `/paidusers` - View all active paid members
• `/stop` - Restart the bot process"""

    # User Help Text
    HELP_TEXT = """📖 **ᴜʟᴛɪᴍᴀᴛᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ɢᴜɪᴅᴇ**

🔹 **Commands Available:**
• `/cookie` - Set or view YouTube `cookies.txt` (bypasses 403 / bot detection)
• `/clearcookie` - Delete saved YouTube cookies
• `/ytdl` (or `/yt`) - Dedicated YouTube video downloader
• `/extractcptxt` (or `/cptxt`) - Extract Classplus course to `.txt` (100% Free & Unlimited!)
• `/myplan` - Check your membership plan & downloads quota
• `/dl` - Download a single video / stream link
• `/upload` - Batch download links from a `.txt` file
• `/cp` - Classplus DRM/NDRM video downloader
• `/classx` (or `/cx`) - ClassX Google Edge Cache stream downloader
• `/help` - Show this guide

🔹 **Free vs Paid Membership:**
• **Free Users:** Get **5 free video downloads**.
• **Paid Members:** Enjoy **Unlimited downloads** with no limits!
• Check your membership status anytime using `/myplan`.
• Contact Admin to purchase Paid Membership.

🔹 **Direct Link Download:**
Just send any video URL directly in chat! Supported:
• YouTube: `https://youtu.be/...`
• ClassX: `https://*.classx.co.in/...` or `https://transcoded-videos.classx.co.in/...`
• Classplus: Stream link, `contentHashId`, or testbook link
• Direct M3U8: `https://.../index.m3u8`
• Direct MPD / DRM: `https://.../manifest.mpd` (with auto or manual keys)
• PhysicsWallah (PW): `https://sec1.pw.live/...`
• Google Drive: `https://drive.google.com/file/d/...`
• Direct Videos & PDFs: `https://.../file.mp4` / `file.pdf`

🔹 **Batch .txt File Format:**
You can send a `.txt` file with lines formatted as:
`Title 1 : https://link1.m3u8`
`Title 2 : https://link2.mpd`
`Title 3 : https://subdomain.classx.co.in/stream/master.m3u8`
`https://link4.mp4`

🔹 **ClassX Downloads:**
Use `/classx` or paste ClassX link. The bot automatically generates required headers (`Referer`, `Origin`, and Google Edge tokens) so videos download cleanly without 403 Forbidden errors.

🔹 **Classplus DRM:**
Use `/cp` or send a Classplus link. Provide your `x-access-token` (or `no` if public or using default bot token). Akamai tokens and DRM keys are derived automatically.

🔹 **DRM MPD with Manual Keys:**
If you already have Widevine keys, you can send:
`https://.../manifest.mpd * <kid>:<key>`
or `https://.../manifest.mpd --key <kid>:<key>`"""

    USER_HELP_TEXT = HELP_TEXT

    # Admin Help Text with Admin Table appended
    ADMIN_HELP_TEXT = HELP_TEXT + """

👑 **ADMIN COMMANDS REFERENCE:**
• `/addpaid <user_id> [days]` - Add paid access (e.g. `/addpaid 123456789 30`)
• `/rempaid <user_id>` - Remove paid membership
• `/resetlimit <user_id>` - Reset user download count back to 0
• `/status <user_id>` - Check any user's stats & expiry date
• `/paidusers` - List all active paid members
• `/stop` - Restart the bot process"""

    Q1_TEXT = """<b>
❏ sᴇɴᴅ ǫᴜᴀʟɪᴛʏ ʏᴏᴜ ᴡᴀɴᴛ
➤ 𝟷𝟺𝟺ᴘ - sᴇɴᴅ `144`
➤ 𝟸𝟺𝟶ᴘ - sᴇɴᴅ `240`
➤ 𝟹𝟼𝟶ᴘ - sᴇɴᴅ `360`
➤ 𝟺𝟾𝟶ᴘ - sᴇɴᴅ `480`
➤ 𝟽𝟸𝟶ᴘ - sᴇɴᴅ `720`
➤ 𝟷𝟶𝟾𝟶ᴘ - sᴇɴᴅ `1080`
➤ ʙᴇsᴛ - sᴇɴᴅ `best`</b>"""

    C1_TEXT = """<b>
✏️ ɴᴏᴡ ᴇɴᴛᴇʀ ᴀ ᴄᴀᴘᴛɪᴏɴ ᴛᴏ ᴀᴅᴅ ᴄᴀᴘᴛɪᴏɴ ᴏɴ ʏᴏᴜʀ ᴜᴘʟᴏᴀᴅᴇᴅ ғɪʟᴇ
(ᴏʀ sᴇɴᴅ `default` ғᴏʀ sᴛᴀɴᴅᴀʀᴅ ᴄᴀᴘᴛɪᴏɴ)</b>"""

    T1_TEXT = """<b>🌄 ɴᴏᴡ sᴇɴᴅ ᴛʜᴇ ᴛʜᴜᴍʙ ᴜʀʟ
Eg » `https://graph.org/file/698599feb76711fa080f6.jpg`

ᴏʀ ɪғ ᴅᴏɴ'ᴛ ᴡᴀɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ sᴇɴᴅ = `no`

ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟ ᴜʀʟ ᴜsᴇ ᴛʜɪs ʙᴏᴛ - @FileToUrlX_Bot 
➤ sᴇɴᴅ ɪᴍᴀɢᴇ ɪɴ ʙᴏᴛ
➤ Reply `/telegraph`</b>"""
