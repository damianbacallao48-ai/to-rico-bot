import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask

# ================= SERVIDOR WEB (HEALTHCHECK RAILWAY) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "OK", 200

# ================= CREDENCIALES EXACTAS =================
TELEGRAM_BOT_TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_CHAT_ID = 6731555041

JAP_API_KEY = "3532b6a51bcc7638bcc9841c5cc1d425"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True)

# ================= CATÁLOGO DE SERVICIOS Y COMBOS =================
SERVICIOS = {
    "ig_likes_1000": {
        "service_id": "1234",
        "nombre": "❤️ 1.000 Likes de Instagram",
        "precio_cup": 1000,
        "cantidad": 1000
    },
    "ig_followers_1000": {
        "service_id": "1001",
        "nombre": "👥 1.000 Seguidores de Instagram",
        "precio_cup": 3500,
        "cantidad": 1000
    },
    "tt_views_1000": {
        "service_id": "1002",
        "nombre": "👀 1.000 Vistas TikTok",
        "precio_cup": 1000,
        "cantidad": 1000
    },
    "tt_followers_1000": {
        "service_id": "1003",
        "nombre": "👤 1.000 Seguidores TikTok",
        "precio_cup": 3000,
        "cantidad": 1000
    },
    "combo_ig_1": {
        "service_id": "1001",
        "nombre": "🔥 Combo: 1.000 Seg + 500 Likes IG",
        "precio_cup": 5000,
        "cantidad": 1000
    }
}

user_data = {}
pending_orders = {}

def send_jap_order(service_id, link, quantity):
    payload = {
        "key": JAP_API_KEY,
        "action": "add",
        "service": str(service_id),
        "link": link,
        "quantity": str(quantity)
    }
    try:
        r = requests.post(JAP_API_URL, data=payload, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, data in SERVICIOS.items():
        markup.add(types.InlineKeyboardButton(f"{data['nombre']} ➔ {data['precio_cup']} CUP", callback_data=f"buy_{key}"))
    
    bot.reply_to(
        message,
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *IMPULSO REDES PRO* ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Selecciona el servicio que deseas adquirir:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['balance'])
def check_balance(message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    res = requests.post(JAP_API_URL, data={"key": JAP_API_KEY, "action": "balance"}).json()
    if "balance" in res:
        bot.reply_to(message, f"💰 Saldo en JAP: {res['balance']} {res.get('currency', 'USD')}")
    else:
        bot.reply_to(message, f"⚠️ Error JAP: {res.get('error', res)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    service_key = call.data.replace('buy_', '')
    service = SERVICIOS.get(service_key)
    chat_id = call.message.chat.id
    user_data[chat_id] = {'service_key': service_key, 'step': 'link'}
    
    bot.edit_message_text(
        f"Has seleccionado: *{service['nombre']}*\n"
        f"💰 Total: *{service['precio_cup']} CUP*\n\n"
        "🔗 *Envía el enlace directo de tu publicación o perfil:*",
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'link')
def handle_link(message):
    chat_id = message.chat.id
    link = message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://")):
        bot.reply_to(message, "⚠️ Envía un enlace válido (con http:// o https://)")
        return

    user_data[chat_id]['link'] = link
    user_data[chat_id]['step'] = 'receipt'
    s_key = user_data[chat_id]['service_key']
    service = SERVICIOS[s_key]

    bot.reply_to(
        message,
        f"✅ *Detalles de la orden:*\n"
        f"📦 {service['nombre']}\n"
        f"🔗 `{link}`\n"
        f"💵 Total: *{service['precio_cup']} CUP*\n\n"
        f"💳 Realiza el pago y envía aquí la *foto o captura del comprobante*.",
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    if user_data.get(chat_id, {}).get('step') != 'receipt':
        return

    photo_id = message.photo[-1].file_id
    order_id = str(message.message_id)
    s_key = user_data[chat_id]['service_key']
    service = SERVICIOS[s_key]
    link = user_data[chat_id]['link']

    pending_orders[order_id] = {
        'user_id': chat_id,
        'user_name': message.from_user.first_name,
        'service': service,
        'link': link
    }

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Aprobar y Enviar", callback_data=f"approve_{order_id}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{order_id}")
    )

    caption = (
        f"🔔 *Nuevo comprobante recibido:*\n\n"
        f"👤 Cliente: {message.from_user.first_name} (`{chat_id}`)\n"
        f"📦 {service['nombre']}\n"
        f"💰 Monto: {service['precio_cup']} CUP\n"
        f"🔗 Enlace: `{link}`"
    )

    bot.send_photo(ADMIN_CHAT_ID, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
    bot.reply_to(message, "✅ *Comprobante recibido con éxito.* En breves momentos será revisado.", parse_mode="Markdown")
    user_data.pop(chat_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_admin_action(call):
    action, order_id = call.data.split('_', 1)
    order = pending_orders.get(order_id)
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if not order:
        bot.answer_callback_query(call.id, "Esta orden ya fue tramitada.")
        return

    if action == "approve":
        res = send_jap_order(order["service"]["service_id"], order["link"], order["service"]["cantidad"])
        if "order" in res:
            jap_id = res["order"]
            bot.edit_message_caption(
                caption=f"{call.message.caption}\n\n✅ *Aprobado y Enviado a JAP*\n🆔 ID JAP: `{jap_id}`",
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="Markdown"
            )
            bot.send_message(
                order["user_id"],
                f"🎉 ¡Tu pago ha sido confirmado! Tu orden de *{order['service']['nombre']}* ya está en marcha."
            )
            bot.answer_callback_query(call.id, "¡Orden enviada a JAP con éxito!")
        else:
            err_msg = res.get("error", res)
            bot.send_message(ADMIN_CHAT_ID, f"⚠️ Error JAP: {err_msg}")
            bot.answer_callback_query(call.id, "Error en JAP")

    elif action == "reject":
        bot.edit_message_caption(
            caption=f"{call.message.caption}\n\n❌ *Comprobante Rechazado*",
            chat_id=chat_id,
            message_id=msg_id,
            parse_mode="Markdown"
        )
        bot.send_message(order["user_id"], "❌ Tu comprobante no pudo ser verificado. Contacta a soporte.")
        bot.answer_callback_query(call.id, "Orden rechazada")

def start_bot():
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    # Iniciar bot de Telegram en hilo secundario continuo
    t = threading.Thread(target=start_bot, daemon=True)
    t.start()
    
    # Iniciar Flask en hilo principal para que Railway detecte el puerto abierto y nunca cierre el contenedor
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
