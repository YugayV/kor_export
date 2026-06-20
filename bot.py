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
APP_ROLE = (os.getenv("APP_ROLE") or "both").strip().lower()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN and APP_ROLE != "web":
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
bot = telebot.TeleBot(BOT_TOKEN or "0:0")

OWNER_LABELS = {
    1: "Физическое лицо (для личного использования)",
    2: "Юридическое лицо",
    3: "Физическое лицо (для перепродажи)",
}

AGE_LABELS = {
    "0-3": "до 3 лет",
    "3-5": "от 3 до 5 лет",
    "5-7": "от 5 до 7 лет",
    "7-0": "от 7 лет",
}

ENGINE_LABELS = {
    1: "Бензиновый",
    2: "Дизельный",
    4: "Электрический",
    5: "Последовательный гибрид",
    6: "Параллельный гибрид",
}

POWER_UNIT_LABELS = {
    1: "л.с.",
    2: "кВт",
}

CURRENCY_LABELS = {
    "RUB": "Российский рубль",
    "USD": "Доллар США",
    "EUR": "Евро",
    "CNY": "Китайский юань",
    "JPY": "Японская йена",
    "KRW": "Корейская вона",
}

AGE_INPUT_MAP = {
    1: "0-3",
    2: "3-5",
    3: "5-7",
    4: "7-0",
}

CURRENCY_INPUT_MAP = {
    1: "RUB",
    2: "USD",
    3: "EUR",
    4: "CNY",
    5: "JPY",
    6: "KRW",
}

ELECTRIC_LIKE_ENGINES = {4, 5}
ICE_ENGINES = {1, 2, 6}
POWER_KW_PER_HP = 1 / 1.3596

# 2026 amounts. For 2025 and 2027-2030 calcus scales util coefficients by year.
UTIL_YEAR_FACTORS = {
    2025: 1 / 1.2,
    2026: 1.0,
    2027: 1.1,
    2028: 1.21,
    2029: 1.331,
    2030: 1.4641,
}

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

UTIL_TABLE_PERSONAL_EV = [
    (58.85, 3400, 5200),
    (73.55, 991200, 1641600),
    (95.61, 1317600, 1912800),
    (117.68, 1560000, 2227200),
    (139.75, 1848000, 2594400),
    (161.81, 2193600, 3024000),
    (183.88, 2599200, 3523200),
    (205.94, 3079200, 4104000),
    (9999.0, 3648000, 4780800),
]

UTIL_TABLE_PERSONAL_1_2 = [
    (117.68, 3400, 5200),
    (139.75, 900000, 1492800),
    (161.81, 952800, 1584000),
    (183.0, 1010400, 1677600),
    (205.94, 1142400, 1838400),
    (228.0, 1291200, 2011200),
    (250.0, 1459200, 2203200),
    (272.13, 1663200, 2412000),
    (294.2, 1896000, 2640000),
    (316.26, 2160000, 2892000),
    (338.33, 2464800, 3168000),
    (367.75, 2808000, 3468000),
    (9999.0, 3201600, 3796800),
]

UTIL_TABLE_PERSONAL_2_3 = [
    (117.68, 3400, 5200),
    (139.75, 2306800, 3456000),
    (161.81, 2364000, 3501600),
    (183.88, 2402400, 3552000),
    (205.94, 2520000, 3660000),
    (228.0, 2620800, 3770400),
    (250.0, 2726400, 3873600),
    (272.13, 2834400, 4010400),
    (294.2, 2949600, 4123200),
    (316.26, 3067200, 4248000),
    (338.33, 3189600, 4384800),
    (367.75, 3316800, 4540800),
    (9999.0, 3448800, 4704000),
]

UTIL_TABLE_COMMERCIAL_EV = [
    (58.85, 800800, 1408800),
    (73.55, 991200, 1641600),
    (95.61, 1317600, 1912800),
    (117.68, 1560000, 2227200),
    (139.75, 1848000, 2594400),
    (161.81, 2193600, 3024000),
    (183.88, 2599200, 3523200),
    (205.94, 3079200, 4104000),
    (9999.0, 3648000, 4780800),
]

