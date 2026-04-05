"""
The Federation of Sol

Flagship — Genesis:
    Combat (5;2), Sustain.
    No combat-relevant ability.

Mech — ZS Thunderbolt M2:
    Combat (6;1), Sustain.
    No combat-relevant ability.

Faction unit upgrade — Spec Ops (replaces Infantry):
    Base    : Combat (7;1)
    Upgraded: Combat (6;1)

Faction unit upgrade — Sol Carrier II (replaces Carrier):
    Base    : Combat (9;1), no sustain — same as standard Carrier.
    Upgraded: Combat (9;1), Sustain.
"""

from __future__ import annotations

import random

from units import UnitType, Ability
from factions import FactionAbilities, register_faction, AgentAbilities, register_agent


# ---------------------------------------------------------------------------
# Unit definitions
# ---------------------------------------------------------------------------

GENESIS = UnitType(
    name='Genesis',
    combat=Ability(combat_value=5, num_dice=2),
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

ZS_THUNDERBOLT_M2 = UnitType(
    name='ZS Thunderbolt M2',
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

# Spec Ops replaces Infantry: better combat value, improves further when upgraded.
SPEC_OPS = UnitType(
    name='Infantry',
    combat=Ability(combat_value=7, num_dice=1),
    upgraded_combat=Ability(combat_value=6, num_dice=1),
    sustain_damage=False,
    unit_category='Ground Force',
    afb=None,
    upgraded_afb=None,
    bombardment=None,
    upgraded_bombardment=None,
    space_cannon=None,
    upgraded_space_cannon=None,
)

# Sol Carrier II replaces Carrier: gains Sustain when upgraded.
SOL_CARRIER_II = UnitType(
    name='Carrier',
    combat=Ability(combat_value=9, num_dice=1),
    upgraded_combat=Ability(combat_value=9, num_dice=1),
    sustain_damage=False,
    unit_category='Ship',
    afb=None,
    upgraded_afb=None,
    bombardment=None,
    upgraded_bombardment=None,
    space_cannon=None,
    upgraded_space_cannon=None,
    upgraded_sustain_damage=True,
)


# ---------------------------------------------------------------------------
# Faction abilities
# ---------------------------------------------------------------------------

class SolAbilities(FactionAbilities):

    name = 'The Federation of Sol'
    name_aliases = ['Sol']

    flagship = GENESIS
    mech = ZS_THUNDERBOLT_M2

    def __init__(self) -> None:
        super().__init__()
        self.unit_overrides = {
            'Infantry': SPEC_OPS,
            'Carrier':  SOL_CARRIER_II,
        }


register_faction(SolAbilities())


# ---------------------------------------------------------------------------
# Agent — Evelyn Delouis
# ---------------------------------------------------------------------------

class SolAgent(AgentAbilities):
    """
    Evelyn Delouis (Sol agent).

    At the start of round 1 of ground combat, the best-combat-value ground
    force rolls 1 extra die.  Optimal play: always used on round 1.
    """

    name = "Evelyn Delouis"
    faction_source = "The Federation of Sol"

    def extra_hits_ground_round(
        self,
        own: list,
        enemy: list,
        round_num: int,
    ) -> int:
        if round_num != 1:
            return 0
        combat_units = [u for u in own if u.effective_combat is not None]
        if not combat_units:
            return 0
        best = min(combat_units, key=lambda u: u.effective_combat.combat_value)
        return 1 if random.randint(1, 10) >= best.effective_combat.combat_value else 0


register_agent(SolAgent())
