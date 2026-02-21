from __future__ import annotations

import os
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


internal_resource_project_links = db.Table(
    "internal_resource_project_links",
    db.Column("resource_id", db.Integer, db.ForeignKey("internal_resource.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("internal_project.id"), primary_key=True),
)

internal_resource_task_links = db.Table(
    "internal_resource_task_links",
    db.Column("resource_id", db.Integer, db.ForeignKey("internal_resource.id"), primary_key=True),
    db.Column("task_id", db.Integer, db.ForeignKey("internal_task.id"), primary_key=True),
)

internal_resource_tag_links = db.Table(
    "internal_resource_tag_links",
    db.Column("resource_id", db.Integer, db.ForeignKey("internal_resource.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("internal_resource_tag.id"), primary_key=True),
)

internal_message_channel_member_links = db.Table(
    "internal_message_channel_member_links",
    db.Column("channel_id", db.Integer, db.ForeignKey("internal_message_channel.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("internal_user.id"), primary_key=True),
)


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), nullable=False)

    # Relationship to features
    features = db.relationship("Feature", backref="service", lazy=True)


class Feature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)


class Slide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    owner = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), nullable=False)


class Branding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(200), nullable=False)
    Slogan = db.Column(db.String(200), nullable=False)
    Tagline = db.Column(db.String(1000), nullable=False)


class Page_Heading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(200), nullable=False)
    Slogan_1 = db.Column(db.String(200), nullable=False)
    Slogan_2 = db.Column(db.String(200), nullable=False)
    Tagline = db.Column(db.String(1000), nullable=False)


class InternalUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="consultant")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    projects = db.relationship("InternalProject", backref="owner", lazy=True)
    message_channels = db.relationship(
        "InternalMessageChannel",
        secondary=internal_message_channel_member_links,
        back_populates="members",
        lazy=True,
    )
    sent_messages = db.relationship("InternalMessage", back_populates="sender", lazy=True)
    created_message_channels = db.relationship(
        "InternalMessageChannel",
        back_populates="creator",
        lazy=True,
        foreign_keys="InternalMessageChannel.created_by_id",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class InternalClient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    industry = db.Column(db.String(120), nullable=False)
    account_owner = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="active")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    projects = db.relationship("InternalProject", backref="client", lazy=True, cascade="all, delete-orphan")


class InternalProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("internal_client.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=True)
    industry_category = db.Column(db.String(80), nullable=False, default="general", index=True)
    stage = db.Column(db.String(64), nullable=False, default="discovery")
    status = db.Column(db.String(32), nullable=False, default="on-track")
    due_date = db.Column(db.Date, nullable=True)
    value_estimate = db.Column(db.Numeric(12, 2), nullable=True)
    summary = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tasks = db.relationship("InternalTask", backref="project", lazy=True, cascade="all, delete-orphan")
    resources = db.relationship(
        "InternalResource",
        secondary=internal_resource_project_links,
        back_populates="projects",
        lazy=True,
    )
    message_channel = db.relationship(
        "InternalMessageChannel",
        back_populates="project",
        uselist=False,
        lazy=True,
        cascade="all, delete-orphan",
    )


class InternalTask(db.Model):
    PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
    STATUS_RANK = {"todo": 0, "in-progress": 1, "blocked": 2, "done": 3}

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("internal_project.id"), nullable=False)
    parent_task_id = db.Column(db.Integer, db.ForeignKey("internal_task.id"), nullable=True, index=True)
    title = db.Column(db.String(240), nullable=False)
    assignee = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.String(32), nullable=False, default="medium")
    status = db.Column(db.String(32), nullable=False, default="todo")
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    subtasks = db.relationship(
        "InternalTask",
        backref=db.backref("parent_task", remote_side=[id]),
        lazy=True,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    resources = db.relationship(
        "InternalResource",
        secondary=internal_resource_task_links,
        back_populates="tasks",
        lazy=True,
    )

    @property
    def is_done(self) -> bool:
        return (self.status or "").strip().lower() == "done"

    @property
    def sort_key(self):
        normalized_priority = (self.priority or "").strip().lower()
        normalized_status = (self.status or "").strip().lower()
        return (
            self.STATUS_RANK.get(normalized_status, 4),
            self.PRIORITY_RANK.get(normalized_priority, 3),
            self.due_date or date.max,
            self.created_at or datetime.min.replace(tzinfo=timezone.utc),
            self.id or 0,
        )

    @property
    def ordered_subtasks(self) -> list["InternalTask"]:
        return sorted(self.subtasks, key=lambda task: task.sort_key)


class InternalResource(db.Model):
    SAFE_SCHEMES = {"http", "https"}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    projects = db.relationship(
        "InternalProject",
        secondary=internal_resource_project_links,
        back_populates="resources",
        lazy=True,
    )
    tasks = db.relationship(
        "InternalTask",
        secondary=internal_resource_task_links,
        back_populates="resources",
        lazy=True,
    )
    tags = db.relationship(
        "InternalResourceTag",
        secondary=internal_resource_tag_links,
        back_populates="resources",
        lazy=True,
        order_by="InternalResourceTag.name",
    )

    @property
    def tag_names(self) -> list[str]:
        return [tag.name for tag in self.tags]

    @property
    def searchable_text(self) -> str:
        parts = [self.title, self.category, self.description, self.link]
        parts.extend(project.name for project in self.projects)
        parts.extend(task.title for task in self.tasks)
        parts.extend(self.tag_names)
        return " ".join(part for part in parts if part).lower()

    @property
    def safe_link(self) -> str:
        raw_link = (self.link or "").strip()
        if not raw_link:
            return "#"
        if raw_link.startswith("/"):
            return raw_link
        parsed = urlparse(raw_link)
        if parsed.scheme.lower() in self.SAFE_SCHEMES and parsed.netloc:
            return raw_link
        return "#"


class InternalResourceTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resources = db.relationship(
        "InternalResource",
        secondary=internal_resource_tag_links,
        back_populates="tags",
        lazy=True,
    )


class InternalAnnouncement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class InternalProjectStarterPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    template_json = db.Column(db.Text, nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=True, index=True)
    updated_by = db.relationship("InternalUser", lazy=True, foreign_keys=[updated_by_id])
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class InternalMessageChannel(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "direct_user_low_id",
            "direct_user_high_id",
            name="uq_internal_message_channel_direct_pair",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    channel_type = db.Column(db.String(16), nullable=False, default="group", index=True)
    name = db.Column(db.String(160), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("internal_project.id"), nullable=True, unique=True, index=True)
    direct_user_low_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=True, index=True)
    direct_user_high_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project = db.relationship("InternalProject", back_populates="message_channel", lazy=True)
    creator = db.relationship(
        "InternalUser",
        back_populates="created_message_channels",
        lazy=True,
        foreign_keys=[created_by_id],
    )
    direct_user_low = db.relationship("InternalUser", lazy=True, foreign_keys=[direct_user_low_id])
    direct_user_high = db.relationship("InternalUser", lazy=True, foreign_keys=[direct_user_high_id])
    members = db.relationship(
        "InternalUser",
        secondary=internal_message_channel_member_links,
        back_populates="message_channels",
        lazy=True,
    )
    messages = db.relationship(
        "InternalMessage",
        back_populates="channel",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="InternalMessage.created_at.asc()",
    )


class InternalMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("internal_message_channel.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("internal_user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    channel = db.relationship("InternalMessageChannel", back_populates="messages", lazy=True)
    sender = db.relationship("InternalUser", back_populates="sent_messages", lazy=True)


def _seed_public_site_data() -> None:
    if Service.query.first() or Slide.query.first() or Branding.query.first() or Page_Heading.query.first():
        return

    print("--- Seeding Database with ELF Pitch Deck Data ---")

    branding = Branding(
        Title="ELF",
        Slogan="Novel AI Solutions",
        Tagline=(
            "Enhance the effiency of your business with tailored AI-integration "
            "and automation solutions, built for your specific needs"
        ),
    )

    about_us_page = Page_Heading(
        Title="about_us",
        Slogan_1="Dynamic",
        Slogan_2="Problem Solvers.",
        Tagline="Solving real-world problems with personalised AI solutions.",
    )
    solutions_page = Page_Heading(
        Title="solutions",
        Slogan_1='"The Future of AI"',
        Slogan_2="Today.",
        Tagline="Solutions devised by ELF.",
    )
    enquiry_page = Page_Heading(
        Title="enquiry",
        Slogan_1="Let's",
        Slogan_2="Talk",
        Tagline=(
            "Whether you need a specific solution or a general consult, we are eager to hear from you."
        ),
    )

    slide_about_us_1 = Slide(
        title="Adaptable",
        description=(
            "There is no standard solution for all firms. We have the ability to "
            "quickly adjust strategies, recommendations and solutions to suit your particular needs"
        ),
        owner="about_us",
        icon="fa-puzzle-piece",
    )
    slide_about_us_2 = Slide(
        title="Data-driven",
        description=(
            "Elf heavily emphasises providing measurable results. Elf will always provide "
            "a report with quantifible metrics to show the positive impact of our solutions"
        ),
        owner="about_us",
        icon="fa-chart-line",
    )
    slide_about_us_3 = Slide(
        title="Technical",
        description=(
            "Elf's strength lies in knowledge depth for proposed solutions. Every project "
            "is accompanied with an unneccessarily in-depth technical report"
        ),
        owner="about_us",
        icon="fa-terminal",
    )
    mini_slide_about_us_1 = Slide(
        title="Consultation",
        description=(
            "An ELF representative meets your firm's representative for a consultation, "
            "delving into firm specific issues"
        ),
        owner="about_us_mini",
        icon="fa-terminal",
    )
    mini_slide_about_us_2 = Slide(
        title="Proposal",
        description=(
            "ELF researches and compiles a proposal detailing AI solutions suitable for your firm."
        ),
        owner="about_us_mini",
        icon="fa-terminal",
    )
    mini_slide_about_us_3 = Slide(
        title="Implementation",
        description=(
            "ELF colloborates with your team to seamlessly integrate and implement the proposed solutions."
        ),
        owner="about_us_mini",
        icon="fa-terminal",
    )
    mini_slide_about_us_4 = Slide(
        title="Maintenance",
        description=(
            "ELF cares deeply about reliability of our systems and will continue to monitor, "
            "upgrade and maintain our implementations."
        ),
        owner="about_us_mini",
        icon="fa-terminal",
    )

    service_4 = Service(
        title="ELF Consultation",
        description=(
            "Book a free meeting to discuss your companies processes. Elf will "
            "research, craft and implement a unique AI and Automation solution"
        ),
        icon="fa-handshake",
    )
    f4_2 = Feature(text="Data-Driven Objectives: Elf provides measurable results.", service=service_4)
    f4_3 = Feature(
        text="Technical: Every project is accompanied with an in-depth technical report",
        service=service_4,
    )
    f4_1 = Feature(
        text=(
            "Adaptable: There is no standard solution for all firms. "
            "We have the ability to quickly adjust strategies, recommendations and solutions"
        ),
        service=service_4,
    )

    service_1 = Service(
        title="ELF Hybrid Transcription",
        description=(
            'A "Certificate of Veracity" compliant system. We leverage '
            "transcription hardware, Elf software and limited human review to "
            "reduce trancription costs by an estimated 93%."
        ),
        icon="fa-microphone-lines",
    )
    f1_1 = Feature(text="Advanced Technology: Plaud Note Pro Hardware", service=service_1)
    f1_2 = Feature(text="High Fidelity: Advanced AI Concensus Model", service=service_1)
    f1_3 = Feature(
        text="High Savings: 93% Cost Reduction on purely human subscription",
        service=service_1,
    )

    service_2 = Service(
        title="ELF Law LLM",
        description=(
            "A locally deployed Large Language Model (LLM) hosted on an in-house server. "
            "It ingests entire case libraries to generates answers based on your accumulated knowledge."
        ),
        icon="fa-brain",
    )
    f2_1 = Feature(
        text="High Data Security: Local deployment ensures sensitive data stays in-house.",
        service=service_2,
    )
    f2_2 = Feature(
        text="No Hallucination Risk: Citation is forced, meaning cases cited will be real.",
        service=service_2,
    )
    f2_3 = Feature(
        text="High Control: Your lawyers likely use AI, this provides an avenue to manage it,",
        service=service_2,
    )

    service_3 = Service(
        title="ELF Education Audio-AI",
        description=(
            "An integrated AI solution based on utilising ceiling mounted microphone arrays to "
            "provide analysis, insights and reports for parents and teachers alike"
        ),
        icon="fa-ear-listen",
    )
    f3_1 = Feature(
        text="High Fidelity: Audio is captured accurately by ceiling mounted microphone arrays.",
        service=service_3,
    )
    f3_2 = Feature(
        text="POPIA compliant: Through Voice Identification and audio deletion, we ensure privacy.",
        service=service_3,
    )
    f3_3 = Feature(
        text="Insightful: Provides early detection, social insights and academic profiles.",
        service=service_3,
    )

    db.session.add_all(
        [
            branding,
            about_us_page,
            solutions_page,
            enquiry_page,
            slide_about_us_1,
            slide_about_us_2,
            slide_about_us_3,
            mini_slide_about_us_1,
            mini_slide_about_us_2,
            mini_slide_about_us_3,
            mini_slide_about_us_4,
            service_4,
            f4_2,
            f4_3,
            f4_1,
            service_1,
            f1_1,
            f1_2,
            f1_3,
            service_2,
            f2_1,
            f2_2,
            f2_3,
            service_3,
            f3_1,
            f3_2,
            f3_3,
        ]
    )
    db.session.commit()
    print("--- Public site seed complete ---")


def _seed_internal_site_data() -> None:
    seeded_any = False

    if not InternalClient.query.first():
        client_one = InternalClient(
            name="Apex Legal Group",
            industry="Legal Services",
            account_owner="Shingai Mushonga",
            status="active",
            notes="Pilot client for workflow automation and legal research support.",
        )
        client_two = InternalClient(
            name="BrightPath Academy",
            industry="Education",
            account_owner="Operations Team",
            status="active",
            notes="Audio intelligence engagement with teaching outcomes dashboard.",
        )
        db.session.add_all([client_one, client_two])
        db.session.flush()

        project_one = InternalProject(
            name="Matter Intake Automation",
            client=client_one,
            stage="Delivery",
            status="on-track",
            summary="Automate client intake classification and assignment.",
        )
        project_two = InternalProject(
            name="Classroom Audio Insights",
            client=client_two,
            stage="Validation",
            status="at-risk",
            summary="Deploy quality checks and reporting pipeline for school stakeholders.",
        )
        db.session.add_all([project_one, project_two])
        db.session.flush()

        intake_task = InternalTask(
            project=project_one,
            title="Finalize intake taxonomy",
            assignee="Research Team",
            priority="high",
            status="in-progress",
        )
        routing_task = InternalTask(
            project=project_one,
            title="Review edge-case routing",
            assignee="Delivery Team",
            priority="medium",
            status="todo",
        )
        audio_task = InternalTask(
            project=project_two,
            title="Validate microphone placement model",
            assignee="Field Ops",
            priority="high",
            status="in-progress",
        )
        db.session.add_all([intake_task, routing_task, audio_task])
        db.session.flush()
        db.session.add(
            InternalTask(
                project=project_one,
                parent_task=intake_task,
                title="Confirm confidence thresholds",
                assignee="Research Team",
                priority="medium",
                status="todo",
            )
        )
        seeded_any = True

    if not InternalResource.query.first():
        def get_or_create_tag(raw_name: str) -> InternalResourceTag:
            normalized_name = " ".join(raw_name.strip().lower().split())
            existing_tag = InternalResourceTag.query.filter_by(name=normalized_name).first()
            if existing_tag:
                return existing_tag
            new_tag = InternalResourceTag(name=normalized_name)
            db.session.add(new_tag)
            db.session.flush()
            return new_tag

        project_for_playbook = InternalProject.query.filter_by(name="Matter Intake Automation").first()
        project_for_template = InternalProject.query.filter_by(name="Classroom Audio Insights").first()
        fallback_project = InternalProject.query.order_by(InternalProject.created_at.asc()).first()

        task_for_playbook = InternalTask.query.filter_by(title="Finalize intake taxonomy").first()
        task_for_template = InternalTask.query.filter_by(title="Review edge-case routing").first()
        task_for_checklist = InternalTask.query.filter_by(title="Validate microphone placement model").first()
        fallback_task = InternalTask.query.order_by(InternalTask.created_at.asc()).first()

        delivery_playbook = InternalResource(
            title="Delivery Playbook",
            category="operations",
            link="/internal/resources#delivery-playbook",
            description="Standard project execution flow from discovery to deployment.",
            projects=[project_for_playbook or fallback_project] if (project_for_playbook or fallback_project) else [],
            tasks=[task_for_playbook or fallback_task] if (task_for_playbook or fallback_task) else [],
        )

        proposal_template = InternalResource(
            title="Proposal Template",
            category="sales",
            link="/internal/resources#proposal-template",
            description="Reusable proposal structure for consultancy engagements.",
            projects=[project_for_template or fallback_project] if (project_for_template or fallback_project) else [],
            tasks=[task_for_template or fallback_task] if (task_for_template or fallback_task) else [],
        )

        security_checklist = InternalResource(
            title="Security Checklist",
            category="compliance",
            link="/internal/resources#security-checklist",
            description="Controls and review points before production deployment.",
            projects=[project_for_template or fallback_project] if (project_for_template or fallback_project) else [],
            tasks=[task_for_checklist or fallback_task] if (task_for_checklist or fallback_task) else [],
        )
        db.session.add_all([delivery_playbook, proposal_template, security_checklist])

        delivery_playbook.tags = [
            get_or_create_tag("delivery"),
            get_or_create_tag("playbook"),
            get_or_create_tag("operations"),
        ]
        proposal_template.tags = [
            get_or_create_tag("proposal"),
            get_or_create_tag("sales"),
            get_or_create_tag("template"),
        ]
        security_checklist.tags = [
            get_or_create_tag("security"),
            get_or_create_tag("compliance"),
            get_or_create_tag("deployment"),
        ]

        seeded_any = True

    if not InternalAnnouncement.query.first():
        db.session.add(
            InternalAnnouncement(
                title="Internal Portal Enabled",
                body=(
                    "Use this portal for project visibility, knowledge sharing, and delivery coordination. "
                    "Create staff accounts with the Flask CLI command: create-internal-user."
                ),
            )
        )
        seeded_any = True

    admin_email = (os.getenv("INTERNAL_ADMIN_EMAIL") or "").strip().lower()
    admin_password = os.getenv("INTERNAL_ADMIN_PASSWORD") or ""
    admin_name = (os.getenv("INTERNAL_ADMIN_NAME") or "Portal Admin").strip() or "Portal Admin"
    if admin_email and admin_password and not InternalUser.query.filter_by(email=admin_email).first():
        admin_user = InternalUser(full_name=admin_name, email=admin_email, role="admin", is_active=True)
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        seeded_any = True

    if seeded_any:
        db.session.commit()
        print("--- Internal portal seed complete ---")


def setup_database(seed: bool = False) -> None:
    """Creates tables and optionally seeds data."""
    db.create_all()
    if not seed:
        return

    _seed_public_site_data()
    _seed_internal_site_data()
    print("--- Database Ready ---")
