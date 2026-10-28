"""Tests for the restarting pebble simulation game."""

import unittest

from wofa import FiniteAutomata

from bubbles import PebbleSimulationGames


class PebbleSimulationTest(unittest.TestCase):
    """Validate basic pebble-game behavior and the formal hierarchy witness."""

    @staticmethod
    def _hierarchy_witness(k):
        """Build the formal k-versus-k+1 pebble witness."""
        symbols = [f'b{index}' for index in range(k + 1)]
        p_final = 2
        automaton0 = FiniteAutomata(
            initials={0},
            transitions=[
                (0, 'a', 1),
                *[(1, symbol, p_final) for symbol in symbols],
            ],
            finals={0, 1, p_final},
        )

        first_pebble = 1
        final_state = k + 2
        transitions1 = [
            (0, 'a', first_pebble + index)
            for index in range(k + 1)
        ]
        transitions1.extend(
            (first_pebble + index, symbol, final_state)
            for index, symbol in enumerate(symbols)
        )
        automaton1 = FiniteAutomata(
            initials={0},
            transitions=transitions1,
            finals=set(range(final_state + 1)),
        )
        return automaton0, automaton1, set(symbols) | {'a'}

    def test_identical_automata_are_pebble_simulation_equivalent(self):
        """Identical automata are equivalent with one pebble."""
        FiniteAutomata.set_alphabet({'a'})
        automaton0 = FiniteAutomata({0}, [(0, 'a', 1)], {1})
        automaton1 = FiniteAutomata({0}, [(0, 'a', 1)], {1})
        self.assertTrue(
            PebbleSimulationGames(automaton0, automaton1, 1).solve()[0]
        )

    def test_pebble_size_must_be_positive(self):
        """Pebble capacities must be positive."""
        FiniteAutomata.set_alphabet({'a'})
        automaton0 = FiniteAutomata({0}, [], {0})
        automaton1 = FiniteAutomata({0}, [], {0})
        with self.assertRaises(ValueError):
            PebbleSimulationGames(automaton0, automaton1, 0)

        game = PebbleSimulationGames(automaton0, automaton1, 1)
        game.set_pebble_size(2)
        self.assertEqual(game.pebble_size, 2)
        with self.assertRaises(ValueError):
            game.set_pebble_size(0)

    def test_different_languages_are_rejected(self):
        """A missing response makes Player I win."""
        FiniteAutomata.set_alphabet({'a'})
        accepting = FiniteAutomata({0}, [(0, 'a', 1)], {1})
        rejecting = FiniteAutomata({0}, [], set())
        self.assertFalse(
            PebbleSimulationGames(accepting, rejecting, 1).solve()[0]
        )

    def test_restart_predecessors_are_checked_in_both_directions(self):
        """A violation after a restart is propagated back to the start."""
        FiniteAutomata.set_alphabet({'a'})
        nonaccepting_initial = FiniteAutomata(
            {0},
            [(0, 'a', 1)],
            {1},
        )
        accepting_initial = FiniteAutomata(
            {0},
            [(0, 'a', 1)],
            {0, 1},
        )
        self.assertFalse(
            PebbleSimulationGames(
                nonaccepting_initial,
                accepting_initial,
                1,
            ).solve()[0]
        )

    def test_pebble_hierarchy_separates_k_from_k_plus_one(self):
        """The formal witness is not k-, but is k+1-pebble equivalent."""
        for k in (1, 2, 3):
            with self.subTest(k=k):
                automaton0, automaton1, alphabet = self._hierarchy_witness(k)
                FiniteAutomata.set_alphabet(alphabet)
                self.assertFalse(
                    PebbleSimulationGames(
                        automaton0,
                        automaton1,
                        k,
                    ).solve()[0]
                )
                automaton0, automaton1, _ = self._hierarchy_witness(k)
                self.assertTrue(
                    PebbleSimulationGames(
                        automaton0,
                        automaton1,
                        k + 1,
                    ).solve()[0]
                )


if __name__ == '__main__':
    unittest.main()
