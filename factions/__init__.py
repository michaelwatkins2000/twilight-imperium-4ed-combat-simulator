"""
Phase 4 — Faction-specific units, abilities, technologies, and agents.

Each faction is implemented in its own module (e.g. factions/sardakk.py) and
registers itself by calling register_faction() at import time.  Agents are
registered via register_agent() in the same module.

Usage in combat/simulator:
    from factions import get_faction, FactionAbilities, get_agent, AgentAbilities
    faction = get_faction("sardakk")   # FactionAbilities instance or None
    agent  = get_agent("sol")          # AgentAbilities instance or None

FactionAbilities hooks (override in subclasses as needed):
    pre_space_combat(own, enemy)          → (own, enemy)   before SC Offence
    post_afb_space(own, enemy)            → (own, enemy)   after AFB, before Assault Cannon
    pre_ground_rounds(own, enemy)         → (own, enemy)   after Magen, before main rounds
    post_roll_ground(own_hits, enemy_hits)→ int            modify own hits after rolling
    end_of_round_space(own, enemy)        → (own, enemy)   end of each space combat round
    end_of_round_ground(own, enemy)       → (own, enemy)   end of each ground combat round
    get_combat_roll_modifier(unit, fleet) → int            per-unit roll modifier

AgentAbilities hooks (override in subclasses as needed):
    start_of_space_round(own, enemy, round_num) → (own, enemy)
    extra_hits_space_round(own, enemy, round_num) → int
    start_of_ground_round(own, enemy, round_num) → (own, enemy)
    extra_hits_ground_round(own, enemy, round_num) → int
    Agents are single-use; by convention implementations gate on round_num == 1.

Unit injection (set in faction __init__):
    flagship        UnitType accessible as "Flagship" in fleet parser
    mech            UnitType accessible as "Mech" in fleet parser
    unit_overrides  dict[str, UnitType] — base unit name → replacement
                    e.g. {"Dreadnought": sardakk_dreadnought}

Combat modifier:
    combat_roll_modifier    int baseline for get_combat_roll_modifier
    get_combat_roll_modifier(unit, own_fleet)
        Override for abilities that give different bonuses to different units
        (e.g. C'Morran N'orr: +1 to all OTHER ships in the fleet).

Faction technologies:
    faction_tech_aliases  dict[str, str] — normalised alias → field name
                          e.g. {"valkyrie": "valkyrie_particle_weave"}
    active_faction_techs  set[str] of activated field names (set by main.py)
"""

from __future__ import annotations

import copy
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from units import UnitType
    from combat import Unit


