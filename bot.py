import os
import json
import requests
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- CONFIGURACIÓN PRINCIPAL ---
BOT_TOKEN = "8998730541:AAE4p-o4lCvShtYy
5alFEXnOFn5SCDmDtr0"


ADMIN_ID = 6731555041

# Panel SMM (JAP / JustAnotherPanel u otro compatible con API v2)
API_URL = os.environ.get("API_URL", "https://justanotherpanel.com/api/v2")
API_KEY = os.environ.get("API_KEY", "")

bot = telebot.TeleBot(BOT_TOKEN)

# --- BASE DE DATOS LOCAL (JSON) ---
DB_FILE = "database.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user_balance(user_id):
    db = load_db()
    return db["users"].get(str(user_id), {}).get("balance", 0.0)

def update_user_balance(user_id, amount):
    db = load_db()
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0}
    db["users"][uid]["balance"] += amount
    save_db(db)
    return db["users"][uid]["balance"]

# Catálogo local de servicios disponibles
SERVICIOS = {
    "1": {"nombre": "Seguidores de Instagram [Garantía]", "precio_mil": 1.50, "service_id": 101},
    "2": {"nombre": "Likes de Instagram [Rápidos]", "precio_mil": 0.50, "service_id": 102},
    "3": {"nombre": "Vistas de TikTok [Alta Retención]", "precio_mil": 0.30, "service_id": 103},
    "4": {"nombre": "Seguidores de TikTok", "precio_mil": 2.00, "service_id": 104}
}

user_sessions = {}

# --- SERVIDOR WEB PARA MANTENER ACTIVO EL CONTENEDOR ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot en funcionamiento activo."

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- MANEJADORES DE COMANDOS ---

@bot.message_handler(commands=['start'])
def start_command(message):
    first_name = message.from_user.first_name or "Usuario"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_order = types.InlineKeyboardButton("🛒 Realizar Pedido", callback_data="btn_order")
    btn_balance = types.InlineKeyboardButton("💰 Mi Saldo", callback_data="btn_balance")
    btn_services = types.InlineKeyboardButton("📋 Lista de Servicios", callback_data="btn_services")
    btn_support = types.InlineKeyboardButton("🆘 Soporte", callback_data="btn_support")
    markup.add(btn_order, btn_balance, btn_services, btn_support)

    texto = (
        f"👋 ¡Hola, *{first_name}*! Bienvenido a *Impulso Redes Pro*.\n\n"
        "Potencia tus redes sociales de forma rápida, segura y automatizada.\n\n"
        "Selecciona una opción del menú para comenzar:"
    )
    bot.send_message(message.chat.id, texto, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['recargar'])
