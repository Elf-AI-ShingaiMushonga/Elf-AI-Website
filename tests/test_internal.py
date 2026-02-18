import re

from models import InternalClient, InternalProject, InternalResource, InternalResourceTag, InternalTask, InternalUser, db


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _csrf_token_for_path(client, path: str) -> str:
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 200
    return _extract_csrf_token(response.get_data(as_text=True))


def _login(client):
    csrf_token = _csrf_token_for_path(client, "/internal/login")
    return client.post(
        "/internal/login",
        data={"email": "internal-admin@elf-ai.co.za", "password": "secret-password", "csrf_token": csrf_token},
        follow_redirects=False,
    )


def test_internal_login_page(client):
    response = client.get("/internal/login")
    assert response.status_code == 200
    assert "Internal Sign In" in response.get_data(as_text=True)


def test_internal_dashboard_requires_authentication(client):
    response = client.get("/internal", follow_redirects=False)
    assert response.status_code == 302
    assert "/internal/login" in response.headers["Location"]


def test_internal_login_with_invalid_credentials(client):
    csrf_token = _csrf_token_for_path(client, "/internal/login")
    response = client.post(
        "/internal/login",
        data={"email": "wrong@elf-ai.co.za", "password": "bad-password", "csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Invalid email or password." in response.get_data(as_text=True)


def test_internal_login_and_dashboard_access(client):
    login_response = _login(client)
    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/internal/dashboard")

    dashboard_response = client.get("/internal/dashboard")
    assert dashboard_response.status_code == 200
    html = dashboard_response.get_data(as_text=True)
    assert "Delivery Dashboard" in html
    assert "Operational Priorities" in html


def test_internal_sections_access_when_logged_in(client):
    _login(client)

    clients_response = client.get("/internal/clients")
    assert clients_response.status_code == 200
    assert "Client Registry" in clients_response.get_data(as_text=True)

    projects_response = client.get("/internal/projects")
    assert projects_response.status_code == 200
    assert "Project Operations" in projects_response.get_data(as_text=True)

    todos_response = client.get("/internal/todos")
    assert todos_response.status_code == 200
    assert "Nested To-Do Board" in todos_response.get_data(as_text=True)

    resources_response = client.get("/internal/resources")
    assert resources_response.status_code == 200
    assert "Internal Site Requirements" in resources_response.get_data(as_text=True)


def test_internal_logout(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/dashboard")
    logout_response = client.post(
        "/internal/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert logout_response.status_code == 302
    assert logout_response.headers["Location"].endswith("/internal/login")

    redirected = client.get("/internal/dashboard", follow_redirects=False)
    assert redirected.status_code == 302
    assert "/internal/login" in redirected.headers["Location"]


def test_internal_logout_get_not_allowed(client):
    _login(client)
    response = client.get("/internal/logout", follow_redirects=False)
    assert response.status_code == 405


def test_internal_client_add(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/clients")

    response = client.post(
        "/internal/clients/add",
        data={
            "csrf_token": csrf_token,
            "name": "New Intake Client",
            "industry": "Healthcare",
            "account_owner": "Internal Admin",
            "status": "active",
            "notes": "Created during intake flow test.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/clients")

    with client.application.app_context():
        created_client = InternalClient.query.filter_by(name="New Intake Client").first()
        assert created_client is not None
        assert created_client.industry == "Healthcare"


def test_internal_project_add(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        owner_record = InternalUser.query.filter_by(email="internal-admin@elf-ai.co.za").first()
        assert client_record is not None
        assert owner_record is not None

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Internal Delivery Sprint",
            "client_id": str(client_record.id),
            "owner_id": str(owner_record.id),
            "stage": "delivery",
            "status": "on-track",
            "summary": "Scoped delivery sprint for internal project add test.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/internal/projects?client_id={client_record.id}" in response.headers["Location"]

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="Internal Delivery Sprint").first()
        assert created_project is not None
        assert created_project.client_id == client_record.id


def test_internal_todo_add_nested_task(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/todos")

    with client.application.app_context():
        parent_task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert parent_task is not None
        project_id = parent_task.project_id
        parent_task_id = parent_task.id

    response = client.post(
        "/internal/todos/add",
        data={
            "csrf_token": csrf_token,
            "view_mode": "nested",
            "project_id": str(project_id),
            "parent_task_id": str(parent_task_id),
            "title": "Draft client summary",
            "assignee": "Internal Admin",
            "priority": "high",
            "status": "todo",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/todos?view=nested")

    with client.application.app_context():
        created_task = InternalTask.query.filter_by(title="Draft client summary").first()
        assert created_task is not None
        assert created_task.parent_task_id == parent_task_id
        assert created_task.priority == "high"


def test_internal_todo_priority_queue_order(client):
    _login(client)
    response = client.get("/internal/todos?view=priority")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    queue_titles = re.findall(r"Queue #\d+</p>\s*<p class=\"text-white font-semibold\">([^<]+)</p>", html)
    assert queue_titles
    assert queue_titles[0] == "Prepare weekly update"
    assert "Archive previous sprint artifacts" in queue_titles
    assert "Search by task, assignee, project, or linked doc..." in html
    assert "Due soon threshold:" in html


def test_internal_todo_project_scope_filter(client):
    _login(client)

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        assert client_record is not None
        scoped_project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert scoped_project is not None
        scoped_project_id = scoped_project.id
        other_project = InternalProject(
            name="Other Project Scope",
            client=client_record,
            stage="delivery",
            status="on-track",
            summary="Secondary project for scope filtering.",
        )
        db.session.add(other_project)
        db.session.flush()
        db.session.add(
            InternalTask(
                project=other_project,
                title="Other project task",
                assignee="Internal Admin",
                priority="medium",
                status="todo",
            )
        )
        db.session.commit()

    response = client.get(f"/internal/todos?view=nested&project_id={scoped_project_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Prepare weekly update" in html
    assert "Other project task" not in html


def test_internal_resource_add_with_tags_and_links(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/resources")

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert project is not None
        assert task is not None

    response = client.post(
        "/internal/resources/add",
        data={
            "csrf_token": csrf_token,
            "title": "QA Runbook",
            "link": "https://example.com/qa-runbook",
            "category": "operations",
            "description": "Weekly QA execution runbook",
            "tags": "qa, runbook, delivery",
            "project_ids": [str(project.id)],
            "task_ids": [str(task.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/internal/resources" in response.headers["Location"]

    with client.application.app_context():
        created_resource = InternalResource.query.filter_by(title="QA Runbook").first()
        assert created_resource is not None
        assert {tag.name for tag in created_resource.tags} == {"qa", "runbook", "delivery"}
        assert project.id in {linked_project.id for linked_project in created_resource.projects}
        assert task.id in {linked_task.id for linked_task in created_resource.tasks}


def test_internal_resource_search_and_tag_filter(client):
    _login(client)

    response = client.get("/internal/resources?q=playbook&category=operations&tag=playbook")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Internal Playbook" in html
    assert "Linked Projects" in html
    assert "Linked To-Do Items" in html


def test_internal_resource_state_filters(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert project is not None
        assert task is not None

        unlinked_resource = InternalResource(
            title="Unlinked Internal Checklist",
            category="operations",
            link="https://example.com/unlinked-checklist",
            description="Not linked to project or task",
        )
        untagged_resource = InternalResource(
            title="Untagged Delivery Note",
            category="operations",
            link="https://example.com/untagged-note",
            description="Linked but intentionally untagged",
            projects=[project],
            tasks=[task],
        )
        linked_resource = InternalResource(
            title="Tagged Linked SOP",
            category="operations",
            link="https://example.com/tagged-linked-sop",
            description="Linked resource with tags",
            projects=[project],
            tasks=[task],
        )
        linked_resource.tags = [InternalResourceTag(name="sop-tag")]
        db.session.add_all([unlinked_resource, untagged_resource, linked_resource])
        db.session.commit()

    unlinked_response = client.get("/internal/resources?state=unlinked")
    unlinked_html = unlinked_response.get_data(as_text=True)
    assert unlinked_response.status_code == 200
    assert "Unlinked Internal Checklist" in unlinked_html
    assert "Tagged Linked SOP" not in unlinked_html

    untagged_response = client.get("/internal/resources?state=untagged")
    untagged_html = untagged_response.get_data(as_text=True)
    assert untagged_response.status_code == 200
    assert "Untagged Delivery Note" in untagged_html
    assert "Tagged Linked SOP" not in untagged_html

    linked_response = client.get("/internal/resources?state=linked")
    linked_html = linked_response.get_data(as_text=True)
    assert linked_response.status_code == 200
    assert "Tagged Linked SOP" in linked_html
    assert "Unlinked Internal Checklist" not in linked_html


def test_internal_resource_project_scope_filter(client):
    _login(client)

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        scoped_project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert client_record is not None
        assert scoped_project is not None
        scoped_project_id = scoped_project.id

        other_project = InternalProject(
            name="Resource Scope Project",
            client=client_record,
            stage="build",
            status="on-track",
            summary="Project for scoped resource filtering.",
        )
        db.session.add(other_project)
        db.session.flush()

        scoped_resource = InternalResource(
            title="Scoped Project Runbook",
            category="operations",
            link="https://example.com/scoped-runbook",
            description="Resource linked to base scoped project",
            projects=[scoped_project],
        )
        other_resource = InternalResource(
            title="Other Project Runbook",
            category="operations",
            link="https://example.com/other-runbook",
            description="Resource linked to other project",
            projects=[other_project],
        )
        db.session.add_all([scoped_resource, other_resource])
        db.session.commit()

    response = client.get(f"/internal/resources?project_id={scoped_project_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Scoped Project Runbook" in html
    assert "Other Project Runbook" not in html


def test_internal_post_requires_csrf(client):
    _login(client)

    response = client.post(
        "/internal/resources/add",
        data={
            "title": "No CSRF",
            "link": "https://example.com/no-csrf",
            "category": "operations",
            "description": "Should fail CSRF validation",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "CSRF token missing or invalid" in response.get_data(as_text=True)


def test_internal_resource_add_rejects_unsafe_link(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/resources")

    response = client.post(
        "/internal/resources/add",
        data={
            "csrf_token": csrf_token,
            "title": "Unsafe Link Doc",
            "link": "javascript:alert(1)",
            "category": "operations",
            "description": "Unsafe link should be blocked",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_resource = InternalResource.query.filter_by(title="Unsafe Link Doc").first()
        assert created_resource is None


def test_internal_linked_docs_visible_on_projects_and_todos(client):
    _login(client)

    project_response = client.get("/internal/projects")
    assert project_response.status_code == 200
    project_html = project_response.get_data(as_text=True)
    assert "Linked Docs" in project_html
    assert "Internal Playbook" in project_html

    todo_response = client.get("/internal/todos")
    assert todo_response.status_code == 200
    todo_html = todo_response.get_data(as_text=True)
    assert "Project Docs" in todo_html
    assert "Internal Playbook" in todo_html
