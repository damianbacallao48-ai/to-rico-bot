import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# Configuración de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= CONFIGURACIÓN DIRECTA =================
TELEGRAM_BOT_TOKEN = "8998730541:AAE4p-o41CvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_CHAT_ID = 6731555041

# JustAnotherPanel
JAP_API_KEY = "3532b6a51bcc7638bcc9841c5cc1d425"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

# Catálogo de Servicios
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

SELECT_SERVICE, ENTER_LINK, AWAIT_RECEIPT = range(3)
pending_orders = {}

# ================= FUNCIONES =================
def send_jap_order(service_id, link, quantity):
    """Envía la orden a JustAnotherPanel"""
    data = {
        "key": JAP_API_KEY,
        "action": "add",
        "service": str(service_id),
        "link": link,
        "quantity": str(quantity)
    }
    try:
        response = requests.post(JAP_API_URL, data=data, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for s_key, s_data in SERVICIOS.items():
        keyboard.append([InlineKeyboardButton(f"{s_data['nombre']} - {s_data['precio_cup']} CUP", callback_data=f"buy_{s_key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 *Bienvenido a Impulso Redes Pro*\n\n"
        "Selecciona el servicio que deseas adquirir:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_SERVICE

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta el saldo disponible en JAP"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    res = requests.post(JAP_API_URL, data={"key": JAP_API_KEY, "action": "balance"}).json()
    if "balance" in res:
        await update.message.reply_text(f"💰 Saldo en JAP: {res['balance']} {res.get('currency', 'USD')}")
    else:
        await update.message.reply_text(f"⚠️ Error JAP: {res.get('error', res)}")

async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    service_key = query.data.replace("buy_", "")
    context.user_data["selected_service"] = service_key
    service = SERVICIOS[service_key]

    await query.edit_message_text(
        f"Has seleccionado: *{service['nombre']}*\n"
        f"💰 Total a pagar: *{service['precio_cup']} CUP*\n\n"
        "🔗 *Por favor, envía el enlace directo de tu publicación o perfil:*",
        parse_mode="Markdown"
    )
    return ENTER_LINK

async def link_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://")):
        await update.message.reply_text("⚠️ Enlace no válido. Debe empezar con http:// o https://")
        return ENTER_LINK

    context.user_data["order_link"] = link
    service_key = context.user_data["selected_service"]
    service = SERVICIOS[service_key]

    datos_pago = (
        f"✅ *Detalles de la compra:*\n"
        f"📦 Servicio: {service['nombre']}\n"
        f"🔗 Enlace: `{link}`\n"
        f"💵 Monto a transferir: *{service['precio_cup']} CUP*\n\n"
        f"💳 Realiza el pago y envía la *captura del comprobante* aquí."
    )
    await update.message.reply_text(datos_pago, parse_mode="Markdown")
    return AWAIT_RECEIPT

async def receipt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    service_key = context.user_data.get("selected_service")
    service = SERVICIOS[service_key]
    link = context.user_data.get("order_link")

    order_id = str(update.message.message_id)
    pending_orders[order_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "service": service,
        "link": link
    }

    # Botones que recibe el Administrador
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar y Enviar", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{order_id}")
        ]
    ])

    admin_caption = (
        f"🔔 *Nuevo comprobante recibido:*\n\n"
        f"👤 Cliente: {user.full_name} (`{user.id}`)\n"
        f"📦 Servicio: {service['nombre']}\n"
        f"💰 Monto: {service['precio_cup']} CUP\n"
        f"🔗 Enlaces: {link}"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo.file_id,
        caption=admin_caption,
        reply_markup=admin_keyboard
    )

    await update.message.reply_text("✅ *Comprobante recibido con éxito.* En breves momentos tu pago será revisado.", parse_mode="Markdown")
    return ConversationHandler.END

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, order_id = data.split("_", 1)
    order = pending_orders.get(order_id)

    if not order:
        await query.message.reply_text("⚠️️ No se encontró la información de esta orden o ya fue procesada.")
        return

    if action == "approve":
        res = send_jap_order(
            service_id=order["service"]["service_id"],
            link=order["link"],
            quantity=order["service"]["cantidad"]
        )

        if "order" in res:
            jap_id = res["order"]
            await query.edit_message_caption(
                caption=f"{query.message.caption}\n\n✅ Orden Aprobada\n🆔 ID JAP: {jap_id}"
            )
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"🎉 ¡Tu pago ha sido aprobado! Tu orden de {order['service']['nombre']} está en camino."
            )
        elif "error" in res:
            await query.message.reply_text(f"⚠️ JAP devolvió este error: {res['error']}")
        else:
            await query.message.reply_text(f"⚠️ Respuesta del panel: {res}")

    elif action == "reject":
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ Comprobante Rechazado"
        )
        await context.bot.send_message(
            chat_id=order["user_id"],
            text="❌ Tu comprobante no pudo ser verificado. Contacta a soporte."
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_SERVICE: [CallbackQueryHandler(service_selected, pattern="^buy_")],
            ENTER_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_received)],
            AWAIT_RECEIPT: [MessageHandler(filters.PHOTO, receipt_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^(approve|reject)_"))

    logger.info("Impulso Redes Pro en línea.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
