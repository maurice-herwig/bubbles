from wofa import get_solution, get_submission, FiniteAutomata
from bubbles import BufferedBisimulationGames

if __name__ == '__main__':
    solution = get_solution(exercise="A")
    submission = get_submission(directory="A", name="2")  # Nicht equivlant beispiel: 1; Equivalent beispiel: 2

    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    submission.remove_non_alphabet_transitions()

    print(solution)
    print(submission)

    print(f'Is the solution and the submission equivalent? {solution.equivalence_test(other=submission)}')

    buffered_bisimulation_game = BufferedBisimulationGames(automaton0=solution, automaton1=submission, buffer_size=3)
    res = buffered_bisimulation_game.solve()
    print(res)
