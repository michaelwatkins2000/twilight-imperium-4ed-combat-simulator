import random
import copy
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from units import UnitType, Ability


class CombatResult(Enum):
    ATTACKER_WIN = "Attacker Win"
    DEFENDER_WIN = "Defender Win"
    DRAW = "Draw"


def roll_ability(ability: Ability) -> int:
    """Roll an ability's dice and return total hits scored."""
    return sum(1 for _ in range(ability.num_dice) if random.randint(1, 10) >= ability.combat_value)


@dataclass
class Unit:
    unit_type: UnitType
    upgraded: bool = False
    damaged: bool = False  # True once sustain damage has been used

    @property
    def name(self) -> str:
        return self.unit_type.name

    @property
    def effective_combat(self) -> Optional[Ability]:
        if self.upgraded and self.unit_type.upgraded_combat is not None:
            return self.unit_type.upgraded_combat
        return self.unit_type.combat

    @property
    def effective_afb(self) -> Optional[Ability]:
        if self.upgraded and self.unit_type.upgraded_afb is not None:
            return self.unit_type.upgraded_afb
        return self.unit_type.afb

    @property
    def effective_bombardment(self) -> Optional[Ability]:
        if self.upgraded and self.unit_type.upgraded_bombardment is not None:
            return self.unit_type.upgraded_bombardment
        return self.unit_type.bombardment

    @property
    def effective_space_cannon(self) -> Optional[Ability]:
        if self.upgraded and self.unit_type.upgraded_space_cannon is not None:
            return self.unit_type.upgraded_space_cannon
        return self.unit_type.space_cannon

    @property
    def can_sustain(self) -> bool:
        return self.unit_type.sustain_damage and not self.damaged

    def roll_combat(self) -> int:
        """Roll main combat dice and return total hits scored."""
        c = self.effective_combat
        return roll_ability(c) if c is not None else 0


def assign_hits(units: list[Unit], hits: int) -> list[Unit]:
    """
    Assign incoming hits to a fleet optimally:

    1. Use sustain damage on highest-value units first (War Sun, Dreadnought).
    2. Destroy lowest-value units first (Fighter, Destroyer, Cruiser, Carrier ... War Sun).

    Returns the surviving unit list (units are mutated for sustain state).
    """
    if hits <= 0:
        return units

    remaining = hits
    surviving = list(units)

    # Step 1: absorb hits via sustain damage (best units first)
    sustainers = sorted(
        [u for u in surviving if u.can_sustain],
        key=lambda u: -u.unit_type.destroy_priority,
    )
    for unit in sustainers:
        if remaining <= 0:
            break
        unit.damaged = True
        remaining -= 1

    if remaining <= 0:
        return surviving

    # Step 2: destroy units, cheapest first
    to_destroy = set()
    destroyable = sorted(surviving, key=lambda u: u.unit_type.destroy_priority)
    for unit in destroyable:
        if remaining <= 0:
            break
        to_destroy.add(id(unit))
        remaining -= 1

    return [u for u in surviving if id(u) not in to_destroy]


def assign_hits_to_fighters(units: list[Unit], hits: int) -> list[Unit]:
    """
    AFB hit assignment: hits can only be assigned to Fighters.
    Excess hits (no fighters remaining) are wasted.
    Fighters have no sustain, so they are simply destroyed.
    """
    if hits <= 0:
        return units

    to_destroy = set()
    for u in units:
        if hits <= 0:
            break
        if u.name == 'Fighter':
            to_destroy.add(id(u))
            hits -= 1

    return [u for u in units if id(u) not in to_destroy]


def _determine_result(attackers: list[Unit], defenders: list[Unit]) -> CombatResult:
    if attackers and not defenders:
        return CombatResult.ATTACKER_WIN
    if defenders and not attackers:
        return CombatResult.DEFENDER_WIN
    return CombatResult.DRAW


