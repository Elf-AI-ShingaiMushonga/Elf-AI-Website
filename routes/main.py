import hmac
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from flask_mail import Message
from sqlalchemy.orm import selectinload

from extension import mail
from models import (
    Branding,
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

main_bp = Blueprint("main", __name__)

INTERNAL_SITE_REQUIREMENTS = [
    {
        "area": "Access and Security",
        "items": [
            "Role-based access for consultants, operations, and admins.",
            "Strong authentication with hashed passwords and session control.",
            "Audit visibility for user activity and account status.",
        ],
    },
    {
        "area": "Project Delivery Operations",
        "items": [
            "Shared dashboard for project health, open tasks, and delivery status.",
            "Client and project registry with ownership and stage tracking.",
            "Task-level visibility for priorities, due dates, and assignees.",
        ],
    },
    {
        "area": "Knowledge and Reuse",
        "items": [
            "Central resource library for templates, playbooks, and compliance checklists.",
            "Standardized project lifecycle requirements to reduce delivery variance.",
            "Internal announcements for process updates and operational notices.",
        ],
    },
    {
        "area": "Governance and Quality",
        "items": [
            "Clear pre-deployment quality and security controls.",
            "Standard reporting expectations for scope, outcomes, and ROI.",
            "Consistent operational cadence across engagements.",
        ],
    },
]

INTERNAL_TASK_PRIORITIES = ("high", "medium", "low")
INTERNAL_TASK_STATUSES = ("todo", "in-progress", "blocked", "done")
INTERNAL_TASK_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
INTERNAL_TASK_STATUS_RANK = {"todo": 0, "in-progress": 1, "blocked": 2, "done": 3}
INTERNAL_PROJECT_STAGES = ("discovery", "build", "delivery", "operations")
INTERNAL_PROJECT_STATUSES = ("on-track", "at-risk", "blocked", "completed")
INTERNAL_RESOURCE_STATES = ("all", "linked", "unlinked", "untagged")
RESOURCE_CATEGORY_FALLBACK = "general"
CSRF_TOKEN_SESSION_KEY = "_internal_csrf_token"
SAFE_RESOURCE_LINK_SCHEMES = {"http", "https"}


def _site_url() -> str:
    configured_site_url = (current_app.config.get("SITE_URL") or "").strip().rstrip("/")
    if configured_site_url:
        return configured_site_url
    return request.url_root.rstrip("/")


def _build_seo(path: str, title: str, description: str, image_filename: str = "images/hero1.png") -> dict:
    site_url = _site_url()
    canonical_path = path if path.startswith("/") else f"/{path}"
    canonical = f"{site_url}{canonical_path}"
    og_image = f"{site_url}{url_for('static', filename=image_filename)}"

    structured_data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{site_url}/#organization",
                "name": "ELF-AI",
                "alternateName": "ELF-AI",
                "url": site_url,
                "logo": f"{site_url}{url_for('static', filename='images/Logo.png')}",
                "email": "shingai.mushonga@elf-ai.co.za",
                "description": (
                    "ELF-AI is a problem-solving AI consultancy that designs, implements, "
                    "and trains teams on practical AI solutions."
                ),
            },
            {
                "@type": "WebSite",
                "@id": f"{site_url}/#website",
                "url": site_url,
                "name": "ELF-AI",
                "publisher": {"@id": f"{site_url}/#organization"},
            },
            {
                "@type": "WebPage",
                "@id": f"{canonical}#webpage",
                "url": canonical,
                "name": title,
                "description": description,
                "isPartOf": {"@id": f"{site_url}/#website"},
                "about": {"@id": f"{site_url}/#organization"},
            },
        ],
    }

    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_image": og_image,
        "site_name": "ELF-AI",
        "keywords": (
            "ELF-AI, AI consultancy, AI solutions, AI automation, "
            "business process automation, SME AI consulting"
        ),
        "structured_data": structured_data,
    }


def _render_page(template_name: str, *, path: str, title: str, description: str, **context):
    seo = _build_seo(path=path, title=title, description=description)
    return render_template(template_name, seo=seo, **context)


def _safe_next_url(next_target: str | None) -> str | None:
    if next_target and next_target.startswith("/"):
        return next_target
    return None


def _internal_status_class(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"on-track", "active", "done", "completed"}:
        return "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
    if normalized in {"at-risk", "blocked", "todo"}:
        return "bg-amber-500/20 text-amber-300 border border-amber-500/30"
    if normalized in {"critical", "delayed"}:
        return "bg-rose-500/20 text-rose-300 border border-rose-500/30"
    return "bg-slate-500/20 text-slate-300 border border-slate-500/30"


def _internal_priority_class(priority: str | None) -> str:
    normalized = (priority or "").strip().lower()
    if normalized == "high":
        return "text-rose-300"
    if normalized == "medium":
        return "text-amber-300"
    return "text-blue-300"


