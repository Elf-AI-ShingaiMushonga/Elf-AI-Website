from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from flask_mail import Message

from extension import mail
from models import Branding, Page_Heading, Service, Slide, db

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    services = Service.query.all()
    branding = Branding.query.first()
    carousel_images = ["hero1.png"]
    return render_template(
        "index.html",
        services=services,
        branding=branding,
        carousel_images=carousel_images,
    )


@main_bp.route("/solutions")
def solutions():
    services = Service.query.all()
    solution = Page_Heading.query.filter_by(Title="solutions").first()
    return render_template("solutions.html", services=services, solution=solution)


@main_bp.route("/about")
def about():
    about_us = Page_Heading.query.filter_by(Title="about_us").first()
    about_us_slide = Slide.query.filter_by(owner="about_us").all()
    about_us_slide_mini = Slide.query.filter_by(owner="about_us_mini").all()
    picture = "hero2.png"
    return render_template(
        "about.html",
        about_us=about_us,
        about_us_slide=about_us_slide,
        about_us_slide_mini=about_us_slide_mini,
        picture=picture,
    )


@main_bp.route("/enquire")
def enquire():
    enquiry = Page_Heading.query.filter_by(Title="enquiry").first()
    services = Service.query.all()
    return render_template("enquire.html", enquiry=enquiry, services=services)


@main_bp.route("/contact", methods=["POST"])
def contact():
    name = (request.form.get("name") or "").strip()
    email = request.form.get('email')
    message_body = request.form.get('message')  
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
        recipients=['shingai.mushonga@elf-ai.co.za'] # Or use app.config['MAIL_USERNAME']
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
        mail.send(msg) # <--- This actually sends it!
        flash(f"Thank you, {name}. We will contact you regarding '{service_name}'.", "success")
    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        flash("Message saved, but we couldn't send the email confirmation.", "warning")
    return redirect(url_for("main.home", _anchor="contact"))


@main_bp.route("/healthz")
def healthz():
    return {"status": "ok"}, 200
