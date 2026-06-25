"""US3 integration tests — image resolution + status lifecycle, with Docker mocked/absent."""
import pytest


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    from storage import db, seed
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    db._engine = None
    seed.seed_catalog()
    yield
    db._engine = None


def test_resolve_image_from_seed(seeded):
    from storage.integration import resolve_image
    assert resolve_image("flaml") == "automlbenchmark/flaml:1.2.4-v2.1.3"


def test_resolve_image_via_hub_when_not_seeded(seeded, monkeypatch):
    """A framework not in the seed falls back to the Docker Hub tags API."""
    from storage import integration
    monkeypatch.setattr(integration, "_newest_tag", lambda n: "9.9-vZ")
    assert integration.resolve_image("brandnewml") == "automlbenchmark/brandnewml:9.9-vZ"


def test_pinned_available_resolves_offline(seeded, monkeypatch):
    """A pinned `available` framework resolves without any Docker Hub call (reproducible/offline)."""
    from storage import integration

    def _boom(name):
        raise AssertionError("Hub API must not be called for a pinned framework")
    monkeypatch.setattr(integration, "_newest_tag", _boom)
    assert integration.resolve_image("autosklearn") == "automlbenchmark/autosklearn:0.15.0-v2.1.6"


def test_integrate_docker_absent_fails_gracefully(seeded, monkeypatch):
    from storage import integration
    monkeypatch.setattr(integration, "_docker_available", lambda: False)
    assert integration.integrate("autosklearn") == "failed"
    s = integration.integration_status("autosklearn")
    assert s["status"] == "failed" and "Docker" in s["last_error"]


def test_integrate_starts_worker_sets_integrating(seeded, monkeypatch):
    from storage import integration
    monkeypatch.setattr(integration, "_docker_available", lambda: True)
    monkeypatch.setattr(integration.subprocess, "Popen", lambda *a, **k: None)  # don't actually spawn
    assert integration.integrate("tpot") == "integrating"
    assert integration.integration_status("tpot")["status"] == "integrating"


def test_run_pull_success_marks_integrated(seeded, monkeypatch):
    from storage import integration
    monkeypatch.setattr(integration, "_docker_available", lambda: True)

    class _R:
        returncode = 0
        stderr = ""
    monkeypatch.setattr(integration.subprocess, "run", lambda *a, **k: _R())

    assert integration._run_pull("gama") == 0       # gama is pinned in the seed
    s = integration.integration_status("gama")
    assert s["status"] == "integrated" and s["image"] == "automlbenchmark/gama:23.0.0-v2.1.3"


def test_run_pull_failure_records_error(seeded, monkeypatch):
    from storage import integration
    monkeypatch.setattr(integration, "_docker_available", lambda: True)
    monkeypatch.setattr(integration, "_newest_tag", lambda n: "1.0-vX")

    class _R:
        returncode = 1
        stderr = "manifest unknown: amd64 only"
    monkeypatch.setattr(integration.subprocess, "run", lambda *a, **k: _R())

    assert integration._run_pull("lightautoml") == 1
    s = integration.integration_status("lightautoml")
    assert s["status"] == "failed" and "manifest" in s["last_error"]
