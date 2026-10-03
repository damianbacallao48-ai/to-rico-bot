import os
import re
import requests

def descargar(url):
    match = re.search(r'/(?:reel|p|tv)/([a-zA-Z0-9_-]+)', url)
    if not match:
        return None
    shortcode = match.group(1)
    clean_target = f"https://www.instagram.com/reel/{shortcode}/"

    video_url = None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Vía 1: Extractor CDN directo
    try:
        r = requests.get(f"https://api.vkrdownloader.com/v1/get?url={clean_target}", timeout=10).json()
        downloads = r.get("data", {}).get("downloads", [])
        for item in downloads:
            if "video" in str(item.get("format", "")).lower() or item.get("format_id") in ["mp4", "video"]:
                video_url = item.get("url")
                break
    except Exception:
        pass

    # Vía 2: Extractor DDInstagram
    if not video_url:
        try:
            r_dd = requests.get(f"https://api.ddinstagram.com/reel/{shortcode}/", timeout=10).json()
            video_url = r_dd.get("video_url")
        except Exception:
            pass

    if video_url:
        try:
            os.makedirs("descargas", exist_ok=True)
            file_path = f"descargas/ig_{os.urandom(4).hex()}.mp4"
            with requests.get(video_url, headers=headers, stream=True, timeout=50) as req:
                req.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in req.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 100 * 1024:
                return file_path
            elif os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error descargando IG: {e}")

    return None
