"""
Phase 3 — Generic combat technologies.

Each technology is a boolean flag on the Technologies dataclass.
Parse from a space-separated string via Technologies.parse().

Supported token forms (case-insensitive):
    x89 / x89_bacterial_weapon
    antimass / antimass_deflectors
    graviton / graviton_laser_system
    plasma / plasma_scoring
    magen / magen_defence_grid
    duranium / duranium_armour
    assault / assault_cannon
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional

# Map every accepted alias → canonical field name
TECH_ALIASES: dict[str, str] = {
    'x89':                    'x89_bacterial_weapon',
    'x89bacterialweapon':     'x89_bacterial_weapon',
    'antimass':               'antimass_deflectors',
    'antimassdeflectors':     'antimass_deflectors',
    'graviton':               'graviton_laser_system',
    'gravitonlasersystem':    'graviton_laser_system',
    'plasma':                 'plasma_scoring',
    'plasmascoring':          'plasma_scoring',
    'magen':                  'magen_defence_grid',
    'magendefencegrid':       'magen_defence_grid',
    'magendefensegrid':       'magen_defence_grid',
    'duranium':               'duranium_armour',
    'duraniumarmour':         'duranium_armour',
    'duraniumarmor':          'duranium_armour',
    'assault':                'assault_cannon',
    'assaultcannon':          'assault_cannon',
}


def _normalize_tech(token: str) -> str:
    return token.lower().replace(' ', '').replace('_', '').replace('-', '')


@dataclass
class Technologies:
    """
    Boolean flags for each generic combat technology a faction may possess.

    x89_bacterial_weapon  — Ground: double all hits on enemy ground forces
                            (attacker: bombardment + combat hits doubled;
                             defender: combat hits doubled; no bombardment)
    antimass_deflectors   — Space Cannon: subtract 1 from each incoming SC die
                            (both SC Offence and SC Defence)
    graviton_laser_system — Space Cannon Offence: owner's SC hits must target
                            non-Fighter ships first; excess hits spill onto
                            Fighters once all non-Fighters are eliminated
    plasma_scoring        — Space Cannon + Bombardment: +1 extra die rolled at
                            the best (lowest) combat value among the firing units
    magen_defence_grid    — Ground: after Space Cannon Defence, if defender has
                            a PDS structure, score 1 free hit against attacker's
                            ground forces; targets non-sustain units first
    duranium_armour       — All combat: at the end of each round, repair one
                            damaged unit that did NOT sustain this round
                            (checked before win condition)
    assault_cannon        — Space: after SC Offence + AFB, if owner has ≥3
                            non-Fighter ships, destroy 1 enemy non-Fighter
                            (no sustain allowed); both sides checked simultaneously
    """
    x89_bacterial_weapon:  bool = False
    antimass_deflectors:   bool = False
    graviton_laser_system: bool = False
    plasma_scoring:        bool = False
    magen_defence_grid:    bool = False
    duranium_armour:       bool = False
    assault_cannon:        bool = False

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def parse(tech_string: Optional[str]) -> 'Technologies':
        """
        Parse a space-separated technology string into a Technologies instance.

        Raises ValueError with a helpful message on unknown tokens.
        Returns Technologies() (all False) for None or blank input.
        """
        if not tech_string or not tech_string.strip():
            return Technologies()

        kwargs: dict[str, bool] = {}
        for raw in tech_string.strip().split():
            key = _normalize_tech(raw)
            field_name = TECH_ALIASES.get(key)
            if field_name is None:
                known = ', '.join(sorted({v for v in TECH_ALIASES.values()}))
                raise ValueError(
                    f"Unknown technology '{raw}'. "
                    f"Available: {known}"
                )
            kwargs[field_name] = True

        return Technologies(**kwargs)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def active_names(self) -> list[str]:
        """Return field names of all enabled technologies."""
        return [f.name for f in fields(self) if getattr(self, f.name)]