UTIL_TABLE_COMMERCIAL_1_2 = [
    (51.48, 800800, 1408800),
    (73.55, 800800, 1408800),
    (95.61, 800800, 1408800),
    (117.68, 800800, 1408800),
    (139.75, 900000, 1492800),
    (161.81, 952800, 1584000),
    (183.88, 1010400, 1677600),
    (205.94, 1142400, 1838400),
    (228.0, 1291200, 2011200),
    (250.0, 1459200, 2203200),
    (272.13, 1663200, 2412000),
    (294.2, 1896000, 2640000),
    (316.26, 2160000, 2892000),
    (338.33, 2464800, 3168000),
    (367.75, 2808000, 3468000),
    (9999.0, 3201600, 3796800),
]

UTIL_TABLE_COMMERCIAL_2_3 = [
    (51.48, 2250400, 3407200),
    (73.55, 2250400, 3407200),
    (95.61, 2250400, 3407200),
    (117.68, 2250400, 3407200),
    (139.75, 2306800, 3456000),
    (161.81, 2364000, 3501600),
    (183.88, 2402400, 3552000),
    (205.94, 2520000, 3660000),
    (228.0, 2620800, 3770400),
    (250.0, 2726400, 3873600),
    (272.13, 2834400, 4010400),
    (294.2, 2949600, 4094400),
    (316.26, 3067200, 4209600),
    (338.33, 3189600, 4327200),
    (367.75, 3316800, 4447200),
    (9999.0, 3448800, 4572000),
]

UTIL_TABLE_COMMERCIAL_3_3_5 = [
    (51.48, 2584000, 3956200),
    (73.55, 2584000, 3956200),
    (95.61, 2584000, 3956200),
    (117.68, 2584000, 3956200),
    (139.75, 2635200, 4000800),
    (161.81, 2688000, 4044000),
    (183.88, 2743200, 4087200),
    (205.94, 2810400, 4144800),
    (228.0, 2880000, 4248000),
    (250.0, 3038400, 4356000),
    (272.13, 3206400, 4485600),
    (294.2, 3384000, 4620000),
    (316.26, 3568800, 4759200),
    (338.33, 3765600, 4900800),
    (367.75, 3972000, 5049600),
    (9999.0, 4190400, 5200800),
]

UTIL_TABLE_COMMERCIAL_3_5_PLUS = [
    (51.48, 3290600, 4325800),
    (73.55, 3290600, 4325800),
    (95.61, 3290600, 4325800),
    (117.68, 3290600, 4325800),
    (139.75, 3345600, 4389600),
    (161.81, 3403200, 4456800),
    (183.88, 3460800, 4524000),
    (205.94, 3530400, 4627200),
    (228.0, 3600000, 4732800),
    (250.0, 3727200, 4992000),
    (272.13, 3857600, 5268000),
    (294.2, 3993600, 5558400),
    (316.26, 4132800, 5863200),
    (338.33, 4276800, 6187200),
    (367.75, 4425600, 6528000),
    (9999.0, 4581600, 6885600),
]

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
                krw_usd = d["rates"].get("KRW", 1350.0)
                cny_usd = d["rates"].get("CNY", 7.0)
                jpy_usd = d["rates"].get("JPY", 157.0)
                # Вычисляем EUR/RUB
                eur_rub = rub_usd / eur_usd if eur_usd != 0 else 87.59
                
                _cached_rates = {
                    "EUR_USD": eur_usd if eur_usd else 1.08,
                    "EUR_RUB": eur_rub if eur_rub else 87.59,
                    "RUB_USD": rub_usd if rub_usd else 92.0,
                    "USD_RUB": rub_usd if rub_usd else 92.0,
                    "KRW_USD": krw_usd if krw_usd else 1350.0,
                    "CNY_USD": cny_usd if cny_usd else 7.0,
                    "JPY_USD": jpy_usd if jpy_usd else 157.0,
                }
                _last_update = now
                return _cached_rates
    except:
        pass
    
    # Если не удалось получить новые курсы, возвращаем дефолтные
    if _cached_rates is None:
        _cached_rates = {
            "EUR_USD": 1.08,
            "EUR_RUB": 87.59,
            "RUB_USD": 92.0,
            "USD_RUB": 92.0,
            "KRW_USD": 1350.0,
            "CNY_USD": 7.0,
            "JPY_USD": 157.0,
        }
        _last_update = now
    return _cached_rates

