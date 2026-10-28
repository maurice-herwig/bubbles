"""Buffered correction simulation games."""

from ..simulation.BufferedSimulationGames import BufferedSimulationGames
from .CorrectionGames import CorrectionGames


class BufferedCorrectionSimulationGames(CorrectionGames):
    """Search for a bounded correction making two NFAs buffered equivalent."""

    def __init__(
            self,
            automaton0,
            automaton1,
            buffer_size: int,
            correction_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a buffered correction simulation game."""
        self.buffer_size = buffer_size
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            correction_size=correction_size,
            remove_dead_states=remove_dead_states,
        )

    def _solve_corrected_automaton(self, automaton0) -> bool:
        """Solve the normal buffered simulation game for ``automaton0``."""
        game = BufferedSimulationGames(
            automaton0=automaton0,
            automaton1=self._copy_automaton(self._base_automaton1),
            buffer_size=self.buffer_size,
            remove_dead_states=self.remove_dead_states,
        )
        return game.solve()[0]
