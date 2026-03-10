# Twilight Imperium 4E Combat Simulator

A Monte Carlo combat probability calculator for **Twilight Imperium 4th Edition**. Provide your fleets, run thousands of simulated combats, and get attacker/defender win percentages.

---

## Current Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Core space & ground combat | ✅ Complete |
| 2 | Pre-combat steps (AFB, Space Cannon, Bombardment) | ✅ Complete |
| 3 | Generic technologies | 🔜 Planned |
| 4 | Faction units, flagships, mechs & abilities | 🔜 Planned |
| 5 | Web UI | 🔜 Planned |

---

## Installation

Requires Python 3.10+.

```bash
# Clone the repo
git clone git@github.com:michaelwatkins2000/twilight-imperium-4ed-combat-simulator.git
cd twilight-imperium-4ed-combat-simulator

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Interactive mode

Run with no arguments to be guided through all inputs:

```bash
python main.py
```

### Scripted mode

Pass all arguments directly for quick re-runs:

```bash
# Space combat
python main.py --combat-type space \
    --attacker "Cruiser:2 Fighter:3" \
    --defender "Dreadnought:1:upgraded"

# Space combat with PDS
python main.py -c space \
    -a "Destroyer:2 Fighter:3" \
    -d "Cruiser:1" \
    --att-pds "PDS:1" \
    --def-pds "PDS:1:upgraded"

# Ground combat with bombardment
python main.py -c ground \
    -a "Infantry:3" \
    -d "Infantry:2" \
    --att-ships "Dreadnought:1 War_Sun:1"

# Ground combat with defender PDS (blocks bombardment, fires Space Cannon Defence)
python main.py -c ground \
    -a "Infantry:3" \
    --att-ships "Dreadnought:1" \
    -d "Infantry:2" \
    --def-pds "PDS:1"

# Custom simulation count
python main.py -c space -a "War_Sun:1" -d "Cruiser:3" -n 50000
```

### Fleet format

```
UnitName:count            # base unit
UnitName:count:upgraded   # upgraded unit
```

Unit names are **case-insensitive** and accept spaces, underscores, or no separator (`warsun`, `war_sun`, `War Sun` all work).

---

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--combat-type` | `-c` | `space` or `ground` |
| `--attacker` | `-a` | Attacker's main fleet |
| `--defender` | `-d` | Defender's main fleet |
| `--att-pds` | | Attacker PDS — Space Cannon Offence (space only) |
| `--def-pds` | | Defender PDS — Space Cannon Offence (space) or Space Cannon Defence + Planetary Shield (ground) |
| `--att-ships` | | Attacker ships in orbit for Bombardment (ground only) |
| `--simulations` | `-n` | Number of simulations (default: 10,000) |

---

## Units

### Ships (space combat)

| Unit | Combat | Upgraded | AFB | Bombardment | Sustain |
|------|--------|----------|-----|-------------|---------|
| Fighter | 9 | 8 | — | — | No |
| Destroyer | 9 | 8 | 9 (2 dice) → 6 (3 dice) | — | No |
| Cruiser | 7 | 6 | — | — | No |
| Carrier | 9 | 9 | — | — | No |
| Dreadnought | 5 | 5 | — | 5 | Yes |
| War Sun | 3 (3 dice) | — | — | 3 (3 dice) | Yes |

### Ground Forces

| Unit | Combat | Upgraded | Sustain |
|------|--------|----------|---------|
| Infantry | 8 | 7 | No |

### Structures

| Unit | Space Cannon | Upgraded |
|------|-------------|----------|
| PDS | 6 | 5 |

---

## Combat Sequence

### Space Combat
1. **Space Cannon Offence** — both sides' PDS fire simultaneously; hits assigned to any ship (including Fighters)
2. **Anti-Fighter Barrage** — both sides' Destroyers fire simultaneously; hits assigned to Fighters only (cannot be sustained)
3. **Main combat rounds** — both sides roll simultaneously until one side is eliminated

> Fighters can absorb Space Cannon hits before AFB fires, so the order matters.

### Ground Combat
1. **Bombardment** — attacker's ships bombard defender's ground forces *(skipped if defender has PDS — Planetary Shield)*
2. **Space Cannon Defence** — defender's PDS fires at attacker's ground forces *(only if defender has PDS)*
3. **Main combat rounds** — both sides roll simultaneously until one side is eliminated

**Outcomes:** Attacker Win / Defender Win / Draw (simultaneous elimination)

---

## Project Structure

```
├── unit_combat_values.csv   # Unit stats (source of truth)
├── units.py                 # UnitType & Ability dataclasses, CSV loader
├── combat.py                # Combat simulation logic
├── simulator.py             # Monte Carlo runner
├── main.py                  # CLI (Typer)
└── requirements.txt
```
