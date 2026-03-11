import io
import json
import re
from datetime import date, timedelta

from models import (
    InternalClient,
    InternalDocPage,
    InternalMessage,
    InternalMessageChannel,
    InternalProjectDeliverable,
    InternalProjectMilestone,
    InternalProjectRisk,
    InternalProjectStakeholder,
    InternalProjectStatusUpdate,
    InternalProject,
    InternalProjectStarterPlan,
    InternalResource,
    InternalResourceTag,
    InternalTask,
    InternalUser,
    db,
)


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
    assert "Delivery Command Center" in html
    assert "Operational Priorities" in html
    assert "Projects Requiring Attention" in html


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

    messages_response = client.get("/internal/messages")
    assert messages_response.status_code == 200
    assert "Consultant Messaging" in messages_response.get_data(as_text=True)

    docs_response = client.get("/internal/docs")
    assert docs_response.status_code == 200
    assert "Workspace Docs" in docs_response.get_data(as_text=True)


def test_internal_omnibar_requires_authentication(client):
    response = client.get("/internal/go?q=projects", follow_redirects=False)
    assert response.status_code == 302
    assert "/internal/login" in response.headers["Location"]


def test_internal_omnibar_quick_target_navigation(client):
    _login(client)

    response = client.get("/internal/go?q=projects", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/projects")

    docs_response = client.get("/internal/go?q=docs", follow_redirects=False)
    assert docs_response.status_code == 302
    assert docs_response.headers["Location"].endswith("/internal/docs")


def test_internal_omnibar_project_match_navigation(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert project is not None
        project_id = project.id

    response = client.get("/internal/go?q=project:%20Test%20Internal%20Project", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/internal/projects/{project_id}")


def test_internal_omnibar_task_match_navigation(client):
    _login(client)

    with client.application.app_context():
        task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert task is not None
        project_id = task.project_id

    response = client.get("/internal/go?q=task:%20Prepare%20weekly%20update", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/internal/todos?view=priority&project_id={project_id}")


def test_internal_omnibar_doc_page_match_navigation(client):
    _login(client)

    response = client.get("/internal/go?q=page:%20Delivery%20Handbook", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/docs/delivery-handbook")


def test_internal_omnibar_unknown_query_shows_feedback(client):
    _login(client)

    response = client.get("/internal/go?q=not-a-real-internal-destination", follow_redirects=True)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No exact match found. Try page names or prefixes:" in html
    assert "Delivery Command Center" in html


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


def test_internal_project_add_uses_default_timeline_and_starter_plan(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        owner_record = InternalUser.query.filter_by(email="internal-admin@elf-ai.co.za").first()
        assert client_record is not None
        assert owner_record is not None
        expected_due_date = date.today() + timedelta(days=45)

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Timeline Defaults Project",
            "client_mode": "existing",
            "client_id": str(client_record.id),
            "owner_id": "self",
            "timeline_days": "45",
            "stage": "discovery",
            "status": "on-track",
            "summary": "Project created with default timeline and starter tasks.",
            "create_starter_plan": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="Timeline Defaults Project").first()
        assert created_project is not None
        assert created_project.client_id == client_record.id
        assert created_project.owner_id == owner_record.id
        assert created_project.due_date == expected_due_date

        project_task_titles = {task.title for task in created_project.tasks}
        assert "Kickoff and Discovery" in project_task_titles
        assert "Solution Build and Validation" in project_task_titles
        assert "Value Review and Scale Plan" in project_task_titles


def test_internal_project_add_can_create_client_inline(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Inline Client Kickoff",
            "client_mode": "new",
            "new_client_name": "Inline Intake Client",
            "new_client_industry": "Retail",
            "new_client_account_owner": "Internal Admin",
            "new_client_status": "active",
            "new_client_notes": "Created directly during kickoff flow.",
            "timeline_days": "30",
            "owner_id": "self",
            "stage": "build",
            "status": "on-track",
            "summary": "Kickoff project with inline client creation.",
            "create_starter_plan": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/internal/projects?client_id=" in response.headers["Location"]

    with client.application.app_context():
        created_client = InternalClient.query.filter_by(name="Inline Intake Client").first()
        created_project = InternalProject.query.filter_by(name="Inline Client Kickoff").first()
        assert created_client is not None
        assert created_project is not None
        assert created_project.client_id == created_client.id


def test_internal_project_add_respects_existing_client_mode(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    with client.application.app_context():
        existing_client = InternalClient.query.filter_by(name="Test Client").first()
        assert existing_client is not None
        existing_client_id = existing_client.id

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Existing Mode Project",
            "client_mode": "existing",
            "client_id": str(existing_client_id),
            "new_client_name": "Should Not Be Created",
            "new_client_industry": "Finance",
            "new_client_account_owner": "Internal Admin",
            "owner_id": "self",
            "stage": "build",
            "status": "on-track",
            "summary": "Ensure stale new-client fields do not override selected client.",
            "create_starter_plan": "0",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="Existing Mode Project").first()
        assert created_project is not None
        assert created_project.client_id == existing_client_id
        stale_client = InternalClient.query.filter_by(name="Should Not Be Created").first()
        assert stale_client is None


def test_internal_project_add_can_disable_starter_plan(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        assert client_record is not None
        client_id = client_record.id

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "No Starter Plan Project",
            "client_mode": "existing",
            "client_id": str(client_id),
            "owner_id": "self",
            "timeline_days": "30",
            "stage": "discovery",
            "status": "on-track",
            "summary": "Project created without starter task generation.",
            "create_starter_plan": "0",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="No Starter Plan Project").first()
        assert created_project is not None
        assert len(created_project.tasks) == 0


def test_internal_project_workspace_page(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert project is not None
        project_id = project.id

    response = client.get(f"/internal/projects/{project_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Project Overview" in html
    assert "Milestone Plan" in html
    assert "Deliverables" in html
    assert "Risk Register" in html
    assert "Stakeholder Register" in html
    assert "Pilot execution is underway" in html
    assert "Delivery Handbook" in html


def test_internal_project_workspace_overview_update(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert project is not None
        project_id = project.id
        delivery_user = InternalUser.query.filter_by(email="delivery-consultant@elf-ai.co.za").first()
        assert delivery_user is not None
        delivery_user_id = delivery_user.id

    csrf_token = _csrf_token_for_path(client, f"/internal/projects/{project_id}")
    response = client.post(
        f"/internal/projects/{project_id}/overview",
        data={
            "csrf_token": csrf_token,
            "name": "Updated Internal Project",
            "summary": "Expanded scope and commercial baseline.",
            "stage": "operations",
            "status": "at-risk",
            "owner_id": str(delivery_user_id),
            "due_date": (date.today() + timedelta(days=14)).isoformat(),
            "value_estimate": "18000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/internal/projects/{project_id}#overview")

    with client.application.app_context():
        updated_project = db.session.get(InternalProject, project_id)
        assert updated_project is not None
        assert updated_project.name == "Updated Internal Project"
        assert updated_project.stage == "operations"
        assert updated_project.status == "at-risk"
        assert updated_project.owner_id == delivery_user_id
        assert float(updated_project.value_estimate) == 18000.0


def test_internal_project_workspace_add_operating_records(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert project is not None
        project_id = project.id

    csrf_token = _csrf_token_for_path(client, f"/internal/projects/{project_id}")

    milestone_response = client.post(
        f"/internal/projects/{project_id}/milestones/add",
        data={
            "csrf_token": csrf_token,
            "title": "Go-Live Decision",
            "owner_name": "Internal Admin",
            "status": "planned",
            "due_date": (date.today() + timedelta(days=8)).isoformat(),
            "notes": "Approve production launch after QA sign-off.",
        },
        follow_redirects=False,
    )
    assert milestone_response.status_code == 302

    deliverable_response = client.post(
        f"/internal/projects/{project_id}/deliverables/add",
        data={
            "csrf_token": csrf_token,
            "title": "Launch Checklist",
            "owner_name": "Internal Admin",
            "status": "in-progress",
            "due_date": (date.today() + timedelta(days=6)).isoformat(),
            "link": "https://example.com/launch-checklist",
            "description": "Checklist for launch readiness and rollback plan.",
        },
        follow_redirects=False,
    )
    assert deliverable_response.status_code == 302

    risk_response = client.post(
        f"/internal/projects/{project_id}/risks/add",
        data={
            "csrf_token": csrf_token,
            "title": "Client review cycle could slip by a week",
            "owner_name": "Internal Admin",
            "severity": "medium",
            "status": "open",
            "due_date": (date.today() + timedelta(days=4)).isoformat(),
            "mitigation": "Pre-book client review slot and circulate materials early.",
        },
        follow_redirects=False,
    )
    assert risk_response.status_code == 302

    stakeholder_response = client.post(
        f"/internal/projects/{project_id}/stakeholders/add",
        data={
            "csrf_token": csrf_token,
            "name": "Jordan Sponsor",
            "role_title": "Programme Sponsor",
            "organisation": "Test Client",
            "email": "jordan.sponsor@example.com",
            "stakeholder_type": "client",
            "influence_level": "core",
            "notes": "Needs weekly summary before steering review.",
        },
        follow_redirects=False,
    )
    assert stakeholder_response.status_code == 302

    status_update_response = client.post(
        f"/internal/projects/{project_id}/status-updates/add",
        data={
            "csrf_token": csrf_token,
            "headline": "Launch preparation has started",
            "summary": "The team is preparing launch readiness artefacts and closing final QA items.",
            "wins": "Drafted launch checklist.",
            "risks": "Client review cycle remains tight.",
            "next_steps": "Close QA and confirm go-live date.",
            "progress_percent": "55",
        },
        follow_redirects=False,
    )
    assert status_update_response.status_code == 302

    with client.application.app_context():
        assert InternalProjectMilestone.query.filter_by(title="Go-Live Decision", project_id=project_id).first() is not None
        assert InternalProjectDeliverable.query.filter_by(title="Launch Checklist", project_id=project_id).first() is not None
        assert InternalProjectRisk.query.filter_by(title="Client review cycle could slip by a week", project_id=project_id).first() is not None
        assert InternalProjectStakeholder.query.filter_by(name="Jordan Sponsor", project_id=project_id).first() is not None
        latest_update = InternalProjectStatusUpdate.query.filter_by(
            headline="Launch preparation has started",
            project_id=project_id,
        ).first()
        assert latest_update is not None
        assert latest_update.progress_percent == 55


def test_internal_project_workspace_inline_status_updates(client):
    _login(client)

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        milestone = InternalProjectMilestone.query.filter_by(title="Pilot Review").first()
        deliverable = InternalProjectDeliverable.query.filter_by(title="Weekly Client Update").first()
        risk = InternalProjectRisk.query.filter_by(title="Edge-case routing may delay launch").first()
        assert project is not None
        assert milestone is not None
        assert deliverable is not None
        assert risk is not None
        project_id = project.id
        milestone_id = milestone.id
        deliverable_id = deliverable.id
        risk_id = risk.id

    csrf_token = _csrf_token_for_path(client, f"/internal/projects/{project_id}")
    milestone_response = client.post(
        f"/internal/projects/{project_id}/milestones/{milestone_id}/status",
        data={"csrf_token": csrf_token, "status": "done"},
        follow_redirects=False,
    )
    assert milestone_response.status_code == 302

    deliverable_response = client.post(
        f"/internal/projects/{project_id}/deliverables/{deliverable_id}/status",
        data={"csrf_token": csrf_token, "status": "delivered"},
        follow_redirects=False,
    )
    assert deliverable_response.status_code == 302

    risk_response = client.post(
        f"/internal/projects/{project_id}/risks/{risk_id}/status",
        data={"csrf_token": csrf_token, "status": "mitigated"},
        follow_redirects=False,
    )
    assert risk_response.status_code == 302

    with client.application.app_context():
        assert db.session.get(InternalProjectMilestone, milestone_id).status == "done"
        assert db.session.get(InternalProjectDeliverable, deliverable_id).status == "delivered"
        assert db.session.get(InternalProjectRisk, risk_id).status == "mitigated"


def test_internal_docs_workspace_page(client):
    _login(client)

    response = client.get("/internal/docs")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Workspace Docs" in html
    assert "Delivery Handbook" in html
    assert "Project Brief" in html
    assert "Weekly rhythm" in html


def test_internal_docs_create_page(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/docs")

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        parent_page = InternalDocPage.query.filter_by(slug="delivery-handbook").first()
        assert project is not None
        assert parent_page is not None

    response = client.post(
        "/internal/docs/add",
        data={
            "csrf_token": csrf_token,
            "title": "Steering Meeting Notes",
            "summary": "Notes and decisions from the weekly steering call.",
            "body": "# Steering Meeting Notes\n\n- [x] Reviewed pilot quality\n- [ ] Confirm launch window",
            "status": "published",
            "project_id": str(project.id),
            "parent_id": str(parent_page.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/docs/steering-meeting-notes")

    with client.application.app_context():
        created_page = InternalDocPage.query.filter_by(slug="steering-meeting-notes").first()
        assert created_page is not None
        assert created_page.project_id == project.id
        assert created_page.parent_id == parent_page.id


def test_internal_docs_update_page(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/docs/delivery-handbook")

    with client.application.app_context():
        page = InternalDocPage.query.filter_by(slug="delivery-handbook").first()
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert page is not None
        assert project is not None
        page_id = page.id
        project_id = project.id

    response = client.post(
        f"/internal/docs/{page_id}/update",
        data={
            "csrf_token": csrf_token,
            "title": "Delivery Operating Handbook",
            "summary": "Updated handbook for delivery operating rules.",
            "body": "# Delivery Operating Handbook\n\n## Weekly rhythm\n- [x] Publish the update\n\n> Keep the client team aligned.",
            "status": "published",
            "project_id": str(project_id),
            "parent_id": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/internal/docs/delivery-operating-handbook")

    with client.application.app_context():
        updated_page = db.session.get(InternalDocPage, page_id)
        assert updated_page is not None
        assert updated_page.slug == "delivery-operating-handbook"
        assert updated_page.title == "Delivery Operating Handbook"
        assert "Keep the client team aligned" in updated_page.body


def test_internal_project_starter_plan_template_update_changes_generated_tasks_for_industry(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    custom_template = [
        {
            "title": "Consultation Kickoff",
            "priority": "high",
            "due_percent": 25,
            "subtasks": [
                {"title": "Run discovery workshop", "due_percent": 10},
                {"title": "Confirm target KPI baseline", "due_percent": 20},
            ],
        },
        {
            "title": "Implementation Rollout",
            "priority": "medium",
            "due_percent": 100,
            "subtasks": [
                {"title": "Launch production workflow", "due_percent": 85},
                {"title": "Handover operations checklist", "due_percent": 100},
            ],
        },
    ]

    update_response = client.post(
        "/internal/projects/starter-plan",
        data={
            "csrf_token": csrf_token,
            "starter_plan_category": "legal",
            "starter_plan_template": json.dumps(custom_template),
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 302
    assert update_response.headers["Location"].endswith(
        "/internal/projects?starter_plan_category=legal#starter-plan-template"
    )

    with client.application.app_context():
        template_record = InternalProjectStarterPlan.query.filter_by(name="legal").first()
        assert template_record is not None
        assert "Consultation Kickoff" in template_record.template_json

        client_record = InternalClient.query.filter_by(name="Test Client").first()
        assert client_record is not None
        client_id = client_record.id

    project_response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Custom Starter Plan Project",
            "client_mode": "existing",
            "client_id": str(client_id),
            "owner_id": "self",
            "timeline_days": "30",
            "industry_category": "legal",
            "stage": "discovery",
            "status": "on-track",
            "summary": "Project created with custom starter plan template.",
            "create_starter_plan": "1",
        },
        follow_redirects=False,
    )
    assert project_response.status_code == 302

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="Custom Starter Plan Project").first()
        assert created_project is not None
        task_titles = {task.title for task in created_project.tasks}
        assert "Consultation Kickoff" in task_titles
        assert "Implementation Rollout" in task_titles
        assert "Kickoff and Discovery" not in task_titles
        assert created_project.industry_category == "legal"


def test_internal_project_add_uses_default_industry_starter_plan(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    with client.application.app_context():
        client_record = InternalClient.query.filter_by(name="Test Client").first()
        assert client_record is not None
        client_id = client_record.id

    response = client.post(
        "/internal/projects/add",
        data={
            "csrf_token": csrf_token,
            "name": "Default Finance Plan Project",
            "client_mode": "existing",
            "client_id": str(client_id),
            "owner_id": "self",
            "timeline_days": "30",
            "industry_category": "finance",
            "stage": "discovery",
            "status": "on-track",
            "summary": "Project created using default finance starter template.",
            "create_starter_plan": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_project = InternalProject.query.filter_by(name="Default Finance Plan Project").first()
        assert created_project is not None
        assert created_project.industry_category == "finance"
        task_titles = {task.title for task in created_project.tasks}
        assert "Controls and Requirements Discovery" in task_titles
        assert "Kickoff and Discovery" not in task_titles


def test_internal_project_starter_plan_template_update_rejects_invalid_json(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/projects")

    response = client.post(
        "/internal/projects/starter-plan",
        data={
            "csrf_token": csrf_token,
            "starter_plan_category": "healthcare",
            "starter_plan_template": "{invalid-json}",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/internal/projects?starter_plan_category=healthcare#starter-plan-template"
    )

    with client.application.app_context():
        template_record = InternalProjectStarterPlan.query.filter_by(name="healthcare").first()
        assert template_record is None


def test_internal_messages_project_channel_auto_created(client):
    _login(client)

    response = client.get("/internal/messages")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Consultant Messaging" in html
    assert "Test Internal Project" in html

    with client.application.app_context():
        project = InternalProject.query.filter_by(name="Test Internal Project").first()
        assert project is not None
        assert project.message_channel is not None
        assert project.message_channel.channel_type == "project"


def test_internal_messages_create_direct_channel(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/messages")

    with client.application.app_context():
        current_user = InternalUser.query.filter_by(email="internal-admin@elf-ai.co.za").first()
        recipient_user = InternalUser.query.filter_by(email="delivery-consultant@elf-ai.co.za").first()
        assert current_user is not None
        assert recipient_user is not None
        current_user_id = current_user.id
        recipient_user_id = recipient_user.id

    response = client.post(
        "/internal/messages/direct/start",
        data={
            "csrf_token": csrf_token,
            "recipient_id": str(recipient_user_id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/internal/messages?channel_id=" in response.headers["Location"]

    with client.application.app_context():
        direct_channel = InternalMessageChannel.query.filter_by(channel_type="direct").first()
        assert direct_channel is not None
        member_ids = {member.id for member in direct_channel.members}
        assert member_ids == {current_user_id, recipient_user_id}


def test_internal_messages_create_group_and_post_message(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/messages")

    with client.application.app_context():
        current_user = InternalUser.query.filter_by(email="internal-admin@elf-ai.co.za").first()
        delivery_user = InternalUser.query.filter_by(email="delivery-consultant@elf-ai.co.za").first()
        operations_user = InternalUser.query.filter_by(email="operations-analyst@elf-ai.co.za").first()
        assert current_user is not None
        assert delivery_user is not None
        assert operations_user is not None
        current_user_id = current_user.id
        delivery_user_id = delivery_user.id
        operations_user_id = operations_user.id

    create_group_response = client.post(
        "/internal/messages/group/create",
        data={
            "csrf_token": csrf_token,
            "name": "Delivery Standup",
            "member_ids": [str(delivery_user_id), str(operations_user_id)],
        },
        follow_redirects=False,
    )
    assert create_group_response.status_code == 302
    assert "/internal/messages?channel_id=" in create_group_response.headers["Location"]

    with client.application.app_context():
        group_channel = InternalMessageChannel.query.filter_by(
            channel_type="group",
            name="Delivery Standup",
        ).first()
        assert group_channel is not None
        member_ids = {member.id for member in group_channel.members}
        assert member_ids == {current_user_id, delivery_user_id, operations_user_id}
        group_channel_id = group_channel.id

    post_csrf_token = _csrf_token_for_path(client, f"/internal/messages?channel_id={group_channel_id}")
    post_message_response = client.post(
        "/internal/messages/post",
        data={
            "csrf_token": post_csrf_token,
            "channel_id": str(group_channel_id),
            "body": "Kickoff note: align today on blockers and next milestones.",
        },
        follow_redirects=False,
    )
    assert post_message_response.status_code == 302
    assert post_message_response.headers["Location"].endswith(f"/internal/messages?channel_id={group_channel_id}")

    with client.application.app_context():
        created_message = InternalMessage.query.filter(
            InternalMessage.channel_id == group_channel_id,
            InternalMessage.body.ilike("%Kickoff note%"),
        ).first()
        assert created_message is not None
        assert created_message.sender_id == current_user_id


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
    assert "Filter this queue by task, assignee, project, or linked doc..." in html
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


def test_internal_todo_status_and_priority_updates(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/todos")

    with client.application.app_context():
        task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert task is not None
        task_id = task.id

    status_response = client.post(
        f"/internal/todos/{task_id}/status",
        data={
            "csrf_token": csrf_token,
            "view_mode": "priority",
            "status": "done",
        },
        follow_redirects=False,
    )
    assert status_response.status_code == 302
    assert status_response.headers["Location"].endswith("/internal/todos?view=priority")

    priority_response = client.post(
        f"/internal/todos/{task_id}/priority",
        data={
            "csrf_token": csrf_token,
            "view_mode": "nested",
            "priority": "low",
        },
        follow_redirects=False,
    )
    assert priority_response.status_code == 302
    assert priority_response.headers["Location"].endswith("/internal/todos?view=nested")

    with client.application.app_context():
        updated_task = db.session.get(InternalTask, task_id)
        assert updated_task is not None
        assert updated_task.status == "done"
        assert updated_task.priority == "low"


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


def test_internal_resource_add_with_uploaded_file(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/resources")

    response = client.post(
        "/internal/resources/add",
        data={
            "csrf_token": csrf_token,
            "title": "Uploaded Delivery Checklist",
            "category": "operations",
            "description": "Checklist uploaded directly from the portal",
            "document_file": (io.BytesIO(b"delivery-checklist"), "delivery-checklist.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/internal/resources" in response.headers["Location"]

    with client.application.app_context():
        created_resource = InternalResource.query.filter_by(title="Uploaded Delivery Checklist").first()
        assert created_resource is not None
        assert created_resource.link.startswith("/internal/resources/files/")
        resource_link = created_resource.link

    file_response = client.get(resource_link, follow_redirects=False)
    assert file_response.status_code == 200
    assert file_response.data == b"delivery-checklist"

    anon_client = client.application.test_client()
    unauthorized_response = anon_client.get(resource_link, follow_redirects=False)
    assert unauthorized_response.status_code == 302
    assert "/internal/login" in unauthorized_response.headers["Location"]


def test_internal_resource_add_requires_link_or_uploaded_file(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/resources")

    response = client.post(
        "/internal/resources/add",
        data={
            "csrf_token": csrf_token,
            "title": "Missing Link Or File",
            "category": "operations",
            "description": "Should be rejected when no link or upload is provided",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_resource = InternalResource.query.filter_by(title="Missing Link Or File").first()
        assert created_resource is None


def test_internal_resource_add_rejects_unsupported_uploaded_file_type(client):
    _login(client)
    csrf_token = _csrf_token_for_path(client, "/internal/resources")

    response = client.post(
        "/internal/resources/add",
        data={
            "csrf_token": csrf_token,
            "title": "Unsafe Uploaded File",
            "category": "operations",
            "description": "Upload with unsupported extension should be rejected",
            "document_file": (io.BytesIO(b"binary-content"), "unsafe.exe"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.application.app_context():
        created_resource = InternalResource.query.filter_by(title="Unsafe Uploaded File").first()
        assert created_resource is None


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
        scoped_task = InternalTask.query.filter_by(title="Prepare weekly update").first()
        assert client_record is not None
        assert scoped_project is not None
        assert scoped_task is not None
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
        task_only_resource = InternalResource(
            title="Task Linked Scoped Doc",
            category="operations",
            link="https://example.com/task-linked-scoped-doc",
            description="Resource linked via scoped project task only",
            tasks=[scoped_task],
        )
        db.session.add_all([scoped_resource, other_resource, task_only_resource])
        db.session.commit()

    response = client.get(f"/internal/resources?project_id={scoped_project_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Scoped Project Runbook" in html
    assert "Task Linked Scoped Doc" in html
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