def set_rates(eur_usd, eur_rub, rub_usd):
    """Устанавливаем курсы вручную"""
    global _cached_rates, _last_update
    _cached_rates = {
        "EUR_USD": float(eur_usd),
        "EUR_RUB": float(eur_rub),
        "RUB_USD": float(rub_usd),
        "USD_RUB": float(rub_usd),
        "KRW_USD": 1350.0,
        "CNY_USD": 7.0,
        "JPY_USD": 157.0,
    }
    _last_update = datetime.now()
    return _cached_rates

def get_age_code(year=None, age=None):
    if isinstance(age, str) and age in AGE_LABELS:
        return age

    if year not in (None, "", 0):
        current_year = datetime.now().year
        car_year = int(year)
        age_years = max(0, current_year - car_year)
        if age_years <= 2:
            return "0-3"
        if age_years <= 4:
            return "3-5"
        if age_years <= 6:
            return "5-7"
        return "7-0"

    if age is not None:
        return AGE_INPUT_MAP.get(int(age), "0-3")

    return "0-3"


def get_power_hp(power, power_unit):
    power = float(power)
    if int(power_unit) == 1:
        return power
    return power / POWER_KW_PER_HP


def get_power_kw(power, power_unit):
    power = float(power)
    if int(power_unit) == 2:
        return power
    return power * POWER_KW_PER_HP


def get_price_usd(price, currency, rates, krw_usd=None, usd_rub=None):
    price = float(price)
    currency = (currency or "KRW").upper()
    usd_rub = float(usd_rub or rates.get("USD_RUB") or rates.get("RUB_USD") or 92.0)
    eur_usd = float(rates.get("EUR_USD") or 0.92)
    cny_usd = float(rates.get("CNY_USD") or 7.0)
    jpy_usd = float(rates.get("JPY_USD") or 157.0)
    krw_usd = float(krw_usd or rates.get("KRW_USD") or 1350.0)

    if currency == "USD":
        return price
    if currency == "KRW":
        return price / krw_usd
    if currency == "RUB":
        return price / usd_rub
    if currency == "EUR":
        return price / eur_usd
    if currency == "CNY":
        return price / cny_usd
    if currency == "JPY":
        return price / jpy_usd
    return price


def get_customs_duty_personal(cc, price_eur, age_code):
    if age_code == "0-3":
        if price_eur <= 8500:
            return max(price_eur * 0.54, cc * 2.5)
        if price_eur <= 16700:
            return max(price_eur * 0.48, cc * 3.5)
        if price_eur <= 42300:
            return max(price_eur * 0.48, cc * 5.5)
        if price_eur <= 84500:
            return max(price_eur * 0.48, cc * 7.5)
        if price_eur <= 169000:
            return max(price_eur * 0.48, cc * 15.0)
        return max(price_eur * 0.48, cc * 20.0)

    if age_code == "3-5":
        if cc <= 1000:
            return cc * 1.5
        if cc <= 1500:
            return cc * 1.7
        if cc <= 1800:
            return cc * 2.5
        if cc <= 2300:
            return cc * 2.7
        if cc <= 3000:
            return cc * 3.0
        return cc * 3.6

    if cc <= 1000:
        return cc * 3.0
    if cc <= 1500:
        return cc * 3.2
    if cc <= 1800:
        return cc * 3.5
    if cc <= 2300:
        return cc * 4.8
    if cc <= 3000:
        return cc * 5.0
    return cc * 5.7


def get_customs_duty_commercial_gasoline(cc, price_eur, age_code):
    if age_code == "0-3":
        rate = 0.15 if cc <= 2800 else 0.125
        return price_eur * rate
    if age_code in {"3-5", "5-7"}:
        if cc <= 1000:
            return max(price_eur * 0.20, cc * 0.36)
        if cc <= 1500:
            return max(price_eur * 0.20, cc * 0.40)
        if cc <= 1800:
            return max(price_eur * 0.20, cc * 0.36)
        if cc <= 3000:
            return max(price_eur * 0.20, cc * 0.44)
        return max(price_eur * 0.20, cc * 0.80)

    if cc <= 1000:
        return cc * 1.4
    if cc <= 1500:
        return cc * 1.5
    if cc <= 1800:
        return cc * 1.6
    if cc <= 3000:
        return cc * 2.2
    return cc * 3.2


