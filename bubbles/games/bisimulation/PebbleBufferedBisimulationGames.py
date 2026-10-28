"""Placeholder for a future pebble-buffered bisimulation game."""

from wofa import FiniteAutomata

from .BisimulationGames import BisimulationGames


class PebbleBufferedBisimulationGames(BisimulationGames):
    """Scaffold for a future pebble-buffered bisimulation game.

    The formal project currently defines the buffered bisimulation game and
    the pebble simulation game, but not a finalized pebble-buffered
    bisimulation game. The implementation is therefore intentionally left as
    a placeholder.
    """

    def __init__(
            self,
            automaton0: FiniteAutomata,
            automaton1: FiniteAutomata,
            remove_dead_states: bool = True,
    ):
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            remove_dead_states=remove_dead_states,
        )

    def solve(self):
        """Solve the future pebble-buffered bisimulation game."""
        # TODO: Define and implement the pebble-buffered bisimulation game.
        raise NotImplementedError(
            "Pebble-buffered bisimulation is not implemented yet."
        )
