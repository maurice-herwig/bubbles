"""Tests for shared game infrastructure and preparation behavior."""

import unittest

from wofa import FiniteAutomata

from bubbles.games import BufferedBisimulationGames, TwoWaySetMap
from bubbles.games.bisimulation.BisimulationGames import BisimulationGames


class GameInfrastructureTest(unittest.TestCase):
    """Exercise shared preparation, storage, and propagation helpers."""

    def test_two_way_set_map_operations(self):
        """The bidirectional obligation map keeps both indexes consistent."""
        relation = TwoWaySetMap()
        key0 = ('key', 0)
        key1 = ('key', 1)
        value0 = ('value', 0)
        value1 = ('value', 1)

        relation.add(key0, value0)
        relation.add_many(key0, {value1})
        relation.add(key1, value1)

        self.assertTrue(relation.has_key(key0))
        self.assertTrue(relation.has_value(value1))
        self.assertEqual(relation.get_values(key0), {value0, value1})
        self.assertEqual(relation.get_keys(value1), {key0, key1})
        self.assertEqual(relation.keys(), {key0, key1})
        self.assertEqual(relation.values(), {value0, value1})
        self.assertEqual(
            relation.items(),
            {key0: {value0, value1}, key1: {value1}},
        )
        self.assertFalse(relation.remove(key0, ('missing',)))
        self.assertTrue(relation.remove(key0, value0))
        self.assertFalse(relation.remove(key0, value0))
        self.assertFalse(relation.is_empty_for_key(key0))
        self.assertEqual(relation.remove_value_everywhere(value1), {key0, key1})
        self.assertTrue(relation.is_empty_for_key(key0))
        self.assertEqual(relation.remove_key(key1), set())
        relation.add(key0, value0)
        relation.add(key0, value1)
        self.assertEqual(relation.remove_key(key0), {value0, value1})
        self.assertFalse(relation.has_key(key0))
        self.assertFalse(relation.has_value(value0))
        self.assertEqual(relation.remove_value_everywhere(('missing',)), set())
        relation.add(key0, value0)
        self.assertTrue(relation.remove(key0, value0))
        self.assertFalse(relation.has_key(key0))
        self.assertFalse(relation.has_value(value0))
        self.assertEqual(str(relation), '{}')

    def test_attractor_propagation_discharges_pending_obligations(self):
        """Pending Player-II obligations are discharged by new successors."""
        player2_node = (0, '', 0, 0, 1)
        successor = (0, '', 0, 0, 2)
        obligations = TwoWaySetMap()
        obligations.add(player2_node, successor)
        all_nodes = set()
        new_nodes = set()

        self.assertFalse(
            BisimulationGames.propagate_new_attractor_nodes(
                nodes_to_process=[successor],
                all_attractor_nodes=all_nodes,
                new_attractor_nodes=new_nodes,
                seen_player2_nodes_not_in_attractor=obligations,
                check_initial=lambda *_: False,
            )
        )

        already_added_obligations = TwoWaySetMap()
        already_added_obligations.add(player2_node, successor)
        already_added = {player2_node}
        self.assertFalse(
            BisimulationGames.propagate_new_attractor_nodes(
                nodes_to_process=[successor],
                all_attractor_nodes=already_added,
                new_attractor_nodes=set(),
                seen_player2_nodes_not_in_attractor=already_added_obligations,
                check_initial=lambda *_: False,
            )
        )
        self.assertEqual(all_nodes, {player2_node})
        self.assertEqual(new_nodes, {player2_node})

        self.assertFalse(
            BisimulationGames.propagate_new_attractor_nodes(
                nodes_to_process=[('untracked',)],
                all_attractor_nodes=all_nodes,
                new_attractor_nodes=new_nodes,
                seen_player2_nodes_not_in_attractor=obligations,
                check_initial=lambda *_: False,
            )
        )

        second_obligations = TwoWaySetMap()
        second_obligations.add(player2_node, successor)
        self.assertTrue(
            BisimulationGames.propagate_new_attractor_nodes(
                nodes_to_process=[successor],
                all_attractor_nodes=set(),
                new_attractor_nodes=set(),
                seen_player2_nodes_not_in_attractor=second_obligations,
                check_initial=lambda *_: True,
            )
        )

    def test_preparation_removes_non_alphabet_and_unreachable_states(self):
        """Preparation keeps only relevant transitions and reachable states."""
        FiniteAutomata.set_alphabet({'a'})
        game = BufferedBisimulationGames(
            FiniteAutomata(
                initials={0},
                transitions=[(0, 'a', 1), (0, 'b', 1)],
                finals={1, 2},
            ),
            FiniteAutomata(
                initials={0},
                transitions=[(0, 'a', 1)],
                finals={1},
            ),
            buffer_size=1,
        )
        prepared0 = game.get_automatons()[0]
        self.assertEqual(prepared0.get_transitions(), [(0, 'a', 1)])
        self.assertEqual(prepared0.get_number_of_states(), 2)

    def test_preparation_normalizes_multiple_initial_states(self):
        """Multiple initial states are merged and old helper states removed."""
        FiniteAutomata.set_alphabet({'a'})
        game = BufferedBisimulationGames(
            FiniteAutomata(
                initials={0, 1},
                transitions=[(0, 'a', 2), (1, 'a', 2)],
                finals={2},
            ),
            FiniteAutomata(
                initials={0},
                transitions=[(0, 'a', 1)],
                finals={1},
            ),
            buffer_size=1,
        )
        prepared0 = game.get_automatons()[0]
        self.assertEqual(len(prepared0.get_initials()), 1)
        self.assertEqual(prepared0.get_number_of_states(), 2)

    def test_empty_language_is_replaced_by_empty_nfa(self):
        """An automaton without productive initials keeps a valid start state."""
        FiniteAutomata.set_alphabet({'a'})
        game = BufferedBisimulationGames(
            FiniteAutomata(initials={0}, transitions=[], finals=set()),
            FiniteAutomata(initials={0}, transitions=[], finals=set()),
            buffer_size=1,
        )
        for automaton in game.get_automatons().values():
            self.assertEqual(automaton.get_initials(), {0})
            self.assertEqual(automaton.get_finals(), set())
            self.assertEqual(automaton.get_transitions(), [])

    def test_dead_state_removal_can_be_disabled(self):
        """Dead states are removed by default but preserved when requested."""
        FiniteAutomata.set_alphabet({'a', 'b'})

        default_game = BufferedBisimulationGames(
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
        )
        self.assertEqual(
            default_game.get_automatons()[0].get_transitions(),
            [(0, 'b', 1)],
        )

        preserved_game = BufferedBisimulationGames(
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
            preserved_game.get_automatons()[0].get_transitions(),
            [(0, 'a', 1), (0, 'b', 2)],
        )

    def test_buffer_size_validation(self):
        """Buffer capacities must be positive."""
        FiniteAutomata.set_alphabet({'a'})
        with self.assertRaises(ValueError):
            BufferedBisimulationGames(
                FiniteAutomata({0}, [], set()),
                FiniteAutomata({0}, [], set()),
                buffer_size=0,
            )

        game = BufferedBisimulationGames(
            FiniteAutomata({0}, [], {0}),
            FiniteAutomata({0}, [], {0}),
            buffer_size=1,
        )
        with self.assertRaises(ValueError):
            game.set_buffer_size(0)

    def test_totality_helper(self):
        """The shared totality predicate recognizes complete automata."""
        FiniteAutomata.set_alphabet({'a'})
        complete = FiniteAutomata({0}, [(0, 'a', 0)], {0})
        incomplete = FiniteAutomata({0}, [], {0})
        self.assertTrue(BisimulationGames._is_total(complete))
        self.assertFalse(BisimulationGames._is_total(incomplete))

    def test_abstract_solve_stub_is_callable(self):
        """The abstract base stub remains harmless when called directly."""
        self.assertIsNone(BisimulationGames.solve(None))


if __name__ == '__main__':
    unittest.main()
