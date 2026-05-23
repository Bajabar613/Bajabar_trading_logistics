from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, engine
from models import Base, Contact

import os
import uuid
import logging
import smtplib
import ssl
import asyncio

from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone

# =========================================================
# LOAD ENV
# =========================================================

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# =========================================================
# CREATE DATABASE TABLES
# =========================================================

Base.metadata.create_all(bind=engine)

# =========================================================
# APP
# =========================================================

app = FastAPI(title="BAJABAR API")

api_router = APIRouter(prefix="/api")

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# =========================================================
# Pydantic MODELS
# =========================================================

class ContactIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    email: EmailStr
    phone: Optional[str] = ""
    company: Optional[str] = ""
    service: Optional[str] = ""
    message: str
    division: str


class ContactOut(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = ""
    company: Optional[str] = ""
    service: Optional[str] = ""
    message: str
    division: str
    timestamp: str

# =========================================================
# EMAIL FUNCTION
# =========================================================

def _send_email(to_addrs: list, subject: str, html_body: str) -> bool:

    host = os.environ.get("SMTP_HOST")

    logger.info(f"SMTP HOST: {host}")

    if not host:
        logger.info("SMTP not configured")
        return False

    try:

        port = int(os.environ.get("SMTP_PORT", "465"))

        user = os.environ.get("SMTP_USER", "")

        pwd = os.environ.get("SMTP_PASS", "")

        sender = os.environ.get("SMTP_FROM", user)

        logger.info(f"Connecting to SMTP: {host}:{port}")

        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject

        msg["From"] = sender

        msg["To"] = ", ".join(to_addrs)

        msg.attach(MIMEText(html_body, "html"))

        ctx = ssl.create_default_context()

        with smtplib.SMTP_SSL(
             host,
             465,
             context=ctx,
             timeout=60
        ) as server:

            server.login(user, pwd)

            server.sendmail(
                sender,
                to_addrs,
                msg.as_string()
            )
        logger.info(f"Email sent successfully to {to_addrs}")

        return True

    except Exception as e:

        import traceback

        logger.error("========== EMAIL ERROR ==========")
        logger.error(str(e))
        traceback.print_exc()
        logger.error("================================")

        return False

# =========================================================
# ROOT ROUTES
# =========================================================

@api_router.get("/")
async def root():

    return {
        "message": "BAJABAR API up",
        "service": "bajabar"
    }


@api_router.get("/health")
async def health():

    return {
        "status": "ok"
    }

# =========================================================
# CONTACT FORM
# =========================================================

@api_router.post("/contact", response_model=ContactOut)
async def submit_contact(payload: ContactIn):

    if payload.division not in ("logistics", "trading"):

        raise HTTPException(
            status_code=400,
            detail="Invalid division"
        )

    # =====================================================
    # CREATE RECORD
    # =====================================================

    record = payload.model_dump()

    record["id"] = str(uuid.uuid4())

    record["timestamp"] = datetime.now(
        timezone.utc
    ).isoformat()

    # =====================================================
    # SAVE TO SUPABASE POSTGRES
    # =====================================================

    db = SessionLocal()

    try:

        contact = Contact(
            id=record["id"],
            name=record["name"],
            email=record["email"],
            phone=record["phone"],
            company=record["company"],
            service=record["service"],
            message=record["message"],
            division=record["division"],
            timestamp=record["timestamp"]
        )

        db.add(contact)

        db.commit()

    finally:

        db.close()

    # =====================================================
    # COMPANY EMAILS
    # =====================================================

    company_emails = os.environ.get(
        "NOTIFY_EMAILS",
        "sales@bajabarinc.ae,contact@bajabarinc.ae"
    ).split(",")

    company_emails = [
        e.strip()
        for e in company_emails
        if e.strip()
    ]

    division_label = (
        "Freight & Logistics"
        if payload.division == "logistics"
        else "General Trading"
    )

    # =====================================================
    # COMPANY NOTIFICATION EMAIL
    # =====================================================

    notif_html = f"""
<div style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0">
    <tr>
      <td align="center">

        <table width="650" cellpadding="0" cellspacing="0"
        style="background:#ffffff;border-radius:14px;
        overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.08)">

          <tr>
            <td style="background:#0b3d91;padding:28px">
              <h2 style="margin:0;color:#ffffff;font-size:24px">
                New Website Enquiry
              </h2>

              <p style="margin:8px 0 0;color:#dbeafe;font-size:14px">
                BAJABAR INCORPORATION FZE
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:35px">

              <table width="100%" cellpadding="10" cellspacing="0"
              style="margin-top:20px;border-collapse:collapse">

                <tr style="background:#f8fafc">
                  <td style="font-weight:700;width:180px">
                    Customer Name
                  </td>

                  <td>{payload.name}</td>
                </tr>

                <tr>
                  <td style="font-weight:700">
                    Email Address
                  </td>

                  <td>{payload.email}</td>
                </tr>

                <tr style="background:#f8fafc">
                  <td style="font-weight:700">
                    Phone Number
                  </td>

                  <td>{payload.phone or '-'}</td>
                </tr>

                <tr>
                  <td style="font-weight:700">
                    Company
                  </td>

                  <td>{payload.company or '-'}</td>
                </tr>

                <tr style="background:#f8fafc">
                  <td style="font-weight:700">
                    Service
                  </td>

                  <td>{payload.service or '-'}</td>
                </tr>

                <tr>
                  <td style="font-weight:700">
                    Division
                  </td>

                  <td>{division_label}</td>
                </tr>

              </table>

              <div style="margin-top:30px">

                <p style="font-weight:700">
                  Customer Message
                </p>

                <div style="background:#f8fafc;
                border-left:4px solid #0b3d91;
                padding:18px;
                border-radius:8px;
                line-height:1.8">

                  {payload.message}

                </div>

              </div>

              <p style="margin-top:30px;font-size:13px">
                Submitted via BAJABAR Website Contact Form<br>
                Time: {record['timestamp']}
              </p>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""

    # =====================================================
    # CUSTOMER AUTO REPLY EMAIL
    # =====================================================

    reply_html = f"""
<div style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0">
    <tr>
      <td align="center">

        <table width="650" cellpadding="0" cellspacing="0"
        style="background:#ffffff;border-radius:14px;
        overflow:hidden;box-shadow:0 6px 24px rgba(0,0,0,0.08)">

          <tr>
            <td style="background:#0b3d91;padding:30px;text-align:center">

              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700">
                BAJABAR INCORPORATION FZE
              </h1>

              <p style="margin:8px 0 0;color:#dbeafe;font-size:14px">
                Freight • Logistics • General Trading
              </p>

            </td>
          </tr>

          <tr>
            <td style="padding:40px">

              <p style="font-size:16px;margin:0 0 20px">
                Dear <strong>{payload.name}</strong>,
              </p>

              <p style="font-size:15px;line-height:1.8">
                Thank you for contacting
                <strong>BAJABAR INCORPORATION FZE</strong>.
              </p>

              <p style="font-size:15px;line-height:1.8">
                Your enquiry has been successfully received.
              </p>

              <div style="background:#f8fafc;
              border-left:4px solid #0b3d91;
              padding:18px 20px;
              margin:30px 0;
              border-radius:8px">

                <p style="margin:0 0 10px;font-weight:600">
                  Your Submitted Enquiry
                </p>

                <p style="margin:0;line-height:1.7">
                  {payload.message}
                </p>

              </div>

              <div style="margin-top:35px">

                <p style="margin:0;font-weight:700">
                  Best Regards,
                </p>

                <p style="margin:8px 0 0;
                color:#0b3d91;
                font-weight:700;
                font-size:18px">

                  BAJABAR INCORPORATION FZE

                </p>

                <p style="margin:10px 0 0;
                line-height:1.7;
                font-size:14px">

                  SAIF Zone, Sharjah, UAE<br>
                  Email: sales@bajabarinc.ae<br>
                  Phone: +971 6 5526501

                </p>

              </div>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""

    # =====================================================
    # SEND EMAILS
    # =====================================================

    loop = asyncio.get_running_loop()

    company_sent = await loop.run_in_executor(
        None,
        _send_email,
        company_emails,
        f"[BAJABAR {division_label}] New Enquiry from {payload.name}",
        notif_html
    )

    customer_sent = await loop.run_in_executor(
        None,
        _send_email,
        [payload.email],
        "We received your enquiry – BAJABAR INCORPORATION FZE",
        reply_html
    )

    if not company_sent or not customer_sent:

        raise HTTPException(
            status_code=500,
            detail="Email sending failed"
        )

    return ContactOut(**record)

# =========================================================
# CONTACT LIST
# =========================================================

@api_router.get("/contacts", response_model=List[ContactOut])
async def list_contacts(
    division: Optional[str] = None,
    limit: int = 100
):

    db = SessionLocal()

    try:

        query = db.query(Contact)

        if division:
            query = query.filter(Contact.division == division)

        rows = query.order_by(
            Contact.timestamp.desc()
        ).limit(limit).all()

        return [
            ContactOut(
                id=row.id,
                name=row.name,
                email=row.email,
                phone=row.phone,
                company=row.company,
                service=row.service,
                message=row.message,
                division=row.division,
                timestamp=row.timestamp
            )
            for row in rows
        ]

    finally:

        db.close()

# =========================================================
# APP CONFIG
# =========================================================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get(
        "CORS_ORIGINS",
        "*"
    ).split(","),

    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# STARTUP
# =========================================================

@app.get("/")
async def main():

    return {
        "message": "BAJABAR Backend Running"
    }