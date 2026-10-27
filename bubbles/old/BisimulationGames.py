"""Legacy base class preserving the former totalized-game semantics."""

from wofa import FiniteAutomata

from ..games.BisimulationGames import BisimulationGames as SharedBisimulationGames


class BisimulationGames(SharedBisimulationGames):
    """Compatibility base class for the old game implementations."""

    def _prepare_automatons(self):
        """Prepare automata and totalize them for the legacy games."""
        super()._prepare_automatons()

        for automaton in self.automatons.values():
            if not self._is_total(automaton):
                automaton.add_dead_state()
