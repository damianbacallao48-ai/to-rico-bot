import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta
import requests
import yt_dlp
from flask import Flask
from telebot import TeleBot, types

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
BOT_TOKEN = "8875681851:AAF-LUfVC7MoSW_Mwxva82NVxVnaknQpAfU"
ADMIN_ID = 6731555041
CANAL_OBLIGATORIO = "@torico_cuba_db"
CANAL_ENLACE = "https://t.me/torico_cuba_db"
LIMITE_GRATIS = 2
ADMIN_USER = "@torico_cuba_db"

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo 24/7"

def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================
# BASE DE DATOS LOCAL (SQLite)
# ==========================================
conn = sqlite3.connect("usuarios.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        user_id INTEGER PRIMARY KEY,
        descargas INTEGER DEFAULT 0,
        vip_hasta TEXT
    )
''')
conn.commit()

def verificar_estado_usuario(user_id):
    if user_id == ADMIN_ID:
        return True, "admin", "👑 Dueño / Acceso Total"
    
    cursor.execute("SELECT descargas, vip_hasta FROM usuarios WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ahora = datetime.now()

    if not res:
        cursor.execute("INSERT INTO usuarios (user_id, descargas) VALUES (?, 0)", (user_id,))
        conn.commit()
        return True, "free", f"Prueba gratuita (0/{LIMITE_GRATIS} usadas)"

    descargas, vip_hasta_str = res

    if vip_hasta_str:
        try:
            vip_hasta = datetime.strptime(vip_hasta_str, "%Y-%m-%d %H:%M:%S")
            if ahora < vip_hasta:
                dias_restantes = (vip_hasta - ahora).days + 1
                return True, "vip", f"⭐ Miembro VIP ({dias_restantes} días activos)"
        except Exception:
            pass

    if descargas < LIMITE_GRATIS:
        return True, "free", f"Prueba gratuita ({descargas}/{LIMITE_GRATIS} usadas)"

    return False, "expired", f"Agotado ({descargas}/{LIMITE_GRATIS})"

def sumar_descarga(user_id):
    if user_id != ADMIN_ID:
        cursor.execute("UPDATE usuarios SET descargas = descargas + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def activar_vip_15_dias(user_id):
    nueva_fecha = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO usuarios (user_id, vip_hasta) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET vip_hasta = excluded.vip_hasta
    ''', (user_id, nueva_fecha))
    conn.commit()
    return nueva_fecha

