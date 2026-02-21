"""add project industry category and align starter-plan default key

Revision ID: 20260221_02_project_industry
Revises: 20260221_01_starter_plan
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_02_project_industry"
down_revision = "20260221_01_starter_plan"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name, column_name):
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(inspector, table_name, index_name):
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_project") and not _column_exists(
        inspector,
        "internal_project",
        "industry_category",
    ):
        with op.batch_alter_table("internal_project", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "industry_category",
                    sa.String(length=80),
                    nullable=False,
                    server_default="general",
                )
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project") and _column_exists(inspector, "internal_project", "industry_category"):
        if not _index_exists(inspector, "internal_project", "ix_internal_project_industry_category"):
            op.create_index(
                "ix_internal_project_industry_category",
                "internal_project",
                ["industry_category"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_starter_plan"):
        has_general = bind.execute(
            sa.text(
                "SELECT 1 FROM internal_project_starter_plan WHERE name = :name LIMIT 1"
            ),
            {"name": "general"},
        ).scalar()
        has_default = bind.execute(
            sa.text(
                "SELECT 1 FROM internal_project_starter_plan WHERE name = :name LIMIT 1"
            ),
            {"name": "default"},
        ).scalar()
        if has_default and not has_general:
            bind.execute(
                sa.text(
                    "UPDATE internal_project_starter_plan SET name = :new_name WHERE name = :old_name"
                ),
                {"new_name": "general", "old_name": "default"},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_project_starter_plan"):
        has_general = bind.execute(
            sa.text(
                "SELECT 1 FROM internal_project_starter_plan WHERE name = :name LIMIT 1"
            ),
            {"name": "general"},
        ).scalar()
        has_default = bind.execute(
            sa.text(
                "SELECT 1 FROM internal_project_starter_plan WHERE name = :name LIMIT 1"
            ),
            {"name": "default"},
        ).scalar()
        if has_general and not has_default:
            bind.execute(
                sa.text(
                    "UPDATE internal_project_starter_plan SET name = :new_name WHERE name = :old_name"
                ),
                {"new_name": "default", "old_name": "general"},
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project") and _column_exists(inspector, "internal_project", "industry_category"):
        if _index_exists(inspector, "internal_project", "ix_internal_project_industry_category"):
            op.drop_index("ix_internal_project_industry_category", table_name="internal_project")

        with op.batch_alter_table("internal_project", schema=None) as batch_op:
            batch_op.drop_column("industry_category")
