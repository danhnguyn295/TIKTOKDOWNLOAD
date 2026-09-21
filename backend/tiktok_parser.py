import re
import urllib.parse
from typing import Optional, Dict, Any, List
import httpx
import logging

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CurlAsyncSession = None
    CURL_CFFI_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok_parser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIKWM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.tikwm.com",
    "Referer": "https://www.tikwm.com/",
    "X-Requested-With": "XMLHttpRequest",
}

TIKMATE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://tikmate.app",
    "Referer": "https://tikmate.app/",
}

def clean_tiktok_url(raw_url: str) -> str:
    """Finds and extracts a valid TikTok URL from raw user text/link."""
    raw_url = raw_url.strip()
    match = re.search(r"https?://[^\s]+", raw_url)
    if not match:
        raise ValueError("Không tìm thấy đường link hợp lệ trong nội dung đã nhập.")
    
    # Strip any trailing punctuation (.,;:!?)'" etc.)
    url = match.group(0).rstrip(".,;:!?)'\"<>[]{}")
    
    # Check if user entered an incomplete link or profile link
    if re.search(r"/@[\w\.-]+/(?:video|photo|phot|v)/?$", url, re.I):
        raise ValueError("Đường dẫn bị thiếu mã số ID bài viết ở cuối (ví dụ thiếu dãy số như /photo/7412345678...). Vui lòng nhấp hẳn vào bài viết trên TikTok để sao chép liên kết đầy đủ.")

    if re.search(r"/@[\w\.-]+/?$", url):
        raise ValueError("Đây là đường dẫn Trang cá nhân (Profile) của tác giả, không phải bài đăng video. Vui lòng nhấp vào một video cụ thể để sao chép link.")

    parsed = urllib.parse.urlparse(url)
    # If standard desktop video or photo URL, clean tracking query parameters
    if re.search(r"/(?:video|photo|v)/(\d+)", parsed.path):
        cleaned = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return cleaned
    
    # For short links, keep path and query if present or stripped
    cleaned = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    return cleaned

async def resolve_redirect_url(url: str) -> str:
    """Follows redirects for shortlinks (vt.tiktok.com, vm.tiktok.com, /t/..., etc.)."""
    # If the URL already contains a video or photo ID, do not follow redirect!
    if re.search(r"/(?:video|photo|v)/(\d+)", url):
        return url

    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    is_shortlink = any(x in domain for x in ["vt.tiktok.com", "vm.tiktok.com", "m.tiktok.com"]) or "/t/" in parsed.path
    if not is_shortlink:
        return url

    redirect_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        async with httpx.AsyncClient(headers=redirect_headers, follow_redirects=False, timeout=8.0) as client:
            resp = await client.get(url)
            loc = resp.headers.get("location")
            if loc and re.search(r"/(?:video|photo|v)/(\d+)", loc):
                return loc.split("?")[0]
            
            # Try following redirects
            resp_follow = await client.get(url, follow_redirects=True)
            final_url = str(resp_follow.url)
            if re.search(r"/(?:video|photo|v)/(\d+)", final_url):
                return final_url.split("?")[0]
    except Exception as e:
        logger.warning(f"Error resolving redirect for {url}: {e}")

    # If redirect did not yield a valid video ID, keep the original short link
    return url

def format_number(num: Optional[int]) -> str:
    """Formats numbers to friendly strings like 12.5K, 1.2M."""
    if num is None:
        return "0"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def format_bytes(bytes_count: Optional[int]) -> str:
    """Formats bytes to MB or KB."""
    if not bytes_count or bytes_count <= 0:
        return ""
    mb = bytes_count / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = bytes_count / 1024
    return f"{kb:.0f} KB"

