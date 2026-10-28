"""Tests for the buffered simulation game scaffold."""

import unittest

from wofa import FiniteAutomata

from bubbles import (
    BufferedBisimulationGames,
    BufferedSimulationGames,
    SimulationGames,
)
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

    @staticmethod
    def _buffer_hierarchy_witness(k):
        """Build the formal witness separating simulation k from k+1."""
        final0 = k + 1
        transitions0 = [
            *[(state, 'a', state + 1) for state in range(k)],
            (k, 'b', final0),
            (k, 'c', final0),
            (final0, 'a', final0),
            (final0, 'b', final0),
            (final0, 'c', final0),
        ]
        automaton0 = FiniteAutomata(
            initials={0},
            transitions=transitions0,
            finals=set(range(k + 2)),
        )

        final1 = 2 * k + 1
        transitions1 = [
            (0, 'a', 1),
            (0, 'a', k + 1),
            *[(state, 'a', state + 1) for state in range(1, k)],
            *[(state, 'a', state + 1) for state in range(k + 1, 2 * k)],
            (k, 'b', final1),
            (2 * k, 'c', final1),
            (final1, 'a', final1),
            (final1, 'b', final1),
            (final1, 'c', final1),
        ]
        automaton1 = FiniteAutomata(
            initials={0},
            transitions=transitions1,
            finals=set(range(2 * k + 2)),
        )
        return automaton0, automaton1

    @staticmethod
    def _simulation_not_bisimulation_witness():
        """Build the formal witness separating simulation from bisimulation."""
        automaton0 = FiniteAutomata(
            initials={0},
            transitions=[
                (0, 'a', 1),
                (0, 'a', 2),
                (1, 'b', 1),
                (1, 'c', 3),
                (2, 'b', 2),
                (3, 'b', 3),
            ],
            finals={0, 1, 2, 3},
        )
        automaton1 = FiniteAutomata(
            initials={0},
            transitions=[
                (0, 'a', 1),
                (1, 'b', 1),
                (1, 'c', 2),
                (2, 'b', 2),
            ],
            finals={0, 1, 2},
        )
        return automaton0, automaton1

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

    def test_formal_simulation_hierarchy_witness(self):
        """The formal witness separates every k from k+1."""
        FiniteAutomata.set_alphabet({'a', 'b', 'c'})
        for k in (1, 2, 3):
            with self.subTest(k=k):
                automaton0, automaton1 = self._buffer_hierarchy_witness(k)
                self.assertTrue(
                    automaton0.equivalence_test(other=automaton1)
                )
                self.assertFalse(
                    BufferedSimulationGames(
                        automaton0=self._buffer_hierarchy_witness(k)[0],
                        automaton1=self._buffer_hierarchy_witness(k)[1],
                        buffer_size=k,
                    ).solve()[0]
                )
                self.assertTrue(
                    BufferedSimulationGames(
                        automaton0=self._buffer_hierarchy_witness(k)[0],
                        automaton1=self._buffer_hierarchy_witness(k)[1],
                        buffer_size=k + 1,
                    ).solve()[0]
                )

    def test_formal_simulation_can_be_strictly_weaker_than_bisimulation(self):
        """The formal witness is simulation equivalent but not bisimilar."""
        FiniteAutomata.set_alphabet({'a', 'b', 'c'})
        for k in (1, 2, 3):
            with self.subTest(k=k):
                simulation0, simulation1 = self._simulation_not_bisimulation_witness()
                self.assertTrue(
                    simulation0.equivalence_test(other=simulation1)
                )
                simulation0, simulation1 = self._simulation_not_bisimulation_witness()
                self.assertTrue(
                    BufferedSimulationGames(
                        simulation0,
                        simulation1,
                        buffer_size=k,
                    ).solve()[0]
                )
                bisimulation0, bisimulation1 = self._simulation_not_bisimulation_witness()
                self.assertFalse(
                    BufferedBisimulationGames(
                        bisimulation0,
                        bisimulation1,
                        buffer_size=k,
                    ).solve()[0]
                )


if __name__ == '__main__':
    unittest.main()
