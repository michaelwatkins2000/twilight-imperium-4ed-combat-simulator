"""
The Sardakk N'orr

Faction ability:
    Unrelenting — +1 to all combat rolls (space and ground, does not affect
                  SC, AFB, or bombardment).

Flagship — C'Morran N'orr:
    Combat (6;2), Sustain.
    Ability: all OTHER ships in the fleet get an additional +1 to their
             combat rolls while this ship is present.

Mech — Valkyrie Exoskeleton:
    Combat (6;1), Sustain.
    Ability: after this unit uses SUSTAIN DAMAGE during ground combat,
             produce 1 hit against the opponent's ground forces (normal
             assignment rules apply).

Faction technology — Valkyrie Particle Weave:
    Aliases: valkyrie, vpw, valkyrieparticleweave
    After making combat rolls during a round of ground combat, if the
    opponent produced ≥1 hit, produce 1 additional hit (normal assignment
    rules apply). Activates every eligible round.

Faction unit upgrade — Sardakk Dreadnought:
    Replaces the standard Dreadnought when this faction is selected.
    Combat (5;1) / Bombardment (5;1) base.
    Upgraded bombardment (4;2) — represents the faction Dreadnought upgrade tech.
    (Special ability TBD in a later phase.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from units import UnitType, Ability
from factions import FactionAbilities, register_faction

if TYPE_CHECKING:
    from combat import Unit


# ---------------------------------------------------------------------------
# Unit definitions
# ---------------------------------------------------------------------------

C_MORRAN_NORR = UnitType(
    name="C'Morran N'orr",
    combat=Ability(combat_value=6, num_dice=2),
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

VALKYRIE_EXOSKELETON = UnitType(
    name='Valkyrie Exoskeleton',
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

# Sardakk's faction Dreadnought: bombardment (4;2) at all levels.
SARDAKK_DREADNOUGHT = UnitType(
    name='Dreadnought',
    combat=Ability(combat_value=5, num_dice=1),
    upgraded_combat=Ability(combat_value=5, num_dice=1),
    sustain_damage=True,
    unit_category='Ship',
    afb=None,
    upgraded_afb=None,
    bombardment=Ability(combat_value=4, num_dice=2),
    upgraded_bombardment=Ability(combat_value=4, num_dice=2),
    space_cannon=None,
    upgraded_space_cannon=None,
)


# ---------------------------------------------------------------------------
# Faction abilities
# ---------------------------------------------------------------------------

class SardakkAbilities(FactionAbilities):

    name = "Sardakk N'orr"

    # Unrelenting: +1 to all combat rolls (applies to all units via base modifier)
    combat_roll_modifier = 1

    flagship = C_MORRAN_NORR
    mech = VALKYRIE_EXOSKELETON

    def __init__(self) -> None:
        super().__init__()
        self.unit_overrides = {'Dreadnought': SARDAKK_DREADNOUGHT}
        self.faction_tech_aliases = {
            'valkyrie':               'valkyrie_particle_weave',
            'vpw':                    'valkyrie_particle_weave',
            'valkyrieparticleweave':  'valkyrie_particle_weave',
        }

    # ------------------------------------------------------------------
    # C'Morran N'orr: +1 to combat rolls of all OTHER ships in the fleet
    # ------------------------------------------------------------------

    def get_combat_roll_modifier(self, unit: 'Unit', own_fleet: list['Unit']) -> int:
        modifier = self.combat_roll_modifier  # +1 from Unrelenting
        flagship_present = any(u.name == C_MORRAN_NORR.name for u in own_fleet)
        if flagship_present and unit.name != C_MORRAN_NORR.name:
            modifier += 1
        return modifier

    # ------------------------------------------------------------------
    # Valkyrie Particle Weave (faction tech, ground combat)
    # ------------------------------------------------------------------

    def post_roll_ground(self, own_hits: int, enemy_hits: int) -> int:  # no Unit refs needed
        if 'valkyrie_particle_weave' in self.active_faction_techs and enemy_hits >= 1:
            return own_hits + 1
        return own_hits

    # ------------------------------------------------------------------
    # Valkyrie Exoskeleton: sustain → 1 hit on opponent (ground combat)
    # ------------------------------------------------------------------

    def end_of_round_ground(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        from combat import assign_hits  # lazy import to avoid circular dependency
        for unit in own:
            if unit.name == VALKYRIE_EXOSKELETON.name and unit.sustained_this_round:
                enemy = assign_hits(enemy, 1)
        return own, enemy


register_faction(SardakkAbilities())
