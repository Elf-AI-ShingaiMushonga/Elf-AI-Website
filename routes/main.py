from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_mail import Message

from extension import mail
from models import Branding, Page_Heading, Service, Slide, db

main_bp = Blueprint("main", __name__)


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
                "name": "ELF AI",
                "alternateName": "ELF-AI",
                "url": site_url,
                "logo": f"{site_url}{url_for('static', filename='images/Logo.png')}",
                "email": "shingai.mushonga@elf-ai.co.za",
                "description": (
                    "ELF AI is a problem-solving AI consultancy that designs, implements, "
                    "and trains teams on practical AI solutions."
                ),
            },
            {
                "@type": "WebSite",
                "@id": f"{site_url}/#website",
                "url": site_url,
                "name": "ELF AI",
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
        "site_name": "ELF AI",
        "keywords": (
            "ELF AI, ELF-AI, AI consultancy, AI solutions, AI automation, "
            "business process automation, SME AI consulting"
        ),
        "structured_data": structured_data,
    }


def _render_page(template_name: str, *, path: str, title: str, description: str, **context):
    seo = _build_seo(path=path, title=title, description=description)
    return render_template(template_name, seo=seo, **context)


@main_bp.route("/")
def home():
    services = Service.query.all()
    branding = Branding.query.first()
    carousel_images = ["hero1.png"]
    return _render_page(
        "index.html",
        path="/",
        title="ELF AI | Problem-Solving AI Consultancy for SMEs",
        description=(
            "ELF AI (ELF-AI) helps businesses solve operational problems with practical AI "
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
        title="AI Solutions | ELF AI",
        description=(
            "Explore ELF AI solution tracks for workflow automation, faster delivery, lower costs, "
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
        title="About ELF AI | AI Problem-Solving Consultancy",
        description=(
            "Learn how ELF AI combines delivery, training, and operational support to build "
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
        title="Contact ELF AI | Start Your AI Consultation",
        description=(
            "Contact ELF AI to discuss your business challenge and get a scoped plan for a "
            "practical, testable AI solution."
        ),
        enquiry=enquiry,
        services=services,
    )


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
    email = request.form.get("email")
    message_body = request.form.get("message")
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
    flash(
        f"Thank you, {name or 'there'}. We will contact you regarding '{service_name}'.",
        "success",
    )

    msg = Message(
        subject=f"New Lead: {name}",
        recipients=["shingai.mushonga@elf-ai.co.za"],  # Or use app.config['MAIL_USERNAME']
    )

    # This creates the email body
    msg.body = f"""
        Name: {name}
        Email: {email}
        Service Interest: {service_name}

        Message:
        {message_body}
    """
    msg.reply_to = email
    try:
        mail.send(msg)  # <--- This actually sends it!
        flash(f"Thank you, {name}. We will contact you regarding '{service_name}'.", "success")
    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        flash("Message saved, but we couldn't send the email confirmation.", "warning")
    return redirect(url_for("main.home", _anchor="contact"))


@main_bp.route("/healthz")
def healthz():
    return {"status": "ok"}, 200
