"""Additional behavioral tests for buffered bisimulation games."""

import unittest

from wofa import FiniteAutomata

from bubbles import BufferedBisimulationGames


def _automaton(transitions, finals, alphabet=('a', 'b')) -> FiniteAutomata:
    """Build a one-initial-state automaton for a test case."""
    FiniteAutomata.set_alphabet(set(alphabet))
    return FiniteAutomata(
        initials={0},
        transitions=transitions,
        finals=set(finals),
    )


def _solve(transitions0, finals0, transitions1, finals1, buffer_size):
    """Construct and solve one buffered bisimulation test instance."""
    game = BufferedBisimulationGames(
        automaton0=_automaton(transitions0, finals0),
        automaton1=_automaton(transitions1, finals1),
        buffer_size=buffer_size,
    )
    return game.solve()[0]


class BufferedBisimulationBehaviorTest(unittest.TestCase):
    """Validate core rules of the revised buffered game."""

    def test_identical_automata_are_buffered_bisimilar(self):
        """Identical NFAs must be equivalent for every tested buffer size."""
        transitions = [(0, 'a', 1), (1, 'a', 1), (1, 'b', 1)]
        for buffer_size in range(1, 4):
            with self.subTest(buffer_size=buffer_size):
                self.assertTrue(
                    _solve(
                        transitions,
                        {1},
                        transitions,
                        {1},
                        buffer_size,
                    )
                )

    def test_language_difference_is_rejected_for_every_buffer_size(self):
        """A word accepted by only one automaton cannot be buffered bisimilar."""
        for buffer_size in range(1, 4):
            with self.subTest(buffer_size=buffer_size):
                self.assertFalse(
                    _solve(
                        [(0, 'a', 1)],
                        {0, 1},
                        [],
                        {0},
                        buffer_size,
                    )
                )

    def test_missing_player_ii_response_is_immediate_loss(self):
        """A missing response transition must make Player I win."""
        self.assertFalse(
            _solve(
                [(0, 'a', 1)],
                {0, 1},
                [],
                {0},
                buffer_size=1,
            )
        )

    def test_unproductive_dead_branch_is_removed_during_preparation(self):
        """Language-preserving dead branches do not affect the cleaned game."""
        automaton0 = _automaton(
            [(0, 'a', 1), (0, 'b', 2)],
            {0, 1},
        )
        automaton1 = _automaton(
            [(0, 'a', 1)],
            {0, 1},
        )
        game = BufferedBisimulationGames(automaton0, automaton1, buffer_size=1)
        prepared0, prepared1 = game.get_automatons().values()

        self.assertEqual(prepared0.get_transitions(), prepared1.get_transitions())
        self.assertTrue(game.solve()[0])


if __name__ == '__main__':
    unittest.main()