def _normalize_internal_task_priority(raw_value: str | None) -> str:
    normalized = (raw_value or "medium").strip().lower()
    return normalized if normalized in INTERNAL_TASK_PRIORITIES else "medium"


def _normalize_internal_task_status(raw_value: str | None) -> str:
    normalized = (raw_value or "todo").strip().lower()
    return normalized if normalized in INTERNAL_TASK_STATUSES else "todo"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _task_sort_key(task: InternalTask):
    priority_rank = INTERNAL_TASK_PRIORITY_RANK.get((task.priority or "").strip().lower(), 3)
    status_rank = INTERNAL_TASK_STATUS_RANK.get((task.status or "").strip().lower(), 4)
    return (
        status_rank,
        priority_rank,
        task.due_date or date.max,
        task.created_at or datetime.min.replace(tzinfo=timezone.utc),
        task.id or 0,
    )


def _normalize_internal_project_stage(raw_value: str | None) -> str:
    normalized = (raw_value or "discovery").strip().lower()
    return normalized if normalized in INTERNAL_PROJECT_STAGES else "discovery"


def _normalize_internal_project_status(raw_value: str | None) -> str:
    normalized = (raw_value or "on-track").strip().lower()
    return normalized if normalized in INTERNAL_PROJECT_STATUSES else "on-track"


def _normalize_resource_category(raw_value: str | None) -> str:
    normalized = " ".join((raw_value or RESOURCE_CATEGORY_FALLBACK).strip().split()).lower()
    return normalized or RESOURCE_CATEGORY_FALLBACK


def _category_label(raw_value: str | None) -> str:
    normalized = _normalize_resource_category(raw_value)
    return normalized.replace("-", " ").title()


