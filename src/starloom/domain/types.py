"""Domain enums for the starloom galaxy generator."""

from enum import Enum


class Size(int, Enum):
    TINY = 1
    SMALL = 2
    MEDIUM = 3
    LARGE = 4
    ENORMOUS = 5


class PlanetClass(str, Enum):
    TELLURIC = "TELLURIC"
    GASEOUS = "GASEOUS"
    ICE = "ICE"
    LAVA = "LAVA"
    LIQUID = "LIQUID"
    ASTEROID = "ASTEROID"


class TopographyType(str, Enum):
    CANYON = "CANYON"
    BASIN = "BASIN"
    KARST = "KARST"
    PLAINS = "PLAINS"
    HILLS = "HILLS"
    CLIFFS = "CLIFFS"
    PEAKS = "PEAKS"


class ClimateType(str, Enum):
    VOLCANIC = "VOLCANIC"
    ARID = "ARID"
    STEPPE = "STEPPE"
    TEMPERATE = "TEMPERATE"
    HUMID = "HUMID"
    RAINY = "RAINY"
    FROZEN = "FROZEN"


class LocationType(str, Enum):
    TRIBAL = "TRIBAL"
    TRADING = "TRADING"
    CITY = "CITY"
    METROPOLIS = "METROPOLIS"


class NodeType(str, Enum):
    """Placeholder — concrete values are defined by the content pack."""

    GENERIC = "GENERIC"


class NameStyle(str, Enum):
    GENERIC = "GENERIC"
    PERSON = "PERSON"
    RESIDENCE = "RESIDENCE"
    BAR = "BAR"


class ReproMode(str, Enum):
    COMPATIBLE = "compatible"
    STRICT = "strict"


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationStage(str, Enum):
    CONFIG = "config"
    CONTENT_PACK = "content_pack"
    CONSTRAINTS = "constraints"
