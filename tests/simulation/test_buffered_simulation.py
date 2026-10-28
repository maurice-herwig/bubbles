"""Tests for the buffered simulation game scaffold."""

import unittest

from wofa import FiniteAutomata

from bubbles import BufferedSimulationGames, SimulationGames
from bubbles.games.simulation.BufferedSimulationGames import (
    CHOICE,
    CONSUME,
    FLUSH,
    Position,
)


class BufferedSimulationScaffoldTest(unittest.TestCase):
    """Validate the currently implemented simulation-game infrastructure."""

    def setUp(self):
        FiniteAutomata.set_alphabet({'a'})

        self.automaton0 = FiniteAutomata(
            initials={0},
            transitions=[(0, 'a', 1)],
            finals={1},
        )
        self.automaton1 = FiniteAutomata(
            initials={0},
            transitions=[(0, 'a', 1)],
            finals={1},
        )

    def test_position_definition_uses_formal_order(self):
        """Positions contain both states, buffer, direction, and phase."""
        position: Position = (0, "a", 1, 0, CONSUME)
        self.assertEqual(position, (0, "a", 1, 0, 1))
        self.assertEqual((CHOICE, CONSUME, FLUSH), (0, 1, 2))

    def test_game_inherits_simulation_infrastructure(self):
        """Buffered simulation uses the shared simulation base class."""
        game = BufferedSimulationGames(
            self.automaton0,
            self.automaton1,
            buffer_size=2,
        )
        self.assertIsInstance(game, SimulationGames)
        self.assertEqual(game.buffer_size, 2)
        self.assertEqual(game.initials[0], {0})
        self.assertEqual(game.initials[1], {0})

    def test_buffer_size_must_be_positive(self):
        """The buffer capacity must be at least one."""
        with self.assertRaises(ValueError):
            BufferedSimulationGames(
                self.automaton0,
                self.automaton1,
                buffer_size=0,
            )

        game = BufferedSimulationGames(
            self.automaton0,
            self.automaton1,
            buffer_size=1,
        )
        game.set_buffer_size(2)
        self.assertEqual(game.buffer_size, 2)
        with self.assertRaises(ValueError):
            game.set_buffer_size(0)

    def test_initial_acceptance_violation_is_rejected(self):
        """An accepting active initial state must be matched immediately."""
        accepting_initial = FiniteAutomata(
            initials={0},
            transitions=[(0, 'a', 1)],
            finals={0, 1},
        )
        nonaccepting_initial = FiniteAutomata(
            initials={0},
            transitions=[(0, 'a', 1)],
            finals={1},
        )
        game = BufferedSimulationGames(
            accepting_initial,
            nonaccepting_initial,
            buffer_size=1,
        )
        self.assertFalse(game.solve()[0])

    def test_noninitial_missing_response_reaches_full_consume_case(self):
        """Missing responses are also detected at noninitial state pairs."""
        automaton0 = FiniteAutomata(
            initials={0},
            transitions=[
                (0, 'a', 1),
                (0, 'b', 2),
                (1, 'a', 2),
                (2, 'a', 2),
                (2, 'b', 2),
            ],
            finals={2},
        )
        automaton1 = FiniteAutomata(
            initials={0},
            transitions=[
                (0, 'a', 1),
                (0, 'b', 2),
                (1, 'b', 2),
                (2, 'a', 2),
                (2, 'b', 2),
            ],
            finals={2},
        )
        game = BufferedSimulationGames(
            automaton0,
            automaton1,
            buffer_size=1,
        )
        self.assertFalse(game.solve()[0])

    def test_identical_automata_are_buffered_simulation_equivalent(self):
        """Identical automata have matching responses in both directions."""
        game = BufferedSimulationGames(
            self.automaton0,
            self.automaton1,
            buffer_size=1,
        )
        equivalent, message = game.solve()
        self.assertTrue(equivalent)
        self.assertIn("buffered simulation equivalent", message)

    def test_missing_response_is_rejected(self):
        """A word accepted by only one automaton cannot be simulated."""
        rejecting = FiniteAutomata(
            initials={0},
            transitions=[],
            finals=set(),
        )
        game = BufferedSimulationGames(
            self.automaton0,
            rejecting,
            buffer_size=1,
        )
        equivalent, message = game.solve()
        self.assertFalse(equivalent)
        self.assertIn("not buffered simulation equivalent", message)

    def test_buffered_solver_handles_multiple_buffer_sizes(self):
        """The predecessor rules work for both one and two buffered symbols."""
        for buffer_size in (1, 2):
            game = BufferedSimulationGames(
                FiniteAutomata(
                    initials={0},
                    transitions=[(0, 'a', 1), (1, 'a', 2)],
                    finals={2},
                ),
                FiniteAutomata(
                    initials={0},
                    transitions=[(0, 'a', 1), (1, 'a', 2)],
                    finals={2},
                ),
                buffer_size=buffer_size,
            )
            self.assertTrue(game.solve()[0])

    def test_dead_state_flag_is_forwarded_to_shared_preparation(self):
        """Buffered simulation can preserve unproductive transitions."""
        FiniteAutomata.set_alphabet({'a', 'b'})
        game = BufferedSimulationGames(
            FiniteAutomata(
                initials={0},
                transitions=[(0, 'a', 1), (0, 'b', 2)],
                finals={2},
            ),
            FiniteAutomata(
                initials={0},
                transitions=[(0, 'b', 1)],
                finals={1},
            ),
            buffer_size=1,
            remove_dead_states=False,
        )
        self.assertEqual(
            game.get_automatons()[0].get_transitions(),
            [(0, 'a', 1), (0, 'b', 2)],
        )


if __name__ == '__main__':
    unittest.main()
