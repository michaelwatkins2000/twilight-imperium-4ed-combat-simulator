"""
Twilight Imperium 4E Combat Calculator — Phase 4

All options are optional. If omitted, the tool will prompt interactively
and display available units before asking for fleet input.

Usage (fully scripted):
    python main.py --combat-type space \\
        --attacker "cruiser:2 fighter:3" --defender "dreadnought:1" \\
        --att-pds "pds:2" --def-pds "pds:1:upgraded"

    python main.py --combat-type ground \\
        --attacker "infantry:3" --defender "infantry:2" \\
        --att-ships "dreadnought:1 war_sun:1" --def-pds "pds:1"

Usage (interactive):
    python main.py

Fleet format (space-separated tokens):
    UnitName:count           — base unit,     e.g.  cruiser:2
    UnitName:count:upgraded  — upgraded unit, e.g.  cruiser:2:upgraded

Unit names are case-insensitive. 'War Sun' → warsun / war_sun / War_Sun etc.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from units import UnitType, Ability, load_unit_types, build_lookup, _normalize
from combat import Unit
from simulator import run_simulation
from technologies import Technologies
from factions import FactionAbilities, get_faction, list_factions, get_all_factions, normalize_tech_alias

app = typer.Typer(add_completion=False)

COMBAT_TYPES = {
    'space':  'Ship',
    'ground': 'Ground Force',
}


# ---------------------------------------------------------------------------
# Fleet parsing
# ---------------------------------------------------------------------------

def parse_fleet(
    raw: str,
    lookup: dict[str, UnitType],
    label: str,
) -> list[Unit] | None:
    """
    Parse a fleet string into Unit objects.
    Returns None on any error (prints message), so callers can re-prompt or abort.
    """
    units: list[Unit] = []
    for token in raw.strip().split():
        parts = token.split(':')

        if len(parts) == 2:
            raw_name, count_str = parts
            upgraded = False
        elif len(parts) == 3 and parts[2].lower() == 'upgraded':
            raw_name, count_str = parts[0], parts[1]
            upgraded = True
        else:
            typer.echo(
                f"  [{label}] Invalid token '{token}'. "
                "Expected 'UnitName:count' or 'UnitName:count:upgraded'.",
                err=True,
            )
            return None

        key = _normalize(raw_name)
        if key not in lookup:
            available = ', '.join(ut.name for ut in lookup.values())
            typer.echo(f"  [{label}] Unknown unit '{raw_name}'. Available: {available}", err=True)
            return None

        unit_type = lookup[key]

        try:
            count = int(count_str)
        except ValueError:
            typer.echo(f"  [{label}] Count must be an integer (got '{count_str}' in '{token}')", err=True)
            return None

        if count < 1:
            typer.echo(f"  [{label}] Count must be >= 1 (got {count} for '{raw_name}')", err=True)
            return None

        if upgraded and not unit_type.has_upgrade:
            typer.echo(f"  [{label}] '{unit_type.name}' has no upgrade available.", err=True)
            return None

        for _ in range(count):
            units.append(Unit(unit_type=unit_type, upgraded=upgraded))

    if not units:
        typer.echo(f"  [{label}] Fleet must contain at least one unit.", err=True)
        return None

    return units


def parse_optional_fleet(
    raw: str,
    lookup: dict[str, UnitType],
    label: str,
) -> list[Unit] | None:
    """Like parse_fleet but an empty/blank string returns an empty list (not an error)."""
    if not raw.strip():
        return []
    return parse_fleet(raw, lookup, label)


def prompt_fleet(label: str, lookup: dict[str, UnitType]) -> list[Unit]:
    """Prompt repeatedly until a valid non-empty fleet string is entered."""
    while True:
        raw = typer.prompt(f"{label} fleet")
        fleet = parse_fleet(raw, lookup, label)
        if fleet is not None:
            return fleet


def prompt_optional_fleet(label: str, lookup: dict[str, UnitType]) -> list[Unit]:
    """Prompt for a fleet string; blank input returns [] (skip)."""
    while True:
        raw = typer.prompt(f"{label} (press Enter to skip)", default="")
        fleet = parse_optional_fleet(raw, lookup, label)
        if fleet is not None:
            return fleet


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _unit_brief(ut: UnitType) -> str:
    """Compact stats for a unit used in the faction listing."""
    parts = []
    if ut.combat:
        dice = f" ({ut.combat.num_dice} dice)" if ut.combat.num_dice > 1 else ""
        parts.append(f"combat {ut.combat.combat_value}{dice}")
    if ut.sustain_damage:
        parts.append("sustain")
    return ", ".join(parts) if parts else "—"


def _ab(ab: Optional[Ability]) -> str:
    """Format an Ability for display: '5' or '5 (3 dice)'."""
    if ab is None:
        return "—"
    if ab.num_dice == 1:
        return str(ab.combat_value)
    return f"{ab.combat_value} ({ab.num_dice} dice)"


def _unit_row(ut: UnitType) -> str:
    """Single-line display of a unit's stats and upgrade info."""
    parts = []

    if ut.combat:
        dice = f" ({ut.combat.num_dice} dice)" if ut.combat.num_dice > 1 else ""
        sustain = " [sustain]" if ut.sustain_damage else ""
        parts.append(f"combat {ut.combat.combat_value}{dice}{sustain}")

    if ut.afb:
        parts.append(f"AFB {_ab(ut.afb)}")

    if ut.bombardment:
        parts.append(f"bombard {_ab(ut.bombardment)}")

    if ut.space_cannon:
        parts.append(f"space cannon {_ab(ut.space_cannon)}")

    base = "  |  ".join(parts)

    if not ut.has_upgrade:
        return base

    # Show what changes on upgrade
    upgrades = []
    if ut.upgraded_combat and ut.upgraded_combat != ut.combat:
        dice = f" ({ut.upgraded_combat.num_dice} dice)" if ut.upgraded_combat.num_dice > 1 else ""
        upgrades.append(f"combat {ut.upgraded_combat.combat_value}{dice}")
    if ut.upgraded_afb and ut.upgraded_afb != ut.afb:
        upgrades.append(f"AFB {_ab(ut.upgraded_afb)}")
    if ut.upgraded_bombardment and ut.upgraded_bombardment != ut.bombardment:
        upgrades.append(f"bombard {_ab(ut.upgraded_bombardment)}")
    if ut.upgraded_space_cannon and ut.upgraded_space_cannon != ut.space_cannon:
        upgrades.append(f"space cannon {_ab(ut.upgraded_space_cannon)}")

    upgrade_str = ", ".join(upgrades) if upgrades else "no stat changes"
    return f"{base}  →  upgrade: {upgrade_str}"


