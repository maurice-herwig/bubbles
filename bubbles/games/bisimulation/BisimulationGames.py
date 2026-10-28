from typing import Callable

from ...util.TwoWaySetMap import TwoWaySetMap
from ..Games import Games


class BisimulationGames(Games):
    """Base class for the newly defined bisimulation games."""

    @staticmethod
    def propagate_new_attractor_nodes(
            nodes_to_process: list[tuple],
            all_attractor_nodes: set[tuple],
            new_attractor_nodes: set[tuple],
            seen_player2_nodes_not_in_attractor: TwoWaySetMap,
            check_initial: Callable[..., bool],
    ) -> bool:
        """Propagate the player-I attractor through stored player-II obligations.

        For player-II nodes we must realize the universal predecessor rule:
        a player-II node enters the attractor iff all of its successors already
        belong to the attractor.

        The map `seen_player2_nodes_not_in_attractor` stores, for every
        player-II node not yet in the attractor, the successors that are still
        outside the attractor. Whenever one of these successors enters the
        attractor, this method removes it from the pending obligations and adds
        newly discharged player-II nodes to the attractor.
        """
        while nodes_to_process:
            propagated_node = nodes_to_process.pop()

            if not seen_player2_nodes_not_in_attractor.has_value(propagated_node):
                continue

            for new_player2_attractor_node in seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                    propagated_node):

                if new_player2_attractor_node in all_attractor_nodes:
                    continue

                if check_initial(*new_player2_attractor_node):
                    return True

                all_attractor_nodes.add(new_player2_attractor_node)
                new_attractor_nodes.add(new_player2_attractor_node)
                nodes_to_process.append(new_player2_attractor_node)

        return False

