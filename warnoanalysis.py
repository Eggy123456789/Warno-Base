import json
import csv
from statistics import mean
from pathlib import Path
import os
# ==========================================================
# TO DO:
# Adjust suppression, sometimes it can be overwhelming DONE?
# Prob filter different range brackets (remember shock trait)
# Do smth about AT score
# moving score, i.e. "stabilizer"
# LIMITATION: cant account for base veterancy for non SF "shock" units i.e. AERO-RIFLES
# ==========================================================
print("Current working directory:")
print(os.getcwd())

# ==========================================================
# FILE PATHS/CONSTANTS
# ==========================================================

BASE_DIR = Path(__file__).parent

WEAPONS_FILE = BASE_DIR / "weapons.json"
UNITS_FILE = BASE_DIR / "units.json"

# ==========================================================
# LOAD DATA
# ==========================================================

with open(WEAPONS_FILE, "r", encoding="utf-8") as f:
    weapon_data = json.load(f)

with open(UNITS_FILE, "r", encoding="utf-8") as f:
    unit_data = json.load(f)

if "weapons" in weapon_data:
    weapon_data = weapon_data["weapons"]

# ==========================================================
# BUILD INFANTRY LOOKUP
# ==========================================================

cost_lookup = {}

for unit in unit_data:

    if unit.get("infoPanelType") != "infantry":
        continue

    # Exclude units not currently available in any division
    if not unit.get("divisions"):
        continue

    wd = unit.get("weaponDescriptorName")

    if not wd:
        continue

    wd = wd.split("/")[-1]

    cost_lookup[wd] = {
        "name": unit.get("name", wd),
        "cost": unit.get("commandPoints", 0),
        "hp": unit.get("maxDamage", 10),
        "divisions": unit.get("divisions", []),
        "specialities": unit.get("specialities", [])
    }

print(f"Found {len(cost_lookup)} infantry entries")

# ==========================================================
# HELPERS
# ==========================================================

def average_accuracy(ammo):

    try:
        ground = ammo["staticAccuracyOverDistance"]["ground"]

        if len(ground) == 0:
            return ammo.get("staticAccuracy", 0) / 100

        return mean(x["accuracy"] for x in ground) / 100

    except:
        return ammo.get("staticAccuracy", 0) / 100

def range_factor(ammo):

    STANDARD_RANGE = 850
    LEVEL_OFF_RANGE = 400

    weapon_range = ammo.get("groundMaxRange", 0)

    if weapon_range <= 0:
        return 0

    # Full effectiveness for long-range infantry weapons
    if weapon_range >= STANDARD_RANGE:
        return 1.0

    # Sharper penalty below 400m
    if weapon_range <= LEVEL_OFF_RANGE:

        factor = 0.65 + 0.25 * (
            weapon_range / LEVEL_OFF_RANGE
        )

    # Above 400m, penalty mostly levels off
    else:

        factor = 0.90 + 0.10 * (
            (weapon_range - LEVEL_OFF_RANGE)
            / (STANDARD_RANGE - LEVEL_OFF_RANGE)
        )

    # Protect close-assault weapons
    ammo_name = ammo.get("name", "").lower()

    assault_keywords = [
        "satchel",
        "rpo",
        "flame",
        "flam",
        "lpo"
    ]

    if any(word in ammo_name for word in assault_keywords):
        factor = max(factor, 0.90)

    return factor

def get_unit_modifiers(unit_name, specialities):

    accuracy_bonus = 0
    rof_multiplier = 1.0

    # Reservists: -5 accuracy
    if "_reservist" in specialities:
        accuracy_bonus -= 5

    # Militia: normal units fire 20% faster than militia, so militia has 1 / 1.20 of normal ROF. i think?
    if "_militia" in specialities:
        rof_multiplier *= 1 / 1.20

    # Most special forces: +12 accuracy, +20% ROF. im not going to implement the 3 vet guys bc lazy
    if "_sf" in specialities:
        accuracy_bonus += 12
        rof_multiplier *= 1.20

    # Rangers exception: +8 accuracy, +10% ROF
    if "ranger" in unit_name.lower():
        accuracy_bonus = 8
        rof_multiplier = 1.10

    return accuracy_bonus, rof_multiplier

