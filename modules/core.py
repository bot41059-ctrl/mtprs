import os
import re
import glob
import shutil
import time
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import subprocess
import concurrent.futures
from urllib.parse import urlparse

try:
    import tgcrypto
except ImportError:
    pass

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger("core")


def duration(filename: str) -> float:
    """Returns video duration in seconds via ffprobe."""
    if not os.path.isfile(filename):
        return 0.0
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", filename
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15
        )
        return float(result.stdout.decode().strip())
    except Exception:
        return 0.0


def get_video_resolution(filename: str) -> tuple[int, int]:
    """Returns (width, height) of video file via ffprobe, default (1280, 720)."""
    if not os.path.isfile(filename):
        return 1280, 720
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", filename
        ]
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=15).decode().strip()
        parts = res.split("x")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 1280, 720


def exec(cmd):
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = process.stdout.decode()
    return output


def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        fut = list(executor.map(exec, cmds))
        return fut


async def aio(url: str, name: str) -> str:
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url: str, name: str) -> str:
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka


def parse_txt_line(line: str) -> tuple[str, str]:
    """
    Parses a single line from a batch .txt file.
    Supports formats:
      - Title : https://url...
      - Title:https://url...
      - Title | https://url...
      - https://url... (extracts filename as title)
      - https://url... Title
      - contentHashId
    """
    line = line.strip()
    if not line:
        return "", ""

    url_match = re.search(r'(https?://[^\s]+)', line)
    if url_match:
        url = url_match.group(1).strip()
        title_part = line.replace(url, '').strip()
        title_part = re.sub(r'^[ :|\-\t]+|[ :|\-\t]+$', '', title_part).strip()
        if not title_part:
            path = urlparse(url).path
            base = os.path.basename(path)
            title_part = os.path.splitext(base)[0] or "Video"
        return title_part, url
    else:
        # Check if it's a raw Classplus contentHashId or token
        clean = line.strip()
        if len(clean) > 8 and " " not in clean:
            return "Classplus_Stream", clean
        return "", ""


def extract_keys_from_url_string(text: str) -> tuple[str, list[str]]:
    """
    Checks if a URL has embedded decryption keys.
    Examples:
      - https://domain.com/manifest.mpd * 3d4a...:82bc...
      - https://domain.com/manifest.mpd --key 3d4a...:82bc...
      - https://domain.com/manifest.mpd | 3d4a...:82bc...
    """
    text = text.strip()
    keys = []
    
    # Check for * or | separator
    for sep in [" * ", " | ", " --key "]:
        if sep in text:
            parts = text.split(sep)
            url = parts[0].strip()
            for p in parts[1:]:
                # Extract any hex:hex pattern
                matches = re.findall(r'([a-fA-F0-9]{32}:[a-fA-F0-9]{32})', p)
                if matches:
                    keys.extend(matches)
                else:
                    k_clean = p.strip().strip('"').strip("'")
                    if ":" in k_clean:
                        keys.append(k_clean)
            return url, keys

    # Check for direct hex:hex key pattern anywhere after URL
    url_m = re.match(r'^(https?://[^\s]+)', text)
    if url_m:
        url = url_m.group(1).strip()
        remainder = text[len(url):]
        hex_keys = re.findall(r'([a-fA-F0-9]{32}:[a-fA-F0-9]{32})', remainder)
        if hex_keys:
            return url, hex_keys
        return url, []

    return text, []


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


