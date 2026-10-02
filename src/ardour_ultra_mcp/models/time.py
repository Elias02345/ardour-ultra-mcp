from typing import Annotated, Literal

from pydantic import Field

from .base import Finite, Model, Samples

TICKS_PER_QUARTER = 1920  # Temporal::ticks_per_beat, verified in Ardour 9.8 source


MAX_QUARTER_TICKS = 2147483647 * TICKS_PER_QUARTER + (TICKS_PER_QUARTER - 1)
QuarterTicks = Annotated[int, Field(strict=True, ge=0, le=MAX_QUARTER_TICKS)]


class SamplePosition(Model):
    unit: Literal["samples"] = "samples"
    samples: Samples


class SecondPosition(Model):
    unit: Literal["seconds"] = "seconds"
    seconds: Annotated[Finite, Field(ge=0, le=1e10)]


class MusicalPosition(Model):
    unit: Literal["bbt"] = "bbt"
    bar: Annotated[int, Field(strict=True, ge=1, le=1000000)]
    beat: Annotated[int, Field(strict=True, ge=1, le=128)]
    tick: Annotated[int, Field(strict=True, ge=0, lt=1920)] = 0


class TickPosition(Model):
    unit: Literal["quarter_ticks"] = "quarter_ticks"
    ticks: QuarterTicks


Position = Annotated[
    SamplePosition | SecondPosition | MusicalPosition | TickPosition, Field(discriminator="unit")
]
