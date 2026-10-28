"""Tests for correction representations and correction-game search."""

import unittest

from wofa import FiniteAutomata

from bubbles import (
    BufferedCorrectionSimulationGames,
    PebbleCorrectionSimulationGames,
)
from bubbles.games.corrections.CorrectionGames import CorrectionGames


class DummyCorrectionGame(CorrectionGames):
    """Small controllable correction game for testing the search layer."""

    def __init__(self, *args, winning_predicate=None, **kwargs):
        self.winning_predicate = winning_predicate or (lambda _automaton: False)
        self.checked_automatons = []
        super().__init__(*args, **kwargs)

    def _solve_corrected_automaton(self, automaton):
        self.checked_automatons.append(automaton)
        return self.winning_predicate(automaton)


class CorrectionGamesTest(unittest.TestCase):
    """Exercise correction construction, layering, and search."""

    @staticmethod
    def _automata():
        """Return two small automata with the same structure."""
        return (
            FiniteAutomata(
                {0},
                [(0, 'a', 1), (1, 'b', 1)],
                {1},
            ),
            FiniteAutomata(
                {0},
                [(0, 'a', 1), (1, 'b', 1)],
                {1},
            ),
        )

    def setUp(self):
        FiniteAutomata.set_alphabet({'a', 'b'})
        automaton0, automaton1 = self._automata()
        self.game = DummyCorrectionGame(
            automaton0,
            automaton1,
            correction_size=2,
            remove_dead_states=False,
        )

    def test_empty_correction_has_four_empty_components(self):
        """The empty correction contains no modifications."""
        self.assertEqual(
            self.game.empty_correction,
            (frozenset(), frozenset(), frozenset(), frozenset()),
        )

    def test_negative_correction_size_is_rejected(self):
        """A correction budget cannot be negative."""
        automaton0, automaton1 = self._automata()
        with self.assertRaises(ValueError):
            DummyCorrectionGame(automaton0, automaton1, -1)

    def test_correction_size_counts_all_components(self):
        """Each correction operation contributes exactly one unit."""
        correction = (
            frozenset({2}),
            frozenset({(2, 'a', 0), (0, 'b', 2)}),
            frozenset({(0, 'a', 1)}),
            frozenset({1}),
        )
        self.assertEqual(self.game._correction_size_of(correction), 5)

    def test_state_only_correction_is_identified_as_unused(self):
        """An isolated inserted state is not solved as a separate game."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
        )
        self.assertTrue(self.game._contains_only_unused_states(correction))

    def test_empty_correction_is_not_identified_as_unused(self):
        """The empty correction still needs a normal-game evaluation."""
        self.assertFalse(
            self.game._contains_only_unused_states(
                self.game.empty_correction
            )
        )

    def test_used_inserted_state_is_not_identified_as_unused(self):
        """A correction with a transition must be evaluated normally."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
            inserted_transitions={(2, 'a', 0)},
        )
        self.assertFalse(self.game._contains_only_unused_states(correction))

    def test_extend_correction_adds_inserted_state(self):
        """State insertion preserves existing correction components."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
        )
        self.assertEqual(correction[0], frozenset({2}))
        self.assertEqual(correction[1:], (frozenset(), frozenset(), frozenset()))

    def test_extend_correction_adds_all_operation_types(self):
        """All four correction components can be extended."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
            inserted_transitions={(2, 'a', 0)},
            deleted_transitions={(0, 'a', 1)},
            toggled_states={1},
        )
        self.assertEqual(correction[0], frozenset({2}))
        self.assertEqual(correction[1], frozenset({(2, 'a', 0)}))
        self.assertEqual(correction[2], frozenset({(0, 'a', 1)}))
        self.assertEqual(correction[3], frozenset({1}))

    def test_current_states_include_inserted_states(self):
        """The current state universe contains base and inserted states."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
        )
        self.assertEqual(self.game._current_states(correction), {0, 1, 2})

    def test_base_transitions_are_read_from_prepared_automaton(self):
        """The base transition set excludes correction insertions."""
        self.assertEqual(
            self.game._base_transitions(),
            {(0, 'a', 1), (1, 'b', 1)},
        )

    def test_possible_inserted_transitions_excludes_existing_transitions(self):
        """Only absent transitions are offered for insertion."""
        transitions = self.game._possible_inserted_transitions(
            {0, 1},
            self.game._base_transitions(),
            frozenset({(0, 'b', 1)}),
        )
        self.assertNotIn((0, 'a', 1), transitions)
        self.assertNotIn((0, 'b', 1), transitions)
        self.assertIn((1, 'a', 0), transitions)

    def test_first_inserted_state_uses_next_consecutive_identifier(self):
        """The first inserted state receives the first unused state ID."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        states = {
            correction[0]
            for correction in extensions[1]
            if correction[0]
        }
        self.assertEqual(states, {frozenset({2})})

    def test_second_inserted_state_is_consecutive(self):
        """The second inserted state follows the first without a gap."""
        first = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
        )
        extensions = self.game._correction_extensions(first)
        inserted_state_sets = {
            correction[0]
            for correction in extensions[2]
            if len(correction[0]) == 2
        }
        self.assertIn(frozenset({2, 3}), inserted_state_sets)

    def test_one_operation_extensions_have_next_layer_size(self):
        """Ordinary extensions are placed one layer above the parent."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        self.assertIn(1, extensions)
        for correction in extensions[1]:
            self.assertEqual(self.game._correction_size_of(correction), 1)

    def test_state_transition_extension_is_in_next_but_one_layer(self):
        """State-plus-transition extensions are placed in layer two."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        compound = {
            correction
            for correction in extensions[2]
            if len(correction[0]) == 1 and len(correction[1]) == 1
        }
        self.assertTrue(compound)
        self.assertTrue(
            all(self.game._correction_size_of(correction) == 2
                for correction in compound)
        )

    def test_state_only_correction_is_kept_as_intermediate_layer(self):
        """The state-only precursor remains available in the next layer."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        self.assertIn(
            self.game._extend_correction(
                self.game.empty_correction,
                inserted_states={2},
            ),
            extensions[1],
        )

    def test_inserted_transition_can_use_new_state(self):
        """A new transition may target or leave a newly inserted state."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        self.assertTrue(
            any(
                any(2 in (source, target) for source, _, target in correction[1])
                for correction in extensions[2]
            )
        )

    def test_deleted_transition_is_generated_once(self):
        """Existing transitions can be deleted but not deleted twice."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        deleted = {
            correction[2]
            for correction in extensions[1]
            if correction[2]
        }
        self.assertEqual(
            deleted,
            {frozenset({(0, 'a', 1)}), frozenset({(1, 'b', 1)})},
        )

        correction = self.game._extend_correction(
            self.game.empty_correction,
            deleted_transitions={(0, 'a', 1)},
        )
        extensions = self.game._correction_extensions(correction)
        self.assertNotIn(
            self.game._extend_correction(
                correction,
                deleted_transitions={(0, 'a', 1)},
            ),
            extensions.get(2, set()),
        )

    def test_toggled_state_is_generated_once(self):
        """Every current state can be toggled at most once."""
        extensions = self.game._correction_extensions(
            self.game.empty_correction
        )
        toggled = {
            correction[3]
            for correction in extensions[1]
            if correction[3]
        }
        self.assertEqual(toggled, {frozenset({0}), frozenset({1})})

        correction = self.game._extend_correction(
            self.game.empty_correction,
            toggled_states={0},
        )
        extensions = self.game._correction_extensions(correction)
        self.assertNotIn(
            self.game._extend_correction(
                correction,
                toggled_states={0},
            ),
            extensions.get(2, set()),
        )

    def test_inserted_transition_is_not_generated_twice(self):
        """An already inserted transition is excluded from extensions."""
        transition = (0, 'b', 1)
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_transitions={transition},
        )
        extensions = self.game._correction_extensions(correction)
        self.assertNotIn(
            self.game._extend_correction(
                correction,
                inserted_transitions={transition},
            ),
            extensions.get(2, set()),
        )

    def test_no_extensions_exist_at_full_budget(self):
        """A correction at the budget limit cannot be extended."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            inserted_states={2},
            inserted_transitions={(2, 'a', 0)},
        )
        self.assertEqual(self.game._correction_size_of(correction), 2)
        self.assertEqual(self.game._correction_extensions(correction), {})

    def test_apply_correction_changes_transitions_and_finals(self):
        """Applying a correction performs all requested modifications."""
        correction = (
            frozenset({2}),
            frozenset({(1, 'a', 2)}),
            frozenset({(0, 'a', 1)}),
            frozenset({1}),
        )
        corrected = self.game._apply_correction(correction)
        self.assertNotIn((0, 'a', 1), corrected.get_transitions())
        self.assertIn((1, 'a', 2), corrected.get_transitions())
        self.assertNotIn(1, corrected.get_finals())

    def test_apply_correction_does_not_mutate_base_automaton(self):
        """Applying a correction leaves the stored base automaton unchanged."""
        correction = self.game._extend_correction(
            self.game.empty_correction,
            deleted_transitions={(0, 'a', 1)},
        )
        self.game._apply_correction(correction)
        self.assertIn(
            (0, 'a', 1),
            self.game._base_automaton0.get_transitions(),
        )

    def test_breadth_first_search_returns_empty_correction_when_winning(self):
        """A winning empty correction is returned immediately."""
        automaton0, automaton1 = self._automata()
        game = DummyCorrectionGame(
            automaton0,
            automaton1,
            correction_size=2,
            remove_dead_states=False,
            winning_predicate=lambda _automaton: True,
        )
        result, correction = game.solve()
        self.assertTrue(result)
        self.assertEqual(correction, game.empty_correction)
        self.assertEqual(len(game.checked_automatons), 1)

    def test_breadth_first_search_can_find_state_transition_correction(self):
        """The search reaches a solution in the direct second layer."""
        def wins(automaton):
            return any(
                target == 2
                for _, _, target in automaton.get_transitions()
            )

        game = DummyCorrectionGame(
            *self._automata(),
            correction_size=2,
            remove_dead_states=False,
            winning_predicate=wins,
        )
        result, correction = game.solve()
        self.assertTrue(result)
        self.assertEqual(game._correction_size_of(correction), 2)
        self.assertEqual(correction[0], frozenset({2}))
        self.assertEqual(len(correction[1]), 1)

    def test_breadth_first_search_reports_no_solution(self):
        """The search fails when no correction can make the predicate true."""
        result, correction = self.game.solve()
        self.assertFalse(result)
        self.assertIsNone(correction)

    def test_correction_size_zero_only_checks_empty_correction(self):
        """Zero budget prevents all correction extensions."""
        game = DummyCorrectionGame(
            *self._automata(),
            correction_size=0,
            remove_dead_states=False,
        )
        result, correction = game.solve()
        self.assertFalse(result)
        self.assertIsNone(correction)
        self.assertEqual(len(game.checked_automatons), 1)

    def test_buffered_correction_game_uses_normal_buffered_game(self):
        """The buffered correction wrapper solves identical automata."""
        game = BufferedCorrectionSimulationGames(
            *self._automata(),
            buffer_size=1,
            correction_size=0,
            remove_dead_states=False,
        )
        result, correction = game.solve()
        self.assertTrue(result)
        self.assertEqual(correction, game.empty_correction)

    def test_pebble_correction_game_uses_normal_pebble_game(self):
        """The pebble correction wrapper solves identical automata."""
        game = PebbleCorrectionSimulationGames(
            *self._automata(),
            pebble_size=1,
            correction_size=0,
            remove_dead_states=False,
        )
        result, correction = game.solve()
        self.assertTrue(result)
        self.assertEqual(correction, game.empty_correction)


if __name__ == '__main__':
    unittest.main()
