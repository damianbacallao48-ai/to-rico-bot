import os
import requests
import telebot
from telebot import types

TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_ID = 6731555041
JAP_KEY = "b1aede7e7f18cdf8de142d14b2967e10"
JAP_URL = "https://justanotherpanel.com/api/v2"

# Datos de pago para el cliente
DATOS_PAGO = {
    "tarjeta": "9238-1299-7952-7274",
    "nombre": "Daemon",
    "telefono": "+5358960660"
}

bot = telebot.TeleBot(TOKEN)

SERVICIOS = {
    # Instagram Seguidores (30D Garantía)
    "ig_fol": {"id": "10129", "name": "👥 1.000 Seguidores IG (Garantía 30D)", "cup": 4000, "qty": 1000},
    
    # Instagram Likes (30D Garantía)
    "ig_likes": {"id": "10130", "name": "❤️ 1.000 Likes IG (Garantía 30D)", "cup": 1500, "qty": 1000},
    
    # TikTok 10k
    "tt_likes": {"id": "10333", "name": "❤️ 10.000 Likes TikTok VIP", "cup": 2500, "qty": 10000},
    
    # TikTok Seguidores (30D Garantía)
    "tt_fol": {"id": "9777", "name": "🎵 1.000 Seguidores TikTok (Garantía 30D)", "cup": 3000, "qty": 1000},
    
    # Facebook Seguidores de Página
    "fb_fol": {"id": "1724", "name": "👍 1.000 Seguidores FB Página", "cup": 3000, "qty": 1000},
    
    # Facebook Likes de Página (30D Garantía)
    "fb_likes": {"id": "9230", "name": "💙 1.000 Likes FB Página (Garantía 30D)", "cup": 1500, "qty": 1000},
    
    # Combo: 1k Seg (ID 10129) + 500 Likes IG
    "combo": {"id": "10129", "name": "🔥 Combo: 1k Seg + 500 Likes IG", "cup": 4000, "qty": 1000}
}

user_data = {}
orders = {}

def call_jap(srv_id, link, qty):
    data = {
        "key": JAP_KEY,
        "action": "add",
        "service": str(srv_id),
        "link": link,
        "quantity": str(qty)
    }
    try:
        req = requests.post(JAP_URL, data=data, timeout=25)
        return req.json()
    except Exception as e:
        return {"error": str(e)}

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.chat.id
    user_data.pop(uid, None)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, s in SERVICIOS.items():
        kb.add(types.InlineKeyboardButton(f"{s['name']} ➔ {s['cup']} CUP", callback_data=f"b_{k}"))
    bot.send_message(uid, "⚡ *IMPULSO REDES PRO*\nSelecciona un servicio:", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['balance'])
def cmd_balance(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        r = requests.post(JAP_URL, data={"key": JAP_KEY, "action": "balance"}, timeout=15).json()
        bot.reply_to(msg, f"💰 Saldo JAP: {r.get('balance', 'Error')} {r.get('currency', 'USD')}")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ Error: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('b_'))
def on_select(call):
    uid = call.message.chat.id
    key = call.data[2:]
    srv = SERVICIOS.get(key)
    if not srv:
        return
    user_data[uid] = {'key': key, 'step': 'link'}
    bot.answer_callback_query(call.id)
    bot.send_message(uid, f"Seleccionaste: *{srv['name']}*\nPrecio: *{srv['cup']} CUP*\n\n🔗 Envía el enlace de tu perfil o publicación:")

@bot.message_handler(content_types=['text'])
def on_text(msg):
    uid = msg.chat.id
    st = user_data.get(uid, {})
    if st.get('step') == 'link':
        txt = msg.text.strip()
        if not (txt.startswith('http://') or txt.startswith('https://')):
            bot.reply_to(msg, "⚠️ Envía un enlace válido con http:// o https://")
            return
        user_data[uid]['link'] = txt
        user_data[uid]['step'] = 'proof'
        srv = SERVICIOS[st['key']]
        
        texto_pago = (
            f"✅ *Enlace recibido:* `{txt}`\n"
            f"💰 *Total a pagar:* *{srv['cup']} CUP*\n\n"
            f"💳 *Datos de transferencia:*\n"
            f"• Tarjeta: `{DATOS_PAGO['tarjeta']}`\n"
            f"• Titular: *{DATOS_PAGO['nombre']}*\n"
            f"• Móvil: `{DATOS_PAGO['telefono']}`\n\n"
            f"📸 *Envía ahora la captura o foto del comprobante de pago.*"
        )
        bot.reply_to(msg, texto_pago, parse_mode="Markdown")
    else:
        bot.reply_to(msg, "Usa /start para iniciar un pedido.")

@bot.message_handler(content_types=['photo'])
def on_photo(msg):
    uid = msg.chat.id
    st = user_data.get(uid, {})
    if st.get('step') != 'proof':
        bot.reply_to(msg, "Usa /start para seleccionar un servicio primero.")
        return
    pid = msg.photo[-1].file_id
    oid = str(msg.message_id)
    srv = SERVICIOS[st['key']]
    orders[oid] = {'uid': uid, 'srv': srv, 'link': st['link']}
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Aprobar", callback_data=f"a_{oid}"),
        types.InlineKeyboardButton("❌ Rechazar", callback_data=f"r_{oid}")
    )
    cap = (
        f"🔔 *Nuevo Pago Recibido*\n"
        f"👤 Cliente: {msg.from_user.first_name} (`{uid}`)\n"
        f"📦 Servicio: {srv['name']}\n"
        f"💵 Monto: *{srv['cup']} CUP*\n"
        f"🔗 Enlace: `{st['link']}`"
    )
    bot.send_photo(ADMIN_ID, pid, caption=cap, parse_mode="Markdown", reply_markup=kb)
    bot.reply_to(msg, "✅ Comprobante recibido. Revisando tu pago para activar la orden...")
    user_data.pop(uid, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith(('a_', 'r_')))
def on_decision(call):
    act, oid = call.data.split('_', 1)
    od = orders.get(oid)
    if not od:
        bot.answer_callback_query(call.id, "Procesada.")
        return
    if act == "a":
        res = call_jap(od['srv']['id'], od['link'], od['srv']['qty'])
        if "order" in res:
            bot.edit_message_caption(f"{call.message.caption}\n\n✅ *Aprobado JAP ID:* `{res['order']}`", chat_id=call.message.chat.id, message_id=call.message.message_id)
            bot.send_message(od['uid'], f"🎉 ¡Pago confirmado! Tu orden de *{od['srv']['name']}* ya se está procesando.")
        else:
            bot.send_message(ADMIN_ID, f"⚠️ Error JAP: {res.get('error', res)}")
    else:
        bot.edit_message_caption(f"{call.message.caption}\n\n❌ *Rechazado*", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(od['uid'], "❌ Tu comprobante fue rechazado. Revisa tu pago o contacta a soporte.")
    bot.answer_callback_query(call.id, "Listo")

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
