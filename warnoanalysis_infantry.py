import json
import csv
from statistics import mean
from pathlib import Path
import os

# ==========================================================
# FILE PATHS / CONSTANTS
# ==========================================================

print("Current working directory:")
print(os.getcwd())

BASE_DIR = Path(__file__).parent

WEAPONS_FILE = BASE_DIR / "weapons.json"
UNITS_FILE = BASE_DIR / "units.json"
OUTPUT_FOLDER = BASE_DIR

NORMAL_RANGE = 500
SHOCK_RANGE = 150

SUPPRESSION_MAX = 141.65
HP_MAX = 16

DPS_WEIGHT = 0.45
SUPPRESSION_WEIGHT = 0.20
HP_WEIGHT = 0.35

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

    # Exclude removed/upcoming units with no division availability
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
# HELPER FUNCTIONS
# ==========================================================

def can_fire_at_range(ammo, target_range):
    weapon_min = ammo.get("groundMinRange", 0)
    weapon_max = ammo.get("groundMaxRange", 0)

    return weapon_min <= target_range <= weapon_max


def accuracy_at_range(ammo, target_range, accuracy_bonus=0):
    """
    Uses static ground accuracy.

    If the weapon has a ground accuracy table:
    - exact target range match = use that value
    - otherwise average the two closest distance points

    If no table exists:
    - use staticAccuracy

    Accuracy is capped between 0% and 100%.
    """

    accuracy_table = ammo.get(
        "staticAccuracyOverDistance",
        {}
    ).get("ground")

    if not accuracy_table:
        accuracy = ammo.get("staticAccuracy", 0)
    else:
        exact_match = [
            x["accuracy"]
            for x in accuracy_table
            if x["distance"] == target_range
        ]

        if exact_match:
            accuracy = exact_match[0]
        else:
            closest = sorted(
                accuracy_table,
                key=lambda x: abs(x["distance"] - target_range)
            )[:2]

            accuracy = mean(x["accuracy"] for x in closest)

    accuracy += accuracy_bonus
    accuracy = max(0, min(100, accuracy))

    return accuracy / 100


def is_close_assault_weapon(ammo):
    """
    Weapons excluded from normal 500m DPS, but included in shock/close-range DPS.
    """

    ammo_name = ammo.get("name", "").lower()
    descriptor = ammo.get("descriptorName", "").lower()
    minmax = ammo.get("minMaxCategory", "").lower()

    close_keywords = [
        "this should not be used"
    ]

    return (
        any(word in ammo_name for word in close_keywords)
        or any(word in descriptor for word in close_keywords)
        or "shotgun" in minmax
    )


def is_special_assault_weapon(ammo):
    """
    Weapons that may have HEAT/penetration values but should not be classified
    as real AT weapons.
    """

    ammo_name = ammo.get("name", "").lower()
    descriptor = ammo.get("descriptorName", "").lower()

    excluded_at_keywords = [
        "satchel",
        "rpo",
        "flame",
        "flam",
        "lpo"
    ]

    return (
        any(word in ammo_name for word in excluded_at_keywords)
        or any(word in descriptor for word in excluded_at_keywords)
    )


def is_at_weapon(ammo):
    penetration = ammo.get("penetration", 0)

    return (
        penetration > 2
        and not is_special_assault_weapon(ammo)
    )


def get_unit_modifiers(unit_name, specialities):
    """
    Applies known unit-wide modifiers.

    Reservist:
    -5 accuracy

    Militia:
    normal units have 20% more ROF than militia,
    so militia is modeled as 1/1.20 ROF.

    Special Forces:
    assumed 2-vet
    +12 accuracy
    +20% ROF

    Rangers:
    treated as 1-vet
    +8 accuracy
    +10% ROF
    """

    accuracy_bonus = 0
    rof_multiplier = 1.0

    if "_reservist" in specialities:
        accuracy_bonus -= 5

    if "_militia" in specialities:
        rof_multiplier *= 1 / 1.20

    if "_sf" in specialities:
        accuracy_bonus += 12
        rof_multiplier *= 1.20

    if "ranger" in unit_name.lower():
        accuracy_bonus = 8
        rof_multiplier = 1.10

    return accuracy_bonus, rof_multiplier


