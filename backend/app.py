import os
import urllib.parse
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
import logging

from backend.tiktok_parser import parse_tiktok_video, HEADERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok_app")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="TikTok HD Downloader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ParseRequest(BaseModel):
    url: str

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "TikTok HD Downloader"}

@app.post("/api/parse")
async def parse_video(req: ParseRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường link TikTok hợp lệ.")
    
    try:
        data = await parse_tiktok_video(req.url)
        return {"success": True, "data": data}
    except ValueError as ve:
        logger.warning(f"Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to parse video: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Không thể tải video: {str(e)}"
        )

@app.get("/api/download")
async def proxy_download(
    url: str = Query(..., description="Target file URL"),
    filename: str = Query("tiktok_video.mp4", description="Downloaded filename")
):
    """
    Proxies remote media file and streams it directly to client browser
    with Content-Disposition attachment to trigger download dialog and bypass CORS/hotlinking.
    """
    try:
        decoded_url = urllib.parse.unquote(url).strip()
        clean_filename = urllib.parse.unquote(filename).replace('"', '').strip()
        
        # Ensure full absolute URL
        if decoded_url.startswith("//"):
            decoded_url = f"https:{decoded_url}"
        elif decoded_url.startswith("/"):
            decoded_url = f"https://www.tikwm.com{decoded_url}"
            
        parsed_target = urllib.parse.urlparse(decoded_url)
        domain = parsed_target.netloc.lower()
        
        # Prepare custom headers to avoid CDN 403 / 503
        request_headers = dict(HEADERS)
        if "tikwm.com" in domain:
            request_headers["Referer"] = "https://www.tikwm.com/"
        elif "lovetik.com" in domain:
            request_headers["Referer"] = "https://lovetik.com/"
        elif "tiktok" in domain:
            request_headers["Referer"] = "https://www.tiktok.com/"
        else:
            request_headers["Referer"] = f"{parsed_target.scheme}://{parsed_target.netloc}/"
        
        client = httpx.AsyncClient(headers=request_headers, follow_redirects=True, timeout=60.0)
        req = client.build_request("GET", decoded_url)
        res = await client.send(req, stream=True)
        
        if res.status_code >= 400:
            await client.aclose()
            logger.warning(f"Proxy download received {res.status_code} for {decoded_url}, redirecting directly")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=decoded_url, status_code=307)
        
        content_type = res.headers.get("content-type", "application/octet-stream")
        content_length = res.headers.get("content-length")
        
        import re
        ascii_fallback = re.sub(r'[^\w\.-]', '_', clean_filename) or "tiktok_download.mp4"
        encoded_filename = urllib.parse.quote(clean_filename, encoding='utf-8')
        
        response_headers = {
            "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Length",
        }
        if content_length:
            response_headers["Content-Length"] = content_length
            
        async def stream_generator():
            try:
                async for chunk in res.aiter_bytes(chunk_size=1024 * 64):
                    yield chunk
            finally:
                await res.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_generator(),
            media_type=content_type,
            headers=response_headers,
            status_code=res.status_code
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying download: {e}")
        if decoded_url.startswith("http://") or decoded_url.startswith("https://"):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=decoded_url, status_code=307)
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải file: {str(e)}")

# Mount static frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
