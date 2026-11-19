"""Explicit Language Guard environment identity and isolation (ADR-025).

Build channel, runtime environment, backend host, data directory, account
identity, and Cloud Sync status are independent facts. A Git branch or EXE
filename alone does not authorize production network writes.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

ENV_DEVELOPMENT = "development"
ENV_STAGING = "staging"
ENV_PRODUCTION = "production"

VALID_ENVIRONMENTS = frozenset({ENV_DEVELOPMENT, ENV_STAGING, ENV_PRODUCTION})

# Folder names under %APPDATA% / %LOCALAPPDATA% for frozen builds.
DATA_FOLDER = {
    ENV_DEVELOPMENT: "langstudyguard-dev",
    ENV_STAGING: "langstudyguard-staging",
    ENV_PRODUCTION: "langstudyguard",
}

EXE_BASENAME = {
    ENV_DEVELOPMENT: "langstudyguard-dev.exe",
    ENV_STAGING: "langstudyguard-staging.exe",
    ENV_PRODUCTION: "langstudyguard.exe",
}

STARTUP_LINK = {
    ENV_DEVELOPMENT: "langstudyguard-dev.lnk",
    ENV_STAGING: "langstudyguard-staging.lnk",
    ENV_PRODUCTION: "langstudyguard.lnk",
}

# Hosts that non-production builds must never send authenticated traffic to.
KNOWN_PRODUCTION_HOSTS = frozenset(
    {
        "langstudyguard.com",
        "www.langstudyguard.com",
        "api.langstudyguard.com",
        "account.langstudyguard.com",
    }
)

# Staging may only talk to localhost / private lab hosts unless explicitly trusted.
DEFAULT_STAGING_ALLOWED_HOSTS = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "::1",
    }
)

MANIFEST_NAME = "build_manifest.json"


class EnvironmentIdentityError(RuntimeError):
    """Unknown, incomplete, or conflicting environment identity."""


@dataclass(frozen=True)
class BuildManifest:
    channel: str
    version: str
    commit_sha: str
    built_at: str = ""


@dataclass(frozen=True)
class EnvironmentIdentity:
    """Resolved identity. Fields stay independent — do not collapse them."""

    build_channel: str
    runtime_environment: str
    version: str
    commit_sha: str
    data_folder: str
    install_folder: str
    exe_basename: str
    startup_link: str
    network_writes_allowed: bool
    identity_error: str = ""

    @property
    def is_production(self) -> bool:
        return self.runtime_environment == ENV_PRODUCTION

    @property
    def is_non_production(self) -> bool:
        return self.runtime_environment != ENV_PRODUCTION

    def display_title(self, app_name: str = "Language Guard") -> str:
        label = {
            ENV_PRODUCTION: "PRODUCTION",
            ENV_STAGING: "STAGING",
            ENV_DEVELOPMENT: "DEVELOPMENT",
        }.get(self.runtime_environment, "UNKNOWN")
        return f"{app_name} — {label}"

    def banner_text(self) -> str:
        if self.identity_error:
            return f"ENVIRONMENT ERROR — {self.identity_error}"
        if self.runtime_environment == ENV_PRODUCTION:
            return "PRODUCTION"
        if self.runtime_environment == ENV_STAGING:
            return "STAGING — test data only"
        return "DEVELOPMENT — local / synthetic data"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.dirname(here)
    if is_frozen():
        return getattr(sys, "_MEIPASS", base)
    return base


def _normalize_env(raw: str) -> str:
    value = (raw or "").strip().lower()
    aliases = {
        "dev": ENV_DEVELOPMENT,
        "develop": ENV_DEVELOPMENT,
        "local": ENV_DEVELOPMENT,
        "stage": ENV_STAGING,
        "prod": ENV_PRODUCTION,
    }
    return aliases.get(value, value)


def load_build_manifest(path: Optional[str] = None) -> Optional[BuildManifest]:
    """Load bundled or adjacent build_manifest.json. Missing is OK for source runs."""
    candidates = []
    if path:
        candidates.append(path)
    candidates.append(os.path.join(resource_dir(), MANIFEST_NAME))
    # Source tree: repo-root build_manifest.json (optional).
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(os.path.dirname(here), MANIFEST_NAME))
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        channel = _normalize_env(str(data.get("channel") or data.get("build_channel") or ""))
        version = str(data.get("version") or "").strip()
        sha = str(data.get("commit_sha") or data.get("git_sha") or "").strip()
        built_at = str(data.get("built_at") or "").strip()
        if channel in VALID_ENVIRONMENTS and version and sha:
            return BuildManifest(
                channel=channel,
                version=version,
                commit_sha=sha,
                built_at=built_at,
            )
    return None


def _runtime_from_environ() -> str:
    raw = (
        os.environ.get("LG_APP_ENVIRONMENT")
        or os.environ.get("APP_ENVIRONMENT")
        or os.environ.get("LANGUAGE_GUARD_ENV")
        or ""
    )
    return _normalize_env(raw)


def _trusted_staging_hosts() -> frozenset:
    raw = (os.environ.get("LG_TRUSTED_STAGING_HOSTS") or "").strip()
    if not raw:
        return DEFAULT_STAGING_ALLOWED_HOSTS
    hosts = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return frozenset(hosts | set(DEFAULT_STAGING_ALLOWED_HOSTS))


_MANIFEST_UNSET = object()


def resolve_identity(
    *,
    manifest: object = _MANIFEST_UNSET,
    runtime_override: Optional[str] = None,
    frozen: Optional[bool] = None,
) -> EnvironmentIdentity:
    """Resolve and validate environment identity. Fail closed on conflict.

    Pass ``manifest=None`` to simulate a frozen build with no manifest.
    Omit ``manifest`` to load ``build_manifest.json`` from disk when present.
    """
    frozen = is_frozen() if frozen is None else bool(frozen)
    if manifest is _MANIFEST_UNSET:
        manifest = load_build_manifest()
    runtime_env = _normalize_env(runtime_override) if runtime_override else _runtime_from_environ()

    error = ""
    if frozen:
        if manifest is None:
            # Frozen builds without a manifest are incomplete — fail closed.
            build_channel = ""
            error = "missing build manifest"
            version = ""
            commit_sha = "unknown"
        else:
            build_channel = manifest.channel
            version = manifest.version
            commit_sha = manifest.commit_sha
            if runtime_env and runtime_env != build_channel:
                error = (
                    f"runtime {runtime_env!r} conflicts with build channel "
                    f"{build_channel!r}"
                )
            runtime_env = build_channel
    else:
        # Source runs default to development; optional LG_APP_ENVIRONMENT.
        build_channel = manifest.channel if manifest else ENV_DEVELOPMENT
        version = (manifest.version if manifest else "") or _source_version_fallback()
        commit_sha = (manifest.commit_sha if manifest else "") or "source"
        if not runtime_env:
            runtime_env = ENV_DEVELOPMENT
        if runtime_env not in VALID_ENVIRONMENTS:
            error = f"unknown runtime environment {runtime_env!r}"
            runtime_env = ""
        elif build_channel in VALID_ENVIRONMENTS and runtime_env == ENV_PRODUCTION and build_channel != ENV_PRODUCTION:
            # Source tree must not silently claim production.
            error = "source tree cannot claim production without a production build channel"
        elif (
            build_channel in VALID_ENVIRONMENTS
            and runtime_env != build_channel
            and runtime_env == ENV_PRODUCTION
        ):
            error = "production runtime requires production build channel"

    if not error:
        if build_channel and build_channel not in VALID_ENVIRONMENTS:
            error = f"unknown build channel {build_channel!r}"
        if runtime_env and runtime_env not in VALID_ENVIRONMENTS:
            error = f"unknown runtime environment {runtime_env!r}"

    if error:
        # Prefer never touching production when identity is broken.
        if frozen and build_channel in (ENV_STAGING, ENV_DEVELOPMENT):
            folder_key = build_channel
        elif frozen:
            folder_key = ENV_STAGING
        else:
            folder_key = ENV_DEVELOPMENT
        display_runtime = runtime_env or "unknown"
    else:
        folder_key = runtime_env if runtime_env in VALID_ENVIRONMENTS else ENV_DEVELOPMENT
        display_runtime = folder_key

    folder = DATA_FOLDER[folder_key]
    writes_ok = (
        not bool(error)
        and display_runtime in VALID_ENVIRONMENTS
        and build_channel in VALID_ENVIRONMENTS
    )
    if frozen and manifest is None:
        writes_ok = False

    return EnvironmentIdentity(
        build_channel=build_channel or "unknown",
        runtime_environment=display_runtime,
        version=version or "unknown",
        commit_sha=commit_sha or "unknown",
        data_folder=folder,
        install_folder=folder,
        exe_basename=EXE_BASENAME.get(folder_key, EXE_BASENAME[ENV_STAGING]),
        startup_link=STARTUP_LINK.get(folder_key, STARTUP_LINK[ENV_STAGING]),
        network_writes_allowed=writes_ok,
        identity_error=error,
    )


def _source_version_fallback() -> str:
    try:
        import config as _config

        return str(getattr(_config, "APP_VERSION", "") or "unknown")
    except Exception:
        return "unknown"


_IDENTITY: Optional[EnvironmentIdentity] = None


def get_identity(*, refresh: bool = False) -> EnvironmentIdentity:
    global _IDENTITY
    if _IDENTITY is None or refresh:
        _IDENTITY = resolve_identity()
    return _IDENTITY


def reset_identity_cache() -> None:
    """Test helper — clear cached identity."""
    global _IDENTITY
    _IDENTITY = None


def backend_host(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else "http://" + raw)
    host = (parsed.hostname or "").strip().lower()
    return host


def is_known_production_host(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if host in KNOWN_PRODUCTION_HOSTS:
        return True
    # Treat any langstudyguard.com subdomain as production.
    return host.endswith(".langstudyguard.com")


def is_loopback_host(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    return host in {"127.0.0.1", "localhost", "::1"}


def validate_backend_for_identity(
    identity: EnvironmentIdentity,
    server_url: str,
) -> Optional[str]:
    """Return an error string if authenticated use of this URL is forbidden."""
    if identity.identity_error:
        return identity.identity_error
    host = backend_host(server_url)
    if not host:
        return "missing backend host"
    env = identity.runtime_environment
    if env == ENV_PRODUCTION:
        # Production may use production hosts or an explicitly configured URL;
        # channel/runtime already matched via resolve_identity.
        return None
    if is_known_production_host(host):
        return f"{env} build refused production host {host}"
    if env == ENV_STAGING:
        allowed = _trusted_staging_hosts()
        if host not in allowed and not is_loopback_host(host):
            return (
                f"staging backend host {host!r} is not trusted "
                "(set LG_TRUSTED_STAGING_HOSTS for remote staging)"
            )
    if env == ENV_DEVELOPMENT and not is_loopback_host(host) and is_known_production_host(host):
        return f"development build refused production host {host}"
    if env == ENV_DEVELOPMENT and not is_loopback_host(host):
        # Development defaults to localhost only.
        trusted = _trusted_staging_hosts()
        if host not in trusted:
            return f"development backend host {host!r} is not localhost/trusted"
    return None


def assert_network_writes_allowed(
    server_url: str,
    *,
    identity: Optional[EnvironmentIdentity] = None,
) -> None:
    """Fail closed before any authenticated account/sync network write."""
    identity = identity or get_identity()
    if not identity.network_writes_allowed:
        raise EnvironmentIdentityError(
            identity.identity_error or "network writes disabled: incomplete environment identity"
        )
    problem = validate_backend_for_identity(identity, server_url)
    if problem:
        raise EnvironmentIdentityError(problem)


def normalize_fs_path(path: str) -> str:
    """Windows-aware absolute path with optional realpath (fail soft on errors)."""
    raw = os.path.expandvars(os.path.expanduser((path or "").strip()))
    if not raw:
        return ""
    absolute = os.path.abspath(raw)
    try:
        return os.path.realpath(absolute)
    except OSError:
        return os.path.normcase(os.path.normpath(absolute))


def _normcase(path: str) -> str:
    return os.path.normcase(normalize_fs_path(path))


def production_data_dir(
    *,
    appdata: Optional[str] = None,
) -> str:
    root = appdata if appdata is not None else (os.environ.get("APPDATA") or os.path.expanduser("~"))
    return os.path.join(root, DATA_FOLDER[ENV_PRODUCTION])


def production_install_dir(
    *,
    localappdata: Optional[str] = None,
) -> str:
    root = (
        localappdata
        if localappdata is not None
        else (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~"))
    )
    return os.path.join(root, DATA_FOLDER[ENV_PRODUCTION])


def paths_overlap(a: str, b: str) -> bool:
    """True when either path equals or contains the other (Windows-normalized)."""
    left = _normcase(a).rstrip("\\/")
    right = _normcase(b).rstrip("\\/")
    if not left or not right:
        return False
    if left == right:
        return True
    sep = os.sep
    return left.startswith(right + sep) or right.startswith(left + sep)


def validate_data_root_for_identity(
    path: str,
    identity: Optional[EnvironmentIdentity] = None,
    *,
    appdata: Optional[str] = None,
    localappdata: Optional[str] = None,
) -> Optional[str]:
    """Return an error if a non-production build may not use this data root.

    Isolated synthetic directories (including pytest temp dirs) remain allowed.
    Production AppData / install trees are always rejected for non-production.
    """
    identity = identity or get_identity()
    if identity.runtime_environment == ENV_PRODUCTION and not identity.identity_error:
        return None
    candidate = normalize_fs_path(path)
    if not candidate:
        return "empty data directory"
    prod_data = production_data_dir(appdata=appdata)
    prod_install = production_install_dir(localappdata=localappdata)
    if paths_overlap(candidate, prod_data):
        return f"non-production data root overlaps production AppData: {prod_data}"
    if paths_overlap(candidate, prod_install):
        return f"non-production data root overlaps production install dir: {prod_install}"
    # Exact production folder name under AppData/LocalAppData even if env roots differ.
    base = os.path.basename(candidate.rstrip("\\/"))
    if os.path.normcase(base) == os.path.normcase(DATA_FOLDER[ENV_PRODUCTION]):
        parent = os.path.basename(os.path.dirname(candidate.rstrip("\\/")))
        # Roaming / Local are common Windows AppData leaf names.
        if os.path.normcase(parent) in {
            "roaming",
            "local",
            "application data",
        } or paths_overlap(candidate, prod_data) or paths_overlap(candidate, prod_install):
            return f"non-production build refused production folder name {base!r}"
    return None


def assert_data_root_allowed(
    path: str,
    *,
    identity: Optional[EnvironmentIdentity] = None,
    appdata: Optional[str] = None,
    localappdata: Optional[str] = None,
) -> str:
    """Validate and return the normalized data root. Fail closed on isolation errors."""
    identity = identity or get_identity()
    problem = validate_data_root_for_identity(
        path,
        identity,
        appdata=appdata,
        localappdata=localappdata,
    )
    if problem:
        raise EnvironmentIdentityError(problem)
    return normalize_fs_path(path)


class RedirectRejected(EnvironmentIdentityError):
    """HTTP redirect would leak credentials or reach a forbidden host."""


def assert_redirect_allowed(
    location: str,
    *,
    identity: Optional[EnvironmentIdentity] = None,
) -> None:
    """Fail closed when a redirect target is forbidden for this identity.

    Account/sync clients must not follow redirects; this validates the Location
    header so tests can prove production destinations are refused without contact.
    """
    identity = identity or get_identity()
    target = (location or "").strip()
    if not target:
        raise RedirectRejected("redirect missing Location")
    # Relative redirects stay on the original host — still refuse to follow with credentials.
    if "://" not in target:
        raise RedirectRejected("credentialed requests refuse to follow redirects")
    problem = validate_backend_for_identity(identity, target)
    if problem:
        raise RedirectRejected(problem)
    # Even trusted hosts: never auto-follow with Bearer/password payloads.
    raise RedirectRejected("credentialed requests refuse to follow redirects")


def open_without_redirects(request: "urllib.request.Request", timeout: float):
    """urlopen that never follows redirects (credentials stay on the first hop).

    ``build_opener`` always installs ``HTTPRedirectHandler`` by default, so we
    replace it with a handler that surfaces 3xx as ``HTTPError`` instead of
    re-issuing the request (which would forward Authorization / body).
    """
    import urllib.error
    import urllib.request

    class _NoFollowRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    opener = urllib.request.build_opener(_NoFollowRedirects)
    return opener.open(request, timeout=timeout)


def settings_environment_marker(identity: Optional[EnvironmentIdentity] = None) -> str:
    identity = identity or get_identity()
    return identity.runtime_environment


def settings_token_compatible(
    settings: dict,
    identity: Optional[EnvironmentIdentity] = None,
) -> bool:
    """Reject a stored session that belongs to a different environment folder/channel."""
    identity = identity or get_identity()
    if not isinstance(settings, dict):
        return False
    marker = str(settings.get("environment") or settings.get("app_environment") or "").strip().lower()
    if not marker:
        # Legacy production settings have no marker. Only production may adopt them,
        # and only when using the production data folder.
        return identity.runtime_environment == ENV_PRODUCTION and identity.data_folder == DATA_FOLDER[ENV_PRODUCTION]
    return marker == identity.runtime_environment


def cloud_sync_ui_state(
    *,
    signed_in: bool,
    engine_running: bool,
    engine_status: Optional[str] = None,
    engine_detail: str = "",
    caught_up: Optional[bool] = None,
    feature_flag_known: Optional[bool] = None,
) -> tuple[str, str]:
    """Return (label, detail) for Cloud Sync — never guess 'Synced'."""
    if not signed_in:
        return "Disabled", "Guest mode — account sync off"
    if feature_flag_known is False:
        return "Unavailable", "Server feature flag could not be verified"
    if not engine_running:
        return "Disabled", "Sync worker not running"
    status = (engine_status or "").strip().lower()
    if status in {"conflict"}:
        return "Conflict", engine_detail or "Action required"
    if status in {"offline"}:
        return "Offline", engine_detail or "Server unreachable"
    if status in {"pending"}:
        return "Pending", engine_detail or "Upload or download in progress"
    if status in {"synced", "ok", "caught_up"}:
        if caught_up is False:
            return "Pending", engine_detail or "Catch-up not confirmed"
        if caught_up is None and status != "synced":
            return "Unknown", engine_detail or "Catch-up not confirmed"
        return "Synced", engine_detail or "Caught up"
    if not status:
        return "Unknown", engine_detail or "No sync status yet"
    return status.title(), engine_detail or status


def environment_details(
    *,
    identity: Optional[EnvironmentIdentity] = None,
    backend_url: str = "",
    data_directory: str = "",
    account_label: str = "",
    cloud_sync_label: str = "",
    cloud_sync_detail: str = "",
) -> dict:
    """Non-sensitive About / Environment Details payload."""
    identity = identity or get_identity()
    host = backend_host(backend_url)
    return {
        "application_version": identity.version,
        "build_channel": identity.build_channel,
        "git_commit_sha": identity.commit_sha,
        "runtime_environment": identity.runtime_environment,
        "backend_host": host or "(none)",
        "data_directory": data_directory or "(unset)",
        "logged_in_account": account_label or "(guest)",
        "cloud_sync_status": cloud_sync_label or "Unknown",
        "cloud_sync_detail": cloud_sync_detail,
        "identity_error": identity.identity_error,
        "network_writes_allowed": identity.network_writes_allowed,
    }