def _normalize_resource_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[,\n;]+", raw_value):
        normalized = " ".join(chunk.strip().lower().lstrip("#").split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_tags.append(normalized)
    return normalized_tags


def _parse_int_list(raw_values: list[str]) -> list[int]:
    parsed_ids: list[int] = []
    seen: set[int] = set()
    for raw_value in raw_values:
        try:
            parsed_id = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed_id <= 0 or parsed_id in seen:
            continue
        seen.add(parsed_id)
        parsed_ids.append(parsed_id)
    return parsed_ids


def _is_safe_resource_link(raw_value: str | None) -> bool:
    if not raw_value:
        return False
    candidate = raw_value.strip()
    if not candidate:
        return False
    if candidate.startswith("/"):
        return True

    parsed = urlparse(candidate)
    return parsed.scheme.lower() in SAFE_RESOURCE_LINK_SCHEMES and bool(parsed.netloc)


def _internal_csrf_token() -> str:
    token = session.get(CSRF_TOKEN_SESSION_KEY)
    if token:
        return token
    token = secrets.token_urlsafe(32)
    session[CSRF_TOKEN_SESSION_KEY] = token
    return token


def _is_valid_internal_csrf_token(raw_value: str | None) -> bool:
    token = session.get(CSRF_TOKEN_SESSION_KEY)
    if not token or not raw_value:
        return False
    return hmac.compare_digest(token, raw_value)


@main_bp.before_app_request
def load_internal_user() -> None:
    user_id = session.get("internal_user_id")
    if not user_id:
        g.internal_user = None
        return

    user = db.session.get(InternalUser, user_id)
    if not user or not user.is_active:
        session.pop("internal_user_id", None)
        g.internal_user = None
        return

    g.internal_user = user


@main_bp.before_app_request
def verify_internal_csrf() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if not request.path.startswith("/internal/"):
        return

    submitted = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if _is_valid_internal_csrf_token(submitted):
        return

    current_app.logger.warning("Blocked internal CSRF validation for path=%s", request.path)
    return current_app.response_class("CSRF token missing or invalid.", status=400, mimetype="text/plain")


@main_bp.app_context_processor
def inject_internal_user_context():
    return {
        "current_internal_user": getattr(g, "internal_user", None),
        "internal_status_class": _internal_status_class,
        "internal_priority_class": _internal_priority_class,
        "csrf_token": _internal_csrf_token,
    }


def internal_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not getattr(g, "internal_user", None):
            next_target = _safe_next_url(request.path)
            return redirect(url_for("main.internal_login", next=next_target))
        return view_func(*args, **kwargs)

    return wrapped


@main_bp.route("/")
def home():
    services = Service.query.all()
    branding = Branding.query.first()
    carousel_images = ["hero1.png"]
    return _render_page(
        "index.html",
        path="/",
        title="ELF-AI | Problem-Solving AI Consultancy for SMEs",
        description=(
            "ELF-AI helps businesses solve operational problems with practical AI "
            "solutions, deployment support, and in-house team training."
        ),
        services=services,
        branding=branding,
        carousel_images=carousel_images,
    )


@main_bp.route("/solutions")
def solutions():
    services = Service.query.all()
    solution = Page_Heading.query.filter_by(Title="solutions").first()
    return _render_page(
        "solutions.html",
        path="/solutions",
        title="AI Solutions | ELF-AI",
        description=(
            "Explore ELF-AI solution tracks for workflow automation, faster delivery, lower costs, "
            "and measurable ROI for your business."
        ),
        services=services,
        solution=solution,
    )


@main_bp.route("/about")
def about():
    about_us = Page_Heading.query.filter_by(Title="about_us").first()
    about_us_slide = Slide.query.filter_by(owner="about_us").all()
    about_us_slide_mini = Slide.query.filter_by(owner="about_us_mini").all()
    picture = "hero2.png"
    return _render_page(
        "about.html",
        path="/about",
        title="About ELF-AI | AI Problem-Solving Consultancy",
        description=(
            "Learn how ELF-AI combines delivery, training, and operational support to build "
            "long-term AI capability inside your team."
        ),
        about_us=about_us,
        about_us_slide=about_us_slide,
        about_us_slide_mini=about_us_slide_mini,
        picture=picture,
    )


@main_bp.route("/enquire")
def enquire():
    enquiry = Page_Heading.query.filter_by(Title="enquiry").first()
    services = Service.query.all()
    return _render_page(
        "enquire.html",
        path="/enquire",
        title="Contact ELF-AI | Start Your AI Consultation",
        description=(
            "Contact ELF-AI to discuss your business challenge and get a scoped plan for a "
            "practical, testable AI solution."
        ),
        enquiry=enquiry,
        services=services,
    )


@main_bp.route("/internal/login", methods=["GET", "POST"])
def internal_login():
    if getattr(g, "internal_user", None):
        return redirect(url_for("main.internal_dashboard"))

    next_target = _safe_next_url(request.args.get("next") or request.form.get("next"))
    has_users = InternalUser.query.count() > 0

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = InternalUser.query.filter_by(email=email).first()
        if not user or not user.is_active or not user.check_password(password):
            flash("Invalid email or password.", "warning")
        else:
            session.clear()
            session["internal_user_id"] = user.id
            session[CSRF_TOKEN_SESSION_KEY] = secrets.token_urlsafe(32)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            flash(f"Welcome back, {user.full_name}.", "success")
            return redirect(next_target or url_for("main.internal_dashboard"))

    return render_template(
        "internal/login.html",
        has_users=has_users,
        next_target=next_target or "",
    )


@main_bp.route("/internal/logout", methods=["POST"])
@internal_login_required
def internal_logout():
    session.pop("internal_user_id", None)
    session.pop(CSRF_TOKEN_SESSION_KEY, None)
    flash("You have been signed out.", "success")
    return redirect(url_for("main.internal_login"))


@main_bp.route("/internal")
@main_bp.route("/internal/dashboard")
@internal_login_required
def internal_dashboard():
    open_tasks = InternalTask.query.filter(InternalTask.status != "done").count()
    clients_count = InternalClient.query.count()
    active_projects = InternalProject.query.filter(InternalProject.status != "completed").count()
    blocked_tasks = InternalTask.query.filter(InternalTask.status == "blocked").count()
    today = date.today()
    due_soon_cutoff = today + timedelta(days=7)
    due_soon_tasks = InternalTask.query.filter(
        InternalTask.status != "done",
        InternalTask.due_date.isnot(None),
        InternalTask.due_date >= today,
        InternalTask.due_date <= due_soon_cutoff,
    ).count()
    overdue_tasks = InternalTask.query.filter(
        InternalTask.status != "done",
        InternalTask.due_date.isnot(None),
        InternalTask.due_date < today,
    ).count()

    upcoming_tasks = (
        InternalTask.query.filter(InternalTask.status != "done")
        .order_by(InternalTask.due_date.is_(None), InternalTask.due_date.asc(), InternalTask.created_at.desc())
        .limit(8)
        .all()
    )
    recent_projects = InternalProject.query.order_by(InternalProject.created_at.desc()).limit(6).all()
    announcements = InternalAnnouncement.query.order_by(InternalAnnouncement.created_at.desc()).limit(4).all()
    total_resources = InternalResource.query.count()
    resources_without_tags = InternalResource.query.filter(~InternalResource.tags.any()).count()
    resources_without_links = InternalResource.query.filter(
        ~InternalResource.projects.any(),
        ~InternalResource.tasks.any(),
    ).count()
    resources_linked = total_resources - resources_without_links
    journey_steps = [
        {
            "title": "Capture Lead Context",
            "body": "Use enquiry notes and meeting outcomes to define the first delivery objective.",
            "href": url_for("main.enquire"),
            "label": "View Enquiry Page",
        },
        {
            "title": "Create Client + Project",
            "body": "Register the client and spin up a scoped project with clear owner, stage, and due date.",
            "href": url_for("main.internal_clients"),
            "label": "Open Client Registry",
        },
        {
            "title": "Plan Execution",
            "body": "Break work into nested tasks and order the priority queue before kickoff.",
            "href": url_for("main.internal_todos", view="priority"),
            "label": "Open To-Do Queue",
        },
        {
            "title": "Link Knowledge",
            "body": "Attach playbooks and SOPs to project and task records for fast team reuse.",
            "href": url_for("main.internal_resources"),
            "label": "Open Knowledge Library",
        },
    ]

    return render_template(
        "internal/dashboard.html",
        stats={
            "clients": clients_count,
            "active_projects": active_projects,
            "open_tasks": open_tasks,
            "blocked": blocked_tasks,
            "due_soon": due_soon_tasks,
            "overdue": overdue_tasks,
            "requirements": sum(len(item["items"]) for item in INTERNAL_SITE_REQUIREMENTS),
            "resources": total_resources,
        },
        knowledge_stats={
            "total": total_resources,
            "linked": resources_linked,
            "without_links": resources_without_links,
            "without_tags": resources_without_tags,
        },
        upcoming_tasks=upcoming_tasks,
        recent_projects=recent_projects,
        announcements=announcements,
        due_soon_cutoff=due_soon_cutoff,
        journey_steps=journey_steps,
    )


@main_bp.route("/internal/clients")
@internal_login_required
def internal_clients():
    clients = InternalClient.query.order_by(InternalClient.status.asc(), InternalClient.name.asc()).all()
    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )
    client_statuses = ("active", "at-risk", "paused", "completed")
    return render_template(
        "internal/clients.html",
        clients=clients,
        active_internal_users=active_internal_users,
        client_statuses=client_statuses,
    )