TECH_DISPLAY = {
    'x89_bacterial_weapon':  ('x89',     'Ground: double all hits on defending ground forces'),
    'antimass_deflectors':   ('antimass','Space Cannon: -1 to each incoming SC die roll'),
    'graviton_laser_system': ('graviton','Space SC Offence: own hits must target non-Fighters'),
    'plasma_scoring':        ('plasma',  'SC + Bombardment: +1 extra die at best combat value'),
    'magen_defence_grid':    ('magen',   'Ground: 1 free hit on attacker after SC Defence'),
    'duranium_armour':       ('duranium','All: repair 1 damaged unit/round (not sustained this round)'),
    'assault_cannon':        ('assault', 'Space: destroy cheapest enemy non-Fighter if ≥3 own non-Fighters'),
}


def show_tech_table() -> None:
    typer.echo("\nAvailable technologies (space-separated, use short alias or full name):")
    alias_w = max(len(v[0]) for v in TECH_DISPLAY.values())
    for field_name, (alias, desc) in TECH_DISPLAY.items():
        typer.echo(f"  {alias:{alias_w}}  ({field_name})  —  {desc}")
    typer.echo()


def parse_technologies(
    raw: Optional[str],
    label: str,
    faction: Optional[FactionAbilities] = None,
) -> Optional[Technologies]:
    """
    Parse a technology string into a Technologies instance.
    Faction-tech tokens are activated on the faction object and consumed
    before the remainder is forwarded to Technologies.parse().
    Returns None and prints an error on failure.
    """
    if not raw or not raw.strip():
        return Technologies()

    generic_tokens: list[str] = []
    for token in raw.strip().split():
        norm = normalize_tech_alias(token)
        if faction is not None and norm in faction.faction_tech_aliases:
            faction.active_faction_techs.add(faction.faction_tech_aliases[norm])
        else:
            generic_tokens.append(token)

    try:
        return Technologies.parse(' '.join(generic_tokens) if generic_tokens else None)
    except ValueError as exc:
        typer.echo(f"  [{label}] {exc}", err=True)
        return None


