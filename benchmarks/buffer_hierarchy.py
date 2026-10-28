"""Measure buffered bisimulation and simulation hierarchies.

For every WoFa submission this benchmark checks the implication

    k-buffered bisimilar => language equivalent

for all tested buffer sizes. For language-equivalent pairs it records the
smallest tested buffer size for which the revised buffered bisimulation holds.
Because no finite completeness bound is assumed, the search is limited by the
explicit ``--max-k`` argument.
"""

import argparse
import signal
from collections import Counter
from dataclasses import dataclass
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import BufferedBisimulationGames, BufferedSimulationGames


TASKS = tuple('ABCDEFGHIJKLMNOPQRS')
DEFAULT_TIMEOUT_SECONDS = 30.0


class BufferedGameTimeout(Exception):
    """Raised when one buffered-game solve exceeds its time limit."""


def _timeout_handler(signum, frame):
    """Raise the timeout exception when the per-solve timer expires."""
    raise BufferedGameTimeout


@dataclass
class TaskSummary:
    """Collected hierarchy statistics for one WoFa task."""

    task: str
    total_submissions: int = 0
    non_parseable: int = 0
    language_equivalent: int = 0
    non_equivalent_without_k1_match: int = 0
    first_buffer_counts: Counter = None
    equivalent_without_match: int = 0
    tested_pairs: int = 0
    total_equivalence_runtime: float = 0.0
    total_bisimulation_runtime: float = 0.0
    total_simulation_runtime: float = 0.0
    bisimulation_runtimes: dict[int, list[float]] = None
    simulation_runtimes: dict[int, list[float]] = None
    simulation_first_buffer_counts: Counter = None
    simulation_equivalent_without_match: int = 0
    simulation_implication_violations_by_k: Counter = None
    bisimulation_without_simulation_by_k: Counter = None
    simulation_without_bisimulation_by_k: Counter = None
    simulation_hierarchy_by_k: Counter = None
    bisimulation_timeouts_by_k: Counter = None
    simulation_timeouts_by_k: Counter = None
    timed_out_pairs: int = 0

    def __post_init__(self):
        if self.first_buffer_counts is None:
            self.first_buffer_counts = Counter()
        if self.bisimulation_runtimes is None:
            self.bisimulation_runtimes = {}
        if self.simulation_runtimes is None:
            self.simulation_runtimes = {}
        if self.simulation_first_buffer_counts is None:
            self.simulation_first_buffer_counts = Counter()
        if self.simulation_implication_violations_by_k is None:
            self.simulation_implication_violations_by_k = Counter()
        if self.bisimulation_without_simulation_by_k is None:
            self.bisimulation_without_simulation_by_k = Counter()
        if self.simulation_without_bisimulation_by_k is None:
            self.simulation_without_bisimulation_by_k = Counter()
        if self.simulation_hierarchy_by_k is None:
            self.simulation_hierarchy_by_k = Counter()
        if self.bisimulation_timeouts_by_k is None:
            self.bisimulation_timeouts_by_k = Counter()
        if self.simulation_timeouts_by_k is None:
            self.simulation_timeouts_by_k = Counter()


