import copy
import hmac
import json
import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_mail import Message
from markupsafe import Markup, escape
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from extension import mail
from models import (
    Branding,
    InternalAnnouncement,
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
            "Role-based access for admins, consultants, and operations.",
            "Strong authentication with hashed passwords and session controls.",
            "Clear visibility of account status and activity.",
        ],
    },
    {
        "area": "Project Delivery Operations",
        "items": [
            "Shared dashboard for project health and open work.",
            "Client and project registry with owner and stage tracking.",
            "Task visibility for priority, due dates, and assignees.",
        ],
    },
    {
        "area": "Knowledge and Reuse",
        "items": [
            "Central library for playbooks, templates, and checklists.",
            "Standard lifecycle requirements to reduce delivery variance.",
            "Internal announcements for process updates.",
        ],
    },
    {
        "area": "Governance and Quality",
        "items": [
            "Defined pre-deployment quality and security checks.",
            "Standard reporting for scope, outcomes, and ROI.",
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
INTERNAL_MILESTONE_STATUSES = ("planned", "in-progress", "at-risk", "done")
INTERNAL_DELIVERABLE_STATUSES = ("planned", "in-progress", "review", "delivered")
INTERNAL_RISK_SEVERITIES = ("critical", "high", "medium", "low")
INTERNAL_RISK_STATUSES = ("open", "monitoring", "mitigated", "closed")
INTERNAL_STAKEHOLDER_TYPES = ("client", "internal", "partner", "vendor")
INTERNAL_STAKEHOLDER_INFLUENCE_LEVELS = ("decision-maker", "core", "support", "observer")
INTERNAL_DOC_STATUSES = ("published", "draft", "archived")
INTERNAL_MESSAGE_CHANNEL_TYPES = ("project", "direct", "group")
INTERNAL_RESOURCE_STATES = ("all", "linked", "unlinked", "untagged")
INTERNAL_CALENDAR_EVENT_KINDS = ("all", "milestone", "deliverable", "task", "risk", "project")
RESOURCE_CATEGORY_FALLBACK = "general"
DEFAULT_PROJECT_TIMELINE_DAYS = 30
PROJECT_TIMELINE_PRESETS = (14, 30, 45, 60, 90)
PROJECT_TIMELINE_MIN_DAYS = 7
PROJECT_TIMELINE_MAX_DAYS = 365
PROJECT_STARTER_PLAN_RECORD_NAME = "default"
DEFAULT_PROJECT_INDUSTRY_CATEGORY = "general"
CSRF_TOKEN_SESSION_KEY = "_internal_csrf_token"
PUBLIC_CONTACT_FORM_STATE_SESSION_KEY = "_public_contact_form_state"
PUBLIC_CONTACT_FORM_ERRORS_SESSION_KEY = "_public_contact_form_errors"
SAFE_RESOURCE_LINK_SCHEMES = {"http", "https"}
DEFAULT_PUBLIC_DEMO_URL = "https://elf-ai-demo.co.za"
RESOURCE_UPLOAD_ALLOWED_EXTENSIONS = {
    "csv",
    "doc",
    "docx",
    "md",
    "pdf",
    "ppt",
    "pptx",
    "rtf",
    "txt",
    "xls",
    "xlsx",
}
DEFAULT_RESOURCE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_PROJECT_STARTER_PLANS_BY_INDUSTRY = {
    "general": [
        {
            "title": "Kickoff and Discovery",
            "priority": "high",
            "due_percent": 20,
            "subtasks": [
                {"title": "Confirm delivery objective and success metric", "due_percent": 8},
                {"title": "Map current workflow and bottlenecks", "due_percent": 14},
                {"title": "Approve scope and execution cadence", "due_percent": 20},
            ],
        },
        {
            "title": "Solution Build and Validation",
            "priority": "high",
            "due_percent": 55,
            "subtasks": [
                {"title": "Implement pilot workflow with target users", "due_percent": 38},
                {"title": "Review model and process output quality", "due_percent": 48},
                {"title": "Prioritize iteration backlog", "due_percent": 55},
            ],
        },
        {
            "title": "Rollout and Team Enablement",
            "priority": "medium",
            "due_percent": 82,
            "subtasks": [
                {"title": "Prepare launch checklist and fallback plan", "due_percent": 67},
                {"title": "Deliver team training and handover", "due_percent": 76},
                {"title": "Go-live monitoring and issue triage", "due_percent": 82},
            ],
        },
        {
            "title": "Value Review and Scale Plan",
            "priority": "medium",
            "due_percent": 100,
            "subtasks": [
                {"title": "Measure ROI against baseline KPI", "due_percent": 90},
                {"title": "Present optimisation and scale recommendations", "due_percent": 100},
            ],
        },
    ],
    "legal": [
        {
            "title": "Matter Intake and Risk Triage",
            "priority": "high",
            "due_percent": 20,
            "subtasks": [
                {"title": "Capture matter scope and parties", "due_percent": 8},
                {"title": "Run conflict and risk screening", "due_percent": 14},
                {"title": "Approve legal strategy and timelines", "due_percent": 20},
            ],
        },
        {
            "title": "Research and Draft Assembly",
            "priority": "high",
            "due_percent": 55,
            "subtasks": [
                {"title": "Compile precedent and authority bundle", "due_percent": 38},
                {"title": "Prepare first-pass draft pack", "due_percent": 48},
                {"title": "Review citations and factual accuracy", "due_percent": 55},
            ],
        },
        {
            "title": "Client Review and Filing Readiness",
            "priority": "medium",
            "due_percent": 82,
            "subtasks": [
                {"title": "Run client review and amendment cycle", "due_percent": 67},
                {"title": "Finalize filing and compliance checklist", "due_percent": 76},
                {"title": "Submit and track filing milestones", "due_percent": 82},
            ],
        },
        {
            "title": "Post-Matter Retrospective",
            "priority": "medium",
            "due_percent": 100,
            "subtasks": [
                {"title": "Summarize outcome and lessons learned", "due_percent": 90},
                {"title": "Update playbooks and precedents", "due_percent": 100},
            ],
        },
    ],
    "healthcare": [
        {
            "title": "Clinical Workflow Discovery",
            "priority": "high",
            "due_percent": 20,
            "subtasks": [
                {"title": "Map patient intake and triage journey", "due_percent": 8},
                {"title": "Define safety, quality, and response KPIs", "due_percent": 14},
                {"title": "Approve pilot care pathway scope", "due_percent": 20},
            ],
        },
        {
            "title": "Compliance and Data Governance",
            "priority": "high",
            "due_percent": 55,
            "subtasks": [
                {"title": "Validate privacy and consent controls", "due_percent": 38},
                {"title": "Configure audit and access monitoring", "due_percent": 48},
                {"title": "Run governance sign-off checklist", "due_percent": 55},
            ],
        },
        {
            "title": "Pilot and Staff Enablement",
            "priority": "medium",
            "due_percent": 82,
            "subtasks": [
                {"title": "Launch pilot in target unit", "due_percent": 67},
                {"title": "Train clinicians and support staff", "due_percent": 76},
                {"title": "Monitor incidents and escalation flow", "due_percent": 82},
            ],
        },
        {
            "title": "Outcome and Safety Review",
            "priority": "medium",
            "due_percent": 100,
            "subtasks": [
                {"title": "Compare outcomes to baseline metrics", "due_percent": 90},
                {"title": "Finalize scale recommendation", "due_percent": 100},
            ],
        },
    ],
    "finance": [
        {
            "title": "Controls and Requirements Discovery",
            "priority": "high",
            "due_percent": 20,
            "subtasks": [
                {"title": "Map current controls and approval gates", "due_percent": 8},
                {"title": "Define risk and compliance thresholds", "due_percent": 14},
                {"title": "Approve scoped pilot use case", "due_percent": 20},
            ],
        },
        {
            "title": "Model Validation and Backtesting",
            "priority": "high",
            "due_percent": 55,
            "subtasks": [
                {"title": "Prepare validation dataset and assumptions", "due_percent": 38},
                {"title": "Run backtesting and variance analysis", "due_percent": 48},
                {"title": "Sign off performance guardrails", "due_percent": 55},
            ],
        },
        {
            "title": "Deployment and Monitoring Controls",
            "priority": "medium",
            "due_percent": 82,
            "subtasks": [
                {"title": "Deploy with approval workflow controls", "due_percent": 67},
                {"title": "Train operations and risk teams", "due_percent": 76},
                {"title": "Enable live monitoring and alerts", "due_percent": 82},
            ],
        },
        {
            "title": "Quarterly Value and Risk Review",
            "priority": "medium",
            "due_percent": 100,
            "subtasks": [
                {"title": "Review portfolio impact and exceptions", "due_percent": 90},
                {"title": "Update control playbook and roadmap", "due_percent": 100},
            ],
        },
    ],
}
DEFAULT_PROJECT_STARTER_PLAN_TEMPLATE = DEFAULT_PROJECT_STARTER_PLANS_BY_INDUSTRY[DEFAULT_PROJECT_INDUSTRY_CATEGORY]
DEFAULT_PROJECT_AUTOMATION_VARIABLES = [
    {
        "key": "success_metric",
        "label": "Success Metric",
        "default": "Define the KPI improvement target for this engagement.",
    },
    {
        "key": "delivery_scope",
        "label": "Delivery Scope",
        "default": "Pilot the target workflow and prepare the rollout pack.",
    },
]
DEFAULT_PROJECT_AUTOMATION_MILESTONES = [
    {
        "title": "{{ project_name }} kickoff approved",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 18,
        "notes": "Confirm scope, cadence, and named stakeholders for {{ client_name }}.",
    },
    {
        "title": "{{ project_name }} pilot validated",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 62,
        "notes": "Validate output quality against {{ success_metric }} and agree next-step changes.",
    },
    {
        "title": "{{ project_name }} handover ready",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 100,
        "notes": "Confirm delivery assets, training notes, and launch readiness for {{ client_name }}.",
    },
]
DEFAULT_PROJECT_AUTOMATION_DELIVERABLES = [
    {
        "title": "{{ project_name }} kickoff pack",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 20,
        "description": "Briefing pack covering scope, owners, cadence, and {{ delivery_scope }}.",
        "link": "",
    },
    {
        "title": "{{ project_name }} delivery pack",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 78,
        "description": "Working delivery package for {{ client_name }} including the pilot workflow and QA notes.",
        "link": "",
    },
    {
        "title": "{{ project_name }} handover summary",
        "owner_name": "{{ owner_name }}",
        "status": "planned",
        "due_percent": 100,
        "description": "Final handover summary linked to {{ success_metric }} and the agreed operating cadence.",
        "link": "",
    },
]
DEFAULT_PROJECT_AUTOMATION_DOCUMENTS = [
    {
        "ref": "project-brief",
        "title": "{{ project_name }} Brief",
        "summary": "Working brief for {{ client_name }} covering scope, owners, and success criteria.",
        "status": "published",
        "body": (
            "# {{ project_name }}\n\n"
            "## Objective\n"
            "{{ project_summary }}\n\n"
            "## Client\n"
            "{{ client_name }}\n\n"
            "## Success Metric\n"
            "{{ success_metric }}\n\n"
            "## Delivery Scope\n"
            "{{ delivery_scope }}\n"
        ),
    },
    {
        "parent_ref": "project-brief",
        "title": "{{ project_name }} Launch Checklist",
        "summary": "Checklist for kickoff, validation, and handover readiness.",
        "status": "draft",
        "body": (
            "# Launch Checklist\n\n"
            "- [ ] Confirm stakeholders and cadence with {{ client_name }}.\n"
            "- [ ] Align milestones to {{ success_metric }}.\n"
            "- [ ] Publish the delivery pack and handover notes.\n"
        ),
    },
]


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


def _public_demo_url() -> str:
    configured_demo_url = (current_app.config.get("PUBLIC_DEMO_URL") or "").strip()
    return configured_demo_url or DEFAULT_PUBLIC_DEMO_URL


def _safe_next_url(next_target: str | None) -> str | None:
    if next_target and next_target.startswith("/"):
        return next_target
    return None


def _safe_public_return_target(raw_target: str | None) -> str | None:
    if not raw_target:
        return None
    candidate = raw_target.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    if not candidate.startswith("/"):
        return None
    if candidate.startswith("/internal"):
        return None
    return candidate


def _is_valid_public_email(raw_value: str | None) -> bool:
    candidate = (raw_value or "").strip()
    if not candidate or "\n" in candidate or "\r" in candidate:
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", candidate))


def _store_public_contact_feedback(form_state: dict[str, str], errors: dict[str, str] | None = None) -> None:
    session[PUBLIC_CONTACT_FORM_STATE_SESSION_KEY] = form_state
    if errors:
        session[PUBLIC_CONTACT_FORM_ERRORS_SESSION_KEY] = errors
    else:
        session.pop(PUBLIC_CONTACT_FORM_ERRORS_SESSION_KEY, None)


def _pop_public_contact_feedback() -> tuple[dict[str, str], dict[str, str]]:
    form_state = session.pop(PUBLIC_CONTACT_FORM_STATE_SESSION_KEY, None) or {}
    form_errors = session.pop(PUBLIC_CONTACT_FORM_ERRORS_SESSION_KEY, None) or {}
    if not isinstance(form_state, dict):
        form_state = {}
    if not isinstance(form_errors, dict):
        form_errors = {}
    return form_state, form_errors


def _clear_public_contact_feedback() -> None:
    session.pop(PUBLIC_CONTACT_FORM_STATE_SESSION_KEY, None)
    session.pop(PUBLIC_CONTACT_FORM_ERRORS_SESSION_KEY, None)


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


def _parse_month(value: str | None) -> date | None:
    candidate = (value or "").strip()
    if not candidate:
        return None
    try:
        return date.fromisoformat(f"{candidate}-01")
    except ValueError:
        return None


def _month_start(value: date | None = None) -> date:
    reference = value or date.today()
    return reference.replace(day=1)


def _next_month_start(value: date) -> date:
    return (value.replace(day=28) + timedelta(days=4)).replace(day=1)


def _previous_month_start(value: date) -> date:
    return (value.replace(day=1) - timedelta(days=1)).replace(day=1)


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


def _normalize_internal_milestone_status(raw_value: str | None) -> str:
    normalized = (raw_value or "planned").strip().lower()
    return normalized if normalized in INTERNAL_MILESTONE_STATUSES else "planned"


def _normalize_internal_deliverable_status(raw_value: str | None) -> str:
    normalized = (raw_value or "planned").strip().lower()
    return normalized if normalized in INTERNAL_DELIVERABLE_STATUSES else "planned"


def _normalize_internal_risk_severity(raw_value: str | None) -> str:
    normalized = (raw_value or "medium").strip().lower()
    return normalized if normalized in INTERNAL_RISK_SEVERITIES else "medium"


def _normalize_internal_risk_status(raw_value: str | None) -> str:
    normalized = (raw_value or "open").strip().lower()
    return normalized if normalized in INTERNAL_RISK_STATUSES else "open"


def _normalize_internal_stakeholder_type(raw_value: str | None) -> str:
    normalized = (raw_value or "client").strip().lower()
    return normalized if normalized in INTERNAL_STAKEHOLDER_TYPES else "client"


def _normalize_internal_stakeholder_influence(raw_value: str | None) -> str:
    normalized = (raw_value or "core").strip().lower()
    return normalized if normalized in INTERNAL_STAKEHOLDER_INFLUENCE_LEVELS else "core"


def _normalize_internal_doc_status(raw_value: str | None) -> str:
    normalized = (raw_value or "published").strip().lower()
    return normalized if normalized in INTERNAL_DOC_STATUSES else "published"


def _slugify_text(raw_value: str | None, fallback: str = "page") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (raw_value or "").strip().lower()).strip("-")
    return normalized or fallback


def _unique_internal_doc_slug(title: str, *, page_id: int | None = None) -> str:
    base_slug = _slugify_text(title, fallback="page")
    candidate = base_slug
    suffix = 2
    while True:
        existing_page = InternalDocPage.query.filter_by(slug=candidate).first()
        if not existing_page or existing_page.id == page_id:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


def _render_internal_doc_inline(text: str) -> str:
    if not text:
        return ""

    rendered_parts: list[str] = []
    cursor = 0
    token_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*(.+?)\*\*")

    for match in token_pattern.finditer(text):
        rendered_parts.append(str(escape(text[cursor:match.start()])))
        label, href, code_text, strong_text = match.groups()
        if label is not None and href is not None:
            safe_href = href.strip()
            if _is_safe_resource_link(safe_href):
                rendered_parts.append(
                    f'<a href="{escape(safe_href)}" class="text-blue-300 underline underline-offset-2" '
                    f'target="_blank" rel="noopener noreferrer">{escape(label)}</a>'
                )
            else:
                rendered_parts.append(str(escape(label)))
        elif code_text is not None:
            rendered_parts.append(
                f'<code class="rounded-md bg-slate-900 px-1.5 py-0.5 text-[0.92em] text-blue-200">{escape(code_text)}</code>'
            )
        elif strong_text is not None:
            rendered_parts.append(f"<strong>{escape(strong_text)}</strong>")
        cursor = match.end()

    rendered_parts.append(str(escape(text[cursor:])))
    return "".join(rendered_parts)


def _render_internal_doc_body(raw_text: str | None) -> Markup:
    lines = (raw_text or "").splitlines()
    html_blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            html_blocks.append(
                '<pre class="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950 px-4 py-4 text-sm text-slate-200"><code>'
                f"{escape(chr(10).join(code_lines))}</code></pre>"
            )
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            anchor = _slugify_text(heading_text, fallback="section")
            heading_classes = {
                1: "text-3xl font-black text-white mt-2",
                2: "text-2xl font-bold text-white mt-2",
                3: "text-xl font-bold text-white mt-2",
            }
            html_blocks.append(
                f'<h{level} id="{anchor}" class="{heading_classes[level]}">{_render_internal_doc_inline(heading_text)}</h{level}>'
            )
            index += 1
            continue

        if re.match(r"^[-*]\s+\[[ xX]\]\s+", stripped):
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                match = re.match(r"^[-*]\s+\[([ xX])\]\s+(.+)$", candidate)
                if not match:
                    break
                checked = match.group(1).lower() == "x"
                item_text = _render_internal_doc_inline(match.group(2).strip())
                checkbox_class = "bg-blue-500 border-blue-500 text-white" if checked else "border-slate-600"
                checkmark = '<i class="fa-solid fa-check text-[10px]"></i>' if checked else ""
                items.append(
                    '<li class="flex items-start gap-3 rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2">'
                    f'<span class="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-md border {checkbox_class}">{checkmark}</span>'
                    f'<span class="text-slate-200">{item_text}</span>'
                    "</li>"
                )
                index += 1
            html_blocks.append(f'<ul class="space-y-2">{"".join(items)}</ul>')
            continue

        if re.match(r"^[-*]\s+.+$", stripped):
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not re.match(r"^[-*]\s+.+$", candidate) or re.match(r"^[-*]\s+\[[ xX]\]\s+", candidate):
                    break
                item_text = _render_internal_doc_inline(re.sub(r"^[-*]\s+", "", candidate, count=1))
                items.append(f'<li class="text-slate-200">{item_text}</li>')
                index += 1
            html_blocks.append(f'<ul class="list-disc space-y-2 pl-5">{"".join(items)}</ul>')
            continue

        if re.match(r"^\d+\.\s+.+$", stripped):
            items: list[str] = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not re.match(r"^\d+\.\s+.+$", candidate):
                    break
                item_text = _render_internal_doc_inline(re.sub(r"^\d+\.\s+", "", candidate, count=1))
                items.append(f'<li class="text-slate-200">{item_text}</li>')
                index += 1
            html_blocks.append(f'<ol class="list-decimal space-y-2 pl-5">{"".join(items)}</ol>')
            continue

        if stripped.startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip().lstrip(">").strip())
                index += 1
            quote_html = "<br>".join(_render_internal_doc_inline(item) for item in quote_lines if item)
            html_blocks.append(
                '<blockquote class="rounded-2xl border border-blue-500/20 bg-blue-500/10 px-4 py-3 text-slate-200">'
                f"{quote_html}</blockquote>"
            )
            continue

        paragraph_lines: list[str] = []
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                break
            if candidate.startswith("```") or re.match(r"^(#{1,3})\s+(.+)$", candidate):
                break
            if candidate.startswith(">") or re.match(r"^[-*]\s+.+$", candidate) or re.match(r"^\d+\.\s+.+$", candidate):
                break
            paragraph_lines.append(candidate)
            index += 1
        paragraph_html = " ".join(_render_internal_doc_inline(item) for item in paragraph_lines)
        html_blocks.append(f'<p class="text-base leading-7 text-slate-200">{paragraph_html}</p>')

    return Markup("\n".join(html_blocks))


