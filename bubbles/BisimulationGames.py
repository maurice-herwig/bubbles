from abc import ABC, abstractmethod
from typing import Callable

from wofa import FiniteAutomata

from .TwoWaySetMap import TwoWaySetMap


class BisimulationGames(ABC):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata):
        self.automatons = {0: automaton0, 1: automaton1}
        self.__prepare_automatons()

        # Precompute the sets of final, non-final, and initial states for both automata to speed up the game solving.
        self.finals = {index: self.automatons[index].get_finals() for index in range(2)}
        self.non_finals = {
            index: {
                state
                for state in range(self.automatons[index].get_number_of_states())
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
            # Keep only transitions over the agreed alphabet of the game.
            self.automatons[i].remove_non_alphabet_transitions()

            # States that cannot be reached from the start configuration never
            # matter for the game graph.
            self.automatons[i].remove_unreachable_states()

            # If the automaton has multiple initials, we merge them into one equivalent start state.
            self.automatons[i].normalize_initial_states()

            # Check whether the automaton is already total, i.e. whether every
            # state has at least one outgoing transition for every letter.
            total = True
            for letter in FiniteAutomata.alphabet:
                for state in range(self.automatons[i].get_number_of_states()):
                    if not self.automatons[i].get_successors(s=state, a=letter):
                        total = False
                        break
                if not total:
                    break

            # If some transition is missing, add a dead state to totalize the
            # automaton. Missing player-II responses are then represented by a
            # transition into this dead sink instead of by undefined behavior.
            if not total:
                self.automatons[i].add_dead_state()

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
