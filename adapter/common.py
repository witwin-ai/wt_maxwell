"""Small shared conversion helpers for the maxwell adapter maps."""
from typing import Any, List, Optional, Tuple

TOL = 1e-6
_AXIS_VECTORS = {"Ex": (1.0, 0.0, 0.0), "Ey": (0.0, 1.0, 0.0), "Ez": (0.0, 0.0, 1.0)}
_LETTER_TO_FIELD = {"x": "Ex", "y": "Ey", "z": "Ez"}


def num(value: Any) -> float:
    """Component scalar (tensor or number) -> python float."""
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def vec(value: Any) -> List[float]:
    """Component vector (tensor or list) -> python floats."""
    seq = value.tolist() if hasattr(value, "tolist") else value
    return [float(v) for v in seq]


def axis_name(vector: Tuple[float, float, float]) -> Optional[str]:
    """"Ex"/"Ey"/"Ez" if ``vector`` is an axis unit vector, else None."""
    for name, axis in _AXIS_VECTORS.items():
        if all(abs(a - b) <= TOL for a, b in zip(vector, axis)):
            return name
    return None


def axis_field(letter: str) -> str:
    """Resolved axis letter "x"/"y"/"z" -> "Ex"/"Ey"/"Ez" (else "auto")."""
    return _LETTER_TO_FIELD.get(str(letter), "auto")


def freqs_to_studio(frequencies: Any) -> List[float]:
    """Platform frequencies tuple/None -> component list ([] = broadband)."""
    return [] if frequencies is None else [float(f) for f in frequencies]


def freqs_to_platform(values: Any) -> Optional[tuple]:
    """Component frequency list -> platform tuple, or None when empty (broadband)."""
    out = tuple(num(v) for v in (values or []))
    return out or None
