from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter

from wofa import FiniteAutomata, SubmissionIterator, get_solution

from bubbles import BufferedBisimulationGames, MultiPebbleBisimulationGames

MAX_BUFFER_PEBBLE_SIZE = 2
TASKS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S']


@dataclass
class BlowupStats:
    nfa_states: int
    dfa_states: int
    ratio: float
    fraction_of_powerset: float


def clone_automaton(automaton: FiniteAutomata) -> FiniteAutomata:
    """Return a structural copy so benchmark operations cannot mutate inputs."""
    return FiniteAutomata(
        initials=set(automaton.get_initials()),
        transitions=list(automaton.get_transitions()),
        finals=set(automaton.get_finals()),
    )


def count_reachable_determinized_states(automaton: FiniteAutomata) -> int:
    """Count reachable subset states created by the powerset construction.

    This intentionally does not minimize the resulting DFA. The metric is meant
    to capture determinization blow-up, not the size of the minimal DFA.
    """
    initial_subset = frozenset(automaton.get_initials())
    seen = {initial_subset}
    todo = [initial_subset]

    while todo:
        subset = todo.pop()

        for letter in FiniteAutomata.get_alphabet():
            successor_subset = frozenset(
                successor
                for state in subset
                for successor in automaton.get_successors(s=state, a=letter)
            )

            if successor_subset not in seen:
                seen.add(successor_subset)
                todo.append(successor_subset)

    return len(seen)


def calc_blowup_stats(automaton: FiniteAutomata) -> BlowupStats:
    nfa_states = automaton.get_number_of_states()
    dfa_states = count_reachable_determinized_states(automaton)

    return BlowupStats(
        nfa_states=nfa_states,
        dfa_states=dfa_states,
        ratio=dfa_states / nfa_states if nfa_states else 0.0,
        fraction_of_powerset=dfa_states / (2 ** nfa_states) if nfa_states else 0.0,
    )


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def format_seconds(value: float | None) -> str:
    return f'{value:.6f}s' if value is not None else 'n/a'


def print_task_summary(task: str, summary: dict):
    print()
    print(f'Task {task}')
    print('------')
    print(f'Total submissions: {summary["total_submissions"]}')
    print(f'Non-parseable submissions: {summary["non_parseable"]}')
    print(f'Measured pairs: {summary["measured_pairs"]}')
    print(f'Equivalent pairs: {summary["equivalent_pairs"]}')
    print(f'Average pair blow-up max: {average(summary["pair_blowup_max"]):.6f}')
    print(f'Max pair blow-up max: {max(summary["pair_blowup_max"], default=0.0):.6f}')
    print(f'Average pair DFA states sum: {average(summary["pair_dfa_states_sum"]):.2f}')
    print(f'Average equivalence-test runtime: {format_seconds(average(summary["eq_runtimes"]))}')

    for k in range(1, MAX_BUFFER_PEBBLE_SIZE + 1):
        print(
            f'k={k}: '
            f'buffer avg {format_seconds(average(summary["buffer_runtimes"][k]))}, '
            f'pebble avg {format_seconds(average(summary["pebble_runtimes"][k]))}, '
            f'buffer/eq avg {average(summary["buffer_over_eq"][k]) or 0.0:.6f}, '
            f'pebble/eq avg {average(summary["pebble_over_eq"][k]) or 0.0:.6f}'
        )


def blowup_bucket(pair_blowup_max: float) -> str:
    if pair_blowup_max <= 1:
        return '<=1'
    if pair_blowup_max <= 2:
        return '<=2'
    if pair_blowup_max <= 5:
        return '<=5'
    if pair_blowup_max <= 10:
        return '<=10'
    return '>10'


