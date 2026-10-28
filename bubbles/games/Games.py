"""Common infrastructure shared by all game implementations."""

from abc import ABC, abstractmethod

from wofa import FiniteAutomata


class Games(ABC):
    """Base class for games played on two finite automata.

    This class contains only infrastructure common to different game
    families. Concrete subclasses define the actual game rules in ``solve``.
    """

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata):
        """Initialize a game on two finite automata."""
        self.automatons = {0: automaton0, 1: automaton1}
        self._prepare_automatons()

        self.states = {
            index: set(range(self.automatons[index].get_number_of_states()))
            for index in range(2)
        }
        self.finals = {
            index: self.automatons[index].get_finals()
            for index in range(2)
        }
        self.non_finals = {
            index: {
                state
                for state in self.states[index]
                if state not in self.finals[index]
            }
            for index in range(2)
        }
        self.initials = {
            index: self.automatons[index].get_initials()
            for index in range(2)
        }

    def _prepare_automatons(self):
        """Normalize both input automata to the common game assumptions.

        Transitions outside the configured alphabet, unreachable states, and
        unproductive states are removed. Multiple initial states are merged;
        empty-language automata are replaced by WoFa's canonical empty NFA.
        Missing transitions remain missing because concrete games may
        interpret them as an immediate loss for the responding player.
        """
        for index in range(2):
            automaton = self.automatons[index]

            if any(
                    transition[1] not in FiniteAutomata.alphabet
                    for transition in automaton.get_transitions()
            ):
                automaton.remove_non_alphabet_transitions()

            if automaton.reachable() != set(range(automaton.get_number_of_states())):
                automaton.remove_unreachable_states()

            productive_states = automaton.productive()
            if not automaton.get_initials() & productive_states:
                self.automatons[index] = FiniteAutomata.empty_nfa()
                continue

            if productive_states != set(range(automaton.get_number_of_states())):
                automaton.remove_unproductive_states()

            if len(automaton.get_initials()) != 1:
                automaton.normalize_initial_states()
                if automaton.reachable() != set(range(automaton.get_number_of_states())):
                    automaton.remove_unreachable_states()

    @staticmethod
    def _is_total(automaton: FiniteAutomata) -> bool:
        """Return whether every state has a successor for every letter."""
        return all(
            automaton.get_successors(s=state, a=letter)
            for letter in FiniteAutomata.alphabet
            for state in range(automaton.get_number_of_states())
        )

    @abstractmethod
    def solve(self):
        """Solve the concrete game."""
        pass

    def get_automatons(self):
        """Return the prepared automata used by the game."""
        return self.automatons
