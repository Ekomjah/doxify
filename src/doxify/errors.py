class DoxifyError(Exception):
    """Base class for expected Doxify failures."""


class RepoError(DoxifyError):
    """The selected path is not a usable local git repository."""


class SessionError(DoxifyError):
    """A session directory is missing or invalid."""


class ModelError(DoxifyError):
    """The configured Ollama local or cloud endpoint is unavailable."""


class GenerationError(DoxifyError):
    """A section could not be generated or parsed."""


class ScoutError(DoxifyError):
    """Release notes could not be fetched, extracted, or matched."""
