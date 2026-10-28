"""Pebble correction simulation games."""

from ..simulation.PebbleSimulationGames import PebbleSimulationGames
from .CorrectionGames import CorrectionGames


class PebbleCorrectionSimulationGames(CorrectionGames):
    """Search for a bounded correction making two NFAs pebble equivalent."""

    def __init__(
            self,
            automaton0,
            automaton1,
            pebble_size: int,
            correction_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a pebble correction simulation game."""
        self.pebble_size = pebble_size
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            correction_size=correction_size,
            remove_dead_states=remove_dead_states,
        )

    def _solve_corrected_automaton(self, automaton0) -> bool:
        """Solve the normal pebble simulation game for ``automaton0``."""
        game = PebbleSimulationGames(
            automaton0=automaton0,
            automaton1=self._copy_automaton(self._base_automaton1),
            pebble_size=self.pebble_size,
            remove_dead_states=self.remove_dead_states,
        )
        return game.solve()[0]
