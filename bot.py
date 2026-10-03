import os
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask
from telebot import TeleBot, types

# Importar motores independientes
import motor_tiktok
import motor_youtube
import motor_instagram

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
    return "Bot Modular Activo"

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
    raw_text = message.text.strip()

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
        if "tiktok.com" in raw_text:
            archivo = motor_tiktok.descargar(raw_text)
        elif "youtube.com" in raw_text or "youtu.be" in raw_text:
            archivo = motor_youtube.descargar(raw_text)
        elif "instagram.com" in raw_text or "instagr.am" in raw_text:
            archivo = motor_instagram.descargar(raw_text)

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
    print("Iniciando servicio modular...")
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
