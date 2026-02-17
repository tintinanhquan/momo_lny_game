class BotState:
    """Hold runtime board and automation counters."""

    def __init__(self) -> None:
        self.move_count = 0
        self.consecutive_failures = 0
