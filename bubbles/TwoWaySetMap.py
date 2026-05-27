from collections import defaultdict
from typing import DefaultDict, Iterable


class TwoWaySetMap:

    def __init__(self):
        self._forward: DefaultDict[tuple, set[tuple]] = defaultdict(set)
        self._reverse: DefaultDict[tuple, set[tuple]] = defaultdict(set)

    def add(self, key: tuple, value: tuple):
        self._forward[key].add(value)
        self._reverse[value].add(key)

    def add_many(self, key: tuple, values: Iterable[tuple]):
        for value in values:
            self.add(key, value)

    def has_key(self, key: tuple) -> bool:
        return key in self._forward

    def has_value(self, value: tuple) -> bool:
        return value in self._reverse

    def get_values(self, key: tuple) -> set[tuple]:
        return set(self._forward.get(key, set()))

    def get_keys(self, value: tuple) -> set[tuple]:
        return set(self._reverse.get(value, set()))

    def remove(self, key: tuple, value: tuple) -> bool:
        if key not in self._forward or value not in self._forward[key]:
            return False

        self._forward[key].remove(value)
        if not self._forward[key]:
            del self._forward[key]

        self._reverse[value].remove(key)
        if not self._reverse[value]:
            del self._reverse[value]

        return True

    def remove_value_everywhere(self, value: tuple) -> set[tuple]:
        if value not in self._reverse:
            return set()

        affected_keys = set(self._reverse.pop(value))
        empty_keys = set()

        for key in affected_keys:
            self._forward[key].remove(value)
            if not self._forward[key]:
                del self._forward[key]
                empty_keys.add(key)

        return empty_keys

    def remove_key(self, key: tuple) -> set[tuple]:
        if key not in self._forward:
            return set()

        removed_values = self._forward.pop(key)
        for value in removed_values:
            self._reverse[value].remove(key)
            if not self._reverse[value]:
                del self._reverse[value]

        return set(removed_values)

    def is_empty_for_key(self, key: tuple) -> bool:
        return not self._forward.get(key)

    def keys(self) -> set[tuple]:
        return set(self._forward.keys())

    def values(self) -> set[tuple]:
        return set(self._reverse.keys())

    def items(self) -> dict[tuple, set[tuple]]:
        return {key: set(values) for key, values in self._forward.items()}
