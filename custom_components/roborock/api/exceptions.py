"""Roborock exceptions."""

class RoborockException(Exception):
    """Class for Roborock exceptions."""

class RoborockTimeout(RoborockException):
    """Class for Roborock timeout exceptions."""

class VacuumError(RoborockException):
    """Class for vacuum errors."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__()


class CommandVacuumError(RoborockException):
    """Class for command vacuum errors."""
    def __init__(self, command: str, vacuum_error: VacuumError):
        self.message = f"{command}: {str(vacuum_error)}"
        super().__init__(self.message)
