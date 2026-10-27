from abc import ABC, abstractmethod
from typing import Callable

from wofa import FiniteAutomata

from .TwoWaySetMap import TwoWaySetMap


class BisimulationGames(ABC):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata):
        self.automatons = {0: automaton0, 1: automaton1}
        self.__prepare_automatons()

        # Precompute the sets of final, non-final, and initial states for both automata to speed up the game solving.
        self.states = {index: set(range(self.automatons[index].get_number_of_states())) for index in range(2)}
        self.finals = {index: self.automatons[index].get_finals() for index in range(2)}
        self.non_finals = {
            index: {
                state
                for state in self.states[index]
                if state not in self.finals[index]
            }
            for index in range(2)
        }
        self.initials = {index: self.automatons[index].get_initials() for index in range(2)}

    def __prepare_automatons(self):
        """Normalize both input automata to the game assumptions.

        Before the attractor construction starts, each automaton is prepared so
        that the game operates on a clean and uniform representation:

        1. remove transitions whose labels are not part of the common alphabet,
        2. remove unreachable states,
        3. normalize the set of initial states to a single initial state,
        4. totalize the automaton by adding a dead state if some transition is
           missing.

        The last step is important because the backward game construction
        assumes that player-II response moves are always represented by regular
        successors in the automaton, rather than by an implicit "no move"
        situation.
        """
        for i in range(2):
            automaton = self.automatons[i]

            # Keep only transitions over the agreed alphabet of the game. This
            # call can rewrite the automaton, so skip it when all transition
            # labels are already part of the current alphabet.
            if any(transition[1] not in FiniteAutomata.alphabet for transition in automaton.get_transitions()):
                automaton.remove_non_alphabet_transitions()

            # States that cannot be reached from the start configuration never
            # matter for the game graph. Avoid calling the shrinking routine
            # again once every state is already reachable.
            if automaton.reachable() != set(range(automaton.get_number_of_states())):
                automaton.remove_unreachable_states()

            # If the automaton has multiple initials, merge them into one
            # equivalent start state. If it already has a single initial state,
            # leave it untouched so repeated game construction is idempotent.
            if len(automaton.get_initials()) != 1:
                automaton.normalize_initial_states()

                # Normalizing multiple initial states can make old helper or
                # start states unreachable. Remove them immediately so the
                # prepared automaton is stable for later game constructions.
                if automaton.reachable() != set(range(automaton.get_number_of_states())):
                    automaton.remove_unreachable_states()

            # If some transition is missing, add a dead state to totalize the
            # automaton. Missing player-II responses are then represented by a
            # transition into this dead sink instead of by undefined behavior.
            if not self.__is_total(automaton):
                automaton.add_dead_state()

    @staticmethod
    def __is_total(automaton: FiniteAutomata) -> bool:
        """Return whether every state has a successor for every alphabet letter."""
        return all(
            automaton.get_successors(s=state, a=letter)
            for letter in FiniteAutomata.alphabet
            for state in range(automaton.get_number_of_states())
        )

    @abstractmethod
    def solve(self):
        pass

    @staticmethod
    def propagate_new_attractor_nodes(
            nodes_to_process: list[tuple],
            all_attractor_nodes: set[tuple],
            new_attractor_nodes: set[tuple],
            seen_player2_nodes_not_in_attractor: TwoWaySetMap,
            check_initial: Callable[..., bool],
    ) -> bool:
        """Propagate the player-I attractor through stored player-II obligations.

        For player-II nodes we must realize the universal predecessor rule:
        a player-II node enters the attractor iff all of its successors already
        belong to the attractor.

        The map `seen_player2_nodes_not_in_attractor` stores, for every
        player-II node not yet in the attractor, the successors that are still
        outside the attractor. Whenever one of these successors enters the
        attractor, this method removes it from the pending obligations and adds
        newly discharged player-II nodes to the attractor.
        """
        while nodes_to_process:
            propagated_node = nodes_to_process.pop()

            if not seen_player2_nodes_not_in_attractor.has_value(propagated_node):
                continue

            for new_player2_attractor_node in seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    propagated_node):

                if new_player2_attractor_node in all_attractor_nodes:
                    continue

                if check_initial(*new_player2_attractor_node):
                    return True

                all_attractor_nodes.add(new_player2_attractor_node)
                new_attractor_nodes.add(new_player2_attractor_node)
                nodes_to_process.append(new_player2_attractor_node)

        return False

    def get_automatons(self):
        return self.automatons