def _internal_doc_outline(raw_text: str | None) -> list[dict]:
    outline: list[dict] = []
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if not match:
            continue
        level = len(match.group(1))
        text = match.group(2).strip()
        outline.append({"level": level, "text": text, "anchor": _slugify_text(text, fallback="section")})
    return outline


def _normalize_progress_percent(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        progress_percent = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None
    if progress_percent < 0 or progress_percent > 100:
        return None
    return progress_percent


def _parse_currency_value(raw_value: str | None) -> Decimal | None | object:
    candidate = (raw_value or "").strip().replace(",", "")
    if not candidate:
        return None
    try:
        parsed = Decimal(candidate)
    except (InvalidOperation, ValueError):
        return ...
    if parsed < 0:
        return ...
    return parsed


def _serialize_currency(value) -> str:
    if value is None:
        return ""
    try:
        return format(Decimal(value), "f").rstrip("0").rstrip(".")
    except (InvalidOperation, ValueError, TypeError):
        return str(value)


def _timeline_status_sort_rank(status: str | None) -> int:
    normalized = (status or "").strip().lower()
    rank = {
        "planned": 0,
        "in-progress": 1,
        "review": 2,
        "at-risk": 3,
        "done": 4,
        "delivered": 4,
        "closed": 4,
    }
    return rank.get(normalized, 5)


def _internal_risk_severity_class(severity: str | None) -> str:
    normalized = (severity or "").strip().lower()
    if normalized == "critical":
        return "bg-rose-500/20 text-rose-200 border border-rose-500/40"
    if normalized == "high":
        return "bg-orange-500/20 text-orange-200 border border-orange-500/40"
    if normalized == "medium":
        return "bg-amber-500/20 text-amber-200 border border-amber-500/40"
    return "bg-blue-500/20 text-blue-200 border border-blue-500/40"


def _internal_calendar_kind_meta(kind: str) -> dict[str, str]:
    palette = {
        "milestone": {
            "label": "Milestone",
            "icon": "fa-flag-checkered",
            "badge_class": "bg-amber-500/10 text-amber-200 border border-amber-500/30",
            "dot_class": "bg-amber-300",
        },
        "deliverable": {
            "label": "Deliverable",
            "icon": "fa-box-open",
            "badge_class": "bg-emerald-500/10 text-emerald-200 border border-emerald-500/30",
            "dot_class": "bg-emerald-300",
        },
        "task": {
            "label": "Task",
            "icon": "fa-list-check",
            "badge_class": "bg-blue-500/10 text-blue-200 border border-blue-500/30",
            "dot_class": "bg-blue-300",
        },
        "risk": {
            "label": "Risk",
            "icon": "fa-shield-halved",
            "badge_class": "bg-rose-500/10 text-rose-200 border border-rose-500/30",
            "dot_class": "bg-rose-300",
        },
        "project": {
            "label": "Project",
            "icon": "fa-diagram-project",
            "badge_class": "bg-indigo-500/10 text-indigo-200 border border-indigo-500/30",
            "dot_class": "bg-indigo-300",
        },
    }
    return palette.get(kind, palette["task"])


def _internal_calendar_event_sort_key(event: dict):
    kind_rank = {
        "milestone": 0,
        "deliverable": 1,
        "task": 2,
        "risk": 3,
        "project": 4,
    }
    return (
        event.get("due_date") or date.max,
        kind_rank.get(event.get("kind"), 9),
        (event.get("project_name") or "").lower(),
        (event.get("title") or "").lower(),
        event.get("id") or "",
    )


def _normalize_project_timeline_days(raw_value: str | None) -> int:
    if raw_value is None:
        return DEFAULT_PROJECT_TIMELINE_DAYS
    try:
        parsed_days = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return DEFAULT_PROJECT_TIMELINE_DAYS
    return min(max(parsed_days, PROJECT_TIMELINE_MIN_DAYS), PROJECT_TIMELINE_MAX_DAYS)


def _normalize_industry_category(raw_value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (raw_value or "").strip().lower()).strip("-")
    if normalized == PROJECT_STARTER_PLAN_RECORD_NAME:
        normalized = DEFAULT_PROJECT_INDUSTRY_CATEGORY
    return normalized or DEFAULT_PROJECT_INDUSTRY_CATEGORY


def _industry_category_label(category: str | None) -> str:
    return _normalize_industry_category(category).replace("-", " ").title()


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


def _internal_user_is_senior(user: InternalUser | None) -> bool:
    if not user:
        return False

    normalized_role = " ".join((user.role or "").strip().lower().split())
    if not normalized_role:
        return False

    role_tokens = {token for token in re.split(r"[\s/_-]+", normalized_role) if token}
    if "admin" in role_tokens:
        return True

    senior_role_tokens = {
        "chief",
        "director",
        "head",
        "lead",
        "manager",
        "operations",
        "partner",
        "principal",
        "senior",
    }
    return bool(role_tokens & senior_role_tokens)


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


def _resource_upload_directory() -> str:
    configured_directory = (current_app.config.get("INTERNAL_RESOURCE_UPLOAD_DIR") or "").strip()
    upload_directory = configured_directory or os.path.join(
        current_app.instance_path,
        "uploads",
        "internal_resources",
    )
    os.makedirs(upload_directory, exist_ok=True)
    return upload_directory


def _resource_upload_max_bytes() -> int:
    configured_limit = current_app.config.get("INTERNAL_RESOURCE_UPLOAD_MAX_BYTES", DEFAULT_RESOURCE_UPLOAD_MAX_BYTES)
    try:
        parsed_limit = int(configured_limit)
    except (TypeError, ValueError):
        return DEFAULT_RESOURCE_UPLOAD_MAX_BYTES
    return parsed_limit if parsed_limit > 0 else DEFAULT_RESOURCE_UPLOAD_MAX_BYTES


def _resource_upload_limit_label() -> str:
    return f"{_resource_upload_max_bytes() / (1024 * 1024):g}"


def _allowed_resource_upload_extension(filename: str) -> str | None:
    if "." not in filename:
        return None
    extension = filename.rsplit(".", 1)[1].strip().lower()
    if extension in RESOURCE_UPLOAD_ALLOWED_EXTENSIONS:
        return extension
    return None


def _resource_upload_size(uploaded_file) -> int | None:
    stream = getattr(uploaded_file, "stream", None)
    if stream is None:
        return None

    try:
        current_position = stream.tell()
        stream.seek(0, os.SEEK_END)
        file_size = stream.tell()
        stream.seek(current_position)
    except (OSError, ValueError):
        return None
    return file_size if isinstance(file_size, int) else None


def _save_resource_upload(uploaded_file) -> tuple[str | None, str | None]:
    submitted_filename = (uploaded_file.filename or "").strip()
    if not submitted_filename:
        return None, "Select a file to upload."

    safe_filename = secure_filename(submitted_filename)
    extension = _allowed_resource_upload_extension(safe_filename)
    if not extension:
        allowed_extensions = ", ".join(f".{item}" for item in sorted(RESOURCE_UPLOAD_ALLOWED_EXTENSIONS))
        return None, f"Unsupported file type. Allowed types: {allowed_extensions}."

    upload_size = _resource_upload_size(uploaded_file)
    if upload_size is None:
        return None, "Could not read uploaded file size."
    if upload_size <= 0:
        return None, "Uploaded file is empty."

    max_upload_bytes = _resource_upload_max_bytes()
    if upload_size > max_upload_bytes:
        return None, f"Uploaded file exceeds the {_resource_upload_limit_label()} MB limit."

    stored_filename = (
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        f"-{secrets.token_hex(8)}.{extension}"
    )
    upload_path = os.path.join(_resource_upload_directory(), stored_filename)

    try:
        uploaded_file.stream.seek(0)
    except (AttributeError, OSError, ValueError):
        pass

    uploaded_file.save(upload_path)
    return stored_filename, None


def _internal_resource_uploaded_filename(raw_link: str | None) -> str | None:
    candidate = (raw_link or "").strip()
    if not candidate:
        return None

    download_prefix = url_for("main.internal_resource_file_download", filename="")
    if not candidate.startswith(download_prefix):
        return None

    filename = candidate.removeprefix(download_prefix).strip().lstrip("/")
    if not filename or "/" in filename or filename != secure_filename(filename):
        return None
    return filename


def _delete_internal_resource_upload(raw_link: str | None) -> None:
    uploaded_filename = _internal_resource_uploaded_filename(raw_link)
    if not uploaded_filename:
        return

    upload_path = os.path.join(_resource_upload_directory(), uploaded_filename)
    try:
        if os.path.isfile(upload_path):
            os.remove(upload_path)
    except OSError:
        current_app.logger.warning("Failed to remove internal resource upload: %s", upload_path)


def _parse_positive_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _project_workspace_url(project_id: int, anchor: str = "", **query_params) -> str:
    filtered_params = {key: value for key, value in query_params.items() if value not in {None, "", 0}}
    target = url_for("main.internal_project_workspace", project_id=project_id, **filtered_params)
    return f"{target}{anchor}" if anchor else target


def _project_list_redirect(selected_client_id: int | None = None, anchor: str = "") -> str:
    kwargs = {}
    if selected_client_id:
        kwargs["client_id"] = selected_client_id
    target = url_for("main.internal_projects", **kwargs)
    return f"{target}{anchor}" if anchor else target


def _prepare_project_for_delete(project: InternalProject) -> None:
    for task in project.tasks:
        task.resources = []
    project.resources = []
    if project.message_channel:
        project.message_channel.members = []


def _internal_todos_redirect_kwargs(
    view_mode_raw: str | None,
    project_scope_raw: str | None,
    *,
    edit_task_id: int | None = None,
) -> dict[str, str | int]:
    view_mode = (view_mode_raw or "nested").strip().lower()
    if view_mode not in {"nested", "priority"}:
        view_mode = "nested"

    redirect_kwargs: dict[str, str | int] = {"view": view_mode}
    project_scope_id = _parse_positive_int(project_scope_raw)
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id
    if edit_task_id:
        redirect_kwargs["edit_task_id"] = edit_task_id
    return redirect_kwargs


def _internal_resources_redirect_kwargs(
    *,
    default_query: str | None = None,
    edit_resource_id: int | None = None,
) -> dict[str, str | int]:
    redirect_kwargs: dict[str, str | int] = {}

    query_term = (request.form.get("redirect_q") or default_query or "").strip()
    if query_term:
        redirect_kwargs["q"] = query_term

    selected_category = (request.form.get("redirect_category") or "all").strip().lower()
    if selected_category and selected_category != "all":
        redirect_kwargs["category"] = selected_category

    selected_tag = (request.form.get("redirect_tag") or "all").strip().lower()
    if selected_tag and selected_tag != "all":
        redirect_kwargs["tag"] = selected_tag

    selected_state = (request.form.get("redirect_state") or "all").strip().lower()
    if selected_state in INTERNAL_RESOURCE_STATES and selected_state != "all":
        redirect_kwargs["state"] = selected_state

    project_scope_id = _parse_positive_int(request.form.get("project_scope"))
    if project_scope_id:
        redirect_kwargs["project_id"] = project_scope_id

    if edit_resource_id:
        redirect_kwargs["edit_id"] = edit_resource_id

    return redirect_kwargs


def _internal_resource_tag_records(tag_names: list[str]) -> list[InternalResourceTag]:
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
    return resource_tags


def _ensure_project_message_channel(
    project: InternalProject,
    *,
    created_by: InternalUser | None = None,
) -> InternalMessageChannel:
    if project.message_channel:
        return project.message_channel

    channel = InternalMessageChannel(
        channel_type="project",
        name=f"{project.name} Channel",
        project=project,
        creator=created_by,
    )
    db.session.add(channel)
    return channel


def _normalize_percentage(raw_value) -> float | None:
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return None
    if parsed < 0 or parsed > 100:
        return None
    return parsed


def _normalize_template_identifier(raw_value: str | None) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(raw_value or "").strip().lower()).strip("_")


def _normalize_project_template_variables(raw_variables) -> tuple[list[dict] | None, str | None]:
    if raw_variables is None or raw_variables == "":
        return [], None
    if not isinstance(raw_variables, list):
        return None, "Template variables must be a JSON array."

    normalized_variables: list[dict] = []
    seen_keys: set[str] = set()
    for variable_index, variable in enumerate(raw_variables, start=1):
        if isinstance(variable, str):
            raw_key = variable
            label = variable
            default_value = ""
        elif isinstance(variable, dict):
            raw_key = variable.get("key")
            label = str(variable.get("label") or raw_key or "").strip()
            default_value = str(variable.get("default") or "").strip()
        else:
            return None, f"Template variable {variable_index} must be a string or object."

        key = _normalize_template_identifier(raw_key)
        if not key:
            return None, f"Template variable {variable_index} requires a valid key."
        if key in seen_keys:
            return None, f"Template variable '{key}' is duplicated."
        seen_keys.add(key)
        normalized_variables.append(
            {
                "key": key,
                "label": label or key.replace("_", " ").title(),
                "default": default_value,
            }
        )

    return normalized_variables, None


def _normalize_project_template_task_entry(
    raw_task,
    *,
    entry_label: str,
    default_priority: str = "medium",
    default_status: str = "todo",
    default_assignee: str = "{{ owner_name }}",
    default_due_percent: float = 100,
) -> tuple[dict | None, str | None]:
    if not isinstance(raw_task, dict):
        return None, f"{entry_label} must be a JSON object."

    title = " ".join(str(raw_task.get("title") or "").strip().split())
    if not title:
        return None, f"{entry_label} is missing a valid title."

    priority = _normalize_internal_task_priority(raw_task.get("priority") or default_priority)
    status = _normalize_internal_task_status(raw_task.get("status") or default_status)
    assignee = " ".join(str(raw_task.get("assignee") or default_assignee).strip().split()) or default_assignee
    due_percent = _normalize_percentage(raw_task.get("due_percent", default_due_percent))
    if due_percent is None:
        return None, f"{entry_label} requires due_percent between 0 and 100."

    subtasks_raw = raw_task.get("subtasks") or []
    if not isinstance(subtasks_raw, list):
        return None, f"{entry_label} subtasks must be a JSON array."

    normalized_subtasks: list[dict] = []
    for subtask_index, subtask in enumerate(subtasks_raw, start=1):
        if isinstance(subtask, str):
            subtask_payload = {"title": subtask}
        elif isinstance(subtask, dict):
            subtask_payload = subtask
        else:
            return None, f"{entry_label} subtask {subtask_index} must be an object or string."

        normalized_subtask, error_message = _normalize_project_template_task_entry(
            subtask_payload,
            entry_label=f"{entry_label} subtask {subtask_index}",
            default_priority=priority,
            default_status=status,
            default_assignee=assignee,
            default_due_percent=due_percent,
        )
        if error_message or not normalized_subtask:
            return None, error_message
        normalized_subtask["subtasks"] = []
        normalized_subtasks.append(normalized_subtask)

    return {
        "title": title,
        "priority": priority,
        "status": status,
        "assignee": assignee,
        "due_percent": due_percent,
        "subtasks": normalized_subtasks,
    }, None


def _normalize_project_template_tasks(raw_tasks) -> tuple[list[dict] | None, str | None]:
    if raw_tasks is None or raw_tasks == "":
        return [], None
    if not isinstance(raw_tasks, list):
        return None, "Template tasks must be a JSON array."

    normalized_tasks: list[dict] = []
    for task_index, task in enumerate(raw_tasks, start=1):
        normalized_task, error_message = _normalize_project_template_task_entry(
            task,
            entry_label=f"Task {task_index}",
        )
        if error_message or not normalized_task:
            return None, error_message
        normalized_tasks.append(normalized_task)
    return normalized_tasks, None


