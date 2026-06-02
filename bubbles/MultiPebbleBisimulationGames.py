from wofa import FiniteAutomata

from .BisimulationGames import BisimulationGames
from .TwoWaySetMap import TwoWaySetMap


class MultiPebbleBisimulationGames(BisimulationGames):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata, pebbles: int):
        """Create the game instance for two NFA and k pebbles."""
        assert pebbles >= 1, "The number of pebbles must be at least 1."
        self.pebbles = pebbles
        super().__init__(automaton0, automaton1)

    def set_pebbles(self, pebbles: int):
        """Set the number of pebbles for the game."""
        assert pebbles >= 1, "The number of pebbles must be at least 1."
        self.pebbles = pebbles

    def solve(self):
        # TODO
        pass
