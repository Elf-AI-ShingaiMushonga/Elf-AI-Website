"""add configurable project starter plan template table

Revision ID: 20260221_01_starter_plan
Revises: 20260219_01_messaging_platform
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_01_starter_plan"
down_revision = "20260219_01_messaging_platform"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def _index_exists(inspector, table_name, index_name):
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "internal_project_starter_plan"):
        op.create_table(
            "internal_project_starter_plan",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("template_json", sa.Text(), nullable=False),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["updated_by_id"], ["internal_user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_starter_plan"):
        if not _index_exists(
            inspector,
            "internal_project_starter_plan",
            "ix_internal_project_starter_plan_name",
        ):
            op.create_index(
                "ix_internal_project_starter_plan_name",
                "internal_project_starter_plan",
                ["name"],
                unique=True,
            )
        if not _index_exists(
            inspector,
            "internal_project_starter_plan",
            "ix_internal_project_starter_plan_updated_by_id",
        ):
            op.create_index(
                "ix_internal_project_starter_plan_updated_by_id",
                "internal_project_starter_plan",
                ["updated_by_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_project_starter_plan"):
        op.drop_table("internal_project_starter_plan")
