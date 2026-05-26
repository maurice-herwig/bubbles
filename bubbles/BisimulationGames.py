from abc import ABC, abstractmethod

from wofa import FiniteAutomata


class BisimulationGames(ABC):

    def __init__(self, automaton1: FiniteAutomata, automaton2: FiniteAutomata):
        self.automaton1 = automaton1
        self.automaton2 = automaton2

    @abstractmethod
    def solve(self):
        pass
