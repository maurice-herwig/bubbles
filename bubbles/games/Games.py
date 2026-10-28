"""Common infrastructure shared by all game implementations."""

from abc import ABC, abstractmethod
from functools import cache

from wofa import FiniteAutomata


class Games(ABC):
    """Base class for games played on two finite automata.

    This class contains only infrastructure common to different game
    families. Concrete subclasses define the actual game rules in ``solve``.
    """

    def __init__(
            self,
            automaton0: FiniteAutomata,
            automaton1: FiniteAutomata,
            remove_dead_states: bool = True,
    ):
        """Initialize a game on two finite automata.

        Args:
            remove_dead_states: Whether to remove states from which no final
                state is reachable during automaton preparation.
        """
        self.remove_dead_states = remove_dead_states
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

        Transitions outside the configured alphabet and unreachable states are
        removed. If ``remove_dead_states`` is enabled, unproductive states are
        removed as well and empty-language automata are replaced by WoFa's
        canonical empty NFA. Multiple initial states are merged. Missing
        transitions remain missing because concrete games may interpret them
        as an immediate loss for the responding player.
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

            if self.remove_dead_states:
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

    @cache
    def _successors(
            self,
            automaton_index: int,
            state: int,
            letter: str,
    ) -> frozenset[int]:
        """Return and cache the successors of a state for one letter."""
        return frozenset(
            self.automatons[automaton_index].get_successors(
                s=state,
                a=letter,
            )
        )

    @cache
    def _predecessors(
            self,
            automaton_index: int,
            state: int,
            letter: str,
    ) -> frozenset[int]:
        """Return and cache the predecessors of a state for one letter."""
        return frozenset(
            self.automatons[automaton_index].get_predecessors(
                s=state,
                a=letter,
            )
        )

    @cache
    def _reachable_states(
            self,
            automaton_index: int,
            state: int,
            word: str,
    ) -> frozenset[int]:
        """Return and cache all states reachable after reading ``word``."""
        reachable = {state}
        for letter in word:
            reachable = {
                successor
                for current_state in reachable
                for successor in self._successors(
                    automaton_index,
                    current_state,
                    letter,
                )
            }
        return frozenset(reachable)

    @cache
    def _reverse_reachable_states(
            self,
            automaton_index: int,
            target_state: int,
            word: str,
    ) -> frozenset[int]:
        """Return and cache states that can read ``word`` to a target state."""
        possible_predecessors = {target_state}
        for letter in reversed(word):
            possible_predecessors = {
                predecessor
                for current_state in possible_predecessors
                for predecessor in self._predecessors(
                    automaton_index,
                    current_state,
                    letter,
                )
            }
        return frozenset(possible_predecessors)

    @abstractmethod
    def solve(self):
        """Solve the concrete game."""
        pass

    def get_automatons(self):
        """Return the prepared automata used by the game."""
        return self.automatons
