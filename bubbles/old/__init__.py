"""Legacy BUBBLES game implementations.

These classes implement the former game definitions and are kept available
for comparison and backwards compatibility while the new games are developed.
"""

from .BisimulationGames import BisimulationGames
from ..games import TwoWaySetMap
from .BufferedBisimulationGames import BufferedBisimulationGames
from .MultiPebbleBisimulationGames import MultiPebbleBisimulationGames

__all__ = [
    "BisimulationGames",
    "BufferedBisimulationGames",
    "MultiPebbleBisimulationGames",
    "TwoWaySetMap",
]
