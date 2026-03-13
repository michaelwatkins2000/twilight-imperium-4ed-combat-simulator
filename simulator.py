from collections import Counter
from typing import Optional

from combat import CombatResult, Unit, simulate_space_combat, simulate_ground_combat
from technologies import Technologies
from factions import FactionAbilities


def run_simulation(
    combat_type: str,
    att_main: list[Unit],
    def_main: list[Unit],
    *,
    att_pds: Optional[list[Unit]] = None,
    att_ships: Optional[list[Unit]] = None,
    def_pds: Optional[list[Unit]] = None,
    att_techs: Optional[Technologies] = None,
    def_techs: Optional[Technologies] = None,
    att_faction: Optional[FactionAbilities] = None,
    def_faction: Optional[FactionAbilities] = None,
    n_simulations: int = 10_000,
) -> dict:
    """
    Run n_simulations independent combats and return win probabilities.

    combat_type  : 'space' or 'ground'
    att_main     : attacker's main combat units (ships / ground forces)
    def_main     : defender's main combat units
    att_pds      : attacker's PDS — Space Cannon Offence (space combat only)
    att_ships    : attacker's ships in orbit — Bombardment (ground combat only)
    def_pds      : defender's PDS — Space Cannon Offence (space) or
                   Space Cannon Defence + Planetary Shield (ground)
    att_techs    : attacker's active generic technologies
    def_techs    : defender's active generic technologies
    att_faction  : attacker's faction abilities
    def_faction  : defender's faction abilities
    """
    att_pds = att_pds or []
    att_ships = att_ships or []
    def_pds = def_pds or []
    att_techs = att_techs or Technologies()
    def_techs = def_techs or Technologies()

    results: Counter = Counter()

    for _ in range(n_simulations):
        if combat_type == 'space':
            result = simulate_space_combat(
                att_main, def_main, att_pds, def_pds,
                att_techs, def_techs, att_faction, def_faction,
            )
        else:
            result = simulate_ground_combat(
                att_main, def_main, att_ships, def_pds,
                att_techs, def_techs, att_faction, def_faction,
            )
        results[result] += 1

    return {
        'attacker_win': results[CombatResult.ATTACKER_WIN] / n_simulations * 100,
        'defender_win': results[CombatResult.DEFENDER_WIN] / n_simulations * 100,
        'draw':         results[CombatResult.DRAW]         / n_simulations * 100,
        'n_simulations': n_simulations,
    }
