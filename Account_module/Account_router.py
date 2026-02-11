"""
Account feedback router.

Provides an endpoint for users to submit reasons for:
- Phone number change
- Account deletion

This does NOT execute the change/delete immediately; it only logs the request
for internal review.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional

from deps import get_db
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.User.user_model import User
from Member_module.Member_model import Member

from .Account_model import AccountFeedbackRequest
from .Account_schema import AccountFeedbackRequestBody


router = APIRouter(prefix="/account", tags=["Account"])


@router.post("/feedback")
def submit_account_feedback(
    data: AccountFeedbackRequestBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_member: Optional[Member] = Depends(get_current_member),
):
    """
    Submit feedback for phone number change and/or account deletion.
    Backend logs one row per non-empty reason.

    **Phone Change Request JSON:**
    ```json
    {
      "current_phone": "6364309657",
      "new_phone": "9876543210",
      "phone_change_reason": "I lost my old SIM card and got a new number",
      "account_delete_reason": null
    }
    ```

    **Account Deletion Request JSON:**
    ```json
    {
      "account_delete_reason": "I no longer need this account",
      "phone_change_reason": null,
      "current_phone": null,
      "new_phone": null
    }
    ```
    """
    # Basic validation: at least one reason must be provided
    phone_reason = (data.phone_change_reason or "").strip()
    delete_reason = (data.account_delete_reason or "").strip()

    if not phone_reason and not delete_reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please share a short reason for phone number change or account deletion.",
        )

    # Derive member information (self profile) - fall back to user if not available
    member_id = current_member.id if current_member else None
    member_name = None
    if current_member and getattr(current_member, "name", None):
        member_name = current_member.name
    elif getattr(current_user, "name", None):
        member_name = current_user.name

    # Helper to insert a feedback row
    def _create_feedback(request_type: str, reason: str, new_phone: Optional[str] = None) -> None:
        if not reason:
            return

        feedback = AccountFeedbackRequest(
            user_id=current_user.id,
            member_id=member_id,
            member_name=member_name,
            current_phone=data.current_phone,
            new_phone=new_phone if request_type == "PHONE_CHANGE" else None,  # Only store new_phone for phone change requests
            request_type=request_type,
            reason=reason,
        )
        db.add(feedback)

    # Create rows for each non-empty reason
    if phone_reason:
        _create_feedback("PHONE_CHANGE", phone_reason, data.new_phone)

    if delete_reason:
        _create_feedback("ACCOUNT_DELETION", delete_reason)

    db.commit()

    return {
        "status": "success",
        "message": "Your request has been submitted.",
    }


