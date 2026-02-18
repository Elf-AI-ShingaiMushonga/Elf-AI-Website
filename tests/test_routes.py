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
    assert response.headers["Location"].endswith("/#contact")


def test_contact_specific_service_redirects(client):
    response = client.post(
        "/contact",
        data={"name": "Jamie", "service": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/#contact")


def test_contact_sets_single_success_flash(client, monkeypatch):
    monkeypatch.setattr(mail, "send", lambda _msg: None)
    response = client.post(
        "/contact",
        data={"name": "Pat", "email": "pat@example.com", "message": "Hello", "service": "0"},
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
    assert response.headers["Location"].endswith("/#contact")
    assert send_called is False
