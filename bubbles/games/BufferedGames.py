"""Shared infrastructure for games with a finite buffer."""


class BufferedGamesMixin:
    """Provide common buffer configuration for concrete buffered games.

    The mixin deliberately does not inherit from :class:`Games`. It can be
    combined with either ``BisimulationGames`` or ``SimulationGames`` without
    changing their separate game hierarchies.
    """

    def _init_buffer(self, buffer_size: int):
        """Initialize the buffer capacity after validating it."""
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")
        self.buffer_size = buffer_size

    def set_buffer_size(self, buffer_size: int):
        """Set the buffer capacity used by subsequent solver calls."""
        if buffer_size < 1:
            raise ValueError("Buffer size must be at least 1.")
        self.buffer_size = buffer_size
