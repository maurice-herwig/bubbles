from wofa import FiniteAutomata
from itertools import combinations, product

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
            """Add a player-I predecessor node to the attractor.

            In the attractor computation, player-I nodes are existential:
            a player-I node enters the attractor as soon as one of its
            successors is already in the attractor. This helper adds such a
            predecessor, checks whether it is the initial node, and then
            propagates the newly added attractor node through pending player-II
            obligations.
            """
            new_player_1_node = (parameter0, parameter1, move_type)

            if new_player_1_node in all_attractor_nodes:
                return False

            if check_initial(*new_player_1_node):
                return True

            all_attractor_nodes.add(new_player_1_node)
            new_attractor_nodes.add(new_player_1_node)

            return self.propagate_new_attractor_nodes(
                nodes_to_process=[new_player_1_node],
                all_attractor_nodes=all_attractor_nodes,
                new_attractor_nodes=new_attractor_nodes,
                seen_player2_nodes_not_in_attractor=seen_player2_nodes_not_in_attractor,
                check_initial=check_initial,
            )

        def new_player_2_node(parameter0, parameter1, move_type):
            new_node = (parameter0, parameter1, move_type)

            if new_node in all_attractor_nodes:
                return False

            # If we already recorded this player-II node together with its
            # currently unresolved successors, we do not recompute it.
            if seen_player2_nodes_not_in_attractor.has_key(new_node):
                return False

            if isinstance(parameter0, int):
                q = parameter0
                m = parameter1
                i = 0
            else:
                q = parameter1
                m = parameter0
                i = 1

            successors_not_in_attractor = set()

            if move_type == MOVES[COLL]:
                # TODO
                pass

            elif move_type in FiniteAutomata.alphabet:
                all_successor_states = {succ for p in m for succ in
                                        self.automatons[1 - i].get_successors(s=p, a=move_type)}

                # TODO alle Teilmengen von all_successor_states bestimmen die mindestens ein Element enthalten oder maximal self.pebbles elements enthalten bestimmten.

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
                    m = parameter1
                    i = 0
                else:
                    q = parameter1
                    m = parameter0
                    i = 1

                if move_type == MOVES[CHOICE]:
                    for letter in FiniteAutomata.alphabet:
                        # Reverse of the player-II response edge:
                        #
                        #   (q0, M1_old, a) -> (q0, M1, choice)
                        #
                        # where M1 is chosen from the a-successors of M1_old,
                        # and symmetrically:
                        #
                        #   (M0_old, q1, a) -> (M0, q1, choice)
                        #
                        # The current set M is the chosen successor set. We
                        # therefore reconstruct all old pebble sets that could
                        # cover M under the recorded letter.
                        predecessor_map = {
                            p: self.automatons[1 - i].get_predecessors(s=p, a=letter)
                            for p in m
                        }

                        # First build minimal predecessor sets by choosing one
                        # predecessor for every target pebble in M. A single
                        # old state may cover several target pebbles, so the
                        # resulting frozensets can be smaller than M.
                        predecessor_sets = set()
                        predecessor_options = list(predecessor_map.values())

                        if all(predecessor_options):
                            for predecessor_choice in product(*predecessor_options):
                                predecessor_set = frozenset(predecessor_choice)

                                if len(predecessor_set) <= self.pebbles:
                                    predecessor_sets.add(predecessor_set)

                        if not predecessor_sets:
                            continue

                        # Then add all supersets up to size k, because Player
                        # II may have carried additional old pebbles that were
                        # not needed to produce the current successor set M.
                        extended_predecessor_sets = set(predecessor_sets)

                        for predecessor_set in predecessor_sets:
                            missing_states = self.states[1 - i] - predecessor_set
                            remaining_capacity = self.pebbles - len(predecessor_set)

                            for r in range(1, remaining_capacity + 1):
                                for additional_states in combinations(missing_states, r):
                                    extended_predecessor_sets.add(
                                        frozenset(predecessor_set | set(additional_states))
                                    )

                        for predecessor_set in extended_predecessor_sets:
                            if i == 0:
                                if new_player_2_node(parameter0=q, parameter1=predecessor_set, move_type=letter):
                                    return False, f'The automatons are not {self.pebbles}-pebble bisimilar'
                            else:
                                if new_player_2_node(parameter0=predecessor_set, parameter1=q, move_type=letter):
                                    return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                elif move_type == MOVES[MOVE]:
                    # Reverse of the player-I choice-to-move edge:
                    #
                    #   (q0, M1, choice) -> (q0, M1, move)
                    #
                    # and symmetrically:
                    #
                    #   (M0, q1, choice) -> (M0, q1, move)
                    #
                    # Since `choice` is owned by player I, this predecessor is
                    # existential and can be added directly to the attractor.
                    if new_player_1_node(parameter0=parameter0, parameter1=parameter1, move_type=MOVES[CHOICE]):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                    # Reverse of the player-II collapse edge:
                    #
                    #   (q0, M1, coll) -> ({q0}, q1, move)
                    #
                    # for some q1 in M1, and symmetrically:
                    #
                    #   (M0, q1, coll) -> (q0, {q1}, move)
                    #
                    # Therefore this reverse case only applies if the set-side
                    # of the current move node is a singleton. We then rebuild
                    # every possible collapsed predecessor set containing the
                    # current single state `q`, with size at most k.
                    if len(m) == 1:
                        q_in_M = next(iter(m))

                        not_q_states = set(self.states[i]) - {q}

                        new_Ms = []
                        for r in range(self.pebbles):
                            for c in combinations(not_q_states, r):
                                new_Ms.append(frozenset({q, *c}))

                        if i == 0:
                            for new_M in new_Ms:
                                if new_player_2_node(parameter0=new_M, parameter1=q_in_M, move_type=MOVES[COLL]):
                                    return False, f'The automatons are not {self.pebbles}-pebble bisimilar'
                        else:
                            for new_M in new_Ms:
                                if new_player_2_node(parameter0=q_in_M, parameter1=new_M, move_type=MOVES[COLL]):
                                    return False, f'The automatons are not {self.pebbles}-pebble bisimilar'


                elif move_type == MOVES[COLL]:
                    # Reverse of the player-I choice-to-collapse edge:
                    #
                    #   (q0, M1, choice) -> (q0, M1, coll)
                    #
                    # and symmetrically:
                    #
                    #   (M0, q1, choice) -> (M0, q1, coll)
                    #
                    # Since `choice` is owned by player I, the predecessor is
                    # existential and can be added directly to the attractor.
                    if new_player_1_node(parameter0=parameter0, parameter1=parameter1, move_type=MOVES[CHOICE]):
                        return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

                elif move_type in FiniteAutomata.alphabet:

                    # Reverse of the player-I move edge:
                    #
                    #   (q0, M1, move) -> (q0', M1, a)
                    #
                    # and symmetrically:
                    #
                    #   (M0, q1, move) -> (M0, q1', a)
                    #
                    # We therefore enumerate all predecessors of the moved
                    # single pebble under the recorded letter `move_type`.
                    for predecessor in self.automatons[i].get_predecessors(s=q, a=move_type):
                        if i == 0:
                            if new_player_1_node(parameter0=predecessor, parameter1=m, move_type=MOVES[MOVE]):
                                return False, f'The automatons are not {self.pebbles}-pebble bisimilar'
                        else:
                            if new_player_1_node(parameter0=m, parameter1=predecessor, move_type=MOVES[MOVE]):
                                return False, f'The automatons are not {self.pebbles}-pebble bisimilar'

            last_added_attractor_nodes = new_attractor_nodes.copy()
            new_attractor_nodes = set()

        # If the initial node never entered the player-I attractor, then player
        # II can avoid F forever and therefore has a winning strategy.
        return True, f'The automatas are {self.pebbles}-pebble bisimilar'