def ensure_absolute_url(url: Optional[str], base: str = "https://www.tikwm.com") -> Optional[str]:
    """Ensures relative media URLs from APIs have complete https:// scheme and host."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return f"https:{url}"
    elif url.startswith("/"):
        return f"{base.rstrip('/')}{url}"
    return url

async def fetch_tikwm_raw(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetches raw data from TikWM API.
    Bypasses Cloudflare on datacenter/cloud servers (Render, Heroku, AWS)
    using curl_cffi Chrome TLS impersonation, falling back to httpx with browser headers.
    """
    post_data = {
        "url": url,
        "count": 12,
        "cursor": 0,
        "web": 1,
        "hd": 1
    }
    endpoints = ["https://www.tikwm.com/api/", "https://tikwm.com/api/"]

    # 1. Primary: curl_cffi with Chrome TLS impersonation
    if CURL_CFFI_AVAILABLE:
        for ep in endpoints:
            try:
                async with CurlAsyncSession(impersonate="chrome", timeout=15) as session:
                    res = await session.post(ep, data=post_data, headers=TIKWM_HEADERS)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("code") == 0 and data.get("data"):
                            return data["data"]
            except Exception as e:
                logger.warning(f"curl_cffi attempt on {ep} failed: {e}")

    # 2. Fallback: httpx with realistic browser headers
    for ep in endpoints:
        try:
            async with httpx.AsyncClient(headers=TIKWM_HEADERS, timeout=15.0) as client:
                res = await client.post(ep, data=post_data)
                if res.status_code != 200:
                    res = await client.get(ep, params=post_data)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("code") == 0 and data.get("data"):
                        return data["data"]
        except Exception as e:
            logger.warning(f"httpx attempt on {ep} failed: {e}")

    return None

async def extract_via_primary_api(url: str) -> Optional[Dict[str, Any]]:
    """
    Extracts TikTok metadata and high-definition media using TikWM API.
    Supports single videos and multi-photo slideshow carousels.
    """
    res_data = await fetch_tikwm_raw(url)
    if not res_data:
        return None

    try:
        video_id = str(res_data.get("id", ""))
        title = res_data.get("title", "") or "TikTok Video"
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40].strip() or f"tiktok_{video_id}"
        
        author = res_data.get("author", {}) or {}
        author_info = {
            "username": author.get("unique_id", "tiktok_user"),
            "name": author.get("nickname", "TikTok User"),
            "avatar": ensure_absolute_url(author.get("avatar", "")) or ""
        }
        
        stats = {
            "likes": format_number(res_data.get("digg_count")),
            "comments": format_number(res_data.get("comment_count")),
            "shares": format_number(res_data.get("share_count")),
            "views": format_number(res_data.get("play_count")),
        }
        
        downloads: List[Dict[str, Any]] = []
        
        hd_url = ensure_absolute_url(res_data.get("hdplay"))
        std_url = ensure_absolute_url(res_data.get("play"))
        wm_url = ensure_absolute_url(res_data.get("wmplay"))
        music_info = res_data.get("music_info") or {}
        raw_music = music_info.get("play") or res_data.get("music")
        music_url = ensure_absolute_url(raw_music)
        images = res_data.get("images") or []
        is_slideshow = len(images) > 0
        
        # 1. HD No Watermark (Highest Quality)
        if hd_url:
            hd_size = format_bytes(res_data.get("hd_size"))
            downloads.append({
                "id": "hd",
                "label": "Tải chất lượng gốc cao nhất (Full HD / Original)",
                "sublabel": "Độ phân giải cao nhất không dính logo TikTok",
                "badge": "Chất lượng cao nhất",
                "quality": "Full HD",
                "size": hd_size,
                "download_url": f"/api/download?url={urllib.parse.quote(hd_url)}&filename={urllib.parse.quote(safe_title + '_HD.mp4')}",
                "direct_url": hd_url,
                "is_best": True,
                "type": "video"
            })
            
        # 2. Standard No Watermark
        if std_url and std_url != hd_url:
            std_size = format_bytes(res_data.get("size"))
            downloads.append({
                "id": "standard",
                "label": "Tải chất lượng tiêu chuẩn (SD Không logo)",
                "sublabel": "Độ phân giải tiêu chuẩn, dung lượng nhẹ hơn",
                "badge": "Tiêu chuẩn",
                "quality": "SD",
                "size": std_size,
                "download_url": f"/api/download?url={urllib.parse.quote(std_url)}&filename={urllib.parse.quote(safe_title + '.mp4')}",
                "direct_url": std_url,
                "is_best": False if downloads else True,
                "type": "video"
            })
        elif std_url and not hd_url:
            std_size = format_bytes(res_data.get("size"))
            downloads.append({
                "id": "hd",
                "label": "Tải chất lượng gốc (Không logo)",
                "sublabel": "Chất lượng video chuẩn từ TikTok",
                "badge": "Chất lượng gốc",
                "quality": "Gốc",
                "size": std_size,
                "download_url": f"/api/download?url={urllib.parse.quote(std_url)}&filename={urllib.parse.quote(safe_title + '.mp4')}",
                "direct_url": std_url,
                "is_best": True,
                "type": "video"
            })

        # 3. Watermark version if available
        if wm_url and not downloads:
            downloads.append({
                "id": "watermark",
                "label": "Tải video có logo (Bản gốc TikTok)",
                "sublabel": "Video nguyên bản kèm watermark",
                "badge": "Có Logo",
                "quality": "Watermark",
                "size": format_bytes(res_data.get("wm_size")),
                "download_url": f"/api/download?url={urllib.parse.quote(wm_url)}&filename={urllib.parse.quote(safe_title + '_wm.mp4')}",
                "direct_url": wm_url,
                "is_best": True,
                "type": "video"
            })
            
        # 4. Audio (MP3)
        if music_url:
            downloads.append({
                "id": "audio",
                "label": "Tải âm thanh gốc (MP3)",
                "sublabel": "Nhạc nền chất lượng cao từ bài đăng",
                "badge": "MP3",
                "quality": "Audio",
                "size": "",
                "download_url": f"/api/download?url={urllib.parse.quote(music_url)}&filename={urllib.parse.quote(safe_title + '.mp3')}",
                "direct_url": music_url,
                "is_best": False,
                "type": "audio"
            })
        
        # Slideshow images
        image_list = []
        if is_slideshow:
            for idx, raw_img in enumerate(images, 1):
                img_url = ensure_absolute_url(raw_img)
                if img_url:
                    image_list.append({
                        "index": idx,
                        "url": img_url,
                        "download_url": f"/api/download?url={urllib.parse.quote(img_url)}&filename={urllib.parse.quote(f'{safe_title}_photo_{idx}.jpg')}"
                    })
        
        preview_video = std_url or hd_url
        cover = ensure_absolute_url(res_data.get("cover"))
        origin_cover = ensure_absolute_url(res_data.get("origin_cover")) or cover
        
        return {
            "id": video_id,
            "title": title,
            "cover": cover,
            "origin_cover": origin_cover,
            "duration": res_data.get("duration", 0),
            "author": author_info,
            "stats": stats,
            "is_slideshow": is_slideshow,
            "images": image_list,
            "downloads": downloads,
            "preview_video": preview_video,
            "source": "tikwm"
        }
    except Exception as e:
        logger.error(f"Error parsing TikWM payload: {e}")
        return None