def get_customs_duty_commercial_diesel(cc, price_eur, age_code):
    if age_code == "0-3":
        return price_eur * 0.15
    if age_code in {"3-5", "5-7"}:
        if cc <= 1500:
            return max(price_eur * 0.20, cc * 0.32)
        if cc <= 2500:
            return max(price_eur * 0.20, cc * 0.40)
        return max(price_eur * 0.20, cc * 0.80)

    if cc <= 1500:
        return cc * 1.5
    if cc <= 2500:
        return cc * 2.2
    return cc * 3.2


def get_customs_duty(owner, engine_type, cc, price_eur, age_code):
    if int(engine_type) in ELECTRIC_LIKE_ENGINES:
        return price_eur * 0.15
    if int(owner) == 1:
        return get_customs_duty_personal(cc, price_eur, age_code)
    if int(engine_type) == 2:
        return get_customs_duty_commercial_diesel(cc, price_eur, age_code)
    return get_customs_duty_commercial_gasoline(cc, price_eur, age_code)

def get_processing_fee(price_rub):
    if price_rub <= 200000: return 1231
    elif price_rub <= 450000: return 2462
    elif price_rub <= 1200000: return 4924
    elif price_rub <= 2700000: return 13541
    elif price_rub <= 4200000: return 18465
    elif price_rub <= 5500000: return 21344
    elif price_rub <= 10000000: return 49240
    else: return 73860

def get_excise(hp, owner, engine_type):
    if int(owner) != 2 and int(engine_type) not in ELECTRIC_LIKE_ENGINES:
        return 0
    if hp <= 90:
        return 0
    if hp <= 150:
        return 64 * hp
    if hp <= 200:
        return 613 * hp
    if hp <= 300:
        return 1004 * hp
    if hp <= 400:
        return 1711 * hp
    if hp <= 500:
        return 1771 * hp
    return 1829 * hp


def get_util_table(owner, engine_type, cc):
    owner = int(owner)
    engine_type = int(engine_type)
    cc = int(cc)

    if owner == 1 and engine_type in ELECTRIC_LIKE_ENGINES:
        return UTIL_TABLE_PERSONAL_EV
    if owner != 1 and engine_type in ELECTRIC_LIKE_ENGINES:
        return UTIL_TABLE_COMMERCIAL_EV

    if owner == 1 and cc <= 2000:
        return UTIL_TABLE_PERSONAL_1_2
    if owner == 1 and cc <= 3000:
        return UTIL_TABLE_PERSONAL_2_3
    if cc <= 2000:
        return UTIL_TABLE_COMMERCIAL_1_2
    if cc <= 3000:
        return UTIL_TABLE_COMMERCIAL_2_3
    if cc <= 3500:
        return UTIL_TABLE_COMMERCIAL_3_3_5
    return UTIL_TABLE_COMMERCIAL_3_5_PLUS


def get_util_fee(power_kw, age_code, owner, engine_type, cc, calc_year):
    table = get_util_table(owner, engine_type, cc)
    util_col = 1 if age_code == "0-3" else 2
    amount = table[-1][util_col]

    for upper_kw, amount_new, amount_old in table:
        if power_kw <= upper_kw:
            amount = amount_new if util_col == 1 else amount_old
            break

    factor = UTIL_YEAR_FACTORS.get(int(calc_year or 2026), 1.0)
    return round(amount * factor)


def normalize_calculation_input(data):
    normalized = dict(data)

    if "price_krw" in normalized and "price" not in normalized:
        legacy_type = int(normalized.get("type", 0))
        legacy_engine_map = {
            0: 1,  # benzine by default in legacy mode
            1: 6,  # old "hybrid" is closest to parallel hybrid
            2: 4,  # electric
        }
        normalized = {
            "owner": int(normalized.get("owner", 1)),
            "age": get_age_code(age=normalized.get("age")),
            "type": legacy_engine_map.get(legacy_type, 1),
            "power": float(normalized.get("hp", 0)),
            "power_unit": 1,
            "cc": int(normalized.get("cc", 0) or 0),
            "price": float(normalized.get("price_krw", 0)),
            "currency": "KRW",
            "calc_year": int(normalized.get("calc_year") or 2026),
            "krw_usd": float(normalized.get("krw_usd", 1350)),
            "usd_rub": float(normalized.get("usd_rub", 92)),
            "delivery_rub": float(normalized.get("delivery_rub", 0)),
            "broker_rub": float(normalized.get("broker_rub", 100000)),
            "ferry_krw": float(normalized.get("ferry_krw", 3500000)),
            "legacy_type": legacy_type,
        }
    else:
        normalized["owner"] = int(normalized.get("owner", 1))
        normalized["type"] = int(normalized.get("type", 1))
        normalized["power"] = float(normalized.get("power", 0))
        normalized["power_unit"] = int(normalized.get("power_unit", 1))
        normalized["cc"] = int(normalized.get("cc", 0) or 0)
        normalized["price"] = float(normalized.get("price", 0))
        normalized["currency"] = (normalized.get("currency") or "KRW").upper()
        normalized["calc_year"] = int(normalized.get("calc_year") or 2026)
        normalized["krw_usd"] = float(normalized.get("krw_usd", 1350))
        normalized["usd_rub"] = float(normalized.get("usd_rub", 92))
        normalized["delivery_rub"] = float(normalized.get("delivery_rub", 0))
        normalized["broker_rub"] = float(normalized.get("broker_rub", 100000))
        normalized["ferry_krw"] = float(normalized.get("ferry_krw", 3500000))
        normalized["age"] = get_age_code(age=normalized.get("age"))

    return normalized


