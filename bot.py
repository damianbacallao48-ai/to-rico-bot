import os
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

# ================= CONFIGURACIÓN =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TOKEN_TELEGRAM_AQUI")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6731555041"))  # Tu ID de Telegram
JAP_API_KEY = "3532b6a51bcc7638bcc9841c5cc1d425"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

# CallMeBot (WhatsApp Notificaciones)
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", "")      # Ej: +53XXXXXXXX
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "")  # Tu apikey de callmebot

# Tasa de cambio CUP
TASA_CUP = 770.0

# Catálogo de Servicios (ID de JAP, Nombre, Precio base USD aprox)
SERVICIOS = {
    "ig_likes_1000": {
        "service_id": "1000", # Cambiar al ID real si usas otro
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

# Estados para la conversación
SELECT_SERVICE, ENTER_LINK, AWAIT_RECEIPT = range(3)

# Memoria temporal de pedidos pendientes
pending_orders = {}

# ================= FUNCIONES AUXILIARES =================
def send_jap_order(service_id, link, quantity):
    """Envía la orden directamente a JustAnotherPanel"""
    data = {
        "key": JAP_API_KEY,
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    }
    try:
        response = requests.post(JAP_API_URL, data=data, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def notify_whatsapp(mensaje):
    """Envía alerta de comprobante por WhatsApp"""
    if not CALLMEBOT_PHONE or not CALLMEBOT_API_KEY:
        return
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={CALLMEBOT_PHONE}&text={requests.utils.quote(mensaje)}&apikey={CALLMEBOT_API_KEY}"
        requests.get(url, timeout=10)
    except Exception as e:
        logger.error(f"Error enviando WhatsApp: {e}")

# ================= COMANDOS Y FLUJO =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for s_key, s_data in SERVICIOS.items():
        keyboard.append([InlineKeyboardButton(f"{s_data['nombre']} - {s_data['precio_cup']} CUP", callback_data=f"buy_{s_key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 *Bienvenido a Impulso Redes Pro*\n\n"
        "Selecciona el servicio que deseas adquirir para potenciar tus redes:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_SERVICE

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
        await update.message.reply_text("⚠️ Por favor envía un enlace válido que comience con http:// o https://")
        return ENTER_LINK

    context.user_data["order_link"] = link
    service_key = context.user_data["selected_service"]
    service = SERVICIOS[service_key]

    datos_pago = (
        f"✅ *Datos confirmados:*\n"
        f"📦 Servicio: {service['nombre']}\n"
        f"🔗 Enlace: `{link}`\n"
        f"💵 Monto a transferir: *{service['precio_cup']} CUP*\n\n"
        f"💳 Realiza la transferencia a los datos autorizados y envía una *foto/captura del comprobante* aquí mismo."
    )
    await update.message.reply_text(datos_pago, parse_mode="Markdown")
    return AWAIT_RECEIPT

async def receipt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1] # La imagen con mejor resolución
    service_key = context.user_data.get("selected_service")
    service = SERVICIOS[service_key]
    link = context.user_data.get("order_link")

    order_id = str(update.message.message_id)
    pending_orders[order_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "username": user.username or "Sin usuario",
        "service": service,
        "link": link
    }

    # Botones para el Administrador
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar y Enviar", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{order_id}")
        ]
    ])

    admin_caption = (
        f"🔔 *Nuevo comprobante recibido:*\n\n"
        f"👤 *Cliente:* {user.full_name} (`{user.id}`)\n"
        f"📦 *Servicio:* {service['nombre']}\n"
        f"💰 *Monto:* {service['precio_cup']} CUP\n"
        f"🔗 *Enlaces:* {link}"
    )

    # Notificar al Administrador en Telegram
    await context.bot.send_photo(
        chat_id=ADMIN_CHAT_ID,
        photo=photo.file_id,
        caption=admin_caption,
        reply_markup=admin_keyboard,
        parse_mode="Markdown"
    )

    # Alerta por WhatsApp
    notify_whatsapp(f"Nuevo comprobante de {user.full_name} por {service['precio_cup']} CUP para {service['nombre']}")

    await update.message.reply_text("✅ *Comprobante recibido con éxito.* En breves momentos tu pago será revisado y tu orden procesada.", parse_mode="Markdown")
    return ConversationHandler.END

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, order_id = data.split("_", 1)
    order = pending_orders.get(order_id)

    if not order:
        await query.message.reply_text("⚠️ No se encontró la información de esta orden o ya fue procesada.")
        return

    if action == "approve":
        # Enviar orden a JustAnotherPanel
        res = send_jap_order(
            service_id=order["service"]["service_id"],
            link=order["link"],
            quantity=order["service"]["cantidad"]
        )

        if "order" in res:
            jap_order_id = res["order"]
            await query.edit_message_caption(
                caption=f"{query.message.caption_markdown}\n\n✅ *Aprobado y enviado a JAP*\n🆔 ID JAP: `{jap_order_id}`",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"🎉 ¡Tu pago ha sido aprobado! Tu orden de *{order['service']['nombre']}* está en camino.",
                parse_mode="Markdown"
            )
        elif "error" in res:
            await query.message.reply_text(f"⚠️ JAP devolvió este error: {res['error']}")
        else:
            await query.message.reply_text(f"⚠️ Respuesta inesperada de JAP: {res}")

    elif action == "reject":
        await query.edit_message_caption(
            caption=f"{query.message.caption_markdown}\n\n❌ *Comprobante Rechazado*",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=order["user_id"],
            text="❌ Lo sentimos, tu comprobante no pudo ser verificado. Contacta a soporte para más detalles."
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
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^(approve|reject)_"))

    logger.info("Impulso Redes Pro en línea.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
