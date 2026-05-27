from wofa import FiniteAutomata
from .BisimulationGames import BisimulationGames

import pprint

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
        def check_initial(state_pair: tuple, w: str, i: int, m: int):
            # TODO aufschrieb aktuell nur für ein startzustand
            return state_pair[0] in initials[0] and state_pair[1] in initials[1] and w == '' and i == 0 and m == 0

        finals = {i: self.automatons[i].get_finals() for i in range(2)}
        non_finals = {i: {s for s in range(self.automatons[i].get_number_of_states()) if s not in finals[i]}
                      for i in range(2)}
        initials = {i: self.automatons[i].get_initials() for i in range(2)}

        def new_player1_node(state_pair: tuple, w: str, i: int, m: int):
            new_node = (state_pair, w, i, m)

            if new_node in all_attractor_nodes:
                return False

            # TODO überpüfen ob er aus der liste einer von player 2 nodes genommen werden kann die noch nicht im Attraktor sind.

            if check_initial(*new_node):
                return True

            all_attractor_nodes.add(new_node)
            new_attractor_nodes.add(new_node)
            return False

        def new_player2_node(state_pair: tuple, w: str, i: int, m: int):
            new_node = (state_pair, w, i, m)

            if new_node in all_attractor_nodes:
                return False

            # TODO Liste mit allen bereits gesehenen player 2 nodes, die nicht im attraktor sind.

            if m == MOVES[FLUSH]:
                if new_node in all_attractor_nodes:
                    return False

                # Compute all states that can be reached by flushing the buffer
                successors = used_automaton.get_successors(s=p, a=v[0]) if v else {p}
                for letter in v[1:]:
                    successors = {
                        successor
                        for s in successors
                        for successor in used_automaton.get_successors(s=s, a=letter)
                    }

                # Compute all nodes that can be reached by flushing the buffer
                successors_not_in_attractor = set()
                for successor in successors:
                    successor_state_pair = (state_pair[0], successor) if i == 0 else (successor, state_pair[1])
                    successor_node = (successor_state_pair, '', 1 - i, MOVES[MOVE])

                    if successor_node not in all_attractor_nodes:
                        successors_not_in_attractor.add(successor_node)

                # Check if all successors nodes are in the attractor, then player 2 have no choice to don't play into the attractor.
                if not successors_not_in_attractor:

                    if check_initial(*new_node):
                        return True

                    all_attractor_nodes.add(new_node)
                    new_attractor_nodes.add(new_node)
                else:
                    # TODO abspeichern in liste der bereits gesehen spieler 2 Knoten aber noch nicht im attraktor knoten.
                    pass
            elif m == MOVES[MOVE]:
                # TODO
                pass

            return False

        def add_moves_to_player1_node_for_choice_nodes(state_pair: tuple, aw: str, i: int):
            a = aw[0]
            w = aw[1:]

            for q in self.automatons[i].get_predecessors(s=state_pair[i], a=a):
                new_state_pair = (q, state_pair[1]) if i == 0 else (state_pair[0], q)
                if new_player1_node(state_pair=new_state_pair, w=w, i=i, m=MOVES[MOVE]):
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
                    for m in range(4):
                        new_node = ((p, q), '', i, m)
                        if check_initial(*new_node):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                        all_attractor_nodes.add(new_node)

        last_added_attractor_nodes = all_attractor_nodes.copy()
        new_attractor_nodes = set()

        # main loop
        while last_added_attractor_nodes:
            for (state_pair, aw, i, m) in last_added_attractor_nodes:

                # choice
                if m == MOVES[CHOICE]:
                    n = len(aw)
                    if n == self.buffer_size:
                        # kann nur von Spieler 1 darhin gespiellt worden sein
                        if add_moves_to_player1_node_for_choice_nodes(state_pair=state_pair, aw=aw, i=i):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                    elif n == (self.buffer_size - 1):
                        # kann von 1 oder 2 dahin gespielt worden sein
                        # case player 1
                        if add_moves_to_player1_node_for_choice_nodes(state_pair=state_pair, aw=aw, i=i):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                        # case plyer 2
                        # TODO

                    elif (self.buffer_size - 1) > n > 0:
                        # kann nur von 1 dahin gespielt worden sein
                        if add_moves_to_player1_node_for_choice_nodes(state_pair=state_pair, aw=aw, i=i):
                            return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                elif m == MOVES[FLUSH]:
                    if new_player1_node(state_pair=state_pair, w=aw, i=i, m=MOVES[CHOICE]):
                        return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                elif m == MOVES[MOVE]:
                    # Variante 1 Spieler 1 hat dorthin gespielt
                    if new_player1_node(state_pair=state_pair, w=aw, i=i, m=MOVES[CHOICE]):
                        return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

                    # Variante 2 Spieler 2 hat den buffer geleert
                    if aw == '':

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
                            new_state_pair = (state_pair[0], p) if i == 0 else (p, state_pair[1])
                            if new_player2_node(state_pair=new_state_pair, w=v, i=(1 - i), m=MOVES[FLUSH]):
                                return False, f'The automatas are not {self.buffer_size}-buffer equivalent'

            # Update for next iteration
            last_added_attractor_nodes = new_attractor_nodes.copy()
            new_attractor_nodes = set()

        #  Player 2 wins the game
        return True, f'The automatas are {self.buffer_size}-buffer equivalent'
