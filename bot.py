import os
import json
import urllib.parse
import requests
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- CONFIGURACIÓN PRINCIPAL ---
BOT_TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_ID = 6731555041

API_URL = "https://justanotherpanel.com/api/v2"
API_KEY = "3625c0a8ec2d5e89b7172cfcbbc65955"

# --- NOTIFICACIÓN POR WHATSAPP (Opcional vía CallMeBot) ---
WHATSAPP_PHONE = "+5358960660"
CALLMEBOT_APIKEY = ""  # Si activas CallMeBot coloca aquí tu clave numérica

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATOS DE COBRO Y CONTACTO ---
DATOS_PAGO = {
    "tarjeta": "9238 1299 7952 7274",
    "titular": "Daemon",
    "telefono": "+5358960660",
    "telegram_contacto": "Daemon0110"
}

def enviar_whatsapp(texto):
    if not CALLMEBOT_APIKEY:
        return
    try:
        msg_encoded = urllib.parse.quote(texto)
        url = f"https://api.callmebot.com/whatsapp.php?phone={WHATSAPP_PHONE}&text={msg_encoded}&apikey={CALLMEBOT_APIKEY}"
        requests.get(url, timeout=10)
    except Exception:
        pass

# --- CATÁLOGO DE SERVICIOS Y COMBOS ---
PAQUETES = {
    "ig_likes": {
        "tipo": "simple",
        "red": "Instagram",
        "nombre": "❤️ 1.000 Likes de Instagram",
        "precio": 1000,
        "service_id": 5956,
        "cantidad": 1000,
        "tipo_link": "enlace de la publicación o reel"
    },
    "ig_seguidores": {
        "tipo": "simple",
        "red": "Instagram",
        "nombre": "👤 1.000 Seguidores Instagram (Garantía 30D)",
        "precio": 3500,
        "service_id": 7514,
        "cantidad": 1000,
        "tipo_link": "enlace de tu perfil público"
    },
    "tt_vistas": {
        "tipo": "simple",
        "red": "TikTok",
        "nombre": "👁️ 1.000 Vistas de TikTok (Súper Rápidas)",
        "precio": 1000,
        "service_id": 4412,
        "cantidad": 1000,
        "tipo_link": "enlace del video"
    },
    "tt_seguidores": {
        "tipo": "simple",
        "red": "TikTok",
        "nombre": "👥 1.000 Seguidores TikTok (Garantía 30D)",
        "precio": 3000,
        "service_id": 10090,
        "cantidad": 1000,
        "tipo_link": "enlace de tu perfil"
    },
    "combo_ig_completo": {
        "tipo": "combo",
        "red": "Combos",
        "nombre": "🔥 Combo IG: 1.000 Seguidores + 500 Likes",
        "precio": 5000,
        "subservicios": [
            {
                "service_id": 7514,
                "cantidad": 1000,
                "label": "Seguidores",
                "tipo_link": "enlace del perfil de Instagram"
            },
            {
                "service_id": 5956,
                "cantidad": 500,
                "label": "Likes",
                "tipo_link": "enlace de la publicación o reel"
            }
        ]
    }
}

user_sessions = {}
pedidos_pendientes = {}

# --- SERVIDOR WEB (RAILWAY) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot activo y operando."

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- MENÚ PRINCIPAL ---
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ig = types.InlineKeyboardButton("📸 Instagram", callback_data="cat_Instagram")
    btn_tt = types.InlineKeyboardButton("🎵 TikTok", callback_data="cat_TikTok")
    btn_combos = types.InlineKeyboardButton("🔥 Súper Combos", callback_data="cat_Combos")
    btn_support = types.InlineKeyboardButton("💬 Soporte / Contacto", callback_data="btn_soporte")
    markup.add(btn_ig, btn_tt)
    markup.add(btn_combos)
    markup.add(btn_support)

    texto = (
        f"👋 ¡Hola, *{message.from_user.first_name}*!\n\n"
        "Bienvenido a **Impulso Redes Pro**.\n"
        "Potencia tu cuenta con seguidores, likes y reproducciones garantizadas.\n\n"
        "Selecciona la red social o paquete que deseas:"
    )
    bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