def print_bucket_summary(records: list[dict]):
    buckets = defaultdict(list)
    for record in records:
        buckets[blowup_bucket(record['pair_blowup_max'])].append(record)

    print()
    print('Runtime by Blow-up Bucket')
    print('-------------------------')

    for bucket in ('<=1', '<=2', '<=5', '<=10', '>10'):
        bucket_records = buckets[bucket]
        if not bucket_records:
            print(f'{bucket}: no measurements')
            continue

        eq_runtimes = [record['eq_runtime'] for record in bucket_records]
        avg_blowup = average([record['pair_blowup_max'] for record in bucket_records])
        print(
            f'{bucket}: {len(bucket_records)} pairs, '
            f'avg blow-up max {avg_blowup:.6f}, '
            f'eq avg {format_seconds(average(eq_runtimes))}'
        )

        for k in range(1, MAX_BUFFER_PEBBLE_SIZE + 1):
            buffer_runtimes = [record['buffer_runtimes'][k] for record in bucket_records]
            pebble_runtimes = [record['pebble_runtimes'][k] for record in bucket_records]
            buffer_over_eq = [
                record['buffer_runtimes'][k] / record['eq_runtime']
                for record in bucket_records
                if record['eq_runtime'] > 0
            ]
            pebble_over_eq = [
                record['pebble_runtimes'][k] / record['eq_runtime']
                for record in bucket_records
                if record['eq_runtime'] > 0
            ]
            print(
                f'  k={k}: '
                f'buffer avg {format_seconds(average(buffer_runtimes))}, '
                f'pebble avg {format_seconds(average(pebble_runtimes))}, '
                f'buffer/eq avg {average(buffer_over_eq) or 0.0:.6f}, '
                f'pebble/eq avg {average(pebble_over_eq) or 0.0:.6f}'
            )


def new_summary() -> dict:
    return {
        'total_submissions': 0,
        'non_parseable': 0,
        'measured_pairs': 0,
        'equivalent_pairs': 0,
        'pair_blowup_max': [],
        'pair_blowup_sum': [],
        'pair_dfa_states_sum': [],
        'eq_runtimes': [],
        'buffer_runtimes': defaultdict(list),
        'pebble_runtimes': defaultdict(list),
        'buffer_over_eq': defaultdict(list),
        'pebble_over_eq': defaultdict(list),
        'records': [],
    }


def add_summary(target: dict, source: dict):
    for key in ('total_submissions', 'non_parseable', 'measured_pairs', 'equivalent_pairs'):
        target[key] += source[key]

    for key in ('pair_blowup_max', 'pair_blowup_sum', 'pair_dfa_states_sum', 'eq_runtimes'):
        target[key].extend(source[key])

    target['records'].extend(source['records'])

    for k in range(1, MAX_BUFFER_PEBBLE_SIZE + 1):
        target['buffer_runtimes'][k].extend(source['buffer_runtimes'][k])
        target['pebble_runtimes'][k].extend(source['pebble_runtimes'][k])
        target['buffer_over_eq'][k].extend(source['buffer_over_eq'][k])
        target['pebble_over_eq'][k].extend(source['pebble_over_eq'][k])


