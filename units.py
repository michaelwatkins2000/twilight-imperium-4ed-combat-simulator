import csv
import os
from dataclasses import dataclass
from typing import Optional


# Priority for assigning casualties — lower number = destroy first.
# Carrier sits below Cruiser to reflect real play patterns (capacity considerations).
# Sustain damage is used on highest priority units first (reverse order).
UNIT_DESTROY_PRIORITY = {
    'Fighter':      1,
    'Destroyer':    2,
    'Cruiser':      3,
    'Carrier':      4,
    'Infantry':     5,
    'Dreadnought':  6,
    'War Sun':      7,
}


@dataclass(frozen=True)
class Ability:
    """A combat ability: rolls num_dice dice, each hitting on >= combat_value."""
    combat_value: int
    num_dice: int


@dataclass(frozen=True)
class UnitType:
    name: str
    combat: Optional[Ability]            # Main combat ability (None for structures like PDS)
    upgraded_combat: Optional[Ability]   # None if no upgrade or upgrade doesn't change combat
    sustain_damage: bool
    unit_category: str                   # 'Ship', 'Ground Force', or 'Structure'
    afb: Optional[Ability]               # Anti-Fighter Barrage
    upgraded_afb: Optional[Ability]
    bombardment: Optional[Ability]
    upgraded_bombardment: Optional[Ability]
    space_cannon: Optional[Ability]
    upgraded_space_cannon: Optional[Ability]

    @property
    def destroy_priority(self) -> int:
        return UNIT_DESTROY_PRIORITY.get(self.name, 99)

    @property
    def has_upgrade(self) -> bool:
        """True if the unit has any upgradeable stats."""
        return any([
            self.upgraded_combat is not None,
            self.upgraded_afb is not None,
            self.upgraded_bombardment is not None,
            self.upgraded_space_cannon is not None,
        ])


def _normalize(name: str) -> str:
    """Lowercase and strip spaces/underscores for case-insensitive lookup."""
    return name.lower().replace(' ', '').replace('_', '')


def _parse_ability(s: str) -> Optional[Ability]:
    """
    Parse an ability string:
      '(value;dice)' → Ability(value, dice)
      bare integer   → Ability(value, 1)  [1 die assumed]
      '', 'N/A'      → None
    """
    s = s.strip()
    if not s or s == 'N/A':
        return None
    if s.startswith('('):
        inner = s.strip('()')
        cv, nd = inner.split(';')
        return Ability(combat_value=int(cv), num_dice=int(nd))
    return Ability(combat_value=int(s), num_dice=1)


def load_unit_types(csv_path: Optional[str] = None) -> dict[str, UnitType]:
    """
    Load unit types from CSV. Returns a dict keyed by canonical name (e.g. 'War Sun').
    Use build_lookup() for case-insensitive input matching.
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'unit_combat_values.csv')

    unit_types = {}
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Unit Name'].strip()
            unit_types[name] = UnitType(
                name=name,
                combat=_parse_ability(row['Combat Value']),
                upgraded_combat=_parse_ability(row['Upgraded Combat Value']),
                sustain_damage=row['Sustain Damage'].strip() == 'Yes',
                unit_category=row['Type of Unit'].strip(),
                afb=_parse_ability(row['Anti Fighter Barrage']),
                upgraded_afb=_parse_ability(row['Upgraded Anti Fighter Barrage']),
                bombardment=_parse_ability(row['Bombardment']),
                upgraded_bombardment=_parse_ability(row['Upgraded Bombardment']),
                space_cannon=_parse_ability(row['Space Cannon']),
                upgraded_space_cannon=_parse_ability(row['Upgraded Space Cannon']),
            )

    return unit_types


def build_lookup(unit_types: dict[str, UnitType]) -> dict[str, UnitType]:
    """
    Returns a case-insensitive lookup dict. Keys are normalised (lowercase,
    no spaces or underscores), values are UnitType objects.

    Accepted inputs for 'War Sun': 'war sun', 'War Sun', 'warsun', 'war_sun', etc.
    """
    return {_normalize(name): ut for name, ut in unit_types.items()}