def _normalize_project_template_milestones(raw_milestones) -> tuple[list[dict] | None, str | None]:
    if raw_milestones is None or raw_milestones == "":
        return [], None
    if not isinstance(raw_milestones, list):
        return None, "Template milestones must be a JSON array."

    normalized_milestones: list[dict] = []
    for milestone_index, milestone in enumerate(raw_milestones, start=1):
        if not isinstance(milestone, dict):
            return None, f"Milestone {milestone_index} must be a JSON object."

        title = " ".join(str(milestone.get("title") or "").strip().split())
        if not title:
            return None, f"Milestone {milestone_index} is missing a valid title."

        owner_name = " ".join(
            str(milestone.get("owner_name") or "{{ owner_name }}").strip().split()
        ) or "{{ owner_name }}"
        due_percent = _normalize_percentage(milestone.get("due_percent", 100))
        if due_percent is None:
            return None, f"Milestone {milestone_index} requires due_percent between 0 and 100."

        normalized_milestones.append(
            {
                "title": title,
                "owner_name": owner_name,
                "status": _normalize_internal_milestone_status(milestone.get("status")),
                "due_percent": due_percent,
                "notes": str(milestone.get("notes") or "").strip(),
            }
        )

    return normalized_milestones, None


def _normalize_project_template_deliverables(raw_deliverables) -> tuple[list[dict] | None, str | None]:
    if raw_deliverables is None or raw_deliverables == "":
        return [], None
    if not isinstance(raw_deliverables, list):
        return None, "Template deliverables must be a JSON array."

    normalized_deliverables: list[dict] = []
    for deliverable_index, deliverable in enumerate(raw_deliverables, start=1):
        if not isinstance(deliverable, dict):
            return None, f"Deliverable {deliverable_index} must be a JSON object."

        title = " ".join(str(deliverable.get("title") or "").strip().split())
        description = str(deliverable.get("description") or "").strip()
        if not title:
            return None, f"Deliverable {deliverable_index} is missing a valid title."
        if not description:
            return None, f"Deliverable {deliverable_index} requires a description."

        owner_name = " ".join(
            str(deliverable.get("owner_name") or "{{ owner_name }}").strip().split()
        ) or "{{ owner_name }}"
        due_percent = _normalize_percentage(deliverable.get("due_percent", 100))
        if due_percent is None:
            return None, f"Deliverable {deliverable_index} requires due_percent between 0 and 100."

        normalized_deliverables.append(
            {
                "title": title,
                "owner_name": owner_name,
                "status": _normalize_internal_deliverable_status(deliverable.get("status")),
                "due_percent": due_percent,
                "description": description,
                "link": str(deliverable.get("link") or "").strip(),
            }
        )

    return normalized_deliverables, None


def _normalize_project_template_documents(raw_documents) -> tuple[list[dict] | None, str | None]:
    if raw_documents is None or raw_documents == "":
        return [], None
    if not isinstance(raw_documents, list):
        return None, "Template documents must be a JSON array."

    normalized_documents: list[dict] = []
    seen_refs: set[str] = set()
    for document_index, document in enumerate(raw_documents, start=1):
        if not isinstance(document, dict):
            return None, f"Document {document_index} must be a JSON object."

        title = " ".join(str(document.get("title") or "").strip().split())
        summary = str(document.get("summary") or "").strip()
        body = str(document.get("body") or "").strip()
        if not title or not summary or not body:
            return None, f"Document {document_index} requires title, summary, and body."

        ref = _normalize_template_identifier(document.get("ref"))
        if ref:
            if ref in seen_refs:
                return None, f"Document ref '{ref}' is duplicated."
            seen_refs.add(ref)

        parent_ref = _normalize_template_identifier(document.get("parent_ref"))
        if parent_ref and ref and parent_ref == ref:
            return None, f"Document {document_index} cannot reference itself as a parent."

        normalized_documents.append(
            {
                "ref": ref,
                "parent_ref": parent_ref,
                "title": title,
                "summary": summary,
                "body": body,
                "status": _normalize_internal_doc_status(document.get("status")),
                "slug": _slugify_text(str(document.get("slug") or "").strip(), fallback=""),
            }
        )

    known_refs = {document["ref"] for document in normalized_documents if document["ref"]}
    for document_index, document in enumerate(normalized_documents, start=1):
        parent_ref = document.get("parent_ref")
        if parent_ref and parent_ref not in known_refs:
            return None, f"Document {document_index} references unknown parent_ref '{parent_ref}'."

    return normalized_documents, None


def _build_project_starter_plan_template(task_template: list[dict]) -> dict:
    template_payload = {
        "variables": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_VARIABLES),
        "milestones": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_MILESTONES),
        "deliverables": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_DELIVERABLES),
        "documents": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_DOCUMENTS),
        "tasks": copy.deepcopy(task_template),
    }
    normalized_template, error_message = _normalize_project_starter_plan_template(template_payload)
    if error_message or not normalized_template:
        return {
            "variables": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_VARIABLES),
            "milestones": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_MILESTONES),
            "deliverables": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_DELIVERABLES),
            "documents": copy.deepcopy(DEFAULT_PROJECT_AUTOMATION_DOCUMENTS),
            "tasks": [],
        }
    return normalized_template


def _normalize_project_starter_plan_template(raw_template) -> tuple[dict | None, str | None]:
    if isinstance(raw_template, list):
        raw_template = {"tasks": raw_template}
    if not isinstance(raw_template, dict):
        return None, "Automation template must be a JSON object or legacy JSON array."

    normalized_variables, error_message = _normalize_project_template_variables(raw_template.get("variables"))
    if error_message or normalized_variables is None:
        return None, error_message

    normalized_tasks, error_message = _normalize_project_template_tasks(raw_template.get("tasks"))
    if error_message or normalized_tasks is None:
        return None, error_message

    normalized_milestones, error_message = _normalize_project_template_milestones(raw_template.get("milestones"))
    if error_message or normalized_milestones is None:
        return None, error_message

    normalized_deliverables, error_message = _normalize_project_template_deliverables(raw_template.get("deliverables"))
    if error_message or normalized_deliverables is None:
        return None, error_message

    normalized_documents, error_message = _normalize_project_template_documents(raw_template.get("documents"))
    if error_message or normalized_documents is None:
        return None, error_message

    if not any((normalized_tasks, normalized_milestones, normalized_deliverables, normalized_documents)):
        return None, "Automation template must define at least one task, milestone, deliverable, or document."

    return {
        "variables": normalized_variables,
        "milestones": normalized_milestones,
        "deliverables": normalized_deliverables,
        "documents": normalized_documents,
        "tasks": normalized_tasks,
    }, None


def _serialize_project_starter_plan_template(template: dict) -> str:
    return json.dumps(template, indent=2, ensure_ascii=True)


def _project_starter_plan_record(industry_category: str) -> InternalProjectStarterPlan | None:
    normalized_category = _normalize_industry_category(industry_category)
    record = InternalProjectStarterPlan.query.filter_by(name=normalized_category).first()
    if record:
        return record
    if normalized_category == DEFAULT_PROJECT_INDUSTRY_CATEGORY:
        return InternalProjectStarterPlan.query.filter_by(name=PROJECT_STARTER_PLAN_RECORD_NAME).first()
    return None


def _default_project_starter_plan_template(industry_category: str) -> dict:
    normalized_category = _normalize_industry_category(industry_category)
    industry_template = DEFAULT_PROJECT_STARTER_PLANS_BY_INDUSTRY.get(normalized_category)
    if industry_template:
        return _build_project_starter_plan_template(industry_template)
    return _build_project_starter_plan_template(DEFAULT_PROJECT_STARTER_PLAN_TEMPLATE)


def _load_project_starter_plan_template(industry_category: str = DEFAULT_PROJECT_INDUSTRY_CATEGORY) -> dict:
    normalized_category = _normalize_industry_category(industry_category)
    default_template = _default_project_starter_plan_template(normalized_category)
    record = _project_starter_plan_record(normalized_category)
    if not record:
        return default_template

    try:
        raw_template = json.loads(record.template_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default_template

    normalized_template, error_message = _normalize_project_starter_plan_template(raw_template)
    if error_message or not normalized_template:
        return default_template
    return normalized_template


def _project_starter_plan_categories(existing_projects: list[InternalProject], clients: list[InternalClient]) -> list[str]:
    default_categories = set(DEFAULT_PROJECT_STARTER_PLANS_BY_INDUSTRY.keys())
    custom_categories = {_normalize_industry_category(plan.name) for plan in InternalProjectStarterPlan.query.all()}
    project_categories = {_normalize_industry_category(project.industry_category) for project in existing_projects}
    client_categories = {_normalize_industry_category(client.industry) for client in clients}
    all_categories = default_categories | custom_categories | project_categories | client_categories
    all_categories.add(DEFAULT_PROJECT_INDUSTRY_CATEGORY)
    return sorted(all_categories)


def _project_starter_plan_editor_context(industry_category: str) -> dict:
    normalized_category = _normalize_industry_category(industry_category)
    record = _project_starter_plan_record(normalized_category)
    template = _load_project_starter_plan_template(normalized_category)
    source = "custom" if record and _normalize_industry_category(record.name) == normalized_category else "default"
    return {
        "starter_plan_category": normalized_category,
        "starter_plan_category_label": _industry_category_label(normalized_category),
        "starter_plan_source": source,
        "starter_plan_template_text": _serialize_project_starter_plan_template(template),
        "starter_plan_updated_at": record.updated_at if record else None,
        "starter_plan_updated_by": record.updated_by.full_name if record and record.updated_by else None,
        "starter_plan_variables": template.get("variables", []),
        "starter_plan_stats": {
            "tasks": len(template.get("tasks", [])),
            "milestones": len(template.get("milestones", [])),
            "deliverables": len(template.get("deliverables", [])),
            "documents": len(template.get("documents", [])),
        },
    }


def _parse_project_template_runtime_variables(raw_value: str | None) -> tuple[dict[str, str] | None, str | None]:
    candidate = (raw_value or "").strip()
    if not candidate:
        return {}, None

    try:
        parsed_variables = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"Template variables must be valid JSON (line {exc.lineno}, column {exc.colno})."

    if not isinstance(parsed_variables, dict):
        return None, "Template variables must be a JSON object."

    normalized_variables: dict[str, str] = {}
    for raw_key, raw_variable_value in parsed_variables.items():
        normalized_key = _normalize_template_identifier(raw_key)
        if not normalized_key:
            return None, "Template variable keys must contain letters, numbers, or underscores."
        if isinstance(raw_variable_value, (dict, list)):
            return None, f"Template variable '{raw_key}' must be a string, number, or boolean."
        normalized_variables[normalized_key] = str(raw_variable_value).strip()

    return normalized_variables, None


def _render_project_template_text(raw_value: str | None, context: dict[str, str]) -> str:
    if raw_value is None:
        return ""
    return re.sub(
        r"{{\s*([a-zA-Z0-9_]+)\s*}}",
        lambda match: context.get(match.group(1), match.group(0)),
        str(raw_value),
    )


def _project_template_context(
    project: InternalProject,
    *,
    timeline_days: int,
    owner_display_name: str,
    plan_template: dict,
    runtime_variables: dict[str, str] | None = None,
) -> dict[str, str]:
    project_due_date = project.due_date or (date.today() + timedelta(days=max(timeline_days, 1)))
    context = {
        "project_name": project.name,
        "project_summary": project.summary,
        "client_name": project.client.name if project.client else "",
        "client_account_owner": project.client.account_owner if project.client else "",
        "owner_name": owner_display_name or (project.client.account_owner if project.client else "") or "Project Team",
        "timeline_days": str(max(timeline_days, 1)),
        "industry_category": project.industry_category or DEFAULT_PROJECT_INDUSTRY_CATEGORY,
        "industry_label": _industry_category_label(project.industry_category),
        "due_date": project_due_date.isoformat(),
        "due_date_display": project_due_date.strftime("%d %b %Y"),
        "today": date.today().isoformat(),
        "today_display": date.today().strftime("%d %b %Y"),
    }

    for variable in plan_template.get("variables", []):
        key = variable.get("key")
        if not key or key in context:
            continue
        rendered_default = _render_project_template_text(variable.get("default"), context).strip()
        context[key] = rendered_default

    for key, value in (runtime_variables or {}).items():
        context[key] = value
    return context


def _apply_project_starter_plan(
    project: InternalProject,
    *,
    timeline_days: int,
    owner_display_name: str,
    plan_template: dict | None = None,
    runtime_variables: dict[str, str] | None = None,
) -> None:
    start_date = date.today()
    effective_timeline_days = max(timeline_days, 1)
    project_due_date = project.due_date or (start_date + timedelta(days=effective_timeline_days))
    delivery_owner = owner_display_name or project.client.account_owner or "Project Team"
    starter_plan = plan_template or _load_project_starter_plan_template(project.industry_category)
    template_context = _project_template_context(
        project,
        timeline_days=timeline_days,
        owner_display_name=delivery_owner,
        plan_template=starter_plan,
        runtime_variables=runtime_variables,
    )

    def milestone(percentage: float) -> date:
        clamped_percentage = min(max(float(percentage), 0), 100) / 100
        span_days = max((project_due_date - start_date).days, 1)
        offset_days = max(1, int(round(span_days * clamped_percentage)))
        target_date = start_date + timedelta(days=offset_days)
        return min(target_date, project_due_date)

    for phase in starter_plan.get("milestones", []):
        rendered_title = " ".join(_render_project_template_text(phase["title"], template_context).strip().split())
        rendered_owner_name = (
            " ".join(_render_project_template_text(phase.get("owner_name"), template_context).strip().split())
            or delivery_owner
        )
        rendered_notes = _render_project_template_text(phase.get("notes"), template_context).strip() or None
        db.session.add(
            InternalProjectMilestone(
                project=project,
                title=rendered_title,
                owner_name=rendered_owner_name,
                status=phase["status"],
                due_date=milestone(phase.get("due_percent", 100)),
                notes=rendered_notes,
            )
        )

    for deliverable in starter_plan.get("deliverables", []):
        rendered_title = " ".join(
            _render_project_template_text(deliverable["title"], template_context).strip().split()
        )
        rendered_owner_name = (
            " ".join(
                _render_project_template_text(deliverable.get("owner_name"), template_context).strip().split()
            )
            or delivery_owner
        )
        rendered_description = _render_project_template_text(
            deliverable.get("description"),
            template_context,
        ).strip()
        rendered_link = _render_project_template_text(deliverable.get("link"), template_context).strip()
        if rendered_link and not _is_safe_resource_link(rendered_link):
            rendered_link = ""
        db.session.add(
            InternalProjectDeliverable(
                project=project,
                title=rendered_title,
                owner_name=rendered_owner_name,
                status=deliverable["status"],
                due_date=milestone(deliverable.get("due_percent", 100)),
                link=rendered_link or None,
                description=rendered_description,
            )
        )

    created_pages_by_ref: dict[str, InternalDocPage] = {}
    pending_doc_parents: list[tuple[InternalDocPage, str | None]] = []
    for document in starter_plan.get("documents", []):
        rendered_title = " ".join(_render_project_template_text(document["title"], template_context).strip().split())
        rendered_summary = _render_project_template_text(document.get("summary"), template_context).strip()
        rendered_body = _render_project_template_text(document.get("body"), template_context).strip()
        rendered_slug_source = _render_project_template_text(document.get("slug"), template_context).strip() or rendered_title
        page = InternalDocPage(
            title=rendered_title,
            slug=_unique_internal_doc_slug(rendered_slug_source),
            summary=rendered_summary,
            body=rendered_body,
            status=document["status"],
            project=project,
            author=getattr(g, "internal_user", None),
        )
        db.session.add(page)
        if document.get("ref"):
            created_pages_by_ref[document["ref"]] = page
        pending_doc_parents.append((page, document.get("parent_ref")))

    for page, parent_ref in pending_doc_parents:
        if parent_ref:
            page.parent = created_pages_by_ref.get(parent_ref)

    for phase in starter_plan.get("tasks", []):
        phase_due_date = milestone(phase.get("due_percent", 100))
        rendered_phase_title = " ".join(_render_project_template_text(phase["title"], template_context).strip().split())
        rendered_phase_assignee = (
            " ".join(_render_project_template_text(phase.get("assignee"), template_context).strip().split())
            or delivery_owner
        )
        parent_task = InternalTask(
            project=project,
            title=rendered_phase_title,
            assignee=rendered_phase_assignee,
            priority=phase["priority"],
            status=phase["status"],
            due_date=phase_due_date,
        )
        db.session.add(parent_task)

        for subtask in phase.get("subtasks", []):
            rendered_subtask_title = " ".join(
                _render_project_template_text(subtask["title"], template_context).strip().split()
            )
            rendered_subtask_assignee = (
                " ".join(_render_project_template_text(subtask.get("assignee"), template_context).strip().split())
                or rendered_phase_assignee
            )
            db.session.add(
                InternalTask(
                    project=project,
                    parent_task=parent_task,
                    title=rendered_subtask_title,
                    assignee=rendered_subtask_assignee,
                    priority=subtask["priority"],
                    status=subtask["status"],
                    due_date=milestone(subtask.get("due_percent", phase.get("due_percent", 100))),
                )
            )


def _get_or_create_direct_channel(
    current_user: InternalUser,
    recipient_user: InternalUser,
) -> tuple[InternalMessageChannel, bool]:
    low_id, high_id = sorted((current_user.id, recipient_user.id))
    existing_channel = InternalMessageChannel.query.filter_by(
        channel_type="direct",
        direct_user_low_id=low_id,
        direct_user_high_id=high_id,
    ).first()
    if existing_channel:
        return existing_channel, False

    channel = InternalMessageChannel(
        channel_type="direct",
        direct_user_low_id=low_id,
        direct_user_high_id=high_id,
        creator=current_user,
    )
    channel.members = [current_user, recipient_user]
    db.session.add(channel)
    return channel, True


def _internal_user_can_access_channel(
    channel: InternalMessageChannel,
    user: InternalUser,
) -> bool:
    if channel.channel_type == "project":
        return True
    return any(member.id == user.id for member in channel.members)


def _internal_channel_label(channel: InternalMessageChannel, user: InternalUser) -> tuple[str, str]:
    channel_type = (channel.channel_type or "").strip().lower()
    if channel_type not in INTERNAL_MESSAGE_CHANNEL_TYPES:
        channel_type = "group"

    if channel_type == "project":
        if channel.project and channel.project.client:
            return channel.project.name, channel.project.client.name
        if channel.project:
            return channel.project.name, "Project Channel"
        return channel.name or "Project Channel", "Project Channel"

    if channel_type == "direct":
        peer_user = next((member for member in channel.members if member.id != user.id), None)
        if peer_user:
            return peer_user.full_name, f"{peer_user.role.title()} · {peer_user.email}"
        return "Direct Message", "Peer channel"

    member_count = len(channel.members)
    member_suffix = "member" if member_count == 1 else "members"
    return channel.name or "Group Channel", f"{member_count} {member_suffix}"


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


def _safe_internal_referrer_url() -> str | None:
    raw_referrer = (request.referrer or "").strip()
    if not raw_referrer:
        return None

    parsed = urlparse(raw_referrer)
    if not parsed.path.startswith("/internal"):
        return None

    if parsed.query:
        return f"{parsed.path}?{parsed.query}"
    return parsed.path


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
        "current_internal_user_is_senior": _internal_user_is_senior(getattr(g, "internal_user", None)),
        "internal_status_class": _internal_status_class,
        "internal_priority_class": _internal_priority_class,
        "internal_risk_severity_class": _internal_risk_severity_class,
        "internal_user_is_senior": _internal_user_is_senior,
        "csrf_token": _internal_csrf_token,
        "public_demo_url": _public_demo_url,
    }


