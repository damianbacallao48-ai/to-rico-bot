import os
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
# BASE DE DATOS LOCAL
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
# MOTORES DE DESCARGA
# ==========================================

# TikTok (intacto)
def descargar_tiktok_api(url):
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
        print(f"Error TikTok API: {e}")
    return None

# Instagram (corregido con API dedicada para saltar el bloqueo de login)
def descargar_instagram_api(url):
    try:
        clean_url = url.split("?")[0].rstrip("/") + "/"
        api_url = f"https://api.vkrdownloader.com/v1/get?url={clean_url}"
        r = requests.get(api_url, timeout=20).json()
        
        video_url = None
        data = r.get("data", {})
        
        # Buscar el stream de video
        if isinstance(data, dict):
            downloads = data.get("downloads", [])
            for item in downloads:
                if item.get("format_id") in ["mp4", "video"] or "video" in str(item.get("format", "")).lower():
                    video_url = item.get("url")
                    break
            if not video_url and downloads:
                video_url = downloads[0].get("url")

        # Fallback a Cobalt
        if not video_url:
            cobalt_headers = {"Accept": "application/json", "Content-Type": "application/json"}
            c_res = requests.post("https://api.cobalt.tools", json={"url": clean_url}, headers=cobalt_headers, timeout=15)
            if c_res.status_code == 200:
                video_url = c_res.json().get("url")

        if video_url:
            os.makedirs("descargas", exist_ok=True)
            file_path = f"descargas/insta_{os.urandom(4).hex()}.mp4"
            with requests.get(video_url, stream=True, timeout=50) as req:
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
        print(f"Error Instagram API: {e}")
    return None

# YouTube (intacto: la misma configuración móvil que ya te funcionó)
def descargar_youtube_api(url):
    try:
        cobalt_url = "https://api.cobalt.tools"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        res = requests.post(cobalt_url, json={"url": url, "videoQuality": "720"}, headers=headers, timeout=15)
        if res.status_code == 200:
            v_url = res.json().get("url")
            if v_url:
                os.makedirs("descargas", exist_ok=True)
                file_path = f"descargas/yt_{os.urandom(4).hex()}.mp4"
                with requests.get(v_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 100 * 1024:
                    return file_path
    except Exception as e:
        print(f"Error en API YouTube: {e}")
    return None

def descargar_ytdlp(url):
    os.makedirs("descargas", exist_ok=True)
    out_pattern = f"descargas/dl_{os.urandom(4).hex()}.%(ext)s"
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': out_pattern,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 48 * 1024 * 1024,
        'socket_timeout': 25,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1'
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

# ==========================================
# COMANDOS Y MENSAJES
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
    url = message.text.strip()

    if "?" in url:
        url = url.split("?")[0]

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

    msg_espera = bot.reply_to(message, "⏳ *Descargando video...*", parse_mode="Markdown")
    os.makedirs("descargas", exist_ok=True)
    archivo = None

    try:
        # 1. TikTok
        if "tiktok.com" in url:
            archivo = descargar_tiktok_api(url)
            
        # 2. Instagram (Nunca usa yt-dlp para no disparar el error de cookies)
        elif "instagram.com" in url:
            archivo = descargar_instagram_api(url)
            
        # 3. YouTube (Shorts o videos)
        elif "youtube.com" in url or "youtu.be" in url:
            archivo = descargar_youtube_api(url)
            if not archivo or not os.path.exists(archivo):
                archivo = descargar_ytdlp(url)

        # 4. Otras plataformas
        if not archivo or not os.path.exists(archivo):
            if "instagram.com" not in url:
                archivo = descargar_ytdlp(url)

        if archivo and os.path.exists(archivo):
            bot.edit_message_text("📤 *Enviando video...*", chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="Markdown")
            with open(archivo, 'rb') as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    supports_streaming=True,
                    caption="🎬 Video descargado con éxito\n📢 Canal: @torico_cuba_db"
                )
            
            if tipo_usuario == "free":
                sumar_descarga(user_id)

            bot.delete_message(message.chat.id, msg_espera.message_id)
        else:
            bot.edit_message_text("❌ No se pudo descargar el video. Verifica que la cuenta no sea privada y vuelve a intentarlo.", chat_id=message.chat.id, message_id=msg_espera.message_id)
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
