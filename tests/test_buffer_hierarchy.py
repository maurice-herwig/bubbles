"""Tests for the strict buffered-bisimulation hierarchy witness."""

import unittest

from wofa import FiniteAutomata

from bubbles import BufferedBisimulationGames


def _build_buffer_hierarchy_automaton0(k: int) -> FiniteAutomata:
    """Build the left witness automaton from the formal hierarchy example."""
    final_state = k + 1
    transitions = [
        (state, 'a', state + 1)
        for state in range(k)
    ]
    transitions.extend([
        (k, 'b', final_state),
        (k, 'c', final_state),
    ])
    transitions.extend([
        (final_state, letter, final_state)
        for letter in ('a', 'b', 'c')
    ])

    return FiniteAutomata(
        initials={0},
        transitions=transitions,
        finals=set(range(final_state + 1)),
    )


def _build_buffer_hierarchy_automaton1(k: int) -> FiniteAutomata:
    """Build the right witness automaton from the formal hierarchy example."""
    branch_b_start = 1
    branch_c_start = k + 1
    final_state = 2 * k + 1

    transitions = [
        (0, 'a', branch_b_start),
        (0, 'a', branch_c_start),
    ]
    transitions.extend([
        (branch_b_start + offset, 'a', branch_b_start + offset + 1)
        for offset in range(k - 1)
    ])
    transitions.extend([
        (branch_c_start + offset, 'a', branch_c_start + offset + 1)
        for offset in range(k - 1)
    ])
    transitions.extend([
        (branch_b_start + k - 1, 'b', final_state),
        (branch_c_start + k - 1, 'c', final_state),
    ])
    transitions.extend([
        (final_state, letter, final_state)
        for letter in ('a', 'b', 'c')
    ])

    return FiniteAutomata(
        initials={0},
        transitions=transitions,
        finals=set(range(final_state + 1)),
    )


class BufferedHierarchyTest(unittest.TestCase):
    """Validate the strict separation between consecutive buffer sizes."""

    def test_formal_witness_separates_k_from_k_plus_one(self):
        """The formal witness is k-bisimilar exactly from k+1 onwards."""
        FiniteAutomata.set_alphabet({'a', 'b', 'c'})

        for k in range(1, 5):
            with self.subTest(k=k):
                game = BufferedBisimulationGames(
                    automaton0=_build_buffer_hierarchy_automaton0(k),
                    automaton1=_build_buffer_hierarchy_automaton1(k),
                    buffer_size=k,
                )
                prepared_automaton0, prepared_automaton1 = game.get_automatons().values()

                self.assertTrue(
                    prepared_automaton0.equivalence_test(other=prepared_automaton1)
                )
                self.assertFalse(game.solve()[0])

                game.set_buffer_size(k + 1)
                self.assertTrue(game.solve()[0])


if __name__ == '__main__':
    unittest.main()
