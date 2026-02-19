import re
from pathlib import Path


VERSION_NUM_LIMIT = 32
REVISION_PATTERN = re.compile(r'^\s*revision\s*=\s*"([^"]+)"', re.MULTILINE)
DOWN_REVISION_PATTERN = re.compile(r'^\s*down_revision\s*=\s*(None|"([^"]+)")', re.MULTILINE)


def _migration_files() -> list[Path]:
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    return sorted(path for path in versions_dir.glob("*.py") if path.name != "__init__.py")


def test_migration_revision_lengths_fit_alembic_version_column():
    for migration_path in _migration_files():
        content = migration_path.read_text(encoding="utf-8")
        revision_match = REVISION_PATTERN.search(content)
        assert revision_match is not None, f"Missing revision in {migration_path.name}"

        revision = revision_match.group(1)
        assert len(revision) <= VERSION_NUM_LIMIT, (
            f"Revision '{revision}' in {migration_path.name} exceeds {VERSION_NUM_LIMIT} chars."
        )


def test_migration_down_revisions_exist():
    revisions_by_file = {}
    down_revisions = {}

    for migration_path in _migration_files():
        content = migration_path.read_text(encoding="utf-8")
        revision_match = REVISION_PATTERN.search(content)
        down_revision_match = DOWN_REVISION_PATTERN.search(content)

        assert revision_match is not None, f"Missing revision in {migration_path.name}"
        assert down_revision_match is not None, f"Missing down_revision in {migration_path.name}"

        revision = revision_match.group(1)
        down_revision = down_revision_match.group(2) if down_revision_match.group(1) != "None" else None

        revisions_by_file[migration_path.name] = revision
        down_revisions[migration_path.name] = down_revision

    all_revisions = set(revisions_by_file.values())
    for migration_name, down_revision in down_revisions.items():
        if down_revision is None:
            continue
        assert down_revision in all_revisions, (
            f"down_revision '{down_revision}' in {migration_name} does not match any migration revision."
        )