def parse_faction(raw: Optional[str], label: str) -> Optional[FactionAbilities]:
    """
    Look up a faction by name. Returns None (no faction) for blank input,
    or prints an error and returns None sentinel on unknown name.
    Use the returned value's truthiness carefully: a valid faction is always
    truthy (it has a name); None means either 'not provided' or 'error'.
    We distinguish by whether raw was provided.
    """
    if not raw or not raw.strip():
        return None
    faction = get_faction(raw.strip())
    if faction is None:
        available = ', '.join(list_factions()) or '(none registered yet)'
        typer.echo(
            f"  [{label}] Unknown faction '{raw}'. Available: {available}",
            err=True,
        )
    return faction  # None on unknown, FactionAbilities on success


def inject_faction_units(
    lookup: dict[str, UnitType],
    faction: FactionAbilities,
) -> None:
    """
    Mutate a fleet lookup in-place to add faction-specific units:
    - 'flagship' → faction's flagship UnitType
    - 'mech'     → faction's mech UnitType
    - Any unit_overrides replace the corresponding base-unit entry.
    """
    if faction.flagship is not None:
        lookup[_normalize('Flagship')] = faction.flagship
    if faction.mech is not None:
        lookup[_normalize('Mech')] = faction.mech
    for base_name, override_type in faction.unit_overrides.items():
        key = _normalize(base_name)
        if key in lookup:
            lookup[key] = override_type


def show_unit_table(units: dict[str, UnitType], header: str) -> None:
    typer.echo(f"\n{header}:")
    width = max(len(n) for n in units)
    for name, ut in units.items():
        typer.echo(f"  {name:{width}} : {_unit_row(ut)}")
    typer.echo("\n  Format: UnitName:count  or  UnitName:count:upgraded")


