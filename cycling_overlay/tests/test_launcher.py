from app import launcher


def test_launcher_checks_zeroconf_dependency():
    assert ("zeroconf", "zeroconf") in launcher.REQUIRED_PACKAGES


def test_launcher_ignores_valid_cache_when_dependency_is_missing(monkeypatch):
    calls = []

    monkeypatch.setattr(launcher, "is_cache_valid", lambda: True)
    monkeypatch.setattr(launcher, "check_dependencies", lambda: ["zeroconf"] if not calls else [])
    monkeypatch.setattr(launcher, "write_cache", lambda: calls.append("cache"))

    class Result:
        returncode = 0

    monkeypatch.setattr(launcher, "install_deps", lambda gui=False: calls.append("install") or Result())

    assert launcher.ensure_dependencies(gui=False) is True
    assert calls == ["install", "cache"]
