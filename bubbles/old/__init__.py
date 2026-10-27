"""Legacy BUBBLES game implementations.

These classes implement the former game definitions and are kept available
for comparison and backwards compatibility while the new games are developed.
"""

from .BisimulationGames import BisimulationGames
from .BufferedBisimulationGames import BufferedBisimulationGames
from .MultiPebbleBisimulationGames import MultiPebbleBisimulationGames
from .TwoWaySetMap import TwoWaySetMap

__all__ = [
    "BisimulationGames",
    "BufferedBisimulationGames",
    "MultiPebbleBisimulationGames",
    "TwoWaySetMap",
]
