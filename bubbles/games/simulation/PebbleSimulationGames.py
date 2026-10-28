"""Restarting pebble simulation game."""

from functools import cache
from itertools import combinations

from wofa import FiniteAutomata

from ...util.TwoWaySetMap import TwoWaySetMap
from .SimulationGames import SimulationGames


CHOICE = 0

Position = tuple[int, int, frozenset[int], int | str]


class PebbleSimulationGames(SimulationGames):
    """Solve the newly defined restarting pebble simulation game.

    Positions have the formal shape
    ``(direction, active_state, pebble_states, phase)``. The pebble set is
    represented by a ``frozenset`` so positions remain hashable and can be
    used by the on-the-fly attractor solver.
    """

    def __init__(
            self,
            automaton0: FiniteAutomata,
            automaton1: FiniteAutomata,
            pebble_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a pebble simulation game."""
        if pebble_size < 1:
            raise ValueError("Pebble size must be at least 1.")

        self.pebble_size = pebble_size
        self._pebble_sets_cache = {}
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            remove_dead_states=remove_dead_states,
        )

    def set_pebble_size(self, pebble_size: int):
        """Set the maximum number of pebbles used by subsequent solves."""
        if pebble_size < 1:
            raise ValueError("Pebble size must be at least 1.")
        self.pebble_size = pebble_size

    def _get_pebble_sets(self, automaton_index: int):
        """Return cached nonempty pebble sets for the current size bound."""
        cache_key = (automaton_index, self.pebble_size)
        if cache_key not in self._pebble_sets_cache:
            states = tuple(self.states[automaton_index])
            self._pebble_sets_cache[cache_key] = tuple(
                frozenset(pebble_set)
                for size in range(
                    1,
                    min(self.pebble_size, len(states)) + 1,
                )
                for pebble_set in combinations(states, size)
            )
        return self._pebble_sets_cache[cache_key]

    def solve(self):
        """Solve the restarting pebble simulation game by attractor iteration."""
        alphabet = tuple(FiniteAutomata.alphabet)
        all_attractor_nodes: set[Position] = set()
        new_attractor_nodes: set[Position] = set()
        seen_player2_nodes_not_in_attractor = TwoWaySetMap()

        initial_state0 = next(iter(self.initials[0]))
        initial_state1 = next(iter(self.initials[1]))
        initial_state_pair = (initial_state0, initial_state1)
        initial_position = (
            0,
            initial_state0,
            frozenset({initial_state1}),
            CHOICE,
        )

        def _make_position(
                direction: int,
                active_state: int,
                pebble_states: frozenset[int],
                phase: int | str,
        ) -> Position:
            """Create a hashable pebble-game position."""
            return direction, active_state, pebble_states, phase

        def _add_attractor_node(position: Position) -> bool:
            """Add a position and report whether it is the initial position."""
            if position in all_attractor_nodes:
                return False

            all_attractor_nodes.add(position)
            new_attractor_nodes.add(position)
            return position == initial_position

        @cache
        def _acceptance_matches(
                direction: int,
                active_state: int,
                pebble_states: frozenset[int],
        ) -> bool:
            """Check the directional acceptance condition of a Choice node."""
            return (
                active_state not in self.finals[direction]
                or any(
                    state in self.finals[1 - direction]
                    for state in pebble_states
                )
            )

        def _pebble_sets(automaton_index: int):
            """Return all nonempty pebble sets allowed by the size bound."""
            return self._get_pebble_sets(automaton_index)

        @cache
        def _response_states(
                direction: int,
                pebble_states: frozenset[int],
                letter: str,
        ) -> frozenset[int]:
            """Return the union of all pebble successors for one letter."""
            return frozenset(
                successor
                for state in pebble_states
                for successor in self._successors(
                    1 - direction,
                    state,
                    letter,
                )
            )

        def _initial_attractor_nodes() -> bool:
            """Add all immediately winning pebble-game positions.

            The initial attractor contains Choice positions that violate the
            directional acceptance condition and Move positions for which the
            union of all possible pebble responses is empty.

            Returns:
                ``True`` if the actual initial position is added.
            """
            for direction in (0, 1):
                response_automaton_index = 1 - direction
                for active_state in self.states[direction]:
                    for pebble_states in _pebble_sets(response_automaton_index):
                        if not _acceptance_matches(
                                direction,
                                active_state,
                                pebble_states,
                        ):
                            if _add_attractor_node(
                                    _make_position(
                                        direction,
                                        active_state,
                                        pebble_states,
                                        CHOICE,
                                    )
                            ):
                                return True

                        for letter in alphabet:
                            if not _response_states(
                                    direction,
                                    pebble_states,
                                    letter,
                            ):
                                if _add_attractor_node(
                                        _make_position(
                                            direction,
                                            active_state,
                                            pebble_states,
                                            letter,
                                        )
                                ):
                                    return True

            return False

        def _add_player_i_predecessor(position: Position) -> bool:
            """Add Player-I predecessors of an attractor position.

            Player I controls ``CHOICE`` positions and may either choose a
            transition in the active automaton or restart in the opposite
            direction. Therefore this helper handles two predecessor forms:

            * reverse a symbol transition into a ``MOVE`` position, and
            * reverse a restart into an initial ``CHOICE`` position.

            Every generated predecessor is added through
            ``_add_attractor_node`` so that the actual initial position is
            detected immediately.

            Returns:
                ``True`` if a generated predecessor is the initial position.
            """
            direction, active_state, pebble_states, phase = position

            # A symbol phase is a Player-II position reached after Player I
            # selected a symbol and an active-automaton transition.
            if phase != CHOICE:
                for predecessor_state in self._predecessors(
                        direction,
                        active_state,
                        phase,
                ):
                    predecessor = _make_position(
                        direction,
                        predecessor_state,
                        pebble_states,
                        CHOICE,
                    )
                    if _add_attractor_node(predecessor):
                        return True
                return False

            # A restart always targets the initial Choice position in the
            # selected direction. Reverse that edge for all possible active
            # states and pebble sets in the opposite direction.
            target_initial_position = _make_position(
                direction,
                initial_state_pair[direction],
                frozenset({initial_state_pair[1 - direction]}),
                CHOICE,
            )
            if position != target_initial_position:
                return False

            predecessor_direction = 1 - direction
            for predecessor_state in self.states[predecessor_direction]:
                for predecessor_pebble_states in _pebble_sets(direction):
                    predecessor = _make_position(
                        predecessor_direction,
                        predecessor_state,
                        predecessor_pebble_states,
                        CHOICE,
                    )
                    if _add_attractor_node(predecessor):
                        return True

            return False

        @cache
        def _player_ii_successors(position: Position) -> frozenset[Position]:
            """Enumerate all legal successors of a Player-II ``MOVE`` node.

            For a move position with symbol ``a``, Player II may select every
            nonempty subset of the union of all pebble successors whose size
            does not exceed ``self.pebble_size``.
            """
            direction, active_state, pebble_states, phase = position
            if phase == CHOICE:
                return frozenset()

            response_states = _response_states(
                direction,
                pebble_states,
                phase,
            )
            successors: set[Position] = set()
            response_states_tuple = tuple(response_states)

            for size in range(
                    1,
                    min(self.pebble_size, len(response_states_tuple)) + 1,
            ):
                for selected_states in combinations(response_states_tuple, size):
                    successors.add(
                        _make_position(
                            direction,
                            active_state,
                            frozenset(selected_states),
                            CHOICE,
                        )
                    )

            return frozenset(successors)

        def _add_player_ii_predecessor(position: Position) -> bool:
            """Add Player-II predecessors whose every response is losing."""
            if position[3] != CHOICE:
                return False

            direction, active_state, target_pebble_states, _ = position

            def _consider_candidate(candidate: Position) -> bool:
                """Apply the universal predecessor rule to one Move node."""
                if (
                        candidate in all_attractor_nodes
                        or seen_player2_nodes_not_in_attractor.has_key(candidate)
                ):
                    return False

                successors = _player_ii_successors(candidate)
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

            # A Move node has the same direction and active state as its
            # Choice successor. Its symbol and previous pebble set are
            # enumerated backwards; the target pebble set must be one of its
            # legal nonempty responses.
            response_automaton_index = 1 - direction
            for letter in alphabet:
                for predecessor_pebble_states in _pebble_sets(
                        response_automaton_index
                ):
                    candidate = _make_position(
                        direction,
                        active_state,
                        predecessor_pebble_states,
                        letter,
                    )
                    candidate_response_states = _response_states(
                        direction,
                        predecessor_pebble_states,
                        letter,
                    )
                    if not target_pebble_states.issubset(candidate_response_states):
                        continue
                    if _consider_candidate(candidate):
                        return True

            return False

        def _propagate_new_attractor_nodes() -> bool:
            """Discharge Player-II obligations for newly added positions."""
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

        if _initial_attractor_nodes():
            return False, "The automatons are not pebble simulation equivalent"

        while new_attractor_nodes:
            current_frontier = new_attractor_nodes.copy()
            new_attractor_nodes.clear()

            for position in current_frontier:
                ready_player2_nodes = seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    position
                )
                for player2_node in ready_player2_nodes:
                    if _add_attractor_node(player2_node):
                        return False, "The automatons are not pebble simulation equivalent"

                if _add_player_i_predecessor(position):
                    return False, "The automatons are not pebble simulation equivalent"

                if _add_player_ii_predecessor(position):
                    return False, "The automatons are not pebble simulation equivalent"

            if _propagate_new_attractor_nodes():
                return False, "The automatons are not pebble simulation equivalent"

        return True, "The automatons are pebble simulation equivalent"
