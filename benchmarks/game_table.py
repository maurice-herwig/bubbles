"""Create a LaTeX table for the three game hierarchies.

Only language-equivalent submissions are tested with the game implementations.
For a successful game at buffer/pebble size ``k``, all larger sizes are counted
as successful as well. A game solve is aborted after 30 seconds by default.
"""

import argparse
import signal
from dataclasses import dataclass, field
from pathlib import Path

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import (
    BufferedBisimulationGames,
    BufferedSimulationGames,
    PebbleSimulationGames,
)


TASKS = tuple('ABCDEFGHIJKLMNOPQRS')
GAME_NAMES = (
    'buffered_simulation',
    'pebble_simulation',
    'buffered_bisimulation',
)
GAME_LABELS = {
    'buffered_simulation': 'Buffered Simulation',
    'pebble_simulation': 'Pebble Simulation',
    'buffered_bisimulation': 'Buffered Bisimulation',
}
MAX_K = 5
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_OUTPUT = Path('tmp/game_hierarchy_table.tex')


class GameTimeout(Exception):
    """Raised when a single game solve exceeds its time limit."""


def _timeout_handler(signum, frame):
    """Raise the timeout exception when the interval timer expires."""
    raise GameTimeout


@dataclass
class TaskSummary:
    """Statistics for one WoFa task."""

    task: str
    parseable: int = 0
    language_equivalent: int = 0
    equivalent_by_game: dict[str, list[int]] = field(default_factory=dict)
    timeouts_by_game: dict[str, list[int]] = field(default_factory=dict)

    def __post_init__(self):
        for game_name in GAME_NAMES:
            self.equivalent_by_game.setdefault(game_name, [0] * MAX_K)
            self.timeouts_by_game.setdefault(game_name, [0] * MAX_K)