def _solve_with_timeout(game, timeout_seconds: float):
    """Solve one buffered game and abort it after ``timeout_seconds``."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return game.solve()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return a structural copy for an isolated game construction."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def run_task(
        task: str,
        max_k: int,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TaskSummary:
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

        # Both game preparations mutate their inputs. Use isolated copies and
        # explicitly enable the benchmark's dead-state preprocessing.
        bisimulation_game = BufferedBisimulationGames(
            automaton0=clone_automaton(solution),
            automaton1=clone_automaton(submission),
            buffer_size=1,
            remove_dead_states=True,
        )
        simulation_game = BufferedSimulationGames(
            automaton0=clone_automaton(solution),
            automaton1=clone_automaton(submission),
            buffer_size=1,
            remove_dead_states=True,
        )
        automaton0, automaton1 = bisimulation_game.get_automatons().values()

        start_time = perf_counter()
        equivalent = automaton0.equivalence_test(other=automaton1)
        summary.total_equivalence_runtime += perf_counter() - start_time
        summary.tested_pairs += 1

        if equivalent:
            summary.language_equivalent += 1

        first_bisimulation_k = None
        first_simulation_k = None
        previous_simulation_equivalent = None
        bisimulation_active = True
        simulation_active = True
        bisimulation_timeout_k = None
        simulation_timeout_k = None
        tested_max_k = max_k if equivalent else 1
        for k in range(1, tested_max_k + 1):
            if bisimulation_active:
                bisimulation_game.set_buffer_size(buffer_size=k)
                start_time = perf_counter()
                try:
                    bisimilar, _ = _solve_with_timeout(
                        bisimulation_game,
                        timeout_seconds=timeout_seconds,
                    )
                except BufferedGameTimeout:
                    bisimilar = None
                    bisimulation_timeout_k = k
                    bisimulation_active = False
                    summary.bisimulation_timeouts_by_k[k] += 1
                bisimulation_runtime = perf_counter() - start_time
                summary.total_bisimulation_runtime += bisimulation_runtime
                summary.bisimulation_runtimes.setdefault(k, []).append(
                    bisimulation_runtime
                )
            else:
                bisimilar = True

            if simulation_active:
                simulation_game.set_buffer_size(buffer_size=k)
                start_time = perf_counter()
                try:
                    simulation_equivalent, _ = _solve_with_timeout(
                        simulation_game,
                        timeout_seconds=timeout_seconds,
                    )
                except BufferedGameTimeout:
                    simulation_equivalent = None
                    simulation_timeout_k = k
                    simulation_active = False
                    summary.simulation_timeouts_by_k[k] += 1
                simulation_runtime = perf_counter() - start_time
                summary.total_simulation_runtime += simulation_runtime
                summary.simulation_runtimes.setdefault(k, []).append(
                    simulation_runtime
                )
            else:
                simulation_equivalent = True

            if bisimilar is True:
                if first_bisimulation_k is None:
                    first_bisimulation_k = k
            if simulation_equivalent is True:
                if first_simulation_k is None:
                    first_simulation_k = k

            if (
                    equivalent
                    and previous_simulation_equivalent is False
                    and simulation_equivalent is True
            ):
                summary.simulation_hierarchy_by_k[k] += 1
            previous_simulation_equivalent = simulation_equivalent

            if simulation_equivalent is True and not equivalent:
                summary.simulation_implication_violations_by_k[k] += 1
                print(
                    f'WARNING {task}{iterator.index}: '
                    f'{k}-buffered simulation equivalent but not language equivalent'
                )

            if bisimilar is True and simulation_equivalent is False:
                summary.bisimulation_without_simulation_by_k[k] += 1
                print(
                    f'WARNING {task}{iterator.index}: '
                    f'{k}-buffered bisimilar but not {k}-buffered simulation equivalent'
                )

            if bisimilar is False and simulation_equivalent is True:
                summary.simulation_without_bisimulation_by_k[k] += 1
                print(
                    f'INFO {task}{iterator.index}: '
                    f'{k}-buffered simulation equivalent but not {k}-buffered bisimilar'
                )

            # Both relations are monotone in the buffer size. Stop evaluating
            # an individual game after its first successful buffer size. The
            # other game remains active if it still needs larger sizes.
            if bisimilar is True:
                bisimulation_active = False
            if simulation_equivalent is True:
                simulation_active = False
            if not bisimulation_active and not simulation_active:
                break

        pair_timed_out = (
            bisimulation_timeout_k is not None
            or simulation_timeout_k is not None
        )
        if pair_timed_out:
            summary.timed_out_pairs += 1
        elif first_bisimulation_k is None:
            if equivalent:
                summary.first_buffer_counts['not-found'] += 1
                summary.equivalent_without_match += 1
            else:
                summary.non_equivalent_without_k1_match += 1
        else:
            if equivalent:
                summary.first_buffer_counts[first_bisimulation_k] += 1

        if not pair_timed_out and first_simulation_k is None:
            if equivalent:
                summary.simulation_first_buffer_counts['not-found'] += 1
                summary.simulation_equivalent_without_match += 1
        elif equivalent:
            summary.simulation_first_buffer_counts[first_simulation_k] += 1

        if pair_timed_out:
            timeout_parts = []
            if bisimulation_timeout_k is not None:
                timeout_parts.append(f'bisimulation-k={bisimulation_timeout_k}')
            if simulation_timeout_k is not None:
                timeout_parts.append(f'simulation-k={simulation_timeout_k}')
            print(
                f'RESULT {task}{iterator.index}: timeout '
                f'({", ".join(timeout_parts)}) '
                f'after {timeout_seconds:g}s'
            )
        elif equivalent:
            print(
                f'RESULT {task}{iterator.index}: '
                f'language-equivalent=True, '
                f'first-bisimulation-k={first_bisimulation_k or "not-found"}, '
                f'first-simulation-k={first_simulation_k or "not-found"}'
            )
        else:
            print(
                f'RESULT {task}{iterator.index}: '
                f'language-equivalent=False, '
                f'1-buffered-bisimilar={bool(first_bisimulation_k)}, '
                f'1-buffered-simulation-equivalent={bool(first_simulation_k)}'
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
    print(f'Non-equivalent pairs without a 1-buffer match: {summary.non_equivalent_without_k1_match}')
    print(f'Equivalent pairs without a match up to k={max_k}: {summary.equivalent_without_match}')
    print(f'Buffered-game timeouts: {summary.timed_out_pairs}')
    print('Bisimulation timeouts by k:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.bisimulation_timeouts_by_k[k]}')
    print('Simulation timeouts by k:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.simulation_timeouts_by_k[k]}')
    print(
        'Simulation implication violations '
        '(simulation equivalent but not language equivalent): '
        f'{sum(summary.simulation_implication_violations_by_k.values())}'
    )
    for k in range(1, max_k + 1):
        print(
            f'  k={k}: '
            f'{summary.simulation_implication_violations_by_k[k]}'
        )
    print('Bisimulation pairs without simulation equivalence by k:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.bisimulation_without_simulation_by_k[k]}')
    print('Simulation pairs without bisimulation by k:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.simulation_without_bisimulation_by_k[k]}')
    print('Simulation hierarchy transitions (not k, but k+1 equivalent):')
    for k in range(2, max_k + 1):
        print(
            f'  k={k - 1} -> k={k}: '
            f'{summary.simulation_hierarchy_by_k[k]}'
        )
    print('First matching bisimulation buffer size among language-equivalent pairs:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.first_buffer_counts[k]}')
    print('First matching simulation buffer size among language-equivalent pairs:')
    for k in range(1, max_k + 1):
        print(f'  k={k}: {summary.simulation_first_buffer_counts[k]}')
    print('Average buffered bisimulation runtime by k:')
    for k in range(1, max_k + 1):
        runtimes = summary.bisimulation_runtimes.get(k, [])
        if runtimes:
            average_runtime = sum(runtimes) / len(runtimes)
            print(f'  k={k}: {average_runtime:.6f}s over {len(runtimes)} runs')
        else:
            print(f'  k={k}: no measurements')
    print('Average buffered simulation runtime by k:')
    for k in range(1, max_k + 1):
        runtimes = summary.simulation_runtimes.get(k, [])
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
    all_bisimulation_runtimes = [
        runtime
        for runtimes in summary.bisimulation_runtimes.values()
        for runtime in runtimes
    ]
    average_bisimulation_runtime = (
        sum(all_bisimulation_runtimes) / len(all_bisimulation_runtimes)
        if all_bisimulation_runtimes
        else 0.0
    )
    all_simulation_runtimes = [
        runtime
        for runtimes in summary.simulation_runtimes.values()
        for runtime in runtimes
    ]
    average_simulation_runtime = (
        sum(all_simulation_runtimes) / len(all_simulation_runtimes)
        if all_simulation_runtimes
        else 0.0
    )
    print(f'Average equivalence-test runtime: {average_equivalence_runtime:.6f}s')
    print(
        'Average buffered bisimulation runtime: '
        f'{average_bisimulation_runtime:.6f}s'
    )
    print(
        'Average buffered simulation runtime: '
        f'{average_simulation_runtime:.6f}s'
    )


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
        default=5,
        help='Largest buffer size tested for each pair (default: 5).',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            'Maximum runtime in seconds per buffered-game solve '
            f'(default: {DEFAULT_TIMEOUT_SECONDS:g}).'
        ),
    )
    return parser.parse_args()


def main():
    """Run and print the buffered hierarchy experiment."""
    args = parse_args()
    if args.max_k < 1:
        raise ValueError('--max-k must be at least 1.')
    if args.timeout <= 0:
        raise ValueError('--timeout must be positive.')

    tasks = args.tasks or TASKS
    for task in tasks:
        print_summary(
            run_task(
                task=task,
                max_k=args.max_k,
                timeout_seconds=args.timeout,
            ),
            max_k=args.max_k,
        )


if __name__ == '__main__':
    main()
