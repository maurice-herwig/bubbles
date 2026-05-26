from wofa import FiniteAutomata
from .BisimulationGames import BisimulationGames

import pprint

CHOICE = "CHOICE"
MOVE = "MOVE"
FLUSH = "FLUSH"
MOVES = {CHOICE: 0, MOVE: 1, FLUSH: 2}


class BufferedBisimulationGames(BisimulationGames):

    # 0 -> choice
    # 1 > move
    # 2 -> flush

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata, buffer_size: int):

        assert buffer_size >= 1, "Buffer size must be at least 1"
        super().__init__(automaton0, automaton1)
        self.buffer_size = buffer_size

    def solve(self):

        finals = {i: self.automatons[i].get_finals() for i in range(2)}
        non_finals = {i: {s for s in range(self.automatons[i].get_number_of_states()) if s not in finals[i]}
                      for i in range(2)}
        initials = {i: self.automatons[i].get_initials() for i in range(2)}

        def check_initial(state_pair: tuple, w: str, i: int, m: int):
            # TODO aufschrieb aktuell nur für ein startzustand
            return state_pair[0] in initials[0] and state_pair[1] in initials[1] and w == '' and i == 0 and m == 0

        # TODO Datenstruktur für besseren zugriff optimieren
        attractor0 = set()
        for p in finals[0]:
            for q in non_finals[1]:
                for i in range(2):
                    for m in range(3):
                        new_node = ((p, q), '', i, m)
                        if check_initial(*new_node):
                            return True

                        attractor0.add(new_node)

        for p in non_finals[0]:
            for q in finals[1]:
                for i in range(2):
                    for m in range(4):
                        new_node = ((p, q), '', i, m)
                        if check_initial(*new_node):
                            return True

                        attractor0.add(new_node)

        # TODO ab hier aufräumen, da die Datenstruktur nicht optimal ist
        pprint.pprint(attractor0)
        current_attractor = attractor0
        seen_nodes = attractor0
        next_attractor = set()

        # TODO hilfsfunktionen für Player 1 nodes and player 2 nodes

        # TODO while loop mit Abbruchbedingung
        for (state_pair, aw, i, m) in current_attractor:

            # choice
            if m == MOVES[CHOICE]:
                n = len(aw)
                if n == self.buffer_size:
                    # kann nur von Spieler 1 darhin gespiellt worden sein
                    a = aw[0]
                    w = aw[1:]

                    for q in self.automatons[i].get_predecessors(s=state_pair[i], a=a):
                        new_state_pair = (q, state_pair[1]) if i == 0 else (state_pair[0], q)  # TODO checken
                        new_node = (new_state_pair, w, i, MOVES[MOVE])

                        if new_node in seen_nodes:
                            continue

                        if check_initial(*new_node):
                            return True

                        seen_nodes.add(new_node)
                        next_attractor.add(new_node)

                elif n == (self.buffer_size - 1):
                    # TODO kann von 1 oder 2 dahin gespielt worden sein
                    pass
                elif n < (self.buffer_size - 1):
                    # kann nur von 1 dahin gespielt worden sein
                    # TODO müsste gleich zu wenn n == self.buffer_size sein
                    # TODO überprüfen ob n nicht mindestens 1 sein muss, bin ich mir aktuell nicht ganz sicher
                    pass
            elif m == MOVES[FLUSH]:
                new_node = (state_pair, aw, i, MOVES[CHOICE])

                if check_initial(*new_node):
                    return True

                seen_nodes.add(new_node)
                next_attractor.add(new_node)

            elif m == MOVES[MOVE]:
                # Variante 1 Spieler 1 hat dorthin gespielt
                new_node = (state_pair, aw, i, MOVES[CHOICE])

                if check_initial(*new_node):
                    return True

                seen_nodes.add(new_node)
                next_attractor.add(new_node)

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

                    # TODO das in eine eigne Funktion packen
                    # Für alle Flush nodes die möglichen nachfolger nodes bestimmen
                    for p, v in pos_flash:

                        new_state_pair = (p, state_pair[1]) if i == 0 else (state_pair[0], p)  # TODO checken
                        new_node = (new_state_pair, v, 1 - i, MOVES[FLUSH])

                        if new_node in seen_nodes:
                            continue

                        successors = used_automaton.get_successors(s=p, a=v[0]) if v else {p}
                        for a in v[1:]:
                            successors = {
                                successor
                                for s in successors
                                for successor in used_automaton.get_successors(s=s, a=a)
                            }

                        # TODO für alle diese möglichkeiten den Buffer zu leeren überprüfen ob alle Knoten bereits in
                        #  im Attraktor sind, wenn nicht abspeichern mit den Knoten die noch dem Attraktor hinzugefügt werden können.
