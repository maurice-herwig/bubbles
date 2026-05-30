from wofa import get_solution, get_submission, FiniteAutomata
from bubbles import BufferedBisimulationGames

if __name__ == '__main__':
    solution = get_solution(exercise="D")
    submission = get_submission(directory="D", name="5")
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())

    print(f'Is the solution and the submission equivalent? {solution.equivalence_test(other=submission)}')

    buffered_bisimulation_game = BufferedBisimulationGames(automaton0=solution, automaton1=submission, buffer_size=10)

    print(solution)
    print(submission)

    res = buffered_bisimulation_game.solve()
    print(res)
