import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuración básica de logs para monitoreo en Railway
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración de credenciales
# Puedes definirlos aquí directamente o vía Variables de Entorno en Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TELEGRAM_BOT_TOKEN_AQUI")
JAP_API_KEY = os.getenv("JAP_API_KEY", "3532b6a51bcc7638bcc9841c5cc1d425")
JAP_API_URL = "https://justanotherpanel.com/api/v2"


def jap_request(payload: dict) -> dict:
    """Envía peticiones al API de JustAnotherPanel."""
    data = {
        "key": JAP_API_KEY,
        **payload
    }
    try:
        response = requests.post(JAP_API_URL, data=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error conectando con JAP: {e}")
        return {"error": f"Fallo de conexión: {str(e)}"}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de inicio."""
    user = update.effective_user.first_name
    mensaje = (
        f"👋 ¡Hola, {user}!\n\n"
        "Bienvenido al bot de servicios SMM.\n\n"
        "Comandos disponibles:\n"
        "/balance - Consulta el saldo en JustAnotherPanel\n"
        "/servicios - Consulta información de servicios\n"
        "/orden <service_id> <enlace> <cantidad> - Crear un pedido"
    )
    await update.message.reply_text(mensaje)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Consulta el saldo actual de la cuenta en JAP."""
    await update.message.reply_text("⏳ Consultando saldo en JustAnotherPanel...")
    
    result = jap_request({"action": "balance"})
    
    if "balance" in result:
        balance = result.get("balance")
        currency = result.get("currency", "USD")
        await update.message.reply_text(f"💰 Saldo disponible: {balance} {currency}")
    elif "error" in result:
        await update.message.reply_text(f"❌ Error al consultar saldo: {result['error']}")
    else:
        await update.message.reply_text(f"⚠️️ Respuesta inesperada: {result}")


async def orden_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crea una orden en JustAnotherPanel."""
    # Uso esperado: /orden <service_id> <enlace> <cantidad>
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ Formato incorrecto.\n"
            "Uso: `/orden <ID_SERVICIO> <ENLACE> <CANTIDAD>`\n"
            "Ejemplo: `/orden 1024 https://instagram.com/usuario 1000`",
            parse_mode="Markdown"
        )
        return

    service_id = context.args[0]
    link = context.args[1]
    quantity = context.args[2]

    await update.message.reply_text(f"⏳ Procesando orden para {link} ({quantity} unidades)...")

    payload = {
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    }

    result = jap_request(payload)

    if "order" in result:
        order_id = result.get("order")
        await update.message.reply_text(f"✅ ¡Orden creada exitosamente!\n🆔 ID de Orden: `{order_id}`", parse_mode="Markdown")
    elif "error" in result:
        await update.message.reply_text(f"❌ Error al crear la orden: {result['error']}")
    else:
        await update.message.reply_text(f"⚠️ Respuesta del panel: {result}")


async def servicios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el estado de los servicios."""
    await update.message.reply_text("⏳ Conectando con JAP para verificar conexión...")
    result = jap_request({"action": "services"})
    
    if isinstance(result, list):
        total = len(result)
        await update.message.reply_text(f"✅ Conexión API válida. Total de servicios disponibles: {total}")
    elif isinstance(result, dict) and "error" in result:
        await update.message.reply_text(f"❌ Error devuelto por JAP: {result['error']}")
    else:
        await update.message.reply_text("⚠️ No se pudo obtener la lista de servicios.")


def main():
    if TELEGRAM_BOT_TOKEN == "TU_TELEGRAM_BOT_TOKEN_AQUI" or not TELEGRAM_BOT_TOKEN:
        logger.error("No se ha configurado TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command