async def extract_via_tikmate_api(url: str) -> Optional[Dict[str, Any]]:
    """
    Fallback extraction using Tikmate API (api.tikmate.app/api/lookup).
    """
    try:
        async with httpx.AsyncClient(headers=TIKMATE_HEADERS, timeout=15.0) as client:
            res = await client.post("https://api.tikmate.app/api/lookup", data={"url": url})
            if res.status_code != 200:
                return None
            data = res.json()
            if not data.get("success") or not data.get("token") or not data.get("id"):
                return None

            vid = str(data.get("id"))
            token = str(data.get("token"))
            title = data.get("desc") or "TikTok Video"
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40].strip() or f"tiktok_{vid}"

            author_name = data.get("author_name") or "TikTok User"
            author_id = data.get("author_id") or "tiktok_user"
            author_avatar = data.get("author_avatar") or ""

            author_info = {
                "username": author_id,
                "name": author_name,
                "avatar": author_avatar
            }

            stats = {
                "likes": format_number(data.get("like_count")),
                "comments": format_number(data.get("comment_count")),
                "shares": format_number(data.get("share_count")),
                "views": "-"
            }

            hd_url = f"https://tikmate.app/download/{token}/{vid}.mp4?hd=1"
            sd_url = f"https://tikmate.app/download/{token}/{vid}.mp4"

            downloads: List[Dict[str, Any]] = [
                {
                    "id": "hd",
                    "label": "Tải chất lượng gốc cao nhất (Full HD / Original)",
                    "sublabel": "Độ phân giải cao nhất không dính logo",
                    "badge": "Chất lượng cao nhất",
                    "quality": "Full HD",
                    "size": "",
                    "download_url": f"/api/download?url={urllib.parse.quote(hd_url)}&filename={urllib.parse.quote(safe_title + '_HD.mp4')}",
                    "direct_url": hd_url,
                    "is_best": True,
                    "type": "video"
                },
                {
                    "id": "standard",
                    "label": "Tải chất lượng tiêu chuẩn (SD Không logo)",
                    "sublabel": "Độ phân giải tiêu chuẩn, tải nhanh",
                    "badge": "Tiêu chuẩn",
                    "quality": "SD",
                    "size": "",
                    "download_url": f"/api/download?url={urllib.parse.quote(sd_url)}&filename={urllib.parse.quote(safe_title + '.mp4')}",
                    "direct_url": sd_url,
                    "is_best": False,
                    "type": "video"
                }
            ]

            cover = data.get("cover") or data.get("dynamic_cover")

            return {
                "id": vid,
                "title": title,
                "cover": cover,
                "origin_cover": cover,
                "duration": 0,
                "author": author_info,
                "stats": stats,
                "is_slideshow": False,
                "images": [],
                "downloads": downloads,
                "preview_video": sd_url,
                "source": "tikmate"
            }
    except Exception as e:
        logger.warning(f"Tikmate fallback error: {e}")
        return None

