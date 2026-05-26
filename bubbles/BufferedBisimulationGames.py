from wofa import FiniteAutomata
from .BisimulationGames import BisimulationGames

import pprint

MOVES = {0: "choice", 1: "move", 2: "flush", 3: "step"}


class BufferedBisimulationGames(BisimulationGames):

    # 0 -> choice
    # 1 > move
    # 2 -> flush
    # 3 -> step TODO: step wird nicht gebraucht...

    def __init__(self, automaton0: FiniteAutomata, automaton1: FiniteAutomata, buffer_size: int):

        assert buffer_size >= 1, "Buffer size must be at least 1"
        super().__init__(automaton0, automaton1)
        self.buffer_size = buffer_size

    def solve(self):

        finals = {i: self.automatons[i].get_finals() for i in range(2)}
        non_finals = {i: {s for s in range(self.automatons[i].get_number_of_states()) if s not in finals[i]}
                      for i in range(2)}
        initials = {i: self.automatons[i].get_initials() for i in range(2)}

        def check_initial(p, w, q, i, m):
            return p in initials[0] and q in initials[1] and w == '' and i == 0 and m == 0

        # TODO Datenstruktur für besseren zugriff optimieren
        attractor0 = set()
        for p in finals[0]:
            for q in non_finals[1]:
                for i in range(2):
                    for m in range(4):
                        if check_initial(p, '', q, i, m):
                            return True

                        attractor0.add((p, '', q, i, m))

        for p in non_finals[0]:
            for q in finals[1]:
                for i in range(2):
                    for m in range(4):
                        if check_initial(p, '', q, i, m):
                            return True

                        attractor0.add((p, '', q, i, m))

        # TODO ab hier aufräumen, da die Datenstruktur nicht optimal ist
        pprint.pprint(attractor0)
        current_attractor = attractor0
        seen_nodes = attractor0
        next_attractor = set()

        # TODO while loop mit Abbruchbedingung
        for (p, w, q, i, m) in current_attractor:

            # choice
            if m == 0:
                n = len(w)
                if n == self.buffer_size:
                    # kann nur von Spieler 1 darhin gespiellt worden sein
                    a = w[0]
                    v = w[1:]
                    pass
                elif n == (self.buffer_size - 1):
                    # TODO kann von 1 oder 2 dahin gespielt worden sein
                    pass
                elif n < (self.buffer_size - 1):
                    # TODO kann nur von 1 dahin gespielt worden sein
                    pass

        return False
