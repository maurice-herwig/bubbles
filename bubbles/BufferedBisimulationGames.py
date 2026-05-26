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
                        # TODO weg nur zum testen hier
                        new_node = ((p, q), 'aa', i, m)
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

        print()

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
                        new_state_pair = (q, state_pair[1]) if i == 0 else (state_pair[0], q)
                        new_node = (new_state_pair, w, i, MOVES[MOVE])

                        if new_node in seen_nodes:
                            continue

                        if check_initial(*new_node):
                            return True

                        next_attractor.add(new_node)

                elif n == (self.buffer_size - 1):
                    # TODO kann von 1 oder 2 dahin gespielt worden sein
                    pass
                elif n < (self.buffer_size - 1):
                    # TODO kann nur von 1 dahin gespielt worden sein
                    pass

        return False