def get_mp4decrypt_bin() -> str | None:
    """Finds Bento4 mp4decrypt binary on Linux/Windows/Docker."""
    candidates = [
        "/usr/local/bin/mp4decrypt",
        "/usr/bin/mp4decrypt",
        os.path.join(os.getcwd(), "bin", "mp4decrypt"),
        os.path.join(os.getcwd(), "bin", "mp4decrypt.exe"),
        os.path.join(os.getcwd(), "mp4decrypt"),
        os.path.join(os.getcwd(), "mp4decrypt.exe"),
        os.path.join(os.path.dirname(__file__), "..", "bin", "mp4decrypt"),
        os.path.join(os.path.dirname(__file__), "..", "mp4decrypt"),
        os.path.join(os.path.dirname(__file__), "..", "mp4decrypt.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            if os.name != 'nt':
                try:
                    os.chmod(c, 0o755)
                except Exception:
                    pass
            return os.path.abspath(c)
    w = shutil.which("mp4decrypt") or shutil.which("mp4decrypt.exe")
    return w


def get_n_m3u8dl_bin() -> str:
    """Finds N_m3u8DL-RE binary on Windows, Linux, and Docker, or auto-downloads if missing."""
    candidates = [
        "/usr/local/bin/N_m3u8DL-RE",
        "/usr/bin/N_m3u8DL-RE",
        os.path.join(os.getcwd(), "bin", "N_m3u8DL-RE"),
        os.path.join(os.getcwd(), "bin", "N_m3u8DL-RE.exe"),
        os.path.join(os.getcwd(), "N_m3u8DL-RE"),
        os.path.join(os.getcwd(), "N_m3u8DL-RE.exe"),
        os.path.join(os.path.dirname(__file__), "..", "bin", "N_m3u8DL-RE"),
        os.path.join(os.path.dirname(__file__), "..", "N_m3u8DL-RE"),
        os.path.join(os.path.dirname(__file__), "..", "N_m3u8DL-RE.exe"),
        os.path.join(os.path.dirname(__file__), "..", "..", "N_m3u8DL-RE.exe"),
        os.path.join(os.path.dirname(__file__), "..", "..", "N_m3u8DL-RE"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            if os.name != 'nt':
                try:
                    os.chmod(c, 0o755)
                except Exception:
                    pass
            return os.path.abspath(c)
    w = shutil.which("N_m3u8DL-RE") or shutil.which("N_m3u8DL-RE.exe")
    if w:
        return w

    # Fallback: Auto-download if not installed anywhere
    bin_dir = os.path.join(os.getcwd(), "bin")
    os.makedirs(bin_dir, exist_ok=True)

    if os.name != 'nt':
        target = os.path.join(bin_dir, "N_m3u8DL-RE")
        if not os.path.isfile(target):
            try:
                import urllib.request
                import tarfile
                print("[Auto-Installer] N_m3u8DL-RE not found on Linux. Downloading Linux x64 binary...")
                url = "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.6.0-beta/N_m3u8DL-RE_v0.6.0-beta_linux-x64_20260629.tar.gz"
                tmp_tar = os.path.join(bin_dir, "n_m3u8.tar.gz")
                urllib.request.urlretrieve(url, tmp_tar)
                with tarfile.open(tmp_tar, "r:gz") as tar:
                    tar.extractall(path=bin_dir)
                if os.path.exists(tmp_tar):
                    os.remove(tmp_tar)
                print(f"[Auto-Installer] Successfully installed N_m3u8DL-RE at {target}")
            except Exception as e:
                print(f"[Auto-Installer] Failed to download N_m3u8DL-RE: {e}")
        if os.path.isfile(target):
            try:
                os.chmod(target, 0o755)
            except Exception:
                pass
            return os.path.abspath(target)
        return "N_m3u8DL-RE"
    else:
        target = os.path.join(bin_dir, "N_m3u8DL-RE.exe")
        if not os.path.isfile(target):
            try:
                import urllib.request
                import zipfile
                print("[Auto-Installer] N_m3u8DL-RE.exe not found on Windows. Downloading Win x64 binary...")
                url = "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.6.0-beta/N_m3u8DL-RE_v0.6.0-beta_win-x64_20260629.zip"
                tmp_zip = os.path.join(bin_dir, "n_m3u8.zip")
                urllib.request.urlretrieve(url, tmp_zip)
                with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
                    zip_ref.extractall(bin_dir)
                if os.path.exists(tmp_zip):
                    os.remove(tmp_zip)
                print(f"[Auto-Installer] Successfully installed N_m3u8DL-RE.exe at {target}")
            except Exception as e:
                print(f"[Auto-Installer] Failed to download N_m3u8DL-RE.exe: {e}")
        if os.path.isfile(target):
            return os.path.abspath(target)
        return "N_m3u8DL-RE.exe"


async def download_drm_mpd(url: str, name: str, keys: list = None, quality: str = "720"):
    """
    Downloads and decrypts MPD / M3U8 stream using N_m3u8DL-RE with FFmpeg merging.
    Supports Widevine keys, resolution selection, and custom platform headers.
    """
    n_bin = get_n_m3u8dl_bin()
    url = url.strip().strip('"').strip("'")
    clean_name = re.sub(r'[\\/*?:"<>|]', '', name).strip()
    
    # Remove existing files with the same name before downloading
    for ext in [".mp4", ".mkv", ".ts"]:
        f_old = f"{clean_name}{ext}"
        if os.path.isfile(f_old):
            try:
                os.remove(f_old)
            except Exception:
                pass

    cmd_args = [
        n_bin,
        url,
        "--auto-select",
        "--save-dir", ".",
        "--save-name", clean_name,
        "-M", "format=mp4",
        "--del-after-done",
        "--thread-count", "16",
        "--download-retry-count", "5",
        "--check-segments-count", "false",
    ]

    # Pass decryption keys if available
    if keys:
        for k in keys:
            if k and isinstance(k, str) and k.strip():
                clean_k = k.strip().strip('"').strip("'")
                cmd_args.extend(["--key", clean_k])

    # Pass mp4decrypt binary path if present
    mp4dec = get_mp4decrypt_bin()
    if mp4dec:
        cmd_args.extend(["--decryption-binary-path", os.path.abspath(mp4dec)])

    # Selective quality with fallback
    if quality and str(quality).lower() != "best" and str(quality).lower() != "un":
        digits = re.findall(r'\d+', str(quality))
        if digits:
            q_val = digits[0]
            cmd_args.extend(["-sv", f'res="{q_val}*|.*":for=best', "-sa", "for=best"])
        else:
            cmd_args.extend(["-sv", "for=best", "-sa", "for=best"])
    else:
        cmd_args.extend(["-sv", "for=best", "-sa", "for=best"])

    # Headers for ClassX streams
    if any(k in url.lower() for k in ["classx.co.in", "transcoded-videos.classx", "classx"]):
        try:
            from classx import get_classx_n_m3u8dl_args
            cmd_args.extend(get_classx_n_m3u8dl_args(url))
        except Exception:
            m_tenant = re.search(r'/videos/([a-zA-Z0-9_\-]+?)(?:-data)?/', url)
            t_name = m_tenant.group(1) if m_tenant else "transcoded-videos"
            cmd_args.extend([
                "-H", f"Referer: https://{t_name}.classx.co.in/",
                "-H", f"Origin: https://{t_name}.classx.co.in",
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ])
    # Headers for ClassPlus / Testbook / Akamai CDN
    elif any(x in url.lower() for x in ["classplus", "media-cdn", "testbook", "akamai", "hdnts=", "hdntl="]):
        cmd_args.extend([
            "-H", "Referer: https://web.classplusapp.com/",
            "-H", "Origin: https://web.classplusapp.com",
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ])
        tok_m = re.search(r'[?&](hdnt[sl]=[^&]+)', url)
        if tok_m:
            cmd_args.extend(["-H", f"Cookie: {tok_m.group(1)}"])
    else:
        cmd_args.extend([
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ])

    ffm = shutil.which("ffmpeg") or ("ffmpeg.exe" if os.path.isfile("ffmpeg.exe") else None)
    if ffm:
        cmd_args.extend(["--ffmpeg-binary-path", os.path.abspath(ffm)])

    print(f"[N_m3u8DL-RE Download] Executing: {' '.join(cmd_args)}")
    logging.info(f"[N_m3u8DL-RE Download] Executing: {' '.join(cmd_args)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    stdout, _ = await proc.communicate()
    output_str = stdout.decode(errors='ignore') if stdout else ""

    # Check for expected output file
    for ext in [".mp4", ".mkv", ".ts"]:
        f = f"{clean_name}{ext}"
        if os.path.isfile(f) and os.path.getsize(f) > 1000:
            return f

    escaped_name = glob.escape(clean_name)
    matches = glob.glob(f"{escaped_name}*.mp4") or glob.glob(f"{escaped_name}*.mkv")
    for m in matches:
        if os.path.isfile(m) and os.path.getsize(m) > 1000 and not m.endswith(".jpg"):
            return m

    raise Exception(f"N_m3u8DL-RE download failed or output file not found.\n{output_str[-400:]}")


failed_counter = 0

async def download_video(url, cmd, name):
    """Downloads video using yt-dlp with aria2c or native multi-fragment acceleration."""
    global failed_counter
    is_yt = any(k in (url or "").lower() for k in ["youtube.com", "youtu.be", "youtube-nocookie"])
    is_hls = any(k in (url or "").lower() for k in [".m3u8", "hdnts=", "hdntl=", "classplus", "classx", "azure/media"])

    if is_yt:
        download_cmd = f'{cmd} -R 25 --fragment-retries 25 --concurrent-fragments 4'
    elif is_hls:
        # 🚀 High-speed parallel fragment downloading for ClassPlus / Akamai / HLS (16 threads)
        download_cmd = f'{cmd} -R 25 --fragment-retries 25 --concurrent-fragments 16 --buffersize 16M'
    else:
        download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    print(download_cmd)
    logging.info(download_cmd)
    
    # Run command; if it fails, fall back to high-speed multi-fragment yt-dlp
    k = subprocess.run(download_cmd, shell=True)
    if k.returncode != 0:
        fallback_cmd = f'{cmd} -R 25 --fragment-retries 25 --concurrent-fragments 16 --buffersize 16M'
        print(f"[Fallback yt-dlp]: {fallback_cmd}")
        k = subprocess.run(fallback_cmd, shell=True)

    if "visionias" in cmd and k.returncode != 0 and failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        await download_video(url, cmd, name)
    failed_counter = 0

    clean_name = name.replace('"', '').replace("'", "").strip()
    for ext in ["", ".mp4", ".mkv", ".webm", ".mp4.webm"]:
        cand = f"{clean_name}{ext}" if not clean_name.endswith(ext) or not ext else clean_name
        if os.path.isfile(cand) and os.path.getsize(cand) > 1000:
            return cand

    name_no_ext = os.path.splitext(clean_name)[0]
    for ext in [".mp4", ".mkv", ".webm", ".mp4.webm"]:
        cand = f"{name_no_ext}{ext}"
        if os.path.isfile(cand) and os.path.getsize(cand) > 1000:
            return cand

    matches = glob.glob(f"{name_no_ext}*")
    for m in matches:
        if os.path.isfile(m) and os.path.getsize(m) > 1000 and not m.endswith(".jpg"):
            return m

    raise Exception(f"Video download failed or output file not found for: {name}")


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name):
    reply = await m.reply_text(f"Uploading » `{name}`")
    time.sleep(1)
    await m.reply_document(ka, caption=cc1)
    await reply.delete(True)
    if os.path.isfile(ka):
        try:
            os.remove(ka)
        except Exception:
            pass


async def send_vid(bot: Client, m: Message, cc, filename, thumb, name, prog):
    """Sends video to Telegram with duration, resolution, thumbnail, and live progress bar."""
    if not os.path.isfile(filename):
        raise Exception(f"Video file to upload does not exist: {filename}")

    dur = int(duration(filename))
    width, height = get_video_resolution(filename)

    # Frame capture: 5s if short, 60s if longer
    ss_time = "00:00:05" if dur < 60 else "00:01:00"
    subprocess.run(
        f'ffmpeg -y -i "{filename}" -ss {ss_time} -vframes 1 "{filename}.jpg"',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        await prog.delete(True)
    except Exception:
        pass

    reply = await m.reply_text(f"**⥣ Uploading ...** » `{name}`")
    try:
        if thumb == "no" or not os.path.isfile(str(thumb)):
            thumbnail = f"{filename}.jpg" if os.path.isfile(f"{filename}.jpg") else None
        else:
            thumbnail = thumb
    except Exception:
        thumbnail = None

    start_time = time.time()

    try:
        await m.reply_video(
            filename,
            caption=cc,
            supports_streaming=True,
            height=height,
            width=width,
            thumb=thumbnail,
            duration=dur,
            progress=progress_bar,
            progress_args=(reply, start_time)
        )
    except Exception:
        # Fallback to document upload if video streaming/format is rejected
        await m.reply_document(
            filename,
            caption=cc,
            thumb=thumbnail,
            progress=progress_bar,
            progress_args=(reply, start_time)
        )

    # Cleanup temp files
    if os.path.isfile(filename):
        try:
            os.remove(filename)
        except Exception:
            pass
    if os.path.isfile(f"{filename}.jpg"):
        try:
            os.remove(f"{filename}.jpg")
        except Exception:
            pass
    try:
        await reply.delete(True)
    except Exception:
        pass
