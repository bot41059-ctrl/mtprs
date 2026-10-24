import glob
import logging
import os
import re
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET
import requests

logger = logging.getLogger("classplus")

try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    WIDEVINE_ENABLED = True
except ImportError:
    WIDEVINE_ENABLED = False


DEFAULT_CP_HEADERS = {
    'host': 'api.classplusapp.com',
    'accept-language': 'en',
    'api-version': '56',
    'app-version': '1.12.1.1',
    'build-number': '56',
    'connection': 'Keep-Alive',
    'content-type': 'application/json',
    'device-details': 'motorola_Moto G4_SDK-32',
    'device-id': 'c28d3cb16bbdac01',
    'region': 'IN',
    'user-agent': 'Mobile-Android',
    'accept-encoding': 'gzip'
}


DEFAULT_CP_TOKEN = os.environ.get(
    "CP_TOKEN", 
    os.environ.get("token_cp", "eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9r")
)


def is_classplus_url(url_or_hash: str) -> bool:
    """Checks whether the given URL or identifier is a Classplus stream or contentHashId."""
    if not url_or_hash:
        return False
    u = url_or_hash.lower().strip()
    return any(k in u for k in [
        'classplus',
        'testbook.com',
        'cpvod',
        'tencdn',
        'contenthashid',
        'contenthashidl',
        'media-cdn.classplusapp.com',
        'akamai-cdn.classplusapp.com',
        'hdnts=',
        'hdntl='
    ])