def weapon_stats(weapon, accuracy_bonus=0, rof_multiplier=1.0):

    ammo = weapon["ammo"]

    count = weapon.get("numberOfWeapons", 1)

    he = ammo.get("heDamage", 0)

    rof = ammo.get("trueRateOfFire", 0) * rof_multiplier

    suppress = ammo.get("suppress", 0)

    accuracy = average_accuracy(ammo)
    accuracy = max(0, accuracy + accuracy_bonus / 100)

    penetration = ammo.get("penetration", 0)

    effective_dps = (
        count
        * he
        * rof
        / 60
        * accuracy
        * range_factor(ammo)
    )

    suppression = (
        count
        * suppress
        * rof
        / 60
    )

    at_score = (
        count
        * penetration
        * rof
        / 60
        * accuracy
    )

    return {
        "effective_dps": effective_dps,
        "suppression": suppression,
        "at_score": at_score,
        "count": count
    }

# ==========================================================
# RESULT LISTS
# ==========================================================

all_infantry = []
actual_infantry = []
infantry_with_at = []

# ==========================================================
# MAIN ANALYSIS
# ==========================================================

for descriptor_name, squad in weapon_data.items():

    if descriptor_name not in cost_lookup:
        continue

    squad_dps = 0
    squad_suppression = 0
    squad_at_score = 0
    squad_size = 0

    small_arms_count = 0
    has_at_weapon = False

    unit_name = cost_lookup[descriptor_name]["name"]
    specialities = cost_lookup[descriptor_name]["specialities"]

    accuracy_bonus, rof_multiplier = get_unit_modifiers(
        unit_name,
        specialities
    )

    for weapon in squad.get("weapons", []):

        ammo = weapon["ammo"]

        stats = weapon_stats(
            weapon,
            accuracy_bonus,
            rof_multiplier
        )

        squad_size += stats["count"]

        penetration = ammo.get("penetration", 0)

        # AT weapon detection
        ammo_name = ammo.get("name", "").lower()

        excluded_at_keywords = [
            "satchel",
            "rpo",
            "flame",
            "flam"
        ]

        is_special_assault_weapon = any(
            word in ammo_name
            for word in excluded_at_keywords
        )

        is_at_weapon = (
            penetration > 2
            and not is_special_assault_weapon
        )

        if is_at_weapon:
            has_at_weapon = True
            squad_at_score += stats["at_score"]
        else:
            squad_dps += stats["effective_dps"]
            squad_suppression += stats["suppression"]

        # Small arms detection
        if (
            penetration == 0
            and ammo.get("trueRateOfFire", 0) > 15
        ):
            small_arms_count += stats["count"]

    cost = cost_lookup[descriptor_name]["cost"]
    hp = cost_lookup[descriptor_name]["hp"]

    
    normalized_suppression = squad_suppression / 118.2 #118.2 is the max suppression value found
    normalized_hp = hp / 16 #max HP value found

    combat_score = (
        squad_dps * 0.45
        + normalized_suppression * 0.20
        + normalized_hp * 0.35
    )

    value_score = (
        combat_score / cost
        if cost > 0
        else 0
    )

    row = {
        "Unit": cost_lookup[descriptor_name]["name"],
        "Cost": cost,
        #"SquadSize": squad_size, NOT CORRECT
        "SmallArms": small_arms_count,
        "HP": hp,
        "NormalizedHP": round(normalized_hp, 4),
        "EffectiveDPS": round(squad_dps, 3),

        "Suppression": round(squad_suppression, 2),
        "NormalizedSuppression": round(normalized_suppression, 4),

        "ATScore": round(squad_at_score, 2),

        "CombatScore": round(combat_score, 4),
        "ValueScore": round(value_score, 4)
    }
    
    # ------------------------------------------------------
    # ALL INFANTRY
    # ------------------------------------------------------

    all_infantry.append(row)

    # ------------------------------------------------------
    # ACTUAL INFANTRY
    # ------------------------------------------------------

    is_actual_infantry = (
        squad_size >= 4
        and small_arms_count >= 4
    )

    if is_actual_infantry:
        actual_infantry.append(row)

    # ------------------------------------------------------
    # ACTUAL INFANTRY WITH AT
    # ------------------------------------------------------

    if is_actual_infantry and has_at_weapon:
        infantry_with_at.append(row)

