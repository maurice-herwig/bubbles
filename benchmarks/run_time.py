from collections import defaultdict
from time import perf_counter

from wofa import get_solution, FiniteAutomata, SubmissionIterator
from bubbles import BufferedBisimulationGames

MAX_BUFFER_SIZE = 3

TASKS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']

if __name__ == '__main__':
    # Select the benchmark task whose reference solution and submissions are
    # loaded below.
    task = TASKS[12]  # 5, 11, 12
    print(f'---------{task}------------')

    # Load the reference solution and use its alphabet as the common alphabet
    # for all subsequent automata operations.
    solution = get_solution(exercise=task)
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())

    # Iterate over all submissions that belong to the selected task.
    iterator = SubmissionIterator(task=task)

    # Store the measured runtimes of the buffered bisimulation solver grouped
    # by buffer size k.
    runtimes_b_buffer = defaultdict(list)
    # Store the measured runtimes of the plain language-equivalence test.
    runtimes_eq_test = []
    # Count how many submissions are k-buffer equivalent to the solution.
    number_of_k_buff_sims = defaultdict(int)
    # Count all processed submissions, including non-parseable ones.
    number_of_submissions = 0
    # Count correct submissions that are deterministic finite automata.
    correct_dfa = 0
    # Count correct submissions that are not deterministic finite automata.
    correct_non_dfa = 0
    # Count incorrect submissions that are deterministic finite automata.
    incorrect_dfa = 0
    # Count incorrect submissions that are not deterministic finite automata.
    incorrect_non_dfa = 0
    # Count submissions that could not be parsed into an automaton.
    non_parseable = 0

    for sub in iterator:
        # Print the current submission index to make long benchmark runs
        # observable in the terminal.
        print(iterator.index)
        number_of_submissions += 1

        if sub:
            # Build the game object once for the current submission. The game
            # internally prepares both automata before they are analyzed.
            buffered_bisimulation_game = BufferedBisimulationGames(
                automaton0=solution,
                automaton1=sub,
                buffer_size=1,
            )
            prepared_automatas = buffered_bisimulation_game.get_automatons()

            # Record whether the prepared submission automaton is deterministic.
            is_sub_dfa = prepared_automatas[1].is_deterministic()

            # Measure the runtime of the standard language-equivalence test.
            start_time = perf_counter()
            equivalent = prepared_automatas[0].equivalence_test(other=prepared_automatas[1])
            eq_runtime = perf_counter() - start_time

            # Classify the submission by correctness and determinism.
            if equivalent:
                if is_sub_dfa:
                    correct_dfa += 1
                else:
                    correct_non_dfa += 1
            else:
                if is_sub_dfa:
                    incorrect_dfa += 1
                else:
                    incorrect_non_dfa += 1

            # Buffered bisimulation is only benchmarked when at least one of the
            # two prepared automata is nondeterministic.
            if (not is_sub_dfa) or (not prepared_automatas[0].is_deterministic()):
                # Measure the runtime for 1-buffer bisimulation.
                start_time = perf_counter()
                one_buf_sim, _ = buffered_bisimulation_game.solve()
                one_buf_runtime = perf_counter() - start_time

                # Store the measured solver runtime for k = 1.
                runtimes_b_buffer[1].append(one_buf_runtime)
                # Store the measured equivalence-test runtime for the same pair.
                runtimes_eq_test.append(eq_runtime)

                # A buffered bisimulation result may never classify a pair as
                # equivalent if plain language equivalence already failed.
                if one_buf_sim and not equivalent:
                    raise Exception(
                        'Found a submission that is not equivalent but 1 buffered equivalent to the solution')

                if one_buf_sim:
                    number_of_k_buff_sims[1] += 1

                for k in range(2, MAX_BUFFER_SIZE + 1):
                    # Reuse the same prepared game object and only increase the
                    # buffer size for the next measurement.
                    buffered_bisimulation_game.set_buffer_size(buffer_size=k)

                    # Measure the runtime for the current buffer size k.
                    start_time = perf_counter()
                    k_buf_sim, _ = buffered_bisimulation_game.solve()
                    k_buf_runtime = perf_counter() - start_time

                    # Store the measured solver runtime for this k.
                    runtimes_b_buffer[k].append(k_buf_runtime)

                    # Again guard against impossible outcomes.
                    if k_buf_sim and not equivalent:
                        raise Exception(
                            f'Found a submission that is not equivalent but {k} buffered equivalent to the solution')

                    if k_buf_sim:
                        number_of_k_buff_sims[k] += 1

        else:
            # Count submissions that could not be parsed into an automaton at all.
            non_parseable += 1

    print()
    print('Summary')
    print('-------')
    print(f'Task: {task}')
    print(f'Total submissions: {number_of_submissions}')
    print(f'Non-parseable submissions: {non_parseable}')
    print(f'Equivalent DFA submissions: {correct_dfa}')
    print(f'Equivalent non-DFA submissions: {correct_non_dfa}')
    print(f'Non-equivalent DFA submissions: {incorrect_dfa}')
    print(f'Non-equivalent non-DFA submissions: {incorrect_non_dfa}')

    if runtimes_eq_test:
        avg_eq_runtime = sum(runtimes_eq_test) / len(runtimes_eq_test)
        print(f'Average equivalence-test runtime: {avg_eq_runtime:.6f}s over {len(runtimes_eq_test)} runs')
    else:
        print('Average equivalence-test runtime: no measurements recorded')

    print()
    print('Buffered Bisimulation')
    print('---------------------')
    for k in range(1, MAX_BUFFER_SIZE + 1):
        runtimes = runtimes_b_buffer[k]
        number_of_equivalent = number_of_k_buff_sims[k]

        if runtimes:
            avg_runtime = sum(runtimes) / len(runtimes)
            print(
                f'k={k}: {number_of_equivalent} equivalent, '
                f'{len(runtimes)} measured runs, average runtime {avg_runtime:.6f}s'
            )
        else:
            print(f'k={k}: no measurements recorded')
