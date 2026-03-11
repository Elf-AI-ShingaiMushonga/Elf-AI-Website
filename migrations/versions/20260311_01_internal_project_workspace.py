"""add internal project workspace tables

Revision ID: 20260311_01_workspace_hub
Revises: 20260221_02_project_industry
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_01_workspace_hub"
down_revision = "20260221_02_project_industry"
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

    if not _table_exists(inspector, "internal_project_milestone"):
        op.create_table(
            "internal_project_milestone",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("owner_name", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_milestone"):
        if not _index_exists(
            inspector,
            "internal_project_milestone",
            "ix_internal_project_milestone_project_id",
        ):
            op.create_index(
                "ix_internal_project_milestone_project_id",
                "internal_project_milestone",
                ["project_id"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_project_deliverable"):
        op.create_table(
            "internal_project_deliverable",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("owner_name", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("link", sa.String(length=500), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_deliverable"):
        if not _index_exists(
            inspector,
            "internal_project_deliverable",
            "ix_internal_project_deliverable_project_id",
        ):
            op.create_index(
                "ix_internal_project_deliverable_project_id",
                "internal_project_deliverable",
                ["project_id"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_project_stakeholder"):
        op.create_table(
            "internal_project_stakeholder",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("role_title", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("organisation", sa.String(length=160), nullable=False),
            sa.Column("stakeholder_type", sa.String(length=32), nullable=False),
            sa.Column("influence_level", sa.String(length=32), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_stakeholder"):
        if not _index_exists(
            inspector,
            "internal_project_stakeholder",
            "ix_internal_project_stakeholder_project_id",
        ):
            op.create_index(
                "ix_internal_project_stakeholder_project_id",
                "internal_project_stakeholder",
                ["project_id"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_project_risk"):
        op.create_table(
            "internal_project_risk",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("owner_name", sa.String(length=120), nullable=False),
            sa.Column("severity", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("mitigation", sa.Text(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_risk"):
        if not _index_exists(inspector, "internal_project_risk", "ix_internal_project_risk_project_id"):
            op.create_index(
                "ix_internal_project_risk_project_id",
                "internal_project_risk",
                ["project_id"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_project_status_update"):
        op.create_table(
            "internal_project_status_update",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column("headline", sa.String(length=200), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("wins", sa.Text(), nullable=True),
            sa.Column("risks", sa.Text(), nullable=True),
            sa.Column("next_steps", sa.Text(), nullable=True),
            sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["author_id"], ["internal_user.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_status_update"):
        if not _index_exists(
            inspector,
            "internal_project_status_update",
            "ix_internal_project_status_update_project_id",
        ):
            op.create_index(
                "ix_internal_project_status_update_project_id",
                "internal_project_status_update",
                ["project_id"],
                unique=False,
            )
        if not _index_exists(
            inspector,
            "internal_project_status_update",
            "ix_internal_project_status_update_author_id",
        ):
            op.create_index(
                "ix_internal_project_status_update_author_id",
                "internal_project_status_update",
                ["author_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_project_status_update"):
        op.drop_table("internal_project_status_update")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_risk"):
        op.drop_table("internal_project_risk")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_stakeholder"):
        op.drop_table("internal_project_stakeholder")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_deliverable"):
        op.drop_table("internal_project_deliverable")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_project_milestone"):
        op.drop_table("internal_project_milestone")