class FactionAbilities:
    """
    Base class for faction combat abilities. All hooks are no-ops by default.
    Subclass and override only what the faction needs.
    """

    name: str = "Generic"
    flagship: Optional['UnitType'] = None
    mech: Optional['UnitType'] = None

    # Added to each main-combat die result (positive = advantage).
    # Override get_combat_roll_modifier() for per-unit variation.
    combat_roll_modifier: int = 0

    def __init__(self) -> None:
        self.unit_overrides: dict[str, 'UnitType'] = {}
        # alias (normalised) → field name on this object
        self.faction_tech_aliases: dict[str, str] = {}
        # field names of currently active faction techs
        self.active_faction_techs: set[str] = set()

    # ------------------------------------------------------------------
    # Per-unit roll modifier
    # ------------------------------------------------------------------

    def get_combat_roll_modifier(self, unit: 'Unit', own_fleet: list['Unit']) -> int:
        """
        Return the combat roll modifier for a given unit.
        Override when different units in the same fleet get different bonuses
        (e.g. C'Morran N'orr's bonus only applies to OTHER ships).
        """
        return self.combat_roll_modifier

    # ------------------------------------------------------------------
    # Hooks — return (own_fleet, enemy_fleet) after any modifications.
    # The engine passes mutable lists; the hook may mutate or replace them.
    # ------------------------------------------------------------------

    def pre_space_combat(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called before Space Cannon Offence. e.g. Mentak Ambush."""
        return own, enemy

    def post_afb_space(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called after AFB, before Assault Cannon."""
        return own, enemy

    def pre_ground_rounds(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called after Magen, before main ground combat rounds. e.g. L1Z1X Harrow."""
        return own, enemy

    def post_roll_ground(self, own_hits: int, enemy_hits: int) -> int:
        """
        Called after both sides roll in a ground combat round, before hit assignment.
        Both sides receive the RAW (pre-modification) enemy hit count so that
        simultaneous effects resolve correctly.
        Returns the (possibly modified) own_hits value.
        e.g. Valkyrie Particle Weave: +1 if enemy produced ≥1 hit.
        """
        return own_hits

    def end_of_round_space(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called after hits are assigned in a space combat round, before Duranium."""
        return own, enemy

    def end_of_round_ground(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
    ) -> tuple[list['Unit'], list['Unit']]:
        """
        Called after hits are assigned in a ground combat round, before Duranium.
        e.g. Valkyrie Exoskeleton: produce 1 hit when the Mech sustains.
        """
        return own, enemy


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, FactionAbilities] = {}


def _normalize_faction(name: str) -> str:
    return name.lower().replace(' ', '').replace("'", '').replace('_', '').replace('-', '')


def register_faction(faction: FactionAbilities) -> None:
    """
    Register a faction instance so it can be retrieved by name or any alias.
    Automatically registers a short alias: the first word of the name, skipping
    a leading 'The' (e.g. "The Arborec" → "arborec", "Sardakk N'orr" → "sardakk").
    Factions may provide additional aliases via their `name_aliases` attribute.
    """
    key = _normalize_faction(faction.name)
    _REGISTRY[key] = faction
    # Short alias: skip a leading "the"
    words = faction.name.split()
    short_word = words[1] if words[0].lower() == 'the' and len(words) > 1 else words[0]
    first_word = _normalize_faction(short_word)
    if first_word != key:
        _REGISTRY[first_word] = faction
    # Any extra aliases the faction declares
    for alias in getattr(faction, 'name_aliases', []):
        _REGISTRY[_normalize_faction(alias)] = faction


def get_faction(name: str) -> Optional[FactionAbilities]:
    """
    Look up a faction by name and return a COPY so the caller can activate
    faction techs without mutating the registered singleton.
    Returns None if no faction matches.
    """
    singleton = _REGISTRY.get(_normalize_faction(name))
    if singleton is None:
        return None
    instance = copy.copy(singleton)
    instance.active_faction_techs = set()   # fresh set for this run
    return instance


def list_factions() -> list[str]:
    """Return a sorted list of all registered faction names (deduplicated)."""
    return sorted({f.name for f in _REGISTRY.values()})


def get_all_factions() -> list['FactionAbilities']:
    """Return unique registered faction objects sorted by name."""
    seen: set[int] = set()
    result: list[FactionAbilities] = []
    for faction in _REGISTRY.values():
        if id(faction) not in seen:
            seen.add(id(faction))
            result.append(faction)
    return sorted(result, key=lambda f: f.name)


def normalize_tech_alias(token: str) -> str:
    """Normalise a faction-tech token for alias lookup."""
    return token.lower().replace(' ', '').replace('_', '').replace('-', '')


# ---------------------------------------------------------------------------
# Agent system
# ---------------------------------------------------------------------------

class AgentAbilities:
    """
    Base class for faction agent abilities. All hooks are no-ops by default.
    Subclass and override only what the agent needs.

    Agents are single-use — by convention, implementations gate their effect
    on round_num == 1 (optimal play: always use on the first round).

    extra_hits_* hooks return additional hits added to the rolling side's raw
    hit count (before X-89 doubling, after unit rolls).
    """

    name: str = "Generic Agent"
    faction_source: str = ""   # display name of the faction that owns this agent

    def start_of_space_round(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
        round_num: int,
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called at the start of each space combat round before rolling."""
        return own, enemy

    def extra_hits_space_round(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
        round_num: int,
    ) -> int:
        """Extra hits contributed by this agent to own side in a space round."""
        return 0

    def start_of_ground_round(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
        round_num: int,
    ) -> tuple[list['Unit'], list['Unit']]:
        """Called at the start of each ground combat round before rolling."""
        return own, enemy

    def extra_hits_ground_round(
        self,
        own: list['Unit'],
        enemy: list['Unit'],
        round_num: int,
    ) -> int:
        """Extra hits contributed by this agent to own side in a ground round."""
        return 0


_AGENT_REGISTRY: dict[str, AgentAbilities] = {}


def register_agent(agent: AgentAbilities) -> None:
    """
    Register an agent so it can be retrieved by its faction_source name or
    the short alias (first non-'The' word, same convention as register_faction).
    Additional aliases may be declared via the agent's `name_aliases` attribute.
    """
    key = _normalize_faction(agent.faction_source)
    _AGENT_REGISTRY[key] = agent
    words = agent.faction_source.split()
    short_word = words[1] if words[0].lower() == 'the' and len(words) > 1 else words[0]
    short = _normalize_faction(short_word)
    if short != key:
        _AGENT_REGISTRY[short] = agent
    # Mirror the owning faction's name_aliases into the agent registry,
    # so any alias that works for --att-faction also works for --att-agents.
    faction = _REGISTRY.get(key)
    if faction is not None:
        for alias in getattr(faction, 'name_aliases', []):
            _AGENT_REGISTRY[_normalize_faction(alias)] = agent


def get_agent(name: str) -> Optional[AgentAbilities]:
    """
    Look up an agent by faction name. Returns a shallow copy so each
    simulation run gets a fresh instance. Returns None if not found.
    """
    singleton = _AGENT_REGISTRY.get(_normalize_faction(name))
    return copy.copy(singleton) if singleton is not None else None


def list_agents() -> list[str]:
    """Return a sorted deduplicated list of faction_source names with agents."""
    return sorted({a.faction_source for a in _AGENT_REGISTRY.values()})


def _import_all() -> None:
    """Import all faction modules so they self-register."""
    import importlib
    import pkgutil
    import factions as _pkg

    for module_info in pkgutil.iter_modules(_pkg.__path__):
        if module_info.name != '__init__':
            importlib.import_module(f'factions.{module_info.name}')


_import_all()
