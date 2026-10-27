"""Measure the hierarchy of the revised buffered bisimulation game.

For every WoFa submission this benchmark checks the implication

    k-buffered bisimilar => language equivalent

for all tested buffer sizes. For language-equivalent pairs it records the
smallest tested buffer size for which the revised buffered bisimulation holds.
Because no finite completeness bound is assumed, the search is limited by the
explicit ``--max-k`` argument.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import BufferedBisimulationGames


TASKS = tuple('ABCDEFGHIJKLMNOPQRS')


@dataclass
class TaskSummary:
    """Collected hierarchy statistics for one WoFa task."""

    task: str
    total_submissions: int = 0
    non_parseable: int = 0
    language_equivalent: int = 0
    first_buffer_counts: Counter = None
    equivalent_without_match: int = 0
    implication_violations: int = 0
    tested_pairs: int = 0
    total_equivalence_runtime: float = 0.0
    total_buffer_runtime: float = 0.0

    def __post_init__(self):
        if self.first_buffer_counts is None:
            self.first_buffer_counts = Counter()


def clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return a structural copy for an isolated game construction."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def run_task(task: str, max_k: int) -> TaskSummary:
    """Run the hierarchy experiment for all submissions of ``task``."""
    summary = TaskSummary(task=task)
    solution = get_solution(exercise=task)
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    iterator = SubmissionIterator(task=task)

    for submission in iterator:
        summary.total_submissions += 1
        print(f'{task}{iterator.index}')

        if not submission:
            summary.non_parseable += 1
            print(f'RESULT {task}{iterator.index}: non-parseable')
            continue

        # The game preparation works on its inputs, so isolate the benchmark
        # pair from the WoFa objects and reuse the prepared game for all k.
        game = BufferedBisimulationGames(
            automaton0=clone_automaton(solution),
            automaton1=clone_automaton(submission),
            buffer_size=1,
        )
        automaton0, automaton1 = game.get_automatons().values()

        start_time = perf_counter()
        equivalent = automaton0.equivalence_test(other=automaton1)
        summary.total_equivalence_runtime += perf_counter() - start_time
        summary.tested_pairs += 1

        if equivalent:
            summary.language_equivalent += 1

        first_matching_k = None
        for k in range(1, max_k + 1):
            game.set_buffer_size(buffer_size=k)
            start_time = perf_counter()
            buffer_similar, _ = game.solve()
            summary.total_buffer_runtime += perf_counter() - start_time

            if buffer_similar:
                first_matching_k = k
                break

        if first_matching_k is None:
            summary.first_buffer_counts['not-found'] += 1
            if equivalent:
                summary.equivalent_without_match += 1
        else:
            summary.first_buffer_counts[first_matching_k] += 1
            if not equivalent:
                summary.implication_violations += 1
                print(
                    f'WARNING {task}{iterator.index}: '
                    f'{first_matching_k}-buffer bisimilar but not language equivalent'
                )

        print(
            f'RESULT {task}{iterator.index}: '
            f'language-equivalent={equivalent}, '
            f'first-buffer-k={first_matching_k or "not-found"}'
        )

    return summary


def print_summary(summary: TaskSummary, max_k: int):
    """Print the hierarchy results for one task."""
    print()
    print(f'Task {summary.task}')
    print('------')
    print(f'Total submissions: {summary.total_submissions}')
    print(f'Non-parseable submissions: {summary.non_parseable}')
    print(f'Tested pairs: {summary.tested_pairs}')
    print(f'Language-equivalent pairs: {summary.language_equivalent}')
    print(f'Equivalent pairs without a match up to k={max_k}: {summary.equivalent_without_match}')
    print(f'Implication violations: {summary.implication_violations}')
    print('First matching buffer size:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.first_buffer_counts[k]}')
    print(f'  not found: {summary.first_buffer_counts["not-found"]}')
    print(f'Equivalence runtime: {summary.total_equivalence_runtime:.6f}s')
    print(f'Buffered-game runtime: {summary.total_buffer_runtime:.6f}s')


def parse_args():
    """Parse command-line options for the hierarchy benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--task',
        choices=TASKS,
        action='append',
        dest='tasks',
        help='Task to run; may be supplied multiple times (default: all tasks).',
    )
    parser.add_argument(
        '--max-k',
        type=int,
        default=10,
        help='Largest buffer size tested for each pair (default: 10).',
    )
    return parser.parse_args()


def main():
    """Run and print the buffered hierarchy experiment."""
    args = parse_args()
    if args.max_k < 1:
        raise ValueError('--max-k must be at least 1.')

    tasks = args.tasks or TASKS
    for task in tasks:
        print_summary(run_task(task=task, max_k=args.max_k), max_k=args.max_k)


if __name__ == '__main__':
    main()
