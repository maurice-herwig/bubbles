"""Small examples for using the current BUBBLES game implementations."""

from wofa import FiniteAutomata

from bubbles import (
    BufferedBisimulationGames,
    BufferedSimulationGames,
    PebbleSimulationGames,
)


def clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return an isolated copy for a game that prepares its inputs."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def buffered_simulation_hierarchy_witness(k: int):
    """Build the formal witness that separates buffered simulation ``k`` and ``k+1``."""
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


def run_examples():
    """Run the current game examples on a formal hierarchy witness."""
    automaton0, automaton1 = buffered_simulation_hierarchy_witness(k=1)
    FiniteAutomata.set_alphabet({'a', 'b', 'c'})

    print(
        'Language equivalent:',
        automaton0.equivalence_test(other=automaton1),
    )

    for size in (1, 2):
        bisimulation_game = BufferedBisimulationGames(
            automaton0=clone_automaton(automaton0),
            automaton1=clone_automaton(automaton1),
            buffer_size=size,
            remove_dead_states=True,
        )
        simulation_game = BufferedSimulationGames(
            automaton0=clone_automaton(automaton0),
            automaton1=clone_automaton(automaton1),
            buffer_size=size,
            remove_dead_states=True,
        )
        pebble_game = PebbleSimulationGames(
            automaton0=clone_automaton(automaton0),
            automaton1=clone_automaton(automaton1),
            pebble_size=size,
            remove_dead_states=True,
        )

        print(f'\nSize k={size}')
        print('  Buffered bisimulation:', bisimulation_game.solve())
        print('  Buffered simulation:  ', simulation_game.solve())
        print('  Pebble simulation:    ', pebble_game.solve())


if __name__ == '__main__':
    run_examples()
