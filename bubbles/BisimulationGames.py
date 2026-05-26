from abc import ABC, abstractmethod

from wofa import FiniteAutomata


class BisimulationGames(ABC):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata):
        self.automatons = {0: automaton0, 1: automaton1}

    @abstractmethod
    def solve(self):
        pass
