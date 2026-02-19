"""add internal messaging platform tables

Revision ID: 20260219_01_internal_messaging_platform
Revises: 20260218_01_internal_knowledge_library_links
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260219_01_internal_messaging_platform"
down_revision = "20260218_01_internal_knowledge_library_links"
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

    if not _table_exists(inspector, "internal_message_channel"):
        op.create_table(
            "internal_message_channel",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("channel_type", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=True),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("direct_user_low_id", sa.Integer(), nullable=True),
            sa.Column("direct_user_high_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["internal_project.id"]),
            sa.ForeignKeyConstraint(["direct_user_low_id"], ["internal_user.id"]),
            sa.ForeignKeyConstraint(["direct_user_high_id"], ["internal_user.id"]),
            sa.ForeignKeyConstraint(["created_by_id"], ["internal_user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", name="uq_internal_message_channel_project_id"),
            sa.UniqueConstraint(
                "direct_user_low_id",
                "direct_user_high_id",
                name="uq_internal_message_channel_direct_pair",
            ),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_message_channel"):
        if not _index_exists(inspector, "internal_message_channel", "ix_internal_message_channel_channel_type"):
            op.create_index(
                "ix_internal_message_channel_channel_type",
                "internal_message_channel",
                ["channel_type"],
                unique=False,
            )
        if not _index_exists(inspector, "internal_message_channel", "ix_internal_message_channel_project_id"):
            op.create_index(
                "ix_internal_message_channel_project_id",
                "internal_message_channel",
                ["project_id"],
                unique=False,
            )
        if not _index_exists(
            inspector,
            "internal_message_channel",
            "ix_internal_message_channel_direct_user_low_id",
        ):
            op.create_index(
                "ix_internal_message_channel_direct_user_low_id",
                "internal_message_channel",
                ["direct_user_low_id"],
                unique=False,
            )
        if not _index_exists(
            inspector,
            "internal_message_channel",
            "ix_internal_message_channel_direct_user_high_id",
        ):
            op.create_index(
                "ix_internal_message_channel_direct_user_high_id",
                "internal_message_channel",
                ["direct_user_high_id"],
                unique=False,
            )
        if not _index_exists(inspector, "internal_message_channel", "ix_internal_message_channel_created_by_id"):
            op.create_index(
                "ix_internal_message_channel_created_by_id",
                "internal_message_channel",
                ["created_by_id"],
                unique=False,
            )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_message_channel_member_links"):
        op.create_table(
            "internal_message_channel_member_links",
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["channel_id"], ["internal_message_channel.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["internal_user.id"]),
            sa.PrimaryKeyConstraint("channel_id", "user_id"),
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "internal_message"):
        op.create_table(
            "internal_message",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("channel_id", sa.Integer(), nullable=False),
            sa.Column("sender_id", sa.Integer(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["channel_id"], ["internal_message_channel.id"]),
            sa.ForeignKeyConstraint(["sender_id"], ["internal_user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_message"):
        if not _index_exists(inspector, "internal_message", "ix_internal_message_channel_id"):
            op.create_index("ix_internal_message_channel_id", "internal_message", ["channel_id"], unique=False)
        if not _index_exists(inspector, "internal_message", "ix_internal_message_sender_id"):
            op.create_index("ix_internal_message_sender_id", "internal_message", ["sender_id"], unique=False)
        if not _index_exists(inspector, "internal_message", "ix_internal_message_created_at"):
            op.create_index("ix_internal_message_created_at", "internal_message", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "internal_message"):
        op.drop_table("internal_message")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_message_channel_member_links"):
        op.drop_table("internal_message_channel_member_links")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "internal_message_channel"):
        op.drop_table("internal_message_channel")
