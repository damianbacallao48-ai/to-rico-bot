import os
import glob
import re
import sqlite3
import threading
import shutil
from datetime import datetime, timedelta

import requests
import instaloader
import yt_dlp
import imageio_ffmpeg
from flask import Flask
from telebot import TeleBot, types


# ============================================================
# CONFIGURACIÓN
# ============================================================
BOT_TOKEN = "8875681851:AAF-LUfVC7MoSW_Mwxva82NVxVnaknQpAfU"

ADMIN_ID = 6731555041
CANAL_OBLIGATORIO = "@torico_cuba_db"
CANAL_ENLACE = "https://t.me/torico_cuba_db"

LIMITE_GRATIS = 2
ADMIN_USER = "@torico_cuba_db"

DB_FILE = "usuarios.db"

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Cache temporal de enlaces
CACHE_ENLACES = {}

# Evita problemas de concurrencia con SQLite
DB_LOCK = threading.RLock()

# Ruta al binario ejecutable de ffmpeg provisto por imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# ============================================================
# INSTALOADER
# ============================================================
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    quiet=True,
)


# ============================================================
# SERVIDOR WEB
# ============================================================
@app.route("/")
def home():
    return "Bot en línea"


def iniciar_servidor_web():
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ============================================================
# BASE DE DATOS
# ============================================================
def obtener_conexion():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def inicializar_bd():
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    user_id INTEGER PRIMARY KEY,
                    descargas INTEGER DEFAULT 0,
                    vip_hasta TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def verificar_estado_usuario(user_id):
    if user_id == ADMIN_ID:
        return True, "admin", "👑 Dueño / Acceso Total"

    with DB_LOCK:
        conn = obtener_conexion()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT descargas, vip_hasta FROM usuarios WHERE user_id = ?",
                (user_id,),
            )
            res = cursor.fetchone()
            ahora = datetime.now()

            if not res:
                cursor.execute(
                    "INSERT INTO usuarios (user_id, descargas, vip_hasta) "
                    "VALUES (?, 0, NULL)",
                    (user_id,),
                )
                conn.commit()
                return (
                    True,
                    "free",
                    f"Prueba gratuita (0/{LIMITE_GRATIS} usadas)",
                )

            descargas, vip_hasta_str = res

            if vip_hasta_str:
                try:
                    vip_hasta = datetime.strptime(
                        vip_hasta_str, "%Y-%m-%d %H:%M:%S"
                    )
                    if ahora < vip_hasta:
                        dias_restantes = max(
                            1, (vip_hasta - ahora).days + 1
                        )
                        return (
                            True,
                            "vip",
                            f"⭐ Miembro VIP ({dias_restantes} días activos)",
                        )
                except (ValueError, TypeError):
                    pass

            if descargas < LIMITE_GRATIS:
                return (
                    True,
                    "free",
                    f"Prueba gratuita ({descargas}/{LIMITE_GRATIS} usadas)",
                )

            return (
                False,
                "expired",
                f"Agotado ({descargas}/{LIMITE_GRATIS})",
            )
        finally:
            conn.close()


def sumar_descarga(user_id):
    if user_id == ADMIN_ID:
        return

    with DB_LOCK:
        conn = obtener_conexion()
        try:
            conn.execute(
                """
                INSERT INTO usuarios (user_id, descargas, vip_hasta)
                VALUES (?, 1, NULL)
                ON CONFLICT(user_id)
                DO UPDATE SET descargas = descargas + 1
                """,
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()


def activar_vip_15_dias(user_id):
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            ahora = datetime.now()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT vip_hasta FROM usuarios WHERE user_id = ?",
                (user_id,),
            )
            res = cursor.fetchone()
            fecha_base = ahora

            if res and res[0]:
                try:
                    fecha_existente = datetime.strptime(
                        res[0], "%Y-%m-%d %H:%M:%S"
                    )
                    if fecha_existente > ahora:
                        fecha_base = fecha_existente
                except (ValueError, TypeError):
                    pass

            nueva_fecha = fecha_base + timedelta(days=15)
            fecha_str = nueva_fecha.strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                """
                INSERT INTO usuarios (user_id, descargas, vip_hasta)
                VALUES (?, 0, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET vip_hasta = excluded.vip_hasta
                """,
                (user_id, fecha_str),
            )
            conn.commit()
            return fecha_str
        finally:
            conn.close()


