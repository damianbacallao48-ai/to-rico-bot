# 2. YOUTUBE (CON FFMPEG HABILITADO)
def descargar_youtube(url):
    try:
        os.makedirs("descargas", exist_ok=True)
        out_pattern = f"descargas/yt_{os.urandom(4).hex()}.%(ext)s"
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': out_pattern,
            'quiet': True,
            'no_warnings': True,
            'max_filesize': 48 * 1024 * 1024,
            'socket_timeout': 30,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip'
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            mp4_name = base + ".mp4"
            if os.path.exists(mp4_name):
                return mp4_name
            if os.path.exists(filename):
                return filename
    except Exception as e:
        print(f"Error YouTube: {e}")
    return None
