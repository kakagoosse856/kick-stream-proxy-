import base64
import httpx
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Kick Proxy Auto", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://kick.com", "Origin": "https://kick.com"}
CHUNK_TIMEOUT = 30

def decode_url(encoded: str) -> str:
    encoded += "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded.encode()).decode()

def get_streamlink_url(channel: str) -> str:
    """استخراج رابط m3u8 تلقائي من قناة Kick"""
    result = subprocess.run(
        ["streamlink", f"https://kick.com/{channel}", "best", "--stream-url"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception("القناة غير مباشرة أو الرابط غير موجود")
    return result.stdout.strip()

async def fetch_url(url: str) -> str:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text

# ======= الصفحة الرئيسية (HTML) =======
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kick Proxy Auto</title>
    </head>
    <body>
        <h1>🚀 Kick Proxy Auto</h1>
        <form action="/auto" method="get">
            <input name="channel" placeholder="اسم القناة على Kick">
            <button type="submit">تشغيل البث</button>
        </form>
    </body>
    </html>
    """

# ======= استخراج البث تلقائي =======
@app.get("/auto")
async def auto(channel: str):
    try:
        m3u8_url = get_streamlink_url(channel)
        content = await fetch_url(m3u8_url)
        lines = content.splitlines()
        final = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                final.append(line)
                continue
            # فك Base64 إذا موجود
            if "u=" in line:
                m = line.split("u=")[1].split("&")[0]
                try:
                    decoded = decode_url(m)
                    final.append(decoded)
                except:
                    final.append(line)
            else:
                final.append(line)
        return {"channel": channel, "final_m3u8": final, "direct_play": m3u8_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ======= جلب قطعة فيديو =======
@app.get("/proxy/chunk/{encoded_url}")
async def proxy_chunk(encoded_url: str):
    try:
        url = decode_url(encoded_url)
        async with httpx.AsyncClient(timeout=CHUNK_TIMEOUT, headers=HEADERS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = "video/MP2T" if url.endswith(".ts") else "application/vnd.apple.mpegurl"
            return StreamingResponse(resp.aiter_bytes(), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