async def extract_via_lovetik_api(url: str) -> Optional[Dict[str, Any]]:
    """
    Fallback extraction using LoveTik API.
    """
    api_url = "https://lovetik.com/api/ajax/search"
    # LoveTik works better with /video/ instead of /photo/
    norm_url = re.sub(r"/photo/(\d+)", r"/video/\1", url)

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
            res = await client.post(api_url, data={"query": norm_url})
            if res.status_code != 200:
                res = await client.post(api_url, data={"query": url})
                if res.status_code != 200:
                    return None
            
            data = res.json()
            if data.get("status") != "ok" or not data.get("links"):
                return None
            
            vid = data.get("vid", "tiktok")
            title = data.get("desc", "TikTok Video") or "TikTok Video"
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40].strip() or f"tiktok_{vid}"
            author_name = data.get("author", "TikTok User")
            
            author_info = {
                "username": author_name.lower().replace(" ", "_"),
                "name": author_name,
                "avatar": data.get("cover") or ""
            }
            
            stats = {
                "likes": "-",
                "comments": "-",
                "shares": "-",
                "views": "-"
            }
            
            downloads: List[Dict[str, Any]] = []
            preview_video = ""
            
            for link in data.get("links", []):
                d_url = ensure_absolute_url(link.get("a"), base="https://lovetik.com")
                label = link.get("t", "")
                sub = link.get("s", "")
                
                if not d_url:
                    continue
                    
                if "Nowatermark (HD)" in label or sub == "HD":
                    downloads.append({
                        "id": "hd",
                        "label": "Tải chất lượng gốc cao nhất (Full HD / Original)",
                        "sublabel": "Độ phân giải cao nhất không dính logo",
                        "badge": "Chất lượng cao nhất",
                        "quality": "Full HD",
                        "size": "",
                        "download_url": f"/api/download?url={urllib.parse.quote(d_url)}&filename={urllib.parse.quote(safe_title + '_HD.mp4')}",
                        "direct_url": d_url,
                        "is_best": True,
                        "type": "video"
                    })
                    if not preview_video:
                        preview_video = d_url
                elif "Nowatermark" in label:
                    downloads.append({
                        "id": "standard",
                        "label": "Tải chất lượng tiêu chuẩn (SD Không logo)",
                        "sublabel": "Độ phân giải tiêu chuẩn, tải nhanh",
                        "badge": "Tiêu chuẩn",
                        "quality": "SD",
                        "size": "",
                        "download_url": f"/api/download?url={urllib.parse.quote(d_url)}&filename={urllib.parse.quote(safe_title + '.mp4')}",
                        "direct_url": d_url,
                        "is_best": False if downloads else True,
                        "type": "video"
                    })
                    if not preview_video:
                        preview_video = d_url
                elif "MP3" in label or "Audio" in label:
                    downloads.append({
                        "id": "audio",
                        "label": "Tải âm thanh gốc (MP3)",
                        "sublabel": "Nhạc nền chất lượng cao",
                        "badge": "MP3",
                        "quality": "Audio",
                        "size": "",
                        "download_url": f"/api/download?url={urllib.parse.quote(d_url)}&filename={urllib.parse.quote(safe_title + '.mp3')}",
                        "direct_url": d_url,
                        "is_best": False,
                        "type": "audio"
                    })
                    
            if not downloads:
                return None
                
            return {
                "id": vid,
                "title": title,
                "cover": data.get("cover"),
                "origin_cover": data.get("cover"),
                "duration": 0,
                "author": author_info,
                "stats": stats,
                "is_slideshow": False,
                "images": [],
                "downloads": downloads,
                "preview_video": preview_video,
                "source": "lovetik"
            }
    except Exception as e:
        logger.error(f"Error in extract_via_lovetik_api: {e}")
        return None

