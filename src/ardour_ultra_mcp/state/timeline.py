"""Deterministic piecewise constant timeline for the simulator (not an Ardour replacement)."""

from dataclasses import dataclass, field
from typing import Any

from ..models.base import DomainError, ErrorCode


@dataclass
class Timeline:
    sample_rate: int = 48000
    tempos: list[tuple[int, float]] = field(default_factory=lambda: [(0, 120.0)])
    meters: list[tuple[int, int, int]] = field(default_factory=lambda: [(0, 4, 4)])

    def ticks_to_samples(self, ticks: int) -> int:
        seconds = 0.0
        for index, (start, bpm) in enumerate(self.tempos):
            if ticks <= start:
                break
            end = self.tempos[index + 1][0] if index + 1 < len(self.tempos) else ticks
            seconds += (min(end, ticks) - start) / 1920 * 60 / bpm
        return round(seconds * self.sample_rate)

    def samples_to_ticks(self, samples: int) -> int:
        remaining = samples / self.sample_rate
        for index, (start, bpm) in enumerate(self.tempos):
            if index + 1 == len(self.tempos):
                return start + round(remaining * bpm / 60 * 1920)
            end = self.tempos[index + 1][0]
            duration = (end - start) / 1920 * 60 / bpm
            if remaining <= duration:
                return start + round(remaining * bpm / 60 * 1920)
            remaining -= duration
        raise AssertionError("initial tempo missing")

    def bbt_to_ticks(self, bar: int, beat: int, tick: int) -> int:
        current_bar = 1
        for index, (start, numerator, denominator) in enumerate(self.meters):
            beat_ticks = 1920 * 4 // denominator
            if tick >= beat_ticks:
                raise DomainError(
                    ErrorCode.INVALID_TIME_POSITION, "Tick exceeds current meter beat duration."
                )
            bar_ticks = numerator * beat_ticks
            next_start = self.meters[index + 1][0] if index + 1 < len(self.meters) else None
            next_bar = (
                current_bar + (next_start - start) // bar_ticks if next_start is not None else None
            )
            if next_bar is None or bar < next_bar:
                if beat > numerator:
                    raise DomainError(
                        ErrorCode.INVALID_TIME_POSITION, "Beat exceeds time signature."
                    )
                return start + (bar - current_bar) * bar_ticks + (beat - 1) * beat_ticks + tick
            current_bar = next_bar
        raise AssertionError("initial meter missing")

    def ticks_to_bbt(self, ticks: int) -> dict[str, int]:
        current_bar = 1
        for index, (start, numerator, denominator) in enumerate(self.meters):
            beat_ticks = 1920 * 4 // denominator
            bar_ticks = numerator * beat_ticks
            next_start = self.meters[index + 1][0] if index + 1 < len(self.meters) else None
            if next_start is None or ticks < next_start:
                bars, residual = divmod(ticks - start, bar_ticks)
                beat, tick = divmod(residual, beat_ticks)
                return {"bar": current_bar + bars, "beat": beat + 1, "tick": tick}
            current_bar += (next_start - start) // bar_ticks
        raise AssertionError("initial meter missing")

    def position(self, value: dict[str, Any]) -> int:
        unit = value["unit"]
        if unit == "samples":
            return int(value["samples"])
        if unit == "seconds":
            return int(round(value["seconds"] * self.sample_rate))
        if unit == "quarter_ticks":
            return self.ticks_to_samples(value["ticks"])
        return self.ticks_to_samples(self.bbt_to_ticks(value["bar"], value["beat"], value["tick"]))

    def convert(self, value: dict[str, Any]) -> dict[str, Any]:
        samples = self.position(value)
        ticks = self.samples_to_ticks(samples)
        return {
            "samples": samples,
            "seconds": samples / self.sample_rate,
            "quarter_ticks": ticks,
            "bbt": self.ticks_to_bbt(ticks),
            "ticks_per_quarter": 1920,
        }

    def set_tempo(self, sample: int, bpm: float) -> None:
        ticks = self.samples_to_ticks(sample)
        self.tempos = sorted([(t, b) for t, b in self.tempos if t != ticks] + [(ticks, bpm)])

    def set_meter(self, sample: int, numerator: int, denominator: int) -> None:
        ticks = self.samples_to_ticks(sample)
        bbt = self.ticks_to_bbt(ticks)
        if bbt["beat"] != 1 or bbt["tick"] != 0:
            raise DomainError(
                ErrorCode.INVALID_TIME_POSITION,
                "Simulator meter changes must be at a bar boundary.",
            )
        if any(t > ticks for t, _, _ in self.meters):
            raise DomainError(
                ErrorCode.OPERATION_NOT_SUPPORTED,
                "Simulator cannot rewrite meter before existing changes.",
            )
        self.meters = sorted(
            [(t, n, d) for t, n, d in self.meters if t != ticks] + [(ticks, numerator, denominator)]
        )
