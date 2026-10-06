import time
import requests

# ================= CONFIGURACIÓN =================
TELEGRAM_BOT_TOKEN = "8998730541:AAE4p-o41CvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_CHAT_ID = 6731555041

JAP_API_KEY = "3532b6a51bcc7638bcc9841c5cc1d425"
JAP_API_URL = "https://justanotherpanel.com/api/v2"
TG_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Servicios disponibles
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
        "precio_cup": 1500,
        "cantidad": 1000
    },
    "tt_views_10000": {
        "service_id": "1002",
        "nombre": "👀 10.000 Vistas TikTok",
        "precio_cup": 800,
        "cantidad": 10000
    }
}

user_states = {}
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
        r = requests.post(JAP_API_URL, data=payload, timeout=25)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def tg_send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{TG_API_URL}/sendMessage", json=data, timeout=15)
    except Exception:
        pass

def tg_send_photo(chat_id, photo_id, caption, reply_markup=None):
    data = {"chat_id": chat_id, "photo": photo_id, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{TG_API_URL}/sendPhoto", json=data, timeout=15)
    except Exception:
        pass

def tg_edit_caption(chat_id, message_id, caption):
    data = {"chat_id": chat_id, "message_id": message_id, "caption": caption, "parse_mode": "Markdown"}
    try:
        requests.post(f"{TG_API_URL}/editMessageCaption", json=data, timeout=15)
    except Exception:
        pass

def handle_update(update):
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        from_user = cb["from"]
        chat_id = from_user["id"]
        data = cb.get("data", "")
        message = cb.get("message", {})
        msg_id = message.get("message_id")

        requests.post(f"{TG_API_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})

        if data.startswith("buy_"):
            service_key = data.replace("buy_", "")
            service = SERVICIOS.get(service_key)
            if service:
                user_states[chat_id] = {"step": "waiting_link", "service_key": service_key}
                tg_send_message(
                    chat_id,
                    f"Has seleccionado: *{service['nombre']}*\n"
                    f"💰 Total a pagar: *{service['precio_cup']} CUP*\n\n"
                    "🔗 *Envía el enlace directo de tu publicación o perfil:*"
                )

        elif data.startswith("approve_"):
            order_id = data.replace("approve_", "")
            order = pending_orders.get(order_id)
            if order:
                res = send_jap_order(
                    order["service"]["service_id"],
                    order["link"],
                    order["service"]["cantidad"]
                )
                if "order" in res:
                    jap_id = res["order"]
                    tg_edit_caption(ADMIN_CHAT_ID, msg_id, f"✅ *Orden Aprobada y Enviada*\n🆔 ID JAP: `{jap_id}`")
                    tg_send_message(order["user_id"], f"🎉 ¡Tu pago ha sido confirmado! Tu orden de *{order['service']['nombre']}* está en marcha.")
                else:
                    err_msg = res.get("error", str(res))
                    tg_send_message(ADMIN_CHAT_ID, f"⚠️ JAP devolvió este error: {err_msg}")
            else:
                tg_send_message(ADMIN_CHAT_ID, "⚠️ No se encontró la orden en memoria.")

        elif data.startswith("reject_"):
            order_id = data.replace("reject_", "")
            order = pending_orders.get(order_id)
            tg_edit_caption(ADMIN_CHAT_ID, msg_id, "❌ *Comprobante Rechazado*")
            if order:
                tg_send_message(order["user_id"], "❌ Tu comprobante no pudo ser verificado. Contacta a soporte.")

        return

    if "message" not in update:
        return

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    from_user = msg.get("from", {})
    user_name = from_user.get("first_name", "Cliente")

    if text == "/start":
        buttons = []
        for s_key, s_data in SERVICIOS.items():
            buttons.append([{"text": f"{s_data['nombre']} - {s_data['precio_cup']} CUP", "callback_data": f"buy_{s_key}"}])
        keyboard = {"inline_keyboard": buttons}
        tg_send_message(
            chat_id,
            "🚀 *Bienvenido a Impulso Redes Pro*\n\nSelecciona el servicio que deseas adquirir:",
            reply_markup=keyboard
        )
        user_states[chat_id] = {"step": "waiting_selection"}
        return

    state = user_states.get(chat_id, {}).get("step")

    if state == "waiting_link":
        if text.startswith("http://") or text.startswith("https://"):
            s_key = user_states[chat_id]["service_key"]
            service = SERVICIOS[s_key]
            user_states[chat_id] = {"step": "waiting_receipt", "service_key": s_key, "link": text}
            tg_send_message(
                chat_id,
                f"✅ *Detalles de la compra:*\n"
                f"📦 Servicio: {service['nombre']}\n"
                f"🔗 Enlace: `{text}`\n"
                f"💵 Monto a transferir: *{service['precio_cup']} CUP*\n\n"
                f"💳 Realiza el pago y *envía la foto/captura del comprobante aquí*."
            )
        else:
            tg_send_message(chat_id, "⚠️ El enlace debe comenzar con http:// o https://")
        return

    if state == "waiting_receipt" and "photo" in msg:
        photo = msg["photo"][-1]
        photo_id = photo["file_id"]
        s_key = user_states[chat_id]["service_key"]
        service = SERVICIOS[s_key]
        link = user_states[chat_id]["link"]

        order_id = str(msg["message_id"])
        pending_orders[order_id] = {
            "user_id": chat_id,
            "service": service,
            "link": link
        }

        admin_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Aprobar y Enviar", "callback_data": f"approve_{order_id}"},
                    {"text": "❌ Rechazar", "callback_data": f"reject_{order_id}"}
                ]
            ]
        }

        caption = (
            f"🔔 *Nuevo comprobante recibido:*\n\n"
            f"👤 Cliente: {user_name} (`{chat_id}`)\n"
            f"📦 Servicio: {service['nombre']}\n"
            f"💰 Monto: {service['precio_cup']} CUP\n"
            f"🔗 Enlaces: {link}"
        )

        tg_send_photo(ADMIN_CHAT_ID, photo_id, caption, reply_markup=admin_keyboard)
        tg_send_message(chat_id, "✅ *Comprobante recibido con éxito.* En breve será revisado.")
        user_states.pop(chat_id, None)

def main():
    offset = None
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            res = requests.get(f"{TG_API_URL}/getUpdates", params=params, timeout=40).json()
            if res.get("ok"):
                for upd in res.get("result", []):
                    offset = upd["update_id"] + 1
                    handle_update(upd)
        except Exception:
            time.sleep(2)

if __name__ == "__main__":
    main()