def fleet_summary(units: list[Unit]) -> str:
    from collections import Counter
    counts: Counter = Counter()
    for u in units:
        key = f"{u.name}{'(upgraded)' if u.upgraded else ''}"
        counts[key] += 1
    return ', '.join(f"{n}x {name}" for name, n in counts.items())


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@app.command()
def main(
    combat_type: Annotated[Optional[str], typer.Option(
        '--combat-type', '-c',
        help="Type of combat: 'space' or 'ground'.",
    )] = None,
    attacker: Annotated[Optional[str], typer.Option(
        '--attacker', '-a',
        help="Attacker's main fleet (ships for space, ground forces for ground).",
    )] = None,
    defender: Annotated[Optional[str], typer.Option(
        '--defender', '-d',
        help="Defender's main fleet.",
    )] = None,
    att_pds: Annotated[Optional[str], typer.Option(
        '--att-pds',
        help="Attacker's PDS for Space Cannon Offence (space combat only).",
    )] = None,
    def_pds: Annotated[Optional[str], typer.Option(
        '--def-pds',
        help="Defender's PDS. Space cannon offence (space) or "
             "space cannon defence + planetary shield (ground).",
    )] = None,
    att_ships: Annotated[Optional[str], typer.Option(
        '--att-ships',
        help="Attacker's ships in orbit for Bombardment (ground combat only).",
    )] = None,
    att_tech: Annotated[Optional[str], typer.Option(
        '--att-tech',
        help="Attacker's technologies (space-separated, e.g. 'plasma assault').",
    )] = None,
    def_tech: Annotated[Optional[str], typer.Option(
        '--def-tech',
        help="Defender's technologies (space-separated, e.g. 'antimass duranium').",
    )] = None,
    att_faction: Annotated[Optional[str], typer.Option(
        '--att-faction',
        help="Attacker's faction (e.g. 'sardakk'). Unlocks Flagship, Mech, faction abilities.",
    )] = None,
    def_faction: Annotated[Optional[str], typer.Option(
        '--def-faction',
        help="Defender's faction.",
    )] = None,
    simulations: Annotated[int, typer.Option(
        '--simulations', '-n',
        help="Number of simulations to run.",
        min=1,
    )] = 10_000,
) -> None:

    # --- Combat type ---
    if combat_type is None:
        combat_type = typer.prompt("Combat type [space/ground]")

    combat_type = combat_type.lower()  # type: ignore
    while combat_type not in COMBAT_TYPES:
        typer.echo(f"  Invalid value '{combat_type}'. Enter 'space' or 'ground'.", err=True)
        combat_type = typer.prompt("Combat type [space/ground]")

    # --- Build lookups ---
    all_unit_types = load_unit_types()
    category = COMBAT_TYPES[combat_type]

    main_units = {n: ut for n, ut in all_unit_types.items() if ut.unit_category == category}
    pds_units  = {n: ut for n, ut in all_unit_types.items() if ut.unit_category == 'Structure'}
    ship_units = {n: ut for n, ut in all_unit_types.items() if ut.unit_category == 'Ship'}

    att_main_lookup = build_lookup(main_units)
    def_main_lookup = build_lookup(main_units)
    pds_lookup  = build_lookup(pds_units)
    ship_lookup = build_lookup(ship_units)

    # Interactive mode = neither main fleet was supplied on the command line.
    # In scripted mode, unspecified support flags simply default to empty — no prompts.
    interactive = attacker is None and defender is None

    # --- Factions (resolve before fleet parsing so lookups are injected first) ---
    att_faction_obj: Optional[FactionAbilities] = None
    def_faction_obj: Optional[FactionAbilities] = None

    if interactive and att_faction is None and def_faction is None:
        all_factions = get_all_factions()
        if all_factions:
            from collections import defaultdict
            typer.echo("\nAvailable factions (press Enter to skip):")
            name_w = max(len(f.name) for f in all_factions)
            for f in all_factions:
                words = f.name.split()
                short = (words[1] if words[0].lower() == 'the' and len(words) > 1 else words[0]).lower()
                line = f"  {f.name:{name_w}}  [{short}]"
                if f.faction_tech_aliases:
                    by_field: dict[str, list[str]] = defaultdict(list)
                    for alias, field in f.faction_tech_aliases.items():
                        by_field[field].append(alias)
                    tech_parts = []
                    for aliases in [v for _, v in sorted(by_field.items())]:
                        tech_parts.append(" / ".join(sorted(aliases, key=len)))
                    line += f"  —  faction techs: {',  '.join(tech_parts)}"
                typer.echo(line)
                if f.flagship:
                    typer.echo(f"      Flagship : {_unit_brief(f.flagship)}")
                if f.mech:
                    typer.echo(f"      Mech     : {_unit_brief(f.mech)}")
                typer.echo()

    if att_faction is None and interactive:
        raw = typer.prompt("Attacker faction (press Enter to skip)", default="")
        att_faction = raw.strip() or None

    if att_faction is not None:
        att_faction_obj = parse_faction(att_faction, "Attacker faction")
        if att_faction_obj is None:
            raise typer.Exit(code=1)
        inject_faction_units(att_main_lookup, att_faction_obj)

    if def_faction is None and interactive:
        raw = typer.prompt("Defender faction (press Enter to skip)", default="")
        def_faction = raw.strip() or None

    if def_faction is not None:
        def_faction_obj = parse_faction(def_faction, "Defender faction")
        if def_faction_obj is None:
            raise typer.Exit(code=1)
        inject_faction_units(def_main_lookup, def_faction_obj)

    if interactive:
        show_unit_table(main_units, f"Available units ({combat_type} combat)")
        has_flagship = (att_faction_obj and att_faction_obj.flagship) or (def_faction_obj and def_faction_obj.flagship)
        has_mech = (att_faction_obj and att_faction_obj.mech) or (def_faction_obj and def_faction_obj.mech)
        if (has_flagship and category == 'Ship') or (has_mech and category == 'Ground Force'):
            unit_name = 'Flagship' if category == 'Ship' else 'Mech'
            typer.echo(f"  {unit_name} also available — enter as '{unit_name}:1' (stats shown above)")

    # --- Main fleets ---
    if attacker is None:
        typer.echo()
        attacker_units = prompt_fleet("Attacker", att_main_lookup)
    else:
        attacker_units = parse_fleet(attacker, att_main_lookup, "Attacker")
        if attacker_units is None:
            raise typer.Exit(code=1)

    if defender is None:
        defender_units = prompt_fleet("Defender", def_main_lookup)
    else:
        defender_units = parse_fleet(defender, def_main_lookup, "Defender")
        if defender_units is None:
            raise typer.Exit(code=1)

    # --- PDS ---
    if interactive:
        show_unit_table(pds_units, "Available PDS")
        typer.echo()

    if att_pds is None:
        if interactive and combat_type == 'space':
            att_pds_units = prompt_optional_fleet("Attacker PDS", pds_lookup)
        else:
            att_pds_units = []
    else:
        att_pds_units = parse_optional_fleet(att_pds, pds_lookup, "Attacker PDS")
        if att_pds_units is None:
            raise typer.Exit(code=1)

    if def_pds is None:
        if interactive:
            def_pds_units = prompt_optional_fleet("Defender PDS", pds_lookup)
        else:
            def_pds_units = []
    else:
        def_pds_units = parse_optional_fleet(def_pds, pds_lookup, "Defender PDS")
        if def_pds_units is None:
            raise typer.Exit(code=1)

    # --- Technologies ---
    if interactive:
        show_tech_table()

    if att_tech is None:
        if interactive:
            raw_at = typer.prompt("Attacker technologies (press Enter to skip)", default="")
            att_tech_obj = parse_technologies(raw_at or None, "Attacker tech", att_faction_obj)
            if att_tech_obj is None:
                raise typer.Exit(code=1)
        else:
            att_tech_obj = Technologies()
    else:
        att_tech_obj = parse_technologies(att_tech, "Attacker tech", att_faction_obj)
        if att_tech_obj is None:
            raise typer.Exit(code=1)

    if def_tech is None:
        if interactive:
            raw_dt = typer.prompt("Defender technologies (press Enter to skip)", default="")
            def_tech_obj = parse_technologies(raw_dt or None, "Defender tech", def_faction_obj)
            if def_tech_obj is None:
                raise typer.Exit(code=1)
        else:
            def_tech_obj = Technologies()
    else:
        def_tech_obj = parse_technologies(def_tech, "Defender tech", def_faction_obj)
        if def_tech_obj is None:
            raise typer.Exit(code=1)

    # --- Attacker ships in orbit (ground combat only) ---
    att_ship_units: list[Unit] = []
    if combat_type == 'ground':
        if att_ships is None:
            if interactive:
                show_unit_table(ship_units, "Available ships for orbital bombardment")
                typer.echo()
                att_ship_units = prompt_optional_fleet("Attacker ships in orbit", ship_lookup)
            # else: no orbital ships (scripted, flag not provided)
        else:
            result = parse_optional_fleet(att_ships, ship_lookup, "Attacker ships")
            if result is None:
                raise typer.Exit(code=1)
            att_ship_units = result

    # --- Run simulation ---
    typer.echo(f"\nRunning {simulations:,} simulations of {combat_type} combat...")
    if att_faction_obj:
        typer.echo(f"  Attacker faction: {att_faction_obj.name}")
    typer.echo(f"  Attacker        : {fleet_summary(attacker_units)}")
    if att_pds_units:
        typer.echo(f"  Attacker PDS    : {fleet_summary(att_pds_units)}")
    if att_ship_units:
        typer.echo(f"  Attacker ships  : {fleet_summary(att_ship_units)}")
    if att_tech_obj.active_names():
        typer.echo(f"  Attacker techs  : {', '.join(att_tech_obj.active_names())}")
    if def_faction_obj:
        typer.echo(f"  Defender faction: {def_faction_obj.name}")
    typer.echo(f"  Defender        : {fleet_summary(defender_units)}")
    if def_pds_units:
        typer.echo(f"  Defender PDS    : {fleet_summary(def_pds_units)}")
    if def_tech_obj.active_names():
        typer.echo(f"  Defender techs  : {', '.join(def_tech_obj.active_names())}")

    results = run_simulation(
        combat_type,
        attacker_units,
        defender_units,
        att_pds=att_pds_units,
        att_ships=att_ship_units,
        def_pds=def_pds_units,
        att_techs=att_tech_obj,
        def_techs=def_tech_obj,
        att_faction=att_faction_obj,
        def_faction=def_faction_obj,
        n_simulations=simulations,
    )

    typer.echo("\n" + "=" * 40)
    typer.echo("  Results")
    typer.echo("=" * 40)
    typer.echo(f"  Attacker Win : {results['attacker_win']:5.1f}%")
    typer.echo(f"  Defender Win : {results['defender_win']:5.1f}%")
    typer.echo(f"  Draw         : {results['draw']:5.1f}%")
    typer.echo("=" * 40 + "\n")


if __name__ == '__main__':
    app()
