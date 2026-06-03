from wofa import FiniteAutomata

from .BisimulationGames import BisimulationGames
from .TwoWaySetMap import TwoWaySetMap

CHOICE = "CHOICE"
MOVE = "MOVE"
FLUSH = "FLUSH"
MOVES = {CHOICE: 0, MOVE: 1, FLUSH: 2}


class BufferedBisimulationGames(BisimulationGames):
    """Solve the k-buffered bisimulation game via backward attractor computation.

    The implementation follows the game from the paper:

        G^k_buf(A_0, A_1) = (V, V_1, V_2, E, v_I, F)

    where player I tries to reach the immediately winning positions F and
    player II tries to avoid them forever. Therefore we compute the attractor
    of player I to F. Player II has a winning strategy exactly if the initial
    node is not contained in this attractor.

    The code stores game positions as tuples

        ((q_0, q_1), w, i, m)

    corresponding to the paper notation

        (q_0, w, q_1, i, m).
    """

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata, buffer_size: int):
        """Create the game instance for two NFA and a buffer of size k."""
        assert buffer_size >= 1, "Buffer size must be at least 1"
        self.buffer_size = buffer_size
        super().__init__(automaton0, automaton1)

    def set_buffer_size(self, buffer_size: int):
        """Set the buffer size for the game."""
        assert buffer_size >= 1, "Buffer size must be at least 1"
        self.buffer_size = buffer_size

    def solve(self):
        """Return whether player II wins the k-buffered bisimulation game.

        The method computes the least attractor of player I to the set F of
        immediately winning positions for player I.

        Standard attractor definition:

            Attr_I^0(F) = F

            Attr_I^{n+1}(F) =
                Attr_I^n(F)
                union
                {v in V_I  | exists (v, u) in E with u in Attr_I^n(F)}
                union
                {v in V_II | forall (v, u) in E, u in Attr_I^n(F)}

        Player II has a winning strategy iff the initial node v_I is not in
        Attr_I(F).

        Returns:
            tuple[bool, str]:
                True  if player II wins, i.e. the automata are k-buffer bisimilar.
                False if player I wins, i.e. the initial node is in the attractor.
        """

        def check_initial(
                node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            """Check whether the current node is the initial game position.

            In the paper the initial position is

                v_I = (q_0^I, epsilon, q_1^I, 0, choice).

            The local automaton API exposes `get_initials()`, so this code
            currently treats the initial-state component as a set membership
            test instead of assuming a single initial state.
            """
            return (
                    node_state_pair[0] in self.initials[0]
                    and node_state_pair[1] in self.initials[1]
                    and buffer_word == ''
                    and automaton_index == 0
                    and move_type == MOVES[CHOICE]
            )

        def __propagate_new_attractor_nodes(nodes_to_process: list[tuple]) -> bool:
            """Propagate the player-I attractor through stored player-II obligations.

            For player-II nodes we must realize the universal predecessor rule:

                v in V_II enters Attr_I(F)
                iff every successor of v already belongs to Attr_I(F).

            The map `seen_player2_nodes_not_in_attractor` stores, for every
            player-II node that is not yet in the attractor, the set of its
            successors that are still outside the attractor.

            Whenever a new node u enters the attractor, we remove u from all of
            these pending successor sets. If a pending set becomes empty, then
            the corresponding player-II node now satisfies the universal rule
            and must itself enter the attractor. This can trigger another
            cascade, so we process the nodes via a work list.

            Args:
                nodes_to_process: Newly added attractor nodes whose arrival may
                    discharge pending player-II obligations.

            Returns:
                True iff the initial node is reached during propagation.
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

        def new_player1_node(
                node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            """Add a player-I predecessor node to the attractor.

            This helper is used for existential predecessors. In an attractor
            computation a player-I node enters the attractor as soon as one of
            its successors is already in the attractor.

            Args:
                node_state_pair: Encodes (q_0, q_1).
                buffer_word: Buffer content w.
                automaton_index: The active index i from the paper.
                move_type: One of CHOICE, MOVE, FLUSH.

            Returns:
                True iff adding this node implies that the initial node belongs
                to the attractor.
            """
            new_node = (node_state_pair, buffer_word, automaton_index, move_type)

            if new_node in all_attractor_nodes:
                return False

            if check_initial(*new_node):
                return True

            all_attractor_nodes.add(new_node)
            new_attractor_nodes.add(new_node)
            return __propagate_new_attractor_nodes([new_node])

        def new_player2_node(
                node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            """Process a candidate player-II predecessor node.

            A player-II node may only enter the attractor if all of its
            successors are already in the attractor. This helper explicitly
            computes the still-missing successors for the given player-II node.

            Reverse rules implemented here:

            1. Reverse of flush:

                   (q_0, w, q_1, i, flush)
                       --II flushes on A_(1-i)-->
                   (q'_0, epsilon, q'_1, 1-i, move)

               Hence, when we are given a candidate predecessor of type
               `flush`, we compute all possible forward flush successors and
               check whether all of them are already in the attractor.

            2. Reverse of the full-buffer move case:

                   (q_0, vb, q_1, i, move)
                       --II consumes b on A_(1-i)-->
                   (q'_0, v, q'_1, i, choice)

               This is the paper case |w| = k, where player II responds in the
               opposite automaton and the index i does not change.

            Args:
                node_state_pair: Encodes (q_0, q_1).
                buffer_word: Buffer content w.
                automaton_index: The active index i from the paper.
                move_type: Either FLUSH or MOVE for player-II owned nodes.

            Returns:
                True iff this universal predecessor reasoning reaches the
                initial node.
            """
            new_node = (node_state_pair, buffer_word, automaton_index, move_type)

            if new_node in all_attractor_nodes:
                return False

            # If we already recorded this player-II node together with its
            # currently unresolved successors, we do not recompute it.
            if seen_player2_nodes_not_in_attractor.has_key(new_node):
                return False

            successors_not_in_attractor = set()

            if move_type == MOVES[FLUSH]:
                used_automaton: FiniteAutomata = self.automatons[1 - automaton_index]
                current_state = node_state_pair[1 - automaton_index]

                # Forward rule from the paper:
                #
                #   In a position (q_0, w, q_1, i, flush), player II picks
                #   q'_(1-i) in delta_(1-i)(q_(1-i), w) and the game continues
                #   in (q'_0, epsilon, q'_1, 1-i, move).
                #
                # We therefore enumerate all states reachable by reading the
                # whole word w in automaton A_(1-i).
                # The buffer stores words in the same orientation as the
                # player-I move rule appends them:
                #
                #   w -> aw
                #
                # Hence the oldest symbol is stored at the right end of the
                # buffer word. A flush must therefore read the buffered word
                # from right to left, i.e. in reversed(buffer_word), to stay
                # consistent with the full-buffer MOVE rule that consumes
                # buffer_word[-1].
                flush_word = list(reversed(buffer_word))
                reachable_states = (
                    used_automaton.get_successors(s=current_state, a=flush_word[0])
                    if flush_word
                    else {current_state}
                )
                for letter in flush_word[1:]:
                    reachable_states = {
                        successor_state
                        for intermediate_state in reachable_states
                        for successor_state in used_automaton.get_successors(
                            s=intermediate_state,
                            a=letter,
                        )
                    }

                for reachable_state in reachable_states:
                    successor_state_pair = (
                        (node_state_pair[0], reachable_state)
                        if automaton_index == 0
                        else (reachable_state, node_state_pair[1])
                    )
                    successor_node = (
                        successor_state_pair,
                        '',
                        1 - automaton_index,
                        MOVES[MOVE],
                    )

                    if successor_node not in all_attractor_nodes:
                        successors_not_in_attractor.add(successor_node)

            elif move_type == MOVES[MOVE]:
                # In this branch we model the player-II case of a MOVE node,
                # i.e. the paper case |w| = k. Such a node must therefore have
                # a non-empty buffer.
                assert buffer_word, "Player-II MOVE nodes must have a non-empty buffer."

                last_letter = buffer_word[-1]
                remaining_word = buffer_word[:-1]

                # Forward rule from the paper:
                #
                #   If |w| = k and w = vb, then player II picks
                #   q'_(1-i) in delta_(1-i)(q_(1-i), b)
                #   and the game continues in (q'_0, v, q'_1, i, choice).
                #
                # For the universal predecessor test we enumerate exactly these
                # forward successors.
                for successor_state in self.automatons[1 - automaton_index].get_successors(
                        s=node_state_pair[1 - automaton_index], a=last_letter):
                    successor_state_pair = (
                        (node_state_pair[0], successor_state)
                        if automaton_index == 0
                        else (successor_state, node_state_pair[1])
                    )
                    successor_node = (
                        successor_state_pair,
                        remaining_word,
                        automaton_index,
                        MOVES[CHOICE],
                    )

                    if successor_node not in all_attractor_nodes:
                        successors_not_in_attractor.add(successor_node)

            # Universal predecessor rule:
            #
            #   A player-II node enters Attr_I(F) iff all of its successors are
            #   already in Attr_I(F).
            #
            # Thus, if there is no remaining successor outside the attractor,
            # this node itself must be added.
            if not successors_not_in_attractor:

                if check_initial(*new_node):
                    return True

                all_attractor_nodes.add(new_node)
                new_attractor_nodes.add(new_node)
                if __propagate_new_attractor_nodes([new_node]):
                    return True
            else:
                # Otherwise we remember precisely which successors are still
                # missing. As soon as the last one enters the attractor,
                # propagation will add this player-II node automatically.
                seen_player2_nodes_not_in_attractor.add_many(new_node, successors_not_in_attractor)

            return False

        def add_moves_to_player1_node_for_choice_nodes(
                node_state_pair: tuple, extended_buffer_word: str, automaton_index: int):
            """Compute existential predecessors of a `choice` node via `move`.

            Reverse rule for the player-I move case |w| < k:

                (q_0, w, q_1, i, move)
                    --I chooses a and q'_i in delta_i(q_i, a)-->
                (q'_0, aw, q'_1, i, choice)

            Therefore, when the current attractor node is

                (q'_0, aw, q'_1, i, choice),

            we recover predecessors by removing the first symbol a from the
            buffer and enumerating all predecessor states q_i of q'_i under a
            in automaton A_i.

            Args:
                node_state_pair: Encodes the current (q'_0, q'_1).
                extended_buffer_word: The current buffer word aw.
                automaton_index: The active index i.

            Returns:
                True iff the initial node is reached.
            """
            if not extended_buffer_word:
                return False

            first_letter = extended_buffer_word[0]
            remaining_word = extended_buffer_word[1:]

            for predecessor_state in self.automatons[automaton_index].get_predecessors(
                    s=node_state_pair[automaton_index], a=first_letter):
                predecessor_state_pair = (
                    (predecessor_state, node_state_pair[1])
                    if automaton_index == 0
                    else (node_state_pair[0], predecessor_state)
                )
                if new_player1_node(
                        node_state_pair=predecessor_state_pair,
                        buffer_word=remaining_word,
                        automaton_index=automaton_index,
                        move_type=MOVES[MOVE],
                ):
                    return True

            return False

        # The attractor is initialized with the paper's immediate winning
        # positions for player I:
        #
        #   F = {(q_0, epsilon, q_1, i, m) |
        #        q_0 in F_0 xor q_1 in F_1}
        #
        # and i arbitrary, m arbitrary among the implemented move types.
        #
        # Note: the paper lists {choice, move, flush, step}. The operational
        # rules used by this implementation only require {choice, move, flush},
        # so the code works with exactly these three move kinds.
        all_attractor_nodes = set()

        for left_final_state in self.finals[0]:
            for right_non_final_state in self.non_finals[1]:
                for automaton_index in range(2):
                    for move_type in range(3):
                        new_node = ((left_final_state, right_non_final_state), '', automaton_index, move_type)
                        if check_initial(*new_node):
                            return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                        all_attractor_nodes.add(new_node)

        for left_non_final_state in self.non_finals[0]:
            for right_final_state in self.finals[1]:
                for automaton_index in range(2):
                    for move_type in range(3):
                        new_node = ((left_non_final_state, right_final_state), '', automaton_index, move_type)
                        if check_initial(*new_node):
                            return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

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
            for (state_pair, current_buffer_word, automaton_index, move_type) in last_added_attractor_nodes:

                if move_type == MOVES[CHOICE]:
                    buffer_length = len(current_buffer_word)

                    if buffer_length == self.buffer_size:
                        # Reverse of the player-I move case cannot apply here,
                        # because the predecessor move node would already have
                        # had a full buffer and would therefore belong to player
                        # II. Hence, only the reverse of the player-I move step
                        # that produced this choice node is relevant.
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=automaton_index,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                    elif buffer_length == (self.buffer_size - 1):
                        # This is the mixed boundary case. A choice node with
                        # buffer length k - 1 may have two different predecessor
                        # shapes:
                        #
                        # 1. Player-I move predecessor with |w| < k
                        # 2. Player-II move predecessor with |w| = k and one
                        #    symbol already consumed in the opposite automaton
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=automaton_index,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                        for predecessor_state, predecessor_letter in self.automatons[
                            1 - automaton_index].get_all_predecessors_with_letter(
                            s=state_pair[1 - automaton_index]
                        ):
                            predecessor_state_pair = (
                                (state_pair[0], predecessor_state)
                                if automaton_index == 0
                                else (predecessor_state, state_pair[1])
                            )
                            if new_player2_node(
                                    node_state_pair=predecessor_state_pair,
                                    buffer_word=current_buffer_word + predecessor_letter,
                                    automaton_index=automaton_index,
                                    move_type=MOVES[MOVE],
                            ):
                                return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                    elif (self.buffer_size - 1) > buffer_length > 0:
                        # If 0 < |w| < k - 1, only the player-I move rule can
                        # be a predecessor of the current choice node.
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=automaton_index,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                elif move_type == MOVES[FLUSH]:
                    # Reverse of
                    #
                    #   (q_0, w, q_1, i, choice) -> (q_0, w, q_1, i, flush)
                    #
                    # This is an existential predecessor because `choice`
                    # belongs to player I.
                    if new_player1_node(
                            node_state_pair=state_pair,
                            buffer_word=current_buffer_word,
                            automaton_index=automaton_index,
                            move_type=MOVES[CHOICE],
                    ):
                        return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                elif move_type == MOVES[MOVE]:
                    # Reverse of
                    #
                    #   (q_0, w, q_1, i, choice) -> (q_0, w, q_1, i, move)
                    #
                    # Again an existential predecessor because `choice`
                    # belongs to player I.
                    if new_player1_node(
                            node_state_pair=state_pair,
                            buffer_word=current_buffer_word,
                            automaton_index=automaton_index,
                            move_type=MOVES[CHOICE],
                    ):
                        return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

                    # Reverse of the flush rule can only target a move node with
                    # empty buffer:
                    #
                    #   (q_0, w, q_1, i, flush) -> (q'_0, epsilon, q'_1, 1-i, move)
                    #
                    # So for a current move node with empty buffer we enumerate
                    # all possible predecessor flush nodes.
                    if current_buffer_word == '':
                        used_automaton: FiniteAutomata = self.automatons[automaton_index]
                        possible_flush_predecessors = {(state_pair[automaton_index], '')}

                        predecessor_pairs = used_automaton.get_all_predecessors_with_letter(
                            s=state_pair[automaton_index]
                        )
                        possible_flush_predecessors.update(predecessor_pairs)

                        for _ in range(self.buffer_size - 1):
                            new_predecessor_pairs = set()
                            for predecessor_state, predecessor_word in predecessor_pairs:
                                for new_state, new_letter in used_automaton.get_all_predecessors_with_letter(
                                        s=predecessor_state):
                                    new_predecessor_pairs.add((new_state, predecessor_word + new_letter))
                            possible_flush_predecessors.update(new_predecessor_pairs)
                            predecessor_pairs = new_predecessor_pairs.copy()

                        for predecessor_state, predecessor_word in possible_flush_predecessors:
                            predecessor_state_pair = (
                                (predecessor_state, state_pair[1])
                                if automaton_index == 0
                                else (state_pair[0], predecessor_state)
                            )
                            if new_player2_node(
                                    node_state_pair=predecessor_state_pair,
                                    buffer_word=predecessor_word,
                                    automaton_index=(1 - automaton_index),
                                    move_type=MOVES[FLUSH],
                            ):
                                return False, f'The automatas are not {self.buffer_size}-buffer bisimilar'

            last_added_attractor_nodes = new_attractor_nodes.copy()
            new_attractor_nodes = set()

        # If the initial node never entered the player-I attractor, then player
        # II can avoid F forever and therefore has a winning strategy.
        return True, f'The automatas are {self.buffer_size}-buffer bisimilar'