def internal_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not getattr(g, "internal_user", None):
            next_target = _safe_next_url(request.path)
            return redirect(url_for("main.internal_login", next=next_target))
        return view_func(*args, **kwargs)

    return wrapped


def internal_senior_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not getattr(g, "internal_user", None):
            next_target = _safe_next_url(request.path)
            return redirect(url_for("main.internal_login", next=next_target))
        if not _internal_user_is_senior(g.internal_user):
            flash("Senior access is required for that action.", "warning")
            return redirect(_safe_internal_referrer_url() or url_for("main.internal_dashboard"))
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
    contact_form_state, contact_form_errors = _pop_public_contact_feedback()
    selected_service = request.args.get("service")
    if selected_service and not contact_form_state.get("service"):
        contact_form_state["service"] = selected_service
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
        contact_form_state=contact_form_state,
        contact_form_errors=contact_form_errors,
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
    current_user = g.internal_user
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
        InternalTask.query.options(selectinload(InternalTask.project)).filter(InternalTask.status != "done")
        .order_by(InternalTask.due_date.is_(None), InternalTask.due_date.asc(), InternalTask.created_at.desc())
        .limit(8)
        .all()
    )
    open_task_records = (
        InternalTask.query.options(selectinload(InternalTask.project))
        .filter(InternalTask.status != "done")
        .all()
    )
    recent_projects = (
        InternalProject.query.options(
            selectinload(InternalProject.client),
            selectinload(InternalProject.tasks),
            selectinload(InternalProject.milestones),
            selectinload(InternalProject.risks),
            selectinload(InternalProject.status_updates),
        )
        .order_by(InternalProject.created_at.desc())
        .limit(6)
        .all()
    )
    portfolio_projects = (
        InternalProject.query.options(
            selectinload(InternalProject.client),
            selectinload(InternalProject.tasks),
            selectinload(InternalProject.milestones),
            selectinload(InternalProject.risks),
            selectinload(InternalProject.status_updates),
        )
        .order_by(InternalProject.name.asc())
        .all()
    )
    announcements = InternalAnnouncement.query.order_by(InternalAnnouncement.created_at.desc()).limit(4).all()
    recent_updates = (
        InternalProjectStatusUpdate.query.options(
            selectinload(InternalProjectStatusUpdate.project).selectinload(InternalProject.client),
            selectinload(InternalProjectStatusUpdate.author),
        )
        .order_by(InternalProjectStatusUpdate.created_at.desc())
        .limit(5)
        .all()
    )
    total_resources = InternalResource.query.count()
    resources_without_tags = InternalResource.query.filter(~InternalResource.tags.any()).count()
    resources_without_links = InternalResource.query.filter(
        ~InternalResource.projects.any(),
        ~InternalResource.tasks.any(),
    ).count()
    resources_linked = total_resources - resources_without_links
    active_portfolio_projects = [
        project for project in portfolio_projects if (project.status or "").strip().lower() != "completed"
    ]
    portfolio_progress = (
        int(sum(project.progress_percent for project in active_portfolio_projects) / len(active_portfolio_projects))
        if active_portfolio_projects
        else 0
    )
    stage_breakdown = [
        {
            "stage": stage,
            "label": stage.title(),
            "count": sum(
                1
                for project in active_portfolio_projects
                if (project.stage or "").strip().lower() == stage
            ),
        }
        for stage in INTERNAL_PROJECT_STAGES
    ]
    at_risk_project_records = [
        project
        for project in active_portfolio_projects
        if (project.status or "").strip().lower() in {"at-risk", "blocked"}
        or project.open_risks_count > 0
        or project.overdue_milestones_count > 0
    ]
    at_risk_projects = sorted(
        at_risk_project_records,
        key=lambda project: (
            0 if (project.status or "").strip().lower() == "blocked" else 1,
            -project.open_risks_count,
            -project.overdue_milestones_count,
            project.next_milestone.due_date if project.next_milestone and project.next_milestone.due_date else date.max,
            project.name.lower(),
        ),
    )[:5]
    upcoming_milestones = sorted(
        [
            {"project": project, "milestone": milestone}
            for project in active_portfolio_projects
            for milestone in project.milestones
            if not milestone.is_done and milestone.due_date is not None
        ],
        key=lambda item: (
            item["milestone"].due_date or date.max,
            _timeline_status_sort_rank(item["milestone"].status),
            item["project"].name.lower(),
        ),
    )[:8]
    workload_by_assignee: dict[str, dict] = {}
    current_user_name = (current_user.full_name or "").strip().lower() if current_user else ""
    my_focus_tasks = []
    for task in open_task_records:
        assignee_label = (task.assignee or "Unassigned").strip() or "Unassigned"
        workload = workload_by_assignee.setdefault(
            assignee_label,
            {"assignee": assignee_label, "open_tasks": 0, "high_priority": 0, "blocked": 0},
        )
        workload["open_tasks"] += 1
        if (task.priority or "").strip().lower() == "high":
            workload["high_priority"] += 1
        if (task.status or "").strip().lower() == "blocked":
            workload["blocked"] += 1
        if current_user_name and assignee_label.lower() == current_user_name:
            my_focus_tasks.append(task)
    team_workload_cards = sorted(
        workload_by_assignee.values(),
        key=lambda item: (-item["open_tasks"], -item["high_priority"], item["assignee"].lower()),
    )[:6]
    my_focus_tasks = sorted(my_focus_tasks, key=_task_sort_key)[:5]
    journey_steps = [
        {
            "title": "Capture Lead Context",
            "body": "Use enquiry notes to set the first delivery objective.",
            "href": url_for("main.enquire"),
            "label": "View Enquiry Page",
        },
        {
            "title": "Create Client + Project",
            "body": "Register the client and create a scoped project.",
            "href": url_for("main.internal_clients"),
            "label": "Open Client Registry",
        },
        {
            "title": "Plan Execution",
            "body": "Break work into tasks and order the priority queue.",
            "href": url_for("main.internal_todos", view="priority"),
            "label": "Open To-Do Queue",
        },
        {
            "title": "Link Knowledge",
            "body": "Link docs to projects and tasks for reuse.",
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
            "at_risk_projects": len(at_risk_project_records),
            "portfolio_progress": portfolio_progress,
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
        recent_updates=recent_updates,
        at_risk_projects=at_risk_projects,
        upcoming_milestones=upcoming_milestones,
        team_workload_cards=team_workload_cards,
        my_focus_tasks=my_focus_tasks,
        stage_breakdown=stage_breakdown,
    )


@main_bp.route("/internal/calendar")
@internal_login_required
def internal_calendar():
    today = date.today()
    selected_month = _month_start(_parse_month(request.args.get("month")) or today)
    month_end = _next_month_start(selected_month) - timedelta(days=1)
    grid_start = selected_month - timedelta(days=selected_month.weekday())
    grid_end = grid_start + timedelta(days=41)

    kind_filter = (request.args.get("kind") or "all").strip().lower()
    if kind_filter not in INTERNAL_CALENDAR_EVENT_KINDS:
        kind_filter = "all"

    def include_kind(kind: str) -> bool:
        return kind_filter in {"all", kind}

    visible_events: list[dict] = []

    if include_kind("task"):
        task_records = (
            InternalTask.query.options(
                selectinload(InternalTask.project).selectinload(InternalProject.client),
            )
            .filter(
                InternalTask.status != "done",
                InternalTask.due_date.isnot(None),
                InternalTask.due_date >= grid_start,
                InternalTask.due_date <= grid_end,
            )
            .order_by(InternalTask.due_date.asc(), InternalTask.created_at.asc())
            .all()
        )
        for task in task_records:
            kind_meta = _internal_calendar_kind_meta("task")
            visible_events.append(
                {
                    "id": f"task-{task.id}",
                    "kind": "task",
                    "kind_label": kind_meta["label"],
                    "kind_icon": kind_meta["icon"],
                    "kind_badge_class": kind_meta["badge_class"],
                    "kind_dot_class": kind_meta["dot_class"],
                    "due_date": task.due_date,
                    "title": task.title,
                    "status_label": (task.status or "todo").replace("-", " ").title(),
                    "status_class": _internal_status_class(task.status),
                    "project_name": task.project.name if task.project else "",
                    "project_id": task.project_id,
                    "meta": f"{task.project.name if task.project else 'Unscoped'} · {(task.assignee or 'Unassigned').strip() or 'Unassigned'}",
                    "href": url_for("main.internal_todos", view="priority", project_id=task.project_id),
                }
            )

    if include_kind("milestone"):
        milestone_records = (
            InternalProjectMilestone.query.options(
                selectinload(InternalProjectMilestone.project).selectinload(InternalProject.client),
            )
            .filter(
                InternalProjectMilestone.status != "done",
                InternalProjectMilestone.due_date.isnot(None),
                InternalProjectMilestone.due_date >= grid_start,
                InternalProjectMilestone.due_date <= grid_end,
            )
            .order_by(InternalProjectMilestone.due_date.asc(), InternalProjectMilestone.created_at.asc())
            .all()
        )
        for milestone in milestone_records:
            kind_meta = _internal_calendar_kind_meta("milestone")
            visible_events.append(
                {
                    "id": f"milestone-{milestone.id}",
                    "kind": "milestone",
                    "kind_label": kind_meta["label"],
                    "kind_icon": kind_meta["icon"],
                    "kind_badge_class": kind_meta["badge_class"],
                    "kind_dot_class": kind_meta["dot_class"],
                    "due_date": milestone.due_date,
                    "title": milestone.title,
                    "status_label": (milestone.status or "planned").replace("-", " ").title(),
                    "status_class": _internal_status_class(milestone.status),
                    "project_name": milestone.project.name if milestone.project else "",
                    "project_id": milestone.project_id,
                    "meta": f"{milestone.project.name if milestone.project else 'No project'} · {milestone.owner_name}",
                    "href": _project_workspace_url(milestone.project_id, "#milestones"),
                }
            )

    if include_kind("deliverable"):
        deliverable_records = (
            InternalProjectDeliverable.query.options(
                selectinload(InternalProjectDeliverable.project).selectinload(InternalProject.client),
            )
            .filter(
                InternalProjectDeliverable.status != "delivered",
                InternalProjectDeliverable.due_date.isnot(None),
                InternalProjectDeliverable.due_date >= grid_start,
                InternalProjectDeliverable.due_date <= grid_end,
            )
            .order_by(InternalProjectDeliverable.due_date.asc(), InternalProjectDeliverable.created_at.asc())
            .all()
        )
        for deliverable in deliverable_records:
            kind_meta = _internal_calendar_kind_meta("deliverable")
            visible_events.append(
                {
                    "id": f"deliverable-{deliverable.id}",
                    "kind": "deliverable",
                    "kind_label": kind_meta["label"],
                    "kind_icon": kind_meta["icon"],
                    "kind_badge_class": kind_meta["badge_class"],
                    "kind_dot_class": kind_meta["dot_class"],
                    "due_date": deliverable.due_date,
                    "title": deliverable.title,
                    "status_label": (deliverable.status or "planned").replace("-", " ").title(),
                    "status_class": _internal_status_class(deliverable.status),
                    "project_name": deliverable.project.name if deliverable.project else "",
                    "project_id": deliverable.project_id,
                    "meta": f"{deliverable.project.name if deliverable.project else 'No project'} · {deliverable.owner_name}",
                    "href": _project_workspace_url(deliverable.project_id, "#deliverables"),
                }
            )

    if include_kind("risk"):
        risk_records = (
            InternalProjectRisk.query.options(
                selectinload(InternalProjectRisk.project).selectinload(InternalProject.client),
            )
            .filter(
                InternalProjectRisk.status != "closed",
                InternalProjectRisk.due_date.isnot(None),
                InternalProjectRisk.due_date >= grid_start,
                InternalProjectRisk.due_date <= grid_end,
            )
            .order_by(InternalProjectRisk.due_date.asc(), InternalProjectRisk.created_at.asc())
            .all()
        )
        for risk in risk_records:
            kind_meta = _internal_calendar_kind_meta("risk")
            visible_events.append(
                {
                    "id": f"risk-{risk.id}",
                    "kind": "risk",
                    "kind_label": kind_meta["label"],
                    "kind_icon": kind_meta["icon"],
                    "kind_badge_class": kind_meta["badge_class"],
                    "kind_dot_class": kind_meta["dot_class"],
                    "due_date": risk.due_date,
                    "title": risk.title,
                    "status_label": (risk.severity or "medium").title(),
                    "status_class": _internal_risk_severity_class(risk.severity),
                    "project_name": risk.project.name if risk.project else "",
                    "project_id": risk.project_id,
                    "meta": f"{risk.project.name if risk.project else 'No project'} · {(risk.status or 'open').replace('-', ' ').title()}",
                    "href": _project_workspace_url(risk.project_id, "#risks"),
                }
            )

    if include_kind("project"):
        project_records = (
            InternalProject.query.options(selectinload(InternalProject.client))
            .filter(
                InternalProject.status != "completed",
                InternalProject.due_date.isnot(None),
                InternalProject.due_date >= grid_start,
                InternalProject.due_date <= grid_end,
            )
            .order_by(InternalProject.due_date.asc(), InternalProject.created_at.asc())
            .all()
        )
        for project in project_records:
            kind_meta = _internal_calendar_kind_meta("project")
            visible_events.append(
                {
                    "id": f"project-{project.id}",
                    "kind": "project",
                    "kind_label": kind_meta["label"],
                    "kind_icon": kind_meta["icon"],
                    "kind_badge_class": kind_meta["badge_class"],
                    "kind_dot_class": kind_meta["dot_class"],
                    "due_date": project.due_date,
                    "title": project.name,
                    "status_label": (project.status or "on-track").replace("-", " ").title(),
                    "status_class": _internal_status_class(project.status),
                    "project_name": project.name,
                    "project_id": project.id,
                    "meta": f"{project.client.name if project.client else 'No client'} · {(project.stage or 'discovery').title()}",
                    "href": url_for("main.internal_project_workspace", project_id=project.id),
                }
            )

    visible_events = sorted(visible_events, key=_internal_calendar_event_sort_key)
    events_by_date: dict[date, list[dict]] = {}
    for event in visible_events:
        events_by_date.setdefault(event["due_date"], []).append(event)

    calendar_weeks: list[list[dict]] = []
    for week_index in range(6):
        week_days: list[dict] = []
        for day_index in range(7):
            calendar_day = grid_start + timedelta(days=(week_index * 7) + day_index)
            day_events = events_by_date.get(calendar_day, [])
            week_days.append(
                {
                    "date": calendar_day,
                    "is_current_month": calendar_day.month == selected_month.month and calendar_day.year == selected_month.year,
                    "is_today": calendar_day == today,
                    "events": day_events,
                    "visible_events": day_events[:3],
                    "overflow_count": max(0, len(day_events) - 3),
                }
            )
        calendar_weeks.append(week_days)

    month_events = [
        event for event in visible_events if selected_month <= event["due_date"] <= month_end
    ]
    month_event_counts = {
        "task": InternalTask.query.filter(
            InternalTask.status != "done",
            InternalTask.due_date.isnot(None),
            InternalTask.due_date >= selected_month,
            InternalTask.due_date <= month_end,
        ).count(),
        "milestone": InternalProjectMilestone.query.filter(
            InternalProjectMilestone.status != "done",
            InternalProjectMilestone.due_date.isnot(None),
            InternalProjectMilestone.due_date >= selected_month,
            InternalProjectMilestone.due_date <= month_end,
        ).count(),
        "deliverable": InternalProjectDeliverable.query.filter(
            InternalProjectDeliverable.status != "delivered",
            InternalProjectDeliverable.due_date.isnot(None),
            InternalProjectDeliverable.due_date >= selected_month,
            InternalProjectDeliverable.due_date <= month_end,
        ).count(),
        "risk": InternalProjectRisk.query.filter(
            InternalProjectRisk.status != "closed",
            InternalProjectRisk.due_date.isnot(None),
            InternalProjectRisk.due_date >= selected_month,
            InternalProjectRisk.due_date <= month_end,
        ).count(),
        "project": InternalProject.query.filter(
            InternalProject.status != "completed",
            InternalProject.due_date.isnot(None),
            InternalProject.due_date >= selected_month,
            InternalProject.due_date <= month_end,
        ).count(),
    }
    all_month_event_count = sum(month_event_counts.values())
    month_project_ids = {event["project_id"] for event in month_events if event.get("project_id")}
    overdue_count = sum(1 for event in month_events if event["due_date"] < today)
    next_seven_days_count = sum(
        1 for event in month_events if today <= event["due_date"] <= today + timedelta(days=6)
    )
    earliest_due = month_events[0]["due_date"] if month_events else None

    def calendar_url(target_month: date, target_kind: str | None = None) -> str:
        kwargs = {"month": target_month.strftime("%Y-%m")}
        effective_kind = target_kind or kind_filter
        if effective_kind != "all":
            kwargs["kind"] = effective_kind
        return url_for("main.internal_calendar", **kwargs)

    kind_filters = [
        {
            "value": "all",
            "label": "All items",
            "count": all_month_event_count,
            "href": calendar_url(selected_month, "all"),
            "is_active": kind_filter == "all",
        }
    ]
    for kind in INTERNAL_CALENDAR_EVENT_KINDS:
        if kind == "all":
            continue
        kind_filters.append(
            {
                "value": kind,
                "label": _internal_calendar_kind_meta(kind)["label"],
                "count": month_event_counts.get(kind, 0),
                "href": calendar_url(selected_month, kind),
                "is_active": kind_filter == kind,
            }
        )

    return render_template(
        "internal/calendar.html",
        selected_month=selected_month,
        selected_month_label=selected_month.strftime("%B %Y"),
        previous_month_url=calendar_url(_previous_month_start(selected_month)),
        next_month_url=calendar_url(_next_month_start(selected_month)),
        today_month_url=calendar_url(_month_start(today)),
        weekday_labels=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        calendar_weeks=calendar_weeks,
        month_events=month_events,
        month_summary={
            "items": len(month_events),
            "projects": len(month_project_ids),
            "overdue": overdue_count,
            "next_seven_days": next_seven_days_count,
            "earliest_due": earliest_due,
        },
        active_kind_filter=kind_filter,
        active_kind_label="All items" if kind_filter == "all" else _internal_calendar_kind_meta(kind_filter)["label"],
        kind_filters=kind_filters,
        legend_items=[_internal_calendar_kind_meta(kind) for kind in INTERNAL_CALENDAR_EVENT_KINDS if kind != "all"],
    )


@main_bp.route("/internal/go")
@internal_login_required
def internal_go():
    raw_query = (request.args.get("q") or "").strip()
    if not raw_query:
        return redirect(url_for("main.internal_dashboard"))

    query = " ".join(raw_query.split())
    normalized = query.lower()
    scope = "any"
    prefixes = (
        ("project:", "project"),
        ("project ", "project"),
        ("client:", "client"),
        ("client ", "client"),
        ("task:", "task"),
        ("task ", "task"),
        ("page:", "docpage"),
        ("page ", "docpage"),
        ("wiki:", "docpage"),
        ("wiki ", "docpage"),
        ("doc:", "docpage"),
        ("docs:", "docpage"),
        ("resource:", "resource"),
        ("message:", "message"),
        ("channel:", "message"),
    )
    for prefix, scope_name in prefixes:
        if normalized.startswith(prefix):
            query = " ".join(query[len(prefix) :].split())
            normalized = query.lower()
            scope = scope_name
            break

    if not query:
        return redirect(url_for("main.internal_dashboard"))

    quick_targets = {
        "dashboard": url_for("main.internal_dashboard"),
        "home": url_for("main.internal_dashboard"),
        "todos": url_for("main.internal_todos"),
        "todo": url_for("main.internal_todos"),
        "tasks": url_for("main.internal_todos"),
        "priority": url_for("main.internal_todos", view="priority"),
        "priority queue": url_for("main.internal_todos", view="priority"),
        "calendar": url_for("main.internal_calendar"),
        "schedule": url_for("main.internal_calendar"),
        "projects": url_for("main.internal_projects"),
        "project": url_for("main.internal_projects"),
        "new project": f"{url_for('main.internal_projects')}#new-project",
        "workspace": url_for("main.internal_projects"),
        "clients": url_for("main.internal_clients"),
        "client": url_for("main.internal_clients"),
        "new client": f"{url_for('main.internal_clients')}#new-client",
        "add task": f"{url_for('main.internal_todos')}#new-task",
        "new task": f"{url_for('main.internal_todos')}#new-task",
        "messages": url_for("main.internal_messages"),
        "message": url_for("main.internal_messages"),
        "docs": url_for("main.internal_docs"),
        "doc": url_for("main.internal_docs"),
        "wiki": url_for("main.internal_docs"),
        "pages": url_for("main.internal_docs"),
        "resources": url_for("main.internal_resources"),
        "resource": url_for("main.internal_resources"),
        "knowledge": url_for("main.internal_resources"),
        "library": url_for("main.internal_resources"),
    }
    if normalized in quick_targets:
        return redirect(quick_targets[normalized])

    if normalized.startswith("/internal/"):
        return redirect(normalized)
    if normalized.startswith("internal/"):
        return redirect(f"/{normalized}")

    query_pattern = f"%{query}%"

    def scope_allows(target_scope: str) -> bool:
        return scope in {"any", target_scope}

    if scope_allows("project"):
        project_match = (
            InternalProject.query.filter(InternalProject.name.ilike(query_pattern))
            .order_by(InternalProject.created_at.desc())
            .first()
        )
        if project_match:
            flash(f"Opened project '{project_match.name}'.", "success")
            return redirect(url_for("main.internal_project_workspace", project_id=project_match.id))

    if scope_allows("client"):
        client_match = (
            InternalClient.query.filter(
                or_(
                    InternalClient.name.ilike(query_pattern),
                    InternalClient.industry.ilike(query_pattern),
                    InternalClient.account_owner.ilike(query_pattern),
                )
            )
            .order_by(InternalClient.name.asc())
            .first()
        )
        if client_match:
            flash(f"Opened client '{client_match.name}'.", "success")
            return redirect(url_for("main.internal_projects", client_id=client_match.id))

    if scope_allows("task"):
        task_match = (
            InternalTask.query.options(selectinload(InternalTask.project))
            .filter(
                or_(
                    InternalTask.title.ilike(query_pattern),
                    InternalTask.assignee.ilike(query_pattern),
                )
            )
            .order_by(InternalTask.created_at.desc())
            .first()
        )
        if task_match:
            flash(f"Opened task queue for '{task_match.project.name}'.", "success")
            return redirect(url_for("main.internal_todos", view="priority", project_id=task_match.project_id))

    if scope_allows("docpage"):
        doc_page_match = (
            InternalDocPage.query.filter(
                or_(
                    InternalDocPage.title.ilike(query_pattern),
                    InternalDocPage.summary.ilike(query_pattern),
                    InternalDocPage.body.ilike(query_pattern),
                )
            )
            .order_by(InternalDocPage.updated_at.desc(), InternalDocPage.title.asc())
            .first()
        )
        if doc_page_match:
            flash(f"Opened workspace doc '{doc_page_match.title}'.", "success")
            return redirect(url_for("main.internal_docs", doc_slug=doc_page_match.slug))

    if scope_allows("resource"):
        resource_match = (
            InternalResource.query.filter(
                or_(
                    InternalResource.title.ilike(query_pattern),
                    InternalResource.description.ilike(query_pattern),
                    InternalResource.category.ilike(query_pattern),
                )
            )
            .order_by(InternalResource.title.asc())
            .first()
        )
        if resource_match:
            flash(f"Opened documents matching '{resource_match.title}'.", "success")
            return redirect(url_for("main.internal_resources", q=resource_match.title))

    if scope_allows("message"):
        channel_match = (
            InternalMessageChannel.query.filter(
                InternalMessageChannel.name.isnot(None),
                InternalMessageChannel.name.ilike(query_pattern),
            )
            .order_by(InternalMessageChannel.updated_at.desc(), InternalMessageChannel.created_at.desc())
            .first()
        )
        if channel_match and _internal_user_can_access_channel(channel_match, g.internal_user):
            flash(f"Opened channel '{channel_match.name}'.", "success")
            return redirect(url_for("main.internal_messages", channel_id=channel_match.id))
        if channel_match:
            return redirect(url_for("main.internal_messages"))

        user_match = (
            InternalUser.query.filter(
                InternalUser.is_active.is_(True),
                InternalUser.full_name.ilike(query_pattern),
            )
            .order_by(InternalUser.full_name.asc())
            .first()
        )
        if user_match and user_match.id != g.internal_user.id:
            flash(f"Found consultant '{user_match.full_name}'. Start a direct channel from Messages.", "success")
            return redirect(url_for("main.internal_messages"))

    flash(
        "No exact match found. Try page names or prefixes: project:, client:, task:, page:, resource:, message:.",
        "warning",
    )
    return redirect(url_for("main.internal_dashboard"))


@main_bp.route("/internal/clients")
@internal_login_required
def internal_clients():
    clients = InternalClient.query.order_by(InternalClient.status.asc(), InternalClient.name.asc()).all()
    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )
    client_statuses = ("active", "at-risk", "paused", "completed")
    editable_client = None
    if _internal_user_is_senior(getattr(g, "internal_user", None)):
        edit_client_id = _parse_positive_int(request.args.get("edit_id"))
        if edit_client_id:
            editable_client = next((client for client in clients if client.id == edit_client_id), None)
    return render_template(
        "internal/clients.html",
        clients=clients,
        active_internal_users=active_internal_users,
        client_statuses=client_statuses,
        editable_client=editable_client,
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


@main_bp.route("/internal/clients/<int:client_id>/update", methods=["POST"])
@internal_senior_required
def internal_client_update(client_id: int):
    client_record = db.session.get(InternalClient, client_id)
    if not client_record:
        flash("Client not found.", "warning")
        return redirect(url_for("main.internal_clients"))

    name = " ".join((request.form.get("name") or "").strip().split())
    industry = " ".join((request.form.get("industry") or "").strip().split())
    account_owner = " ".join((request.form.get("account_owner") or "").strip().split())
    status = (request.form.get("status") or "active").strip().lower()
    notes = (request.form.get("notes") or "").strip()
    if status not in {"active", "at-risk", "paused", "completed"}:
        status = "active"

    if not name or not industry or not account_owner:
        flash("Client name, industry, and account owner are required.", "warning")
        return redirect(url_for("main.internal_clients", edit_id=client_id))

    existing_client = InternalClient.query.filter(InternalClient.name.ilike(name)).first()
    if existing_client and existing_client.id != client_id:
        flash("A client with this name already exists.", "warning")
        return redirect(url_for("main.internal_clients", edit_id=client_id))

    client_record.name = name
    client_record.industry = industry
    client_record.account_owner = account_owner
    client_record.status = status
    client_record.notes = notes or None
    db.session.commit()
    flash(f"Client '{name}' updated.", "success")
    return redirect(url_for("main.internal_clients"))


@main_bp.route("/internal/clients/<int:client_id>/delete", methods=["POST"])
@internal_senior_required
def internal_client_delete(client_id: int):
    client_record = db.session.get(InternalClient, client_id)
    if not client_record:
        flash("Client not found.", "warning")
        return redirect(url_for("main.internal_clients"))

    client_name = client_record.name
    project_count = len(client_record.projects)
    for project in client_record.projects:
        _prepare_project_for_delete(project)

    db.session.delete(client_record)
    db.session.commit()
    if project_count:
        flash(f"Client '{client_name}' deleted with {project_count} linked project(s).", "success")
    else:
        flash(f"Client '{client_name}' deleted.", "success")
    return redirect(url_for("main.internal_clients"))


@main_bp.route("/internal/projects")
@internal_login_required
def internal_projects():
    selected_client_id: int | None = None
    selected_client_raw = (request.args.get("client_id") or "").strip()
    selected_starter_plan_category = _normalize_industry_category(request.args.get("starter_plan_category"))
    if selected_client_raw:
        try:
            selected_client_candidate = int(selected_client_raw)
        except ValueError:
            selected_client_candidate = None
        if selected_client_candidate and db.session.get(InternalClient, selected_client_candidate):
            selected_client_id = selected_client_candidate

    all_projects = (
        InternalProject.query.options(
            selectinload(InternalProject.client),
            selectinload(InternalProject.owner),
            selectinload(InternalProject.resources),
            selectinload(InternalProject.message_channel),
            selectinload(InternalProject.milestones),
            selectinload(InternalProject.deliverables),
            selectinload(InternalProject.risks),
            selectinload(InternalProject.status_updates),
        )
        .order_by(InternalProject.status.asc(), InternalProject.name.asc())
        .all()
    )
    selected_client = db.session.get(InternalClient, selected_client_id) if selected_client_id else None
    projects = [
        project for project in all_projects if not selected_client_id or project.client_id == selected_client_id
    ]
    project_cards = []
    for project in projects:
        total_tasks = project.total_tasks_count
        completed_tasks = project.completed_tasks_count
        progress = project.progress_percent
        project_cards.append(
            {
                "project": project,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress": progress,
                "open_risks": project.open_risks_count,
                "milestones": len(project.milestones),
                "deliverables": len(project.deliverables),
                "latest_update": project.latest_status_update,
            }
        )

    clients = InternalClient.query.order_by(InternalClient.name.asc()).all()
    starter_plan_categories = _project_starter_plan_categories(all_projects, clients)
    if selected_starter_plan_category not in starter_plan_categories:
        selected_starter_plan_category = DEFAULT_PROJECT_INDUSTRY_CATEGORY

    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )
    default_project_timeline_days = DEFAULT_PROJECT_TIMELINE_DAYS
    default_project_due_date = date.today() + timedelta(days=default_project_timeline_days)
    starter_plan_editor = _project_starter_plan_editor_context(selected_starter_plan_category)
    return render_template(
        "internal/projects.html",
        project_cards=project_cards,
        clients=clients,
        active_internal_users=active_internal_users,
        project_stages=INTERNAL_PROJECT_STAGES,
        project_statuses=INTERNAL_PROJECT_STATUSES,
        project_timeline_presets=PROJECT_TIMELINE_PRESETS,
        default_project_timeline_days=default_project_timeline_days,
        default_project_due_date=default_project_due_date,
        selected_client_id=selected_client_id,
        selected_client=selected_client,
        project_industry_categories=starter_plan_categories,
        selected_starter_plan_category=selected_starter_plan_category,
        starter_plan_categories=starter_plan_categories,
        starter_plan_category=starter_plan_editor["starter_plan_category"],
        starter_plan_category_label=starter_plan_editor["starter_plan_category_label"],
        starter_plan_source=starter_plan_editor["starter_plan_source"],
        starter_plan_template_text=starter_plan_editor["starter_plan_template_text"],
        starter_plan_updated_at=starter_plan_editor["starter_plan_updated_at"],
        starter_plan_updated_by=starter_plan_editor["starter_plan_updated_by"],
        starter_plan_variables=starter_plan_editor["starter_plan_variables"],
        starter_plan_stats=starter_plan_editor["starter_plan_stats"],
    )


