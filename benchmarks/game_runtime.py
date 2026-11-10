"""Measure runtime and structural metadata for the simulation games."""

import argparse
import csv
import signal
from pathlib import Path
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import (
    BufferedBisimulationGames,
    BufferedSimulationGames,
    PebbleSimulationGames,
)


TASKS = tuple('ABCDEFGHIJKLMNOPQRS')
MAX_K = 5
TIMEOUT_SECONDS = 30.0
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'tmp' / 'game_runtime.csv'
GAME_NAMES = (
    'buffered_simulation',
    'pebble_simulation',
    'buffered_bisimulation',
)


class GameTimeout(Exception):
    """Raised when a game solve exceeds the fixed time limit."""


def _timeout_handler(signum, frame):
    """Raise the timeout exception for the active game solve."""
    raise GameTimeout


def _clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return an isolated structural copy of an automaton."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def _automaton_type(automaton: FiniteAutomata) -> str:
    """Return ``DFA`` or ``NFA`` according to WoFa's determinism check."""
    return 'DFA' if automaton.is_deterministic() else 'NFA'


def _minimal_state_count_without_dead_state(
        automaton: FiniteAutomata,
) -> int:
    """Return the minimal equivalent DFA size without an explicit dead state."""
    minimized = _clone_automaton(automaton).determine().minimize()
    productive_states = minimized.productive()
    return len(productive_states)


def _determinization_blowup(
        automaton: FiniteAutomata,
        minimal_state_count: int,
) -> float:
    """Return minimal-DFA states divided by the original state count."""
    state_count = automaton.get_number_of_states()
    return minimal_state_count / state_count if state_count else 0.0


def _fieldnames(max_k: int) -> list[str]:
    """Return the stable CSV schema for the selected maximum game size."""
    fields = [
        'task',
        'submission',
        'parseable',
        'solution_type',
        'submission_type',
        'solution_states',
        'submission_states',
        'solution_min_states',
        'submission_min_states',
        'solution_determinization_blowup',
        'submission_determinization_blowup',
        'language_equivalent',
        'equivalence_runtime',
    ]
    for game_name in GAME_NAMES:
        for k in range(1, max_k + 1):
            fields.extend((
                f'{game_name}_k{k}_result',
                f'{game_name}_k{k}_runtime',
            ))
    return fields


