"""Roborock exceptions."""

class RoborockException(Exception):
    """Class for Roborock exceptions."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class VacuumError(RoborockException):
    """Class for vacuum errors."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(self.message)


class CommandVacuumError(RoborockException):
    """Class for command vacuum errors."""
    def __init__(self, command: str, vacuum_error: VacuumError):
        self.message = f"{command}: {str(vacuum_error)}"
        super().__init__(self.message)
