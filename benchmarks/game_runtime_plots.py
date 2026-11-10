"""Create runtime plots from the game runtime benchmark CSV."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_INPUT = Path(__file__).resolve().parent / 'tmp' / 'game_runtime.csv'
DEFAULT_OUTPUT = Path(__file__).resolve().parent / 'tmp' / 'game_runtime_plots'

GAMES = (
    ('buffered_simulation', 'Buffered simulation'),
    ('pebble_simulation', 'Pebble simulation'),
    ('buffered_bisimulation', 'Buffered bisimulation'),
)

K_MARKERS = ('o', 's', '^', 'D', 'P')
X_MEASURES = {
    'solution_blowup': (
        'Solution determinization quotient',
        lambda row: row['solution_blowup'],
    ),
    'submission_blowup': (
        'Submission determinization quotient',
        lambda row: row['submission_blowup'],
    ),
    'mean_blowup': (
        'Mean determinization quotient',
        lambda row: (
            row['solution_blowup']
            + row['submission_blowup']
        ) / 2,
    ),
    'max_blowup': (
        'Maximum determinization quotient',
        lambda row: max(
            row['solution_blowup'],
            row['submission_blowup'],
        ),
    ),
    'product_blowup': (
        'Product of determinization quotients',
        lambda row: (
            row['solution_blowup']
            * row['submission_blowup']
        ),
    ),
}


def _read_rows(input_path: Path) -> list[dict[str, str]]:
    """Read parseable rows with non-empty languages from the runtime CSV.

    A zero state ratio denotes an automaton whose productive state set is
    empty after dead-state removal. Such pairs are excluded from the plots.
    """
    with input_path.open(newline='', encoding='utf-8') as file:
        rows = []
        for row in csv.DictReader(file):
            if row.get('parseable') != 'true':
                continue
            try:
                solution_ratio = float(
                    row['solution_determinization_blowup']
                )
                submission_ratio = float(
                    row['submission_determinization_blowup']
                )
            except (KeyError, TypeError, ValueError):
                continue
            if solution_ratio == 0.0 or submission_ratio == 0.0:
                continue
            rows.append(row)
        return rows


def _numeric_rows(rows: list[dict[str, str]], game: str, k: int):
    """Extract rows with a measured runtime for one game and size."""
    runtime_field = f'{game}_k{k}_runtime'
    result_field = f'{game}_k{k}_result'
    for row in rows:
        try:
            runtime = float(row[runtime_field])
            n0 = float(row['solution_states'])
            n1 = float(row['submission_states'])
            solution_blowup = float(row['solution_determinization_blowup'])
            submission_blowup = float(row['submission_determinization_blowup'])
        except (KeyError, TypeError, ValueError):
            # Empty runtimes are expected for sizes inherited after a timeout.
            continue

        yield {
            'runtime': runtime,
            'normalized_runtime': runtime / (n0 + n1) if n0 + n1 else 0.0,
            'result': row[result_field],
            'solution_blowup': solution_blowup,
            'submission_blowup': submission_blowup,
            'solution_states': n0,
            'submission_states': n1,
        }


def _equivalence_rows(rows: list[dict[str, str]]):
    """Extract rows with a measured language-equivalence runtime."""
    for row in rows:
        try:
            runtime = float(row['equivalence_runtime'])
            n0 = float(row['solution_states'])
            n1 = float(row['submission_states'])
            solution_blowup = float(row['solution_determinization_blowup'])
            submission_blowup = float(row['submission_determinization_blowup'])
        except (KeyError, TypeError, ValueError):
            continue

        yield {
            'runtime': runtime,
            'normalized_runtime': runtime / (n0 + n1) if n0 + n1 else 0.0,
            'solution_blowup': solution_blowup,
            'submission_blowup': submission_blowup,
        }


def _plot_measure(
        rows: list[dict[str, str]],
        measure_name: str,
        measure_label: str,
        normalized: bool,
        output_path: Path,
):
    """Create one scatter plot for one x-axis measure."""
    figure, axis = plt.subplots(figsize=(11, 7))
    colors = ('tab:blue', 'tab:orange', 'tab:green')
    plotted = False

    for (game, game_label), color in zip(GAMES, colors):
        for k, marker in enumerate(K_MARKERS, start=1):
            points = list(_numeric_rows(rows, game, k))
            if not points:
                continue

            x_values = []
            y_values = []
            normal_points = []
            timeout_points = []
            x_getter = X_MEASURES[measure_name][1]
            for point in points:
                x_value = x_getter(point)
                y_value = (
                    point['normalized_runtime']
                    if normalized else point['runtime']
                )
                x_values.append(x_value)
                y_values.append(y_value)
                (timeout_points if point['result'] == 'timeout'
                 else normal_points).append((x_value, y_value))

            if normal_points:
                axis.scatter(
                    [point[0] for point in normal_points],
                    [point[1] for point in normal_points],
                    color=color,
                    marker=marker,
                    alpha=0.65,
                    label=f'{game_label}, k={k}',
                )
                plotted = True
            if timeout_points:
                axis.scatter(
                    [point[0] for point in timeout_points],
                    [point[1] for point in timeout_points],
                    color=color,
                    marker='x',
                    s=55,
                    linewidths=1.5,
                    alpha=0.9,
                    label=f'{game_label}, k={k}, timeout',
                )
                plotted = True

            # Aggregate equal x-values separately for every game and k.
            # Timeout measurements are deliberately excluded from the mean.
            average_points = defaultdict(list)
            for x_value, y_value in normal_points:
                average_points[x_value].append(y_value)
            if average_points:
                mean_points = sorted(
                    (
                        x_value,
                        sum(y_values) / len(y_values),
                    )
                    for x_value, y_values in average_points.items()
                )
                axis.plot(
                    [point[0] for point in mean_points],
                    [point[1] for point in mean_points],
                    color=color,
                    linestyle='--',
                    linewidth=1.5,
                    alpha=0.9,
                    label=f'{game_label}, k={k}, mean',
                )

    # The language-equivalence check is independent of k and is shown as a
    # separate series in every plot.
    equivalence_points = list(_equivalence_rows(rows))
    x_getter = X_MEASURES[measure_name][1]
    equivalence_values = [
        (
            x_getter(point),
            point['normalized_runtime'] if normalized else point['runtime'],
        )
        for point in equivalence_points
    ]
    if equivalence_values:
        axis.scatter(
            [point[0] for point in equivalence_values],
            [point[1] for point in equivalence_values],
            color='black',
            marker='v',
            alpha=0.65,
            label='Language equivalence',
        )
        equivalence_means = defaultdict(list)
        for x_value, y_value in equivalence_values:
            equivalence_means[x_value].append(y_value)
        mean_points = sorted(
            (
                x_value,
                sum(y_values) / len(y_values),
            )
            for x_value, y_values in equivalence_means.items()
        )
        axis.plot(
            [point[0] for point in mean_points],
            [point[1] for point in mean_points],
            color='black',
            linestyle='--',
            linewidth=1.5,
            alpha=0.9,
            label='Language equivalence, mean',
        )
        plotted = True

    if not plotted:
        plt.close(figure)
        return

    axis.set_xlabel(measure_label)
    axis.set_ylabel(
        'Runtime / (number of states in both automata) [s]'
        if normalized else 'Runtime [s]'
    )
    axis.set_yscale('log')
    axis.set_title(
        f'Game runtime vs. {measure_label.lower()}'
        + (' (state-normalized)' if normalized else '')
    )
    axis.text(
        0.01,
        0.01,
        'Dashed lines show means over non-timeout measurements.',
        transform=axis.transAxes,
        fontsize='small',
        alpha=0.75,
    )
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize='small', ncol=2)
    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def create_plots(input_path: Path, output_dir: Path):
    """Create all raw and state-normalized runtime plots."""
    rows = _read_rows(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    for measure_name, (measure_label, _) in X_MEASURES.items():
        for normalized in (False, True):
            suffix = 'normalized' if normalized else 'raw'
            output_path = output_dir / f'{measure_name}_{suffix}.png'
            _plot_measure(
                rows,
                measure_name,
                measure_label,
                normalized,
                output_path,
            )
            if output_path.exists():
                generated += 1
                print(f'created {output_path}')
    print(f'Generated {generated} plots from {len(rows)} parseable rows.')


def main():
    """Parse command-line arguments and create the plots."""
    parser = argparse.ArgumentParser(
        description='Plot game runtimes against determinization blow-up measures.'
    )
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f'input CSV does not exist: {args.input}')
    create_plots(args.input, args.output)


if __name__ == '__main__':
    main()
