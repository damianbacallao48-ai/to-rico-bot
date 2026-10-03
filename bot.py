import os
import sqlite3
import threading
from datetime import datetime, timedelta
import requests
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

# Diccionario temporal para guardar información de descargas pendientes
CACHE_ENLACES = {}

@app.route('/')
def home():
    return "Bot en línea"

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
# MOTOR TIKTOK (VIDEO Y AUDIO MP3)
# ==========================================
def obtener_datos_tiktok(url):
    try:
        clean_url = url.split("?")[0]
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        api_url = f"https://www.tikwm.com/api/?url={clean_url}"
        r = requests.get(api_url, headers=headers, timeout=15).json()
        if r.get("code") == 0:
            return r.get("data", {})
    except Exception as e:
        print(f"Error TikTok API: {e}")
    return None

def bajar_archivo(url, destino):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    with requests.get(url, headers=headers, stream=True, timeout=50) as req:
        req.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in req.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
    return os.path.exists(destino) and os.path.getsize(destino) > 50 * 1024

# ==========================================
# COMANDOS Y MENSAJES
# ==========================================

@bot.message_handler(commands=['start'])
def bienvenida(message):
    user_id = message.from_user.id
    _, _, texto_estado = verificar_estado_usuario(user_id)
    texto = (
        "⚡ *¡Bienvenido al Descargador Pro!*\n\n"
        "Envía un enlace de TikTok y podrás elegir:\n"
        "• 🎬 *Video Completo* (en alta calidad y sin marca de agua)\n"
        "• 🎵 *Audio MP3* (canción o sonido original del video)\n\n"
        f"📊 *Tu plan:* `{texto_estado}`\n"
        f"🆔 *Tu ID:* `{user_id}`\n\n"
        "👉 *Pega el enlace de TikTok aquí abajo:*"
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
                f"🎉 *¡Tu suscripción VIP ha sido activada!*\n\nTienes descargas ilimitadas durante 15 días (hasta el {fecha_fin}).",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    except ValueError:
        bot.reply_to(message, "❌ El ID debe ser un número entero.")

@bot.message_handler(func=lambda msg: msg.text and ("tiktok.com" in msg.text))
def recibir_tiktok(message):
    user_id = message.from_user.id
    raw_text = message.text.strip()

    if not esta_suscrito(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Unirme al Canal", url=CANAL_ENLACE))
        bot.reply_to(message, "⚠️ Para descargar contenido, primero únete a nuestro canal:", reply_markup=markup)
        return

    puede_descargar, _, _ = verificar_estado_usuario(user_id)
    if not puede_descargar:
        contacto_link = f"https://t.me/{ADMIN_USER.replace('@', '')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⭐ Adquirir VIP (15 Días)", url=contacto_link))
        texto_bloqueo = (
            "❌ *Has alcanzado el límite de 2 descargas gratuitas.*\n\n"
            "🌟 *Pase VIP (15 días ilimitados):*\n"
            f"🆔 *Tu ID:* `{user_id}`\n\n"
            "Toca el botón para activarte."
        )
        bot.reply_to(message, texto_bloqueo, reply_markup=markup, parse_mode="Markdown")
        return

    msg_espera = bot.reply_to(message, "🔍 *Analizando contenido...*", parse_mode="Markdown")
    datos = obtener_datos_tiktok(raw_text)

    if not datos:
        bot.edit_message_text("❌ No se pudo procesar este enlace de TikTok. Verifica que no sea privado.", chat_id=message.chat.id, message_id=msg_espera.message_id)
        return

    item_id = str(datos.get("id", os.urandom(4).hex()))
    CACHE_ENLACES[item_id] = {
        "video": datos.get("play") or datos.get("wmplay"),
        "audio": datos.get("music"),
        "title": datos.get("title", "Audio de TikTok")
    }

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_video = types.InlineKeyboardButton("🎬 Descargar Video", callback_data=f"vid_{item_id}")
    btn_audio = types.InlineKeyboardButton("🎵 Descargar MP3", callback_data=f"aud_{item_id}")
    markup.add(btn_video, btn_audio)

    bot.edit_message_text(
        "✨ *¿Qué formato deseas descargar?*",
        chat_id=message.chat.id,
        message_id=msg_espera.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('vid_', 'aud_')))
def procesar_seleccion(call):
    user_id = call.from_user.id
    tipo, item_id = call.data.split('_', 1)
    
    info = CACHE_ENLACES.get(item_id)
    if not info:
        bot.answer_callback_query(call.id, "⚠️️ El enlace ha expirado. Envíalo de nuevo.", show_alert=True)
        return

    puede_descargar, tipo_usuario, _ = verificar_estado_usuario(user_id)
    if not puede_descargar:
        bot.answer_callback_query(call.id, "❌ Límite gratuito alcanzado.", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ *Descargando archivo...*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
    
    os.makedirs("descargas", exist_ok=True)
    archivo_local = None

    try:
        if tipo == "vid" and info.get("video"):
            archivo_local = f"descargas/{item_id}.mp4"
            if bajar_archivo(info["video"], archivo_local):
                bot.edit_message_text("📤 *Enviando video...*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
                with open(archivo_local, 'rb') as f:
                    bot.send_video(
                        call.message.chat.id,
                        f,
                        supports_streaming=True,
                        caption="🎬 *Video sin marca de agua listo*\n📢 *Canal:* @torico_cuba_db",
                        parse_mode="Markdown"
                    )
                if tipo_usuario == "free":
                    sumar_descarga(user_id)
                bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                bot.edit_message_text("❌ No se pudo descargar el video.", chat_id=call.message.chat.id, message_id=call.message.message_id)

        elif tipo == "aud" and info.get("audio"):
            archivo_local = f"descargas/{item_id}.mp3"
            if bajar_archivo(info["audio"], archivo_local):
                bot.edit_message_text("📤 *Enviando audio MP3...*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
                with open(archivo_local, 'rb') as f:
                    bot.send_audio(
                        call.message.chat.id,
                        f,
                        title=info.get("title", "TikTok Audio")[:40],
                        caption="🎵 *Audio extraído con éxito*\n📢 *Canal:* @torico_cuba_db",
                        parse_mode="Markdown"
                    )
                if tipo_usuario == "free":
                    sumar_descarga(user_id)
                bot.delete_message(call.message.chat.id, call.message.message_id)
            else:
                bot.edit_message_text("❌ No se pudo extraer el audio de este enlace.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Error al enviar: {e}", chat_id=call.message.chat.id, message_id=call.message.message_id)
    finally:
        if archivo_local and os.path.exists(archivo_local):
            try:
                os.remove(archivo_local)
            except Exception:
                pass

@bot.message_handler(func=lambda msg: msg.text and ("youtube.com" in msg.text or "youtu.be" in msg.text or "instagram.com" in msg.text))
def aviso_mantenimiento(message):
    bot.reply_to(
        message,
        "🛠 *Módulo en mantenimiento programado.*\n\n"
        "Actualmente YouTube e Instagram están en actualización de servidores.\n"
        "👉 Puedes seguir descargando *Videos y Audios MP3 de TikTok* con total normalidad.",
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    print("Iniciando bot con Video y MP3...")
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
