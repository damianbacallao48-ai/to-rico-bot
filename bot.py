import os
import sqlite3
import threading
import requests
from flask import Flask
from telebot import TeleBot, types

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
# Token oficial del nuevo bot @ImpulsoRedesPro_bot
BOT_TOKEN = "8998730541:AAGqFZjYSSyiHl_qu_Ow2wGz9yPQXX2p58Q"
os.environ["BOT_TOKEN"] = BOT_TOKEN  # Sobrescribe variables residuales en el servidor

ADMIN_ID = 6731555041
CANAL_ENLACE = "https://t.me/torico_cuba_db"
ADMIN_USER = "@torico_cuba_db"

# ============================================================
# CREDENCIALES DEL PROVEEDOR SMM MAYORISTA
# ============================================================
SMM_API_URL = "https://tuprioridadsmm.com/api/v2"
SMM_API_KEY = "TU_API_KEY_DEL_PROVEEDOR"

# Catálogo de servicios configurados
SERVICIOS = {
    "tt_views": {
        "nombre": "🎵 TikTok - Vistas Rápidas",
        "service_id": 101,
        "precio_por_1k": 50.0,
        "min": 100,
        "max": 50000,
    },
    "tt_likes": {
        "nombre": "❤️ TikTok - Likes Reales",
        "service_id": 102,
        "precio_por_1k": 150.0,
        "min": 50,
        "max": 10000,
    },
    "ig_views": {
        "nombre": "📸 Instagram - Vistas Reels",
        "service_id": 201,
        "precio_por_1k": 60.0,
        "min": 100,
        "max": 50000,
    },
    "ig_likes": {
        "nombre": "❤️ Instagram - Likes",
        "service_id": 202,
        "precio_por_1k": 180.0,
        "min": 50,
        "max": 10000,
    },
    "yt_views": {
        "nombre": "▶️ YouTube - Vistas / Shorts",
        "service_id": 301,
        "precio_por_1k": 200.0,
        "min": 500,
        "max": 20000,
    },
}

DB_FILE = "smm_panel.db"
DB_LOCK = threading.RLock()

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

SESION_COMPRA = {}


# ============================================================
# SERVIDOR WEB PARA MANTENER ACTIVO RAILWAY
# ============================================================
@app.route("/")
def home():
    return "Bot SMM Activo y en Línea"


def iniciar_servidor_web():
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ============================================================
# BASE DE DATOS
# ============================================================
def obtener_conexion():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def inicializar_bd():
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    user_id INTEGER PRIMARY KEY,
                    saldo REAL DEFAULT 0.0,
                    total_gastado REAL DEFAULT 0.0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    servicio TEXT,
                    enlace TEXT,
                    cantidad INTEGER,
                    costo REAL,
                    orden_id_proveedor TEXT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def obtener_cliente(user_id):
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            cur = conn.cursor()
            cur.execute("SELECT saldo, total_gastado FROM clientes WHERE user_id = ?", (user_id,))
            res = cur.fetchone()
            if not res:
                cur.execute("INSERT INTO clientes (user_id, saldo, total_gastado) VALUES (?, 0.0, 0.0)", (user_id,))
                conn.commit()
                return 0.0, 0.0
            return res[0], res[1]
        finally:
            conn.close()


def ajustar_saldo(user_id, monto):
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO clientes (user_id, saldo, total_gastado)
                VALUES (?, ?, 0.0)
                ON CONFLICT(user_id)
                DO UPDATE SET saldo = saldo + ?
                """,
                (user_id, monto, monto),
            )
            conn.commit()
        finally:
            conn.close()


def registrar_pedido(user_id, servicio_clave, enlace, cantidad, costo, id_externo):
    with DB_LOCK:
        conn = obtener_conexion()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE clientes SET saldo = saldo - ?, total_gastado = total_gastado + ? WHERE user_id = ?",
                (costo, costo, user_id),
            )
            cur.execute(
                """
                INSERT INTO pedidos (user_id, servicio, enlace, cantidad, costo, orden_id_proveedor)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, servicio_clave, enlace, cantidad, costo, str(id_externo)),
            )
            conn.commit()
        finally:
            conn.close()


# ============================================================
# CONEXIÓN CON API MAYORISTA SMM
# ============================================================
def enviar_orden_mayorista(service_id, enlace, cantidad):
    if SMM_API_KEY == "TU_API_KEY_DEL_PROVEEDOR":
        orden_ficticia = f"DEMO-{os.urandom(4).hex().upper()}"
        return True, orden_ficticia

    try:
        payload = {
            "key": SMM_API_KEY,
            "action": "add",
            "service": service_id,
            "link": enlace,
            "quantity": cantidad,
        }
        res = requests.post(SMM_API_URL, data=payload, timeout=20)
        datos = res.json()
        if "order" in datos:
            return True, datos["order"]
        return False, datos.get("error", "Error del panel mayorista")
    except Exception as e:
        print(f"Fallo contactando API mayorista: {e}")
        return False, str(e)