@main_bp.route("/internal/clients/add", methods=["POST"])
@internal_login_required
def internal_client_add():
    name = " ".join((request.form.get("name") or "").strip().split())
    industry = " ".join((request.form.get("industry") or "").strip().split())
    account_owner = " ".join((request.form.get("account_owner") or "").strip().split())
    status = (request.form.get("status") or "active").strip().lower()
    notes = (request.form.get("notes") or "").strip()
    if status not in {"active", "at-risk", "paused", "completed"}:
        status = "active"

    if not name or not industry or not account_owner:
        flash("Client name, industry, and account owner are required.", "warning")
        return redirect(url_for("main.internal_clients"))

    existing_client = InternalClient.query.filter(InternalClient.name.ilike(name)).first()
    if existing_client:
        flash("A client with this name already exists.", "warning")
        return redirect(url_for("main.internal_clients"))

    client_record = InternalClient(
        name=name,
        industry=industry,
        account_owner=account_owner,
        status=status,
        notes=notes or None,
    )
    db.session.add(client_record)
    db.session.commit()
    flash(f"Client '{name}' added.", "success")
    return redirect(url_for("main.internal_clients"))


@main_bp.route("/internal/projects")
@internal_login_required
def internal_projects():
    selected_client_id: int | None = None
    selected_client_raw = (request.args.get("client_id") or "").strip()
    if selected_client_raw:
        try:
            selected_client_candidate = int(selected_client_raw)
        except ValueError:
            selected_client_candidate = None
        if selected_client_candidate and db.session.get(InternalClient, selected_client_candidate):
            selected_client_id = selected_client_candidate

    projects = (
        InternalProject.query.options(selectinload(InternalProject.resources))
        .order_by(InternalProject.status.asc(), InternalProject.name.asc())
        .all()
    )
    project_cards = []
    for project in projects:
        total_tasks = len(project.tasks)
        completed_tasks = sum(1 for task in project.tasks if (task.status or "").lower() == "done")
        progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0
        project_cards.append(
            {
                "project": project,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress": progress,
            }
        )

    clients = InternalClient.query.order_by(InternalClient.name.asc()).all()
    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )
    return render_template(
        "internal/projects.html",
        project_cards=project_cards,
        clients=clients,
        active_internal_users=active_internal_users,
        project_stages=INTERNAL_PROJECT_STAGES,
        project_statuses=INTERNAL_PROJECT_STATUSES,
        selected_client_id=selected_client_id,
    )


