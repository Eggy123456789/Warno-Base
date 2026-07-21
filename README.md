# WARNO Infantry Analysis (Updated to Nemesis 7 Patch, v193438)

A Python tool that analyzes WARNO infantry (for now) units and ranks them based on combat effectiveness and value.

## Overview

WARNO contains hundreds of infantry units with varying squad sizes, weapons, and special traits. This project parses WARNO's unit and weapon data and generates rankings based on:

- Damage output
- Suppression output
- Survivability
- Cost efficiency

The goal is to create a consistent and reasonably accurate comparison of infantry units under standardized combat conditions.

Currently, this project focuses only on infantry and their anti-infantry effectiveness, though I plan to expand it to additional unit types in the future.

---

# Features

## Infantry Categories

The script generates rankings for three categories.

### All Infantry

Includes every infantry-class unit, including:

- Infantry squads
- Mortar teams
- MANPADS
- ATGM teams
- Gun crews
- Command infantry

### Actual Infantry

Attempts to isolate combat infantry.

Requirements:

- Squad size of at least 4
- Excludes command infantry (`hq_inf`)

### Infantry with AT

Actual infantry squads that also possess an anti-tank weapon.

---

# Combat Score

Combat Score is a weighted combination of:

- Effective DPS
- Suppression output
- Survivability

Current formula:

```text
CombatScore =
(EffectiveDPS × 0.45)
+ (NormalizedSuppression × 0.20)
+ (NormalizedHP × 0.35)
```

Where:

```text
NormalizedSuppression = SquadSuppression / 141.65
NormalizedHP = HP / 16
```

(141.65 and 16 are the highest values observed in the infantry dataset.)

---

# Effective DPS

Effective DPS is evaluated at a standardized engagement distance of **500 meters**. I'll probably add 850 meters later.

Each weapon contributes:

```text
EffectiveDPS =
(NumberOfWeapons × HEDamage × TrueRateOfFire / 60)
× Accuracy
```

Unlike previous versions, no range multiplier is applied.

Weapons only contribute if:

- 500m lies between their minimum and maximum ground range
- They are not designated close-assault weapons

---

# Accuracy Calculation

Accuracy is evaluated using each weapon's **ground static accuracy**.

If a weapon provides a `staticAccuracyOverDistance` table:

- If 500m exactly exists, that value is used.
- Otherwise, the two nearest distances are averaged.

After all veterancy and specialty bonuses are applied:

- Accuracy is capped between **0% and 100%**.

No additional bonuses are awarded above 100%.

---

# Shock Combat Score

Shock Combat Score estimates performance during close-range engagements.

It is calculated using the same Combat Score formula, except weapon performance is evaluated at **150 meters**.

- Shock infantry (`_choc`) receive their bonuses:
  - +15% HE damage
  - Approximately +17.6% rate of fire (derived from 15% faster reload and firing animations)

The exported CSV includes:

- ShockCombatScore
- ShockValueScore
- ShockRank
- ShockValueRank

---

# Veterancy and Special Traits

The script currently models the following known modifiers.

## Reservists

- -5 Accuracy

## Militia

- Approximately 16.7% lower rate of fire

## Special Forces

Assumed to receive:

- +12 Accuracy
- +20% Rate of Fire

This approximates two veterancy levels.

## Shock Infantry

Units possessing the `_choc` specialty receive bonuses when calculating Shock Combat Score only.

---

# Value Score

```text
ValueScore =
(CombatScore / CommandPoints) × 100
```

(Command Points are the deployment cost of the unit, excluding transports.)

Multiplying by 100 simply makes the values easier to read.

Shock Value Score is calculated identically using Shock Combat Score.

---

# Output

The script exports:

- `all_infantry.csv`
- `actual_infantry.csv`
- `infantry_with_at.csv`

Each CSV includes:

- CombatRank
- ValueRank
- ShockRank
- ShockValueRank
- Unit
- Cost
- HP
- NormalizedHP
- EffectiveDPS
- Suppression
- NormalizedSuppression
- ShockDPS
- ShockSuppression
- ShockNormalizedSuppression
- ATScore
- CombatScore
- ValueScore
- ShockCombatScore
- ShockValueScore

---

# Limitations

This project does not currently model:

- Base veterancy of most units
- Morale mechanics
- Suppression recovery
- Availability
- Transport options
- Terrain
- Cover
- Ammunition limits

As a result, the rankings should be interpreted as comparative indicators rather than exact predictions of in-game performance.