def _load_rows(output: Path, fieldnames: list[str]) -> dict[tuple[str, str], dict[str, str]]:
    """Load completed result rows and validate the CSV schema."""
    if not output.exists():
        return {}

    with output.open(newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != fieldnames:
            raise ValueError(
                f'CSV schema in {output} does not match max_k and the current script.'
            )
        rows = list(reader)

    return {
        (row['task'], row['submission']): row
        for row in rows
    }


def _write_rows(
        output: Path,
        rows: dict[tuple[str, str], dict[str, str]],
        fieldnames: list[str],
):
    """Rewrite the resumable result CSV atomically at the logical level."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow(rows[key])


def _solve_with_timeout(game):
    """Solve one game with the fixed 30-second timeout."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT_SECONDS)
    try:
        return game.solve()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _create_games(solution, submission):
    """Create independent, dead-state-preprocessed game instances."""
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
    """Set the buffer or pebble size of a game instance."""
    if game_name == 'pebble_simulation':
        game.set_pebble_size(k)
    else:
        game.set_buffer_size(buffer_size=k)


def _measure_game(game_name: str, game, row: dict[str, str], max_k: int, label: str):
    """Measure every size, propagating a timeout to larger sizes."""
    timed_out = False
    for k in range(1, max_k + 1):
        result_field = f'{game_name}_k{k}_result'
        runtime_field = f'{game_name}_k{k}_runtime'

        if timed_out:
            row[result_field] = 'timeout'
            row[runtime_field] = ''
            print(f'  {label} k={k}: timeout (inherited)', flush=True)
            continue

        _set_game_size(game_name, game, k)
        start = perf_counter()
        try:
            equivalent, _ = _solve_with_timeout(game)
        except GameTimeout:
            runtime = perf_counter() - start
            row[result_field] = 'timeout'
            row[runtime_field] = f'{runtime:.9f}'
            timed_out = True
            print(
                f'  {label} k={k}: timeout after {TIMEOUT_SECONDS:g}s',
                flush=True,
            )
            continue

        runtime = perf_counter() - start
        row[result_field] = 'true' if equivalent else 'false'
        row[runtime_field] = f'{runtime:.9f}'
        print(
            f'  {label} k={k}: {row[result_field]} '
            f'({runtime:.6f}s)',
            flush=True,
        )


def _benchmark_submission(task, submission_index, solution, submission, max_k):
    """Create one complete result row for a submission."""
    row = {
        field: ''
        for field in _fieldnames(max_k)
    }
    row.update({
        'task': task,
        'submission': str(submission_index),
        'parseable': 'false' if not submission else 'true',
    })
    if not submission:
        return row

    solution_min_states = _minimal_state_count_without_dead_state(solution)
    submission_min_states = _minimal_state_count_without_dead_state(submission)
    row.update({
        'solution_type': _automaton_type(solution),
        'submission_type': _automaton_type(submission),
        'solution_states': str(solution.get_number_of_states()),
        'submission_states': str(submission.get_number_of_states()),
        'solution_min_states': str(solution_min_states),
        'submission_min_states': str(submission_min_states),
        'solution_determinization_blowup': f'{_determinization_blowup(solution, solution_min_states):.9f}',
        'submission_determinization_blowup': f'{_determinization_blowup(submission, submission_min_states):.9f}',
    })

    start = perf_counter()
    equivalent = solution.equivalence_test(other=submission)
    row['language_equivalent'] = 'true' if equivalent else 'false'
    row['equivalence_runtime'] = f'{perf_counter() - start:.9f}'
    print(
        f'  language-equivalent: {row["language_equivalent"]} '
        f'({row["equivalence_runtime"]}s)',
        flush=True,
    )

    games = _create_games(solution, submission)
    for game_name in GAME_NAMES:
        _measure_game(
            game_name,
            games[game_name],
            row,
            max_k,
            game_name,
        )
    return row


def run(tasks: tuple[str, ...], output: Path, max_k: int):
    """Run all selected tasks and maintain the resumable CSV."""
    fieldnames = _fieldnames(max_k)
    rows = _load_rows(output, fieldnames)

    for task in tasks:
        solution = get_solution(exercise=task)
        FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
        iterator = SubmissionIterator(task=task)
        task_count = 0
        skipped = 0

        print(f'\nTask {task}', flush=True)
        for submission in iterator:
            task_count += 1
            submission_index = str(iterator.index)
            key = (task, submission_index)
            if key in rows:
                skipped += 1
                print(f'{task}{submission_index}: skipped', flush=True)
                continue

            print(f'{task}{submission_index}: measuring', flush=True)
            rows[key] = _benchmark_submission(
                task,
                submission_index,
                solution,
                submission,
                max_k,
            )
            _write_rows(output, rows, fieldnames)

        _write_rows(output, rows, fieldnames)
        print(
            f'Task {task} complete: {task_count - skipped} measured, '
            f'{skipped} skipped',
            flush=True,
        )


def parse_args():
    """Parse command-line options."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--task',
        choices=TASKS,
        action='append',
        dest='tasks',
        help='Task to run. May be supplied multiple times. Default: all tasks.',
    )
    parser.add_argument(
        '--max-k',
        type=int,
        default=MAX_K,
        help=f'Largest tested game size. Default: {MAX_K}.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f'CSV output path. Default: {DEFAULT_OUTPUT}.',
    )
    return parser.parse_args()


def main():
    """Run the resumable runtime benchmark."""
    args = parse_args()
    if args.max_k < 1:
        raise ValueError('--max-k must be at least 1.')
    run(tuple(args.tasks or TASKS), args.output, args.max_k)


if __name__ == '__main__':
    main()
