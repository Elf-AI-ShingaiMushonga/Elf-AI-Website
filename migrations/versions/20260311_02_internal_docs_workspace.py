"""add internal docs workspace table

Revision ID: 20260311_02_docs_workspace
Revises: 20260311_01_workspace_hub
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_02_docs_workspace"
down_revision = "20260311_01_workspace_hub"
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

    if not _table_exists(inspector, "internal_doc_page"):
        op.create_table(
            "internal_doc_page",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("slug", sa.String(length=220), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["author_id"], ["internal_user.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["internal_doc_page.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_doc_page"):
        if not _index_exists(inspector, "internal_doc_page", "ix_internal_doc_page_slug"):
            op.create_index("ix_internal_doc_page_slug", "internal_doc_page", ["slug"], unique=True)
        if not _index_exists(inspector, "internal_doc_page", "ix_internal_doc_page_project_id"):
            op.create_index("ix_internal_doc_page_project_id", "internal_doc_page", ["project_id"], unique=False)
        if not _index_exists(inspector, "internal_doc_page", "ix_internal_doc_page_author_id"):
            op.create_index("ix_internal_doc_page_author_id", "internal_doc_page", ["author_id"], unique=False)
        if not _index_exists(inspector, "internal_doc_page", "ix_internal_doc_page_parent_id"):
            op.create_index("ix_internal_doc_page_parent_id", "internal_doc_page", ["parent_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_doc_page"):
        op.drop_table("internal_doc_page")
