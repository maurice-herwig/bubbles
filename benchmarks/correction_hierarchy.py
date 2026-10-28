"""Measure correction-game success for different ``k`` and ``l`` values.

The benchmark considers only parseable submissions that are not language
equivalent to the corresponding WoFa solution.  For every such pair it tests
the currently implemented correction games for all requested combinations of
game size ``k`` and correction budget ``l``.

At present the repository provides buffered and pebble correction simulation
games.  A buffered correction bisimulation game can be added to
``CORRECTION_GAME_FACTORIES`` once its implementation is available.
"""

import argparse
import signal
from dataclasses import dataclass, field
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import (
    BufferedCorrectionSimulationGames,
    PebbleCorrectionSimulationGames,
)


TASKS = ("A") #tuple("ABCDEFGHIJKLMNOPQRS")
DEFAULT_K_MAX = 3
DEFAULT_L_MAX = 3
DEFAULT_TIMEOUT_SECONDS = 10.0

CORRECTION_GAME_FACTORIES = {
    "buffered_simulation": BufferedCorrectionSimulationGames,
    "pebble_simulation": PebbleCorrectionSimulationGames,
}


class CorrectionGameTimeout(Exception):
    """Raised when one correction-game solve exceeds its time limit."""


def _timeout_handler(signum, frame):
    """Raise the timeout exception when the per-solve timer expires."""
    raise CorrectionGameTimeout


@dataclass
class TaskSummary:
    """Statistics collected for one benchmark task."""

    task: str
    total_submissions: int = 0
    non_parseable: int = 0
    tested_pairs: int = 0
    language_equivalent: int = 0
    non_equivalent_pairs: int = 0
    corrected_by_game: dict[str, dict[int, dict[int, int]]] = field(
        default_factory=dict
    )
    timeouts_by_game: dict[str, dict[int, dict[int, int]]] = field(
        default_factory=dict
    )
    total_runtime_by_game: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        for game_name in CORRECTION_GAME_FACTORIES:
            self.corrected_by_game.setdefault(game_name, {})
            self.timeouts_by_game.setdefault(game_name, {})
            self.total_runtime_by_game.setdefault(game_name, 0.0)

    def add_measurement(self, game_name: str, k: int, l: int, corrected: bool):
        """Record one completed correction-game measurement."""
        if corrected:
            self.corrected_by_game[game_name].setdefault(l, {}).setdefault(k, 0)
            self.corrected_by_game[game_name][l][k] += 1

    def add_timeout(self, game_name: str, k: int, l: int):
        """Record one correction-game timeout."""
        self.timeouts_by_game[game_name].setdefault(l, {}).setdefault(k, 0)
        self.timeouts_by_game[game_name][l][k] += 1