# ============================================================
# SUSCRIPCIÓN AL CANAL
# ============================================================
def esta_suscrito(user_id):
    if user_id == ADMIN_ID:
        return True

    try:
        miembro = bot.get_chat_member(CANAL_OBLIGATORIO, user_id)
        return miembro.status in (
            "creator",
            "administrator",
            "member",
        )
    except Exception as e:
        print(f"Error comprobando suscripción de {user_id}: {e}")
        return False


# ============================================================
# DESCARGA HTTP
# ============================================================
def bajar_archivo(url, destino):
    if not url:
        return False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/140 Safari/537.36"
        )
    }

    try:
        with requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=(15, 60),
            allow_redirects=True,
        ) as req:
            req.raise_for_status()
            with open(destino, "wb") as f:
                for chunk in req.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        return os.path.exists(destino) and os.path.getsize(destino) > 50 * 1024

    except Exception as e:
        print(f"Error descargando archivo: {e}")
        try:
            if os.path.exists(destino):
                os.remove(destino)
        except Exception:
            pass
        return False


# ============================================================
# TIKTOK
# ============================================================
def obtener_datos_tiktok(url):
    try:
        clean_url = url.split("?")[0].strip()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            )
        }

        api_url = "https://www.tikwm.com/api/"
        response = requests.get(
            api_url,
            params={"url": clean_url},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        resultado = response.json()

        if resultado.get("code") == 0:
            return resultado.get("data") or {}

        print(f"TikTok API respondió: {resultado}")
    except Exception as e:
        print(f"Error TikTok API: {e}")

    return None


# ============================================================
# INSTAGRAM
# ============================================================
def extraer_shortcode_instagram(url):
    match = re.search(
        r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)",
        url,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def descargar_instagram_instaloader(url):
    carpeta_destino = None
    try:
        shortcode = extraer_shortcode_instagram(url)
        if not shortcode:
            return None, None

        carpeta_destino = os.path.abspath(
            os.path.join("descargas_instagram", shortcode)
        )
        os.makedirs(carpeta_destino, exist_ok=True)

        post = instaloader.Post.from_shortcode(L.context, shortcode)
        if not post.is_video:
            return None, carpeta_destino

        L.download_post(post, target=carpeta_destino)
        videos = glob.glob(os.path.join(carpeta_destino, "*.mp4"))

        if videos:
            videos.sort(
                key=lambda archivo: os.path.getmtime(archivo),
                reverse=True,
            )
            return videos[0], carpeta_destino

        return None, carpeta_destino
    except Exception as e:
        print(f"Error Instaloader: {e}")
        return None, carpeta_destino


def limpiar_carpeta(carpeta):
    if not carpeta:
        return
    try:
        if os.path.exists(carpeta):
            shutil.rmtree(carpeta, ignore_errors=True)
            padre = os.path.dirname(carpeta)
            if padre and os.path.isdir(padre) and not os.listdir(padre):
                os.rmdir(padre)
    except Exception as e:
        print(f"Error limpiando archivos: {e}")


def descargar_instagram(url):
    os.makedirs("descargas", exist_ok=True)
    clean_url = url.split("?")[0].strip()
    item_id = os.urandom(6).hex()
    salida = os.path.abspath(os.path.join("descargas", f"ig_{item_id}.mp4"))

    opciones = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": salida,
        "format": "best[ext=mp4]/best",
        "ffmpeg_location": FFMPEG_PATH,
    }

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([clean_url])

        if os.path.exists(salida) and os.path.getsize(salida) > 50 * 1024:
            return salida, None
    except Exception as e:
        print(f"Error yt-dlp con Instagram: {e}")

    archivo_loader, carpeta_temp = descargar_instagram_instaloader(clean_url)
    return archivo_loader, carpeta_temp


# ============================================================
# YOUTUBE
# ============================================================
def es_url_youtube(url):
    url_lower = url.lower()
    return (
        "youtube.com/" in url_lower
        or "youtu.be/" in url_lower
        or "youtube-nocookie.com/" in url_lower
    )


