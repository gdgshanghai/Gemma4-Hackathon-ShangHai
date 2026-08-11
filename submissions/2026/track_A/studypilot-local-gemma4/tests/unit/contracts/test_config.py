from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import httpx
from dotenv import dotenv_values
from pydantic import ValidationError

from backend.config import load_settings
from backend.orchestration.lm_studio import LMStudioClient, ModelConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_settings_load_environment_and_resolve_repository_paths(
    tmp_path: Path,
) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={
            "V13_LM_STUDIO_BASE_URL": "http://127.0.0.1:9999/v1",
            "V13_LM_STUDIO_MODEL": "local-test-model",
            "V13_BACKEND_PORT": "9040",
            "V13_CHILD_PORT": "9041",
            "V13_PARENT_PORT": "9042",
            "V13_DB_PATH": "var/test.db",
            "V13_TIMEZONE": "Asia/Shanghai",
            "V13_DEFAULT_SLEEP_TIME": "22:00",
            "V13_MOCK_ENABLED": "true",
            "V13_DEMO_MODE": "true",
        },
    )

    assert settings.repository_root == tmp_path.resolve()
    assert settings.database_path == (tmp_path / "var" / "test.db").resolve()
    assert settings.backend_port == 9040
    assert settings.default_sleep_time.isoformat(timespec="minutes") == "22:00"
    assert settings.mock_enabled is True
    assert settings.demo_mode is True
    with pytest.raises(ValidationError, match="frozen"):
        settings.backend_port = 1


def test_default_settings_contain_no_secret_fields(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path, environ={})

    assert settings.database_path == (
        tmp_path / "data" / "local" / "studypilot_v13.db"
    ).resolve()
    assert not {
        name
        for name in type(settings).model_fields
        if any(secret in name.lower() for secret in ("secret", "token", "password", "key"))
    }


def test_env_example_has_required_local_defaults() -> None:
    values = dotenv_values(PROJECT_ROOT / ".env.example")

    assert values == {
        "V13_LM_STUDIO_BASE_URL": "http://127.0.0.1:1234/v1",
        "V13_LM_STUDIO_MODEL": "gemma-4-26b-a4b-it",
        "V13_BACKEND_PORT": "8040",
        "V13_CHILD_PORT": "8041",
        "V13_PARENT_PORT": "8042",
        "V13_DB_PATH": "data/local/studypilot_v13.db",
        "V13_TIMEZONE": "Asia/Shanghai",
        "V13_DEFAULT_SLEEP_TIME": "21:30",
        "V13_MOCK_ENABLED": "false",
        "V13_DEMO_MODE": "false",
    }


def test_pyproject_pins_runtime_and_tooling_contracts() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))

    assert pyproject["project"]["requires-python"] == ">=3.13"
    assert set(pyproject["project"]["dependencies"]) == {
        "fastapi==0.136.0",
        "uvicorn==0.44.0",
        "httpx==0.28.1",
        "pydantic==2.13.3",
        "python-dotenv==1.0.1",
        "tzdata==2025.3",
    }
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    assert "pytest==9.0.2" in dev_dependencies
    assert "ruff==0.15.11" in dev_dependencies
    assert any(item.startswith("hypothesis") for item in dev_dependencies)
    assert any(item.startswith("pytest-cov") for item in dev_dependencies)
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(item.startswith("real_lm:") for item in markers)
    assert any(item.startswith("e2e:") for item in markers)
    assert pyproject["tool"]["pytest"]["ini_options"]["addopts"] == (
        "-m 'not real_lm'"
    )
    assert pyproject["tool"]["ruff"]["target-version"] == "py313"


@pytest.mark.parametrize(
    "remote_url",
    ["http://example.com:1234/v1", "http://192.168.1.9:1234/v1"],
)
def test_production_client_rejects_non_loopback_host_before_transport(
    tmp_path: Path, remote_url: str
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    settings = load_settings(
        project_root=tmp_path,
        environ={"V13_LM_STUDIO_BASE_URL": remote_url},
    )

    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient.from_settings(settings, transport=httpx.MockTransport(handler))

    assert raised.value.code == "remote_model_host_forbidden"
    assert calls == 0


def test_production_client_rejects_mock_mode_before_transport(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    settings = load_settings(
        project_root=tmp_path,
        environ={"V13_MOCK_ENABLED": "true"},
    )

    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient.from_settings(settings, transport=httpx.MockTransport(handler))

    assert raised.value.code == "mock_model_forbidden"
    assert calls == 0


@pytest.mark.parametrize(
    "local_url",
    [
        "http://127.0.0.1:1234/v1",
        "http://127.77.2.1:1234/v1",
        "http://localhost:1234/v1",
        "http://[::1]:1234/v1",
    ],
)
def test_production_client_accepts_loopback_hosts(
    tmp_path: Path, local_url: str
) -> None:
    settings = load_settings(
        project_root=tmp_path,
        environ={"V13_LM_STUDIO_BASE_URL": local_url},
    )

    client = LMStudioClient.from_settings(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )

    assert client.model_id == "gemma-4-26b-a4b-it"
