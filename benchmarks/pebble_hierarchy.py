"""Measure the hierarchy of the restarting pebble simulation game.

For language-equivalent pairs this benchmark tests every pebble size up to
``max_k``. Non-equivalent pairs are tested only with one pebble, matching the
corresponding buffered hierarchy benchmark.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import PebbleSimulationGames


TASKS = tuple('ABCDEFGHIJKLMNOPQRS')


@dataclass
class TaskSummary:
    """Collected pebble hierarchy statistics for one WoFa task."""

    task: str
    total_submissions: int = 0
    non_parseable: int = 0
    tested_pairs: int = 0
    language_equivalent: int = 0
    non_equivalent_without_k1_match: int = 0
    equivalent_without_match: int = 0
    first_pebble_counts: Counter = None
    implication_violations_by_k: Counter = None
    hierarchy_transitions_by_k: Counter = None
    total_equivalence_runtime: float = 0.0
    total_pebble_runtime: float = 0.0
    pebble_runtimes: dict[int, list[float]] = None

    def __post_init__(self):
        if self.first_pebble_counts is None:
            self.first_pebble_counts = Counter()
        if self.implication_violations_by_k is None:
            self.implication_violations_by_k = Counter()
        if self.hierarchy_transitions_by_k is None:
            self.hierarchy_transitions_by_k = Counter()
        if self.pebble_runtimes is None:
            self.pebble_runtimes = {}


def clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return a structural copy for an isolated game construction."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def run_task(task: str, max_k: int) -> TaskSummary:
    """Run the pebble hierarchy experiment for all submissions of ``task``."""
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

        game = PebbleSimulationGames(
            automaton0=clone_automaton(solution),
            automaton1=clone_automaton(submission),
            pebble_size=1,
            remove_dead_states=True,
        )
        automaton0, automaton1 = game.get_automatons().values()

        start_time = perf_counter()
        equivalent = automaton0.equivalence_test(other=automaton1)
        summary.total_equivalence_runtime += perf_counter() - start_time
        summary.tested_pairs += 1

        if equivalent:
            summary.language_equivalent += 1

        first_pebble_k = None
        previous_pebble_equivalent = None
        tested_max_k = max_k if equivalent else 1

        for k in range(1, tested_max_k + 1):
            game.set_pebble_size(k)
            start_time = perf_counter()
            pebble_equivalent, _ = game.solve()
            pebble_runtime = perf_counter() - start_time

            summary.total_pebble_runtime += pebble_runtime
            summary.pebble_runtimes.setdefault(k, []).append(pebble_runtime)

            if pebble_equivalent and first_pebble_k is None:
                first_pebble_k = k

            if pebble_equivalent and not equivalent:
                summary.implication_violations_by_k[k] += 1
                print(
                    f'WARNING {task}{iterator.index}: '
                    f'{k}-pebble simulation equivalent but not language equivalent'
                )

            if (
                    equivalent
                    and previous_pebble_equivalent is False
                    and pebble_equivalent
            ):
                summary.hierarchy_transitions_by_k[k] += 1

            previous_pebble_equivalent = pebble_equivalent

        if first_pebble_k is None:
            if equivalent:
                summary.first_pebble_counts['not-found'] += 1
                summary.equivalent_without_match += 1
            else:
                summary.non_equivalent_without_k1_match += 1
        elif equivalent:
            summary.first_pebble_counts[first_pebble_k] += 1

        if equivalent:
            print(
                f'RESULT {task}{iterator.index}: '
                f'language-equivalent=True, '
                f'first-pebble-k={first_pebble_k or "not-found"}'
            )
        else:
            print(
                f'RESULT {task}{iterator.index}: '
                f'language-equivalent=False, '
                f'1-pebble-equivalent={bool(first_pebble_k)}'
            )

    return summary


def print_summary(summary: TaskSummary, max_k: int):
    """Print pebble hierarchy results for one task."""
    print()
    print(f'Task {summary.task}')
    print('------')
    print(f'Total submissions: {summary.total_submissions}')
    print(f'Non-parseable submissions: {summary.non_parseable}')
    print(f'Tested pairs: {summary.tested_pairs}')
    print(f'Language-equivalent pairs: {summary.language_equivalent}')
    print(
        'Non-equivalent pairs without a 1-pebble match: '
        f'{summary.non_equivalent_without_k1_match}'
    )
    print(
        f'Equivalent pairs without a match up to k={max_k}: '
        f'{summary.equivalent_without_match}'
    )
    print(
        'Pebble implication violations '
        '(pebble equivalent but not language equivalent): '
        f'{sum(summary.implication_violations_by_k.values())}'
    )
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.implication_violations_by_k[k]}')

    print('Pebble hierarchy transitions (not k, but k+1 equivalent):')
    for k in range(2, max_k + 1):
        print(
            f'  k={k - 1} -> k={k}: '
            f'{summary.hierarchy_transitions_by_k[k]}'
        )

    print('First matching pebble size among language-equivalent pairs:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.first_pebble_counts[k]}')

    print('Average pebble-game runtime by k:')
    for k in range(1, max_k + 1):
        runtimes = summary.pebble_runtimes.get(k, [])
        if runtimes:
            average_runtime = sum(runtimes) / len(runtimes)
            print(f'  k={k}: {average_runtime:.6f}s over {len(runtimes)} runs')
        else:
            print(f'  k={k}: no measurements')

    average_equivalence_runtime = (
        summary.total_equivalence_runtime / summary.tested_pairs
        if summary.tested_pairs
        else 0.0
    )
    all_pebble_runtimes = [
        runtime
        for runtimes in summary.pebble_runtimes.values()
        for runtime in runtimes
    ]
    average_pebble_runtime = (
        sum(all_pebble_runtimes) / len(all_pebble_runtimes)
        if all_pebble_runtimes
        else 0.0
    )
    print(f'Average equivalence-test runtime: {average_equivalence_runtime:.6f}s')
    print(f'Average pebble-game runtime: {average_pebble_runtime:.6f}s')


def parse_args():
    """Parse command-line options for the pebble hierarchy benchmark."""
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
        default=5,
        help='Largest pebble size tested for equivalent pairs (default: 5).',
    )
    return parser.parse_args()


def main():
    """Run and print the pebble hierarchy experiment."""
    args = parse_args()
    if args.max_k < 1:
        raise ValueError('--max-k must be at least 1.')

    tasks = args.tasks or TASKS
    for task in tasks:
        print_summary(run_task(task=task, max_k=args.max_k), max_k=args.max_k)


if __name__ == '__main__':
    main()
