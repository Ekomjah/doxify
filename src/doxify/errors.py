class DoxifyError(Exception):
    """Base class for expected Doxify failures."""


class RepoError(DoxifyError):
    """The selected path is not a usable local git repository."""


class SessionError(DoxifyError):
    """A session directory is missing or invalid."""


class ModelError(DoxifyError):
    """Ollama is unavailable or the requested model is missing."""


class GenerationError(DoxifyError):
    """A section could not be generated or parsed."""
