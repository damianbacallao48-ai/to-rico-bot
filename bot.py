import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask

# ================= SERVIDOR WEB (MANTIENE ACTIVO RAILWAY) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "⚡ Impulso Redes Pro - Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= CREDENCIALES EXACTAS =================
TELEGRAM_BOT_TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_CHAT_ID = 6731555041

JAP_API_KEY = "3532b6a51bcc7638bcc9841c5cc1d425"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ================= CATÁLOGO DE SERVICIOS Y OFERTAS =================
SERVICIOS = {
    # Instagram
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
    # TikTok
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
    # Combos y Promociones
    "combo_ig_1": {
        "service_id": "1001",
        "nombre": "🔥 Combo Pro: 1.000 Seg + 500 Likes IG",
        "precio_cup": 5000,
        "cantidad": 1000
    }
}

user_data = {}
pending_orders = {}

# ================= FUNCIÓN DE ENVÍO A JAP =================
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

# ================= MENÚ PRINCIPAL =================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Botones ordenados y estilizados
    for key, data in SERVICIOS.items():
        markup.add(
            types.InlineKeyboardButton(
                f"{data['nombre']} ➔ {data['precio_cup']} CUP", 
                callback_data=f"buy_{key}"
            )
        )
    
    texto_bienvenida = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *IMPULSO REDES PRO* ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Potencia tu presencia digital al instante con la mejor entrega y garantía.\n\n"
        "👇 *Selecciona una de nuestras ofertas activas:*"
    )
    
    bot.reply_to(message, texto_bienvenida, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['balance'])
def check_balance(message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    res = requests.post(JAP_API_URL, data={"key": JAP_API_KEY, "action": "balance"}).json()
    if "balance" in res:
        bot.reply_to(message, f"💳 *Saldo disponible en JAP:* `{res['balance']} {res.get('currency', 'USD')}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"⚠️ *Error JAP:* {res.get('error', res)}")

# ================= SELECCIÓN DE OFERTA =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    service_key = call.data.replace('buy_', '')
    service = SERVICIOS.get(service_key)
    chat_id = call.message.chat.id
    
    user_data[chat_id] = {'service_key': service_key, 'step': 'link'}
    
    texto_detalle = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📦 *RESUMEN DE SELECCIÓN*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 *Servicio:* {service['nombre']}\n"
        f"💵 *Monto:* `{service['precio_cup']} CUP`\n\n"
        "🔗 *Por favor, envía el enlace directo de tu perfil o publicación:*\n"
        "_(Ejemplo: https://instagram.com/tu_usuario)_"
    )
    
    bot.edit_message_text(
        texto_detalle,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

# ================= CAPTURA DE ENLACE =================
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'link')
def handle_link(message):
    chat_id = message.chat.id
    link = message.text.strip()
    
    if not (link.startswith("http://") or link.startswith("https://")):
        bot.reply_to(message, "⚠️ *Enlace inválido.*\nAsegúrate de copiar el enlace completo que empiece por `http://` o `https://`", parse_mode="Markdown")
        return

    user_data[chat_id]['link'] = link
    user_data[chat_id]['step'] = 'receipt'
    s_key = user_data[chat_id]['service_key']
    service = SERVICIOS[s_key]

    instrucciones_pago = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 *PASO FINAL: REALIZAR PAGO*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Paquete:* {service['nombre']}\n"
        f"🔗 *Destino:* `{link}`\n"
        f"💰 *Total exacto a pagar:* *{service['precio_cup']} CUP*\n\n"
        "📲 Realiza la transferencia por **Transfermóvil** o **EnZona**.\n\n"
        "📸 Una vez completada, **envía la foto/captura del comprobante por aquí** para verificar y activar tu pedido de inmediato."
    )

    bot.reply_to(message, instrucciones_pago, parse_mode="Markdown")

# ================= CAPTURA DEL COMPROBANTE =================
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

    admin_caption = (
        "🔔 *NUEVO COMPROBANTE POR VERIFICAR*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Cliente:* {message.from_user.first_name} (`{chat_id}`)\n"
        f"📦 *Servicio:* {service['nombre']}\n"
        f"💰 *Monto:* {service['precio_cup']} CUP\n"
        f"🔗 *Enlace:* `{link}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    bot.send_photo(ADMIN_CHAT_ID, photo_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
    
    mensaje_cliente = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *COMPROBANTE RECIBIDO CON ÉXITO*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Tu pago está siendo revisado por nuestro equipo.\n"
        "En cuanto sea verificado, tu servicio se procesará automáticamente. 🚀"
    )
    bot.reply_to(message, mensaje_cliente, parse_mode="Markdown")
    user_data.pop(chat_id, None)

# ================= ACCIONES DEL ADMINISTRADOR =================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_admin_action(call):
    action, order_id = call.data.split('_', 1)
    order = pending_orders.get(order_id)
    chat_id = call.message.chat.id
    msg_id = call.message.message_id

    if not order:
        bot.answer_callback_query(call.id, "⚠️ Esta orden ya fue procesada o no existe.")
        return

    if action == "approve":
        res = send_jap_order(order["service"]["service_id"], order["link"], order["service"]["cantidad"])
        if "order" in res:
            jap_id = res["order"]
            
            # Actualizar panel del admin
            bot.edit_message_caption(
                caption=f"{call.message.caption}\n\n✅ *ORDEN APROBADA*\n🆔 ID JAP: `{jap_id}`",
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="Markdown"
            )
            
            # Notificar al cliente
            bot.send_message(
                order["user_id"],
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎉 *¡PAGO CONFIRMADO CON ÉXITO!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Tu orden de *{order['service']['nombre']}* ya fue enviada y se encuentra en marcha.\n\n"
                "¡Gracias por confiar en *Impulso Redes Pro*!",
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, "✅ Orden enviada a JAP")
        else:
            err_msg = res.get("error", res)
            bot.send_message(ADMIN_CHAT_ID, f"⚠️ *Error devuelto por JAP:* `{err_msg}`", parse_mode="Markdown")
            bot.answer_callback_query(call.id, "Error en API JAP")

    elif action == "reject":
        bot.edit_message_caption(
            caption=f"{call.message.caption}\n\n❌ *COMPROBANTE RECHAZADO*",
            chat_id=chat_id,
            message_id=msg_id,
            parse_mode="Markdown"
        )
        bot.send_message(
            order["user_id"],
            "❌ *Comprobante no válido*\n\n"
            "No pudimos verificar la transferencia recibida. Por favor contacta a soporte para solucionar tu caso.",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "Comprobante rechazado")

# ================= ARRANQUE =================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling(skip_pending=True)