def extract_via_ytdlp(url: str) -> Optional[Dict[str, Any]]:
    """
    Fallback extraction using yt-dlp.
    Normalizes /photo/ URLs to /video/ so yt-dlp's extractor regex recognizes it.
    """
    try:
        import yt_dlp
    except ImportError:
        logger.warning("yt-dlp is not installed, skipping yt-dlp fallback.")
        return None
    
    # Normalize photo URL to video URL for yt-dlp compatibility
    fetch_url = re.sub(r"/photo/(\d+)", r"/video/\1", url)
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(fetch_url, download=False)
            if not info:
                return None
            
            video_id = info.get("id", "")
            title = info.get("title") or info.get("description") or "TikTok Video"
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40].strip() or f"tiktok_{video_id}"
            
            author_info = {
                "username": info.get("uploader_id") or info.get("uploader") or "tiktok_user",
                "name": info.get("uploader") or "TikTok User",
                "avatar": info.get("thumbnail") or ""
            }
            
            stats = {
                "likes": format_number(info.get("like_count")),
                "comments": format_number(info.get("comment_count")),
                "shares": format_number(info.get("repost_count")),
                "views": format_number(info.get("view_count")),
            }
            
            formats = info.get("formats", [])
            best_fmt = None
            best_height = 0
            best_tbr = 0
            for f in formats:
                h = f.get("height") or 0
                tbr = f.get("tbr") or 0
                if f.get("url") and (h > best_height or (h == best_height and tbr > best_tbr)):
                    best_height = h
                    best_tbr = tbr
                    best_fmt = f
            
            downloads: List[Dict[str, Any]] = []
            
            video_url = (best_fmt or {}).get("url") or info.get("url")
            if video_url:
                filesize = (best_fmt or {}).get("filesize") or (best_fmt or {}).get("filesize_approx")
                size_str = format_bytes(filesize)
                res_label = f"{best_height}p" if best_height else "Gốc"
                
                downloads.append({
                    "id": "hd",
                    "label": f"Tải chất lượng gốc ({res_label} - Không logo)",
                    "sublabel": "Độ phân giải cao nhất trích xuất từ TikTok",
                    "badge": "Chất lượng gốc",
                    "quality": res_label,
                    "size": size_str,
                    "download_url": f"/api/download?url={urllib.parse.quote(video_url)}&filename={urllib.parse.quote(safe_title + '_HD.mp4')}",
                    "direct_url": video_url,
                    "is_best": True,
                    "type": "video"
                })
            
            return {
                "id": video_id,
                "title": title,
                "cover": info.get("thumbnail"),
                "origin_cover": info.get("thumbnail"),
                "duration": info.get("duration", 0),
                "author": author_info,
                "stats": stats,
                "is_slideshow": False,
                "images": [],
                "downloads": downloads,
                "preview_video": video_url,
                "source": "ytdlp"
            }
    except Exception as e:
        logger.warning(f"Error in extract_via_ytdlp: {e}")
        return None

async def parse_tiktok_video(raw_url: str) -> Dict[str, Any]:
    """
    Main entry point: Cleans URL, resolves redirects, and extracts highest quality media.
    Uses multi-layer resilient fallback strategy:
    1. TikWM API (curl_cffi Chrome TLS impersonation to bypass Cloudflare 403)
    2. Tikmate API (Fast fallback for watermark-free MP4)
    3. LoveTik API (Secondary fallback)
    4. yt-dlp internal extractor
    """
    clean_url = clean_tiktok_url(raw_url)
    resolved_url = await resolve_redirect_url(clean_url)
    
    # 1. Try Primary Engine (TikWM with TLS impersonation)
    for u in [resolved_url, clean_url, raw_url.strip()]:
        result = await extract_via_primary_api(u)
        if result:
            return result
    
    # 2. Try Tikmate Engine
    for u in [resolved_url, clean_url]:
        result_tikmate = await extract_via_tikmate_api(u)
        if result_tikmate:
            return result_tikmate

    # 3. Try LoveTik Engine
    for u in [resolved_url, clean_url]:
        result_lovetik = await extract_via_lovetik_api(u)
        if result_lovetik:
            return result_lovetik

    # 4. Try yt-dlp Engine
    result_ytdlp = extract_via_ytdlp(resolved_url)
    if result_ytdlp:
        return result_ytdlp
    
    raise RuntimeError("Không thể tải thông tin video từ liên kết này. Vui lòng kiểm tra lại đường dẫn TikTok (đảm bảo video đang ở chế độ công khai và liên kết chính xác).")
