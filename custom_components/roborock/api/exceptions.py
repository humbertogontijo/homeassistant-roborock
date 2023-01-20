"""Roborock exceptions."""

class RoborockException(BaseException):
    """Class for Roborock exceptions."""

class RoborockTimeout(RoborockException):
    """Class for Roborock timeout exceptions."""

class RoborockBackoffException(RoborockException):
    """Class for Roborock exceptions when many retries were made."""

class VacuumError(RoborockException):
    """Class for vacuum errors."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__()

    def __str__(self, *args, **kwargs): # real signature unknown
        """ Return str(self). """
        return f"{self.code}: {self.message}"


class CommandVacuumError(RoborockException):
    """Class for command vacuum errors."""
    def __init__(self, command: str, vacuum_error: VacuumError):
        self.message = f"{command}: {str(vacuum_error)}"
        super().__init__(self.message)