def obtener_info_youtube(url):
    try:
        clean_url = url.split("?")[0].strip()
        opciones = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(opciones) as ydl:
            info = ydl.extract_info(clean_url, download=False)

        if not info:
            return None

        return {
            "id": info.get("id"),
            "title": info.get("title") or "Video de YouTube",
            "url": clean_url,
            "duration": info.get("duration") or 0,
            "webpage_url": info.get("webpage_url") or clean_url,
        }
    except Exception as e:
        print(f"Error obteniendo info de YouTube: {e}")
        return None


def descargar_youtube(url, tipo, item_id):
    os.makedirs("descargas", exist_ok=True)

    if tipo == "video":
        salida = os.path.abspath(
            os.path.join("descargas", f"youtube_{item_id}.mp4")
        )
        opciones = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ffmpeg_location": FFMPEG_PATH,
            "outtmpl": salida,
            "format": "best[ext=mp4]/best",
        }

    elif tipo == "audio":
        salida = os.path.abspath(
            os.path.join("descargas", f"youtube_{item_id}.mp3")
        )
        opciones = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ffmpeg_location": FFMPEG_PATH,
            "outtmpl": salida,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
    else:
        return None

    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])

        if os.path.exists(salida):
            return salida

        candidatos = glob.glob(
            os.path.join("descargas", f"youtube_{item_id}.*")
        )
        if candidatos:
            candidatos.sort(
                key=lambda x: os.path.getmtime(x),
                reverse=True,
            )
            return candidatos[0]

    except Exception as e:
        print(f"Error descargando YouTube: {e}")

    return None


# ============================================================
# /START
# ============================================================
@bot.message_handler(commands=["start"])
def bienvenida(message):
    user_id = message.from_user.id
    _, _, texto_estado = verificar_estado_usuario(user_id)

    texto = (
        "⚡ <b>¡Bienvenido al Descargador Pro!</b>\n\n"
        "Envía el enlace de cualquier video:\n"
        "• 🎵 <b>TikTok</b> (Video HD sin marca o Audio MP3)\n"
        "• 📸 <b>Instagram</b> (Reels y Posts en video)\n"
        "• ▶️ <b>YouTube</b> (Video y MP3)\n\n"
        f"📊 <b>Tu plan:</b> <code>{texto_estado}</code>\n"
        f"🆔 <b>Tu ID:</b> <code>{user_id}</code>\n\n"
        "👉 <b>Pega el enlace aquí abajo:</b>"
    )

    bot.reply_to(message, texto, parse_mode="HTML")


