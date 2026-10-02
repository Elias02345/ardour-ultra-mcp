"""Minimal strict OSC codec and loopback-only UDP transport; no implicit strip identities."""

from __future__ import annotations

import asyncio
import ipaddress
import math
import struct
import time
from typing import Any

from pydantic import JsonValue

from ..models.base import DomainError, ErrorCode, Options, Result


def _string(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\x00"
    if b"\x00" in encoded[:-1]:
        raise ValueError("embedded NUL")
    return encoded + b"\x00" * (-len(encoded) % 4)


def encode(address: str, arguments: tuple[int | float | str, ...] = ()) -> bytes:
    if not address.startswith("/") or len(address) > 500:
        raise ValueError("invalid OSC address")
    tags, values = ",", []
    for value in arguments:
        if isinstance(value, int):
            tags += "i"
            values.append(struct.pack(">i", value))
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("non-finite OSC float")
            tags += "f"
            values.append(struct.pack(">f", value))
        else:
            tags += "s"
            values.append(_string(value))
    return _string(address) + _string(tags) + b"".join(values)


def decode(data: bytes) -> tuple[str, list[Any]]:
    if len(data) > 65507 or len(data) % 4:
        raise ValueError("invalid OSC length")
    index = 0

    def string() -> str:
        nonlocal index
        end = data.index(b"\0", index)
        value = data[index:end].decode("utf-8")
        padded = (end + 4) & ~3
        if padded > len(data) or any(data[end:padded]):
            raise ValueError("invalid OSC padding")
        index = padded
        return value

    address, tags = string(), string()
    if not address.startswith("/") or not tags.startswith(","):
        raise ValueError("OSC address/type tags invalid")
    values = []
    for tag in tags[1:]:
        if tag in "ifhd":
            size = 8 if tag in "hd" else 4
            value = struct.unpack_from(">" + tag, data, index)[0]
            index += size
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("non-finite feedback")
            values.append(value)
        elif tag == "s":
            values.append(string())
        elif tag in "TF":
            values.append(tag == "T")
        else:
            raise ValueError("unsupported OSC tag")
    if index != len(data):
        raise ValueError("trailing OSC bytes")
    return address, values


class OSCBackend(asyncio.DatagramProtocol):
    name = "osc"
    commands = frozenset({"ping", "get_transport", "play", "stop", "locate"})

    def __init__(self, host: str = "127.0.0.1", port: int = 3819, timeout: float = 2) -> None:
        if not ipaddress.ip_address(host).is_loopback or not 1 <= port <= 65535:
            raise DomainError(
                ErrorCode.PERMISSION_DENIED, "OSC destination must be loopback and a valid port."
            )
        self.host, self.port, self.timeout = host, port, timeout
        self.transport: asyncio.DatagramTransport | None = None
        self.feedback: dict[str, tuple[list[Any], float]] = {}
        self.pending: dict[str, asyncio.Future[list[Any]]] = {}
        self._lock = asyncio.Lock()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr[0] != self.host:
            return
        try:
            path, values = decode(data)
        except (ValueError, UnicodeDecodeError, struct.error):
            return
        if path not in self.feedback and len(self.feedback) >= 256:
            oldest = min(self.feedback, key=lambda p: self.feedback[p][1])
            del self.feedback[oldest]
        self.feedback[path] = values, time.time()
        pending = self.pending.get(path)
        if pending and not pending.done():
            pending.set_result(values)

    async def open(self) -> None:
        if self.transport is None:
            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                lambda: self, local_addr=(self.host, 0)
            )
            self.transport = transport

    async def query(self, path: str) -> list[Any]:
        await self.open()
        if self.transport is None:
            raise DomainError(ErrorCode.ARDOUR_NOT_CONNECTED, "OSC transport unavailable.")
        future: asyncio.Future[list[Any]] = asyncio.get_running_loop().create_future()
        self.pending[path] = future
        try:
            self.transport.sendto(encode(path), (self.host, self.port))
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError as exc:
            raise DomainError(
                ErrorCode.OSC_TIMEOUT,
                "Ardour did not answer native OSC query.",
                "Enable OSC in Ardour Control Surfaces and check its port; a sent UDP packet alone is not connectivity.",
            ) from exc
        finally:
            self.pending.pop(path, None)

    async def execute(
        self, command: str, arguments: dict[str, JsonValue], options: Options
    ) -> Result:
        if command not in self.commands:
            raise DomainError(
                ErrorCode.BACKEND_UNSUPPORTED, "Deep control requires installed Lua bridge."
            )
        if options.expected_revision is not None:
            raise DomainError(
                ErrorCode.BACKEND_UNSUPPORTED, "OSC cannot enforce session revision preconditions."
            )
        async with self._lock:
            if command in {"ping", "get_transport"}:
                frame = await self.query("/transport_frame")
                speed = await self.query("/transport_speed")
                return Result(
                    data={
                        "samples": frame[0],
                        "speed": speed[0],
                        "observed_at": time.time(),
                        "backend": "osc",
                        "reply_received": True,
                        "connected": True,
                        "confirmed": False,
                        "state_verified": False,
                    },
                    warnings=[
                        "OSC replies are uncorrelated; late UDP replies cannot be distinguished. No stable object state.",
                        "Native 9.8 Dummy OSC readback diverged from Lua in integration; reported OSC values are experimental. Use Lua to verify transport.",
                    ],
                )
            path = {"play": "/transport_play", "stop": "/transport_stop", "locate": "/locate"}[
                command
            ]
            values: tuple[int | float | str, ...] = ()
            if command == "locate":
                position = arguments.get("position")
                if not isinstance(position, dict) or position.get("unit") != "samples":
                    raise DomainError(
                        ErrorCode.BACKEND_UNSUPPORTED,
                        "Native OSC locate accepts explicit samples only; Lua converts musical time.",
                    )
                sample = position.get("samples")
                if not isinstance(sample, int) or not 0 <= sample <= 2147483647:
                    raise DomainError(
                        ErrorCode.INVALID_TIME_POSITION,
                        "Native OSC locate uses signed 32-bit sample argument.",
                    )
                values = sample, 0
            if not options.dry_run:
                await self.open()
                if self.transport is None:
                    raise DomainError(ErrorCode.ARDOUR_NOT_CONNECTED, "OSC transport unavailable.")
                self.transport.sendto(encode(path, values), (self.host, self.port))
            return Result(
                data={
                    "submitted": not options.dry_run,
                    "confirmed": False,
                    "backend": "osc",
                    "valid": True,
                },
                warnings=[
                    "UDP mutation is unacknowledged. Query Ardour to inspect resulting state; do not automatically retry."
                ],
            )

    async def capabilities(self) -> dict[str, JsonValue]:
        return {
            "backend": "osc",
            "commands": [str(x) for x in sorted(self.commands)],
            "stable_object_ids": False,
            "mutation_acknowledgements": False,
            "experimental_commands": ["get_transport", "play", "stop", "locate"],
            "mutation_validation": "Submission only; native 9.8 Dummy locate probe did not move transport with either Python or liblo sender. Use Lua for deterministic transport.",
            "listener": "loopback",
            "ardour_listener_warning": "Ardour's own OSC listener may bind all interfaces; firewall it or use Lua only.",
        }

    async def close(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
