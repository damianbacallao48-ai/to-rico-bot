import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask

# ================= 1. SERVIDOR FLASK (HEALTHCHECK RAILWAY) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= 2. CREDENCIALES EXACTAS =================
TELEGRAM_BOT_TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_CHAT_ID = 6731555041

# Clave confirmada y autenticada con JAP ($5.25 USD)
JAP_API_KEY = "b1aede7e7f18cdf8de142d14b2967e10"
JAP_API_URL = "https://justanotherpanel.com/api/v2"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ================= 3. CATÁLOGO CON IDS REALES DE JAP =================
SERVICIOS = {
    # --- INSTAGRAM ---
    "ig_likes_1000": {
        "service_id": "1910",
        "nombre": "❤️ 1.000 Likes de Instagram",
        "precio_cup": 1000,
        "cantidad": 1000
    },
    "ig_followers_1000": {
        "service_id": "1810",
        "nombre": "👥 1.000 Seguidores de Instagram",
        "precio_cup": 3500,
        "cantidad": 1000
    },
    # --- TIKTOK ---
    "tt_views_10000": {
        "service_id": "10033",
        "nombre": "👀 10.000 Vistas TikTok",
        "precio_cup": 800,
        "cantidad": 10000
    },
    # --- FACEBOOK ---
    "fb_followers_1000": {
        "service_id": "1889",
        "nombre": "👍 1.000 Seguidores de Página Facebook",
        "precio_cup": 2000,
        "cantidad": 1000
    },
    "fb_likes_1000": {
        "service_id": "1722",
        "nombre": "💙 1.000 Likes Facebook (Posts)",
        "precio_cup": 1500,
        "cantidad": 1000
    },
    # --- COMBOS ---
    "combo_ig_1": {
        "service_id": "1810",
        "nombre": "🔥 Combo: 1.000 Seg + 500 Likes IG",
        "precio_cup": 5000,
        "cantidad": 1000
    }
}

user_data = {}
pending_orders = {}

# ================= 4. FUNCIÓN API JAP =================
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

# ================= 5. COMANDOS BÁSICOS =================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_data.pop(chat_id, None)  # Resetea cualquier estado anterior
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, data in SERVICIOS.items():
        markup.add(
            types.InlineKeyboardButton(
                f"{data['nombre']} ➔ {data['precio_cup']} CUP",
                callback_data=f"buy_{key}"
            )
        )
    
    bot.send_message(
        chat_id,
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
    try:
        res = requests.post(JAP_API_URL, data={"key": JAP_API_KEY, "action": "balance"}, timeout=15).json()
        if "balance" in res:
            bot.reply_to(message, f"💰 Saldo en JAP: {res['balance']} {res.get('currency', 'USD')}")
        else:
            bot.reply_to(message, f"⚠️ Error JAP: {res.get('error', res)}")
    except Exception as e:
        bot.reply_to
