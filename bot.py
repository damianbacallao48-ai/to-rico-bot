import os
import requests
import telebot
from telebot import types

TOKEN = "8998730541:AAE4p-o4lCvShtYy5alFEXnOFn5SCDmDtR0"
ADMIN_ID = 6731555041
JAP_KEY = "b1aede7e7f18cdf8de142d14b2967e10"
JAP_URL = "https://justanotherpanel.com/api/v2"

bot = telebot.TeleBot(TOKEN)

SERVICIOS = {
    # Instagram Seguidores (30D Garantía) -> Costo: ~2.011 CUP | Ganancia: +1.488 CUP
    "ig_fol": {"id": "10129", "name": "👥 1.000 Seguidores IG (Garantía 30D)", "cup": 3500, "qty": 1000},
    
    # Instagram Likes (30D Garantía) -> Costo: ~375 CUP | Ganancia: +625 CUP
    "ig_likes": {"id": "10130", "name": "❤️ 1.000 Likes IG (Garantía 30D)", "cup": 1000, "qty": 1000},
    
    # TikTok Vistas -> Costo: ~15 CUP | Ganancia: +785 CUP
    "tt_views": {"id": "10333", "name": "👀 10.000 Vistas TikTok", "cup": 800, "qty": 10000},
    
    # TikTok Seguidores (30D Garantía) -> Costo: ~1.732 CUP | Ganancia: +1.268 CUP
    "tt_fol": {"id": "9777", "name": "🎵 1.000 Seguidores TikTok (Garantía 30D)", "cup": 3000, "qty": 1000},
    
    # Facebook Seguidores de Página -> Costo: ~543 CUP | Ganancia: +1.457 CUP
    "fb_fol": {"id": "1724", "name": "👍 1.000 Seguidores FB Página", "cup": 2000, "qty": 1000},
    
    # Facebook Likes de Página (30D Garantía) -> Costo: ~524 CUP | Ganancia: +976 CUP
    "fb_likes": {"id": "9230", "name": "💙 1.000 Likes FB Página (Garantía 30D)", "cup": 1500, "qty": 1000},
    
    # Combo: 1k Seg (ID 10129) + 500 Likes IG -> Costo: ~2.200 CUP | Ganancia: +1.800 CUP
    "combo": {"id": "10129", "name": "🔥 Combo: 1k Seg + 500 Likes IG", "cup": 4000, "qty": 1000}
}

user_data = {}
orders = {}

def call_jap(srv_id, link, qty):
    data = {"key": JAP_KEY, "action": "add", "service": str(srv_id), "link": link, "quantity": str(qty)}
    try:
        return requests.post(JAP_URL, data=data, timeout=25).json
