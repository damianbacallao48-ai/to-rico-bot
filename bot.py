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
# MOTORES DE DESCARGA MULTIPLATAFORMA
# ==========================================

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

def descargar_youtube_api(url):
    """Descarga de YouTube a través de puente API externo para evitar el bloqueo antibot de Railway."""
    try:
        api_url = f"https://api.invidious.io/api/v1/videos/"
        # Opciones de proxies/APIs rotativas directas
        endpoints = [
            f"https://yt-api-service.onrender.com/download?url={url}",
            f"https://pipedapi.kavin.rocks/streams/"
        ]
        
        # Primero intentamos Cobalt con headers de túnel
        cobalt_url = "https://api.cobalt.tools"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
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

def descargar_instagram_api(url):
    try:
        api_endpoint = "https://api.cobalt.tools"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        res = requests.post(api_endpoint, json={"url": url}, headers=headers, timeout=15)
        if res.status_code == 200:
            v_url = res.json().get("url")
            if v_url:
                os.makedirs("descargas", exist_ok=True)
                file_path = f"descargas/insta_{os.urandom(4).hex()}.mp4"
                with requests.get(v_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 100 * 1024:
                    return file_path
    except Exception as e:
        print(f"Error Instagram API: {e}")
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
        "⚡ *¡Bienvenido al Descargador Rápido HD!*\n\n"
        "Baja videos sin marcas de agua y en la mejor calidad de:\n"
        "• 🎵 *TikTok* (sin marca de agua)\n"
        "• 📸 *Instagram Reels y Videos*\n"
        "• 🔴 *YouTube Shorts y Videos*\n\n"
        f"📊 *Tu cuenta:* `{texto_estado}`\n"
        f"🆔 *Tu ID:* `{user_id}`\n\n"
        "👉 *Pega el enlace del video aquí abajo para descargarlo:*"
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
        bot.reply_to(message, f"✅ *VIP Activado!*\n\nUsuario: `{target_id}`\nVálido hasta: `{fecha_fin}`", parse_mode="Markdown")
        
        try:
            bot.send_message(
                target_id,
                f"🎉 *¡Tu suscripción VIP ha sido activada con éxito!*\n\n"
                f"Tienes descargas ilimitadas a máxima velocidad durante 15 días (hasta el `{fecha_fin}`).\n\n"
                "¡Disfruta del servicio!",
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
        bot.reply_to(
            message,
            "⚠️ *Para poder descargar videos gratis, primero debes unirte a nuestro canal oficial:*\n\n"
            "Únete y vuelve a enviar el enlace.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    puede_descargar, tipo_usuario, info = verificar_estado_usuario(user_id)
    if not puede_descargar:
        contacto_link = f"https://t.me/{ADMIN_USER.replace('@', '')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⭐ Activar VIP (15 Días)", url=contacto_link))
        
        texto_bloqueo = (
            "🚫 *Has consumido tus 2 descargas gratuitas de prueba.*\n\n"
            "💎 *Pasa al Pase VIP (15 días completos):*\n"
            "✅ Descargas 100% ilimitadas.\n"
            "✅ Máxima velocidad sin tiempos de espera.\n"
            "✅ Soporte activo 24/7.\n\n"
            f"🆔 *Tu ID:* `{user_id}` *(envíalo al contactar)*\n\n"
            "👇 *Toca el botón de abajo para solicitar tu activación inmediata:*"
        )
        bot.reply_to(message, texto_bloqueo, reply_markup=markup, parse_mode="Markdown")
        return

    msg_espera = bot.reply_to(message, "⚡ *Procesando y descargando video...*", parse_mode="Markdown")
    os.makedirs("descargas", exist_ok=True)
    archivo = None

    try:
        # 1. TikTok
        if "tiktok.com" in url:
            archivo = descargar_tiktok_api(url)
            
        # 2. Instagram
        elif "instagram.com" in url:
            archivo = descargar_instagram_api(url)
            
        # 3. YouTube Shorts / Video
        elif "youtube.com" in url or "youtu.be" in url:
            archivo = descargar_youtube_api(url)

        # 4. Respaldo general usando extractor cliente iOS/Android
        if not archivo or not os.path.exists(archivo):
            archivo = descargar_ytdlp(url)

        if archivo and os.path.exists(archivo):
            bot.edit_message_text("📤 *Subiendo video a Telegram...*", chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="Markdown")
            
            pie_de_video = (
                "🎬 *Video descargado con éxito*\n\n"
                "⚡ *Baja videos de TikTok, Reels y YouTube Shorts con este bot.*\n"
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