@main_bp.route("/internal/projects/starter-plan", methods=["POST"])
@internal_senior_required
def internal_project_starter_plan_update():
    starter_plan_category = _normalize_industry_category(request.form.get("starter_plan_category"))
    raw_template = (request.form.get("starter_plan_template") or "").strip()
    if not raw_template:
        flash("Automation template cannot be empty.", "warning")
        return redirect(
            f"{url_for('main.internal_projects', starter_plan_category=starter_plan_category)}#starter-plan-template"
        )

    try:
        parsed_template = json.loads(raw_template)
    except json.JSONDecodeError as exc:
        flash(
            f"Automation template must be valid JSON (line {exc.lineno}, column {exc.colno}).",
            "warning",
        )
        return redirect(
            f"{url_for('main.internal_projects', starter_plan_category=starter_plan_category)}#starter-plan-template"
        )

    normalized_template, error_message = _normalize_project_starter_plan_template(parsed_template)
    if error_message or not normalized_template:
        flash(error_message or "Invalid automation template.", "warning")
        return redirect(
            f"{url_for('main.internal_projects', starter_plan_category=starter_plan_category)}#starter-plan-template"
        )

    template_record = _project_starter_plan_record(starter_plan_category)
    serialized_template = _serialize_project_starter_plan_template(normalized_template)
    if not template_record:
        template_record = InternalProjectStarterPlan(
            name=starter_plan_category,
            template_json=serialized_template,
            updated_by=getattr(g, "internal_user", None),
        )
        db.session.add(template_record)
    else:
        template_record.name = starter_plan_category
        template_record.template_json = serialized_template
        template_record.updated_by = getattr(g, "internal_user", None)

    db.session.commit()
    flash(
        f"Automation template updated for {_industry_category_label(starter_plan_category)}.",
        "success",
    )
    return redirect(
        f"{url_for('main.internal_projects', starter_plan_category=starter_plan_category)}#starter-plan-template"
    )


