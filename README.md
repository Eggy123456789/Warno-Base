# WARNO Infantry Analysis

A Python tool that analyzes WARNO infantry (for now) units and ranks them based on combat effectiveness and value.

## Overview

WARNO contains hundreds of infantry units with varying squad sizes, weapons, and special traits. This project parses WARNO's unit and weapon data and generates rankings based on:

- Damage output
- Suppression output
- Survivability
- Cost efficiency

We will not perfectly simulate every unique in-game interaction, but this project does aim to provide a generalist ranking that will mostly hold up.

Currently, this project only focuses on infantry units and their anti-infantry effectiveness, but I do plan to expand this into other unit types/purposes.

---

## Features

### Infantry Categories

The script generates rankings for three categories:

#### All Infantry

Includes all infantry-class units, including:

- Infantry squads
- Some mortar teams (I think?)
- MANPADS
- ATGM teams
- Gun crews

#### Actual Infantry

Attempts to isolate true infantry squads.

Requirements:

- Squad size of at least 4. There is probably a better way to do this, but I'm too lazy.

#### Infantry with AT

Actual infantry squads that also possess an anti-tank weapon.

---

## Combat Score

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
NormalizedSuppression = SquadSuppression / 118.2
NormalizedHP = HP / 16
```

(118.2 and 16 are the highest values observed in the infantry dataset.)

---

## Effective DPS

Effective DPS is calculated per weapon:

```text
EffectiveDPS =
(NumberOfWeapons × HEDamage × TrueRateOfFire / 60)
× Accuracy
× RangeFactor
```

---

## Range Adjustment

Short-range weapons receive a range penalty.

850m is treated as the standard infantry engagement range.

The penalty increases below roughly 400m and then levels off.

| Range | Factor |
|--------|---------|
| 850m | 1.00 |
| 700m | ~0.97 |
| 500m | ~0.92 |
| 400m | ~0.90 |
| 300m | ~0.84 |
| 150m | ~0.74 |

Special close-assault weapons such as satchel charges, flamethrowers, and RPO launchers are protected from excessive penalties. I'm not sure if this is a good idea or not.

---

## Veterancy and Special Traits

The script currently models:

### Reservists

-5 Accuracy

### Militia

Approximately 16.7% lower rate of fire

### Special Forces

Assumed to receive:

- +12 Accuracy
- +20% Rate of Fire

This approximates the effects of 2-veterancy special forces.

### Rangers

Treated separately:

- +8 Accuracy
- +10% Rate of Fire

This approximates 1-veterancy units.

---

## Value Score

```text
ValueScore =
CombatScore / CommandPoints
```

(Command Points are how much it costs to deploy a unit, excluding transports.)

This measures combat effectiveness per point spent.

---

## Output

The script exports:

- `all_infantry.csv`
- `actual_infantry.csv`
- `infantry_with_at.csv`

Each CSV includes:

- CombatRank
- ValueRank
- Unit Name
- Cost
- HP
- EffectiveDPS
- Suppression
- CombatScore
- ValueScore

---

## Limitations

This project does not currently model:

- Base veterancy of non-special-forces units (e.g. AERO-RIFLES)
- Moving accuracy (yet!)
- Shock bonuses (yet!)
- Morale mechanics
- Availability
- Transport options

As a result, the rankings should be interpreted as comparative indicators
