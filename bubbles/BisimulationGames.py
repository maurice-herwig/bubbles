from abc import ABC, abstractmethod

from wofa import FiniteAutomata


class BisimulationGames(ABC):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata):
        self.automatons = {0: automaton0, 1: automaton1}
        self.__prepare_automatons()

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

    def get_automatons(self):
        return self.automatons