@main_bp.route("/internal/projects/add", methods=["POST"])
@internal_login_required
def internal_project_add():
    name = " ".join((request.form.get("name") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    stage = _normalize_internal_project_stage(request.form.get("stage"))
    status = _normalize_internal_project_status(request.form.get("status"))
    raw_due_date = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(raw_due_date)
    timeline_days = _normalize_project_timeline_days(request.form.get("timeline_days"))
    industry_category = _normalize_industry_category(request.form.get("industry_category"))
    template_variables_raw = (request.form.get("template_variables") or "").strip()

    client_id_raw = (request.form.get("client_id") or "").strip()
    owner_id_raw = (request.form.get("owner_id") or "").strip()
    client_mode = (request.form.get("client_mode") or "existing").strip().lower()
    create_starter_plan = "1" in request.form.getlist("create_starter_plan")
    redirect_client_id: int | None = None

    if not name or not summary:
        flash("Project name and summary are required.", "warning")
        return redirect(url_for("main.internal_projects"))

    if raw_due_date and not due_date:
        flash("Provide a valid due date.", "warning")
        return redirect(url_for("main.internal_projects"))

    runtime_template_variables, template_variables_error = _parse_project_template_runtime_variables(
        template_variables_raw
    )
    if template_variables_error or runtime_template_variables is None:
        flash(template_variables_error or "Invalid template variables.", "warning")
        return redirect(url_for("main.internal_projects"))

    if not due_date:
        due_date = date.today() + timedelta(days=timeline_days)

    new_client_name = " ".join((request.form.get("new_client_name") or "").strip().split())
    new_client_industry = " ".join((request.form.get("new_client_industry") or "").strip().split())
    new_client_account_owner = " ".join((request.form.get("new_client_account_owner") or "").strip().split())
    new_client_notes = (request.form.get("new_client_notes") or "").strip()
    new_client_status = (request.form.get("new_client_status") or "active").strip().lower()
    if new_client_status not in {"active", "at-risk", "paused", "completed"}:
        new_client_status = "active"

    created_new_client = False
    use_new_client = client_mode == "new"

    if use_new_client:
        if not new_client_name or not new_client_industry or not new_client_account_owner:
            flash("For a new client, provide name, industry, and account owner.", "warning")
            return redirect(url_for("main.internal_projects"))

        existing_client = InternalClient.query.filter(InternalClient.name.ilike(new_client_name)).first()
        if existing_client:
            client_record = existing_client
        else:
            client_record = InternalClient(
                name=new_client_name,
                industry=new_client_industry,
                account_owner=new_client_account_owner,
                status=new_client_status,
                notes=new_client_notes or None,
            )
            db.session.add(client_record)
            db.session.flush()
            created_new_client = True
    else:
        try:
            client_id = int(client_id_raw)
        except ValueError:
            flash("Select a valid client for the project.", "warning")
            return redirect(url_for("main.internal_projects"))
        client_record = db.session.get(InternalClient, client_id)
        if not client_record:
            flash("Selected client does not exist.", "warning")
            return redirect(url_for("main.internal_projects"))

    redirect_client_id = client_record.id

    owner_record = None
    if not owner_id_raw or owner_id_raw == "self":
        owner_record = getattr(g, "internal_user", None)
    elif owner_id_raw == "unassigned":
        owner_record = None
    else:
        try:
            owner_id = int(owner_id_raw)
        except ValueError:
            flash("Invalid project owner.", "warning")
            return redirect(url_for("main.internal_projects", client_id=redirect_client_id))
        owner_record = db.session.get(InternalUser, owner_id)
        if not owner_record or not owner_record.is_active:
            flash("Selected project owner is not available.", "warning")
            return redirect(url_for("main.internal_projects", client_id=redirect_client_id))

    project_record = InternalProject(
        name=name,
        client=client_record,
        owner=owner_record,
        stage=stage,
        status=status,
        due_date=due_date,
        industry_category=industry_category,
        summary=summary,
    )
    db.session.add(project_record)
    _ensure_project_message_channel(project_record, created_by=getattr(g, "internal_user", None))
    if create_starter_plan:
        owner_display_name = owner_record.full_name if owner_record else client_record.account_owner
        starter_plan_template = _load_project_starter_plan_template(industry_category)
        _apply_project_starter_plan(
            project_record,
            timeline_days=timeline_days,
            owner_display_name=owner_display_name,
            plan_template=starter_plan_template,
            runtime_variables=runtime_template_variables,
        )
    db.session.commit()
    success_notes = [f"Project '{name}' created for {client_record.name}."]
    if created_new_client:
        success_notes.append("New client profile added.")
    if create_starter_plan:
        success_notes.append("Automation template applied.")
    flash(" ".join(success_notes), "success")
    return redirect(url_for("main.internal_projects", client_id=redirect_client_id))


@main_bp.route("/internal/projects/<int:project_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_delete(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    client_id = project.client_id
    project_name = project.name
    _prepare_project_for_delete(project)
    db.session.delete(project)
    db.session.commit()
    flash(f"Project '{project_name}' deleted.", "success")
    return redirect(_project_list_redirect(client_id))


@main_bp.route("/internal/projects/<int:project_id>")
@internal_login_required
def internal_project_workspace(project_id: int):
    project = (
        InternalProject.query.options(
            selectinload(InternalProject.client),
            selectinload(InternalProject.owner),
            selectinload(InternalProject.doc_pages).selectinload(InternalDocPage.author),
            selectinload(InternalProject.resources).selectinload(InternalResource.tags),
            selectinload(InternalProject.message_channel),
            selectinload(InternalProject.tasks).selectinload(InternalTask.resources),
            selectinload(InternalProject.milestones),
            selectinload(InternalProject.deliverables),
            selectinload(InternalProject.stakeholders),
            selectinload(InternalProject.risks),
            selectinload(InternalProject.status_updates).selectinload(InternalProjectStatusUpdate.author),
        )
        .filter_by(id=project_id)
        .first_or_404()
    )
    if not project.message_channel:
        _ensure_project_message_channel(project, created_by=g.internal_user)
        db.session.commit()

    today = date.today()
    open_tasks = [task for task in project.tasks if not task.is_done]
    completed_tasks = [task for task in project.tasks if task.is_done]
    focus_tasks = sorted(open_tasks, key=_task_sort_key)[:7]
    completed_tasks_recent = sorted(
        completed_tasks,
        key=lambda task: (
            task.due_date or date.min,
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
            task.id or 0,
        ),
        reverse=True,
    )[:5]
    blocked_tasks = [task for task in open_tasks if (task.status or "").strip().lower() == "blocked"]
    overdue_tasks = [task for task in open_tasks if task.due_date is not None and task.due_date < today]
    team_workload: dict[str, dict] = {}
    for task in open_tasks:
        assignee_label = (task.assignee or "Unassigned").strip() or "Unassigned"
        workload = team_workload.setdefault(
            assignee_label,
            {"assignee": assignee_label, "open_tasks": 0, "high_priority": 0, "blocked": 0},
        )
        workload["open_tasks"] += 1
        if (task.priority or "").strip().lower() == "high":
            workload["high_priority"] += 1
        if (task.status or "").strip().lower() == "blocked":
            workload["blocked"] += 1
    team_workload_cards = sorted(
        team_workload.values(),
        key=lambda item: (-item["open_tasks"], -item["high_priority"], item["assignee"].lower()),
    )

    milestones = project.ordered_milestones
    deliverables = project.ordered_deliverables
    risks = project.ordered_risks
    stakeholders = project.ordered_stakeholders
    status_updates = sorted(
        project.status_updates,
        key=lambda update: (
            update.created_at or datetime.min.replace(tzinfo=timezone.utc),
            update.id or 0,
        ),
        reverse=True,
    )

    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )

    workspace_metrics = {
        "progress": project.progress_percent,
        "open_tasks": len(open_tasks),
        "blocked_tasks": len(blocked_tasks),
        "overdue_tasks": len(overdue_tasks),
        "milestones": len(milestones),
        "deliverables": len(deliverables),
        "open_risks": sum(1 for risk in risks if risk.is_open),
        "stakeholders": len(stakeholders),
        "resources": len(project.resources),
        "doc_pages": len(project.doc_pages),
    }
    milestone_stats = {
        "complete": sum(1 for milestone in milestones if milestone.is_done),
        "open": sum(1 for milestone in milestones if not milestone.is_done),
        "overdue": sum(
            1
            for milestone in milestones
            if milestone.due_date is not None and milestone.due_date < today and not milestone.is_done
        ),
    }
    deliverable_stats = {
        "delivered": sum(1 for deliverable in deliverables if deliverable.is_delivered),
        "in_flight": sum(1 for deliverable in deliverables if not deliverable.is_delivered),
    }
    latest_update = project.latest_status_update
    senior_user = _internal_user_is_senior(getattr(g, "internal_user", None))

    def editable_record_from_query(query_key: str, records: list):
        if not senior_user:
            return None
        record_id = _parse_positive_int(request.args.get(query_key))
        if not record_id:
            return None
        return next((record for record in records if record.id == record_id), None)

    return render_template(
        "internal/project_workspace.html",
        project=project,
        workspace_metrics=workspace_metrics,
        milestone_stats=milestone_stats,
        deliverable_stats=deliverable_stats,
        focus_tasks=focus_tasks,
        completed_tasks_recent=completed_tasks_recent,
        milestones=milestones,
        deliverables=deliverables,
        risks=risks,
        stakeholders=stakeholders,
        doc_pages=sorted(project.doc_pages, key=lambda page: page.sort_key),
        status_updates=status_updates,
        latest_update=latest_update,
        active_internal_users=active_internal_users,
        project_stages=INTERNAL_PROJECT_STAGES,
        project_statuses=INTERNAL_PROJECT_STATUSES,
        milestone_statuses=INTERNAL_MILESTONE_STATUSES,
        deliverable_statuses=INTERNAL_DELIVERABLE_STATUSES,
        risk_severities=INTERNAL_RISK_SEVERITIES,
        risk_statuses=INTERNAL_RISK_STATUSES,
        stakeholder_types=INTERNAL_STAKEHOLDER_TYPES,
        stakeholder_influence_levels=INTERNAL_STAKEHOLDER_INFLUENCE_LEVELS,
        team_workload_cards=team_workload_cards,
        today=today,
        value_estimate_input=_serialize_currency(project.value_estimate),
        editable_milestone=editable_record_from_query("edit_milestone_id", milestones),
        editable_deliverable=editable_record_from_query("edit_deliverable_id", deliverables),
        editable_risk=editable_record_from_query("edit_risk_id", risks),
        editable_stakeholder=editable_record_from_query("edit_stakeholder_id", stakeholders),
        editable_status_update=editable_record_from_query("edit_status_update_id", status_updates),
    )


@main_bp.route("/internal/projects/<int:project_id>/overview", methods=["POST"])
@internal_login_required
def internal_project_overview_update(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    name = " ".join((request.form.get("name") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    stage = _normalize_internal_project_stage(request.form.get("stage"))
    status = _normalize_internal_project_status(request.form.get("status"))
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    owner_id_raw = (request.form.get("owner_id") or "").strip()
    value_estimate_raw = request.form.get("value_estimate")
    parsed_value_estimate = _parse_currency_value(value_estimate_raw)
    anchor = "#overview"

    if not name or not summary:
        flash("Project name and summary are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if due_date_raw and not due_date:
        flash("Provide a valid project due date.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if parsed_value_estimate is ...:
        flash("Value estimate must be a valid positive number.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    owner_record = None
    if owner_id_raw == "unassigned":
        owner_record = None
    elif owner_id_raw == "self" or not owner_id_raw:
        owner_record = getattr(g, "internal_user", None)
    else:
        owner_id = _parse_positive_int(owner_id_raw)
        if not owner_id:
            flash("Select a valid project owner.", "warning")
            return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
        owner_record = db.session.get(InternalUser, owner_id)
        if not owner_record or not owner_record.is_active:
            flash("Selected project owner is not available.", "warning")
            return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    project.name = name
    project.summary = summary
    project.stage = stage
    project.status = status
    project.owner = owner_record
    project.due_date = due_date
    project.value_estimate = parsed_value_estimate
    db.session.commit()
    flash("Project overview updated.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/status-updates/add", methods=["POST"])
@internal_login_required
def internal_project_status_update_add(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    headline = " ".join((request.form.get("headline") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    wins = (request.form.get("wins") or "").strip()
    risks_text = (request.form.get("risks") or "").strip()
    next_steps = (request.form.get("next_steps") or "").strip()
    progress_percent = _normalize_progress_percent(request.form.get("progress_percent"))
    anchor = "#status-updates"

    if not headline or not summary:
        flash("Status headline and summary are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if progress_percent is None:
        flash("Progress percent must be between 0 and 100.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    db.session.add(
        InternalProjectStatusUpdate(
            project=project,
            author=getattr(g, "internal_user", None),
            headline=headline,
            summary=summary,
            wins=wins or None,
            risks=risks_text or None,
            next_steps=next_steps or None,
            progress_percent=progress_percent,
        )
    )
    db.session.commit()
    flash("Project status update published.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/status-updates/<int:update_id>/update", methods=["POST"])
@internal_senior_required
def internal_project_status_update_edit(project_id: int, update_id: int):
    status_update = db.session.get(InternalProjectStatusUpdate, update_id)
    anchor = "#status-updates"
    if not status_update or status_update.project_id != project_id:
        flash("Status update not found.", "warning")
        return redirect(_project_workspace_url(project_id, anchor))

    headline = " ".join((request.form.get("headline") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    wins = (request.form.get("wins") or "").strip()
    risks_text = (request.form.get("risks") or "").strip()
    next_steps = (request.form.get("next_steps") or "").strip()
    progress_percent = _normalize_progress_percent(request.form.get("progress_percent"))

    if not headline or not summary:
        flash("Status headline and summary are required.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_status_update_id=update_id))
    if progress_percent is None:
        flash("Progress percent must be between 0 and 100.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_status_update_id=update_id))

    status_update.headline = headline
    status_update.summary = summary
    status_update.wins = wins or None
    status_update.risks = risks_text or None
    status_update.next_steps = next_steps or None
    status_update.progress_percent = progress_percent
    db.session.commit()
    flash("Project status update updated.", "success")
    return redirect(_project_workspace_url(project_id, anchor))


@main_bp.route("/internal/projects/<int:project_id>/status-updates/<int:update_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_status_update_delete(project_id: int, update_id: int):
    status_update = db.session.get(InternalProjectStatusUpdate, update_id)
    if not status_update or status_update.project_id != project_id:
        flash("Status update not found.", "warning")
        return redirect(_project_workspace_url(project_id, "#status-updates"))

    db.session.delete(status_update)
    db.session.commit()
    flash("Project status update deleted.", "success")
    return redirect(_project_workspace_url(project_id, "#status-updates"))


@main_bp.route("/internal/projects/<int:project_id>/milestones/add", methods=["POST"])
@internal_login_required
def internal_project_milestone_add(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    status = _normalize_internal_milestone_status(request.form.get("status"))
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    notes = (request.form.get("notes") or "").strip()
    anchor = "#milestones"

    if not title or not owner_name:
        flash("Milestone title and owner are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if due_date_raw and not due_date:
        flash("Provide a valid milestone due date.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    db.session.add(
        InternalProjectMilestone(
            project=project,
            title=title,
            owner_name=owner_name,
            status=status,
            due_date=due_date,
            notes=notes or None,
        )
    )
    db.session.commit()
    flash("Milestone added to the project plan.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/milestones/<int:milestone_id>/status", methods=["POST"])
@internal_login_required
def internal_project_milestone_update_status(project_id: int, milestone_id: int):
    milestone = db.session.get(InternalProjectMilestone, milestone_id)
    if not milestone or milestone.project_id != project_id:
        flash("Milestone not found.", "warning")
        return redirect(url_for("main.internal_project_workspace", project_id=project_id))

    milestone.status = _normalize_internal_milestone_status(request.form.get("status"))
    db.session.commit()
    flash("Milestone status updated.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project_id)}#milestones")


@main_bp.route("/internal/projects/<int:project_id>/milestones/<int:milestone_id>/update", methods=["POST"])
@internal_senior_required
def internal_project_milestone_update(project_id: int, milestone_id: int):
    milestone = db.session.get(InternalProjectMilestone, milestone_id)
    anchor = "#milestones"
    if not milestone or milestone.project_id != project_id:
        flash("Milestone not found.", "warning")
        return redirect(_project_workspace_url(project_id, anchor))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    status = _normalize_internal_milestone_status(request.form.get("status"))
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    notes = (request.form.get("notes") or "").strip()

    if not title or not owner_name:
        flash("Milestone title and owner are required.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_milestone_id=milestone_id))
    if due_date_raw and not due_date:
        flash("Provide a valid milestone due date.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_milestone_id=milestone_id))

    milestone.title = title
    milestone.owner_name = owner_name
    milestone.status = status
    milestone.due_date = due_date
    milestone.notes = notes or None
    db.session.commit()
    flash("Milestone updated.", "success")
    return redirect(_project_workspace_url(project_id, anchor))


@main_bp.route("/internal/projects/<int:project_id>/milestones/<int:milestone_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_milestone_delete(project_id: int, milestone_id: int):
    milestone = db.session.get(InternalProjectMilestone, milestone_id)
    if not milestone or milestone.project_id != project_id:
        flash("Milestone not found.", "warning")
        return redirect(_project_workspace_url(project_id, "#milestones"))

    db.session.delete(milestone)
    db.session.commit()
    flash("Milestone deleted.", "success")
    return redirect(_project_workspace_url(project_id, "#milestones"))


@main_bp.route("/internal/projects/<int:project_id>/deliverables/add", methods=["POST"])
@internal_login_required
def internal_project_deliverable_add(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    status = _normalize_internal_deliverable_status(request.form.get("status"))
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    link = (request.form.get("link") or "").strip()
    description = (request.form.get("description") or "").strip()
    anchor = "#deliverables"

    if not title or not owner_name or not description:
        flash("Deliverable title, owner, and description are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if due_date_raw and not due_date:
        flash("Provide a valid deliverable due date.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if link and not _is_safe_resource_link(link):
        flash("Deliverable link must be a relative path or an http/https URL.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    db.session.add(
        InternalProjectDeliverable(
            project=project,
            title=title,
            owner_name=owner_name,
            status=status,
            due_date=due_date,
            link=link or None,
            description=description,
        )
    )
    db.session.commit()
    flash("Deliverable added to the project workspace.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/deliverables/<int:deliverable_id>/status", methods=["POST"])
@internal_login_required
def internal_project_deliverable_update_status(project_id: int, deliverable_id: int):
    deliverable = db.session.get(InternalProjectDeliverable, deliverable_id)
    if not deliverable or deliverable.project_id != project_id:
        flash("Deliverable not found.", "warning")
        return redirect(url_for("main.internal_project_workspace", project_id=project_id))

    deliverable.status = _normalize_internal_deliverable_status(request.form.get("status"))
    db.session.commit()
    flash("Deliverable status updated.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project_id)}#deliverables")


@main_bp.route("/internal/projects/<int:project_id>/deliverables/<int:deliverable_id>/update", methods=["POST"])
@internal_senior_required
def internal_project_deliverable_update(project_id: int, deliverable_id: int):
    deliverable = db.session.get(InternalProjectDeliverable, deliverable_id)
    anchor = "#deliverables"
    if not deliverable or deliverable.project_id != project_id:
        flash("Deliverable not found.", "warning")
        return redirect(_project_workspace_url(project_id, anchor))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    status = _normalize_internal_deliverable_status(request.form.get("status"))
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    link = (request.form.get("link") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not title or not owner_name or not description:
        flash("Deliverable title, owner, and description are required.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_deliverable_id=deliverable_id))
    if due_date_raw and not due_date:
        flash("Provide a valid deliverable due date.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_deliverable_id=deliverable_id))
    if link and not _is_safe_resource_link(link):
        flash("Deliverable link must be a relative path or an http/https URL.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_deliverable_id=deliverable_id))

    deliverable.title = title
    deliverable.owner_name = owner_name
    deliverable.status = status
    deliverable.due_date = due_date
    deliverable.link = link or None
    deliverable.description = description
    db.session.commit()
    flash("Deliverable updated.", "success")
    return redirect(_project_workspace_url(project_id, anchor))


@main_bp.route("/internal/projects/<int:project_id>/deliverables/<int:deliverable_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_deliverable_delete(project_id: int, deliverable_id: int):
    deliverable = db.session.get(InternalProjectDeliverable, deliverable_id)
    if not deliverable or deliverable.project_id != project_id:
        flash("Deliverable not found.", "warning")
        return redirect(_project_workspace_url(project_id, "#deliverables"))

    db.session.delete(deliverable)
    db.session.commit()
    flash("Deliverable deleted.", "success")
    return redirect(_project_workspace_url(project_id, "#deliverables"))


@main_bp.route("/internal/projects/<int:project_id>/risks/add", methods=["POST"])
@internal_login_required
def internal_project_risk_add(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    severity = _normalize_internal_risk_severity(request.form.get("severity"))
    status = _normalize_internal_risk_status(request.form.get("status"))
    mitigation = (request.form.get("mitigation") or "").strip()
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)
    anchor = "#risks"

    if not title or not owner_name or not mitigation:
        flash("Risk title, owner, and mitigation are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if due_date_raw and not due_date:
        flash("Provide a valid target date for the risk plan.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    db.session.add(
        InternalProjectRisk(
            project=project,
            title=title,
            owner_name=owner_name,
            severity=severity,
            status=status,
            mitigation=mitigation,
            due_date=due_date,
        )
    )
    db.session.commit()
    flash("Risk added to the project register.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/risks/<int:risk_id>/status", methods=["POST"])
@internal_login_required
def internal_project_risk_update_status(project_id: int, risk_id: int):
    risk = db.session.get(InternalProjectRisk, risk_id)
    if not risk or risk.project_id != project_id:
        flash("Risk not found.", "warning")
        return redirect(url_for("main.internal_project_workspace", project_id=project_id))

    risk.status = _normalize_internal_risk_status(request.form.get("status"))
    db.session.commit()
    flash("Risk status updated.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project_id)}#risks")


@main_bp.route("/internal/projects/<int:project_id>/risks/<int:risk_id>/update", methods=["POST"])
@internal_senior_required
def internal_project_risk_update(project_id: int, risk_id: int):
    risk = db.session.get(InternalProjectRisk, risk_id)
    anchor = "#risks"
    if not risk or risk.project_id != project_id:
        flash("Risk not found.", "warning")
        return redirect(_project_workspace_url(project_id, anchor))

    title = " ".join((request.form.get("title") or "").strip().split())
    owner_name = " ".join((request.form.get("owner_name") or "").strip().split())
    severity = _normalize_internal_risk_severity(request.form.get("severity"))
    status = _normalize_internal_risk_status(request.form.get("status"))
    mitigation = (request.form.get("mitigation") or "").strip()
    due_date_raw = (request.form.get("due_date") or "").strip()
    due_date = _parse_date(due_date_raw)

    if not title or not owner_name or not mitigation:
        flash("Risk title, owner, and mitigation are required.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_risk_id=risk_id))
    if due_date_raw and not due_date:
        flash("Provide a valid target date for the risk plan.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_risk_id=risk_id))

    risk.title = title
    risk.owner_name = owner_name
    risk.severity = severity
    risk.status = status
    risk.mitigation = mitigation
    risk.due_date = due_date
    db.session.commit()
    flash("Risk updated.", "success")
    return redirect(_project_workspace_url(project_id, anchor))


@main_bp.route("/internal/projects/<int:project_id>/risks/<int:risk_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_risk_delete(project_id: int, risk_id: int):
    risk = db.session.get(InternalProjectRisk, risk_id)
    if not risk or risk.project_id != project_id:
        flash("Risk not found.", "warning")
        return redirect(_project_workspace_url(project_id, "#risks"))

    db.session.delete(risk)
    db.session.commit()
    flash("Risk deleted.", "success")
    return redirect(_project_workspace_url(project_id, "#risks"))


@main_bp.route("/internal/projects/<int:project_id>/stakeholders/add", methods=["POST"])
@internal_login_required
def internal_project_stakeholder_add(project_id: int):
    project = db.session.get(InternalProject, project_id)
    if not project:
        flash("Project not found.", "warning")
        return redirect(url_for("main.internal_projects"))

    name = " ".join((request.form.get("name") or "").strip().split())
    role_title = " ".join((request.form.get("role_title") or "").strip().split())
    email = (request.form.get("email") or "").strip().lower()
    organisation = " ".join((request.form.get("organisation") or "").strip().split())
    stakeholder_type = _normalize_internal_stakeholder_type(request.form.get("stakeholder_type"))
    influence_level = _normalize_internal_stakeholder_influence(request.form.get("influence_level"))
    notes = (request.form.get("notes") or "").strip()
    anchor = "#stakeholders"

    if not name or not role_title or not organisation:
        flash("Stakeholder name, role, and organisation are required.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")
    if email and not _is_valid_public_email(email):
        flash("Enter a valid stakeholder email address.", "warning")
        return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")

    db.session.add(
        InternalProjectStakeholder(
            project=project,
            name=name,
            role_title=role_title,
            email=email or None,
            organisation=organisation,
            stakeholder_type=stakeholder_type,
            influence_level=influence_level,
            notes=notes or None,
        )
    )
    db.session.commit()
    flash("Stakeholder added to the project register.", "success")
    return redirect(f"{url_for('main.internal_project_workspace', project_id=project.id)}{anchor}")


@main_bp.route("/internal/projects/<int:project_id>/stakeholders/<int:stakeholder_id>/update", methods=["POST"])
@internal_senior_required
def internal_project_stakeholder_update(project_id: int, stakeholder_id: int):
    stakeholder = db.session.get(InternalProjectStakeholder, stakeholder_id)
    anchor = "#stakeholders"
    if not stakeholder or stakeholder.project_id != project_id:
        flash("Stakeholder not found.", "warning")
        return redirect(_project_workspace_url(project_id, anchor))

    name = " ".join((request.form.get("name") or "").strip().split())
    role_title = " ".join((request.form.get("role_title") or "").strip().split())
    email = (request.form.get("email") or "").strip().lower()
    organisation = " ".join((request.form.get("organisation") or "").strip().split())
    stakeholder_type = _normalize_internal_stakeholder_type(request.form.get("stakeholder_type"))
    influence_level = _normalize_internal_stakeholder_influence(request.form.get("influence_level"))
    notes = (request.form.get("notes") or "").strip()

    if not name or not role_title or not organisation:
        flash("Stakeholder name, role, and organisation are required.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_stakeholder_id=stakeholder_id))
    if email and not _is_valid_public_email(email):
        flash("Enter a valid stakeholder email address.", "warning")
        return redirect(_project_workspace_url(project_id, anchor, edit_stakeholder_id=stakeholder_id))

    stakeholder.name = name
    stakeholder.role_title = role_title
    stakeholder.email = email or None
    stakeholder.organisation = organisation
    stakeholder.stakeholder_type = stakeholder_type
    stakeholder.influence_level = influence_level
    stakeholder.notes = notes or None
    db.session.commit()
    flash("Stakeholder updated.", "success")
    return redirect(_project_workspace_url(project_id, anchor))


@main_bp.route("/internal/projects/<int:project_id>/stakeholders/<int:stakeholder_id>/delete", methods=["POST"])
@internal_senior_required
def internal_project_stakeholder_delete(project_id: int, stakeholder_id: int):
    stakeholder = db.session.get(InternalProjectStakeholder, stakeholder_id)
    if not stakeholder or stakeholder.project_id != project_id:
        flash("Stakeholder not found.", "warning")
        return redirect(_project_workspace_url(project_id, "#stakeholders"))

    db.session.delete(stakeholder)
    db.session.commit()
    flash("Stakeholder deleted.", "success")
    return redirect(_project_workspace_url(project_id, "#stakeholders"))


@main_bp.route("/internal/messages")
@internal_login_required
def internal_messages():
    current_user = g.internal_user
    selected_channel_id = _parse_positive_int(request.args.get("channel_id"))

    projects = (
        InternalProject.query.options(
            selectinload(InternalProject.client),
            selectinload(InternalProject.message_channel),
        )
        .order_by(InternalProject.name.asc())
        .all()
    )
    created_project_channels = False
    for project in projects:
        if project.message_channel:
            continue
        _ensure_project_message_channel(project, created_by=current_user)
        created_project_channels = True
    if created_project_channels:
        db.session.commit()
        projects = (
            InternalProject.query.options(
                selectinload(InternalProject.client),
                selectinload(InternalProject.message_channel),
            )
            .order_by(InternalProject.name.asc())
            .all()
        )

    project_channels = [project.message_channel for project in projects if project.message_channel]
    direct_channels = (
        InternalMessageChannel.query.options(
            selectinload(InternalMessageChannel.members),
        )
        .filter(
            InternalMessageChannel.channel_type == "direct",
            InternalMessageChannel.members.any(InternalUser.id == current_user.id),
        )
        .order_by(InternalMessageChannel.updated_at.desc(), InternalMessageChannel.created_at.desc())
        .all()
    )
    group_channels = (
        InternalMessageChannel.query.options(
            selectinload(InternalMessageChannel.members),
        )
        .filter(
            InternalMessageChannel.channel_type == "group",
            InternalMessageChannel.members.any(InternalUser.id == current_user.id),
        )
        .order_by(InternalMessageChannel.updated_at.desc(), InternalMessageChannel.created_at.desc())
        .all()
    )

    all_channel_ids = [channel.id for channel in project_channels + direct_channels + group_channels if channel]
    if selected_channel_id is None and all_channel_ids:
        selected_channel_id = all_channel_ids[0]

    selected_channel = None
    if selected_channel_id:
        selected_channel = (
            InternalMessageChannel.query.options(
                selectinload(InternalMessageChannel.project).selectinload(InternalProject.client),
                selectinload(InternalMessageChannel.members),
                selectinload(InternalMessageChannel.messages).selectinload(InternalMessage.sender),
            )
            .filter_by(id=selected_channel_id)
            .first()
        )
        if selected_channel and not _internal_user_can_access_channel(selected_channel, current_user):
            flash("You do not have access to the selected channel.", "warning")
            selected_channel = None
    if not selected_channel and all_channel_ids:
        fallback_channel_id = all_channel_ids[0]
        if fallback_channel_id != selected_channel_id:
            selected_channel = (
                InternalMessageChannel.query.options(
                    selectinload(InternalMessageChannel.project).selectinload(InternalProject.client),
                    selectinload(InternalMessageChannel.members),
                    selectinload(InternalMessageChannel.messages).selectinload(InternalMessage.sender),
                )
                .filter_by(id=fallback_channel_id)
                .first()
            )

    available_users = (
        InternalUser.query.filter(InternalUser.is_active.is_(True), InternalUser.id != current_user.id)
        .order_by(InternalUser.full_name.asc())
        .all()
    )

    project_channel_cards = []
    for channel in project_channels:
        title, subtitle = _internal_channel_label(channel, current_user)
        project_channel_cards.append({"channel": channel, "title": title, "subtitle": subtitle})

    direct_channel_cards = []
    for channel in direct_channels:
        title, subtitle = _internal_channel_label(channel, current_user)
        direct_channel_cards.append({"channel": channel, "title": title, "subtitle": subtitle})

    group_channel_cards = []
    for channel in group_channels:
        title, subtitle = _internal_channel_label(channel, current_user)
        group_channel_cards.append({"channel": channel, "title": title, "subtitle": subtitle})

    selected_channel_title = None
    selected_channel_subtitle = None
    if selected_channel:
        selected_channel_title, selected_channel_subtitle = _internal_channel_label(selected_channel, current_user)

    return render_template(
        "internal/messages.html",
        project_channel_cards=project_channel_cards,
        direct_channel_cards=direct_channel_cards,
        group_channel_cards=group_channel_cards,
        selected_channel=selected_channel,
        selected_channel_id=selected_channel.id if selected_channel else None,
        selected_channel_title=selected_channel_title,
        selected_channel_subtitle=selected_channel_subtitle,
        available_users=available_users,
    )


@main_bp.route("/internal/messages/direct/start", methods=["POST"])
@internal_login_required
def internal_messages_start_direct():
    current_user = g.internal_user
    recipient_id = _parse_positive_int(request.form.get("recipient_id"))
    if not recipient_id:
        flash("Select a valid consultant to start a direct message.", "warning")
        return redirect(url_for("main.internal_messages"))
    if recipient_id == current_user.id:
        flash("Select another consultant to start a direct message.", "warning")
        return redirect(url_for("main.internal_messages"))

    recipient_user = db.session.get(InternalUser, recipient_id)
    if not recipient_user or not recipient_user.is_active:
        flash("Selected consultant is not available.", "warning")
        return redirect(url_for("main.internal_messages"))

    channel, was_created = _get_or_create_direct_channel(current_user, recipient_user)
    if was_created:
        db.session.commit()
        flash(f"Direct channel opened with {recipient_user.full_name}.", "success")

    return redirect(url_for("main.internal_messages", channel_id=channel.id))


@main_bp.route("/internal/messages/group/create", methods=["POST"])
@internal_login_required
def internal_messages_create_group():
    current_user = g.internal_user
    name = " ".join((request.form.get("name") or "").strip().split())
    member_ids = set(_parse_int_list(request.form.getlist("member_ids")))
    member_ids.add(current_user.id)

    if not name:
        flash("Group name is required.", "warning")
        return redirect(url_for("main.internal_messages"))
    if len(name) > 160:
        flash("Group name must be 160 characters or fewer.", "warning")
        return redirect(url_for("main.internal_messages"))
    if len(member_ids) < 2:
        flash("Select at least one additional consultant for the group.", "warning")
        return redirect(url_for("main.internal_messages"))

    members = (
        InternalUser.query.filter(InternalUser.id.in_(member_ids), InternalUser.is_active.is_(True))
        .order_by(InternalUser.full_name.asc())
        .all()
    )
    if len(members) != len(member_ids):
        flash("One or more selected group members are invalid or inactive.", "warning")
        return redirect(url_for("main.internal_messages"))

    channel = InternalMessageChannel(
        channel_type="group",
        name=name,
        creator=current_user,
    )
    channel.members = members
    db.session.add(channel)
    db.session.commit()
    flash(f"Group '{name}' created.", "success")
    return redirect(url_for("main.internal_messages", channel_id=channel.id))


@main_bp.route("/internal/messages/post", methods=["POST"])
@internal_login_required
def internal_messages_post():
    current_user = g.internal_user
    channel_id = _parse_positive_int(request.form.get("channel_id"))
    body = (request.form.get("body") or "").strip()
    if not channel_id:
        flash("Choose a channel before posting a message.", "warning")
        return redirect(url_for("main.internal_messages"))
    if not body:
        flash("Message body cannot be empty.", "warning")
        return redirect(url_for("main.internal_messages", channel_id=channel_id))
    if len(body) > 3000:
        flash("Message body must be 3000 characters or fewer.", "warning")
        return redirect(url_for("main.internal_messages", channel_id=channel_id))

    channel = (
        InternalMessageChannel.query.options(selectinload(InternalMessageChannel.members))
        .filter_by(id=channel_id)
        .first()
    )
    if not channel:
        flash("Selected channel does not exist.", "warning")
        return redirect(url_for("main.internal_messages"))
    if not _internal_user_can_access_channel(channel, current_user):
        flash("You do not have permission to post in that channel.", "warning")
        return redirect(url_for("main.internal_messages"))

    message = InternalMessage(channel=channel, sender=current_user, body=body)
    channel.updated_at = datetime.now(timezone.utc)
    db.session.add(message)
    db.session.commit()
    return redirect(url_for("main.internal_messages", channel_id=channel.id))


@main_bp.route("/internal/todos")
@internal_login_required
def internal_todos():
    view_mode = (request.args.get("view") or "nested").strip().lower()
    if view_mode not in {"nested", "priority"}:
        view_mode = "nested"
    current_user_is_senior = _internal_user_is_senior(getattr(g, "internal_user", None))
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
    editable_task_id = _parse_positive_int(request.args.get("edit_task_id")) if current_user_is_senior else None
    editable_task = next((task for task in tasks if task.id == editable_task_id), None)

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
        elif editable_task and task.id == editable_task.parent_task_id:
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
    active_internal_users = (
        InternalUser.query.filter_by(is_active=True).order_by(InternalUser.full_name.asc()).all()
    )
    default_task_due_date = date.today() + timedelta(days=7)

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
        active_internal_users=active_internal_users,
        default_task_due_date=default_task_due_date,
        editable_task=editable_task,
    )


@main_bp.route("/internal/todos/add", methods=["POST"])
@internal_login_required
def internal_todo_add():
    redirect_kwargs = _internal_todos_redirect_kwargs(
        request.form.get("view_mode"),
        request.form.get("project_scope"),
    )
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
    redirect_kwargs = _internal_todos_redirect_kwargs(
        request.form.get("view_mode"),
        request.form.get("project_scope"),
    )
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
    redirect_kwargs = _internal_todos_redirect_kwargs(
        request.form.get("view_mode"),
        request.form.get("project_scope"),
    )
    task = db.session.get(InternalTask, task_id)
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.internal_todos", **redirect_kwargs))

    task.priority = _normalize_internal_task_priority(request.form.get("priority"))
    db.session.commit()
    flash("Task priority updated.", "success")
    return redirect(url_for("main.internal_todos", **redirect_kwargs))


@main_bp.route("/internal/todos/<int:task_id>/update", methods=["POST"])
@internal_senior_required
def internal_todo_update(task_id: int):
    task = db.session.get(InternalTask, task_id)
    redirect_kwargs = _internal_todos_redirect_kwargs(
        request.form.get("view_mode"),
        request.form.get("project_scope"),
    )
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.internal_todos", **redirect_kwargs))

    edit_redirect_kwargs = dict(redirect_kwargs)
    edit_redirect_kwargs["edit_task_id"] = task.id
    edit_redirect_target = url_for("main.internal_todos", **edit_redirect_kwargs)

    title = (request.form.get("title") or "").strip()
    assignee = (request.form.get("assignee") or "").strip()
    priority = _normalize_internal_task_priority(request.form.get("priority"))
    status = _normalize_internal_task_status(request.form.get("status"))
    due_date = _parse_date(request.form.get("due_date"))
    project_id = request.form.get("project_id")
    parent_task_id = request.form.get("parent_task_id")

    if not title:
        flash("Task title is required.", "warning")
        return redirect(edit_redirect_target)

    if not assignee:
        flash("Task assignee is required.", "warning")
        return redirect(edit_redirect_target)

    try:
        project_pk = int(project_id or "")
    except ValueError:
        flash("Choose a valid project for the task.", "warning")
        return redirect(edit_redirect_target)

    project = db.session.get(InternalProject, project_pk)
    if not project:
        flash("Selected project does not exist.", "warning")
        return redirect(edit_redirect_target)

    parent_task = None
    if parent_task_id:
        try:
            parent_pk = int(parent_task_id)
        except ValueError:
            flash("Invalid parent task.", "warning")
            return redirect(edit_redirect_target)

        parent_task = db.session.get(InternalTask, parent_pk)
        if not parent_task:
            flash("Parent task not found.", "warning")
            return redirect(edit_redirect_target)
        if parent_task.id == task.id:
            flash("A task cannot be its own parent.", "warning")
            return redirect(edit_redirect_target)
        if parent_task.project_id != project.id:
            flash("Parent task must belong to the same project.", "warning")
            return redirect(edit_redirect_target)

        current_parent = parent_task
        while current_parent:
            if current_parent.id == task.id:
                flash("A task cannot be nested inside one of its own subtasks.", "warning")
                return redirect(edit_redirect_target)
            current_parent = current_parent.parent_task

    if task.subtasks and task.project_id != project.id:
        flash("Move or delete this task's subtasks before changing its project.", "warning")
        return redirect(edit_redirect_target)

    task.project = project
    task.parent_task = parent_task
    task.title = title
    task.assignee = assignee
    task.priority = priority
    task.status = status
    task.due_date = due_date
    db.session.commit()
    flash("Task details updated.", "success")
    return redirect(url_for("main.internal_todos", **redirect_kwargs))


@main_bp.route("/internal/todos/<int:task_id>/delete", methods=["POST"])
@internal_senior_required
def internal_todo_delete(task_id: int):
    redirect_kwargs = _internal_todos_redirect_kwargs(
        request.form.get("view_mode"),
        request.form.get("project_scope"),
    )
    task = db.session.get(InternalTask, task_id)
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.internal_todos", **redirect_kwargs))

    def task_family_size(current_task: InternalTask) -> int:
        return 1 + sum(task_family_size(child) for child in current_task.subtasks)

    deleted_count = task_family_size(task)
    db.session.delete(task)
    db.session.commit()
    if deleted_count > 1:
        flash(f"Task deleted, including {deleted_count - 1} nested subtasks.", "success")
    else:
        flash("Task deleted.", "success")
    return redirect(url_for("main.internal_todos", **redirect_kwargs))


@main_bp.route("/internal/docs")
@main_bp.route("/internal/docs/<string:doc_slug>")
@internal_login_required
def internal_docs(doc_slug: str | None = None):
    current_user_is_senior = _internal_user_is_senior(getattr(g, "internal_user", None))
    query_term = (request.args.get("q") or "").strip()
    query_term_lower = query_term.lower()
    selected_status = (request.args.get("status") or "all").strip().lower()
    selected_project_raw = (request.args.get("project_id") or "all").strip()
    selected_project_filter: int | str = "all"

    pages = (
        InternalDocPage.query.options(
            selectinload(InternalDocPage.project),
            selectinload(InternalDocPage.author),
            selectinload(InternalDocPage.children),
        )
        .order_by(InternalDocPage.updated_at.desc(), InternalDocPage.title.asc())
        .all()
    )
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

    if selected_status not in {"all", *INTERNAL_DOC_STATUSES}:
        selected_status = "all"

    filtered_pages: list[InternalDocPage] = []
    for page in pages:
        if selected_status != "all" and (page.status or "").strip().lower() != selected_status:
            continue
        if selected_project_filter != "all" and page.project_id != selected_project_filter:
            continue
        if query_term_lower and query_term_lower not in page.searchable_text:
            continue
        filtered_pages.append(page)

    filtered_page_ids = {page.id for page in filtered_pages}
    visible_tree_ids: set[int] = set()
    for page in filtered_pages:
        current_page = page
        while current_page:
            visible_tree_ids.add(current_page.id)
            current_page = current_page.parent

    selected_page = None
    if doc_slug:
        selected_page = InternalDocPage.query.options(
            selectinload(InternalDocPage.project),
            selectinload(InternalDocPage.author),
            selectinload(InternalDocPage.children),
            selectinload(InternalDocPage.parent),
        ).filter_by(slug=doc_slug).first_or_404()
        current_page = selected_page
        while current_page:
            visible_tree_ids.add(current_page.id)
            current_page = current_page.parent
    elif filtered_pages:
        selected_page = sorted(filtered_pages, key=lambda page: page.sort_key)[0]

    root_pages = sorted(
        [
            page
            for page in pages
            if page.parent_id is None and (not visible_tree_ids or page.id in visible_tree_ids)
        ],
        key=lambda page: page.sort_key,
    )

    summary_metrics = {
        "total_pages": len(pages),
        "visible_pages": len(filtered_pages) if (query_term or selected_status != "all" or selected_project_filter != "all") else len(pages),
        "draft_pages": sum(1 for page in pages if (page.status or "").strip().lower() == "draft"),
        "linked_projects": len({page.project_id for page in pages if page.project_id}),
    }
    selected_page_body = _render_internal_doc_body(selected_page.body) if selected_page else None
    selected_page_outline = _internal_doc_outline(selected_page.body) if selected_page else []
    doc_form_page = selected_page if current_user_is_senior else None
    page_status_options = [{"value": "all", "label": "All statuses"}] + [
        {"value": status, "label": status.title()} for status in INTERNAL_DOC_STATUSES
    ]
    parent_page_options = sorted(pages, key=lambda page: page.sort_key)

    return render_template(
        "internal/docs.html",
        pages=pages,
        root_pages=root_pages,
        visible_tree_ids=visible_tree_ids,
        filtered_page_ids=filtered_page_ids,
        selected_page=selected_page,
        selected_page_body=selected_page_body,
        selected_page_outline=selected_page_outline,
        doc_form_page=doc_form_page,
        summary_metrics=summary_metrics,
        query_term=query_term,
        selected_status=selected_status,
        page_status_options=page_status_options,
        project_options=project_options,
        selected_project_filter=str(selected_project_filter),
        projects=projects,
        parent_page_options=parent_page_options,
    )


@main_bp.route("/internal/docs/add", methods=["POST"])
@internal_login_required
def internal_doc_add():
    title = " ".join((request.form.get("title") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    body = (request.form.get("body") or "").strip()
    status = _normalize_internal_doc_status(request.form.get("status"))
    project_id = _parse_positive_int(request.form.get("project_id"))
    parent_id = _parse_positive_int(request.form.get("parent_id"))

    if not title or not summary or not body:
        flash("Doc title, summary, and body are required.", "warning")
        return redirect(url_for("main.internal_docs"))

    project = db.session.get(InternalProject, project_id) if project_id else None
    if project_id and not project:
        flash("Selected project does not exist.", "warning")
        return redirect(url_for("main.internal_docs"))

    parent_page = db.session.get(InternalDocPage, parent_id) if parent_id else None
    if parent_id and not parent_page:
        flash("Selected parent page does not exist.", "warning")
        return redirect(url_for("main.internal_docs"))

    page = InternalDocPage(
        title=title,
        slug=_unique_internal_doc_slug(title),
        summary=summary,
        body=body,
        status=status,
        project=project,
        parent=parent_page,
        author=getattr(g, "internal_user", None),
    )
    db.session.add(page)
    db.session.commit()
    flash("Workspace doc created.", "success")
    return redirect(url_for("main.internal_docs", doc_slug=page.slug))


@main_bp.route("/internal/docs/<int:page_id>/update", methods=["POST"])
@internal_senior_required
def internal_doc_update(page_id: int):
    page = db.session.get(InternalDocPage, page_id)
    if not page:
        flash("Doc page not found.", "warning")
        return redirect(url_for("main.internal_docs"))

    title = " ".join((request.form.get("title") or "").strip().split())
    summary = (request.form.get("summary") or "").strip()
    body = (request.form.get("body") or "").strip()
    status = _normalize_internal_doc_status(request.form.get("status"))
    project_id = _parse_positive_int(request.form.get("project_id"))
    parent_id = _parse_positive_int(request.form.get("parent_id"))

    if not title or not summary or not body:
        flash("Doc title, summary, and body are required.", "warning")
        return redirect(url_for("main.internal_docs", doc_slug=page.slug))

    project = db.session.get(InternalProject, project_id) if project_id else None
    if project_id and not project:
        flash("Selected project does not exist.", "warning")
        return redirect(url_for("main.internal_docs", doc_slug=page.slug))

    parent_page = db.session.get(InternalDocPage, parent_id) if parent_id else None
    if parent_id and not parent_page:
        flash("Selected parent page does not exist.", "warning")
        return redirect(url_for("main.internal_docs", doc_slug=page.slug))
    if parent_page and parent_page.id == page.id:
        flash("A page cannot be its own parent.", "warning")
        return redirect(url_for("main.internal_docs", doc_slug=page.slug))

    current_parent = parent_page
    while current_parent:
        if current_parent.id == page.id:
            flash("A page cannot be nested inside one of its own descendants.", "warning")
            return redirect(url_for("main.internal_docs", doc_slug=page.slug))
        current_parent = current_parent.parent

    page.title = title
    page.slug = _unique_internal_doc_slug(title, page_id=page.id)
    page.summary = summary
    page.body = body
    page.status = status
    page.project = project
    page.parent = parent_page
    page.author = getattr(g, "internal_user", None)
    db.session.commit()
    flash("Workspace doc updated.", "success")
    return redirect(url_for("main.internal_docs", doc_slug=page.slug))


@main_bp.route("/internal/docs/<int:page_id>/delete", methods=["POST"])
@internal_senior_required
def internal_doc_delete(page_id: int):
    page = db.session.get(InternalDocPage, page_id)
    if not page:
        flash("Doc page not found.", "warning")
        return redirect(url_for("main.internal_docs"))

    parent_slug = page.parent.slug if page.parent else None

    def page_family_size(current_page: InternalDocPage) -> int:
        return 1 + sum(page_family_size(child) for child in current_page.children)

    deleted_count = page_family_size(page)
    db.session.delete(page)
    db.session.commit()
    if deleted_count > 1:
        flash(f"Workspace page deleted, including {deleted_count - 1} nested child pages.", "success")
    else:
        flash("Workspace page deleted.", "success")
    if parent_slug:
        return redirect(url_for("main.internal_docs", doc_slug=parent_slug))
    return redirect(url_for("main.internal_docs"))


@main_bp.route("/internal/resources")
@internal_login_required
def internal_resources():
    current_user_is_senior = _internal_user_is_senior(getattr(g, "internal_user", None))
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
    recent_doc_pages = (
        InternalDocPage.query.options(selectinload(InternalDocPage.project))
        .order_by(InternalDocPage.updated_at.desc(), InternalDocPage.title.asc())
        .limit(4)
        .all()
    )
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
        linked_project_ids = {project.id for project in resource.projects}
        linked_project_ids.update(task.project_id for task in resource.tasks if task.project_id)
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
        if selected_project_filter != "all" and selected_project_filter not in linked_project_ids:
            continue
        if query_term_lower and query_term_lower not in resource.searchable_text:
            continue
        filtered_resources.append(resource)

    editable_resource_id = _parse_positive_int(request.args.get("edit_id")) if current_user_is_senior else None
    editable_resource = next((resource for resource in resources if resource.id == editable_resource_id), None)
    editable_resource_uploaded_filename = (
        _internal_resource_uploaded_filename(editable_resource.link) if editable_resource else None
    )

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
        "workspace_pages": InternalDocPage.query.count(),
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
        recent_doc_pages=recent_doc_pages,
        summary_metrics=summary_metrics,
        projects=projects,
        tasks=tasks,
        editable_resource=editable_resource,
        editable_resource_project_ids={project.id for project in editable_resource.projects} if editable_resource else set(),
        editable_resource_task_ids={task.id for task in editable_resource.tasks} if editable_resource else set(),
        editable_resource_tags=", ".join(editable_resource.tag_names) if editable_resource else "",
        editable_resource_uploaded_filename=editable_resource_uploaded_filename,
        resource_upload_accept=",".join(f".{item}" for item in sorted(RESOURCE_UPLOAD_ALLOWED_EXTENSIONS)),
        resource_upload_limit_mb=_resource_upload_limit_label(),
    )


@main_bp.route("/internal/resources/files/<path:filename>")
@internal_login_required
def internal_resource_file_download(filename: str):
    return send_from_directory(
        _resource_upload_directory(),
        filename,
        as_attachment=False,
        conditional=True,
    )


@main_bp.route("/internal/resources/add", methods=["POST"])
@internal_login_required
def internal_resource_add():
    redirect_target = url_for("main.internal_resources", **_internal_resources_redirect_kwargs())
    title = (request.form.get("title") or "").strip()
    link = (request.form.get("link") or "").strip()
    uploaded_file = request.files.get("document_file")
    has_uploaded_file = bool(uploaded_file and (uploaded_file.filename or "").strip())
    description = (request.form.get("description") or "").strip()
    category = _normalize_resource_category(request.form.get("category"))
    tag_names = _normalize_resource_tags(request.form.get("tags"))
    project_ids = _parse_int_list(request.form.getlist("project_ids"))
    task_ids = _parse_int_list(request.form.getlist("task_ids"))

    if not title or not description:
        flash("Title and description are required to add a resource.", "warning")
        return redirect(redirect_target)
    if bool(link) and has_uploaded_file:
        flash("Provide either a document link or a file upload, not both.", "warning")
        return redirect(redirect_target)
    if not link and not has_uploaded_file:
        flash("Add either a document link or a file upload.", "warning")
        return redirect(redirect_target)

    projects: list[InternalProject] = []
    tasks: list[InternalTask] = []
    if project_ids:
        projects = InternalProject.query.filter(InternalProject.id.in_(project_ids)).all()
        if len(projects) != len(project_ids):
            flash("One or more selected projects are invalid.", "warning")
            return redirect(redirect_target)
    if task_ids:
        tasks = InternalTask.query.filter(InternalTask.id.in_(task_ids)).all()
        if len(tasks) != len(task_ids):
            flash("One or more selected tasks are invalid.", "warning")
            return redirect(redirect_target)

    if has_uploaded_file:
        uploaded_filename, upload_error = _save_resource_upload(uploaded_file)
        if upload_error:
            flash(upload_error, "warning")
            return redirect(redirect_target)
        link = url_for("main.internal_resource_file_download", filename=uploaded_filename)
    elif not _is_safe_resource_link(link):
        flash("Resource link must be a relative path or an http/https URL.", "warning")
        return redirect(redirect_target)

    resource_tags = _internal_resource_tag_records(tag_names)

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
    return redirect(
        url_for(
            "main.internal_resources",
            **_internal_resources_redirect_kwargs(default_query=title),
        )
    )


@main_bp.route("/internal/resources/<int:resource_id>/update", methods=["POST"])
@internal_senior_required
def internal_resource_update(resource_id: int):
    redirect_kwargs = _internal_resources_redirect_kwargs()
    resource = db.session.get(InternalResource, resource_id)
    if not resource:
        flash("Resource not found.", "warning")
        return redirect(url_for("main.internal_resources", **redirect_kwargs))

    edit_redirect_kwargs = _internal_resources_redirect_kwargs(edit_resource_id=resource.id)
    edit_redirect_target = url_for("main.internal_resources", **edit_redirect_kwargs)

    title = (request.form.get("title") or "").strip()
    link = (request.form.get("link") or "").strip()
    uploaded_file = request.files.get("document_file")
    has_uploaded_file = bool(uploaded_file and (uploaded_file.filename or "").strip())
    description = (request.form.get("description") or "").strip()
    category = _normalize_resource_category(request.form.get("category"))
    tag_names = _normalize_resource_tags(request.form.get("tags"))
    project_ids = _parse_int_list(request.form.getlist("project_ids"))
    task_ids = _parse_int_list(request.form.getlist("task_ids"))

    if not title or not description:
        flash("Title and description are required to update a resource.", "warning")
        return redirect(edit_redirect_target)
    if bool(link) and has_uploaded_file:
        flash("Provide either a document link or a file upload, not both.", "warning")
        return redirect(edit_redirect_target)

    projects: list[InternalProject] = []
    tasks: list[InternalTask] = []
    if project_ids:
        projects = InternalProject.query.filter(InternalProject.id.in_(project_ids)).all()
        if len(projects) != len(project_ids):
            flash("One or more selected projects are invalid.", "warning")
            return redirect(edit_redirect_target)
    if task_ids:
        tasks = InternalTask.query.filter(InternalTask.id.in_(task_ids)).all()
        if len(tasks) != len(task_ids):
            flash("One or more selected tasks are invalid.", "warning")
            return redirect(edit_redirect_target)

    next_link = resource.link
    if has_uploaded_file:
        uploaded_filename, upload_error = _save_resource_upload(uploaded_file)
        if upload_error:
            flash(upload_error, "warning")
            return redirect(edit_redirect_target)
        next_link = url_for("main.internal_resource_file_download", filename=uploaded_filename)
    elif link:
        if not _is_safe_resource_link(link):
            flash("Resource link must be a relative path or an http/https URL.", "warning")
            return redirect(edit_redirect_target)
        next_link = link

    previous_link = resource.link
    resource.title = title
    resource.link = next_link
    resource.category = category
    resource.description = description
    resource.projects = projects
    resource.tasks = tasks
    resource.tags = _internal_resource_tag_records(tag_names)
    db.session.commit()
    if previous_link != next_link:
        _delete_internal_resource_upload(previous_link)
    flash("Resource updated.", "success")
    return redirect(url_for("main.internal_resources", **_internal_resources_redirect_kwargs(default_query=title)))


@main_bp.route("/internal/resources/<int:resource_id>/delete", methods=["POST"])
@internal_senior_required
def internal_resource_delete(resource_id: int):
    redirect_kwargs = _internal_resources_redirect_kwargs()
    resource = db.session.get(InternalResource, resource_id)
    if not resource:
        flash("Resource not found.", "warning")
        return redirect(url_for("main.internal_resources", **redirect_kwargs))

    previous_link = resource.link
    db.session.delete(resource)
    db.session.commit()
    _delete_internal_resource_upload(previous_link)
    flash("Resource deleted.", "success")
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
    budget = (request.form.get("budget") or "").strip()
    message_body = (request.form.get("message") or "").strip()
    return_to = _safe_public_return_target(request.form.get("return_to"))
    form_state = {
        "name": name,
        "email": email,
        "role": role,
        "company": company,
        "phone": phone,
        "timeline": timeline,
        "budget": budget,
        "message": message_body,
        "service": (request.form.get("service") or "0").strip() or "0",
    }
    form_redirect_target = return_to or url_for("main.enquire", _anchor="enquiry-form")
    honeypot = (request.form.get("website") or "").strip()
    if honeypot:
        _clear_public_contact_feedback()
        flash("Thank you. Your enquiry has been received.", "success")
        return redirect(form_redirect_target)

    service_id = request.form.get("service")
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "Enter your full name."
    if not _is_valid_public_email(email):
        errors["email"] = "Enter a valid work email address."
    if not message_body:
        errors["message"] = "Add a short description of the workflow problem you want solved."

    if errors:
        _store_public_contact_feedback(form_state, errors)
        flash("Please correct the enquiry form and try again.", "warning")
        return redirect(form_redirect_target)

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
        Budget Range: {budget or "Not provided"}
        Service Interest: {service_name}

        Message:
        {message_body or "Not provided"}
    """
    if email and ("\n" not in email and "\r" not in email):
        msg.reply_to = email
    try:
        mail.send(msg)  # <--- This actually sends it!
        _clear_public_contact_feedback()
        flash(f"Thank you, {name or 'there'}. We will contact you regarding '{service_name}'.", "success")
    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        _store_public_contact_feedback(form_state)
        flash("Message saved, but we couldn't send the email confirmation.", "warning")
    return redirect(form_redirect_target)


@main_bp.route("/healthz")
def healthz():
    return {"status": "ok"}, 200