def weapon_stats(
    weapon,
    target_range,
    accuracy_bonus=0,
    rof_multiplier=1.0,
    include_close_assault=False,
    apply_shock=False
):
    ammo = weapon["ammo"]

    count = weapon.get("numberOfWeapons", 1)

    if not can_fire_at_range(ammo, target_range):
        return {
            "effective_dps": 0,
            "suppression": 0,
            "at_score": 0,
            "count": count
        }

    if is_close_assault_weapon(ammo) and not include_close_assault:
        return {
            "effective_dps": 0,
            "suppression": 0,
            "at_score": 0,
            "count": count
        }

    he = ammo.get("heDamage", 0)
    rof = ammo.get("trueRateOfFire", 0) * rof_multiplier
    suppress = ammo.get("suppress", 0)
    penetration = ammo.get("penetration", 0)

    if apply_shock:
        he *= 1.15
        rof *= 1 / 0.85

    accuracy = accuracy_at_range(
        ammo,
        target_range,
        accuracy_bonus
    )

    effective_dps = (
        count
        * he
        * rof
        / 60
        * accuracy
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


def calculate_combat_score(dps, normalized_suppression, normalized_hp):
    return (
        dps * DPS_WEIGHT
        + normalized_suppression * SUPPRESSION_WEIGHT
        + normalized_hp * HP_WEIGHT
    )


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

    unit_name = cost_lookup[descriptor_name]["name"]
    cost = cost_lookup[descriptor_name]["cost"]
    hp = cost_lookup[descriptor_name]["hp"]
    specialities = cost_lookup[descriptor_name]["specialities"]

    is_shock = "_choc" in specialities

    is_hq_infantry = (
        "hq_inf" in specialities
        or "_hq_inf" in specialities
    )

    accuracy_bonus, rof_multiplier = get_unit_modifiers(
        unit_name,
        specialities
    )

    squad_dps = 0
    squad_suppression = 0

    shock_dps = 0
    shock_suppression = 0

    squad_at_score = 0
    squad_size = 0
    small_arms_count = 0
    has_at_weapon = False

    for weapon in squad.get("weapons", []):

        ammo = weapon["ammo"]

        normal_stats = weapon_stats(
            weapon,
            target_range=NORMAL_RANGE,
            accuracy_bonus=accuracy_bonus,
            rof_multiplier=rof_multiplier,
            include_close_assault=False,
            apply_shock=False
        )

        shock_stats = weapon_stats(
            weapon,
            target_range=SHOCK_RANGE,
            accuracy_bonus=accuracy_bonus,
            rof_multiplier=rof_multiplier,
            include_close_assault=True,
            apply_shock=is_shock
        )

        squad_size += normal_stats["count"]

        if is_at_weapon(ammo):
            has_at_weapon = True
            squad_at_score += normal_stats["at_score"]
        else:
            squad_dps += normal_stats["effective_dps"]
            squad_suppression += normal_stats["suppression"]

            shock_dps += shock_stats["effective_dps"]
            shock_suppression += shock_stats["suppression"]

        # Used only for rough filtering of "real" infantry
        if (
            not is_at_weapon(ammo)
            and ammo.get("trueRateOfFire", 0) > 15
            and not is_close_assault_weapon(ammo)
        ):
            small_arms_count += normal_stats["count"]

    normalized_suppression = squad_suppression / SUPPRESSION_MAX
    shock_normalized_suppression = shock_suppression / SUPPRESSION_MAX
    normalized_hp = hp / HP_MAX

    combat_score = calculate_combat_score(
        squad_dps,
        normalized_suppression,
        normalized_hp
    )

    shock_combat_score = calculate_combat_score(
        shock_dps,
        shock_normalized_suppression,
        normalized_hp
    )

    value_score = (
        (combat_score / cost) * 100
        if cost > 0
        else 0
    )

    shock_value_score = (
        (shock_combat_score / cost) * 100
        if cost > 0
        else 0
    )

    row = {
        "Unit": unit_name,
        "Cost": cost,
        "SmallArms": small_arms_count,
        "HP": hp,
        "NormalizedHP": round(normalized_hp, 4),

        "EffectiveDPS": round(squad_dps, 3),
        "Suppression": round(squad_suppression, 2),
        "NormalizedSuppression": round(normalized_suppression, 4),

        "ShockDPS": round(shock_dps, 3),
        "ShockSuppression": round(shock_suppression, 2),
        "ShockNormalizedSuppression": round(
            shock_normalized_suppression,
            4
        ),

        "ATScore": round(squad_at_score, 2),

        "CombatScore": round(combat_score, 4),
        "ValueScore": round(value_score, 4),

        "IsShock": is_shock,
        "ShockCombatScore": round(shock_combat_score, 4),
        "ShockValueScore": round(shock_value_score, 4)
    }

    all_infantry.append(row)

    is_actual_infantry = (
        squad_size >= 4
    )

    if is_actual_infantry and not is_hq_infantry:
        actual_infantry.append(row)

    if is_actual_infantry and has_at_weapon and not is_hq_infantry:
        infantry_with_at.append(row)

# ==========================================================
# DATASET RANGES
# ==========================================================

print("\n===== DATASET RANGES =====")

if actual_infantry:
    print("Max DPS:", max(row["EffectiveDPS"] for row in actual_infantry))
    print("Max Suppression:", max(row["Suppression"] for row in actual_infantry))
    print("Max Shock DPS:", max(row["ShockDPS"] for row in actual_infantry))
    print("Max Shock Suppression:", max(row["ShockSuppression"] for row in actual_infantry))
    print("Max HP:", max(row["HP"] for row in actual_infantry))

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
    print("=" * 70)

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
            f"Combat={row['CombatScore']:8.4f} "
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
            f"Combat={row['CombatScore']:8.4f} "
            f"Value={row['ValueScore']:.4f}"
        )

    print("\nTOP 20 BY SHOCK COMBAT SCORE\n")

    by_shock = sorted(
        data,
        key=lambda x: x["ShockCombatScore"],
        reverse=True
    )

    for row in by_shock[:20]:
        print(
            f"{row['Unit'][:35]:35} "
            f"Cost={row['Cost']:3} "
            f"Shock={row['ShockCombatScore']:8.4f} "
            f"ShockValue={row['ShockValueScore']:.4f}"
        )


