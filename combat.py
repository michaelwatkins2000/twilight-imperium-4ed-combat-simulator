import random
import copy
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from units import UnitType, Ability
from technologies import Technologies


class CombatResult(Enum):
    ATTACKER_WIN = "Attacker Win"
    DEFENDER_WIN = "Defender Win"
    DRAW = "Draw"


# ---------------------------------------------------------------------------
# Unit dataclass
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    unit_type: UnitType
    upgraded: bool = False
    damaged: bool = False           # True once sustain damage has been used
    sustained_this_round: bool = False  # Reset each round; blocks Duranium repair

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
        c = self.effective_combat
        return _roll_ability(c) if c is not None else 0


# ---------------------------------------------------------------------------
# Rolling helpers
# ---------------------------------------------------------------------------

def _roll_die(combat_value: int, antimass: bool = False) -> int:
    """Roll a single die; subtract 1 from result if antimass applies."""
    result = random.randint(1, 10)
    if antimass:
        result -= 1
    return 1 if result >= combat_value else 0


def _roll_ability(ability: Ability, antimass: bool = False) -> int:
    """Roll all dice for an ability and return total hits."""
    return sum(_roll_die(ability.combat_value, antimass) for _ in range(ability.num_dice))


def roll_sc_hits(
    pds: list[Unit],
    plasma_scoring: bool = False,
    antimass: bool = False,
) -> int:
    """
    Roll Space Cannon hits for a list of PDS units.

    plasma_scoring: add 1 extra die at the best (lowest) combat value.
    antimass: subtract 1 from each die roll (applied to all dice including plasma).
    """
    if not pds:
        return 0

    hits = sum(
        _roll_ability(u.effective_space_cannon, antimass)
        for u in pds
        if u.effective_space_cannon
    )

    if plasma_scoring:
        sc_abilities = [u.effective_space_cannon for u in pds if u.effective_space_cannon]
        if sc_abilities:
            best_cv = min(a.combat_value for a in sc_abilities)
            hits += _roll_die(best_cv, antimass)

    return hits


def roll_bombardment_hits(
    ships: list[Unit],
    plasma_scoring: bool = False,
    x89: bool = False,
) -> int:
    """
    Roll Bombardment hits for a list of ships.

    plasma_scoring: add 1 extra die at the best (lowest) bombardment combat value.
    x89: double the total hits after rolling.
    """
    if not ships:
        return 0

    hits = sum(
        _roll_ability(u.effective_bombardment)
        for u in ships
        if u.effective_bombardment
    )

    if plasma_scoring:
        bomb_abilities = [u.effective_bombardment for u in ships if u.effective_bombardment]
        if bomb_abilities:
            best_cv = min(a.combat_value for a in bomb_abilities)
            hits += _roll_die(best_cv)

    if x89:
        hits *= 2

    return hits


# ---------------------------------------------------------------------------
# Hit assignment
# ---------------------------------------------------------------------------

