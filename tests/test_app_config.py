import app as app_module


def test_mail_default_sender_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("MAIL_USERNAME", "mail-user@example.com")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "sender@example.com")

    configured_app = app_module.create_app("testing")

    assert configured_app.config["MAIL_DEFAULT_SENDER"] == "sender@example.com"


def test_testing_env_ignores_auto_init_db(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTO_INIT_DB", "true")

    called = {"setup_database": False}

    def fake_setup_database(*_args, **_kwargs):
        called["setup_database"] = True

    monkeypatch.setattr(app_module, "setup_database", fake_setup_database)
    app_module.create_app("testing")

    assert called["setup_database"] is False