print("\n===== DATASET RANGES =====")

print(
    "Max DPS:",
    max(row["EffectiveDPS"] for row in actual_infantry)
)

print(
    "Max Suppression:",
    max(row["Suppression"] for row in actual_infantry)
)

print(
    "Max HP:",
    max(row["HP"] for row in actual_infantry)
)

print(
    "Average DPS:",
    sum(row["EffectiveDPS"] for row in actual_infantry)
    / len(actual_infantry)
)

print(
    "Average Suppression:",
    sum(row["Suppression"] for row in actual_infantry)
    / len(actual_infantry)
)

print(
    "Average HP:",
    sum(row["HP"] for row in actual_infantry)
    / len(actual_infantry)
)


# ==========================================================
# PRINT TOP 20
# ==========================================================

def print_rankings(title, data):

    print(f"\n{'=' * 70}")
    print(title)
    print('=' * 70)

    print("\nTOP 20 BY COMBAT SCORE\n")

    by_combat = sorted(
        data,
        key=lambda x: x["CombatScore"],
        reverse=True
    )

    for row in by_combat[:20]:
        print(
            f"{row['Unit'][:35]:35} "
            f"Cost={row['Cost']:3} "
            f"Combat={row['CombatScore']:8.2f} "
            f"Value={row['ValueScore']:.4f}"
        )

    print("\nTOP 20 BY VALUE SCORE\n")

    by_value = sorted(
        data,
        key=lambda x: x["ValueScore"],
        reverse=True
    )

    for row in by_value[:20]:
        print(
            f"{row['Unit'][:35]:35} "
            f"Cost={row['Cost']:3} "
            f"Combat={row['CombatScore']:8.2f} "
            f"Value={row['ValueScore']:.4f}"
        )


print_rankings("ALL INFANTRY", all_infantry)
print_rankings("ACTUAL INFANTRY", actual_infantry)
print_rankings("INFANTRY WITH AT", infantry_with_at)

# ==========================================================
# EXPORT CSVS
# ==========================================================

OUTPUT_FOLDER = r"C:\Users\xpbai\Downloads"

def export_csv(filename, data):

    if len(data) == 0:
        print(f"No data for {filename}")
        return

    combat_sorted = sorted(
        data,
        key=lambda x: x["CombatScore"],
        reverse=True
    )

    value_sorted = sorted(
        data,
        key=lambda x: x["ValueScore"],
        reverse=True
    )

    combat_ranks = {
        row["Unit"]: i + 1
        for i, row in enumerate(combat_sorted)
    }

    value_ranks = {
        row["Unit"]: i + 1
        for i, row in enumerate(value_sorted)
    }

    export_data = []

    for row in combat_sorted:

        new_row = row.copy()

        new_row["CombatRank"] = combat_ranks[row["Unit"]]
        new_row["ValueRank"] = value_ranks[row["Unit"]]

        export_data.append(new_row)

    fieldnames = (
        ["CombatRank", "ValueRank"]
        + [
            k for k in export_data[0].keys()
            if k not in ["CombatRank", "ValueRank"]
        ]
    )

    output_path = OUTPUT_FOLDER + "\\" + filename

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(export_data)

    print(f"Saved {output_path}")


export_csv("all_infantry.csv", all_infantry)
export_csv("actual_infantry.csv", actual_infantry)
export_csv("infantry_with_at.csv", infantry_with_at)

print("\nCSV files exported successfully.")