def _clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return an isolated structural copy of an automaton."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def _solve_with_timeout(game, timeout_seconds: float):
    """Solve one game and abort it after ``timeout_seconds``."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return game.solve()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _create_games(solution, submission):
    """Create independent game instances with dead-state removal enabled."""
    return {
        'buffered_simulation': BufferedSimulationGames(
            automaton0=_clone_automaton(solution),
            automaton1=_clone_automaton(submission),
            buffer_size=1,
            remove_dead_states=True,
        ),
        'pebble_simulation': PebbleSimulationGames(
            automaton0=_clone_automaton(solution),
            automaton1=_clone_automaton(submission),
            pebble_size=1,
            remove_dead_states=True,
        ),
        'buffered_bisimulation': BufferedBisimulationGames(
            automaton0=_clone_automaton(solution),
            automaton1=_clone_automaton(submission),
            buffer_size=1,
            remove_dead_states=True,
        ),
    }


def _set_game_size(game_name: str, game, k: int):
    """Set the buffer or pebble size for one game."""
    if game_name == 'pebble_simulation':
        game.set_pebble_size(k)
    else:
        game.set_buffer_size(buffer_size=k)


def _measure_game(
        summary: TaskSummary,
        game_name: str,
        game,
        timeout_seconds: float,
):
    """Measure one game and carry successful results to larger sizes."""
    for k in range(1, MAX_K + 1):
        _set_game_size(game_name, game, k)
        try:
            equivalent, _ = _solve_with_timeout(game, timeout_seconds)
        except GameTimeout:
            summary.timeouts_by_game[game_name][k - 1] += 1
            return

        if equivalent:
            for index in range(k - 1, MAX_K):
                summary.equivalent_by_game[game_name][index] += 1
            return


def run_task(
        task: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TaskSummary:
    """Create statistics for all submissions of one task."""
    summary = TaskSummary(task=task)
    solution = get_solution(exercise=task)
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    iterator = SubmissionIterator(task=task)

    for submission in iterator:
        print(f'{task}{iterator.index}', flush=True)
        if not submission:
            continue

        summary.parseable += 1
        games = _create_games(solution, submission)
        automaton0, automaton1 = games['buffered_bisimulation'].get_automatons().values()
        if not automaton0.equivalence_test(other=automaton1):
            continue

        summary.language_equivalent += 1
        for game_name in GAME_NAMES:
            _measure_game(
                summary,
                game_name,
                games[game_name],
                timeout_seconds,
            )

    return summary


def _total_summary(summaries: list[TaskSummary]) -> TaskSummary:
    """Aggregate task summaries into one total row."""
    total = TaskSummary(task='Total')
    for summary in summaries:
        total.parseable += summary.parseable
        total.language_equivalent += summary.language_equivalent
        for game_name in GAME_NAMES:
            for index in range(MAX_K):
                total.equivalent_by_game[game_name][index] += (
                    summary.equivalent_by_game[game_name][index]
                )
                total.timeouts_by_game[game_name][index] += (
                    summary.timeouts_by_game[game_name][index]
                )
    return total


def _latex_escape(value: str) -> str:
    """Escape the small set of characters used in table values."""
    return value.replace('_', r'\_').replace('&', r'\&')


def _table_header() -> list[str]:
    """Return the three LaTeX header rows."""
    first = [r'\textbf{Aufgabe}', r'\textbf{$n$}', r'\textbf{Sprachäquivalent}']
    second = ['', '', '']
    third = ['', '', '']
    for k in range(1, MAX_K + 1):
        first.append(rf'\multicolumn{{6}}{{c}}{{\textbf{{k={k}}}}}')
        for game_name in GAME_NAMES:
            first_game_label = GAME_LABELS[game_name]
            second.append(rf'\multicolumn{{2}}{{c}}{{{first_game_label}}}')
            third.extend([r'Äquiv.', r'Timeout'])
    return [
        ' & '.join(first) + r' \\',
        ' & '.join(second) + r' \\',
        ' & '.join(third) + r' \\',
        r'\midrule',
    ]


def _table_row(summary: TaskSummary) -> str:
    """Render one task or total summary as a LaTeX row."""
    values = [
        _latex_escape(summary.task),
        str(summary.parseable),
        str(summary.language_equivalent),
    ]
    for k in range(MAX_K):
        for game_name in GAME_NAMES:
            values.extend([
                str(summary.equivalent_by_game[game_name][k]),
                str(summary.timeouts_by_game[game_name][k]),
            ])
    return ' & '.join(values) + r' \\'


def write_latex_table(summaries: list[TaskSummary], output: Path):
    """Write all task rows and the total row to ``output``."""
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        r'\begin{table}[ht]',
        r'\centering',
        r'\small',
        r'\begin{tabular}{lrr' + 'rr' * (MAX_K * len(GAME_NAMES)) + r'}',
        r'\toprule',
    ]
    rows.extend(_table_header())
    rows.extend(_table_row(summary) for summary in summaries)
    rows.append(r'\midrule')
    rows.append(_table_row(_total_summary(summaries)))
    rows.extend([
        r'\bottomrule',
        r'\end{tabular}',
        r'\caption{Vergleich der drei Spiele auf dem Benchmarkdatensatz.}',
        r'\label{tab:game-hierarchy-benchmark}',
        r'\end{table}',
        '',
    ])
    output.write_text('\n'.join(rows), encoding='utf-8')


def parse_args():
    """Parse command-line options for the table benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--task',
        choices=TASKS,
        action='append',
        dest='tasks',
        help='Task to run; may be supplied multiple times (default: all tasks).',
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            'Maximum runtime in seconds per game solve '
            f'(default: {DEFAULT_TIMEOUT_SECONDS:g}).'
        ),
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f'LaTeX output path (default: {DEFAULT_OUTPUT}).',
    )
    return parser.parse_args()


def main():
    """Run the benchmark and write its LaTeX table."""
    args = parse_args()
    if args.timeout <= 0:
        raise ValueError('--timeout must be positive.')

    summaries = [
        run_task(task, timeout_seconds=args.timeout)
        for task in (args.tasks or TASKS)
    ]
    write_latex_table(summaries, args.output)
    print(f'LaTeX table written to {args.output}')


if __name__ == '__main__':
    main()