def _clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return an isolated structural copy of an automaton."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def _solve_with_timeout(game, timeout_seconds: float):
    """Solve one correction game and abort it after ``timeout_seconds``."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return game.solve()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _create_game(
        game_name: str,
        solution: FiniteAutomata,
        submission: FiniteAutomata,
        k: int,
        l: int,
):
    """Construct one isolated correction game for ``k`` and ``l``."""
    game_class = CORRECTION_GAME_FACTORIES[game_name]
    common = {
        "automaton0": _clone_automaton(solution),
        "automaton1": _clone_automaton(submission),
        "correction_size": l,
        "remove_dead_states": True,
    }
    if game_name == "pebble_simulation":
        common["pebble_size"] = k
    else:
        common["buffer_size"] = k
    return game_class(**common)


def _language_equivalent(solution, submission) -> bool:
    """Check language equivalence on independently prepared automata."""
    game = _create_game(
        "buffered_simulation",
        solution,
        submission,
        k=1,
        l=0,
    )
    automaton0, automaton1 = game.get_automatons().values()
    return automaton0.equivalence_test(other=automaton1)


def _measure_pair(
        summary: TaskSummary,
        solution: FiniteAutomata,
        submission: FiniteAutomata,
        submission_label: str,
        k_max: int,
        l_max: int,
        timeout_seconds: float,
):
    """Measure every correction game for one non-equivalent pair.

    A successful result is propagated to larger ``k`` values for the same
    correction budget and to larger correction budgets, since the same
    correction remains available there.  A timeout is propagated in the same
    direction: larger game sizes and larger correction budgets are not
    attempted again once a smaller combination has already timed out.
    """
    for game_name in CORRECTION_GAME_FACTORIES:
        successful = set()
        timed_out = set()

        for l in range(l_max + 1):
            for k in range(1, k_max + 1):
                if any(
                        previous_l <= l and previous_k <= k
                        for previous_l, previous_k in successful
                ):
                    summary.add_measurement(game_name, k, l, corrected=True)
                    print(
                        f"RESULT {submission_label}: "
                        f"{game_name}, l={l}, k={k}: corrected "
                        "(inherited)",
                        flush=True,
                    )
                    continue

                if any(
                        previous_l <= l and previous_k <= k
                        for previous_l, previous_k in timed_out
                ):
                    summary.add_timeout(game_name, k, l)
                    print(
                        f"RESULT {submission_label}: "
                        f"{game_name}, l={l}, k={k}: timeout "
                        "(inherited)",
                        flush=True,
                    )
                    continue

                game = _create_game(game_name, solution, submission, k, l)
                start = perf_counter()
                try:
                    corrected, _ = _solve_with_timeout(
                        game,
                        timeout_seconds=timeout_seconds,
                    )
                except CorrectionGameTimeout:
                    summary.add_timeout(game_name, k, l)
                    timed_out.add((l, k))
                    print(
                        f"RESULT {submission_label}: "
                        f"{game_name}, l={l}, k={k}: timeout",
                        flush=True,
                    )
                    continue
                finally:
                    summary.total_runtime_by_game[game_name] += (
                        perf_counter() - start
                    )

                summary.add_measurement(game_name, k, l, corrected)
                print(
                    f"RESULT {submission_label}: "
                    f"{game_name}, l={l}, k={k}: "
                    f"{'corrected' if corrected else 'not corrected'}",
                    flush=True,
                )
                if corrected:
                    successful.add((l, k))


def run_task(
        task: str,
        k_max: int = DEFAULT_K_MAX,
        l_max: int = DEFAULT_L_MAX,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TaskSummary:
    """Run the correction benchmark for all submissions of ``task``."""
    summary = TaskSummary(task=task)
    solution = get_solution(exercise=task)
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    iterator = SubmissionIterator(task=task)

    for submission in iterator:
        summary.total_submissions += 1
        print(f"{task}{iterator.index}", flush=True)

        if not submission:
            summary.non_parseable += 1
            print(f"RESULT {task}{iterator.index}: non-parseable", flush=True)
            continue

        summary.tested_pairs += 1
        if _language_equivalent(solution, submission):
            summary.language_equivalent += 1
            print(f"RESULT {task}{iterator.index}: language-equivalent", flush=True)
            continue

        summary.non_equivalent_pairs += 1
        _measure_pair(
            summary,
            solution,
            submission,
            submission_label=f"{task}{iterator.index}",
            k_max=k_max,
            l_max=l_max,
            timeout_seconds=timeout_seconds,
        )
        print(f"RESULT {task}{iterator.index}: measured", flush=True)

    return summary


def _total_summary(summaries: list[TaskSummary]) -> TaskSummary:
    """Aggregate task summaries into one total summary."""
    total = TaskSummary(task="Total")
    for summary in summaries:
        total.total_submissions += summary.total_submissions
        total.non_parseable += summary.non_parseable
        total.tested_pairs += summary.tested_pairs
        total.language_equivalent += summary.language_equivalent
        total.non_equivalent_pairs += summary.non_equivalent_pairs
        for game_name in CORRECTION_GAME_FACTORIES:
            total.total_runtime_by_game[game_name] += (
                summary.total_runtime_by_game[game_name]
            )
            for l, values in summary.corrected_by_game[game_name].items():
                for k, count in values.items():
                    total.corrected_by_game[game_name].setdefault(l, {}).setdefault(k, 0)
                    total.corrected_by_game[game_name][l][k] += count
            for l, values in summary.timeouts_by_game[game_name].items():
                for k, count in values.items():
                    total.timeouts_by_game[game_name].setdefault(l, {}).setdefault(k, 0)
                    total.timeouts_by_game[game_name][l][k] += count
    return total


def _print_summary(summary: TaskSummary, k_max: int, l_max: int):
    """Print correction counts and timeouts for one task."""
    print(f"\nTask {summary.task}")
    print("------")
    print(f"Total submissions: {summary.total_submissions}")
    print(f"Non-parseable submissions: {summary.non_parseable}")
    print(f"Tested pairs: {summary.tested_pairs}")
    print(f"Language-equivalent pairs: {summary.language_equivalent}")
    print(f"Non-equivalent pairs: {summary.non_equivalent_pairs}")

    for game_name in CORRECTION_GAME_FACTORIES:
        print(f"{game_name}:")
        for l in range(l_max + 1):
            counts = [
                summary.corrected_by_game[game_name].get(l, {}).get(k, 0)
                for k in range(1, k_max + 1)
            ]
            timeouts = [
                summary.timeouts_by_game[game_name].get(l, {}).get(k, 0)
                for k in range(1, k_max + 1)
            ]
            print(f"  l={l}: corrected={counts}, timeouts={timeouts}")
        print(
            f"  total runtime: "
            f"{summary.total_runtime_by_game[game_name]:.6f}s"
        )


def parse_args():
    """Parse command-line options for the correction benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=TASKS,
        action="append",
        dest="tasks",
        help="Task to run; may be supplied multiple times (default: all tasks).",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=DEFAULT_K_MAX,
        help=f"Maximum buffer/pebble size (default: {DEFAULT_K_MAX}).",
    )
    parser.add_argument(
        "--l-max",
        type=int,
        default=DEFAULT_L_MAX,
        help=f"Maximum correction budget (default: {DEFAULT_L_MAX}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Maximum runtime in seconds per correction-game solve "
            f"(default: {DEFAULT_TIMEOUT_SECONDS:g})."
        ),
    )
    return parser.parse_args()


def main():
    """Run the correction benchmark and print its summaries."""
    args = parse_args()
    if args.k_max < 1:
        raise ValueError("--k-max must be at least 1.")
    if args.l_max < 0:
        raise ValueError("--l-max must be non-negative.")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive.")

    summaries = [
        run_task(
            task,
            k_max=args.k_max,
            l_max=args.l_max,
            timeout_seconds=args.timeout,
        )
        for task in (args.tasks or TASKS)
    ]
    for summary in summaries:
        _print_summary(summary, args.k_max, args.l_max)
    _print_summary(_total_summary(summaries), args.k_max, args.l_max)


if __name__ == "__main__":
    main()
