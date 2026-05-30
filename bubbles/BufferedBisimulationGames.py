from wofa import FiniteAutomata
from .BisimulationGames import BisimulationGames
from .TwoWaySetMap import TwoWaySetMap

CHOICE = "CHOICE"
MOVE = "MOVE"
FLUSH = "FLUSH"
MOVES = {CHOICE: 0, MOVE: 1, FLUSH: 2}


class BufferedBisimulationGames(BisimulationGames):

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata, buffer_size: int):

        assert buffer_size >= 1, "Buffer size must be at least 1"
        super().__init__(automaton0, automaton1)
        self.buffer_size = buffer_size

    def solve(self):

        # =====================
        # auxiliary functions
        # =====================
        def check_initial(node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            # TODO aufschrieb aktuell nur für ein startzustand
            return (
                    node_state_pair[0] in initials[0]
                    and node_state_pair[1] in initials[1]
                    and buffer_word == ''
                    and automaton_index == 0
                    and move_type == 0
            )

        finals = {i: self.automatons[i].get_finals() for i in range(2)}
        non_finals = {i: {s for s in range(self.automatons[i].get_number_of_states()) if s not in finals[i]}
                      for i in range(2)}
        initials = {i: self.automatons[i].get_initials() for i in range(2)}

        def propagate_new_attractor_nodes(nodes: list[tuple]) -> bool:
            while nodes:
                propagated_node = nodes.pop()

                if not seen_player2_nodes_not_in_attractor.has_value(propagated_node):
                    continue

                for new_player_2_attractor_node in seen_player2_nodes_not_in_attractor.remove_value_everywhere(
                        propagated_node):

                    if new_player_2_attractor_node in all_attractor_nodes:
                        continue

                    if check_initial(*new_player_2_attractor_node):
                        return True

                    all_attractor_nodes.add(new_player_2_attractor_node)
                    new_attractor_nodes.add(new_player_2_attractor_node)
                    nodes.append(new_player_2_attractor_node)

            return False

        def new_player1_node(
                node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            new_node = (node_state_pair, buffer_word, automaton_index, move_type)

            if new_node in all_attractor_nodes:
                return False

            if check_initial(*new_node):
                return True

            all_attractor_nodes.add(new_node)
            new_attractor_nodes.add(new_node)
            return propagate_new_attractor_nodes([new_node])

        def new_player2_node(
                node_state_pair: tuple, buffer_word: str, automaton_index: int, move_type: int):
            new_node = (node_state_pair, buffer_word, automaton_index, move_type)

            if new_node in all_attractor_nodes:
                return False

            if seen_player2_nodes_not_in_attractor.has_key(new_node):
                return False

            successors_not_in_attractor = set()

            if move_type == MOVES[FLUSH]:
                used_automaton: FiniteAutomata = self.automatons[1 - automaton_index]
                current_state = node_state_pair[1 - automaton_index]

                # Compute all states that can be reached by flushing the buffer
                successors = (
                    used_automaton.get_successors(s=current_state, a=buffer_word[0])
                    if buffer_word
                    else {current_state}
                )
                for letter in buffer_word[1:]:
                    successors = {
                        successor
                        for successor_state in successors
                        for successor in used_automaton.get_successors(s=successor_state, a=letter)
                    }

                # Compute all nodes that can be reached by flushing the buffer
                for successor in successors:
                    successor_state_pair = (
                        (node_state_pair[0], successor)
                        if automaton_index == 0
                        else (successor, node_state_pair[1])
                    )
                    successor_node = (successor_state_pair, '', 1 - automaton_index, MOVES[MOVE])

                    if successor_node not in all_attractor_nodes:
                        successors_not_in_attractor.add(successor_node)

            elif move_type == MOVES[MOVE]:
                assert buffer_word, "Player-II MOVE nodes must have a non-empty buffer."

                last_letter = buffer_word[-1]
                remaining_word = buffer_word[:-1]

                for successor_state in self.automatons[1 - automaton_index].get_successors(
                        s=node_state_pair[1 - automaton_index], a=last_letter):
                    successor_node = ((
                                          (node_state_pair[0], successor_state)
                                          if automaton_index == 0
                                          else (successor_state, node_state_pair[1])
                                      ), remaining_word, automaton_index, MOVES[CHOICE])

                    if successor_node not in all_attractor_nodes:
                        successors_not_in_attractor.add(successor_node)

            # Check if all successors nodes are in the attractor, then player 2 have no choice to don't play into
            # the attractor.
            if not successors_not_in_attractor:

                if check_initial(*new_node):
                    return True

                all_attractor_nodes.add(new_node)
                new_attractor_nodes.add(new_node)
                if propagate_new_attractor_nodes([new_node]):
                    return True
            else:
                # Add all not in attractor successor nodes to the list of seen player 2 nodes that are
                # not in the attractor, so we can check later if we possibly add some of them to the attractor,
                # if we have also add the new node to the attractor.
                seen_player2_nodes_not_in_attractor.add_many(new_node, successors_not_in_attractor)

            return False

        def add_moves_to_player1_node_for_choice_nodes(
                node_state_pair: tuple, extended_buffer_word: str, automaton_index: int):
            if not extended_buffer_word:
                return False

            first_letter = extended_buffer_word[0]
            remaining_word = extended_buffer_word[1:]

            for predecessor_state in self.automatons[automaton_index].get_predecessors(
                    s=node_state_pair[automaton_index], a=first_letter):
                if new_player1_node(
                        node_state_pair=(
                                (predecessor_state, node_state_pair[1])
                                if automaton_index == 0
                                else (node_state_pair[0], predecessor_state)
                        ),
                        buffer_word=remaining_word,
                        automaton_index=automaton_index,
                        move_type=MOVES[MOVE],
                ):
                    return True

            return False

        # =====================
        # End of the auxiliary functions
        # =====================

        # TODO Datenstruktur für besseren zugriff optimieren
        all_attractor_nodes = set()

        for p in finals[0]:
            for q in non_finals[1]:
                for i in range(2):
                    for m in range(3):
                        new_node = ((p, q), '', i, m)
                        if check_initial(*new_node):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                        all_attractor_nodes.add(new_node)

        for p in non_finals[0]:
            for q in finals[1]:
                for i in range(2):
                    for m in range(3):
                        new_node = ((p, q), '', i, m)
                        if check_initial(*new_node):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                        all_attractor_nodes.add(new_node)

        seen_player2_nodes_not_in_attractor = TwoWaySetMap()
        last_added_attractor_nodes = all_attractor_nodes.copy()
        new_attractor_nodes = set()

        # main loop
        while last_added_attractor_nodes:
            for (state_pair, current_buffer_word, i, m) in last_added_attractor_nodes:

                # choice
                if m == MOVES[CHOICE]:
                    n = len(current_buffer_word)
                    if n == self.buffer_size:
                        # kann nur von Spieler 1 darhin gespiellt worden sein
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=i,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                    elif n == (self.buffer_size - 1):
                        # kann von 1 oder 2 dahin gespielt worden sein
                        # case player 1
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=i,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                        # case plyer 2
                        for q, a in self.automatons[1 - i].get_all_predecessors_with_letter(s=state_pair[1 - i]):
                            new_state_pair = (state_pair[0], q) if i == 0 else (q, state_pair[1])
                            if new_player2_node(
                                    node_state_pair=new_state_pair,
                                    buffer_word=current_buffer_word + a,
                                    automaton_index=i,
                                    move_type=MOVES[MOVE],
                            ):
                                return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                    elif (self.buffer_size - 1) > n > 0:
                        # kann nur von 1 dahin gespielt worden sein
                        if add_moves_to_player1_node_for_choice_nodes(
                                node_state_pair=state_pair,
                                extended_buffer_word=current_buffer_word,
                                automaton_index=i,
                        ):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                elif m == MOVES[FLUSH]:
                    if new_player1_node(
                            node_state_pair=state_pair,
                            buffer_word=current_buffer_word,
                            automaton_index=i,
                            move_type=MOVES[CHOICE],
                    ):
                        return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                elif m == MOVES[MOVE]:
                    # Variante 1 Spieler 1 hat dorthin gespielt
                    if new_player1_node(
                            node_state_pair=state_pair,
                            buffer_word=current_buffer_word,
                            automaton_index=i,
                            move_type=MOVES[CHOICE],
                    ):
                        return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                    # Variante 2 Spieler 2 hat den buffer geleert
                    if current_buffer_word == '':

                        # Alle Flush nodes bestimmen
                        used_automaton: FiniteAutomata = self.automatons[i]
                        pos_flash = {(state_pair[i], '')}

                        predecessors = used_automaton.get_all_predecessors_with_letter(s=state_pair[i])
                        pos_flash.update(predecessors)
                        for _ in range(self.buffer_size - 1):
                            new_predecessors = set()
                            for p, v in predecessors:
                                for q, a in used_automaton.get_all_predecessors_with_letter(s=p):
                                    new_predecessors.add((q, a + v))
                            pos_flash.update(new_predecessors)
                            predecessors = new_predecessors.copy()

                        # Für alle Flush nodes die möglichen nachfolger nodes bestimmen
                        for p, v in pos_flash:
                            new_state_pair = (p, state_pair[1]) if i == 0 else (state_pair[0], p)
                            if new_player2_node(
                                    node_state_pair=new_state_pair,
                                    buffer_word=v,
                                    automaton_index=(1 - i),
                                    move_type=MOVES[FLUSH],
                            ):
                                return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

            # Update for next iteration
            last_added_attractor_nodes = new_attractor_nodes.copy()
            new_attractor_nodes = set()

        #  Player 2 wins the game
        return True, f'The automatas are {self.buffer_size}-buffer equivalent'
