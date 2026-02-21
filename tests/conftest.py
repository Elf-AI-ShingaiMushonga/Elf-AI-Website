import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from models import (
    Branding,
    Feature,
    InternalAnnouncement,
    InternalClient,
    InternalProject,
    InternalResource,
    InternalResourceTag,
    InternalTask,
    InternalUser,
    Page_Heading,
    Service,
    Slide,
    db,
)


@pytest.fixture()
def app():
    os.environ["APP_ENV"] = "testing"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["SECRET_KEY"] = "test-secret"
    with tempfile.TemporaryDirectory() as upload_dir:
        app = create_app("testing")
        app.config["INTERNAL_RESOURCE_UPLOAD_DIR"] = upload_dir
        app.config["INTERNAL_RESOURCE_UPLOAD_MAX_BYTES"] = 2 * 1024 * 1024
        with app.app_context():
            db.create_all()

            service = Service(
                title="Test Service",
                description="Test description",
                icon="fa-test",
            )
            db.session.add(service)
            db.session.add(Feature(text="Feature text", service=service))
            db.session.add(
                Branding(
                    Title="ELF",
                    Slogan="Novel AI Solutions",
                    Tagline="Tagline",
                )
            )
            db.session.add(
                Page_Heading(
                    Title="solutions",
                    Slogan_1="Future",
                    Slogan_2="Today",
                    Tagline="Solutions",
                )
            )
            db.session.add(
                Page_Heading(
                    Title="about_us",
                    Slogan_1="Dynamic",
                    Slogan_2="Problem Solvers",
                    Tagline="About",
                )
            )
            db.session.add(
                Page_Heading(
                    Title="enquiry",
                    Slogan_1="Let's",
                    Slogan_2="Talk",
                    Tagline="Enquire",
                )
            )
            db.session.add(
                Slide(
                    title="Adaptable",
                    description="Desc",
                    owner="about_us",
                    icon="fa-puzzle-piece",
                )
            )
            db.session.add(
                Slide(
                    title="Consultation",
                    description="Desc",
                    owner="about_us_mini",
                    icon="fa-terminal",
                )
            )
            internal_user = InternalUser(
                full_name="Internal Admin",
                email="internal-admin@elf-ai.co.za",
                role="admin",
                is_active=True,
            )
            internal_user.set_password("secret-password")
            delivery_user = InternalUser(
                full_name="Delivery Consultant",
                email="delivery-consultant@elf-ai.co.za",
                role="consultant",
                is_active=True,
            )
            delivery_user.set_password("secret-password")
            operations_user = InternalUser(
                full_name="Operations Analyst",
                email="operations-analyst@elf-ai.co.za",
                role="operations",
                is_active=True,
            )
            operations_user.set_password("secret-password")
            db.session.add_all([internal_user, delivery_user, operations_user])

            client_record = InternalClient(
                name="Test Client",
                industry="Legal",
                account_owner="Internal Admin",
                status="active",
                notes="Test client notes",
            )
            db.session.add(client_record)
            db.session.flush()

            project_record = InternalProject(
                name="Test Internal Project",
                client=client_record,
                owner=internal_user,
                stage="delivery",
                status="on-track",
                due_date=date.today() + timedelta(days=5),
                summary="Internal project summary",
            )
            db.session.add(project_record)
            db.session.flush()

            parent_task = InternalTask(
                project=project_record,
                title="Prepare weekly update",
                assignee="Internal Admin",
                priority="high",
                status="in-progress",
                due_date=date.today() + timedelta(days=2),
            )
            db.session.add(parent_task)
            db.session.flush()
            db.session.add(
                InternalTask(
                    project=project_record,
                    parent_task=parent_task,
                    title="Compile supporting metrics",
                    assignee="Internal Admin",
                    priority="medium",
                    status="todo",
                    due_date=date.today() + timedelta(days=3),
                )
            )
            db.session.add(
                InternalTask(
                    project=project_record,
                    title="Archive previous sprint artifacts",
                    assignee="Internal Admin",
                    priority="low",
                    status="todo",
                    due_date=date.today() + timedelta(days=5),
                )
            )
            internal_playbook = InternalResource(
                title="Internal Playbook",
                category="operations",
                link="/internal/resources#playbook",
                description="Internal delivery playbook",
                projects=[project_record],
                tasks=[parent_task],
            )
            internal_playbook.tags = [
                InternalResourceTag(name="playbook"),
                InternalResourceTag(name="delivery"),
            ]
            db.session.add(internal_playbook)
            db.session.add(
                InternalAnnouncement(
                    title="Test Announcement",
                    body="Internal test announcement",
                )
            )
            db.session.commit()
            yield app
            db.session.remove()
            db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
