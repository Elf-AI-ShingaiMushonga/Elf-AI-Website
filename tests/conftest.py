import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from models import Branding, Feature, Page_Heading, Service, Slide, db


@pytest.fixture()
def app():
    os.environ["APP_ENV"] = "testing"
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["SECRET_KEY"] = "test-secret"
    app = create_app("testing")
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
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
