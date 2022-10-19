from datetime import datetime
from typing import List, TypedDict


class SignalHour(TypedDict):
    """Ecowatt hour signal"""

    pas: int
    hvalue: int


class Signal(TypedDict):
    """Ecowatt signal"""

    GenerationFichier: str
    jour: str
    dvalue: int
    message: str
    values: List[SignalHour]
