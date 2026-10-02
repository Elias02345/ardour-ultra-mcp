"""Protocol-independent validation, policy, dispatch and structured diagnostics."""

from __future__ import annotations

import asyncio
import importlib.metadata
import importlib.util
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import JsonValue, ValidationError

from .. import __version__
from ..analysis.audio import analyze, compare
from ..backends.base import Backend
from ..installers.platforms import config_directory, detect_versions, find_ardour, mailbox_directory
from ..models.base import DomainError, ErrorCode, Options, Result
from ..security.paths import PathPolicy
from .catalog import CATALOG, COMPENSABLE, UNSUPPORTED
from .workflows import ensure_bus, render_and_analyze

LOG = logging.getLogger(__name__)


class ControlService:
    def __init__(self, backend: Backend, policy: PathPolicy | None = None) -> None:
        self.backend, self.policy = backend, policy or PathPolicy()
        self._analysis_lock = asyncio.Lock()

    async def call(self, command: str, arguments: dict[str, Any] | Options) -> Result:
        started = time.monotonic()
        try:
            spec = CATALOG.get(command)
            if spec is None:
                raise DomainError(ErrorCode.OPERATION_NOT_SUPPORTED, "Command is not allowlisted.")
            request = spec.request.model_validate(
                arguments.model_dump() if isinstance(arguments, Options) else arguments
            )
            options = Options.model_validate({k: getattr(request, k) for k in Options.model_fields})
            args = request.model_dump(mode="json", exclude=set(Options.model_fields))
            if spec.destructive and not options.confirm_delete and not options.dry_run:
                raise DomainError(
                    ErrorCode.VALIDATION_ERROR,
                    "Explicit confirm_delete is required.",
                    "Use dry_run to inspect affected objects, then set confirm_delete=true.",
                )
            if command == "execute_batch":
                for operation in args["operations"]:
                    if operation["command"] not in COMPENSABLE:
                        raise DomainError(
                            ErrorCode.OPERATION_NOT_SUPPORTED,
                            "Batch includes a non-compensable operation.",
                        )
                    parsed = CATALOG[operation["command"]].request.model_validate(
                        operation["arguments"]
                    )
                    if (
                        parsed.expected_revision is not None
                        or parsed.dry_run
                        or parsed.confirm_delete
                    ):
                        raise DomainError(
                            ErrorCode.VALIDATION_ERROR,
                            "Batch options belong on the outer request only.",
                        )
                    operation["arguments"] = parsed.model_dump(
                        mode="json", exclude=set(Options.model_fields)
                    )
            if command == "get_server_info":
                return Result(
                    data={
                        "name": "ardour-ultra-mcp",
                        "version": __version__,
                        "mcp_sdk": importlib.metadata.version("mcp"),
                        "python": platform.python_version(),
                        "platform": platform.system(),
                        "transport": "stdio",
                        "backend": self.backend.name,
                        "specification": "2026-07-28; official SDK negotiates prior revisions",
                    }
                )
            if command == "get_capabilities":
                caps = await self.backend.capabilities()
                return Result(
                    data={
                        **caps,
                        "local_commands": [s.name for s in CATALOG.values() if s.local],
                        "unsupported": UNSUPPORTED,
                        "tool_count": len(CATALOG),
                        "observed_at": time.time(),
                    }
                )
            if command == "doctor":
                return await self.doctor()
            if command == "ensure_bus":
                return await ensure_bus(self.call, args, options)
            if command == "render_and_analyze":
                return await render_and_analyze(self.call, args, options)
            if command in {"analyze_audio_file", "compare_audio_files"}:
                paths = (
                    [self.policy.audio(args["path"])]
                    if command == "analyze_audio_file"
                    else [self.policy.audio(args["first"]), self.policy.audio(args["second"])]
                )
                if options.dry_run:
                    return Result(
                        data={
                            "valid": True,
                            "files": [str(p) for p in paths],
                            "max_seconds": args["max_seconds"],
                        }
                    )
                async with self._analysis_lock:
                    results = [
                        await asyncio.to_thread(analyze, p, args["max_seconds"]) for p in paths
                    ]
                data = results[0] if len(results) == 1 else compare(*results)
                return Result(data=data)
            export_path: Path | None = None
            if command == "render_range":
                # Capability and Ardour range preflight precede creation of output directory.
                caps = await self.backend.capabilities()
                supported = caps.get("commands", [])
                if not isinstance(supported, list) or command not in supported:
                    raise DomainError(ErrorCode.BACKEND_UNSUPPORTED, "Backend cannot export audio.")
                export_path = self.policy.new_export_directory(
                    args["output_directory"], dry_run=True
                )
                preflight = await self.backend.execute(
                    command,
                    args,
                    Options(dry_run=True, expected_revision=options.expected_revision),
                )
                if preflight.success:
                    preflight.warnings.append(
                        "Ardour export preset controls normalization/rate/encoding/dither; normalization may mask gain changes. Inspect the selected preset."
                    )
                if not preflight.success or options.dry_run:
                    return preflight
                export_path = self.policy.new_export_directory(args["output_directory"])
                args["output_directory"] = str(export_path)
            result = await self.backend.execute(command, args, options)
            if export_path is not None and result.success:
                result.warnings.append(
                    "Ardour export preset controls normalization/rate/encoding/dither; normalization may mask gain changes. Inspect the selected preset."
                )
                export_files = [str(p) for p in sorted(export_path.iterdir()) if p.is_file()]
                result.data["files"] = [x for x in export_files]
                if importlib.util.find_spec("soundfile") is not None:
                    import soundfile as sf

                    metadata: list[JsonValue] = []
                    for filename in export_files:
                        if not isinstance(filename, str):
                            continue
                        try:
                            info = await asyncio.to_thread(sf.info, filename)
                        except (RuntimeError, OSError):
                            result.warnings.append(
                                "Export exists but decoder could not read its metadata; inspect file format."
                            )
                            continue
                        metadata.append(
                            {
                                "path": filename,
                                "sample_rate_hz": info.samplerate,
                                "channels": info.channels,
                                "frames": info.frames,
                                "duration_seconds": info.duration,
                                "format": info.format,
                                "subtype": info.subtype,
                            }
                        )
                        if (
                            result.data.get("session_sample_rate_hz") is not None
                            and result.data.get("session_sample_rate_hz") != info.samplerate
                        ):
                            result.warnings.append(
                                "Export preset sample rate differs from session; see file_metadata."
                            )
                    result.data["file_metadata"] = metadata
                else:
                    result.warnings.append(
                        "Install [analysis] for decoded export metadata; format/rate come from Ardour's preset."
                    )
                if not result.data["files"]:
                    raise DomainError(
                        ErrorCode.BACKEND_ERROR,
                        "Ardour reported export success but produced no output files.",
                        "Inspect Ardour export configuration and the new output directory.",
                    )
            LOG.info(
                "operation",
                extra={
                    "command": command,
                    "success": result.success,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                },
            )
            return result
        except ValidationError as exc:
            # Never include raw input; it can contain file contents or sensitive labels.
            return Result(
                success=False,
                error=DomainError(
                    ErrorCode.VALIDATION_ERROR,
                    "Request schema validation failed.",
                    details=[
                        {"location": [str(v) for v in x["loc"]], "type": x["type"]}
                        for x in exc.errors(include_input=False)
                    ],
                ).detail,
            )
        except DomainError as exc:
            return Result(success=False, error=exc.detail)
        except (OSError, ValueError) as exc:
            LOG.warning(
                "local_operation_failed",
                extra={"command": command, "error_type": type(exc).__name__},
            )
            return Result(
                success=False,
                error=DomainError(
                    ErrorCode.BACKEND_ERROR,
                    "Local backend operation failed.",
                    "Run doctor and inspect stderr diagnostics.",
                ).detail,
            )
        except Exception:
            LOG.exception("unexpected_operation_failure", extra={"command": command})
            return Result(
                success=False,
                error=DomainError(
                    ErrorCode.OUTCOME_UNCERTAIN,
                    "Unexpected backend failure; mutation outcome may be uncertain.",
                    "Inspect affected objects before retrying.",
                ).detail,
            )

    async def doctor(self) -> Result:
        versions = await asyncio.to_thread(detect_versions)
        checks: dict[str, JsonValue] = {
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "package": __version__,
            "ardour_candidates": [str(p) for p in find_ardour()],
            "ardour_versions": [dict(v) for v in versions],
            "mcp_sdk": importlib.metadata.version("mcp"),
            "default_ardour_config": str(config_directory()),
            "default_mailbox": str(mailbox_directory()),
            "analysis_dependencies": {
                name: importlib.util.find_spec(name) is not None
                for name in ["numpy", "scipy", "soundfile", "pyloudnorm"]
            },
            "media_roots": [str(p) for p in self.policy.media_roots],
            "export_roots": [str(p) for p in self.policy.export_roots],
            "platform_daw_validation": "See docs/COMPATIBILITY.md; mocked tests do not prove DAW support",
        }
        try:
            checks["backend"] = await self.backend.capabilities()
            ping = await self.backend.execute("ping", {}, Options())
            checks["connectivity"] = ping.model_dump(mode="json")
        except DomainError as exc:
            checks["connectivity"] = {"success": False, "error": exc.detail.model_dump(mode="json")}
        return Result(data=checks)