def simulate_space_combat(
    att_ships: list[Unit],
    def_ships: list[Unit],
    att_pds: Optional[list[Unit]] = None,
    def_pds: Optional[list[Unit]] = None,
) -> CombatResult:
    """
    Simulate a single space combat to conclusion (no retreats).

    Pre-combat sequence (each fires once, before round 1):
      1. Anti-Fighter Barrage — both sides' Destroyers fire simultaneously;
         hits assigned to Fighters only, cannot be sustained.
      2. Space Cannon Offence — both sides' PDS fire simultaneously;
         hits assigned to any ship using normal assign_hits rules.

    Then main combat rounds until one side is eliminated.
    """
    att_pds = att_pds or []
    def_pds = def_pds or []

    attackers = [copy.copy(u) for u in att_ships]
    defenders = [copy.copy(u) for u in def_ships]

    # Step 1: Anti-Fighter Barrage (simultaneous)
    att_afb = sum(roll_ability(u.effective_afb) for u in attackers if u.effective_afb)
    def_afb = sum(roll_ability(u.effective_afb) for u in defenders if u.effective_afb)
    attackers = assign_hits_to_fighters(attackers, def_afb)
    defenders = assign_hits_to_fighters(defenders, att_afb)

    if not attackers or not defenders:
        return _determine_result(attackers, defenders)

    # Step 2: Space Cannon Offence (simultaneous, hits any ship)
    att_sc = sum(roll_ability(u.effective_space_cannon) for u in att_pds if u.effective_space_cannon)
    def_sc = sum(roll_ability(u.effective_space_cannon) for u in def_pds if u.effective_space_cannon)
    attackers = assign_hits(attackers, def_sc)
    defenders = assign_hits(defenders, att_sc)

    if not attackers or not defenders:
        return _determine_result(attackers, defenders)

    # Main combat rounds
    while attackers and defenders:
        att_hits = sum(u.roll_combat() for u in attackers)
        def_hits = sum(u.roll_combat() for u in defenders)
        attackers = assign_hits(attackers, def_hits)
        defenders = assign_hits(defenders, att_hits)

    return _determine_result(attackers, defenders)


def simulate_ground_combat(
    att_ground: list[Unit],
    def_ground: list[Unit],
    att_ships: Optional[list[Unit]] = None,
    def_pds: Optional[list[Unit]] = None,
) -> CombatResult:
    """
    Simulate a single ground combat to conclusion (no retreats).

    Pre-combat sequence (each fires once, before round 1):
      1. Bombardment — attacker's ships bombard defender's ground forces.
         Skipped entirely if defender has any PDS (Planetary Shield).
      2. Space Cannon Defence — defender's PDS fires at attacker's ground forces.
         Only fires if defender has PDS.

    Then main combat rounds until one side is eliminated.
    """
    att_ships = att_ships or []
    def_pds = def_pds or []

    attackers = [copy.copy(u) for u in att_ground]
    defenders = [copy.copy(u) for u in def_ground]

    defender_has_pds = len(def_pds) > 0

    # Step 1: Bombardment (blocked by Planetary Shield)
    if not defender_has_pds:
        bomb_hits = sum(roll_ability(u.effective_bombardment) for u in att_ships if u.effective_bombardment)
        defenders = assign_hits(defenders, bomb_hits)
        if not defenders:
            return _determine_result(attackers, defenders)

    # Step 2: Space Cannon Defence (defender only, hits ground forces)
    if defender_has_pds:
        sc_def_hits = sum(roll_ability(u.effective_space_cannon) for u in def_pds if u.effective_space_cannon)
        attackers = assign_hits(attackers, sc_def_hits)
        if not attackers:
            return _determine_result(attackers, defenders)

    # Main combat rounds
    while attackers and defenders:
        att_hits = sum(u.roll_combat() for u in attackers)
        def_hits = sum(u.roll_combat() for u in defenders)
        attackers = assign_hits(attackers, def_hits)
        defenders = assign_hits(defenders, att_hits)

    return _determine_result(attackers, defenders)
