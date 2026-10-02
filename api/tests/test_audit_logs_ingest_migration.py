import ast
from pathlib import Path


def test_migration_034_replaces_audit_logs_with_ingest_schema():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/034_audit_logs_ingest_schema.py"
    source = path.read_text()
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert "upgrade" in names
    assert "downgrade" in names
    assert 'revision: str = "034"' in source
    assert 'down_revision: Union[str, None] = "033"' in source
    assert 'op.rename_table("audit_logs", "audit_logs_legacy")' in source
    assert 'op.create_table(\n        "audit_logs"' in source or 'op.create_table(\n        "audit_logs",' in source
    assert "event_id" in source
    assert "uq_audit_logs_event_id" in source
    assert "changed_fields" in source
    assert "before_data" in source
    assert "after_data" in source
    assert "audit_logs_legacy" in source
