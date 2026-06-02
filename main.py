from wofa import FiniteAutomata
from bubbles import BufferedBisimulationGames, MultiPebbleBisimulationGames

if __name__ == '__main__':
    FiniteAutomata.set_alphabet({'a', 'b'})

    automaton0 = FiniteAutomata(initials={0},
                                transitions=[(0, 'a', 1), (1, 'a', 2), (1, 'a', 4), (2, 'a', 3),
                                             (4, 'a', 5), (3, 'b', 6), (5, 'a', 7), (6, 'a', 6), (7, 'a', 7)],
                                finals={6, 7})

    automaton1 = FiniteAutomata(initials={0},
                                transitions=[(0, 'a', 1), (1, 'a', 2), (2, 'a', 3), (3, 'a', 4), (3, 'b', 4),
                                             (4, 'a', 4)],
                                finals={4})

    print(automaton0)
    print(automaton1)
    print(f'Is automaton0 and automaton1 equivalent? {automaton0.equivalence_test(other=automaton1)}')

    multi_pebble_bisimulation_game = MultiPebbleBisimulationGames(automaton0=automaton0,
                                                                  automaton1=automaton1,
                                                                  pebbles=1)
    print(multi_pebble_bisimulation_game.solve())

    """
    buffered_bisimulation_game = BufferedBisimulationGames(automaton0=automaton0, automaton1=automaton1, buffer_size=1)
    print(buffered_bisimulation_game.solve())

    for i in range(2, 6):
        buffered_bisimulation_game.set_buffer_size(buffer_size=i)
        print(buffered_bisimulation_game.solve())
    """