print_rankings("ALL INFANTRY", all_infantry)
print_rankings("ACTUAL INFANTRY", actual_infantry)
print_rankings("INFANTRY WITH AT", infantry_with_at)

# ==========================================================
# EXPORT CSVS
# ==========================================================

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

    shock_sorted = sorted(
        data,
        key=lambda x: x["ShockCombatScore"],
        reverse=True
    )

    shock_value_sorted = sorted(
        data,
        key=lambda x: x["ShockValueScore"],
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

    shock_ranks = {
        row["Unit"]: i + 1
        for i, row in enumerate(shock_sorted)
    }

    shock_value_ranks = {
        row["Unit"]: i + 1
        for i, row in enumerate(shock_value_sorted)
    }

    export_data = []

    for row in combat_sorted:

        new_row = row.copy()

        new_row["CombatRank"] = combat_ranks[row["Unit"]]
        new_row["ValueRank"] = value_ranks[row["Unit"]]
        new_row["ShockRank"] = shock_ranks[row["Unit"]]
        new_row["ShockValueRank"] = shock_value_ranks[row["Unit"]]

        export_data.append(new_row)

    fieldnames = (
        [
            "CombatRank",
            "ValueRank",
            "ShockRank",
            "ShockValueRank"
        ]
        + [
            k for k in export_data[0].keys()
            if k not in [
                "CombatRank",
                "ValueRank",
                "ShockRank",
                "ShockValueRank"
            ]
        ]
    )

    output_path = OUTPUT_FOLDER / filename

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