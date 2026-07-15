class AlphaBistError(Exception):
    """Base exception for AlphaBIST AI."""


class ConfigurationError(AlphaBistError):
    """Raised when application configuration is invalid."""


class ValidationError(AlphaBistError):
    """Raised when user input or financial data is invalid."""


class DataProviderError(AlphaBistError):
    """Raised when market or financial data provider fails."""


class ScoringError(AlphaBistError):
    """Raised when Alpha Score calculation fails."""