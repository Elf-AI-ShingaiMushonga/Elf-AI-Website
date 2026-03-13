import re

from extension import mail


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200


def test_security_headers_present(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("Content-Security-Policy") == "base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
    assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
    assert response.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
    assert response.headers.get("X-Permitted-Cross-Domain-Policies") == "none"


def test_internal_login_is_not_indexed_or_cached(client):
    response = client.get("/internal/login")
    assert response.status_code == 200
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"
    assert response.headers.get("Cache-Control") == "no-store, max-age=0"
    assert response.headers.get("Pragma") == "no-cache"


def test_solutions(client):
    response = client.get("/solutions")
    assert response.status_code == 200


def test_about(client):
    response = client.get("/about")
    assert response.status_code == 200


def test_enquire(client):
    response = client.get("/enquire")
    assert response.status_code == 200


def test_home_includes_seo_metadata(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert '<meta name="description"' in html
    assert '<link rel="canonical"' in html
    assert "ELF-AI" in html


def test_robots_txt(client):
    response = client.get("/robots.txt")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "User-agent: *" in body
    assert "Sitemap: https://elf-ai.co.za/sitemap.xml" in body


def test_sitemap_xml(client):
    response = client.get("/sitemap.xml")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<urlset" in body
    assert "<loc>https://elf-ai.co.za/</loc>" in body
    assert "<loc>https://elf-ai.co.za/about</loc>" in body
    assert "<loc>https://elf-ai.co.za/solutions</loc>" in body
    assert "<loc>https://elf-ai.co.za/enquire</loc>" in body


def test_contact_general_inquiry_redirects(client):
    response = client.post(
        "/contact",
        data={"name": "Pat", "service": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_contact_specific_service_redirects(client):
    response = client.post(
        "/contact",
        data={"name": "Jamie", "service": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_contact_redirects_to_safe_return_target(client):
    response = client.post(
        "/contact",
        data={
            "name": "Pat",
            "service": "0",
            "return_to": "/enquire#enquiry-form",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_contact_ignores_unsafe_return_target(client):
    response = client.post(
        "/contact",
        data={
            "name": "Pat",
            "service": "0",
            "return_to": "https://malicious.example.com/phish",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_contact_ignores_internal_return_target(client):
    response = client.post(
        "/contact",
        data={
            "name": "Pat",
            "service": "0",
            "return_to": "/internal/dashboard",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_contact_sets_single_success_flash(client, monkeypatch):
    monkeypatch.setattr(mail, "send", lambda _msg: None)
    response = client.post(
        "/contact",
        data={"name": "Pat", "email": "pat@example.com", "message": "Need help with workflow automation.", "service": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.session_transaction() as session_state:
        flashes = session_state.get("_flashes", [])

    success_messages = [message for category, message in flashes if category == "success"]
    assert len(success_messages) == 1


def test_contact_honeypot_skips_mail_send(client, monkeypatch):
    send_called = False

    def _fake_send(_msg):
        nonlocal send_called
        send_called = True

    monkeypatch.setattr(mail, "send", _fake_send)
    response = client.post(
        "/contact",
        data={"name": "Bot", "email": "bot@example.com", "website": "spam-link"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")
    assert send_called is False


def test_contact_validation_errors_are_rendered_back_on_enquiry_page(client):
    response = client.post(
        "/contact",
        data={
            "name": "",
            "email": "not-an-email",
            "message": "",
            "company": "ELF Test",
            "timeline": "this-quarter",
            "service": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")

    enquiry_response = client.get("/enquire")
    html = enquiry_response.get_data(as_text=True)
    assert enquiry_response.status_code == 200
    assert "Please correct the enquiry form and try again." in html
    assert "Enter your full name." in html
    assert "Enter a valid work email address." in html
    assert "Add a short description of the workflow problem you want solved." in html
    assert 'value="ELF Test"' in html
    assert 'value="not-an-email"' in html
    assert 'option value="this-quarter" selected' in html
    assert re.search(r'<option value="1"\s+selected', html) is not None


def test_contact_success_redirect_defaults_to_enquiry_form(client, monkeypatch):
    monkeypatch.setattr(mail, "send", lambda _msg: None)

    response = client.post(
        "/contact",
        data={
            "name": "Pat",
            "email": "pat@example.com",
            "message": "Need help reducing turnaround time in our intake workflow.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/enquire#enquiry-form")


def test_404_page_is_branded_and_not_indexed(client):
    response = client.get("/missing-page")
    html = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Page not found" in html
    assert "Return Home" in html
    assert "Book a Meeting" in html
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_500_page_is_branded(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    from app import create_app

    app = create_app("testing")
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.route("/boom")
    def boom():
        raise RuntimeError("boom")

    client = app.test_client()
    response = client.get("/boom")
    html = response.get_data(as_text=True)

    assert response.status_code == 500
    assert "Something broke on our side" in html
    assert "Return Home" in html
    assert response.headers.get("X-Robots-Tag") == "noindex, nofollow"