def calculate(data, rates):
    data = normalize_calculation_input(data)
    owner = int(data["owner"])
    engine_type = int(data["type"])
    power = float(data["power"])
    power_unit = int(data["power_unit"])
    cc = int(data.get("cc", 0) or 0)
    calc_year = int(data.get("calc_year") or 2026)
    age_code = get_age_code(age=data.get("age"))
    currency = (data.get("currency") or "KRW").upper()
    price_value = float(data["price"])
    krw_usd = float(data.get("krw_usd") or rates.get("KRW_USD") or 1350.0)
    usd_rub = float(data.get("usd_rub") or rates.get("USD_RUB") or rates.get("RUB_USD") or 92.0)
    delivery_rub = float(data.get("delivery_rub") or 0)
    broker = float(data.get("broker_rub") or 100000)
    ferry_krw = float(data.get("ferry_krw") or 3500000)

    hp = get_power_hp(power, power_unit)
    kw = get_power_kw(power, power_unit)
    price_usd = get_price_usd(price_value, currency, rates, krw_usd=krw_usd, usd_rub=usd_rub)
    price_rub = price_usd * usd_rub
    price_eur = price_usd * float(rates["EUR_USD"])
    eur_rub = float(rates["EUR_RUB"])

    duty_eur = get_customs_duty(owner, engine_type, cc, price_eur, age_code)
    duty_rub = duty_eur * eur_rub
    proc_fee = get_processing_fee(price_rub)
    excise = get_excise(hp, owner, engine_type)
    util = get_util_fee(kw, age_code, owner, engine_type, cc, calc_year)

    if owner == 2 or engine_type in ELECTRIC_LIKE_ENGINES:
        vat_rate = 0.22
        vat = (price_rub + duty_rub + excise) * vat_rate
    else:
        vat_rate = 0.0
        vat = 0.0

    delivery_ship = (ferry_krw / krw_usd) * usd_rub
    customs_total = duty_rub + proc_fee + excise + util + vat
    calcus_total = price_rub + customs_total
    total = calcus_total + delivery_ship + delivery_rub + broker
    total_delta = total - calcus_total

    return {
        "owner": owner,
        "engine_type": engine_type,
        "currency": currency,
        "price": price_value,
        "price_usd": price_usd,
        "price_rub": price_rub,
        "price_eur": price_eur,
        "power": power,
        "power_unit": power_unit,
        "power_hp": hp,
        "power_kw": kw,
        "cc": cc,
        "calc_year": calc_year,
        "age_code": age_code,
        "duty_eur": duty_eur,
        "duty_rub": duty_rub,
        "proc": proc_fee,
        "excise": excise,
        "util": util,
        "vat_rate": vat_rate,
        "vat": vat,
        "customs_total": customs_total,
        "calcus_total": calcus_total,
        "delivery_ship": delivery_ship,
        "delivery_rus": delivery_rub,
        "broker": broker,
        "total": total,
        "total_delta": total_delta,
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
    ("age", "Возраст авто:\n1 — до 3 лет\n2 — от 3 до 5 лет\n3 — от 5 до 7 лет\n4 — от 7 лет"),
    ("type", "Тип двигателя:\n0 — Бензин/Дизель\n1 — Гибрид\n2 — Электро"),
    ("delivery_rub", "Доставка по России в ₽ (пример: 150000):"),
]