def esta_suscrito(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        miembro = bot.get_chat_member(CANAL_OBLIGATORIO, user_id)
        return miembro.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

# ==========================================
# LIMPIEZA AUTOMÁTICA DE ENLACES
# ==========================================

def sanitizar_enlace(texto):
    url_match = re.search(r'(https?://[^\s]+)', texto)
    if not url_match:
        return None, None
    
    url = url_match.group(1).strip()
    
    # Instagram: extraer solo el código limpio
    ig_match = re.search(r'(?:instagram\.com|instagr\.am)/(?:reel|p|tv)/([a-zA-Z0-9_-]+)', url)
    if ig_match:
        clean_url = f"https://www.instagram.com/reel/{ig_match.group(1)}/"
        return "instagram", clean_url

    # YouTube: extraer ID limpio de 11 caracteres
    yt_match = re.search(r'(?:youtube\.com/shorts/|youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})', url)
    if yt_match:
        clean_url = f"https://www.youtube.com/watch?v={yt_match.group(1)}"
        return "youtube", clean_url

    # TikTok: quitar parámetros
    if "tiktok.com" in url:
        clean_url = url.split("?")[0]
        return "tiktok", clean_url

    return "otro", url

# ==========================================
# MOTORES DE DESCARGA
# ==========================================

# 1. TIKTOK (INTACTO - NO TOCADO)
def descargar_tiktok(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        api_url = f"https://www.tikwm.com/api/?url={url}"
        r = requests.get(api_url, headers=headers, timeout=15).json()
        if r.get("code") == 0:
            data = r.get("data", {})
            video_url = data.get("play") or data.get("wmplay")
            if video_url:
                os.makedirs("descargas", exist_ok=True)
                file_path = f"descargas/tik_{data.get('id', 'temp')}.mp4"
                with requests.get(video_url, headers=headers, stream=True, timeout=45) as req:
                    req.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in req.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 300 * 1024:
                    return file_path
                elif os.path.exists(file_path):
                    os.remove(file_path)
    except Exception as e:
        print(f"Error TikTok: {e}")
    return None

# 2. INSTAGRAM (Restaurado a yt-dlp directo sin requerir ffmpeg ni APIs externas caídas)
def descargar_instagram(url):
    os.makedirs("descargas", exist_ok=True)
    out_pattern = f"descargas/ig_{os.urandom(4).hex()}.%(ext)s"
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': out_pattern,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 48 * 1024 * 1024,
        'socket_timeout': 30
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            mp4_name = base + ".mp4"
            if os.path.exists(mp4_name):
                return mp4_name
            return filename
    except Exception as e:
        print(f"Error yt-dlp Instagram: {e}")
        return None

# 3. YOUTUBE (INTACTO - NO TOCADO: El que funcionó al 100%)
def descargar_youtube(url):
    try:
        r = requests.post(
            "https://api.cobalt.tools",
            json={"url": url, "videoQuality": "720"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=12
        )
        if r.status_code == 200:
            video_url = r.json().get("url")
            if video_url:
                os.makedirs("descargas", exist_ok=True)
                file_path = f"descargas/yt_{os.urandom(4).hex()}.mp4"
                with requests.get(video_url, stream=True, timeout=60) as req:
                    req.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in req.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 100 * 1024:
                    return file_path
    except Exception:
        pass

    try:
        os.makedirs("descargas", exist_ok=True)
        out_pattern = f"descargas/yt_{os.urandom(4).hex()}.%(ext)s"
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
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
            return filename
    except Exception as e:
        print(f"Error yt-dlp YouTube: {e}")

    return None

# ==========================================
# MANEJADOR DE MENSAJES Y COMANDOS
# ==========================================

@bot.message_handler(commands=['start'])
def bienvenida(message):
    user_id = message.from_user.id
    _, _, texto_estado = verificar_estado_usuario(user_id)
    texto = (
        "⚡ *¡Bienvenido al Descargador Rápido!*\n\n"
        "Envía el enlace de cualquier video:\n"
        "• 🎵 *TikTok* (sin marca de agua)\n"
        "• 📸 *Instagram Reels y Videos*\n"
        "• 🔴 *YouTube Shorts y Videos*\n\n"
        f"📊 *Tu plan:* `{texto_estado}`\n"
        f"🆔 *Tu ID:* `{user_id}`\n\n"
        "👉 *Pega el enlace aquí abajo:*"
    )
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['darvip'])
def dar_vip_comando(message):
    if message.from_user.id != ADMIN_ID:
        return

    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(message, "Uso: `/darvip <ID_DEL_USUARIO>`", parse_mode="Markdown")
        return

    try:
        target_id = int(partes[1])
        fecha_fin = activar_vip_15_dias(target_id)
        bot.reply_to(message, f"✅ Usuario `{target_id}` activado como VIP por 15 días (hasta {fecha_fin}).", parse_mode="Markdown")
        try:
            bot.send_message(
                target_id,
                f"🎉 *¡Tu suscripción VIP ha sido activada!*\n\nTienes descargas ilimitadas durante 15 días (hasta el {fecha_fin}). ¡Que lo disfrutes!",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ El ID debe ser un número entero.")

@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text))
def recibir_enlace(message):
    user_id = message.from_user.id

    if not esta_suscrito(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Unirme al Canal", url=CANAL_ENLACE))
        bot.reply_to(message, "⚠️ Para descargar videos gratis, primero únete a nuestro canal:", reply_markup=markup)
        return

    puede_descargar, tipo_usuario, info = verificar_estado_usuario(user_id)
    if not puede_descargar:
        contacto_link = f"https://t.me/{ADMIN_USER.replace('@', '')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⭐ Adquirir VIP (15 Días)", url=contacto_link))
        texto_bloqueo = (
            "❌ *Has alcanzado el límite de 2 descargas gratuitas.*\n\n"
            "🌟 *Pase VIP (15 días de acceso ilimitado):*\n"
            "• Descargas sin límite.\n"
            "• Máxima velocidad de entrega.\n\n"
            f"🆔 *Tu ID para activación:* `{user_id}`\n\n"
            "Toca el botón de abajo para activar tu suscripción."
        )
        bot.reply_to(message, texto_bloqueo, reply_markup=markup, parse_mode="Markdown")
        return

    plataforma, url_limpia = sanitizar_enlace(message.text)
    if not url_limpia:
        bot.reply_to(message, "❌ No se detectó un enlace válido.")
        return

    msg_espera = bot.reply_to(message, "⏳ *Descargando video...*", parse_mode="Markdown")
    os.makedirs("descargas", exist_ok=True)
    archivo = None

    try:
        if plataforma == "tiktok":
            archivo = descargar_tiktok(url_limpia)
        elif plataforma == "instagram":
            archivo = descargar_instagram(url_limpia)
        elif plataforma == "youtube":
            archivo = descargar_youtube(url_limpia)
        else:
            archivo = descargar_youtube(url_limpia)

        if archivo and os.path.exists(archivo):
            bot.edit_message_text("📤 *Enviando video...*", chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="Markdown")
            
            pie_de_video = (
                "🎬 *Video descargado con éxito*\n\n"
                "⚡ *Baja videos de TikTok, Reels y Shorts con este bot.*\n"
                "📢 *Canal oficial:* @torico_cuba_db"
            )
            
            with open(archivo, 'rb') as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    supports_streaming=True,
                    caption=pie_de_video,
                    parse_mode="Markdown"
                )
            
            if tipo_usuario == "free":
                sumar_descarga(user_id)

            bot.delete_message(message.chat.id, msg_espera.message_id)
        else:
            bot.edit_message_text(
                "❌ No se pudo descargar este enlace. Asegúrate de que el contenido no sea privado ni supere los 50MB.",
                chat_id=message.chat.id,
                message_id=msg_espera.message_id
            )
    except Exception as e:
        bot.edit_message_text(f"❌ Error al procesar: {e}", chat_id=message.chat.id, message_id=msg_espera.message_id)
    finally:
        if archivo and os.path.exists(archivo):
            try:
                os.remove(archivo)
            except Exception:
                pass

if __name__ == "__main__":
    print("Iniciando servicio...")
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
