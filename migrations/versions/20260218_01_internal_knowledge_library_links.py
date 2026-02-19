"""add internal knowledge library link tables and task parent id

Revision ID: 20260218_01_knowledge_links
Revises: 
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260218_01_knowledge_links"
down_revision = None
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


def _foreign_key_exists(inspector, table_name, fk_name):
    if not _table_exists(inspector, table_name):
        return False
    return any(foreign_key["name"] == fk_name for foreign_key in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_task") and not _column_exists(inspector, "internal_task", "parent_task_id"):
        with op.batch_alter_table("internal_task", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_task_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_internal_task_parent_task_id_internal_task",
                "internal_task",
                ["parent_task_id"],
                ["id"],
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_task") and _column_exists(inspector, "internal_task", "parent_task_id"):
        if not _index_exists(inspector, "internal_task", "ix_internal_task_parent_task_id"):
            op.create_index("ix_internal_task_parent_task_id", "internal_task", ["parent_task_id"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_resource_tag"):
        op.create_table(
            "internal_resource_tag",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index(op.f("ix_internal_resource_tag_name"), "internal_resource_tag", ["name"], unique=True)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_resource_project_links"):
        op.create_table(
            "internal_resource_project_links",
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.ForeignKeyConstraint(["resource_id"], ["internal_resource.id"]),
            sa.PrimaryKeyConstraint("resource_id", "project_id"),
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_resource_task_links"):
        op.create_table(
            "internal_resource_task_links",
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["resource_id"], ["internal_resource.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["internal_task.id"]),
            sa.PrimaryKeyConstraint("resource_id", "task_id"),
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_resource_tag_links"):
        op.create_table(
            "internal_resource_tag_links",
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["resource_id"], ["internal_resource.id"]),
            sa.ForeignKeyConstraint(["tag_id"], ["internal_resource_tag.id"]),
            sa.PrimaryKeyConstraint("resource_id", "tag_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_resource_tag_links"):
        op.drop_table("internal_resource_tag_links")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_resource_task_links"):
        op.drop_table("internal_resource_task_links")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_resource_project_links"):
        op.drop_table("internal_resource_project_links")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_resource_tag"):
        if _index_exists(inspector, "internal_resource_tag", op.f("ix_internal_resource_tag_name")):
            op.drop_index(op.f("ix_internal_resource_tag_name"), table_name="internal_resource_tag")
        op.drop_table("internal_resource_tag")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_task") and _column_exists(inspector, "internal_task", "parent_task_id"):
        if _index_exists(inspector, "internal_task", "ix_internal_task_parent_task_id"):
            op.drop_index("ix_internal_task_parent_task_id", table_name="internal_task")

        with op.batch_alter_table("internal_task", schema=None) as batch_op:
            if _foreign_key_exists(inspector, "internal_task", "fk_internal_task_parent_task_id_internal_task"):
                batch_op.drop_constraint("fk_internal_task_parent_task_id_internal_task", type_="foreignkey")
            batch_op.drop_column("parent_task_id")
