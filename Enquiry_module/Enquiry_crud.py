from sqlalchemy.orm import Session
import logging
from typing import Optional

from .Enquiry_model import EnquiryRequest

logger = logging.getLogger(__name__)


def create_enquiry(
    db: Session,
    name: str,
    contact_number: str,
    email: str,
    number_of_tests: int,
    organization: Optional[str] = None,
    notes: Optional[str] = None,
) -> EnquiryRequest:
    """Create a new enquiry request."""
    enquiry = EnquiryRequest(
        name=name.strip(),
        contact_number=contact_number.strip(),
        email=email.strip().lower(),
        number_of_tests=number_of_tests,
        organization=organization.strip() if organization else None,
        notes=notes.strip() if notes else None,
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)
    logger.info(f"Enquiry created: id={enquiry.id}, email={enquiry.email}")
    return enquiry
