"""Buffered simulation equivalence game."""

from functools import cache
from itertools import product

from wofa import FiniteAutomata

from ...util.TwoWaySetMap import TwoWaySetMap
from ..BufferedGames import BufferedGamesMixin
from .SimulationGames import SimulationGames


INITIAL = 0
CONSUME = 1
FLUSH = 2

Position = tuple[int, str, int, int, int]


class BufferedSimulationGames(BufferedGamesMixin, SimulationGames):
    """Solve the buffered simulation equivalence game.

    ``CONSUME`` positions with a non-full buffer belong to Player I. Once a
    transition fills the buffer, the resulting ``CONSUME`` position belongs
    to Player II, who consumes the first buffered symbol. ``FLUSH`` positions
    always belong to Player II.
    """

    def __init__(
            self,
            automaton0,
            automaton1,
            buffer_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a buffered simulation equivalence game."""
        self._init_buffer(buffer_size)
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            remove_dead_states=remove_dead_states,
        )

    def solve(self):
        """Solve the game by on-the-fly attractor iteration."""
        alphabet = tuple(FiniteAutomata.alphabet)
        all_attractor_nodes: set[Position] = set()
        new_attractor_nodes: set[Position] = set()
        seen_player2_nodes_not_in_attractor = TwoWaySetMap()

        initial_state0 = next(iter(self.initials[0]))
        initial_state1 = next(iter(self.initials[1]))
        initial_position: Position = (-1, "", -1, -1, INITIAL)

        def _make_position(
                state_pair: tuple[int, int],
                buffer_word: str,
                direction: int,
                phase: int,
        ) -> Position:
            """Create a compact hashable game position."""
            return (
                state_pair[0],
                buffer_word,
                state_pair[1],
                direction,
                phase,
            )

        def _add_attractor_node(position: Position) -> bool:
            """Add a position and report whether it is the initial position."""
            if position in all_attractor_nodes:
                return False
            all_attractor_nodes.add(position)
            new_attractor_nodes.add(position)
            return position == initial_position

        def _acceptance_matches(
                state_pair: tuple[int, int],
                direction: int,
        ) -> bool:
            """Check the directional acceptance condition."""
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
            """Return letters without a response from the comparison state."""
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
            """Yield all nonempty bounded buffer words with a given prefix."""
            for length in range(1, self.buffer_size + 1):
                for suffix in product(alphabet, repeat=length - 1):
                    yield first_letter + ''.join(suffix)

        def _initial_attractor_nodes() -> bool:
            """Add all immediately winning Player-I positions.

            Initial winning positions are the initial acceptance mismatch,
            illegal flushes, flushes without a response, and full consume
            positions without a response to their first buffered symbol.
            """
            initial_acceptance_mismatch = (
                (initial_state0 in self.finals[0])
                != (initial_state1 in self.finals[1])
            )
            if initial_acceptance_mismatch:
                return _add_attractor_node(initial_position)

            for state0 in self.states[0]:
                for state1 in self.states[1]:
                    state_pair = (state0, state1)
                    for direction in (0, 1):
                        active_state = state_pair[direction]

                        missing_letters = _missing_response_letters(
                            state_pair,
                            direction,
                        )
                        for first_letter in missing_letters:
                            for buffer_word in _buffer_words_starting_with(
                                    first_letter
                            ):
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

                        if active_state not in self.finals[direction]:
                            continue

                        if not _acceptance_matches(state_pair, direction):
                            if _add_attractor_node(
                                    _make_position(
                                        state_pair,
                                        "",
                                        direction,
                                        FLUSH,
                                    )
                            ):
                                return True

                        for first_letter in missing_letters:
                            for buffer_word in _buffer_words_starting_with(
                                    first_letter
                            ):
                                if _add_attractor_node(
                                        _make_position(
                                            state_pair,
                                            buffer_word,
                                            direction,
                                            FLUSH,
                                        )
                                ):
                                    return True

            return False

        def _add_player_i_predecessor(position: Position) -> bool:
            """Add Player-I predecessors of an attractor position.

            Player I chooses an active transition from a non-full ``CONSUME``
            position. The resulting position may be a ``CONSUME`` or
            ``FLUSH`` position, subject to the acceptance condition for
            ``FLUSH``.
            """
            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)

            if phase == CONSUME and not buffer_word and (
                    state_pair == (initial_state0, initial_state1)
            ):
                if _add_attractor_node(initial_position):
                    return True

            if phase not in (CONSUME, FLUSH) or not buffer_word:
                return False

            if phase == FLUSH and state_pair[direction] not in self.finals[direction]:
                return False

            last_letter = buffer_word[-1]
            predecessor_buffer = buffer_word[:-1]
            if len(predecessor_buffer) >= self.buffer_size:
                return False

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
                    CONSUME,
                )
                if _add_attractor_node(predecessor):
                    return True

            return False

        @cache
        def _player_ii_successors(
                candidate: Position,
        ) -> frozenset[Position] | None:
            """Enumerate Player-II successors.

            ``None`` denotes a successful terminal ``FLUSH`` for Player II,
            whereas an empty set denotes an immediate Player-I win because
            no response exists.
            """
            state0, buffer_word, state1, direction, phase = candidate
            state_pair = (state0, state1)

            if phase == CONSUME and len(buffer_word) != self.buffer_size:
                return frozenset()

            if phase == FLUSH and not buffer_word:
                return (
                    None
                    if _acceptance_matches(state_pair, direction)
                    else frozenset()
                )

            if phase not in (CONSUME, FLUSH) or not buffer_word:
                return frozenset()

            first_letter = buffer_word[0]
            remaining_word = buffer_word[1:]
            response_states = self._successors(
                1 - direction,
                state_pair[1 - direction],
                first_letter,
            )
            successors: set[Position] = set()
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
                        CONSUME if phase == CONSUME else FLUSH,
                    )
                )
            return frozenset(successors)

        def _add_player_ii_predecessor(position: Position) -> bool:
            """Add Player-II predecessors of an attractor position."""
            state0, buffer_word, state1, direction, phase = position
            state_pair = (state0, state1)

            def _consider(candidate: Position) -> bool:
                """Apply the universal predecessor rule."""
                if (
                        candidate in all_attractor_nodes
                        or seen_player2_nodes_not_in_attractor.has_key(candidate)
                ):
                    return False

                successors = _player_ii_successors(candidate)
                if successors is None:
                    return False
                if not successors:
                    return _add_attractor_node(candidate)

                unresolved = {
                    successor
                    for successor in successors
                    if successor not in all_attractor_nodes
                }
                if not unresolved:
                    return _add_attractor_node(candidate)

                seen_player2_nodes_not_in_attractor.add_many(
                    candidate,
                    unresolved,
                )
                return False

            if phase not in (CONSUME, FLUSH):
                return False

            if phase == CONSUME and len(buffer_word) != self.buffer_size - 1:
                return False

            if phase == FLUSH and len(buffer_word) >= self.buffer_size:
                return False

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
                    if _consider(predecessor):
                        return True

            return False

        if _initial_attractor_nodes():
            return False, "The automatons are not buffered simulation equivalent"

        while new_attractor_nodes:
            current_frontier = new_attractor_nodes.copy()
            new_attractor_nodes.clear()

            for position in current_frontier:
                ready_player2_nodes = (
                    seen_player2_nodes_not_in_attractor
                    .remove_value_everywhere(position)
                )
                for player2_node in ready_player2_nodes:
                    if _add_attractor_node(player2_node):
                        return False, "The automatons are not buffered simulation equivalent"

                if _add_player_i_predecessor(position):
                    return False, "The automatons are not buffered simulation equivalent"

                if _add_player_ii_predecessor(position):
                    return False, "The automatons are not buffered simulation equivalent"

        return True, "The automatons are buffered simulation equivalent"
