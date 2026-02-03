from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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


def setup_database(seed: bool = False) -> None:
    """Creates tables and optionally seeds data."""
    db.create_all()
    # Better approach: Check individual tables
    if seed:
        print("--- Seeding Database with ELF Pitch Deck Data ---")
        if not Slide.query.first():       
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

                # ... seed services ...
        if not Service.query.first():
            s4 = Service(
            title="ELF Consultation",
            description=(
                "Book a free meeting to discuss your companies processes. Elf will "
                "research, craft and implement a unique AI and Automation solution"
            ),
            icon="fa-handshake",
            )

            f4_2 = Feature(
                text="Data-Driven Objectives: Elf provides measurable results.", service=s4
            )
            f4_3 = Feature(
                text="Technical: Every project is accompanied with an in-depth technical report",
                service=s4,
            )
            f4_1 = Feature(
                text=(
                    "Adaptable: There is no standard solution for all firms. "
                    "We have the ability to quickly adjust strategies, recommendations and solutions"
                ),
                service=s4,
            )
            s1 = Service(
                title="ELF Hybrid Transcription",
                description=(
                    'A "Certificate of Veracity" compliant system. We leverage '
                    "transcription hardware, Elf software and limited human review to "
                    "reduce trancription costs by an estimated 93%."
                ),
                icon="fa-microphone-lines",
            )
            f1_1 = Feature(text="Advanced Technology: Plaud Note Pro Hardware", service=s1)
            f1_2 = Feature(text="High Fidelity: Advanced AI Concensus Model", service=s1)
            f1_3 = Feature(
                text="High Savings: 93% Cost Reduction on purely human subscription",
                service=s1,
            )
                # ... seed slides ...
                    # 2. ELF Law Agent
            s2 = Service(
                title="ELF Law LLM",
                description=(
                    "A locally deployed Large Language Model (LLM) hosted on an in-house server. "
                    "It ingests entire case libraries to generates answers based on your accumulated knowledge."
                ),
                icon="fa-brain",
            )
            f2_1 = Feature(
                text="High Data Security: Local deployment ensures sensitive data stays in-house.",
                service=s2,
            )
            f2_2 = Feature(
                text="No Hallucination Risk: Citation is forced, meaning cases cited will be real.",
                service=s2,
            )
            f2_3 = Feature(
                text="High Control: Your lawyers likely use AI, this provides an avenue to manage it,",
                service=s2,
            )

            # 3. Workflow Automation
            s3 = Service(
                title="ELF Education Audio-AI",
                description=(
                    "An integrated AI solution based on utilising ceiling mounted microphone arrays to "
                    "provide analysis, insights and reports for parents and teachers alike"
                ),
                icon="fa-ear-listen",
            )
            f3_1 = Feature(
                text="High Fidelity: Audio is captured accurately by ceiling mounted microphone arrays.",
                service=s3,
            )
            f3_2 = Feature(
                text="POPIA compliant: Through Voice Identification and audio deletion, we ensure privacy.",
                service=s3,
            )
            f3_3 = Feature(
                text="Insightful: Provides early detection, social insights and academic profiles.",
                service=s3,
            )
        if not Page_Heading.query.first():
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
        if not Branding.query.first():
            branding = Branding(
            Title="ELF",
            Slogan="Novel AI Solutions",
            Tagline=(
                "Enhance the effiency of your business with tailored AI-integration "
                "and automation solutions, built for your specific needs"
            ),
        )
        db.session.add_all(
            [
                s4,
                f4_2,
                f4_3,
                f4_1,
                s1,
                s2,
                s3,
                f1_1,
                f1_2,
                f1_3,
                f2_1,
                f2_2,
                f2_3,
                f3_1,
                f3_2,
                f3_3,
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
            ]
        )
        db.session.commit()
        print("--- Database Ready ---")