def run_task(task: str) -> dict:
    summary = new_summary()

    solution = get_solution(exercise=task)
    FiniteAutomata.set_alphabet(solution.calc_and_get_alphabet())
    iterator = SubmissionIterator(task=task)

    for submission in iterator:
        print(f'{task}{iterator.index}')
        summary['total_submissions'] += 1

        if not submission:
            summary['non_parseable'] += 1
            continue

        buffered_game = BufferedBisimulationGames(
            automaton0=clone_automaton(solution),
            automaton1=clone_automaton(submission),
            buffer_size=1,
        )
        prepared_automatons = buffered_game.get_automatons()
        automaton0 = prepared_automatons[0]
        automaton1 = prepared_automatons[1]

        blowup0 = calc_blowup_stats(automaton0)
        blowup1 = calc_blowup_stats(automaton1)
        pair_blowup_max = max(blowup0.ratio, blowup1.ratio)
        pair_blowup_sum = blowup0.ratio + blowup1.ratio
        pair_dfa_states_sum = blowup0.dfa_states + blowup1.dfa_states

        start_time = perf_counter()
        equivalent = automaton0.equivalence_test(other=automaton1)
        eq_runtime = perf_counter() - start_time

        summary['measured_pairs'] += 1
        summary['equivalent_pairs'] += int(equivalent)
        summary['pair_blowup_max'].append(pair_blowup_max)
        summary['pair_blowup_sum'].append(pair_blowup_sum)
        summary['pair_dfa_states_sum'].append(pair_dfa_states_sum)
        summary['eq_runtimes'].append(eq_runtime)

        record = {
            'task': task,
            'submission_index': iterator.index,
            'equivalent': equivalent,
            'nfa_states_0': blowup0.nfa_states,
            'nfa_states_1': blowup1.nfa_states,
            'dfa_states_0': blowup0.dfa_states,
            'dfa_states_1': blowup1.dfa_states,
            'blowup_0': blowup0.ratio,
            'blowup_1': blowup1.ratio,
            'pair_blowup_max': pair_blowup_max,
            'pair_blowup_sum': pair_blowup_sum,
            'pair_dfa_states_sum': pair_dfa_states_sum,
            'eq_runtime': eq_runtime,
            'buffer_runtimes': {},
            'pebble_runtimes': {},
        }

        multi_pebble_game = MultiPebbleBisimulationGames(
            automaton0=clone_automaton(automaton0),
            automaton1=clone_automaton(automaton1),
            pebbles=1,
        )

        for k in range(1, MAX_BUFFER_PEBBLE_SIZE + 1):
            buffered_game.set_buffer_size(buffer_size=k)
            start_time = perf_counter()
            buffer_similar, _ = buffered_game.solve()
            buffer_runtime = perf_counter() - start_time

            multi_pebble_game.set_pebbles(pebbles=k)
            start_time = perf_counter()
            pebble_similar, _ = multi_pebble_game.solve()
            pebble_runtime = perf_counter() - start_time

            if buffer_similar and not equivalent:
                raise Exception(
                    f'{task}{iterator.index}: not equivalent but {k}-buffer bisimilar'
                )

            if pebble_similar != buffer_similar:
                raise Exception(
                    f'{task}{iterator.index}: {k}-pebble and {k}-buffer results differ'
                )

            summary['buffer_runtimes'][k].append(buffer_runtime)
            summary['pebble_runtimes'][k].append(pebble_runtime)
            record['buffer_runtimes'][k] = buffer_runtime
            record['pebble_runtimes'][k] = pebble_runtime

            if eq_runtime > 0:
                summary['buffer_over_eq'][k].append(buffer_runtime / eq_runtime)
                summary['pebble_over_eq'][k].append(pebble_runtime / eq_runtime)

        summary['records'].append(record)

    return summary


if __name__ == '__main__':
    global_summary = new_summary()

    for task in TASKS:
        task_summary = run_task(task)
        print_task_summary(task, task_summary)
        add_summary(global_summary, task_summary)

    print()
    print('Global Summary')
    print('--------------')
    print(f'Tasks: {", ".join(TASKS)}')
    print(f'Total submissions: {global_summary["total_submissions"]}')
    print(f'Non-parseable submissions: {global_summary["non_parseable"]}')
    print(f'Measured pairs: {global_summary["measured_pairs"]}')
    print(f'Equivalent pairs: {global_summary["equivalent_pairs"]}')
    print(f'Average pair blow-up max: {average(global_summary["pair_blowup_max"]):.6f}')
    print(f'Max pair blow-up max: {max(global_summary["pair_blowup_max"], default=0.0):.6f}')
    print(f'Average pair blow-up sum: {average(global_summary["pair_blowup_sum"]):.6f}')
    print(f'Average pair DFA states sum: {average(global_summary["pair_dfa_states_sum"]):.2f}')
    print(f'Average equivalence-test runtime: {format_seconds(average(global_summary["eq_runtimes"]))}')

    for k in range(1, MAX_BUFFER_PEBBLE_SIZE + 1):
        print(
            f'k={k}: '
            f'buffer avg {format_seconds(average(global_summary["buffer_runtimes"][k]))}, '
            f'pebble avg {format_seconds(average(global_summary["pebble_runtimes"][k]))}, '
            f'buffer/eq avg {average(global_summary["buffer_over_eq"][k]) or 0.0:.6f}, '
            f'pebble/eq avg {average(global_summary["pebble_over_eq"][k]) or 0.0:.6f}'
        )

    print_bucket_summary(global_summary['records'])
