import ast
from pathlib import Path


def test_migration_028_has_upgrade_and_non_destructive_comment():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/028_financial_foundation.py"
    source = path.read_text()
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "upgrade" in names
    assert "downgrade" in names
    assert "legal_entities" in source
    assert "Destructive" in source
    assert "down_revision" in source


def test_migration_029_adds_verification_attempts():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/029_legal_entity_verification.py"
    source = path.read_text()
    assert "legal_entity_verification_attempts" in source
    assert "verification_source" in source
    assert "upgrade" in source
    assert "downgrade" in source
    assert 'down_revision' in source
    assert "028" in source
