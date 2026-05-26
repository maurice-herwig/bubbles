from wofa import get_solution, get_submission, FiniteAutomata
from bubbles import BufferedBisimulationGames

if __name__ == '__main__':
    solution = get_solution(exercise="A")
    submission = get_submission(directory="A", name="2")

    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    submission.remove_non_alphabet_transitions()

    buffered_bisimulation_game = BufferedBisimulationGames(automaton1=solution, automaton2=submission, buffer_size=2)

