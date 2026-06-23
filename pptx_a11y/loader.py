from pptx import Presentation


class LoadError(Exception):
    """Raised when a .pptx cannot be opened (missing, corrupt, or not a pptx)."""


def load_presentation(path: str):
    try:
        return Presentation(path)
    except Exception as exc:  # noqa: BLE001 - any open failure is a load failure
        raise LoadError(f"Could not open {path}: {exc}") from exc