def assign_hits(units: list[Unit], hits: int) -> list[Unit]:
    """
    Assign incoming hits to a fleet optimally:
      1. Sustain damage on highest-value units first (War Sun, Dreadnought).
      2. Destroy lowest-value units first (Fighter → War Sun).

    Returns the surviving unit list (sustain state is mutated on units).
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
        unit.sustained_this_round = True
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


def assign_hits_graviton(units: list[Unit], hits: int) -> list[Unit]:
    """
    Graviton Laser System hit assignment:
    SC hits must target non-Fighter ships first. Once all non-Fighters are
    eliminated, any remaining hits spill over onto Fighters normally.
    If there are no non-Fighters at all, hits are assigned normally.
    """
    if hits <= 0:
        return units

    non_fighters = [u for u in units if u.name != 'Fighter']
    fighters = [u for u in units if u.name == 'Fighter']

    if not non_fighters:
        return assign_hits(fighters, hits)

    # Each non-fighter absorbs 1 hit to destroy; sustainers absorb 1 extra.
    non_fighter_capacity = sum(2 if u.can_sustain else 1 for u in non_fighters)
    hits_for_non_fighters = min(hits, non_fighter_capacity)
    hits_for_fighters = hits - hits_for_non_fighters

    surviving_non_fighters = assign_hits(non_fighters, hits_for_non_fighters)
    surviving_fighters = assign_hits(fighters, hits_for_fighters)
    return surviving_non_fighters + surviving_fighters


# ---------------------------------------------------------------------------
# Technology effect helpers
# ---------------------------------------------------------------------------

def apply_duranium_armour(units: list[Unit]) -> None:
    """
    Duranium Armour: at end of each combat round, repair the most valuable
    damaged unit that did NOT use sustain damage this round (mutates in-place).
    """
    candidates = [u for u in units if u.damaged and not u.sustained_this_round]
    if candidates:
        best = max(candidates, key=lambda u: u.unit_type.destroy_priority)
        best.damaged = False


def apply_magen(attacker_ground: list[Unit]) -> list[Unit]:
    """
    Magen Defence Grid: defender scores 1 free hit against attacker's ground
    forces after Space Cannon Defence.

    Targeting priority (defender always picks optimally for themselves):
      - Target non-sustain units first (destroy the most valuable non-sustain unit).
      - If all units can sustain, sustain the cheapest unit.
    """
    if not attacker_ground:
        return attacker_ground

    cannot_sustain = [u for u in attacker_ground if not u.can_sustain]
    can_sustain = [u for u in attacker_ground if u.can_sustain]

    if cannot_sustain:
        # Destroy the most valuable unit that can't sustain
        target = max(cannot_sustain, key=lambda u: u.unit_type.destroy_priority)
        return [u for u in attacker_ground if id(u) != id(target)]
    elif can_sustain:
        # Force sustain on the cheapest unit
        target = min(can_sustain, key=lambda u: u.unit_type.destroy_priority)
        target.damaged = True
        target.sustained_this_round = True
        return attacker_ground

    return attacker_ground


def destroy_cheapest_non_fighter(units: list[Unit]) -> list[Unit]:
    """
    Assault Cannon: destroy the cheapest non-Fighter ship (no sustain allowed).
    If there are no non-Fighters, nothing happens.
    """
    non_fighters = [u for u in units if u.name != 'Fighter']
    if not non_fighters:
        return units
    target = min(non_fighters, key=lambda u: u.unit_type.destroy_priority)
    return [u for u in units if id(u) != id(target)]


def _reset_sustained_flags(units: list[Unit]) -> None:
    """Reset the sustained_this_round flag on all units at start of a new round."""
    for u in units:
        u.sustained_this_round = False


# ---------------------------------------------------------------------------
# Outcome helper
# ---------------------------------------------------------------------------

def _determine_result(attackers: list[Unit], defenders: list[Unit]) -> CombatResult:
    if attackers and not defenders:
        return CombatResult.ATTACKER_WIN
    if defenders and not attackers:
        return CombatResult.DEFENDER_WIN
    return CombatResult.DRAW


# ---------------------------------------------------------------------------
# Space combat
# ---------------------------------------------------------------------------

def simulate_space_combat(
    att_ships: list[Unit],
    def_ships: list[Unit],
    att_pds: Optional[list[Unit]] = None,
    def_pds: Optional[list[Unit]] = None,
    att_techs: Optional[Technologies] = None,
    def_techs: Optional[Technologies] = None,
) -> CombatResult:
    """
    Simulate a single space combat to conclusion (no retreats).

    Pre-combat sequence:
      1. Space Cannon Offence — both sides' PDS fire simultaneously;
         hits assigned to any ship (incl. Fighters).
         Antimass: defender's SC hits against attacker reduced by 1/die.
         Graviton: attacker's SC hits must target non-Fighters.
         Plasma Scoring: +1 extra die at best CV.
      2. Anti-Fighter Barrage — both sides' Destroyers fire simultaneously;
         hits assigned to Fighters only (no sustain).
      3. Assault Cannon — if ≥3 non-Fighter ships, destroy cheapest enemy
         non-Fighter (simultaneous, no sustain; checked after SC+AFB).
      4. Main combat rounds — both sides roll simultaneously until eliminated.
         Duranium Armour: repair 1 unit/round (checked before win condition).
    """
    att_pds = att_pds or []
    def_pds = def_pds or []
    at = att_techs or Technologies()
    dt = def_techs or Technologies()

    attackers = [copy.copy(u) for u in att_ships]
    defenders = [copy.copy(u) for u in def_ships]

    # --- Step 1: Space Cannon Offence (simultaneous) ---
    # Attacker's SC hits defenders; defender's SC hits attackers.
    # antimass on each side applies to the incoming fire against that side.
    att_sc = roll_sc_hits(att_pds, plasma_scoring=at.plasma_scoring, antimass=dt.antimass_deflectors)
    def_sc = roll_sc_hits(def_pds, plasma_scoring=dt.plasma_scoring, antimass=at.antimass_deflectors)

    # Apply Graviton for attacker's SC: must target non-Fighters in defenders
    if at.graviton_laser_system:
        defenders = assign_hits_graviton(defenders, att_sc)
    else:
        defenders = assign_hits(defenders, att_sc)

    # defender's SC hits attackers (antimass reduces die rolls if attacker has it)
    if dt.graviton_laser_system:
        attackers = assign_hits_graviton(attackers, def_sc)
    else:
        attackers = assign_hits(attackers, def_sc)

    if not attackers or not defenders:
        return _determine_result(attackers, defenders)

    # --- Step 2: Anti-Fighter Barrage (simultaneous) ---
    att_afb = sum(_roll_ability(u.effective_afb) for u in attackers if u.effective_afb)
    def_afb = sum(_roll_ability(u.effective_afb) for u in defenders if u.effective_afb)
    attackers = assign_hits_to_fighters(attackers, def_afb)
    defenders = assign_hits_to_fighters(defenders, att_afb)

    if not attackers or not defenders:
        return _determine_result(attackers, defenders)

    # --- Step 3: Assault Cannon (simultaneous) ---
    att_non_fighters = [u for u in attackers if u.name != 'Fighter']
    def_non_fighters = [u for u in defenders if u.name != 'Fighter']

    att_fires_ac = at.assault_cannon and len(att_non_fighters) >= 3
    def_fires_ac = dt.assault_cannon and len(def_non_fighters) >= 3

    # Simultaneous: compute targets before applying either result
    if att_fires_ac:
        defenders = destroy_cheapest_non_fighter(defenders)
    if def_fires_ac:
        attackers = destroy_cheapest_non_fighter(attackers)

    if not attackers or not defenders:
        return _determine_result(attackers, defenders)

    # --- Main combat rounds ---
    while attackers and defenders:
        _reset_suspended_flags = _reset_sustained_flags  # alias for clarity
        _reset_suspended_flags(attackers)
        _reset_suspended_flags(defenders)

        att_hits = sum(u.roll_combat() for u in attackers)
        def_hits = sum(u.roll_combat() for u in defenders)
        attackers = assign_hits(attackers, def_hits)
        defenders = assign_hits(defenders, att_hits)

        # Duranium Armour: repair before checking win condition
        if at.duranium_armour:
            apply_duranium_armour(attackers)
        if dt.duranium_armour:
            apply_duranium_armour(defenders)

    return _determine_result(attackers, defenders)


# ---------------------------------------------------------------------------
# Ground combat
# ---------------------------------------------------------------------------

def simulate_ground_combat(
    att_ground: list[Unit],
    def_ground: list[Unit],
    att_ships: Optional[list[Unit]] = None,
    def_pds: Optional[list[Unit]] = None,
    att_techs: Optional[Technologies] = None,
    def_techs: Optional[Technologies] = None,
) -> CombatResult:
    """
    Simulate a single ground combat to conclusion (no retreats).

    Pre-combat sequence:
      1. Bombardment — attacker's ships bombard defender's ground forces.
         Skipped if defender has PDS (Planetary Shield).
         Plasma Scoring: +1 extra bombardment die at best CV.
         X-89 Bacterial Weapon: double bombardment hits.
      2. Space Cannon Defence — defender's PDS fires at attacker's ground forces.
         Only fires if defender has PDS.
         Plasma Scoring: +1 extra SC die at best CV.
         Antimass: attacker's Antimass reduces incoming SC die rolls by 1.
      3. Magen Defence Grid — if defender has this tech AND a PDS structure,
         score 1 free hit against attacker's ground forces (after SC Defence).
      4. Main combat rounds:
         X-89 (attacker): double all hits against defending ground forces.
         X-89 (defender): double all hits against attacking ground forces.
         Duranium Armour: repair 1 unit/round (before win condition check).
    """
    att_ships = att_ships or []
    def_pds = def_pds or []
    at = att_techs or Technologies()
    dt = def_techs or Technologies()

    attackers = [copy.copy(u) for u in att_ground]
    defenders = [copy.copy(u) for u in def_ground]

    defender_has_pds = len(def_pds) > 0

    # --- Step 1: Bombardment (blocked by Planetary Shield) ---
    if not defender_has_pds and att_ships:
        bomb_hits = roll_bombardment_hits(att_ships, plasma_scoring=at.plasma_scoring, x89=at.x89_bacterial_weapon)
        defenders = assign_hits(defenders, bomb_hits)
        if not defenders:
            return _determine_result(attackers, defenders)

    # --- Step 2: Space Cannon Defence (defender only) ---
    if defender_has_pds:
        sc_def_hits = roll_sc_hits(
            def_pds,
            plasma_scoring=dt.plasma_scoring,
            antimass=at.antimass_deflectors,
        )
        attackers = assign_hits(attackers, sc_def_hits)
        if not attackers:
            return _determine_result(attackers, defenders)

    # --- Step 3: Magen Defence Grid (requires a PDS structure to be present) ---
    if dt.magen_defence_grid and defender_has_pds:
        attackers = apply_magen(attackers)
        if not attackers:
            return _determine_result(attackers, defenders)

    # --- Main combat rounds ---
    while attackers and defenders:
        _reset_sustained_flags(attackers)
        _reset_sustained_flags(defenders)

        att_hits = sum(u.roll_combat() for u in attackers)
        def_hits = sum(u.roll_combat() for u in defenders)

        # X-89 doubles all hits produced by ground forces
        if at.x89_bacterial_weapon:
            att_hits *= 2
        if dt.x89_bacterial_weapon:
            def_hits *= 2

        attackers = assign_hits(attackers, def_hits)
        defenders = assign_hits(defenders, att_hits)

        # Duranium Armour: repair before checking win condition
        if at.duranium_armour:
            apply_duranium_armour(attackers)
        if dt.duranium_armour:
            apply_duranium_armour(defenders)

    return _determine_result(attackers, defenders)
