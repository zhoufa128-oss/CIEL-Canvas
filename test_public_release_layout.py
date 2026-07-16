from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_public_release_documents_and_license_are_present() -> None:
    required = {
        "README.md",
        "README_EN.md",
        "LICENSE",
        "SOURCE_AND_ATTRIBUTION.md",
        "THIRD_PARTY_NOTICES.md",
        "SECURITY.md",
        "RELEASE_NOTES.md",
    }
    assert all((ROOT / name).is_file() for name in required)


def test_env_example_contains_no_values() -> None:
    env_example = ROOT / "release_tools" / "templates" / "defaults" / "config" / ".env.example"
    for line in env_example.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            assert line.rstrip().endswith("=")


def test_release_archives_are_not_git_tracked() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.zip" in gitignore
    assert "*.rar" in gitignore