def cmd_recargar(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ No tienes permisos para usar este comando.")
        return

    partes = message.text.split()
    if len(partes) != 3:
        bot.reply_to(message, "⚠️ Uso incorrecto.\nFormato: `/recargar <ID_USUARIO> <CANTIDAD>`", parse_mode="Markdown")
        return

    try:
        target_id = partes[1]
        monto = float(partes[2])
        nuevo_saldo = update_user_balance(target_id, monto)

        bot.reply_to(
            message,
            f"✅ Se han acreditado ${monto:.2f} al usuario `{target_id}`.\n"
            f"Saldo actual: *${nuevo_saldo:.2f} créditos*",
            parse_mode="Markdown"
        )

        try:
            bot.send_message(
                target_id,
                f"🎉 ¡Tu saldo ha sido recargado!\n\n"
                f"Se agregaron *${monto:.2f} créditos* a tu cuenta.\n"
                f"Saldo total disponible: *${nuevo_saldo:.2f} créditos*",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except ValueError:
        bot.reply_to(message, "❌ El monto debe ser un valor numérico válido.")

# --- CALLBACKS DEL MENÚ ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id

    if call.data == "btn_balance":
        saldo = get_user_balance(user_id)
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"💰 *Tu saldo actual es:* `${saldo:.2f} créditos`\n\n"
            "Para recargar fondos, contacta al administrador.",
            parse_mode="Markdown"
        )

    elif call.data == "btn_services":
        bot.answer_callback_query(call.id)
        texto = "📋 *Servicios Disponibles:*\n\n"
        for k, v in SERVICIOS.items():
            texto += f"• *{v['nombre']}*\n  Precio por 1k: `${v['precio_mil']:.2f}`\n\n"
        bot.send_message(chat_id, texto, parse_mode="Markdown")

    elif call.data == "btn_support":
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"🆘 Para dudas o soporte para recargas, contacta a: [Administrador](tg://user?id={ADMIN_ID})",
            parse_mode="Markdown"
        )

    elif call.data == "btn_order":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for k, v in SERVICIOS.items():
            markup.add(types.InlineKeyboardButton(f"{v['nombre']} - ${v['precio_mil']}/k", callback_data=f"sel_{k}"))
        bot.send_message(chat_id, "Selecciona el servicio que deseas ordenar:", reply_markup=markup)

    elif call.data.startswith("sel_"):
        bot.answer_callback_query(call.id)
        servicio_key = call.data.split("_")[1]
        user_sessions[user_id] = {"servicio": SERVICIOS[servicio_key], "step": "LINK"}
        bot.send_message(
            chat_id,
            f"Seleccionaste: *{SERVICIOS[servicio_key]['nombre']}*\n\n"
            "Envía el *enlace* del perfil, publicación o video a promocionar:",
            parse_mode="Markdown"
        )

# --- FLUJO DE PEDIDO PASO A PASO ---

@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_sessions)
def handle_order_flow(message):
    user_id = str(message.from_user.id)
    session = user_sessions[user_id]

    if session.get("step") == "LINK":
        session["link"] = message.text.strip()
        session["step"] = "CANTIDAD"
        bot.send_message(
            message.chat.id,
            "Ahora indica la **cantidad** que deseas ordenar (ejemplo: 500, 1000):",
            parse_mode="Markdown"
        )

    elif session.get("step") == "CANTIDAD":
        try:
            cantidad = int(message.text.strip())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            bot.reply_to(message, "❌ Por favor introduce un número entero positivo.")
            return

        servicio = session["servicio"]
        costo = (cantidad / 1000.0) * servicio["precio_mil"]
        saldo_disponible = get_user_balance(user_id)

        if saldo_disponible < costo:
            bot.send_message(
                message.chat.id,
                f"❌ Saldo insuficiente.\n\n"
                f"Costo del pedido: *${costo:.2f} créditos*\n"
                f"Tu saldo actual: *${saldo_disponible:.2f} créditos*\n\n"
                "Usa /start para volver al menú o recarga saldo.",
                parse_mode="Markdown"
            )
            del user_sessions[user_id]
            return

        # Descontar saldo
        nuevo_saldo = update_user_balance(user_id, -costo)

        # Enviar orden al panel API (si hay API_KEY configurada)
        order_id = "LOCAL-" + str(message.message_id)
        if API_KEY:
            try:
                payload = {
                    "key": API_KEY,
                    "action": "add",
                    "service": servicio["service_id"],
                    "link": session["link"],
                    "quantity": cantidad
                }
                res = requests.post(API_URL, data=payload, timeout=15).json()
                if "order" in res:
                    order_id = str(res["order"])
            except Exception as e:
                print(f"Error conectando con la API SMM: {e}")

        bot.send_message(
            message.chat.id,
            f"✅ *¡Pedido creado con éxito!*\n\n"
            f"🆔 *ID del Pedido:* `{order_id}`\n"
            f"📌 *Servicio:* {servicio['nombre']}\n"
            f"🔗 *Enlace:* {session['link']}\n"
            f"🔢 *Cantidad:* {cantidad}\n"
            f"💵 *Costo:* ${costo:.2f} créditos\n"
            f"💰 *Saldo restante:* ${nuevo_saldo:.2f} créditos",
            parse_mode="Markdown"
        )
        del user_sessions[user_id]

# --- INICIO DE EJECUCIÓN ---
if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
