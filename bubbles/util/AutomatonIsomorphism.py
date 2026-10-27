"""State-renaming isomorphism checks for finite automata."""

from collections import Counter

from wofa import FiniteAutomata


def _relations(automaton: FiniteAutomata):
    """Build labeled successor and predecessor relations for all states."""
    number_of_states = automaton.get_number_of_states()
    labels = {
        label
        for _, label, _ in automaton.get_transitions()
    }
    successors = {
        state: {label: set() for label in labels}
        for state in range(number_of_states)
    }
    predecessors = {
        state: {label: set() for label in labels}
        for state in range(number_of_states)
    }

    for source, label, target in automaton.get_transitions():
        successors[source].setdefault(label, set()).add(target)
        predecessors[target].setdefault(label, set()).add(source)

    return labels, successors, predecessors


def _refined_state_colors(automaton0: FiniteAutomata, automaton1: FiniteAutomata):
    """Refine state colors jointly for two labeled automaton graphs."""
    labels0, successors0, predecessors0 = _relations(automaton0)
    labels1, successors1, predecessors1 = _relations(automaton1)
    labels = labels0 | labels1
    ordered_labels = tuple(sorted(labels, key=repr))

    states0 = range(automaton0.get_number_of_states())
    states1 = range(automaton1.get_number_of_states())
    initials0 = set(automaton0.get_initials())
    initials1 = set(automaton1.get_initials())
    finals0 = set(automaton0.get_finals())
    finals1 = set(automaton1.get_finals())

    base0 = {
        state: (
            state in initials0,
            state in finals0,
            tuple(len(successors0[state].get(label, set())) for label in ordered_labels),
            tuple(len(predecessors0[state].get(label, set())) for label in ordered_labels),
        )
        for state in states0
    }
    base1 = {
        state: (
            state in initials1,
            state in finals1,
            tuple(len(successors1[state].get(label, set())) for label in ordered_labels),
            tuple(len(predecessors1[state].get(label, set())) for label in ordered_labels),
        )
        for state in states1
    }

    def _compress(signatures0, signatures1):
        """Assign shared integer colors to equal signatures."""
        signatures = set(signatures0.values()) | set(signatures1.values())
        color_ids = {
            signature: index
            for index, signature in enumerate(sorted(signatures, key=repr))
        }
        return (
            {state: color_ids[signature] for state, signature in signatures0.items()},
            {state: color_ids[signature] for state, signature in signatures1.items()},
        )

    colors0, colors1 = _compress(base0, base1)

    while True:
        signatures0 = {
            state: (
                colors0[state],
                tuple(
                    (
                        label,
                        tuple(sorted(
                            (colors0[target] for target in successors0[state].get(label, set())),
                        )),
                    )
                    for label in ordered_labels
                ),
                tuple(
                    (
                        label,
                        tuple(sorted(
                            (colors0[source] for source in predecessors0[state].get(label, set())),
                        )),
                    )
                    for label in ordered_labels
                ),
            )
            for state in states0
        }
        signatures1 = {
            state: (
                colors1[state],
                tuple(
                    (
                        label,
                        tuple(sorted(
                            (colors1[target] for target in successors1[state].get(label, set())),
                        )),
                    )
                    for label in ordered_labels
                ),
                tuple(
                    (
                        label,
                        tuple(sorted(
                            (colors1[source] for source in predecessors1[state].get(label, set())),
                        )),
                    )
                    for label in ordered_labels
                ),
            )
            for state in states1
        }
        refined0, refined1 = _compress(signatures0, signatures1)

        if refined0 == colors0 and refined1 == colors1:
            return labels0, labels1, successors0, successors1, predecessors0, predecessors1, colors0, colors1

        colors0, colors1 = refined0, refined1


def _is_compatible(
        source_state: int,
        target_state: int,
        mapping: dict[int, int],
        inverse_mapping: dict[int, int],
        successors0: dict[int, dict],
        successors1: dict[int, dict],
        predecessors0: dict[int, dict],
        predecessors1: dict[int, dict],
) -> bool:
    """Check all already determined edge constraints for a candidate pair."""
    for label, targets in successors0[source_state].items():
        for source_target in targets:
            if source_target in mapping and mapping[source_target] not in successors1[target_state].get(label, set()):
                return False

    for label, sources in predecessors0[source_state].items():
        for source_source in sources:
            if source_source in mapping and mapping[source_source] not in predecessors1[target_state].get(label, set()):
                return False

    for label, targets in successors1[target_state].items():
        for target_target in targets:
            if target_target in inverse_mapping and inverse_mapping[target_target] not in successors0[source_state].get(label, set()):
                return False

    for label, sources in predecessors1[target_state].items():
        for target_source in sources:
            if target_source in inverse_mapping and inverse_mapping[target_source] not in predecessors0[source_state].get(label, set()):
                return False

    return True


def _fully_matches(
        mapping: dict[int, int],
        successors0: dict[int, dict],
        successors1: dict[int, dict],
) -> bool:
    """Check that a complete mapping preserves every labeled transition."""
    for source_state, labels in successors0.items():
        mapped_source = mapping[source_state]
        for label, targets in labels.items():
            mapped_targets = {
                mapping[target]
                for target in targets
            }
            if mapped_targets != successors1[mapped_source].get(label, set()):
                return False

    return True


def are_isomorphic(automaton0: FiniteAutomata, automaton1: FiniteAutomata) -> bool:
    """Return whether two automata differ only by a state renaming.

    Initial states, final states, and labeled nondeterministic transition
    relations must all be preserved by the bijection. State numbers and their
    ordering are ignored.
    """
    if automaton0.get_number_of_states() != automaton1.get_number_of_states():
        return False

    (
        labels0,
        labels1,
        successors0,
        successors1,
        predecessors0,
        predecessors1,
        colors0,
        colors1,
    ) = _refined_state_colors(automaton0, automaton1)
    if labels0 != labels1:
        return False

    if Counter(colors0.values()) != Counter(colors1.values()):
        return False

    candidates = {
        source_state: [
            target_state
            for target_state, target_color in colors1.items()
            if colors0[source_state] == target_color
        ]
        for source_state in colors0
    }

    mapping: dict[int, int] = {}
    inverse_mapping: dict[int, int] = {}

    def _search() -> bool:
        """Backtrack over color-compatible bijections."""
        if len(mapping) == len(colors0):
            return _fully_matches(mapping, successors0, successors1)

        unassigned_source_states = [
            source_state
            for source_state in colors0
            if source_state not in mapping
        ]

        source_state = min(
            unassigned_source_states,
            key=lambda state: sum(
                candidate not in inverse_mapping
                for candidate in candidates[state]
            ),
        )

        for target_state in candidates[source_state]:
            if target_state in inverse_mapping:
                continue
            if not _is_compatible(
                    source_state,
                    target_state,
                    mapping,
                    inverse_mapping,
                    successors0,
                    successors1,
                    predecessors0,
                    predecessors1,
            ):
                continue

            mapping[source_state] = target_state
            inverse_mapping[target_state] = source_state
            if _search():
                return True
            del mapping[source_state]
            del inverse_mapping[target_state]

        return False

    return _search()
