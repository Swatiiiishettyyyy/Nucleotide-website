"""
Enquiry router - handles test request / enquiry form submission.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from deps import get_db
from .Enquiry_schema import EnquiryRequestCreate, EnquiryResponse
from .Enquiry_crud import create_enquiry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enquiry", tags=["Enquiry"])

SUCCESS_MESSAGE = "Request received! Our team will contact you shortly."


@router.post("", response_model=EnquiryResponse)
def submit_enquiry(
    data: EnquiryRequestCreate,
    db: Session = Depends(get_db),
):
    """
    Submit an enquiry (name, contact, email, number of tests, optional organization and notes).
    Returns success message: "Request received! Our team will contact you shortly."
    """
    try:
        create_enquiry(
            db=db,
            name=data.name,
            contact_number=data.contact_number,
            email=data.email,
            number_of_tests=data.number_of_tests,
            organization=data.organization,
            notes=data.notes,
        )
        return EnquiryResponse(
            status="success",
            message=SUCCESS_MESSAGE,
            name=data.name,
            organization=data.organization,
            contact_number=data.contact_number,
            email=data.email,
            number_of_tests=data.number_of_tests,
            notes=data.notes,
        )
    except Exception as e:
        logger.exception(f"Enquiry submission failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit request. Please try again.",
        )


@router.get("/form", response_class=HTMLResponse)
def enquiry_form_page():
    """Serve the enquiry form as HTML (for browsers)."""
    return _ENQUIRY_HTML


_ENQUIRY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enquiry / Test Request</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, sans-serif; max-width: 480px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }
    label { display: block; margin-bottom: 0.25rem; font-weight: 500; }
    input, textarea { width: 100%; padding: 0.5rem 0.75rem; margin-bottom: 1rem; border: 1px solid #ccc; border-radius: 6px; }
    textarea { min-height: 80px; resize: vertical; }
    button { width: 100%; padding: 0.75rem; background: #2563eb; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    .optional { color: #64748b; font-weight: 400; }
    .message { padding: 1rem; border-radius: 6px; margin-top: 1rem; display: none; }
    .message.success { background: #dcfce7; color: #166534; }
    .message.error { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <h1>Enquiry / Test Request</h1>
  <form id="enquiryForm">
    <label for="name">Name <span style="color:#dc2626">*</span></label>
    <input type="text" id="name" name="name" required placeholder="Your name">

    <label for="contact_number">Contact number <span style="color:#dc2626">*</span></label>
    <input type="tel" id="contact_number" name="contact_number" required placeholder="e.g. +919876543210">

    <label for="email">Email <span style="color:#dc2626">*</span></label>
    <input type="email" id="email" name="email" required placeholder="you@example.com">

    <label for="number_of_tests">Number of tests required <span style="color:#dc2626">*</span></label>
    <input type="number" id="number_of_tests" name="number_of_tests" required min="1" placeholder="e.g. 5">

    <label for="organization">Organization <span class="optional">(optional)</span></label>
    <input type="text" id="organization" name="organization" placeholder="Your organization">

    <label for="notes">Notes <span class="optional">(optional)</span></label>
    <textarea id="notes" name="notes" placeholder="Any additional notes"></textarea>

    <button type="submit">Submit</button>
  </form>
  <div id="message" class="message" role="alert"></div>

  <script>
    document.getElementById('enquiryForm').addEventListener('submit', async function(e) {
      e.preventDefault();
      const msgEl = document.getElementById('message');
      msgEl.style.display = 'none';
      msgEl.className = 'message';

      const form = e.target;
      const body = {
        name: form.name.value.trim(),
        contact_number: form.contact_number.value.trim(),
        email: form.email.value.trim(),
        number_of_tests: parseInt(form.number_of_tests.value, 10) || 1,
        organization: form.organization.value.trim() || null,
        notes: form.notes.value.trim() || null
      };

      try {
        const base = window.location.origin;
        const res = await fetch(base + '/enquiry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok) {
          msgEl.textContent = data.message || 'Request received! Our team will contact you shortly.';
          msgEl.className = 'message success';
          form.reset();
        } else {
          msgEl.textContent = data.detail || (typeof data.detail === 'object' ? JSON.stringify(data.detail) : 'Something went wrong. Please try again.');
          msgEl.className = 'message error';
        }
        msgEl.style.display = 'block';
      } catch (err) {
        msgEl.textContent = 'Network error. Please try again.';
        msgEl.className = 'message error';
        msgEl.style.display = 'block';
      }
    });
  </script>
</body>
</html>
"""