@main_bp.route("/internal/projects/add", methods=["POST"])
@internal_login_required
def internal_project_add():
    name = " ".join((request.form.get("name") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    stage = _normalize_internal_project_stage(request.form.get("stage"))
    status = _normalize_internal_project_status(request.form.get("status"))
    due_date = _parse_date(request.form.get("due_date"))

    client_id_raw = (request.form.get("client_id") or "").strip()
    owner_id_raw = (request.form.get("owner_id") or "").strip()

    if not name or not summary:
        flash("Project name and summary are required.", "warning")
        return redirect(url_for("main.internal_projects"))

    try:
        client_id = int(client_id_raw)
    except ValueError:
        flash("Select a valid client for the project.", "warning")
        return redirect(url_for("main.internal_projects"))
    client_record = db.session.get(InternalClient, client_id)
    if not client_record:
        flash("Selected client does not exist.", "warning")
        return redirect(url_for("main.internal_projects"))

    owner_record = None
    if owner_id_raw:
        try:
            owner_id = int(owner_id_raw)
        except ValueError:
            flash("Invalid project owner.", "warning")
            return redirect(url_for("main.internal_projects", client_id=client_id))
        owner_record = db.session.get(InternalUser, owner_id)
        if not owner_record or not owner_record.is_active:
            flash("Selected project owner is not available.", "warning")
            return redirect(url_for("main.internal_projects", client_id=client_id))

    project_record = InternalProject(
        name=name,
        client=client_record,
        owner=owner_record,
        stage=stage,
        status=status,
        due_date=due_date,
        summary=summary,
    )
    db.session.add(project_record)
    db.session.commit()
    flash(f"Project '{name}' created for {client_record.name}.", "success")
    return redirect(url_for("main.internal_projects", client_id=client_record.id))


@main_bp.route("/internal/todos")
@internal_login_required
def internal_todos():
    view_mode = (request.args.get("view") or "nested").strip().lower()
    if view_mode not in {"nested", "priority"}:
        view_mode = "nested"
    selected_project_id: int | None = None
    selected_project_raw = (request.args.get("project_id") or "").strip()
    if selected_project_raw:
        try:
            selected_project_candidate = int(selected_project_raw)
        except ValueError:
            selected_project_candidate = None
        if selected_project_candidate and db.session.get(InternalProject, selected_project_candidate):
            selected_project_id = selected_project_candidate

    projects = (
        InternalProject.query.options(selectinload(InternalProject.resources))
        .order_by(InternalProject.name.asc())
        .all()
    )
    tasks = (
        InternalTask.query.options(
            selectinload(InternalTask.project),
            selectinload(InternalTask.subtasks),
            selectinload(InternalTask.resources),
        )
        .order_by(InternalTask.created_at.asc())
        .all()
    )

    if selected_project_id:
        top_level_tasks_by_project: dict[int, list[InternalTask]] = {selected_project_id: []}
    else:
        top_level_tasks_by_project = {project.id: [] for project in projects}
    queue_tasks: list[InternalTask] = []
    parent_task_options: list[InternalTask] = []
    for task in tasks:
        if selected_project_id and task.project_id != selected_project_id:
            continue
        if task.parent_task_id is None:
            top_level_tasks_by_project.setdefault(task.project_id, []).append(task)
        if not task.is_done:
            queue_tasks.append(task)
            parent_task_options.append(task)

    for project_id, task_list in top_level_tasks_by_project.items():
        top_level_tasks_by_project[project_id] = sorted(task_list, key=_task_sort_key)

    queue_tasks = sorted(
        queue_tasks,
        key=lambda task: (
            INTERNAL_TASK_PRIORITY_RANK.get((task.priority or "").strip().lower(), 3),
            task.due_date or date.max,
            INTERNAL_TASK_STATUS_RANK.get((task.status or "").strip().lower(), 4),
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )

    queue_counts = {
        "high": sum(1 for task in queue_tasks if (task.priority or "").strip().lower() == "high"),
        "medium": sum(1 for task in queue_tasks if (task.priority or "").strip().lower() == "medium"),
        "low": sum(1 for task in queue_tasks if (task.priority or "").strip().lower() == "low"),
    }
    today = date.today()
    due_soon_cutoff = today + timedelta(days=7)
    task_stats = {
        "open": len(queue_tasks),
        "blocked": sum(1 for task in queue_tasks if (task.status or "").strip().lower() == "blocked"),
        "due_soon": sum(
            1 for task in queue_tasks if task.due_date is not None and today <= task.due_date <= due_soon_cutoff
        ),
        "overdue": sum(1 for task in queue_tasks if task.due_date is not None and task.due_date < today),
    }
    visible_projects = [project for project in projects if not selected_project_id or project.id == selected_project_id]

    return render_template(
        "internal/todos.html",
        view_mode=view_mode,
        projects=projects,
        visible_projects=visible_projects,
        selected_project_id=selected_project_id,
        top_level_tasks_by_project=top_level_tasks_by_project,
        queue_tasks=queue_tasks,
        queue_counts=queue_counts,
        task_stats=task_stats,
        due_soon_cutoff=due_soon_cutoff,
        parent_task_options=sorted(parent_task_options, key=_task_sort_key),
        task_statuses=INTERNAL_TASK_STATUSES,
        task_priorities=INTERNAL_TASK_PRIORITIES,
    )


@main_bp.route("/internal/todos/add", methods=["POST"])
@internal_login_required
def internal_todo_add():
    view_mode = (request.form.get("view_mode") or "nested").strip().lower()
    project_scope = (request.form.get("project_scope") or "").strip()
    redirect_kwargs = {"view": view_mode}
    try:
        project_scope_id = int(project_scope) if project_scope else None
    except ValueError:
        project_scope_id = None
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id
    redirect_target = url_for("main.internal_todos", **redirect_kwargs)

    title = (request.form.get("title") or "").strip()
    assignee = (request.form.get("assignee") or "").strip()
    project_id = request.form.get("project_id")
    parent_task_id = request.form.get("parent_task_id")
    priority = _normalize_internal_task_priority(request.form.get("priority"))
    status = _normalize_internal_task_status(request.form.get("status"))
    due_date = _parse_date(request.form.get("due_date"))

    if not title:
        flash("Task title is required.", "warning")
        return redirect(redirect_target)

    if not assignee:
        flash("Task assignee is required.", "warning")
        return redirect(redirect_target)

    try:
        project_pk = int(project_id or "")
    except ValueError:
        flash("Choose a valid project for the task.", "warning")
        return redirect(redirect_target)

    project = db.session.get(InternalProject, project_pk)
    if not project:
        flash("Selected project does not exist.", "warning")
        return redirect(redirect_target)

    parent_task = None
    if parent_task_id:
        try:
            parent_pk = int(parent_task_id)
        except ValueError:
            flash("Invalid parent task.", "warning")
            return redirect(redirect_target)

        parent_task = db.session.get(InternalTask, parent_pk)
        if not parent_task:
            flash("Parent task not found.", "warning")
            return redirect(redirect_target)
        if parent_task.project_id != project.id:
            flash("Parent task must belong to the same project.", "warning")
            return redirect(redirect_target)

    task = InternalTask(
        project=project,
        parent_task=parent_task,
        title=title,
        assignee=assignee,
        priority=priority,
        status=status,
        due_date=due_date,
    )
    db.session.add(task)
    db.session.commit()
    flash("Task added to the internal to-do list.", "success")
    return redirect(redirect_target)


@main_bp.route("/internal/todos/<int:task_id>/status", methods=["POST"])
@internal_login_required
def internal_todo_update_status(task_id: int):
    view_mode = (request.form.get("view_mode") or "nested").strip().lower()
    project_scope = (request.form.get("project_scope") or "").strip()
    redirect_kwargs = {"view": view_mode}
    try:
        project_scope_id = int(project_scope) if project_scope else None
    except ValueError:
        project_scope_id = None
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id
    task = db.session.get(InternalTask, task_id)
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.internal_todos", **redirect_kwargs))

    task.status = _normalize_internal_task_status(request.form.get("status"))
    db.session.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("main.internal_todos", **redirect_kwargs))


@main_bp.route("/internal/todos/<int:task_id>/priority", methods=["POST"])
@internal_login_required
def internal_todo_update_priority(task_id: int):
    view_mode = (request.form.get("view_mode") or "nested").strip().lower()
    project_scope = (request.form.get("project_scope") or "").strip()
    redirect_kwargs = {"view": view_mode}
    try:
        project_scope_id = int(project_scope) if project_scope else None
    except ValueError:
        project_scope_id = None
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id
    task = db.session.get(InternalTask, task_id)
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.internal_todos", **redirect_kwargs))

    task.priority = _normalize_internal_task_priority(request.form.get("priority"))
    db.session.commit()
    flash("Task priority updated.", "success")
    return redirect(url_for("main.internal_todos", **redirect_kwargs))


@main_bp.route("/internal/resources")
@internal_login_required
def internal_resources():
    query_term = (request.args.get("q") or "").strip()
    query_term_lower = query_term.lower()
    selected_category = (request.args.get("category") or "all").strip().lower()
    selected_tag = (request.args.get("tag") or "all").strip().lower()
    selected_state = (request.args.get("state") or "all").strip().lower()
    selected_project_filter: int | str = "all"
    selected_project_raw = (request.args.get("project_id") or "all").strip()

    resources = (
        InternalResource.query.options(
            selectinload(InternalResource.projects),
            selectinload(InternalResource.tasks).selectinload(InternalTask.project),
            selectinload(InternalResource.tags),
        )
        .order_by(InternalResource.category.asc(), InternalResource.title.asc())
        .all()
    )
    announcements = InternalAnnouncement.query.order_by(InternalAnnouncement.created_at.desc()).all()
    projects = InternalProject.query.order_by(InternalProject.name.asc()).all()
    project_options = [{"value": "all", "label": "All projects"}] + [
        {"value": str(project.id), "label": project.name} for project in projects
    ]
    if selected_project_raw != "all":
        try:
            selected_project_candidate = int(selected_project_raw)
        except ValueError:
            selected_project_candidate = None
        valid_project_ids = {project.id for project in projects}
        if selected_project_candidate in valid_project_ids:
            selected_project_filter = selected_project_candidate

    all_categories = sorted({_normalize_resource_category(resource.category) for resource in resources})
    all_tags = sorted({tag.name for resource in resources for tag in resource.tags})

    if selected_category != "all":
        selected_category = _normalize_resource_category(selected_category)
        if selected_category not in all_categories:
            selected_category = "all"

    if selected_tag != "all" and selected_tag not in all_tags:
        selected_tag = "all"
    if selected_state not in INTERNAL_RESOURCE_STATES:
        selected_state = "all"

    filtered_resources: list[InternalResource] = []
    for resource in resources:
        category_value = _normalize_resource_category(resource.category)
        tag_values = {tag.name for tag in resource.tags}
        is_linked = bool(resource.projects or resource.tasks)
        has_tags = bool(resource.tags)
        if selected_category != "all" and category_value != selected_category:
            continue
        if selected_tag != "all" and selected_tag not in tag_values:
            continue
        if selected_state == "linked" and not is_linked:
            continue
        if selected_state == "unlinked" and is_linked:
            continue
        if selected_state == "untagged" and has_tags:
            continue
        if selected_project_filter != "all" and selected_project_filter not in {project.id for project in resource.projects}:
            continue
        if query_term_lower and query_term_lower not in resource.searchable_text:
            continue
        filtered_resources.append(resource)

    resources_by_category_unsorted: dict[str, list[InternalResource]] = {}
    for resource in filtered_resources:
        category_key = _category_label(resource.category)
        resources_by_category_unsorted.setdefault(category_key, []).append(resource)

    resources_by_category: dict[str, list[InternalResource]] = {}
    for category_key in sorted(resources_by_category_unsorted.keys()):
        resources_by_category[category_key] = sorted(
            resources_by_category_unsorted[category_key], key=lambda resource: resource.title.lower()
        )

    project_ids_linked = {project.id for resource in resources for project in resource.projects}
    task_ids_linked = {task.id for resource in resources for task in resource.tasks}

    tasks = (
        InternalTask.query.options(selectinload(InternalTask.project))
        .order_by(InternalTask.project_id.asc(), InternalTask.title.asc())
        .all()
    )

    category_options = [{"value": category, "label": _category_label(category)} for category in all_categories]
    tag_options = [{"value": tag, "label": tag} for tag in all_tags]
    state_options = [
        {"value": "all", "label": "All document states"},
        {"value": "linked", "label": "Linked only"},
        {"value": "unlinked", "label": "Unlinked only"},
        {"value": "untagged", "label": "Missing tags"},
    ]
    state_labels = {option["value"]: option["label"] for option in state_options}
    unlinked_docs = sum(1 for resource in resources if not resource.projects and not resource.tasks)
    untagged_docs = sum(1 for resource in resources if not resource.tags)
    linked_docs = len(resources) - unlinked_docs

    summary_metrics = {
        "total_docs": len(resources),
        "visible_docs": len(filtered_resources),
        "categories": len(all_categories),
        "tags": len(all_tags),
        "linked_projects": len(project_ids_linked),
        "linked_tasks": len(task_ids_linked),
        "linked_docs": linked_docs,
        "unlinked_docs": unlinked_docs,
        "untagged_docs": untagged_docs,
    }

    return render_template(
        "internal/resources.html",
        resources_by_category=resources_by_category,
        resource_total=len(filtered_resources),
        resources_total_unfiltered=len(resources),
        resource_categories=category_options,
        resource_tags=tag_options,
        selected_category=selected_category,
        selected_tag=selected_tag,
        project_filter_options=project_options,
        selected_project_filter=str(selected_project_filter),
        resource_states=state_options,
        selected_state=selected_state,
        selected_state_label=state_labels.get(selected_state, "All document states"),
        query_term=query_term,
        requirements=INTERNAL_SITE_REQUIREMENTS,
        announcements=announcements,
        summary_metrics=summary_metrics,
        projects=projects,
        tasks=tasks,
    )


@main_bp.route("/internal/resources/add", methods=["POST"])
@internal_login_required
def internal_resource_add():
    title = (request.form.get("title") or "").strip()
    link = (request.form.get("link") or "").strip()
    description = (request.form.get("description") or "").strip()
    category = _normalize_resource_category(request.form.get("category"))
    tag_names = _normalize_resource_tags(request.form.get("tags"))
    project_ids = _parse_int_list(request.form.getlist("project_ids"))
    task_ids = _parse_int_list(request.form.getlist("task_ids"))
    project_scope = (request.form.get("project_scope") or "").strip()

    if not title or not link or not description:
        flash("Title, link, and description are required to add a resource.", "warning")
        return redirect(url_for("main.internal_resources"))
    if not _is_safe_resource_link(link):
        flash("Resource link must be a relative path or an http/https URL.", "warning")
        return redirect(url_for("main.internal_resources"))

    projects: list[InternalProject] = []
    tasks: list[InternalTask] = []
    if project_ids:
        projects = InternalProject.query.filter(InternalProject.id.in_(project_ids)).all()
        if len(projects) != len(project_ids):
            flash("One or more selected projects are invalid.", "warning")
            return redirect(url_for("main.internal_resources"))
    if task_ids:
        tasks = InternalTask.query.filter(InternalTask.id.in_(task_ids)).all()
        if len(tasks) != len(task_ids):
            flash("One or more selected tasks are invalid.", "warning")
            return redirect(url_for("main.internal_resources"))

    existing_tags = (
        InternalResourceTag.query.filter(InternalResourceTag.name.in_(tag_names)).all() if tag_names else []
    )
    existing_tags_by_name = {tag.name: tag for tag in existing_tags}
    resource_tags: list[InternalResourceTag] = []
    for tag_name in tag_names:
        tag = existing_tags_by_name.get(tag_name)
        if not tag:
            tag = InternalResourceTag(name=tag_name)
            db.session.add(tag)
            existing_tags_by_name[tag_name] = tag
        resource_tags.append(tag)

    resource = InternalResource(
        title=title,
        link=link,
        category=category,
        description=description,
        projects=projects,
        tasks=tasks,
        tags=resource_tags,
    )
    db.session.add(resource)
    db.session.commit()
    flash("Resource added to the knowledge library.", "success")
    redirect_kwargs = {"q": title}
    try:
        project_scope_id = int(project_scope) if project_scope else None
    except ValueError:
        project_scope_id = None
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id
    return redirect(url_for("main.internal_resources", **redirect_kwargs))


@main_bp.route("/robots.txt")
def robots_txt():
    site_url = _site_url()
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {site_url}/sitemap.xml",
    ]
    response = current_app.response_class("\n".join(lines), mimetype="text/plain")
    return response


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    site_url = _site_url()
    lastmod = datetime.now(timezone.utc).date().isoformat()
    pages = [
        {"loc": f"{site_url}{url_for('main.home')}", "changefreq": "weekly", "priority": "1.0", "lastmod": lastmod},
        {
            "loc": f"{site_url}{url_for('main.solutions')}",
            "changefreq": "weekly",
            "priority": "0.9",
            "lastmod": lastmod,
        },
        {"loc": f"{site_url}{url_for('main.about')}", "changefreq": "monthly", "priority": "0.8", "lastmod": lastmod},
        {
            "loc": f"{site_url}{url_for('main.enquire')}",
            "changefreq": "weekly",
            "priority": "0.9",
            "lastmod": lastmod,
        },
    ]
    xml = render_template("sitemap.xml", pages=pages)
    response = current_app.response_class(xml, mimetype="application/xml")
    return response


@main_bp.route("/contact", methods=["POST"])
def contact():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    role = (request.form.get("role") or "").strip()
    company = (request.form.get("company") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    timeline = (request.form.get("timeline") or "").strip()
    message_body = (request.form.get("message") or "").strip()
    honeypot = (request.form.get("website") or "").strip()
    if honeypot:
        flash("Thank you. Your enquiry has been received.", "success")
        return redirect(url_for("main.home", _anchor="contact"))

    service_id = request.form.get("service")

    if service_id and service_id != "0":
        try:
            service_pk = int(service_id)
        except ValueError:
            service_pk = None
        interested_service = db.session.get(Service, service_pk) if service_pk else None
        service_name = interested_service.title if interested_service else "General Inquiry"
    else:
        service_name = "General Inquiry"
    msg = Message(
        subject=f"New Lead: {name}",
        recipients=["shingai.mushonga@elf-ai.co.za"],  # Or use app.config['MAIL_USERNAME']
    )

    # This creates the email body
    msg.body = f"""
        Name: {name}
        Email: {email}
        Role: {role or "Not provided"}
        Company: {company or "Not provided"}
        Phone: {phone or "Not provided"}
        Preferred Timeline: {timeline or "Not provided"}
        Service Interest: {service_name}

        Message:
        {message_body or "Not provided"}
    """
    if email and ("\n" not in email and "\r" not in email):
        msg.reply_to = email
    try:
        mail.send(msg)  # <--- This actually sends it!
        flash(f"Thank you, {name or 'there'}. We will contact you regarding '{service_name}'.", "success")
    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        flash("Message saved, but we couldn't send the email confirmation.", "warning")
    return redirect(url_for("main.home", _anchor="contact"))


@main_bp.route("/healthz")
def healthz():
    return {"status": "ok"}, 200
