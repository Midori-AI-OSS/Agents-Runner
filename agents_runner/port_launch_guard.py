from __future__ import annotations

import socket

from collections.abc import Sequence
from dataclasses import dataclass


_DEFAULT_BIND_HOST = "0.0.0.0"
_PORT_MIN = 1
_PORT_MAX = 65535


@dataclass(frozen=True)
class FixedHostPublish:
    """A publish spec with an explicit fixed host port."""

    index: int
    original_publish: str
    host_scope: str
    host_for_bind: str
    host_port: int
    container_segment: str
    protocol_suffix: str
    protocol: str


@dataclass(frozen=True)
class PortConflict:
    """A fixed host publish that is currently not bindable."""

    publish: FixedHostPublish


@dataclass(frozen=True)
class PortRemap:
    """Runtime-only remap from fixed host publish to random host publish."""

    index: int
    original_publish: str
    remapped_publish: str
    original_host_port: int
    host_for_bind: str
    protocol: str


def normalize_port_specs(port_specs: Sequence[str] | None) -> list[str]:
    """Return cleaned publish specs without empty entries."""
    cleaned: list[str] = []
    for raw in port_specs or []:
        spec = str(raw or "").strip()
        if spec:
            cleaned.append(spec)
    return cleaned


def extract_fixed_host_publishes(
    port_specs: Sequence[str] | None,
) -> list[FixedHostPublish]:
    """Extract publish specs that pin a fixed numeric host port."""
    fixed: list[FixedHostPublish] = []
    for index, raw in enumerate(normalize_port_specs(port_specs)):
        publish = _parse_fixed_host_publish(index=index, spec=raw)
        if publish is not None:
            fixed.append(publish)
    return fixed


def detect_port_conflicts(port_specs: Sequence[str] | None) -> list[PortConflict]:
    """Detect fixed host publishes that cannot currently bind."""
    conflicts: list[PortConflict] = []
    for publish in extract_fixed_host_publishes(port_specs):
        if not _can_bind_host_port(
            host=publish.host_for_bind,
            host_port=publish.host_port,
            protocol=publish.protocol,
        ):
            conflicts.append(PortConflict(publish=publish))
    return conflicts


def build_random_host_remaps(
    port_specs: Sequence[str] | None, conflicts: Sequence[PortConflict]
) -> list[PortRemap]:
    """Build runtime remaps for conflicting fixed host publishes."""
    normalized = normalize_port_specs(port_specs)
    remaps: list[PortRemap] = []
    for conflict in conflicts:
        publish = conflict.publish
        if publish.index < 0 or publish.index >= len(normalized):
            continue
        remapped_publish = _to_random_host_publish(publish)
        remaps.append(
            PortRemap(
                index=publish.index,
                original_publish=publish.original_publish,
                remapped_publish=remapped_publish,
                original_host_port=publish.host_port,
                host_for_bind=publish.host_for_bind,
                protocol=publish.protocol,
            )
        )
    return remaps


def apply_port_remaps(
    port_specs: Sequence[str] | None, remaps: Sequence[PortRemap]
) -> list[str]:
    """Return port specs with remaps applied by index."""
    resolved = normalize_port_specs(port_specs)
    for remap in remaps:
        if 0 <= remap.index < len(resolved):
            resolved[remap.index] = remap.remapped_publish
    return resolved


def _parse_fixed_host_publish(*, index: int, spec: str) -> FixedHostPublish | None:
    raw = str(spec or "").strip()
    if not raw:
        return None

    publish_core, protocol_suffix, protocol = _split_protocol_suffix(raw)

    if ":" not in publish_core:
        # Only container port is provided; Docker picks random host port.
        return None

    prefix, container_segment = publish_core.rsplit(":", 1)
    container_segment = container_segment.strip()
    if not container_segment:
        return None

    if ":" in prefix:
        host_scope, host_port_token = prefix.rsplit(":", 1)
    else:
        host_scope, host_port_token = "", prefix

    host_scope = str(host_scope or "").strip()
    host_port_token = str(host_port_token or "").strip()
    if not host_port_token.isdigit():
        return None

    host_port = int(host_port_token)
    if host_port < _PORT_MIN or host_port > _PORT_MAX:
        return None

    host_for_bind = _normalize_host_scope_for_bind(host_scope)

    return FixedHostPublish(
        index=index,
        original_publish=raw,
        host_scope=host_scope,
        host_for_bind=host_for_bind,
        host_port=host_port,
        container_segment=container_segment,
        protocol_suffix=protocol_suffix,
        protocol=protocol,
    )


def _split_protocol_suffix(spec: str) -> tuple[str, str, str]:
    if "/" not in spec:
        return spec, "", "tcp"
    core, raw_protocol = spec.rsplit("/", 1)
    protocol_token = str(raw_protocol or "").strip()
    if not protocol_token:
        return core, "", "tcp"
    return core, f"/{protocol_token}", protocol_token.lower()


def _normalize_host_scope_for_bind(host_scope: str) -> str:
    scoped = str(host_scope or "").strip()
    if not scoped:
        return _DEFAULT_BIND_HOST
    if scoped.startswith("[") and scoped.endswith("]"):
        scoped = scoped[1:-1].strip()
    return scoped or _DEFAULT_BIND_HOST


def _socket_params_for_protocol(protocol: str) -> tuple[int, int]:
    proto = str(protocol or "").strip().lower()
    if proto == "udp":
        return socket.SOCK_DGRAM, socket.IPPROTO_UDP
    return socket.SOCK_STREAM, socket.IPPROTO_TCP


def _can_bind_host_port(*, host: str, host_port: int, protocol: str) -> bool:
    sock_type, proto_number = _socket_params_for_protocol(protocol)
    try:
        infos = socket.getaddrinfo(
            host,
            int(host_port),
            socket.AF_UNSPEC,
            sock_type,
            proto_number,
            socket.AI_PASSIVE,
        )
    except OSError:
        return False

    for family, resolved_type, resolved_proto, _, sockaddr in infos:
        try:
            with socket.socket(family, resolved_type, resolved_proto) as probe:
                if family == socket.AF_INET6:
                    try:
                        probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    except OSError:
                        pass
                probe.bind(sockaddr)
                return True
        except OSError:
            continue
    return False


def _to_random_host_publish(publish: FixedHostPublish) -> str:
    if publish.host_scope:
        return (
            f"{publish.host_scope}::{publish.container_segment}"
            f"{publish.protocol_suffix}"
        )
    return f"{publish.container_segment}{publish.protocol_suffix}"
