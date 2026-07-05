
# -*- coding: utf-8 -*-
# Простой тест расчетов

POWER_KW_PER_HP = 1 / 1.3596
UTIL_YEAR_FACTORS = {2025: 1 / 1.2, 2026: 1.0, 2027: 1.1, 2028: 1.21, 2029: 1.331, 2030: 1.4641}

UTIL_TABLE_PERSONAL_1_2 = [
    (51.48, 800800, 1408800),
    (73.55, 800800, 1408800),
    (95.61, 800800, 1408800),
    (117.68, 800800, 1408800),
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

def get_power_kw(power, power_unit):
    power = float(power)
    if int(power_unit) == 2:
        return power
    return power * POWER_KW_PER_HP

def get_util_fee(power_kw, age_code, table, calc_year):
    util_col = 1 if age_code == "0-3" else 2
    amount = table[-1][util_col]
    for upper_kw, amount_new, amount_old in table:
        if power_kw <= upper_kw:
            amount = amount_new if util_col == 1 else amount_old
            break
    factor = UTIL_YEAR_FACTORS.get(int(calc_year), 1.0)
    return round(amount * factor)

print("=== Тест расчета утильсбора ===")
print()

test_cases = [
    # (мощность в л.с., возраст код, год)
    (100, "0-3", 2026),
    (150, "0-3", 2026),
    (200, "0-3", 2026),
    (100, "3-5", 2026),
]

for hp, age_code, calc_year in test_cases:
    kw = get_power_kw(hp, 1)
    util = get_util_fee(kw, age_code, UTIL_TABLE_PERSONAL_1_2, calc_year)
    print(f"Мощность: {hp} л.с. = {kw:.2f} кВт")
    print(f"Возраст: {age_code}")
    print(f"Год: {calc_year}")
    print(f"Утильсбор: {util} ₽")
    print()
