"""Self-contained environment initialization for the edge counter service."""

from dotenv import find_dotenv, load_dotenv


def init_env(override: bool = False, dotenv_path: str | None = None) -> bool:
    """Find and load .env file into os.environ.

    Searches from current working directory upward if dotenv_path is not specified.
    Returns True if an env file was found and loaded, False otherwise.
    """
    path = dotenv_path or find_dotenv(usecwd=True)
    if path:
        return load_dotenv(dotenv_path=path, override=override)
    return False


__all__ = ["init_env"]

# Ensure unified module identity across standalone and monorepo import paths
import sys

_self_module = sys.modules.get(__name__)
if _self_module is not None:
    for _alias in ("src.env", "services.counter.src.env"):
        sys.modules.setdefault(_alias, _self_module)

