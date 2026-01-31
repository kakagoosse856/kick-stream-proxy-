import asyncio
import base64
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import m3u8
import re
import os

# ========== التهيئة ==========
app = FastAPI(title="Kick Stream Proxy", version="1.0")

# السماح بجميع المصادر (لتشغيل من أي موقع)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== المتغيرات ==========
STREAM_CACHE = {}
CHUNK_TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Referer": "https://kick.com/",
    "Origin": "https://kick.com",
    "DNT": "1",
}

# ========== الدوال المساعدة ==========
def encode_url(url: str) -> str:
    """ترميز الرابط بـ base64"""
    return base64.urlsafe_b64encode(url.encode()).decode()

def decode_url(encoded: str) -> str:
    """فك ترميز الرابط"""
    return base64.urlsafe_b64decode(encoded.encode()).decode()

async def fetch_url(url: str) -> str:
    """جلب محتوى URL"""
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

# ========== المسارات ==========
@app.get("/", response_class=HTMLResponse)
async def home():
    """الصفحة الرئيسية مع مشغل فيديو"""
    return """
<!DOCTYPE html>
<html dir="rtl">
<head>
<meta charset="UTF-8">
<title>Kick Stream Proxy - Python</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
body{margin:0;background:#111;color:#fff;font-family:Arial}
.container{max-width:900px;margin:auto;padding:20px}
input,button{padding:10px;font-size:16px}
video{width:100%;margin-top:20px;background:#000}
</style>
</head>
<body>
<div class="container">
<h2>🎥 Kick Stream Proxy (Python)</h2>
<input id="url" style="width:100%" placeholder="ضع رابط m3u8 هنا">
<button onclick="play()">تشغيل</button>
<video id="v" controls></video>
</div>

<script>
function play(){
  const u=document.getElementById("url").value.trim();
  if(!u) return alert("ضع رابط m3u8");
  const p="/proxy/stream/"+btoa(u);
  const v=document.getElementById("v");

  if(Hls.isSupported()){
    const h=new Hls();
    h.loadSource(p);
    h.attachMedia(v);
  }else{
    v.src=p;
  }
}
</script>
</body>
</html>
"""

@app.get("/proxy/stream/{encoded_url}")
async def proxy_master_playlist(encoded_url: str):
    try:
        master_url = decode_url(encoded_url)
        content = await fetch_url(master_url)

        base_url = master_url.rsplit("/", 1)[0] + "/"
        out = []

        for line in content.splitlines():
            if line.startswith("#") or not line:
                out.append(line)
            else:
                if not line.startswith("http"):
                    line = base_url + line
                out.append("/proxy/chunk/" + encode_url(line))

        return StreamingResponse(
            iter(["\n".join(out)]),
            media_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/proxy/chunk/{encoded_url}")
async def proxy_chunk(encoded_url: str):
    try:
        url = decode_url(encoded_url)
        async with httpx.AsyncClient(timeout=CHUNK_TIMEOUT, headers=HEADERS) as client:
            r = await client.get(url)
            r.raise_for_status()
            return StreamingResponse(
                r.aiter_bytes(),
                media_type=r.headers.get("content-type","video/MP2T"),
                headers={"Access-Control-Allow-Origin": "*"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# ========== التشغيل ==========
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
