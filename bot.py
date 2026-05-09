# -*- coding: utf-8 -*-
import os
import json
import time
import threading
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template_string, jsonify, request

# Загружаем переменные окружения из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")
bot = telebot.TeleBot(BOT_TOKEN)

ВОЗРАСТ = ["до 3 лет", "3-5 лет", "более 5 лет"]
ТИПЫ = ["Бензин/Дизель", "Гибрид", "Электро"]
ПАРОМ_KRW = 3500000

# Кеширование курсов
_cached_rates = None
_last_update = None
CACHE_DURATION = timedelta(hours=1)

# Хранилище истории расчетов
CALCULATIONS_FILE = "calculations.json"

# Загружаем историю из файла
def load_calculations():
    if os.path.exists(CALCULATIONS_FILE):
        try:
            with open(CALCULATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_calculations(data):
    with open(CALCULATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

calculations_history = load_calculations()

# ============================================
# УТИЛЬСБОР 2026 - ТОЧНЫЕ ДАННЫЕ ИЗ EXCEL
# ============================================

# ЭЛЕКТРО/ГИБРИДЫ 0-3 года (2026)
УТИЛЬ_ELECTRO_0_3 = {
    (0, 80): 3400,
    (81, 100): 991200,
    (101, 130): 1317600,
    (131, 160): 1560000,
    (161, 190): 1848000,
    (191, 220): 2193600,
    (221, 250): 2599200,
    (251, 280): 3079200,
    (281, 9999): 3648000,
}

# ЭЛЕКТРО/ГИБРИДЫ 3-5 лет (2026)
УТИЛЬ_ELECTRO_3_5 = {
    (0, 80): 5200,
    (81, 100): 1641600,
    (101, 130): 1912800,
    (131, 160): 2227200,
    (161, 190): 2594400,
    (191, 220): 3024000,
    (221, 250): 3523200,
    (251, 280): 4104000,
    (281, 9999): 4780800,
}

# ДВС 1.0-2.0L 0-3 года (2026)
УТИЛЬ_DVS_1_2L_0_3 = {
    (0, 160): 3400,
    (161, 190): 900000,
    (191, 220): 952800,
    (221, 250): 1010400,
    (251, 280): 1142400,
    (281, 310): 1291200,
    (311, 340): 1459200,
    (341, 370): 1663200,
    (371, 400): 1896000,
    (401, 430): 2160000,
    (431, 460): 2464800,
    (461, 500): 2808000,
    (501, 9999): 3201600,
}

# ДВС 1.0-2.0L 3-5 лет (2026)
УТИЛЬ_DVS_1_2L_3_5 = {
    (0, 160): 5200,
    (161, 190): 1492800,
    (191, 220): 1584000,
    (221, 250): 1677600,
    (251, 280): 1838400,
    (281, 310): 2011200,
    (311, 340): 2203200,
    (341, 370): 2412000,
    (371, 400): 2640000,
    (401, 430): 2892000,
    (431, 460): 3168000,
    (461, 500): 3468000,
    (501, 9999): 3796800,
}

# ДВС 2.0-3.0L 0-3 года (2026)
УТИЛЬ_DVS_2_3L_0_3 = {
    (0, 160): 3400,
    (161, 190): 2306800,
    (191, 220): 2364000,
    (221, 250): 2402400,
    (251, 280): 2520000,
    (281, 310): 2620800,
    (311, 340): 2726400,
    (341, 370): 2834400,
    (371, 400): 2949600,
    (401, 430): 3067200,
    (431, 460): 3189600,
    (461, 500): 3316800,
    (501, 9999): 3448800,
}

# ДВС 2.0-3.0L 3-5 лет (2026)
УТИЛЬ_DVS_2_3L_3_5 = {
    (0, 160): 5200,
    (161, 190): 3456000,
    (191, 220): 3501600,
    (221, 250): 3552000,
    (251, 280): 3660000,
    (281, 310): 3770400,
    (311, 340): 3873600,
    (341, 370): 4010400,
    (371, 400): 4123200,
    (401, 430): 4248000,
    (431, 460): 4384800,
    (461, 500): 4540800,
    (501, 9999): 4704000,
}

def get_rates():
    """Получаем курсы валют с кешированием каждый час"""
    global _cached_rates, _last_update
    
    # Проверяем, нужно ли обновить кеш
    now = datetime.now()
    if _cached_rates is not None and _last_update is not None and (now - _last_update) < CACHE_DURATION:
        return _cached_rates
    
    try:
        # Получаем курсы относительно USD
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if r.status_code == 200:
            d = r.json()
            if "rates" in d:
                eur_usd = d["rates"].get("EUR", 0.92)
                rub_usd = d["rates"].get("RUB", 92.0)
                # Вычисляем EUR/RUB
                eur_rub = rub_usd / eur_usd if eur_usd != 0 else 87.59
                
                _cached_rates = {
                    "EUR_USD": eur_usd if eur_usd else 1.08,
                    "EUR_RUB": eur_rub if eur_rub else 87.59,
                    "RUB_USD": rub_usd if rub_usd else 92.0
                }
                _last_update = now
                return _cached_rates
    except:
        pass
    
    # Если не удалось получить новые курсы, возвращаем дефолтные
    if _cached_rates is None:
        _cached_rates = {"EUR_USD": 1.08, "EUR_RUB": 87.59, "RUB_USD": 92.0}
        _last_update = now
    return _cached_rates

def set_rates(eur_usd, eur_rub, rub_usd):
    """Устанавливаем курсы вручную"""
    global _cached_rates, _last_update
    _cached_rates = {
        "EUR_USD": float(eur_usd),
        "EUR_RUB": float(eur_rub),
        "RUB_USD": float(rub_usd)
    }
    _last_update = datetime.now()
    return _cached_rates

def get_customs_duty(cc, price_eur, age):
    if age == 0:
        return price_eur * 0.48
    elif age == 1:
        if cc <= 2000:
            return cc * 2.7
        else:
            return cc * 3.0
    else:
        if cc <= 1000: return cc * 3.0
        elif cc <= 1500: return cc * 3.2
        elif cc <= 1800: return cc * 3.5
        elif cc <= 2300: return cc * 4.8
        elif cc <= 3000: return cc * 5.0
        else: return cc * 5.7

def get_processing_fee(price_rub):
    if price_rub <= 200000: return 1231
    elif price_rub <= 450000: return 2462
    elif price_rub <= 1200000: return 4924
    elif price_rub <= 2700000: return 13541
    elif price_rub <= 4200000: return 18465
    elif price_rub <= 5500000: return 21344
    elif price_rub <= 10000000: return 49240
    else: return 73860

def get_excise(hp, vehicle_type):
    if vehicle_type == 2:
        if hp <= 90: return 0
        elif hp <= 150: return 64 * hp
        elif hp <= 200: return 613 * hp
        elif hp <= 300: return 1004 * hp
        elif hp <= 400: return 1711 * hp
        elif hp <= 500: return 1771 * hp
        else: return 1829 * hp
    return 0

def get_util_fee(hp, age, vehicle_type, cc):
    cc_liters = cc / 1000
    
    # Электро/гибрид - отдельная таблица
    if vehicle_type == 2:
        table = УТИЛЬ_ELECTRO_0_3 if age == 0 else УТИЛЬ_ELECTRO_3_5
    # ДВС - зависит от объёма
    elif cc_liters <= 2.0:
        table = УТИЛЬ_DVS_1_2L_0_3 if age == 0 else УТИЛЬ_DVS_1_2L_3_5
    else:  # 2.0-3.0L
        table = УТИЛЬ_DVS_2_3L_0_3 if age == 0 else УТИЛЬ_DVS_2_3L_3_5
    
    for (lo, hi), fee in table.items():
        if lo <= hp <= hi:
            return fee
    
    return 5000000

def calculate(data, rates):
    krw_price = data["price_krw"]
    cc = data["cc"]
    hp = data["hp"]
    age = data["age"]
    vtype = data["type"]
    krw_usd = data["krw_usd"]
    usd_rub = data["usd_rub"]
    delivery_rub = data["delivery_rub"]

    eur_rate = rates["EUR_USD"]
    
    price_usd = krw_price / krw_usd
    price_rub = price_usd * usd_rub
    price_eur = price_rub / usd_rub * eur_rate
    
    base_rub = price_rub
    
    duty_eur = 0
    eur_rub = rates["EUR_RUB"]
    if age == 0:
        duty_rub = price_rub * 0.48
    else:
        duty_eur = get_customs_duty(cc, price_eur, age)
        duty_rub = duty_eur * eur_rub
    
    proc_fee = get_processing_fee(price_rub)
    excise = get_excise(hp, vtype)
    util = get_util_fee(hp, age, vtype, cc)
    
    if vtype == 2:
        vat = (base_rub + duty_rub + excise) * 0.20
    else:
        vat = 0
    
    delivery_ship = (ПАРОМ_KRW / krw_usd) * usd_rub
    broker = 100000
    
    total = base_rub + duty_rub + proc_fee + excise + util + vat + delivery_ship + delivery_rub + broker
    
    return {
        "krw": krw_price, "usd": price_usd, "rub": price_rub, "eur": price_eur,
        "duty_eur": duty_eur, "duty_rub": duty_rub,
        "proc": proc_fee, "excise": excise, "util": util, "vat": vat,
        "delivery_ship": delivery_ship, "delivery_rus": delivery_rub,
        "broker": broker, "total": total
    }

def fmt(n):
    return f"{int(n):,}".replace(",", " ")

waiting = {}
user_data = {}

ШАГИ = [
    ("price_krw", "Введите цену в KRW (пример: 25000000):"),
    ("krw_usd", "Курс KRW/USD (пример: 1350):"),
    ("usd_rub", "Курс USD/RUB (пример: 92):"),
    ("cc", "Объём двигателя в см³ (пример: 2000):"),
    ("hp", "Мощность в л.с. (пример: 150):"),
    ("age", "Возраст авто:\n0 — до 3 лет\n1 — 3-5 лет\n2 — более 5 лет"),
    ("type", "Тип двигателя:\n0 — Бензин/Дизель\n1 — Гибрид\n2 — Электро"),
    ("delivery_rub", "Доставка по России в ₽ (пример: 150000):"),
]

def build_main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🧮 Сделать расчёт", callback_data="calc_start"),
        types.InlineKeyboardButton("🔄 Restart", callback_data="calc_restart"),
    )
    markup.add(types.InlineKeyboardButton("💶 Курс EUR/RUB", callback_data="rate_eur_rub"))

    dashboard_url = os.getenv("DASHBOARD_URL")
    if dashboard_url:
        markup.add(types.InlineKeyboardButton("🌐 Дашборд", url=dashboard_url))

    return markup


def begin_calculation(chat_id):
    user_data[chat_id] = {}
    waiting[chat_id] = 0
    bot.send_message(chat_id, ШАГИ[0][1], parse_mode="HTML")


@bot.message_handler(commands=["start"])
def start(m):
    waiting[m.chat.id] = None
    user_data[m.chat.id] = {}

    rates = get_rates()
    bot.reply_to(
        m,
        f"🚗 <b>Калькулятор авто из Кореи</b>\n\n"
        f"💶 EUR/RUB: {rates['EUR_RUB']:.2f}\n"
        f"Обновлено: {_last_update.strftime('%Y-%m-%d %H:%M:%S') if _last_update else 'Нет данных'}\n\n"
        f"Выберите действие кнопками ниже:",
        parse_mode="HTML",
        reply_markup=build_main_menu_markup(),
    )


@bot.message_handler(commands=["reset"])
def reset(m):
    begin_calculation(m.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    try:
        if call.data == "calc_start":
            bot.answer_callback_query(call.id)
            begin_calculation(call.message.chat.id)
        elif call.data == "calc_restart":
            bot.answer_callback_query(call.id, text="Новый расчёт")
            begin_calculation(call.message.chat.id)
        elif call.data == "rate_eur_rub":
            rates = get_rates()
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"💶 EUR/RUB: {rates['EUR_RUB']:.2f}\n"
                f"Обновлено: {_last_update.strftime('%Y-%m-%d %H:%M:%S') if _last_update else 'Нет данных'}",
            )
        else:
            bot.answer_callback_query(call.id)
    except Exception:
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

@bot.message_handler(func=lambda m: True)
def handle(m):
    cid = m.chat.id
    
    if cid not in waiting or waiting[cid] is None:
        start(m)
        return
    
    step = waiting[cid]
    if step >= len(ШАГИ):
        start(m)
        return
    
    field, prompt = ШАГИ[step]
    text = m.text.strip().replace(" ", "").replace(",", "")
    
    try:
        if field in ["cc", "hp", "age", "type"]:
            value = int(text)
        else:
            value = float(text)
        
        user_data[cid][field] = value
        waiting[cid] = step + 1
        
        if waiting[cid] >= len(ШАГИ):
            rates = get_rates()
            result = calculate(user_data[cid], rates)
            data = user_data[cid]
            
            # Сохраняем расчет в историю
            calc_entry = {
                "timestamp": datetime.now().isoformat(),
                "data": data,
                "result": result
            }
            calculations_history.append(calc_entry)
            # Сохраняем только последние 100 расчетов
            if len(calculations_history) > 100:
                calculations_history = calculations_history[-100:]
            save_calculations(calculations_history)
            
            excise_str = f"  🚬 Акциз: {fmt(result['excise'])} ₽\n" if data["type"] == 2 else ""
            vat_str = f"  💸 НДС 20%: {fmt(result['vat'])} ₽\n" if data["type"] == 2 else ""
            
            response = (
                f"🚗 <b>Расчёт авто из Кореи</b>\n\n"
                f"📍 Цена: {fmt(result['krw'])} KRW → ${result['usd']:,.2f} → {fmt(result['rub'])} ₽\n"
                f"💶 ≈ {fmt(result['eur'])} €\n\n"
                f"⛽ {ТИПЫ[data['type']]}\n"
                f"📅 {ВОЗРАСТ[data['age']]} | 🚗 {data['cc']} см³ | 🐎 {data['hp']} л.с.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>Таможня (calcus.ru):</b>\n"
                f"  Пошлина ({fmt(result['duty_eur'])} €): {fmt(result['duty_rub'])} ₽\n"
                f"  Оформление: {fmt(result['proc'])} ₽\n"
                f"{excise_str}"
                f"  ♻️ Утильсбор: {fmt(result['util'])} ₽\n"
                f"{vat_str}"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚢 Паром (3 500 000 KRW): +{fmt(result['delivery_ship'])} ₽\n"
                f"🚛 Доставка по России: +{fmt(result['delivery_rus'])} ₽\n"
                f"🔗 Брокер: +100 000 ₽\n\n"
                f"💰 <b>ИТОГО: {fmt(result['total'])} ₽</b>\n\n"
                f"/reset — новый расчёт"
            )
            
            bot.reply_to(m, response, parse_mode="HTML")
            waiting[cid] = None
            user_data[cid] = {}
        else:
            next_field, next_prompt = ШАГИ[waiting[cid]]
            bot.reply_to(m, next_prompt, parse_mode="HTML")
            
    except ValueError:
        bot.reply_to(m, "⚠️ Введите число!\n\n" + prompt, parse_mode="HTML")

# Flask дашборд
app = Flask(__name__)

# HTML шаблон для продвинутого дашборда
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>🚗 Korea Export Bot Dashboard PRO</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 900px) { .container { grid-template-columns: 1fr; } }
        .card { background: white; padding: 25px; margin: 10px 0; border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        .full-width { grid-column: 1 / -1; }
        h1 { color: white; text-align: center; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); margin-bottom: 30px; font-size: 2.5em; }
        h2 { color: #333; border-bottom: 3px solid #667eea; padding-bottom: 10px; margin-top: 0; }
        .status { padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 1.2em; }
        .online { background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%); color: #155724; }
        .rates-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 20px; }
        .rate-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }
        .rate-value { font-size: 2em; font-weight: bold; margin: 10px 0; }
        .rate-label { font-size: 0.9em; opacity: 0.9; }
        .updated { color: #666; font-size: 0.9em; margin-top: 15px; text-align: center; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1em; transition: border-color 0.3s; }
        input:focus, select:focus { border-color: #667eea; outline: none; }
        button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 8px; font-size: 1em; cursor: pointer; font-weight: bold; transition: transform 0.2s, box-shadow 0.2s; margin-top: 10px; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .result-box { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 10px; margin-top: 20px; }
        .result-value { font-size: 2.5em; font-weight: bold; text-align: center; }
        .history-item { background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #667eea; }
        .chart-container { position: relative; height: 300px; margin-top: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab { padding: 10px 20px; background: #e0e0e0; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .tab.active { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <h1>🚗 Korea Export Bot Dashboard PRO</h1>
    
    <div class="container">
        <div class="card full-width">
            <div class="status online">✅ Бот работает</div>
        </div>
        
        <div class="card">
            <h2>📊 Текущие курсы валют</h2>
            <div class="rates-grid">
                <div class="rate-card">
                    <div class="rate-label">EUR/USD</div>
                    <div class="rate-value" id="eur-usd">{{ "%.2f"|format(rates.EUR_USD) }}</div>
                </div>
                <div class="rate-card">
                    <div class="rate-label">EUR/RUB</div>
                    <div class="rate-value" id="eur-rub">{{ "%.2f"|format(rates.EUR_RUB) }}</div>
                </div>
                <div class="rate-card">
                    <div class="rate-label">RUB/USD</div>
                    <div class="rate-value" id="rub-usd">{{ "%.2f"|format(rates.RUB_USD) }}</div>
                </div>
            </div>
            <p class="updated">Обновлено: {{ last_update }}</p>
        </div>
        
        <div class="card">
            <h2>✏️ Редактировать курсы</h2>
            <div>
                <label>EUR/USD:</label>
                <input type="number" step="0.01" id="edit-eur-usd" value="{{ rates.EUR_USD }}">
            </div>
            <div>
                <label>EUR/RUB:</label>
                <input type="number" step="0.01" id="edit-eur-rub" value="{{ rates.EUR_RUB }}">
            </div>
            <div>
                <label>RUB/USD:</label>
                <input type="number" step="0.01" id="edit-rub-usd" value="{{ rates.RUB_USD }}">
            </div>
            <button onclick="updateRates()">💾 Сохранить курсы</button>
            <button onclick="refreshRates()">🔄 Обновить из API</button>
        </div>
        
        <div class="card full-width">
            <h2>🧮 Калькулятор</h2>
            <div class="container">
                <div>
                    <label>Цена в KRW:</label>
                    <input type="number" id="calc-price-krw" placeholder="25000000">
                    
                    <label>Курс KRW/USD:</label>
                    <input type="number" step="0.01" id="calc-krw-usd" placeholder="1350">
                    
                    <label>Курс USD/RUB:</label>
                    <input type="number" step="0.01" id="calc-usd-rub" placeholder="92">
                    
                    <label>Объём двигателя (см³):</label>
                    <input type="number" id="calc-cc" placeholder="2000">
                    
                    <label>Мощность (л.с.):</label>
                    <input type="number" id="calc-hp" placeholder="150">
                </div>
                <div>
                    <label>Возраст авто:</label>
                    <select id="calc-age">
                        <option value="0">до 3 лет</option>
                        <option value="1">3-5 лет</option>
                        <option value="2">более 5 лет</option>
                    </select>
                    
                    <label>Тип двигателя:</label>
                    <select id="calc-type">
                        <option value="0">Бензин/Дизель</option>
                        <option value="1">Гибрид</option>
                        <option value="2">Электро</option>
                    </select>
                    
                    <label>Доставка по России (₽):</label>
                    <input type="number" id="calc-delivery" placeholder="150000">
                    
                    <button onclick="calculateCost()" style="width: 100%; margin-top: 20px;">💰 Рассчитать</button>
                </div>
            </div>
            <div id="calc-result"></div>
        </div>
        
        <div class="card full-width">
            <h2>📈 Графики и история</h2>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('chart')">📊 График</div>
                <div class="tab" onclick="switchTab('history')">📜 История</div>
            </div>
            <div id="tab-chart" class="tab-content active">
                <div class="chart-container">
                    <canvas id="historyChart"></canvas>
                </div>
            </div>
            <div id="tab-history" class="tab-content">
                <div id="history-list"></div>
            </div>
        </div>
    </div>

    <script>
        let historyData = [];
        let chart = null;

        // Загрузка истории
        async function loadHistory() {
            const response = await fetch('/api/history');
            const data = await response.json();
            historyData = data.history;
            updateChart();
            updateHistoryList();
        }

        // Обновление графика
        function updateChart() {
            const ctx = document.getElementById('historyChart').getContext('2d');
            const labels = historyData.slice(-20).map((item, i) => {
                const date = new Date(item.timestamp);
                return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
            });
            const totals = historyData.slice(-20).map(item => item.result.total);

            if (chart) chart.destroy();
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Итоговая стоимость (₽)',
                        data: totals,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true }
                    },
                    scales: {
                        y: { beginAtZero: false }
                    }
                }
            });
        }

        // Обновление списка истории
        function updateHistoryList() {
            const list = document.getElementById('history-list');
            list.innerHTML = historyData.slice(-10).reverse().map(item => {
                const date = new Date(item.timestamp);
                return `
                    <div class="history-item">
                        <strong>${date.toLocaleString('ru-RU')}</strong><br>
                        Цена: ${item.data.price_krw.toLocaleString()} KRW → Итого: ${Math.round(item.result.total).toLocaleString()} ₽
                    </div>
                `;
            }).join('');
        }

        // Переключение табов
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }

        // Обновление курсов
        async function updateRates() {
            const eurUsd = document.getElementById('edit-eur-usd').value;
            const eurRub = document.getElementById('edit-eur-rub').value;
            const rubUsd = document.getElementById('edit-rub-usd').value;
            
            const response = await fetch('/api/rates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ eur_usd: eurUsd, eur_rub: eurRub, rub_usd: rubUsd })
            });
            
            const data = await response.json();
            document.getElementById('eur-usd').textContent = data.rates.EUR_USD.toFixed(2);
            document.getElementById('eur-rub').textContent = data.rates.EUR_RUB.toFixed(2);
            document.getElementById('rub-usd').textContent = data.rates.RUB_USD.toFixed(2);
            alert('✅ Курсы обновлены!');
        }

        // Обновление курсов из API
        async function refreshRates() {
            location.reload();
        }

        // Расчет стоимости
        async function calculateCost() {
            const data = {
                price_krw: parseFloat(document.getElementById('calc-price-krw').value) || 0,
                krw_usd: parseFloat(document.getElementById('calc-krw-usd').value) || 0,
                usd_rub: parseFloat(document.getElementById('calc-usd-rub').value) || 0,
                cc: parseInt(document.getElementById('calc-cc').value) || 0,
                hp: parseInt(document.getElementById('calc-hp').value) || 0,
                age: parseInt(document.getElementById('calc-age').value),
                type: parseInt(document.getElementById('calc-type').value),
                delivery_rub: parseFloat(document.getElementById('calc-delivery').value) || 0
            };
            
            const response = await fetch('/api/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            document.getElementById('calc-result').innerHTML = `
                <div class="result-box">
                    <div style="text-align: center; font-size: 1.2em; margin-bottom: 10px;">💰 ИТОГО</div>
                    <div class="result-value">${Math.round(result.total).toLocaleString()} ₽</div>
                    <div style="margin-top: 15px; text-align: center;">
                        Цена: ${result.krw.toLocaleString()} KRW → ${result.usd.toFixed(2)} → ${Math.round(result.rub).toLocaleString()} ₽
                    </div>
                </div>
            `;
            loadHistory();
        }

        // Загружаем историю при загрузке страницы
        loadHistory();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    rates = get_rates()
    return render_template_string(
        DASHBOARD_HTML,
        rates=rates,
        last_update=_last_update.strftime('%Y-%m-%d %H:%M:%S') if _last_update else 'Нет данных'
    )

@app.route('/api/rates', methods=['GET', 'POST'])
def api_rates():
    if request.method == 'POST':
        data = request.json
        rates = set_rates(data['eur_usd'], data['eur_rub'], data['rub_usd'])
        return jsonify({"rates": rates})
    rates = get_rates()
    return jsonify({
        "rates": rates,
        "last_update": _last_update.isoformat() if _last_update else None
    })

@app.route('/api/history')
def api_history():
    return jsonify({"history": calculations_history})

@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    data = request.json
    rates = get_rates()
    result = calculate(data, rates)
    
    # Сохраняем расчет в историю
    calc_entry = {
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "result": result
    }
    calculations_history.append(calc_entry)
    if len(calculations_history) > 100:
        calculations_history[:] = calculations_history[-100:]
    save_calculations(calculations_history)
    
    return jsonify(result)

def run_bot():
    """Запускаем бота с автоперезапуском при сбоях"""
    while True:
        try:
            print("🚀 Бот запущен...")
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except ApiTelegramException as e:
            if getattr(e, "error_code", None) == 409:
                print("⚠️ Conflict 409: другой процесс уже делает getUpdates. Остановите второй инстанс/деплой.")
                time.sleep(15)
            else:
                print(f"❌ Ошибка Telegram API: {e}")
                time.sleep(5)
        except Exception as e:
            print(f"❌ Ошибка бота: {e}")
            time.sleep(5)
        finally:
            try:
                bot.stop_polling()
            except Exception:
                pass

def run_flask():
    """Запускаем Flask дашборд с автоперезапуском при сбоях"""
    while True:
        try:
            port = int(os.getenv("PORT", 5000))
            print(f"🌐 Дашборд запущен на порту {port}...")
            app.run(host='0.0.0.0', port=port, use_reloader=False)
        except Exception as e:
            print(f"❌ Ошибка дашборда: {e}")
            print("⏳ Перезапуск дашборда через 5 секунд...")
            time.sleep(5)

def prefetch_euro_rate():
    print("🔄 Загружаем курс евро...")
    rates = get_rates()
    print("✅ Курс евро:")
    print(f"   EUR/RUB: {rates['EUR_RUB']:.2f}")
    print(f"   Обновлено: {_last_update.strftime('%Y-%m-%d %H:%M:%S') if _last_update else 'Нет данных'}")
    print()

if __name__ == "__main__":
    app_role = (os.getenv("APP_ROLE") or "both").strip().lower()

    if app_role == "worker":
        prefetch_euro_rate()
        run_bot()
    elif app_role == "web":
        run_flask()
    else:
        prefetch_euro_rate()

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        print("✅ Все сервисы запущены!")
        while True:
            time.sleep(1)