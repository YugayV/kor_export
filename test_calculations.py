
# -*- coding: utf-8 -*-
import os
import sys

# Импортируем функции из bot.py
sys.path.insert(0, os.path.dirname(__file__))
from bot import (
    get_power_hp,
    get_power_kw,
    get_util_fee,
    get_util_table,
    POWER_KW_PER_HP,
    AGE_INPUT_MAP,
    AGE_LABELS,
    UTIL_YEAR_FACTORS,
    UTIL_TABLE_PERSONAL_EV,
    UTIL_TABLE_PERSONAL_1_2,
    UTIL_TABLE_PERSONAL_2_3,
    UTIL_TABLE_COMMERCIAL_EV,
    UTIL_TABLE_COMMERCIAL_1_2,
    UTIL_TABLE_COMMERCIAL_2_3,
    UTIL_TABLE_COMMERCIAL_3_3_5,
    UTIL_TABLE_COMMERCIAL_3_5_PLUS
)

print("=== Тест расчетов ===")
print()

# Тестовый пример
test_data = [
    # (мощность, единица мощности, владелец, тип двигателя, объем, возраст, год расчета)
    (150, 1, 1, 1, 2000, 1, 2026),  # Физ.лицо, бензин, 2000 см³, до 3 лет
    (200, 1, 1, 1, 3000, 2, 2026),  # Физ.лицо, бензин, 3000 см³, 3-5 лет
    (250, 1, 2, 1, 2000, 1, 2026),  # Юр.лицо, бензин, 2000 см³, до 3 лет
    (100, 1, 1, 4, 0, 1, 2026),     # Физ.лицо, электромобиль
]

for power, power_unit, owner, engine_type, cc, age, calc_year in test_data:
    hp = get_power_hp(power, power_unit)
    kw = get_power_kw(power, power_unit)
    age_code = AGE_INPUT_MAP[age]
    util = get_util_fee(kw, age_code, owner, engine_type, cc, calc_year)
    table = get_util_table(owner, engine_type, cc)
    
    print(f"Тест: мощность={power} {'л.с.' if power_unit == 1 else 'кВт'}, владелец={owner}, двигатель={engine_type}, объем={cc}, возраст={age_code}, год={calc_year}")
    print(f"  Мощность в л.с.: {hp:.2f}")
    print(f"  Мощность в кВт: {kw:.2f}")
    print(f"  Таблица утильсбора: {table}")
    print(f"  Утильсбор: {util} ₽")
    print()
