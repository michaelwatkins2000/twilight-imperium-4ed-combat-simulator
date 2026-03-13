"""
The Arborec

Flagship — Duha Menaimon:
    Combat (7;2), Sustain.
    No combat-relevant ability.

Mech — Letani Behemoth:
    Combat (6;1), Sustain.
    No combat-relevant ability.

Faction unit upgrade — Letani Warrior:
    Replaces Infantry. Same combat stats as standard Infantry (8;1 / 7;1).

No combat-relevant faction ability.
"""

from __future__ import annotations

from units import UnitType, Ability
from factions import FactionAbilities, register_faction


# ---------------------------------------------------------------------------
# Unit definitions
# ---------------------------------------------------------------------------

DUHA_MENAIMON = UnitType(
    name='Duha Menaimon',
    combat=Ability(combat_value=7, num_dice=2),
    upgraded_combat=None,
    sustain_damage=True,
    unit_category='Ship',
    afb=None,
    upgraded_afb=None,
    bombardment=None,
    upgraded_bombardment=None,
    space_cannon=None,
    upgraded_space_cannon=None,
)

LETANI_BEHEMOTH = UnitType(
    name='Letani Behemoth',
    combat=Ability(combat_value=6, num_dice=1),
    upgraded_combat=None,
    sustain_damage=True,
    unit_category='Ground Force',
    afb=None,
    upgraded_afb=None,
    bombardment=None,
    upgraded_bombardment=None,
    space_cannon=None,
    upgraded_space_cannon=None,
)

# Same combat stats as standard Infantry.
LETANI_WARRIOR = UnitType(
    name='Infantry',
    combat=Ability(combat_value=8, num_dice=1),
    upgraded_combat=Ability(combat_value=7, num_dice=1),
    sustain_damage=False,
    unit_category='Ground Force',
    afb=None,
    upgraded_afb=None,
    bombardment=None,
    upgraded_bombardment=None,
    space_cannon=None,
    upgraded_space_cannon=None,
)


# ---------------------------------------------------------------------------
# Faction abilities
# ---------------------------------------------------------------------------

class ArborecAbilities(FactionAbilities):

    name = 'The Arborec'

    flagship = DUHA_MENAIMON
    mech = LETANI_BEHEMOTH

    def __init__(self) -> None:
        super().__init__()
        self.unit_overrides = {'Infantry': LETANI_WARRIOR}


register_faction(ArborecAbilities())
