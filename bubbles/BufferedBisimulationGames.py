from wofa import FiniteAutomata

from .BisimulationGames import BisimulationGames


class BufferedBisimulationGames(BisimulationGames):

    def __init__(self, automaton1: FiniteAutomata, automaton2: FiniteAutomata, buffer_size: int):
        super().__init__(automaton1, automaton2)
        self.buffer_size = buffer_size

    def solve(self):
        raise NotImplementedError("BufferedBisimulationGames.solve() is not implemented yet.")