# ============================================================
# COMANDOS PRINCIPALES
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    saldo, _ = obtener_cliente(user_id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_pedir = types.InlineKeyboardButton("🛒 Realizar Pedido", callback_data="menu_servicios")
    btn_saldo = types.InlineKeyboardButton("💳 Recargar Saldo", callback_data="menu_recarga")
    btn_perfil = types.InlineKeyboardButton("👤 Mi Cuenta", callback_data="menu_cuenta")
    markup.add(btn_pedir)
    markup.add(btn_saldo, btn_perfil)

    texto = (
        "🚀 <b>¡Bienvenido al Panel de Crecimiento en Redes!</b>\n\n"
        "Impulsa tus videos, publicaciones y canales al instante con vistas, likes y reproducciones.\n\n"
        f"💰 <b>Tu Saldo disponible:</b> <code>${saldo:.2f} créditos</code>\n"
        f"🆔 <b>Tu ID:</b> <code>{user_id}</code>\n\n"
        "Elige una opción en el menú inferior:"
    )
    bot.reply_to(message, texto, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "menu_servicios")
def mostrar_servicios(call):
    markup = types.InlineKeyboardMarkup()
    for clave, s in SERVICIOS.items():
        btn = types.InlineKeyboardButton(
            f"{s['nombre']} (${s['precio_por_1k']:.0f}/1k)",
            callback_data=f"sel_{clave}",
        )
        markup.add(btn)

    markup.add(types.InlineKeyboardButton("🔙 Volver", callback_data="menu_inicio"))
    bot.edit_message_text(
        "📋 <b>Selecciona el servicio que deseas solicitar:</b>",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_"))
def iniciar_flujo_pedido(call):
    user_id = call.from_user.id
    clave = call.data.replace("sel_", "")
    servicio = SERVICIOS.get(clave)

    if not servicio:
        bot.answer_callback_query(call.id, "Servicio no disponible.")
        return

    SESION_COMPRA[user_id] = {"servicio": clave, "paso": "esperando_enlace"}

    texto = (
        f"📌 <b>Has seleccionado:</b> {servicio['nombre']}\n\n"
        f"💵 <b>Precio:</b> ${servicio['precio_por_1k']:.2f} por cada 1,000 unidades.\n"
        f"📊 <b>Mínimo:</b> {servicio['min']} | <b>Máximo:</b> {servicio['max']}\n\n"
        "👉 <b>Envía ahora el enlace (URL) de tu video o perfil:</b>"
    )
    bot.edit_message_text(
        texto,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "menu_cuenta")
def ver_cuenta(call):
    user_id = call.from_user.id
    saldo, gastado = obtener_cliente(user_id)
    texto = (
        "👤 <b>Estado de tu Cuenta</b>\n\n"
        f"🆔 <b>ID de Usuario:</b> <code>{user_id}</code>\n"
        f"💰 <b>Saldo disponible:</b> <code>${saldo:.2f} créditos</code>\n"
        f"📊 <b>Total invertido:</b> <code>${gastado:.2f} créditos</code>\n"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Volver", callback_data="menu_inicio"))
    bot.edit_message_text(
        texto,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "menu_recarga")
def ver_recarga(call):
    user_id = call.from_user.id
    texto = (
        "💳 <b>Recarga de Saldo</b>\n\n"
        "Para agregar fondos a tu cuenta, contacta al administrador:\n"
        f"👤 <b>Administrador:</b> {ADMIN_USER}\n"
        f"🆔 <b>Tu ID para acreditar:</b> <code>{user_id}</code>\n\n"
        "Aceptamos transferencias y pagos directos. Al confirmar el pago, tu saldo se reflejará al instante."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Contactar Soporte", url=f"https://t.me/{ADMIN_USER.replace('@', '')}"))
    markup.add(types.InlineKeyboardButton("🔙 Volver", callback_data="menu_inicio"))
    bot.edit_message_text(
        texto,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: call.data == "menu_inicio")
def volver_inicio(call):
    user_id = call.from_user.id
    saldo, _ = obtener_cliente(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_pedir = types.InlineKeyboardButton("🛒 Realizar Pedido", callback_data="menu_servicios")
    btn_saldo = types.InlineKeyboardButton("💳 Recargar Saldo", callback_data="menu_recarga")
    btn_perfil = types.InlineKeyboardButton("👤 Mi Cuenta", callback_data="menu_cuenta")
    markup.add(btn_pedir)
    markup.add(btn_saldo, btn_perfil)

    texto = (
        "🚀 <b>Panel Principal</b>\n\n"
        f"💰 <b>Saldo disponible:</b> <code>${saldo:.2f} créditos</code>\n"
        f"🆔 <b>Tu ID:</b> <code>{user_id}</code>\n\n"
        "Elige una opción:"
    )
    bot.edit_message_text(
        texto,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML",
    )


# ============================================================
# PROCESAMIENTO DE TEXTO (ENLACE Y CANTIDAD)
# ============================================================
@bot.message_handler(func=lambda m: m.from_user.id in SESION_COMPRA)
def procesar_paso_compra(message):
    user_id = message.from_user.id
    estado = SESION_COMPRA.get(user_id)
    texto = message.text.strip()

    if estado["paso"] == "esperando_enlace":
        if not ("http://" in texto or "https://" in texto):
            bot.reply_to(message, "⚠️ Envía un enlace válido que empiece por https://")
            return

        estado["enlace"] = texto
        estado["paso"] = "esperando_cantidad"
        s = SERVICIOS[estado["servicio"]]

        bot.reply_to(
            message,
            (
                "✅ <b>Enlace recibido.</b>\n\n"
                f"¿Cuánta cantidad deseas enviar?\n"
                f"• Mínimo: <b>{s['min']}</b>\n"
                f"• Máximo: <b>{s['max']}</b>\n\n"
                "👉 <b>Escribe solo el número:</b>"
            ),
            parse_mode="HTML",
        )

    elif estado["paso"] == "esperando_cantidad":
        if not texto.isdigit():
            bot.reply_to(message, "❌ Por favor escribe un número entero válido.")
            return

        cantidad = int(texto)
        s = SERVICIOS[estado["servicio"]]

        if cantidad < s["min"] or cantidad > s["max"]:
            bot.reply_to(message, f"❌ La cantidad debe estar entre {s['min']} y {s['max']}.")
            return

        costo = (cantidad / 1000.0) * s["precio_por_1k"]
        saldo_actual, _ = obtener_cliente(user_id)

        if saldo_actual < costo:
            bot.reply_to(
                message,
                (
                    f"❌ <b>Saldo insuficiente.</b>\n\n"
                    f"Costo del pedido: <b>${costo:.2f} créditos</b>\n"
                    f"Tu saldo: <b>${saldo_actual:.2f} créditos</b>\n\n"
                    "Recarga saldo en el menú principal para procesar esta orden."
                ),
                parse_mode="HTML",
            )
            SESION_COMPRA.pop(user_id, None)
            return

        msg_espera = bot.reply_to(message, "⏳ <b>Procesando orden...</b>", parse_mode="HTML")
        exito, resultado = enviar_orden_mayorista(s["service_id"], estado["enlace"], cantidad)

        if exito:
            registrar_pedido(user_id, estado["servicio"], estado["enlace"], cantidad, costo, resultado)
            bot.edit_message_text(
                (
                    "🎉 <b>¡Orden enviada con éxito!</b>\n\n"
                    f"📌 <b>Servicio:</b> {s['nombre']}\n"
                    f"🔢 <b>Cantidad:</b> {cantidad}\n"
                    f"💰 <b>Total descontado:</b> ${costo:.2f} créditos\n"
                    f"🔖 <b>ID de Orden:</b> <code>{resultado}</code>\n\n"
                    "El servicio comenzará a reflejarse en los próximos minutos."
                ),
                chat_id=message.chat.id,
                message_id=msg_espera.message_id,
                parse_mode="HTML",
            )
        else:
            bot.edit_message_text(
                f"❌ Error al procesar con el proveedor: <code>{resultado}</code>\nNo se ha descontado saldo.",
                chat_id=message.chat.id,
                message_id=msg_espera.message_id,
                parse_mode="HTML",
            )

        SESION_COMPRA.pop(user_id, None)


# ============================================================
# PANEL DE CONTROL DE ADMINISTRADOR
# ============================================================
@bot.message_handler(commands=["recargar"])
def cmd_recargar_admin(message):
    """Comando exclusivo para el dueño: /recargar USER_ID MONTO"""
    if message.from_user.id != ADMIN_ID:
        return

    partes = message.text.split()
    if len(partes) < 3:
        bot.reply_to(message, "Uso: <code>/recargar ID_USUARIO MONTO</code>", parse_mode="HTML")
        return

    try:
        target_id = int(partes[1])
        monto = float(partes[2])
        ajustar_saldo(target_id, monto)
        nuevo_saldo, _ = obtener_cliente(target_id)

        bot.reply_to(
            message,
            f"✅ Se han acreditado <b>${monto:.2f}</b> al usuario <code>{target_id}</code>.\nSaldo actual: <b>${nuevo_saldo:.2f} créditos</b>",
            parse_mode="HTML",
        )

        try:
            bot.send_message(
                target_id,
                f"🎉 <b>¡Tu saldo ha sido recargado!</b>\n\nSe agregaron <b>${monto:.2f} créditos</b> a tu cuenta.\nSaldo total disponible: <b>${nuevo_saldo:.2f} créditos</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    except ValueError:
        bot.reply_to(message, "❌ Formato incorrecto. El ID debe ser un número entero y el monto un número.")


# ============================================================
# INICIO
# ============================================================
if __name__ == "__main__":
    print("Iniciando base de datos SMM...")
    inicializar_bd()

    print("Iniciando servidor web...")
    threading.Thread(target=iniciar_servidor_web, daemon=True).start()

    print("Bot SMM listo y en escucha...")
    bot.infinity_polling(timeout=30, skip_pending=True)
