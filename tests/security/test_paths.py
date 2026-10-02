import json
from pathlib import Path

import pytest

from ardour_ultra_mcp.backends.mailbox import atomic_json, read_bounded, slot_lock
from ardour_ultra_mcp.installers.install import install, lua_string, uninstall
from ardour_ultra_mcp.installers.platforms import config_directory, mailbox_directory
from ardour_ultra_mcp.models.base import DomainError
from ardour_ultra_mcp.security.paths import PathPolicy, private_directory


def test_scoped_paths_unicode_space_and_traversal(tmp_path):
    root = tmp_path / "Project 日本 語"
    root.mkdir()
    audio = root / "Bass été.wav"
    audio.write_bytes(b"not audio")
    policy = PathPolicy((root,), (root,))
    assert policy.audio(str(audio)) == audio
    for path in [
        "../a.wav",
        str(root / ".." / "x.wav"),
        str(tmp_path / "other.wav"),
        "https://example.com/audio.wav",
    ]:
        with pytest.raises(DomainError):
            policy.audio(path)
    with pytest.raises(DomainError):
        PathPolicy().audio(str(audio))
    target = policy.new_export_directory(str(root / "pass 1"), dry_run=True)
    assert not target.exists()
    assert policy.new_export_directory(str(target)).is_dir()
    with pytest.raises(DomainError):
        policy.new_export_directory(str(target))


@pytest.mark.skipif(
    __import__("os").name == "nt", reason="unprivileged Windows symlink policy varies"
)
def test_symlink_escape_and_private_mailbox(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "secret.wav"
    outside.write_bytes(b"")
    (allowed / "link.wav").symlink_to(outside)
    with pytest.raises(DomainError):
        PathPolicy((allowed,)).audio(str(allowed / "link.wav"))
    (tmp_path / "mailbox-link").symlink_to(allowed, target_is_directory=True)
    with pytest.raises(DomainError):
        private_directory(tmp_path / "mailbox-link")
    allowed.chmod(0o755)
    with pytest.raises(DomainError):
        private_directory(allowed)


def test_atomic_bounded_io_and_cross_client_lock(tmp_path):
    path = tmp_path / "message.json"
    atomic_json(path, {"unicode": "日本", "value": -4.25})
    assert json.loads(read_bounded(path))["value"] == -4.25
    with pytest.raises(DomainError):
        read_bounded(path, 2)
    with slot_lock(tmp_path / "lock"), pytest.raises(DomainError), slot_lock(tmp_path / "lock"):
        pass
    with slot_lock(tmp_path / "lock"):
        pass
    with pytest.raises((ValueError, DomainError)):
        atomic_json(path, {"value": float("nan")})


def test_install_backup_repeat_and_uninstall_modified_guard(tmp_path):
    root, config = tmp_path / "private", tmp_path / "Ardour config"
    first = install(root, config, export_roots=(tmp_path,))
    script = Path(first["script"])
    token = json.loads((root / "bridge-config.json").read_text())["token"]
    second = install(root, config, export_roots=(tmp_path,))
    assert len(second["backups"]) == 2
    assert json.loads((root / "bridge-config.json").read_text())["token"] == token
    assert "@MAILBOX_LUA@" not in script.read_text()
    script.write_text(script.read_text() + "\n-- modified")
    with pytest.raises(DomainError):
        uninstall(root)
    install(root, config)
    assert uninstall(root)["removed_script"] == str(script) and not script.exists()


@pytest.mark.parametrize(
    "system,ending",
    [
        ("Linux", "/.config/ardour9"),
        ("Darwin", "/Library/Preferences/Ardour9"),
        ("Windows", "/AppData/Local/Ardour9"),
    ],
)
def test_platform_config_paths(system, ending):
    home = Path("/Users/Unicode Space")
    assert (
        str(config_directory(system=system, home=home, env={})).replace("\\", "/").endswith(ending)
    )
    assert "ardour-ultra-mcp" in str(mailbox_directory(system=system, home=home, env={}))


def test_xdg_windows_overrides_and_lua_injection():
    assert (
        str(
            config_directory(
                system="Windows", home=Path("/x"), env={"LOCALAPPDATA": "/private/AppData"}
            )
        ).replace("\\", "/")
        == "/private/AppData/Ardour9"
    )
    assert config_directory(system="Linux", env={"XDG_CONFIG_HOME": "/special"}) == Path(
        "/special/ardour9"
    )
    encoded = lua_string('C:\\Music\\"; os.execute("danger") -- 日本')
    assert "os.execute" not in encoded and "日本" not in encoded
