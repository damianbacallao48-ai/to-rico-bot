import os
import sqlite3
import threading
import requests
import yt_dlp
from flask import Flask
from telebot import TeleBot, types

BOT_TOKEN = "8875681851:AAF-LUfVC7MoSW_Mwxva82NVxVnaknQpAfU"
ADMIN_ID = 6731555041
CANAL_OBLIGATORIO = "@torico_cuba_db"
CANAL_ENLACE = "https://t.me/torico_cuba_db"
LIMITE_DIARIO_GRATIS = 3
ADMIN_USER = "@torico_cuba_db"

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo 24/7"

def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

conn = sqlite3.connect("usuarios.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        user_id INTEGER PRIMARY KEY,
        descargas INTEGER DEFAULT 0,
        es_vip INTEGER DEFAULT 0
    )
''')
conn.commit()

cursor.execute("INSERT INTO usuarios (user_id, es_vip) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET es_vip=1", (ADMIN_ID,))
conn.commit()

def obtener_usuario(user_id):
    if user_id == ADMIN_ID:
        return 0, 1
    cursor.execute("SELECT descargas, es_vip FROM usuarios WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        cursor.execute("INSERT INTO usuarios (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return 0, 0
    return res[0], res[1]

def sumar_descarga(user_id):
    if user_id != ADMIN_ID:
        cursor.execute("UPDATE usuarios SET descargas = descargas + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def esta_suscrito(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        miembro = bot.get_chat_member(CANAL_OBLIGATORIO, user_id)
        return miembro.status in ['creator', 'administrator', 'member']
    except Exception:
        return True

def descargar_tiktok_api(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        api_url = f"https://www.tikwm.com/api/?url={url}"
        r = requests.get(api_url, headers=headers, timeout=15).json()
        if r.get("code") == 0:
            data = r.get("data", {})
            # Priorizar video sin marca, luego video con marca
            video_url = data.get("play")
            if not video_url or not data.get("duration"):
                video_url = data.get("wmplay")
            
            if video_url:
                file_path = f"descargas/vid_{data.get('id', 'temp')}.mp4"
                with requests.get(video_url, headers=headers, stream=True, timeout=45) as req:
                    req.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in req.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                # Si el archivo descargado pesa menos de 800 KB, no es el video real
                if os.path.getsize(file_path) > 800 * 1024:
                    return file_path
                else:
                    os.remove(file_path)
    except Exception as e:
        print(f"Error en TikTok API: {e}")
    return None

def descargar_ytdlp(url):
    os.makedirs("descargas", exist_ok=True)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'descargas/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 48 * 1024 * 1024,
        'socket_timeout': 30
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

@bot.message_handler(commands=['start'])
def bienvenida(message):
    user_id = message.from_user.id
    descargas, es_vip = obtener_usuario(user_id)
    estado = "👑 Dueño / Administrador (Ilimitado)" if user_id == ADMIN_ID else ("⭐ VIP (Ilimitado)" if es_vip else f"Gratis ({descargas}/{LIMITE_DIARIO_GRATIS} usadas)")
    texto = (
        "⚡ *¡Bienvenido al Descargador Rápido!*\n\n"
        "Envía el enlace de cualquier video:\n"
        "• TikTok (sin marca de agua)\n"
        "• Instagram Reels\n"
        "• YouTube Shorts\n\n"
        f"📊 *Tu plan:* {estado}\n"
        f"🆔 *Tu ID:* `{user_id}`\n\n"
        "👉 *Pega el enlace aquí abajo:*"
    )
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text))
def recibir_enlace(message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not esta_suscrito(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Unirme al Canal", url=CANAL_ENLACE))
        bot.reply_to(message, "⚠️ Para descargar videos gratis, primero únete a nuestro canal:", reply_markup=markup)
        return

    descargas, es_vip = obtener_usuario(user_id)
    if not es_vip and descargas >= LIMITE_DIARIO_GRATIS:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⭐ Adquirir VIP Ilimitado", url=f"https://t.me/{ADMIN_USER.replace('@', '')}"))
        bot.reply_to(message, "❌ *Límite diario alcanzado (3/3).* Pasa a VIP:", reply_markup=markup, parse_mode="Markdown")
        return

    msg_espera = bot.reply_to(message, "⏳ *Descargando video...*", parse_mode="Markdown")
    os.makedirs("descargas", exist_ok=True)
    archivo = None

    try:
        if "tiktok.com" in url:
            archivo = descargar_tiktok_api(url)
        if not archivo or not os.path.exists(archivo):
            archivo = descargar_ytdlp(url)

        if archivo and os.path.exists(archivo):
            bot.edit_message_text("📤 *Enviando video...*", chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="Markdown")
            with open(archivo, 'rb') as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    supports_streaming=True,
                    caption="🎬 Video descargado\n📢 Canal: @torico_cuba_db"
                )
            sumar_descarga(user_id)
            bot.delete_message(message.chat.id, msg_espera.message_id)
        else:
            bot.edit_message_text("❌ No se encontró un archivo de video completo.", chat_id=message.chat.id, message_id=msg_espera.message_id)
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