# ============================================================
# /DARVIP
# ============================================================
@bot.message_handler(commands=["darvip"])
def dar_vip_comando(message):
    if message.from_user.id != ADMIN_ID:
        return

    partes = message.text.split()
    if len(partes) < 2:
        bot.reply_to(
            message,
            "Uso: <code>/darvip ID_DEL_USUARIO</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(partes[1])
        fecha_fin = activar_vip_15_dias(target_id)

        bot.reply_to(
            message,
            (
                f"✅ Usuario <code>{target_id}</code> activado como "
                f"VIP por 15 días.\n\n"
                f"📅 Hasta: <code>{fecha_fin}</code>"
            ),
            parse_mode="HTML",
        )

        try:
            bot.send_message(
                target_id,
                (
                    "🎉 <b>¡Tu suscripción VIP ha sido activada!</b>\n\n"
                    "Tienes descargas ilimitadas durante 15 días.\n"
                    f"📅 Hasta: <code>{fecha_fin}</code>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"No se pudo avisar al usuario VIP: {e}")

    except ValueError:
        bot.reply_to(message, "❌ El ID debe ser un número entero.")


# ============================================================
# PROCESAR ENLACES
# ============================================================
@bot.message_handler(
    func=lambda msg: bool(
        msg.text
        and ("http://" in msg.text or "https://" in msg.text)
    )
)
def recibir_enlace(message):
    user_id = message.from_user.id
    raw_text = message.text.strip()

    # Suscripción
    if not esta_suscrito(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "📢 Unirme al Canal",
                url=CANAL_ENLACE,
            )
        )
        bot.reply_to(
            message,
            (
                "⚠️ <b>Antes de descargar debes unirte a nuestro canal.</b>\n\n"
                "Después de unirte, vuelve a enviar el enlace."
            ),
            reply_markup=markup,
            parse_mode="HTML",
        )
        return

    # Límite / VIP
    puede_descargar, tipo_usuario, _ = verificar_estado_usuario(user_id)
    if not puede_descargar:
        contacto_link = f"https://t.me/{ADMIN_USER.replace('@', '')}"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "⭐ Adquirir VIP (15 días)",
                url=contacto_link,
            )
        )
        texto_bloqueo = (
            "❌ <b>Has alcanzado el límite de 2 descargas gratuitas.</b>\n\n"
            "🌟 <b>Pase VIP</b> (15 días de acceso ilimitado)\n"
            f"🆔 <b>Tu ID:</b> <code>{user_id}</code>\n\n"
            "Toca el botón para solicitar la activación."
        )
        bot.reply_to(
            message,
            texto_bloqueo,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return

    # YouTube
    if es_url_youtube(raw_text):
        msg_espera = bot.reply_to(
            message,
            "🔍 <b>Analizando YouTube...</b>",
            parse_mode="HTML",
        )

        info = obtener_info_youtube(raw_text)
        if not info:
            bot.edit_message_text(
                "❌ No se pudo procesar este enlace de YouTube.",
                chat_id=message.chat.id,
                message_id=msg_espera.message_id,
            )
            return

        item_id = str(info.get("id") or os.urandom(6).hex())
        CACHE_ENLACES[item_id] = {
            "youtube": True,
            "url": info["url"],
            "title": info["title"],
            "created": datetime.now(),
        }

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "▶️ Descargar Video",
                callback_data=f"ytv_{item_id}",
            ),
            types.InlineKeyboardButton(
                "🎵 Descargar MP3",
                callback_data=f"yta_{item_id}",
            ),
        )

        bot.edit_message_text(
            (
                "🎬 <b>Video encontrado</b>\n\n"
                f"📌 <b>{info['title'][:100]}</b>\n\n"
                "¿Qué deseas descargar?"
            ),
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return

    # TikTok
    if "tiktok.com" in raw_text.lower():
        msg_espera = bot.reply_to(
            message,
            "🔍 <b>Analizando TikTok...</b>",
            parse_mode="HTML",
        )

        datos = obtener_datos_tiktok(raw_text)
        if not datos:
            bot.edit_message_text(
                "❌ No se pudo procesar este enlace de TikTok.\n"
                "Asegúrate de que el video sea accesible.",
                chat_id=message.chat.id,
                message_id=msg_espera.message_id,
            )
            return

        item_id = str(datos.get("id") or os.urandom(6).hex())
        CACHE_ENLACES[item_id] = {
            "video": datos.get("play") or datos.get("wmplay"),
            "audio": datos.get("music"),
            "title": datos.get("title") or "Audio de TikTok",
            "created": datetime.now(),
        }

        if len(CACHE_ENLACES) > 200:
            elementos = list(CACHE_ENLACES.items())
            elementos.sort(key=lambda x: x[1].get("created", datetime.min))
            for key, _ in elementos[:50]:
                CACHE_ENLACES.pop(key, None)

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_video = types.InlineKeyboardButton(
            "🎬 Descargar Video",
            callback_data=f"vid_{item_id}",
        )
        btn_audio = types.InlineKeyboardButton(
            "🎵 Descargar MP3",
            callback_data=f"aud_{item_id}",
        )
        markup.add(btn_video, btn_audio)

        bot.edit_message_text(
            "✨ <b>¿Qué deseas descargar?</b>",
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return

    # Instagram
    if "instagram.com" in raw_text.lower() or "instagr.am" in raw_text.lower():
        msg_espera = bot.reply_to(
            message,
            "⏳ <b>Descargando de Instagram...</b>",
            parse_mode="HTML",
        )

        archivo_video, carpeta_borrar = descargar_instagram(raw_text)

        if archivo_video and os.path.exists(archivo_video):
            try:
                bot.edit_message_text(
                    "📤 <b>Enviando Reel...</b>",
                    chat_id=message.chat.id,
                    message_id=msg_espera.message_id,
                    parse_mode="HTML",
                )

                with open(archivo_video, "rb") as f:
                    bot.send_video(
                        message.chat.id,
                        f,
                        supports_streaming=True,
                        caption=(
                            "📸 <b>Video de Instagram descargado</b>\n"
                            "📢 <b>Canal oficial:</b> @torico_cuba_db"
                        ),
                        parse_mode="HTML",
                    )

                if tipo_usuario == "free":
                    sumar_descarga(user_id)

                try:
                    bot.delete_message(
                        message.chat.id,
                        msg_espera.message_id,
                    )
                except Exception:
                    pass

            except Exception as e:
                print(f"Error enviando Instagram: {e}")
                try:
                    bot.edit_message_text(
                        "❌ Error enviando el video a Telegram.",
                        chat_id=message.chat.id,
                        message_id=msg_espera.message_id,
                    )
                except Exception:
                    pass
            finally:
                if carpeta_borrar:
                    limpiar_carpeta(carpeta_borrar)
                if os.path.exists(archivo_video):
                    try:
                        os.remove(archivo_video)
                    except Exception:
                        pass
        else:
            if carpeta_borrar:
                limpiar_carpeta(carpeta_borrar)

            try:
                bot.edit_message_text(
                    "❌ No se pudo descargar este video de Instagram.\n\n"
                    "Puede que la publicación sea privada o requiera iniciar sesión.",
                    chat_id=message.chat.id,
                    message_id=msg_espera.message_id,
                )
            except Exception:
                pass
        return

    # Otra plataforma
    bot.reply_to(
        message,
        (
            "💡 <b>Plataformas compatibles actualmente:</b>\n\n"
            "• 🎵 <b>TikTok</b> — Video y MP3\n"
            "• 📸 <b>Instagram</b> — Reels y Posts en video\n"
            "• ▶️ <b>YouTube</b> — Video y MP3"
        ),
        parse_mode="HTML",
    )


# ============================================================
# BOTONES CALLBACK
# ============================================================
@bot.callback_query_handler(
    func=lambda call: call.data.startswith(("vid_", "aud_", "ytv_", "yta_"))
)
def procesar_seleccion(call):
    user_id = call.from_user.id

    # YouTube
    if call.data.startswith(("ytv_", "yta_")):
        tipo_yt, item_id_yt = call.data.split("_", 1)
        info_yt = CACHE_ENLACES.get(item_id_yt)

        if not info_yt or not info_yt.get("youtube"):
            bot.answer_callback_query(
                call.id,
                "⚠️ Enlace expirado. Envíalo de nuevo.",
                show_alert=True,
            )
            return

        creado_yt = info_yt.get("created")
        if creado_yt and datetime.now() - creado_yt > timedelta(minutes=30):
            CACHE_ENLACES.pop(item_id_yt, None)
            bot.answer_callback_query(
                call.id,
                "⚠️ Enlace expirado. Envíalo de nuevo.",
                show_alert=True,
            )
            return

        puede_descargar_yt, tipo_usuario_yt, _ = verificar_estado_usuario(user_id)
        if not puede_descargar_yt:
            bot.answer_callback_query(
                call.id,
                "❌ Has alcanzado el límite gratuito.",
                show_alert=True,
            )
            return

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "⏳ <b>Descargando de YouTube...</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )
        except Exception:
            pass

        archivo_yt = None
        try:
            tipo_descarga = "video" if tipo_yt == "ytv" else "audio"
            archivo_yt = descargar_youtube(
                info_yt["url"],
                tipo_descarga,
                item_id_yt,
            )

            if not archivo_yt or not os.path.exists(archivo_yt):
                bot.edit_message_text(
                    "❌ No se pudo descargar el contenido de YouTube.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )
                return

            bot.edit_message_text(
                "📤 <b>Enviando archivo...</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )

            with open(archivo_yt, "rb") as f:
                if tipo_descarga == "video":
                    bot.send_video(
                        call.message.chat.id,
                        f,
                        supports_streaming=True,
                        caption=(
                            "▶️ <b>Video de YouTube listo</b>\n"
                            "📢 <b>Canal:</b> @torico_cuba_db"
                        ),
                        parse_mode="HTML",
                    )
                else:
                    bot.send_audio(
                        call.message.chat.id,
                        f,
                        title=info_yt.get("title", "Audio de YouTube")[:40],
                        caption=(
                            "🎵 <b>Audio de YouTube listo</b>\n"
                            "📢 <b>Canal:</b> @torico_cuba_db"
                        ),
                        parse_mode="HTML",
                    )

            if tipo_usuario_yt == "free":
                sumar_descarga(user_id)

            try:
                bot.delete_message(
                    call.message.chat.id,
                    call.message.message_id,
                )
            except Exception:
                pass

        except Exception as e:
            print(f"Error procesando YouTube: {e}")
            try:
                bot.edit_message_text(
                    "❌ Ocurrió un error al descargar o enviar el archivo.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )
            except Exception:
                pass
        finally:
            if archivo_yt and os.path.exists(archivo_yt):
                try:
                    os.remove(archivo_yt)
                except Exception:
                    pass
            CACHE_ENLACES.pop(item_id_yt, None)
        return

    # TikTok
    try:
        tipo, item_id = call.data.split("_", 1)
    except ValueError:
        bot.answer_callback_query(call.id, "❌ Solicitud inválida.", show_alert=True)
        return

    info = CACHE_ENLACES.get(item_id)
    if not info:
        bot.answer_callback_query(call.id, "⚠️ Enlace expirado. Envíalo de nuevo.", show_alert=True)
        return

    creado = info.get("created")
    if creado and datetime.now() - creado > timedelta(minutes=30):
        CACHE_ENLACES.pop(item_id, None)
        bot.answer_callback_query(call.id, "⚠️ Enlace expirado. Envíalo de nuevo.", show_alert=True)
        return

    puede_descargar, tipo_usuario, _ = verificar_estado_usuario(user_id)
    if not puede_descargar:
        bot.answer_callback_query(call.id, "❌ Has alcanzado el límite gratuito.", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    try:
        bot.edit_message_text(
            "⏳ <b>Descargando archivo...</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
    except Exception:
        pass

    os.makedirs("descargas", exist_ok=True)
    archivo_local = None

    try:
        if tipo == "vid":
            video_url = info.get("video")
            if not video_url:
                bot.edit_message_text(
                    "❌ TikTok no proporcionó un enlace de video.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )
                return

            archivo_local = os.path.join("descargas", f"{item_id}.mp4")

            if bajar_archivo(video_url, archivo_local):
                bot.edit_message_text(
                    "📤 <b>Enviando video...</b>",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                )

                with open(archivo_local, "rb") as f:
                    bot.send_video(
                        call.message.chat.id,
                        f,
                        supports_streaming=True,
                        caption=(
                            "🎬 <b>Video listo</b>\n"
                            "📢 <b>Canal:</b> @torico_cuba_db"
                        ),
                        parse_mode="HTML",
                    )

                if tipo_usuario == "free":
                    sumar_descarga(user_id)

                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
            else:
                bot.edit_message_text(
                    "❌ No se pudo descargar el video.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )

        elif tipo == "aud":
            audio_url = info.get("audio")
            if not audio_url:
                bot.edit_message_text(
                    "❌ TikTok no proporcionó un enlace de audio.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )
                return

            archivo_local = os.path.join("descargas", f"{item_id}.mp3")

            if bajar_archivo(audio_url, archivo_local):
                bot.edit_message_text(
                    "📤 <b>Enviando audio MP3...</b>",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML",
                )

                with open(archivo_local, "rb") as f:
                    bot.send_audio(
                        call.message.chat.id,
                        f,
                        title=(info.get("title") or "Audio de TikTok")[:40],
                        caption=(
                            "🎵 <b>Audio extraído con éxito</b>\n"
                            "📢 <b>Canal:</b> @torico_cuba_db"
                        ),
                        parse_mode="HTML",
                    )

                if tipo_usuario == "free":
                    sumar_descarga(user_id)

                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except Exception:
                    pass
            else:
                bot.edit_message_text(
                    "❌ No se pudo extraer el audio.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                )

    except Exception as e:
        print(f"Error procesando TikTok: {e}")
        try:
            bot.edit_message_text(
                "❌ Ocurrió un error al enviar el archivo.\n"
                "Inténtalo nuevamente.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
            )
        except Exception:
            pass
    finally:
        if archivo_local and os.path.exists(archivo_local):
            try:
                os.remove(archivo_local)
            except Exception:
                pass
        CACHE_ENLACES.pop(item_id, None)


# ============================================================
# ARRANQUE
# ============================================================
if __name__ == "__main__":
    print("Inicializando base de datos...")
    inicializar_bd()

    print("Iniciando servidor web...")
    threading.Thread(
        target=iniciar_servidor_web,
        daemon=True,
    ).start()

    print("Bot iniciado correctamente.")

    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=True,
            )
        except Exception as e:
            print(f"Error del polling: {e}")
            print("Reintentando en 5 segundos...")
            threading.Event().wait(5)
