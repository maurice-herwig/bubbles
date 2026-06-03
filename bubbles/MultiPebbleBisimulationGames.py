from wofa import FiniteAutomata
from itertools import combinations

from .BisimulationGames import BisimulationGames
from .TwoWaySetMap import TwoWaySetMap

CHOICE = "CHOICE"
MOVE = "MOVE"
COLL = "COLL"
MOVES = {CHOICE: 0, MOVE: 1, COLL: 2}


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
        all_attractor_nodes = set()

        def check_initial(parameter0: int | frozenset, parameter1: int | frozenset, move_type: int) -> bool:
            """Return whether the given node is the initial game position.

            According to the game definition, the initial node is

                (q0I, {q1I}, choice)

            and therefore always has the orientation (single A0 state,
            pebble-set in A1, choice). The symmetric orientation (M0, q1, m)
            is never the initial node.
            """
            return move_type == MOVES[CHOICE] \
                and isinstance(parameter0, int) \
                and parameter0 in self.initials[0] \
                and isinstance(parameter1, frozenset) \
                and (len(frozenset(parameter1)) == 1) \
                and (next(iter(parameter1)) in self.initials[1])

        def new_player_1_node(parameter0, parameter1, move_type):
            new_player_1_node = (parameter0, parameter1, move_type)

            if new_player_1_node in all_attractor_nodes:
                return False

            if check_initial(*new_player_1_node):
                return True

            all_attractor_nodes.add(new_player_1_node)
            new_attractor_nodes.add(new_player_1_node)

            # TODO return propagate_new_attractor_nodes([new_node])

        # TODO überprüfen, ob beim starten wie aktuell minimal ein pebble gesetzt sein muss oder auch 0 gehen.
        for final_state in self.finals[0]:
            for non_finals_pebbles in [set(c) for r in range(1, min(len(self.non_finals[1]), self.pebbles) + 1)
                                       for c in combinations(self.non_finals[1], r)]:
                for i in range(2):
                    new_node = (final_state, frozenset(non_finals_pebbles), i)

                    if check_initial(*new_node):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                    all_attractor_nodes.add(new_node)

        for non_final_state in self.non_finals[0]:
            for finals_pebbles in [set(c) for r in range(1, min(len(self.finals[1]), self.pebbles) + 1)
                                   for c in combinations(self.finals[1], r)]:
                for i in range(2):
                    new_node = (non_final_state, frozenset(finals_pebbles), i)

                    if check_initial(*new_node):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                    all_attractor_nodes.add(new_node)

        for final_state in self.finals[1]:
            for non_finals_pebbles in [set(c) for r in range(1, min(len(self.non_finals[0]), self.pebbles) + 1)
                                       for c in combinations(self.non_finals[0], r)]:
                for i in range(2):
                    new_node = (frozenset(non_finals_pebbles), final_state, i)

                    if check_initial(*new_node):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                    all_attractor_nodes.add(new_node)

        for non_final_state in self.non_finals[1]:
            for finals_pebbles in [set(c) for r in range(1, min(len(self.finals[0]), self.pebbles) + 1)
                                   for c in combinations(self.finals[0], r)]:
                for i in range(2):
                    new_node = (frozenset(finals_pebbles), non_final_state, i)

                    if check_initial(*new_node):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                    all_attractor_nodes.add(new_node)

        # This map stores open player-II proof obligations:
        #
        #   player-II node -> set of successors that are still outside Attr_I(F)
        #
        # It implements the universal predecessor check efficiently.
        seen_player2_nodes_not_in_attractor = TwoWaySetMap()
        last_added_attractor_nodes = all_attractor_nodes.copy()
        new_attractor_nodes = set()

        # Main backward fixpoint iteration.
        #
        # `last_added_attractor_nodes` acts as the current frontier. For every
        # node that just entered the attractor, we compute its backward
        # predecessors according to the rules from the paper.
        while last_added_attractor_nodes:

            for parameter0, parameter1, move_type in last_added_attractor_nodes:
                if isinstance(parameter0, int):
                    q = parameter0
                    M = parameter1
                    i = 0
                else:
                    q = parameter1
                    M = parameter0
                    i = 1

                if move_type == MOVES[CHOICE]:
                    pass

                elif move_type == MOVES[MOVE]:
                    # TODO
                    pass

                elif move_type == MOVES[COLL]:
                    if new_player_1_node(parameter0=parameter0, parameter1=parameter1, move_type=MOVES[CHOICE]):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

            last_added_attractor_nodes = new_attractor_nodes.copy()
            new_attractor_nodes = set()

        # If the initial node never entered the player-I attractor, then player
        # II can avoid F forever and therefore has a winning strategy.
        return True, f'The automatas are {self.pebbles}-pebble bisimilar'
