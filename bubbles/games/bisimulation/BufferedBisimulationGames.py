"""Framework for the newly defined buffered bisimulation game.

The actual transition rules are documented in the formal definition in
``Desktop/Bufferd_formal/bisimulation.tex``.  This module deliberately keeps
the game representation separate from the legacy implementation in
``bubbles.old``.
"""

from functools import cache
from itertools import product

from wofa import FiniteAutomata

from .BisimulationGames import BisimulationGames
from ...util.TwoWaySetMap import TwoWaySetMap


FILL_CHOICE = 0
CHECK = 1
CHOICE = 2
CONSUME = 3
FLUSH = 4

Position = tuple[int, str, int, int, int]


class BufferedBisimulationGames(BisimulationGames):
    """Skeleton for the formally revised buffered bisimulation game.

    Player I controls ``FILL_CHOICE`` and ``CHOICE`` positions.  Player II
    controls ``CHECK``, ``CONSUME`` and ``FLUSH`` positions.  A direction of
    ``i`` means that Player I currently moves in automaton ``A_i`` and Player
    II responds in ``A_(1-i)``.
    """

    def __init__(
            self,
            automaton0: FiniteAutomata,
            automaton1: FiniteAutomata,
            buffer_size: int,
    ):
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")

        self.buffer_size = buffer_size
        super().__init__(automaton0=automaton0, automaton1=automaton1)

    def set_buffer_size(self, buffer_size: int):
        """Set the buffer capacity for subsequent calls to :meth:`solve`."""
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")
        self.buffer_size = buffer_size

    def solve(self):
        """Solve the game.

        The solver will construct only the positions needed by the backward
        attractor computation.  It will not materialize the complete game
        graph in advance.
        """

        alphabet = tuple(FiniteAutomata.alphabet)

        def _words_by_length() -> dict[int, tuple[str, ...]]:
            """Build all buffer words once, grouped by their length."""
            return {
                length: tuple(
                    ''.join(letters)
                    for letters in product(alphabet, repeat=length)
                )
                for length in range(self.buffer_size + 1)
            }

        words_by_length = _words_by_length()
        all_words = tuple(
            word
            for words in words_by_length.values()
            for word in words
        )

        @cache
        def _successors(automaton_index: int, state: int, letter: str) -> frozenset[int]:
            """Return and cache one-step successors for a state and letter."""
            return frozenset(
                self.automatons[automaton_index].get_successors(
                    s=state,
                    a=letter,
                )
            )

        @cache
        def _predecessors(automaton_index: int, state: int, letter: str) -> frozenset[int]:
            """Return and cache one-step predecessors for a state and letter."""
            return frozenset(
                self.automatons[automaton_index].get_predecessors(
                    s=state,
                    a=letter,
                )
            )

        @cache
        def _reachable_states(
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
                    for successor in _successors(automaton_index, current_state, letter)
                }
            return frozenset(reachable)

        @cache
        def _reverse_reachable_states(
                automaton_index: int,
                target_state: int,
                word: str,
        ) -> frozenset[int]:
            """Return and cache states that can read ``word`` to ``target_state``."""
            possible_predecessors = {target_state}
            for letter in reversed(word):
                possible_predecessors = {
                    predecessor
                    for current_state in possible_predecessors
                    for predecessor in _predecessors(
                        automaton_index,
                        current_state,
                        letter,
                    )
                }
            return frozenset(possible_predecessors)

        def _acceptance_matches(
                state_i: int,
                response_state: int,
                direction: int,
        ) -> bool:
            """Return whether a response state matches Player I's acceptance."""
            return (
                (state_i in self.finals[direction])
                == (response_state in self.finals[1 - direction])
            )

        def _make_position(
                state_pair: tuple[int, int],
                buffer_word: str,
                direction: int,
                phase: int,
        ) -> Position:
            """Construct a position in formal order ``(q0, w, q1, i, m)``."""
            return state_pair[0], buffer_word, state_pair[1], direction, phase

        @cache
        def _has_acceptance_compatible_response(
                state_pair: tuple[int, int],
                buffer_word: str,
                direction: int,
        ) -> bool:
            """Return whether Player II has a complete compatible response."""
            response_start = state_pair[1 - direction]
            response_states = _reachable_states(
                automaton_index=1 - direction,
                state=response_start,
                word=buffer_word,
            )

            return any(
                _acceptance_matches(
                    state_i=state_pair[direction],
                    response_state=response_state,
                    direction=direction,
                )
                for response_state in response_states
            )

        initial_state0 = next(iter(self.initials[0]))
        initial_state1 = next(iter(self.initials[1]))
        initial_position = (
            initial_state0,
            "",
            initial_state1,
            0,
            FILL_CHOICE,
        )
        all_attractor_nodes: set[Position] = set()
        new_attractor_nodes: set[Position] = set()
        seen_player2_nodes_not_in_attractor = TwoWaySetMap()

        def _is_initial_position(position: Position) -> bool:
            """Return whether ``position`` is the game's start position."""
            return position == initial_position

        def _add_attractor_node(position: Position) -> bool:
            """Add a node unless it is the start node.

            Returns:
                ``True`` if the start node was found and Player I therefore
                wins immediately; ``False`` otherwise.
            """
            if position in all_attractor_nodes:
                return False

            if _is_initial_position(position):
                return True

            all_attractor_nodes.add(position)
            new_attractor_nodes.add(position)
            return False

        def _add_player_i_predecessor(position: Position) -> bool:
            """Add all Player-I predecessors of an attractor position.

            Requirements for the implementation:

            * ``position`` is already contained in the Player-I attractor.
            * Every generated predecessor must have at least one legal
              Player-I move to ``position``.
            * For a word-extension edge, the last buffer symbol is removed and
              all predecessor states under that symbol are enumerated.
            * The direct ``Check``, ``Consume`` and ``Flush`` edges are
              reversed only when their phase and buffer-size constraints allow
              them.
            * Every generated predecessor must be added through
              ``_add_attractor_node`` so duplicate positions are ignored and
              the initial position is detected immediately.

            Returns:
                ``True`` if a generated predecessor is the initial position.
            """
            current_state0, current_buffer_word, current_state1, direction, phase = position
            current_state_pair = (current_state0, current_state1)

            def _add_predecessor(
                    predecessor_state_pair: tuple[int, int],
                    predecessor_buffer_word: str,
                    predecessor_phase: int,
            ) -> bool:
                """Add one generated Player-I predecessor."""
                return _add_attractor_node(
                    _make_position(
                        state_pair=predecessor_state_pair,
                        buffer_word=predecessor_buffer_word,
                        direction=direction,
                        phase=predecessor_phase,
                    )
                )

            # Reverse a Player-I buffer-extension move. The formal move
            # appends a symbol on the right, so the predecessor is obtained by
            # removing the last symbol and moving to a predecessor state under
            # that symbol in the active automaton.
            if phase in (FILL_CHOICE, CHOICE) and current_buffer_word:
                last_letter = current_buffer_word[-1]
                predecessor_buffer_word = current_buffer_word[:-1]

                for predecessor_state in _predecessors(
                        direction,
                        current_state_pair[direction],
                        last_letter,
                ):
                    predecessor_state_pair = (
                        (predecessor_state, current_state_pair[1])
                        if direction == 0
                        else (current_state_pair[0], predecessor_state)
                    )

                    if _add_predecessor(
                            predecessor_state_pair=predecessor_state_pair,
                            predecessor_buffer_word=predecessor_buffer_word,
                            predecessor_phase=phase,
                    ):
                        return True

            # A full FillChoice position can move to the corresponding Choice
            # position without changing the states or the buffer.
            if phase == CHOICE and len(current_buffer_word) == self.buffer_size:
                if _add_predecessor(
                        predecessor_state_pair=current_state_pair,
                        predecessor_buffer_word=current_buffer_word,
                        predecessor_phase=FILL_CHOICE,
                ):
                    return True

            # A Check request is a Player-I move from the corresponding
            # FillChoice position and is legal only for a non-full buffer.
            if phase == CHECK and len(current_buffer_word) < self.buffer_size:
                if _add_predecessor(
                        predecessor_state_pair=current_state_pair,
                        predecessor_buffer_word=current_buffer_word,
                        predecessor_phase=FILL_CHOICE,
                ):
                    return True

            # At a full buffer Player I may request Consume or Flush from the
            # corresponding Choice position. Flush is also available on an
            # empty buffer.
            if phase == CONSUME and len(current_buffer_word) == self.buffer_size:
                if _add_predecessor(
                        predecessor_state_pair=current_state_pair,
                        predecessor_buffer_word=current_buffer_word,
                        predecessor_phase=CHOICE,
                ):
                    return True

            if phase == FLUSH and len(current_buffer_word) in (0, self.buffer_size):
                if _add_predecessor(
                        predecessor_state_pair=current_state_pair,
                        predecessor_buffer_word=current_buffer_word,
                        predecessor_phase=CHOICE,
                ):
                    return True

            return False

        def _add_player_ii_predecessor(position: Position) -> bool:
            """Add a Player-II predecessor when all responses are losing.

            Requirements for the implementation:

            * The supplied position must be a Player-II position, currently
              one of ``CHECK``, ``CONSUME`` or ``FLUSH``.
            * All legal successors of the position must be enumerated exactly
              according to the formal rules.
            * The position may enter the attractor only if every legal
              successor is already in ``all_attractor_nodes``.
            * If there is no legal Player-II response, the position is an
              immediate Player-I win and must be added to the attractor.
            * If some successors are not yet in the attractor, the unresolved
              obligations must be stored in ``TwoWaySetMap`` so they can be
              discharged when those successors are added later.
            * Every newly added position must go through
              ``_add_attractor_node`` so the initial position is detected
              immediately and the current frontier is updated.

            Returns:
                ``True`` if adding the position discovers the initial node.
            """
            if position in all_attractor_nodes:
                return False

            if seen_player2_nodes_not_in_attractor.has_key(position):
                return False

            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)
            response_states: set[Position] = set()

            if phase == CHECK:
                # A Check response reads the complete buffer in the opposite
                # automaton and then restarts from the initial states in the
                # opposite direction. Every successful response therefore has
                # the same successor position.
                compatible_states = _reachable_states(
                    automaton_index=1 - direction,
                    state=state_pair[1 - direction],
                    word=buffer_word,
                )

                if any(
                        _acceptance_matches(
                            state_i=state_pair[direction],
                            response_state=response_state,
                            direction=direction,
                        )
                        for response_state in compatible_states
                ):
                    response_states.add(
                        _make_position(
                            state_pair=(
                                next(iter(self.initials[0])),
                                next(iter(self.initials[1])),
                            ),
                            buffer_word="",
                            direction=1 - direction,
                            phase=FILL_CHOICE,
                        )
                    )

            elif phase == CONSUME:
                # Consume is only entered with a full, non-empty buffer. The
                # first symbol is consumed in the opposite automaton.
                if len(buffer_word) != self.buffer_size or not buffer_word:
                    raise ValueError("Consume positions must have a full buffer.")

                first_letter = buffer_word[0]
                remaining_word = buffer_word[1:]
                response_states_after_move = _successors(
                    1 - direction,
                    state_pair[1 - direction],
                    first_letter,
                )

                for response_state in response_states_after_move:
                    if remaining_word:
                        successor_state_pair = (
                            (state_pair[0], response_state)
                            if direction == 0
                            else (response_state, state_pair[1])
                        )
                        response_states.add(
                            _make_position(
                                state_pair=successor_state_pair,
                                buffer_word=remaining_word,
                                direction=direction,
                                phase=CHOICE,
                            )
                        )
                    elif _acceptance_matches(
                            state_i=state_pair[direction],
                            response_state=response_state,
                            direction=direction,
                    ):
                        successor_state_pair = (
                            (state_pair[0], response_state)
                            if direction == 0
                            else (response_state, state_pair[1])
                        )
                        response_states.add(
                            _make_position(
                                state_pair=successor_state_pair,
                                buffer_word="",
                                direction=direction,
                                phase=CHOICE,
                            )
                        )

            elif phase == FLUSH:
                # Flush reads the complete buffer in the opposite automaton,
                # checks acceptance, and then restarts the regular game in the
                # opposite direction at the resulting state pair.
                if len(buffer_word) not in (0, self.buffer_size):
                    raise ValueError("Flush positions must have an empty or full buffer.")

                compatible_states = _reachable_states(
                    automaton_index=1 - direction,
                    state=state_pair[1 - direction],
                    word=buffer_word,
                )

                for response_state in compatible_states:
                    if not _acceptance_matches(
                            state_i=state_pair[direction],
                            response_state=response_state,
                            direction=direction,
                    ):
                        continue

                    successor_state_pair = (
                        (state_pair[0], response_state)
                        if direction == 0
                        else (response_state, state_pair[1])
                    )
                    response_states.add(
                        _make_position(
                            state_pair=successor_state_pair,
                            buffer_word="",
                            direction=1 - direction,
                            phase=CHOICE,
                        )
                    )

            else:
                raise ValueError("The supplied position is not a Player-II position.")

            # No legal response means that Player I wins immediately.
            if not response_states:
                return _add_attractor_node(position)

            unresolved_successors = {
                successor
                for successor in response_states
                if successor not in all_attractor_nodes
            }

            # If every legal response is already losing for Player II, this
            # universal predecessor is itself part of the attractor.
            if not unresolved_successors:
                return _add_attractor_node(position)

            # Otherwise retain exactly the responses that still prevent this
            # Player-II node from entering the attractor. The reverse lookup
            # allows the propagation step to find this node when one of those
            # responses is added later.
            seen_player2_nodes_not_in_attractor.add_many(
                position,
                unresolved_successors,
            )
            return False

        def _add_player_ii_predecessors(position: Position) -> bool:
            """Generate and process all Player-II predecessors of a node.

            A ``FILL_CHOICE`` node can be reached from a successful ``CHECK``
            response only when it is the initial state pair. A ``CHOICE`` node
            can be reached from ``CONSUME`` or ``FLUSH``. Each generated
            candidate is checked by ``_add_player_ii_predecessor``.

            Returns:
                ``True`` if a generated predecessor is the initial position.
            """
            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)

            if phase == FILL_CHOICE:
                # Successful Check responses always restart at the initial
                # state pair, with the direction switched and an empty buffer.
                if state_pair != (initial_state0, initial_state1) or buffer_word:
                    return False

                for predecessor_state0 in self.states[0]:
                    for predecessor_state1 in self.states[1]:
                        for predecessor_word in all_words:
                            if len(predecessor_word) >= self.buffer_size:
                                continue

                            predecessor = _make_position(
                                state_pair=(predecessor_state0, predecessor_state1),
                                buffer_word=predecessor_word,
                                direction=1 - direction,
                                phase=CHECK,
                            )
                            if _add_player_ii_predecessor(predecessor):
                                return True

            elif phase == CHOICE:
                # A Consume response removes the first symbol from a full
                # buffer. Reverse that move by prepending every alphabet
                # symbol and enumerating predecessor states in the response
                # automaton.
                if len(buffer_word) == self.buffer_size - 1:
                    for consumed_letter in alphabet:
                        for predecessor_response_state in _predecessors(
                                1 - direction,
                                state_pair[1 - direction],
                                consumed_letter,
                        ):
                            predecessor_state_pair = (
                                (state_pair[0], predecessor_response_state)
                                if direction == 0
                                else (predecessor_response_state, state_pair[1])
                            )
                            predecessor = _make_position(
                                state_pair=predecessor_state_pair,
                                buffer_word=consumed_letter + buffer_word,
                                direction=direction,
                                phase=CONSUME,
                            )
                            if _add_player_ii_predecessor(predecessor):
                                return True

                # A Flush response always produces an empty-buffer Choice
                # position and switches direction. Reverse reachability
                # restricts candidates to response-start states that can
                # actually read the predecessor word to the current state.
                if not buffer_word:
                    predecessor_direction = 1 - direction
                    active_predecessor_state = state_pair[predecessor_direction]
                    target_response_state = state_pair[direction]

                    for predecessor_word in (
                            *words_by_length[0],
                            *words_by_length[self.buffer_size],
                    ):
                        for response_start_state in _reverse_reachable_states(
                                automaton_index=direction,
                                target_state=target_response_state,
                                word=predecessor_word,
                        ):
                            predecessor_state_pair = (
                                (active_predecessor_state, response_start_state)
                                if predecessor_direction == 0
                                else (response_start_state, active_predecessor_state)
                            )
                            predecessor = _make_position(
                                state_pair=predecessor_state_pair,
                                buffer_word=predecessor_word,
                                direction=predecessor_direction,
                                phase=FLUSH,
                            )
                            if _add_player_ii_predecessor(predecessor):
                                return True

            return False

        def _propagate_new_attractor_nodes() -> bool:
            """Discharge Player-II obligations for newly added nodes.

            When an attractor node is added, it is removed from every pending
            Player-II obligation that references it. If an obligation becomes
            empty, its Player-II position is added to the attractor as well.

            Returns:
                ``True`` if propagation discovers the initial position.
            """
            current_frontier = list(new_attractor_nodes)

            while current_frontier:
                propagated_node = current_frontier.pop()
                ready_player2_nodes = seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    propagated_node
                )

                for player2_node in ready_player2_nodes:
                    if _add_attractor_node(player2_node):
                        return True

                    if player2_node in new_attractor_nodes:
                        current_frontier.append(player2_node)

            return False

        def _initial_attractor_nodes() -> bool:
            """Compute immediate Player-I wins and detect the start node."""
            for state0 in self.states[0]:
                for state1 in self.states[1]:
                    state_pair = (state0, state1)

                    for direction in (0, 1):
                        active_state = state_pair[direction]
                        other_state = state_pair[1 - direction]

                        # A reached empty Choice position must satisfy the
                        # directional acceptance condition.
                        if (
                                active_state in self.finals[direction]
                                and other_state not in self.finals[1 - direction]
                        ):
                            if _add_attractor_node(
                                    _make_position(state_pair, "", direction, CHOICE)
                            ):
                                return True

                        # Check positions can contain every word shorter than
                        # k. Player II loses immediately if no complete-word
                        # response has matching acceptance.
                        for buffer_word in all_words:
                            if len(buffer_word) < self.buffer_size and not _has_acceptance_compatible_response(
                                    state_pair=state_pair,
                                    buffer_word=buffer_word,
                                    direction=direction,
                            ):
                                if _add_attractor_node(
                                        _make_position(state_pair, buffer_word, direction, CHECK)
                                ):
                                    return True

                            # Flush is available only for an empty or full
                            # buffer in a reachable Choice position.
                            if len(buffer_word) in (0, self.buffer_size) and not _has_acceptance_compatible_response(
                                    state_pair=state_pair,
                                    buffer_word=buffer_word,
                                    direction=direction,
                            ):
                                if _add_attractor_node(
                                        _make_position(state_pair, buffer_word, direction, FLUSH)
                                ):
                                    return True

                            # Consume positions are reached only with a full
                            # buffer. Player II must match its first symbol.
                            if len(buffer_word) == self.buffer_size:
                                first_letter = buffer_word[0]
                                remaining_word = buffer_word[1:]
                                response_states = _successors(
                                    1 - direction,
                                    other_state,
                                    first_letter,
                                )

                                if not response_states:
                                    if _add_attractor_node(
                                            _make_position(state_pair, buffer_word, direction, CONSUME)
                                    ):
                                        return True
                                elif not remaining_word and not any(
                                        _acceptance_matches(
                                            state_i=active_state,
                                            response_state=response_state,
                                            direction=direction,
                                        )
                                        for response_state in response_states
                                ):
                                    if _add_attractor_node(
                                            _make_position(state_pair, buffer_word, direction, CONSUME)
                                    ):
                                        return True

            return False

        if _initial_attractor_nodes():
            return False, f"The automatons are not {self.buffer_size}-buffer bisimilar"

        while new_attractor_nodes:
            current_frontier = new_attractor_nodes.copy()
            new_attractor_nodes.clear()

            for position in current_frontier:
                # First discharge Player-II obligations that were waiting for
                # this position to enter the attractor.
                ready_player2_nodes = seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    position
                )
                for player2_node in ready_player2_nodes:
                    if _add_attractor_node(player2_node):
                        return False, f"The automatons are not {self.buffer_size}-buffer bisimilar"

                # Then generate both kinds of backward predecessors of the
                # current frontier node.
                if _add_player_i_predecessor(position):
                    return False, f"The automatons are not {self.buffer_size}-buffer bisimilar"

                if _add_player_ii_predecessors(position):
                    return False, f"The automatons are not {self.buffer_size}-buffer bisimilar"

            if _propagate_new_attractor_nodes():
                return False, f"The automatons are not {self.buffer_size}-buffer bisimilar"

        return True, f"The automatons are {self.buffer_size}-buffer bisimilar"