def normalize_public_url(url):
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def get_dashboard_url():
    return normalize_public_url(os.getenv("DASHBOARD_URL"))


def build_main_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🧮 Сделать расчёт", callback_data="calc_start"),
        types.InlineKeyboardButton("🔄 Restart", callback_data="calc_restart"),
    )
    markup.add(types.InlineKeyboardButton("💶 Курс EUR/RUB", callback_data="rate_eur_rub"))

    dashboard_url = get_dashboard_url()
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
        f"🚗 <b>Калькулятор авто из Кореи</b>\n"
        f"Старая форма ввода сохранена, но таможенная логика обновлена по <b>calcus.ru</b>.\n"
        f"Отдельно показывается таможня как у calcus и итог по старому сценарию с паромом, доставкой и брокером.\n\n"
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

        if field == "age" and value not in AGE_INPUT_MAP:
            bot.reply_to(m, "⚠️ Возраст: введите 1, 2, 3 или 4.\n\n" + prompt, parse_mode="HTML")
            return
        if field == "type" and value not in [0, 1, 2]:
            bot.reply_to(m, "⚠️ Тип: введите 0, 1 или 2.\n\n" + prompt, parse_mode="HTML")
            return
        if field in ["krw_usd", "usd_rub"] and value <= 0:
            bot.reply_to(m, "⚠️ Курс должен быть больше 0.\n\n" + prompt, parse_mode="HTML")
            return
        if field in ["price_krw", "cc", "hp"] and value <= 0:
            bot.reply_to(m, "⚠️ Значение должно быть больше 0.\n\n" + prompt, parse_mode="HTML")
            return
        if field == "delivery_rub" and value < 0:
            bot.reply_to(m, "⚠️ Доставка не может быть отрицательной.\n\n" + prompt, parse_mode="HTML")
            return

        user_data[cid][field] = value
        waiting[cid] = step + 1

        if waiting[cid] >= len(ШАГИ):
            try:
                rates = get_rates()
                result = calculate(user_data[cid], rates)
                data = user_data[cid]

                calc_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                    "result": result
                }
                calculations_history.append(calc_entry)
                if len(calculations_history) > 100:
                    del calculations_history[:-100]
                save_calculations(calculations_history)

                excise_str = f"  🚬 Акциз: {fmt(result['excise'])} ₽\n" if result["excise"] > 0 else ""
                vat_str = f"  💸 НДС {int(result['vat_rate'] * 100)}%: {fmt(result['vat'])} ₽\n" if result["vat"] > 0 else ""
                legacy_engine_names = {
                    0: "Бензин/Дизель",
                    1: "Гибрид",
                    2: "Электро",
                }

                response = (
                    f"🚗 <b>Расчёт авто из Кореи</b>\n\n"
                    f"📍 Цена: {fmt(data['price_krw'])} KRW → ${result['price_usd']:,.2f} → {fmt(result['price_rub'])} ₽\n"
                    f"💶 ≈ {fmt(result['price_eur'])} €\n\n"
                    f"⛽ {legacy_engine_names.get(int(data['type']), 'Бензин/Дизель')}\n"
                    f"📅 Возраст: {AGE_LABELS[result['age_code']]} | 🚗 {data['cc']} см³ | 🐎 {data['hp']} л.с.\n"
                    f"🔎 Внутри применена новая логика: {OWNER_LABELS[result['owner']]}, {ENGINE_LABELS[result['engine_type']]}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 <b>Таможня как calcus.ru:</b>\n"
                    f"  Пошлина ({fmt(result['duty_eur'])} €): {fmt(result['duty_rub'])} ₽\n"
                    f"  Оформление: {fmt(result['proc'])} ₽\n"
                    f"{excise_str}"
                    f"  ♻️ Утильсбор: {fmt(result['util'])} ₽\n"
                    f"{vat_str}"
                    f"  Итого таможня: {fmt(result['customs_total'])} ₽\n"
                    f"  <b>Полный итог как calcus: {fmt(result['calcus_total'])} ₽</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚢 Паром (3 500 000 KRW): +{fmt(result['delivery_ship'])} ₽\n"
                    f"🚛 Доставка по России: +{fmt(result['delivery_rus'])} ₽\n"
                    f"🔗 Брокер: +{fmt(result['broker'])} ₽\n"
                    f"📊 Разница с calcus: +{fmt(result['total_delta'])} ₽\n\n"
                    f"💰 <b>ИТОГ ПО СТАРОМУ БОТУ: {fmt(result['total'])} ₽</b>\n\n"
                    f"/reset — новый расчёт"
                )

                bot.reply_to(m, response, parse_mode="HTML")
                waiting[cid] = None
                user_data[cid] = {}
            except Exception:
                bot.reply_to(m, "⚠️ Ошибка расчёта. Проверьте введённые данные.\n\n/reset — новый расчёт", parse_mode="HTML")
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
                    <input type="number" step="0.01" id="calc-krw-usd" placeholder="1350" value="{{ rates.KRW_USD }}">

                    <label>Курс USD/RUB:</label>
                    <input type="number" step="0.01" id="calc-usd-rub" placeholder="92" value="{{ rates.USD_RUB }}">

                    <label>Объём двигателя (см³):</label>
                    <input type="number" id="calc-cc" placeholder="2000">

                    <label>Мощность (л.с.):</label>
                    <input type="number" id="calc-hp" placeholder="150">
                </div>
                <div>
                    <label>Возраст авто:</label>
                    <select id="calc-age">
                        <option value="1">до 3 лет</option>
                        <option value="2">от 3 до 5 лет</option>
                        <option value="3">от 5 до 7 лет</option>
                        <option value="4">от 7 лет</option>
                    </select>

                    <label>Тип двигателя:</label>
                    <select id="calc-type">
                        <option value="0">Бензин/Дизель</option>
                        <option value="1">Гибрид</option>
                        <option value="2">Электро</option>
                    </select>

                    <label>Доставка по России (₽):</label>
                    <input type="number" id="calc-delivery" placeholder="150000" value="150000">

                    <label>Брокер (₽):</label>
                    <input type="number" id="calc-broker" placeholder="100000" value="100000">

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
                const price = item.data.price ?? item.data.price_krw ?? 0;
                const currency = item.data.currency ?? 'KRW';
                return `
                    <div class="history-item">
                        <strong>${date.toLocaleString('ru-RU')}</strong><br>
                        Цена: ${Math.round(price).toLocaleString()} ${currency} → Итого: ${Math.round(item.result.total).toLocaleString()} ₽
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
                hp: parseFloat(document.getElementById('calc-hp').value) || 0,
                age: parseInt(document.getElementById('calc-age').value) || 1,
                type: parseInt(document.getElementById('calc-type').value),
                delivery_rub: parseFloat(document.getElementById('calc-delivery').value) || 0,
                broker_rub: parseFloat(document.getElementById('calc-broker').value) || 0
            };

            if (!data.price_krw || !data.hp) {
                alert('Введите цену и мощность');
                return;
            }
            
            const response = await fetch('/api/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            document.getElementById('calc-result').innerHTML = `
                <div class="result-box">
                    <div style="text-align: center; font-size: 1.2em; margin-bottom: 10px;">� Сравнение итогов</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 15px;">
                        <div style="background: rgba(255,255,255,0.15); border-radius: 12px; padding: 16px;">
                            <div style="text-align: center; font-size: 1.05em; margin-bottom: 8px;">Calcus</div>
                            <div class="result-value" style="font-size: 1.8em;">${Math.round(result.calcus_total).toLocaleString()} ₽</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.15); border-radius: 12px; padding: 16px;">
                            <div style="text-align: center; font-size: 1.05em; margin-bottom: 8px;">U nas</div>
                            <div class="result-value" style="font-size: 1.8em;">${Math.round(result.total).toLocaleString()} ₽</div>
                        </div>
                    </div>
                    <div style="margin-top: 15px; text-align: center;">
                        Цена: ${Math.round(data.price_krw).toLocaleString()} KRW → ${result.price_usd.toFixed(2)} USD → ${Math.round(result.price_rub).toLocaleString()} ₽
                    </div>
                    <div style="margin-top: 10px; text-align: center; font-size: 1.05em;">
                        Таможня как calcus: ${Math.round(result.customs_total).toLocaleString()} ₽
                    </div>
                    <div style="margin-top: 8px; text-align: center; font-size: 1.05em;">
                        Разница: +${Math.round(result.total_delta).toLocaleString()} ₽
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
        last_update=_last_update.strftime('%Y-%m-%d %H:%M:%S') if _last_update else 'Нет данных',
        current_year=datetime.now().year
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
