import asyncio
import json
import struct
import time

import pytest

from ardour_ultra_mcp.backends.mailbox import MailboxBackend, atomic_json
from ardour_ultra_mcp.backends.osc import OSCBackend, decode, encode
from ardour_ultra_mcp.installers.install import install
from ardour_ultra_mcp.models.base import DomainError, ErrorCode, Options


@pytest.fixture
def mailbox(tmp_path):
    root = tmp_path / "private"
    install(root, tmp_path / "config")
    atomic_json(
        root / "heartbeat.json",
        {
            "protocol": 1,
            "epoch": "test",
            "time": time.time(),
            "commands": ["ping", "set_track_gain"],
        },
    )
    return MailboxBackend(root, timeout=0.08)


async def test_mailbox_correlated_response_and_bounds(mailbox):
    async def worker():
        path = mailbox.directory / "request.json"
        while not path.exists():
            await asyncio.sleep(0.001)
        request = json.loads(path.read_text())
        path.unlink()
        atomic_json(
            mailbox.directory / "response.json",
            {
                "protocol": 1,
                "epoch": "test",
                "id": request["id"],
                "result": {"success": True, "data": {"acknowledged": True}},
            },
        )

    task = asyncio.create_task(worker())
    result = await mailbox.execute("ping", {}, Options())
    await task
    assert result.success and result.data["acknowledged"]
    assert not (mailbox.directory / "response.json").exists()


async def test_timeout_does_not_allow_blind_retry(mailbox):
    with pytest.raises(DomainError) as error:
        await mailbox.execute("set_track_gain", {"track_id": "123", "gain_db": -1}, Options())
    assert error.value.detail.code == ErrorCode.OUTCOME_UNCERTAIN
    assert (mailbox.directory / "request.json").exists()
    with pytest.raises(DomainError) as again:
        await mailbox.execute("ping", {}, Options())
    assert again.value.detail.code == ErrorCode.OUTCOME_UNCERTAIN


async def test_bridge_missing_capability_is_not_published(mailbox):
    with pytest.raises(DomainError) as error:
        await mailbox.execute("create_group", {"name": "Unavailable"}, Options())
    assert error.value.detail.code == ErrorCode.BACKEND_UNSUPPORTED
    assert not (mailbox.directory / "request.json").exists()


async def test_read_timeout_and_stale_heartbeat(mailbox):
    with pytest.raises(DomainError) as error:
        await mailbox.execute("ping", {}, Options())
    assert error.value.detail.code == ErrorCode.IPC_TIMEOUT
    atomic_json(mailbox.directory / "heartbeat.json", {"protocol": 1, "epoch": "test", "time": 0})
    with pytest.raises(DomainError) as stale:
        mailbox.heartbeat()
    assert stale.value.detail.code == ErrorCode.BRIDGE_NOT_RUNNING


async def test_wrong_reply_is_not_accepted(mailbox):
    async def worker():
        while not (mailbox.directory / "request.json").exists():
            await asyncio.sleep(0.001)
        atomic_json(
            mailbox.directory / "response.json",
            {"protocol": 1, "epoch": "test", "id": "wrong", "result": {"success": True}},
        )

    task = asyncio.create_task(worker())
    with pytest.raises(DomainError) as error:
        await mailbox.execute("ping", {}, Options())
    await task
    assert error.value.detail.code == ErrorCode.PROTOCOL_ERROR


@pytest.mark.parametrize("arguments", [(), (1,), (1, -4.25, "日本"), ("a b",), (2147483647,)])
def test_osc_wire_roundtrip(arguments):
    path, decoded = decode(encode("/strip/gain", arguments))
    assert path == "/strip/gain" and decoded == list(arguments)


@pytest.mark.parametrize(
    "data", [b"", b"xxxx", b"/a\0x,\0\0\0", b"/a\0\0,i\0\0", b"#bundle\0" + b"\0" * 8]
)
def test_osc_malformed_packet(data):
    with pytest.raises((ValueError, struct.error)):
        decode(data)


async def test_loopback_udp_query_and_truthful_mutation():
    class ArdourEcho(asyncio.DatagramProtocol):
        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            path, _ = decode(data)
            if path == "/transport_frame":
                self.transport.sendto(encode(path, (48000,)), addr)
            if path == "/transport_speed":
                self.transport.sendto(encode(path, (1.0,)), addr)

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(ArdourEcho, local_addr=("127.0.0.1", 0))
    backend = OSCBackend(port=transport.get_extra_info("sockname")[1], timeout=0.05)
    try:
        result = await backend.execute("get_transport", {}, Options())
        assert (
            result.data["samples"] == 48000
            and result.data["reply_received"]
            and not result.data["confirmed"]
        )
        changed = await backend.execute("play", {}, Options())
        assert changed.success and changed.data["confirmed"] is False and changed.warnings
        with pytest.raises(DomainError):
            await backend.execute("play", {}, Options(expected_revision="bad"))
        with pytest.raises(DomainError):
            await backend.execute(
                "locate", {"position": {"unit": "samples", "samples": 2147483648}}, Options()
            )
        with pytest.raises(DomainError):
            await backend.execute("create_midi_region", {}, Options())
    finally:
        await backend.close()
        transport.close()


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.1", "8.8.8.8"])
def test_nonlocal_osc_forbidden(host):
    with pytest.raises(DomainError):
        OSCBackend(host)
