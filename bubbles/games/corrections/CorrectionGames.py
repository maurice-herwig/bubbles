"""Common infrastructure for correction games."""

from abc import abstractmethod

from wofa import FiniteAutomata

from ..Games import Games


Correction = tuple[
    frozenset[int],
    frozenset[tuple[int, str, int]],
    frozenset[tuple[int, str, int]],
    frozenset[int],
]


class CorrectionGames(Games):
    """Base class shared by all correction game implementations.

    Correction games extend the first automaton during a play. Concrete
    subclasses define the game-specific positions and moves, while this class
    will contain the common correction representation and operations.
    """

    def __init__(
            self,
            automaton0,
            automaton1,
            correction_size: int,
            remove_dead_states: bool = True,
    ):
        """Initialize a correction game with a bounded correction budget.

        Args:
            correction_size: Maximum number of correction operations.
            remove_dead_states: Whether to remove unproductive states during
                automaton preparation.
        """
        if correction_size < 0:
            raise ValueError("Correction size must be non-negative.")

        self.correction_size = correction_size
        self.empty_correction: Correction = (
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
        )
        super().__init__(
            automaton0=automaton0,
            automaton1=automaton1,
            remove_dead_states=remove_dead_states,
        )

        self.base_state_count = self.automatons[0].get_number_of_states()
        self._base_automaton0 = self._copy_automaton(self.automatons[0])
        self._base_automaton1 = self._copy_automaton(self.automatons[1])

    @staticmethod
    def _copy_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
        """Return an isolated copy of an automaton."""
        return FiniteAutomata(
            initials=set(automaton.get_initials()),
            transitions=list(automaton.get_transitions()),
            finals=set(automaton.get_finals()),
        )

    @staticmethod
    def _correction_size_of(correction: Correction) -> int:
        """Return the number of operations contained in ``correction``."""
        return sum(len(component) for component in correction)

    @staticmethod
    def _contains_only_unused_states(correction: Correction) -> bool:
        """Return whether ``correction`` only inserts currently unused states.

        Such a correction has no effect on the language or on a simulation
        game yet. It must still be retained as a search predecessor because a
        later extension may add a transition to one of the states.
        """
        inserted_states, inserted_transitions, deleted_transitions, toggled_states = correction
        return bool(inserted_states) and not (
            inserted_transitions or deleted_transitions or toggled_states
        )

    @staticmethod
    def _extend_correction(
            correction: Correction,
            *,
            inserted_states=frozenset(),
            inserted_transitions=frozenset(),
            deleted_transitions=frozenset(),
            toggled_states=frozenset(),
    ) -> Correction:
        """Return ``correction`` extended by the supplied operations."""
        current_states, current_insertions, current_deletions, current_toggles = correction
        return (
            current_states | frozenset(inserted_states),
            current_insertions | frozenset(inserted_transitions),
            current_deletions | frozenset(deleted_transitions),
            current_toggles | frozenset(toggled_states),
        )

    def _current_states(self, correction: Correction) -> frozenset[int]:
        """Return base and already inserted states of a correction."""
        return frozenset(self.states[0] | set(correction[0]))

    def _base_transitions(self) -> frozenset[tuple[int, str, int]]:
        """Return the transitions of the prepared first automaton."""
        return frozenset(self.automatons[0].get_transitions())

    def _correction_extensions(
            self,
            correction: Correction,
    ) -> dict[int, set[Correction]]:
        """Return valid one- and two-operation correction extensions.

        One-operation extensions are placed in the next correction layer.
        Additionally, inserting a state together with a transition incident
        to that state is generated directly in the layer after next. The
        intermediate state-only correction is still generated separately.
        """
        current_size = self._correction_size_of(correction)
        extensions: dict[int, set[Correction]] = {}

        def _add(target_size: int, extension: Correction):
            """Add an extension to its target layer if it fits the budget."""
            if target_size <= self.correction_size:
                extensions.setdefault(target_size, set()).add(extension)

        next_size = current_size + 1
        if next_size > self.correction_size:
            return extensions

        inserted_states, inserted_transitions, deleted_transitions, toggled_states = correction
        base_transitions = self._base_transitions()
        current_states = self._current_states(correction)

        if len(inserted_states) < self.correction_size:
            # New states are indistinguishable up to renaming. We therefore
            # use consecutive identifiers and only generate the next one.
            state = self.base_state_count + len(inserted_states)
            extension = self._extend_correction(
                correction,
                inserted_states={state},
            )
            _add(next_size, extension)

            if current_size + 2 <= self.correction_size:
                states_after_insertion = current_states | {state}
                for transition in self._possible_inserted_transitions(
                        states_after_insertion,
                        base_transitions,
                        inserted_transitions,
                ):
                    extension = self._extend_correction(
                        correction,
                        inserted_states={state},
                        inserted_transitions={transition},
                    )
                    _add(current_size + 2, extension)

        for transition in sorted(
                self._possible_inserted_transitions(
                    current_states,
                    base_transitions,
                    inserted_transitions,
                )
        ):
            extension = self._extend_correction(
                correction,
                inserted_transitions={transition},
            )
            _add(next_size, extension)

        for transition in sorted(base_transitions - deleted_transitions):
            extension = self._extend_correction(
                correction,
                deleted_transitions={transition},
            )
            _add(next_size, extension)

        for state in sorted(current_states - toggled_states):
            extension = self._extend_correction(
                correction,
                toggled_states={state},
            )
            _add(next_size, extension)

        return extensions

    @staticmethod
    def _possible_inserted_transitions(
            states: frozenset[int] | set[int],
            base_transitions: frozenset[tuple[int, str, int]],
            inserted_transitions: frozenset[tuple[int, str, int]],
    ) -> set[tuple[int, str, int]]:
        """Return transitions that may be inserted between current states."""
        existing_transitions = base_transitions | inserted_transitions
        return {
            (source, letter, target)
            for source in states
            for letter in FiniteAutomata.alphabet
            for target in states
            if (source, letter, target) not in existing_transitions
        }

    def _apply_correction(self, correction: Correction) -> FiniteAutomata:
        """Apply ``correction`` to a fresh copy of the prepared first NFA."""
        inserted_states, inserted_transitions, deleted_transitions, toggled_states = correction
        base_transitions = set(self._base_automaton0.get_transitions())
        transitions = (base_transitions - set(deleted_transitions)) | set(
            inserted_transitions
        )
        finals = set(self._base_automaton0.get_finals()) ^ set(toggled_states)
        return FiniteAutomata(
            initials=set(self._base_automaton0.get_initials()),
            transitions=list(transitions),
            finals=finals,
        )

    @abstractmethod
    def _solve_corrected_automaton(self, automaton: FiniteAutomata) -> bool:
        """Return whether Player II wins on a corrected first automaton."""
        pass

    def solve(self) -> tuple[bool, Correction | None]:
        """Search breadth-first for a correction accepted by the game.

        Corrections are tested in increasing order of their size. A correction
        generated by inserting a state and an incident transition may be
        placed directly in the layer two operations larger than its parent.
        """
        layers: dict[int, set[Correction]] = {
            size: set() for size in range(self.correction_size + 1)
        }
        layers[0].add(self.empty_correction)
        visited = {self.empty_correction}

        for size in range(self.correction_size + 1):
            for correction in layers[size]:
                if not self._contains_only_unused_states(correction):
                    corrected_automaton = self._apply_correction(correction)
                    if self._solve_corrected_automaton(corrected_automaton):
                        return True, correction

                if size == self.correction_size:
                    continue

                for target_size, extensions in self._correction_extensions(
                        correction
                ).items():
                    for extension in extensions:
                        if extension in visited:
                            continue
                        visited.add(extension)
                        layers[target_size].add(extension)

        return False, None
