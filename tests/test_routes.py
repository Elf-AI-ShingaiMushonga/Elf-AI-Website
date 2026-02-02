def test_home(client):
    response = client.get("/")
    assert response.status_code == 200


def test_solutions(client):
    response = client.get("/solutions")
    assert response.status_code == 200


def test_about(client):
    response = client.get("/about")
    assert response.status_code == 200


def test_enquire(client):
    response = client.get("/enquire")
    assert response.status_code == 200


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