# --- BOTÓN DE SOPORTE DIRECTO ---
@bot.callback_query_handler(func=lambda call: call.data == "btn_soporte")
def handle_soporte(call):
    bot.answer_callback_query(call.id)
    texto = (
        "💬 *Atención al Cliente y Soporte*\n\n"
        f"👤 Contacto directo: [@{DATOS_PAGO['telegram_contacto']}](https://t.me/{DATOS_PAGO['telegram_contacto']})\n"
        f"📱 Móvil / WhatsApp: `{DATOS_PAGO['telefono']}`\n\n"
        "Escríbenos si tienes dudas con tus pedidos, transferencias o servicios personalizados."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Escribir al Privado", url=f"https://t.me/{DATOS_PAGO['telegram_contacto']}"))
    markup.add(types.InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start"))
    bot.send_message(call.message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

# --- LISTA DE OFERTAS POR CATEGORÍA ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def handle_category(call):
    bot.answer_callback_query(call.id)
    cat = call.data.split("_")[1]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for pkg_id, pkg in PAQUETES.items():
        if pkg["red"] == cat:
            markup.add(types.InlineKeyboardButton(f"{pkg['nombre']} - {pkg['precio']:,} CUP", callback_data=f"buy_{pkg_id}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start"))
    bot.edit_message_text(f"🔥 *Ofertas disponibles en {cat}:*", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📸 Instagram", callback_data="cat_Instagram"),
               types.InlineKeyboardButton("🎵 TikTok", callback_data="cat_TikTok"))
    markup.add(types.InlineKeyboardButton("🔥 Súper Combos", callback_data="cat_Combos"))
    markup.add(types.InlineKeyboardButton("💬 Soporte / Contacto", callback_data="btn_soporte"))
    bot.edit_message_text("Selecciona una opción:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- SELECCIÓN DEL SERVICIO ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    bot.answer_callback_query(call.id)
    pkg_id = call.data.split("_", 1)[1]
    pkg = PAQUETES[pkg_id]
    user_id = str(call.from_user.id)

    if pkg["tipo"] == "simple":
        user_sessions[user_id] = {
            "pkg_id": pkg_id,
            "step": "AWAIT_LINK"
        }
        texto = f"Has seleccionado: *{pkg['nombre']}*\n💰 *Precio:* {pkg['precio']:,} CUP\n\n👉 Envía el *{pkg['tipo_link']}*:"
    else:
        user_sessions[user_id] = {
            "pkg_id": pkg_id,
            "step": "AWAIT_COMBO_LINK",
            "sub_index": 0,
            "links": []
        }
        sub = pkg["subservicios"][0]
        texto = (
            f"Has seleccionado: *{pkg['nombre']}*\n"
            f"💰 *Precio:* {pkg['precio']:,} CUP\n\n"
            f"👉 Envía el primer enlace (*{sub['tipo_link']}*):"
        )

    bot.send_message(call.message.chat.id, texto, parse_mode="Markdown")

# --- RECEPCIÓN DE ENLACES ---
@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_sessions and user_sessions[str(msg.from_user.id)].get("step") in ["AWAIT_LINK", "AWAIT_COMBO_LINK"])
def handle_link_input(message):
    user_id = str(message.from_user.id)
    link = message.text.strip()

    if not link.startswith("http"):
        bot.reply_to(message, "⚠️ El enlace debe comenzar con `http://` o `https://`. Inténtalo de nuevo:")
        return

    session = user_sessions[user_id]
    pkg = PAQUETES[session["pkg_id"]]

    if session["step"] == "AWAIT_LINK":
        session["links"] = [link]
        session["step"] = "AWAIT_PAYMENT_PROOF"
    elif session["step"] == "AWAIT_COMBO_LINK":
        session["links"].append(link)
        session["sub_index"] += 1
        if session["sub_index"] < len(pkg["subservicios"]):
            siguiente = pkg["subservicios"][session["sub_index"]]
            bot.send_message(message.chat.id, f"✅ Recibido. Ahora envía el *{siguiente['tipo_link']}*:", parse_mode="Markdown")
            return
        else:
            session["step"] = "AWAIT_PAYMENT_PROOF"

    texto = (
        f"✅ *Enlaces registrados.*\n\n"
        f"📌 *Detalles del pedido:*\n"
        f"• Servicio: *{pkg['nombre']}*\n"
        f"• Total a pagar: *{pkg['precio']:,} CUP*\n\n"
        "💳 *Datos de transferencia (Transfermóvil / EnZona):*\n"
        f"• Tarjeta: `{DATOS_PAGO['tarjeta']}` *(toca para copiar)*\n"
        f"• Titular: *{DATOS_PAGO['titular']}*\n"
        f"• Móvil de confirmación: `{DATOS_PAGO['telefono']}`\n\n"
        f"🆘 *Dudas:* [@{DATOS_PAGO['telegram_contacto']}](https://t.me/{DATOS_PAGO['telegram_contacto']})\n\n"
        "📸 **Envía la captura de tu transferencia aquí mismo** para validar y activar tu pedido."
    )
    bot.send_message(message.chat.id, texto, parse_mode="Markdown")

# --- RECEPCIÓN DEL COMPROBANTE DE PAGO ---
@bot.message_handler(content_types=['photo'], func=lambda msg: str(msg.from_user.id) in user_sessions and user_sessions[str(msg.from_user.id)].get("step") == "AWAIT_PAYMENT_PROOF")
def handle_payment_proof(message):
    user_id = str(message.from_user.id)
    session = user_sessions[user_id]
    pkg = PAQUETES[session["pkg_id"]]
    order_key = f"{user_id}_{message.message_id}"

    pedidos_pendientes[order_key] = {
        "user_id": user_id,
        "pkg": pkg,
        "links": session["links"]
    }

    bot.send_message(
        message.chat.id,
        "⏳ *Comprobante recibido con éxito.*\nEl administrador revisará el pago en unos instantes y tu pedido se procesará automáticamente.",
        parse_mode="Markdown"
    )

    # Notificación a tu cuenta privada de Telegram
    file_id = message.photo[-1].file_id
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Aprobar y Enviar", callback_data=f"app_{order_key}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"rej_{order_key}")
    )

    caption = (
        f"🔔 *Nuevo comprobante recibido:*\n\n"
        f"👤 Cliente: [{message.from_user.first_name}](tg://user?id={user_id}) (`{user_id}`)\n"
        f"📦 Servicio: {pkg['nombre']}\n"
        f"💰 Monto: *{pkg['precio']:,} CUP*\n"
        f"🔗 Enlaces: {', '.join(session['links'])}"
    )
    bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")

    # Alerta a WhatsApp
    msg_wa = (
        f"🔔 NUEVO PAGO RECIBIDO\n\n"
        f"• Cliente: {message.from_user.first_name}\n"
        f"• Paquete: {pkg['nombre']}\n"
        f"• Monto: {pkg['precio']:,} CUP\n\n"
        f"Abre Telegram para aprobar la orden."
    )
    enviar_whatsapp(msg_wa)

    del user_sessions[user_id]

# --- APROBACIÓN O RECHAZO POR EL ADMINISTRADOR ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("app_") or call.data.startswith("rej_"))
def handle_admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "No tienes permisos.")
        return

    action, order_key = call.data.split("_", 1)
    order = pedidos_pendientes.get(order_key)

    if not order:
        bot.answer_callback_query(call.id, "Este pedido ya fue procesado o no existe.")
        return

    user_id = order["user_id"]
    pkg = order["pkg"]
    links = order["links"]

    if action == "app":
        bot.answer_callback_query(call.id, "Enviando a JAP...")
        ordenes_creadas = []

        if pkg["tipo"] == "simple":
            payload = {
                "key": API_KEY,
                "action": "add",
                "service": pkg["service_id"],
                "link": links[0],
                "quantity": pkg["cantidad"]
            }
            try:
                res = requests.post(API_URL, data=payload, timeout=20).json()
                if "order" in res:
                    ordenes_creadas.append(str(res["order"]))
            except Exception:
                pass
        else:
            for idx, sub in enumerate(pkg["subservicios"]):
                payload = {
                    "key": API_KEY,
                    "action": "add",
                    "service": sub["service_id"],
                    "link": links[idx],
                    "quantity": sub["cantidad"]
                }
                try:
                    res = requests.post(API_URL, data=payload, timeout=20).json()
                    if "order" in res:
                        ordenes_creadas.append(f"{sub['label']}: #{res['order']}")
                except Exception:
                    pass

        if ordenes_creadas:
            ids_str = ", ".join(ordenes_creadas)
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"{call.message.caption}\n\n✅ *Aprobado.* Orden JAP ID: `{ids_str}`",
                parse_mode="Markdown"
            )
            bot.send_message(
                user_id,
                f"🎉 *¡Pago confirmado y orden en proceso!*\n\n"
                f"📌 Paquete: {pkg['nombre']}\n"
                f"🆔 Pedido ID: `{ids_str}`\n\n"
                "La entrega ha comenzado automáticamente.",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(ADMIN_ID, "⚠️ Ocurrió un error al enviar a JAP (posible falta de saldo en tu panel).")

    elif action == "rej":
        bot.answer_callback_query(call.id, "Pedido rechazado.")
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=f"{call.message.caption}\n\n❌ *Rechazado por el administrador.*",
            parse_mode="Markdown"
        )
        bot.send_message(user_id, "❌ Lo sentimos, tu comprobante no pudo ser verificado. Contacta con soporte.")

    del pedidos_pendientes[order_key]

# --- INICIO ---
if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
