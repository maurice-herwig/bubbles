"""Buffered simulation game scaffold."""

from functools import cache
from itertools import product

from wofa import FiniteAutomata

from ...util.TwoWaySetMap import TwoWaySetMap
from .SimulationGames import SimulationGames


CHOICE = 0
CONSUME = 1
FLUSH = 2

Position = tuple[int, str, int, int, int]


class BufferedSimulationGames(SimulationGames):
    """Implementation of the restarting buffered simulation game.

    A position has the form ``(state_0, buffer_word, state_1, direction,
    phase)``. The direction identifies the automaton in which Player I
    currently chooses transitions; the phase identifies the position type.
    """

    def __init__(
            self,
            automaton0,
            automaton1,
            buffer_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a buffered simulation game.

        ``remove_dead_states`` controls whether unproductive states are
        removed during the shared automaton preparation.
        """
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")

        self.buffer_size = buffer_size
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            remove_dead_states=remove_dead_states,
        )

    def set_buffer_size(self, buffer_size: int):
        """Set the buffer capacity used by subsequent calls to ``solve``."""
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")
        self.buffer_size = buffer_size

    def solve(self):
        """Solve the restarting buffered simulation game by attractor iteration."""
        alphabet = tuple(FiniteAutomata.alphabet)
        all_attractor_nodes: set[Position] = set()
        new_attractor_nodes: set[Position] = set()
        seen_player2_nodes_not_in_attractor = TwoWaySetMap()

        initial_state0 = next(iter(self.initials[0]))
        initial_state1 = next(iter(self.initials[1]))
        initial_state_pair = (initial_state0, initial_state1)
        initial_position = (
            initial_state0,
            "",
            initial_state1,
            0,
            CHOICE,
        )

        def _make_position(
                state_pair: tuple[int, int],
                buffer_word: str,
                direction: int,
                phase: int,
        ) -> Position:
            """Create a compact game position from its logical components."""
            return (
                state_pair[0],
                buffer_word,
                state_pair[1],
                direction,
                phase,
            )

        def _add_attractor_node(position: Position) -> bool:
            """Add a position to the attractor and detect the start position."""
            if position in all_attractor_nodes:
                return False

            all_attractor_nodes.add(position)
            new_attractor_nodes.add(position)
            return position == initial_position

        def _acceptance_matches(
                state_pair: tuple[int, int],
                direction: int,
        ) -> bool:
            """Check the directional acceptance condition of a position."""
            active_state = state_pair[direction]
            response_state = state_pair[1 - direction]
            return (
                active_state not in self.finals[direction]
                or response_state in self.finals[1 - direction]
            )

        @cache
        def _missing_response_letters(
                state_pair: tuple[int, int],
                direction: int,
        ) -> frozenset[str]:
            """Return letters for which Player II has no first response."""
            response_state = state_pair[1 - direction]
            return frozenset(
                letter
                for letter in alphabet
                if not self._successors(
                    1 - direction,
                    response_state,
                    letter,
                )
            )

        def _buffer_words_starting_with(first_letter: str):
            """Yield buffer words of lengths one through ``k`` with a prefix."""
            for length in range(1, self.buffer_size + 1):
                for suffix in product(alphabet, repeat=length - 1):
                    yield first_letter + ''.join(suffix)

        def _initial_attractor_nodes() -> bool:
            """Add all positions where Player I wins immediately.

            The initial attractor contains acceptance violations at empty
            ``CHOICE`` and ``FLUSH`` positions, nonempty ``FLUSH`` positions
            whose buffer cannot be read by Player II, and full ``CONSUME``
            positions without a response for the first buffered symbol.

            Returns:
                ``True`` if the actual initial position is added to the
                attractor.
            """
            for state0 in self.states[0]:
                for state1 in self.states[1]:
                    state_pair = (state0, state1)

                    for direction in (0, 1):
                        if not _acceptance_matches(state_pair, direction):
                            if _add_attractor_node(
                                    _make_position(state_pair, "", direction, CHOICE)
                            ):
                                return True

                            if _add_attractor_node(
                                    _make_position(state_pair, "", direction, FLUSH)
                            ):
                                return True

                        for first_letter in _missing_response_letters(
                                state_pair,
                                direction,
                        ):
                            for buffer_word in _buffer_words_starting_with(first_letter):
                                if _add_attractor_node(
                                        _make_position(
                                            state_pair,
                                            buffer_word,
                                            direction,
                                            FLUSH,
                                        )
                                ):
                                    return True

                                if len(buffer_word) == self.buffer_size:
                                    if _add_attractor_node(
                                            _make_position(
                                                state_pair,
                                                buffer_word,
                                                direction,
                                                CONSUME,
                                            )
                                    ):
                                        return True

            return False

        def _add_player_i_predecessor(position: Position) -> bool:
            """Add Player-I predecessors of an attractor position.

            Requirements for the implementation:

            * The supplied position is already in the Player-I attractor.
            * Only ``CHOICE`` positions are controlled by Player I.
            * Every legal symbol and transition choice of Player I must be
              considered in the current direction.
            * A predecessor may append a symbol only while the buffer is not
              full and may lead to either ``CONSUME`` or ``FLUSH``.
            * A Player-I predecessor enters the attractor as soon as one of
              its legal successors is already in the attractor.
            * Every newly added position must be passed to
              ``_add_attractor_node`` so the initial position is detected.

            Returns:
                ``True`` if adding a predecessor discovers the initial
                position.
            """
            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)

            if phase not in (CONSUME, FLUSH):
                return False

            def _consider_choice_predecessor(predecessor: Position) -> bool:
                """Add a Choice predecessor if one of its moves is winning."""
                return _add_attractor_node(predecessor)

            # Player I may flush immediately from every Choice position whose
            # buffer is not full. This is the direct predecessor of a Flush
            # position with the same states and buffer.
            if phase == FLUSH and len(buffer_word) < self.buffer_size:
                if _consider_choice_predecessor(
                        _make_position(state_pair, buffer_word, direction, CHOICE)
                ):
                    return True

            # A Consume move and a Flush move with a nonempty buffer are both
            # created by appending one symbol to the current Choice buffer.
            # Reverse that append by enumerating predecessors of the active
            # state in the automaton controlled by Player I.
            if buffer_word:
                last_letter = buffer_word[-1]
                predecessor_buffer = buffer_word[:-1]
                for predecessor_state in self._predecessors(
                        direction,
                        state_pair[direction],
                        last_letter,
                ):
                    predecessor_state_pair = (
                        (predecessor_state, state1)
                        if direction == 0
                        else (state0, predecessor_state)
                    )
                    predecessor = _make_position(
                        predecessor_state_pair,
                        predecessor_buffer,
                        direction,
                        CHOICE,
                    )
                    if _consider_choice_predecessor(predecessor):
                        return True

            return False

        def _player_ii_successors(candidate: Position) -> set[Position]:
            """Enumerate all legal successors of a Player-II position."""
            state0, buffer_word, state1, direction, phase = candidate
            state_pair = (state0, state1)
            successors: set[Position] = set()

            if phase == CONSUME:
                if buffer_word:
                    first_letter = buffer_word[0]
                    remaining_word = buffer_word[1:]
                    response_states = self._successors(
                        1 - direction,
                        state_pair[1 - direction],
                        first_letter,
                    )
                    for response_state in response_states:
                        successor_state_pair = (
                            (state0, response_state)
                            if direction == 0
                            else (response_state, state1)
                        )
                        successors.add(
                            _make_position(
                                successor_state_pair,
                                remaining_word,
                                direction,
                                CONSUME,
                            )
                        )

                # With spare capacity Player II may stop consuming and return
                # to the corresponding Choice position.
                if len(buffer_word) < self.buffer_size:
                    successors.add(
                        _make_position(state_pair, buffer_word, direction, CHOICE)
                    )

            elif phase == FLUSH:
                if buffer_word:
                    first_letter = buffer_word[0]
                    remaining_word = buffer_word[1:]
                    response_states = self._successors(
                        1 - direction,
                        state_pair[1 - direction],
                        first_letter,
                    )
                    for response_state in response_states:
                        successor_state_pair = (
                            (state0, response_state)
                            if direction == 0
                            else (response_state, state1)
                        )
                        successors.add(
                            _make_position(
                                successor_state_pair,
                                remaining_word,
                                direction,
                                FLUSH,
                            )
                        )
                elif _acceptance_matches(state_pair, direction):
                    # An empty successful Flush restarts in the opposite
                    # direction from the two initial states.
                    successors.add(
                        _make_position(
                            initial_state_pair,
                            "",
                            1 - direction,
                            CHOICE,
                        )
                    )

            return successors

        def _add_player_ii_predecessor(position: Position) -> bool:
            """Add a Player-II predecessor of an attractor position.

            Requirements for the implementation:

            * The supplied position is already in the Player-I attractor.
            * Player-II positions are ``CONSUME`` and ``FLUSH`` positions.
            * All legal Player-II responses must be enumerated exactly.
            * A Player-II position enters the attractor only when every legal
              response is already in the attractor.
            * A non-full ``CONSUME`` position also has the legal response that
              returns to the corresponding ``CHOICE`` position.
            * An empty ``FLUSH`` position restarts in the opposite direction
              and must use the directional acceptance condition.
            * Unresolved responses must be stored in
              ``seen_player2_nodes_not_in_attractor``.
            * A position with no legal Player-II response is an immediate
              Player-I win and must be added to the attractor.
            * Every newly added position must be passed to
              ``_add_attractor_node`` so the initial position is detected.

            Returns:
                ``True`` if adding a predecessor discovers the initial
                position.
            """
            def _consider_player_ii_candidate(candidate: Position) -> bool:
                """Apply the universal predecessor rule to one candidate."""
                if (
                        candidate in all_attractor_nodes
                        or seen_player2_nodes_not_in_attractor.has_key(candidate)
                ):
                    return False

                successors = _player_ii_successors(candidate)

                # No legal response is an immediate Player-I win.
                if not successors:
                    return _add_attractor_node(candidate)

                unresolved_successors = {
                    successor
                    for successor in successors
                    if successor not in all_attractor_nodes
                }

                if not unresolved_successors:
                    return _add_attractor_node(candidate)

                seen_player2_nodes_not_in_attractor.add_many(
                    candidate,
                    unresolved_successors,
                )
                return False

            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)

            # A non-full Consume position may return directly to Choice.
            if phase == CHOICE and len(buffer_word) < self.buffer_size:
                if _consider_player_ii_candidate(
                        _make_position(state_pair, buffer_word, direction, CONSUME)
                ):
                    return True

            # A successful empty Flush restarts at the initial Choice position.
            # Therefore only the initial state pair can have such a predecessor.
            if (
                    phase == CHOICE
                    and not buffer_word
                    and state_pair == (
                        initial_state0,
                        initial_state1,
                    )
            ):
                predecessor_direction = 1 - direction
                for predecessor_state0 in self.states[0]:
                    for predecessor_state1 in self.states[1]:
                        predecessor_state_pair = (
                            predecessor_state0,
                            predecessor_state1,
                        )
                        if _acceptance_matches(
                                predecessor_state_pair,
                                predecessor_direction,
                        ) and _consider_player_ii_candidate(
                                _make_position(
                                    predecessor_state_pair,
                                    "",
                                    predecessor_direction,
                                    FLUSH,
                                )
                        ):
                            return True

            # Reverse one Player-II response step for Consume and Flush.
            if phase in (CONSUME, FLUSH) and len(buffer_word) < self.buffer_size:
                for consumed_letter in alphabet:
                    for predecessor_response_state in self._predecessors(
                            1 - direction,
                            state_pair[1 - direction],
                            consumed_letter,
                    ):
                        predecessor_state_pair = (
                            (state0, predecessor_response_state)
                            if direction == 0
                            else (predecessor_response_state, state1)
                        )
                        predecessor = _make_position(
                            predecessor_state_pair,
                            consumed_letter + buffer_word,
                            direction,
                            phase,
                        )
                        if _consider_player_ii_candidate(predecessor):
                            return True

            return False

        if _initial_attractor_nodes():
            return False, "The automatons are not buffered simulation equivalent"

        while new_attractor_nodes:
            current_frontier = new_attractor_nodes.copy()
            new_attractor_nodes.clear()

            for position in current_frontier:
                ready_player2_nodes = seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    position
                )
                for player2_node in ready_player2_nodes:
                    if _add_attractor_node(player2_node):
                        return False, "The automatons are not buffered simulation equivalent"

                if _add_player_i_predecessor(position):
                    return False, "The automatons are not buffered simulation equivalent"

                if _add_player_ii_predecessor(position):
                    return False, "The automatons are not buffered simulation equivalent"

        return True, "The automatons are buffered simulation equivalent"