def get_classplus_headers(url: str = "") -> Dict[str, str]:
    """Generates the required HTTP headers for Classplus & Akamai CDN EdgeAuth."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://web.classplusapp.com/',
        'Origin': 'https://web.classplusapp.com',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Dest': 'empty'
    }
    m_hdnts = re.search(r'[?&](hdnt[sl]=[^&]+)', url)
    if m_hdnts:
        headers['Cookie'] = m_hdnts.group(1)
    return headers


def extract_content_id(input_str: str) -> Optional[str]:
    """
    Extracts contentHashId, contentId, or vidkey from a URL or raw hash.
    Supports formats:
    - Raw hash: '60b8d...' or 'c18e...'
    - Query params: &contentHashId=..., ?contentHashId=...
    - Query params: &contentHashIdl=..., ?contentHashIdl=...
    - Query params: &contentId=..., ?contentId=...
    - Query params: vidKey=...
    - Path patterns: /lc/{vidKey}/
    """
    if not input_str:
        return None
    s = input_str.strip()
    if "://" not in s and "/" not in s and " " not in s and "&" not in s and "=" not in s:
        return s

    patterns = [
        r'[?&]contentHashId=([^&\s]+)',
        r'[?&]contentHashIdl=([^&\s]+)',
        r'contentHashId=([^&\s]+)',
        r'contentHashIdl=([^&\s]+)',
        r'[?&]contentId=([^&\s]+)',
        r'[?&]vidKey=([^&\s]+)',
        r'/lc/([^/&\s]+)',
        r'/([a-zA-Z0-9]{8,}(?:-[0-9]+[a-z]?)?)/',
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            return m.group(1).split('&')[0].strip()
    return None


def extract_pssh(mpd_url: str) -> Optional[str]:
    """Extracts base64 PSSH from an MPD manifest."""
    try:
        resp = requests.get(mpd_url, timeout=12)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for elem in root.iter():
            if 'ContentProtection' in elem.tag:
                scheme = elem.get('schemeIdUri', '').lower()
                if 'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed' in scheme:
                    for child in elem:
                        if 'pssh' in child.tag.lower() and child.text:
                            return child.text.strip()
    except Exception as err:
        logger.warning(f"Error parsing MPD for PSSH: {err}")
    return None


def extract_widevine_keys(pssh_b64: str, lic_url: str) -> List[str]:
    """Extracts Widevine decryption keys using available .wvd device files."""
    if not WIDEVINE_ENABLED:
        logger.warning("pywidevine is not installed or enabled.")
        return []

    search_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "WVDs", "*.wvd"),
        os.path.join(os.path.dirname(__file__), "WVDs", "*.wvd"),
        os.path.join(os.getcwd(), "WVDs", "*.wvd"),
        os.path.join(os.getcwd(), "modules", "WVDs", "*.wvd"),
        os.path.join(os.path.dirname(__file__), "..", "..", "WVDs", "*.wvd"),
        "WVDs/*.wvd",
        "modules/WVDs/*.wvd",
        "./*.wvd"
    ]
    wvd_files = []
    for pattern in search_dirs:
        found = glob.glob(pattern)
        if found:
            wvd_files.extend(found)

    if not wvd_files:
        logger.warning("No .wvd device file found in any search path.")
        return []

    device_path = os.path.abspath(wvd_files[0])
    logger.info(f"Using Widevine device: {device_path}")

    try:
        device = Device.load(device_path)
        cdm = Cdm.from_device(device)
        session_id = cdm.open()

        challenge = cdm.get_license_challenge(session_id, PSSH(pssh_b64))
        lic_resp = requests.post(
            lic_url,
            data=challenge,
            headers={
                'user-agent': 'okhttp/4.9.3',
                'content-type': 'application/octet-stream'
            },
            timeout=15
        )
        lic_resp.raise_for_status()

        cdm.parse_license(session_id, lic_resp.content)
        keys = [f"{k.kid.hex}:{k.key.hex()}" for k in cdm.get_keys(session_id) if k.type == 'CONTENT']
        cdm.close(session_id)
        logger.info(f"Successfully extracted {len(keys)} Widevine keys: {keys}")
        return keys
    except Exception as err:
        logger.warning(f"Widevine key extraction failed: {err}")
        return []


def sign_classplus_url(url_or_hash: str, token: Optional[str] = None, org_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Signs a Classplus URL or contentHashId using the Classplus API.
    Returns:
    {
        "success": bool,
        "url": str or None,
        "mpd_url": str or None,
        "lic_url": str or None,
        "keys": list of str (e.g. ['kid:key']),
        "media_type": str,
        "error": str or None,
        "raw_response": dict or None
    }
    """
    headers = DEFAULT_CP_HEADERS.copy()
    effective_token = token.strip() if (token and isinstance(token, str) and token.strip() and token.strip().lower() != "no") else DEFAULT_CP_TOKEN
    if effective_token:
        headers["x-access-token"] = effective_token
    if org_code and isinstance(org_code, str) and org_code.strip():
        headers["orgCode"] = org_code.strip()

    raw_input = url_or_hash.strip()

    # URL cleanups matching cp new
    clean_url = raw_input.replace("https://cpvod.testbook.com/", "https://media-cdn.classplusapp.com/drm/")
    clean_url = clean_url.replace("https://tencdn.classplusapp.com/", "https://media-cdn.classplusapp.com/tencent/")

    # If stream is already an authenticated/signed Akamai HLS or DRM stream
    if ".m3u8" in clean_url and any(k in clean_url for k in ["hdnts=", "hdntl=", "key="]):
        m_type = "ClassPlus Akamai (L1)" if ("key=" in clean_url and "userIds=" in clean_url) else "ClassPlus Akamai (L2)"
        return {
            "success": True,
            "url": clean_url,
            "mpd_url": None,
            "lic_url": None,
            "keys": [],
            "media_type": m_type,
            "error": None,
            "raw_response": None
        }

    content_id = extract_content_id(clean_url)
    sign_api = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url"

    candidates_params = []
    if content_id:
        candidates_params.append({"contentId": content_id, "offlineDownload": "false"})
    if clean_url.startswith("http://") or clean_url.startswith("https://"):
        candidates_params.append({"url": clean_url})
    if not candidates_params:
        candidates_params.append({"contentId": clean_url, "offlineDownload": "false"})

    last_error = "Unknown error"
    last_response = None

    for params in candidates_params:
        try:
            resp = requests.get(sign_api, params=params, headers=headers, timeout=20)
            data = resp.json()
            last_response = data

            if 'error' in data or 'Error' in data:
                last_error = data.get('error') or data.get('Error')
                continue

            signed_url = data.get("url") or (data.get("data") or {}).get("url")
            drm_urls = data.get("drmUrls") or (data.get("data") or {}).get("drmUrls")

            if signed_url:
                return {
                    "success": True,
                    "url": signed_url,
                    "mpd_url": None,
                    "lic_url": None,
                    "keys": [],
                    "media_type": "ClassPlus Signed HLS/URL",
                    "error": None,
                    "raw_response": data
                }

            if drm_urls:
                mpd_url = drm_urls.get("manifestUrl") or drm_urls.get("mpdUrl")
                lic_url = drm_urls.get("licenseUrl") or drm_urls.get("licUrl")
                keys = []
                if mpd_url and lic_url:
                    pssh = extract_pssh(mpd_url)
                    if pssh:
                        keys = extract_widevine_keys(pssh, lic_url)

                return {
                    "success": True,
                    "url": mpd_url,
                    "mpd_url": mpd_url,
                    "lic_url": lic_url,
                    "keys": keys,
                    "media_type": "ClassPlus DRM (MPD)",
                    "error": None,
                    "raw_response": data
                }

        except Exception as e:
            last_error = str(e)

    return {
        "success": False,
        "url": None,
        "mpd_url": None,
        "lic_url": None,
        "keys": [],
        "media_type": "Unknown",
        "error": last_error,
        "raw_response": last_response
    }
