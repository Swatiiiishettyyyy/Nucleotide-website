"""
Audit log query endpoints for retrieving audit logs.
Useful for compliance, forensics, and debugging.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.Utils.datetime_utils import to_ist_isoformat
from Login_module.User.user_model import User

# Import all audit models
from Login_module.OTP.OTP_Log_Model import OTPAuditLog
from Cart_module.Cart_audit_model import AuditLog as CartAuditLog
from Address_module.Address_audit_model import AddressAudit
from Audit_module.Profile_audit_crud import ProfileAuditLog  # Model is in this file
from Login_module.Device.Device_session_audit_model import SessionAuditLog
from Member_module.Member_audit_model import MemberAuditLog

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/otp")
def get_otp_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    phone_number: Optional[str] = Query(None, description="Filter by phone number"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get OTP audit logs. Admin only or own logs."""
    query = db.query(OTPAuditLog)
    
    # Non-admin users can only see their own logs
    if not getattr(current_user, 'is_admin', False):
        query = query.filter(OTPAuditLog.user_id == current_user.id)
    elif user_id:
        query = query.filter(OTPAuditLog.user_id == user_id)
    
    if event_type:
        query = query.filter(OTPAuditLog.event_type == event_type)
    if phone_number:
        query = query.filter(OTPAuditLog.phone_number.contains(phone_number))
    if correlation_id:
        query = query.filter(OTPAuditLog.correlation_id == correlation_id)
    if start_date:
        query = query.filter(OTPAuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(OTPAuditLog.timestamp <= end_date)
    
    logs = query.order_by(OTPAuditLog.timestamp.desc()).limit(limit).all()
    
    return {
        "status": "success",
        "count": len(logs),
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "device_id": log.device_id,
                "event_type": log.event_type,
                "phone_number": log.phone_number,
                "reason": log.reason,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "correlation_id": log.correlation_id,
                "timestamp": to_ist_isoformat(log.timestamp)
            }
            for log in logs
        ]
    }


@router.get("/cart")
def get_cart_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get cart audit logs."""
    query = db.query(CartAuditLog)
    
    if not getattr(current_user, 'is_admin', False):
        query = query.filter(CartAuditLog.user_id == current_user.id)
    elif user_id:
        query = query.filter(CartAuditLog.user_id == user_id)
    
    if action:
        query = query.filter(CartAuditLog.action == action)
    if entity_type:
        query = query.filter(CartAuditLog.entity_type == entity_type)
    if correlation_id:
        query = query.filter(CartAuditLog.correlation_id == correlation_id)
    if start_date:
        query = query.filter(CartAuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(CartAuditLog.created_at <= end_date)
    
    logs = query.order_by(CartAuditLog.created_at.desc()).limit(limit).all()
    
    return {
        "status": "success",
        "count": len(logs),
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "correlation_id": log.correlation_id,
                "created_at": to_ist_isoformat(log.created_at)
            }
            for log in logs
        ]
    }


@router.get("/sessions")
def get_session_audit_logs(
    user_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    correlation_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get session audit logs."""
    query = db.query(SessionAuditLog)
    
    if not getattr(current_user, 'is_admin', False):
        query = query.filter(SessionAuditLog.user_id == current_user.id)
    elif user_id:
        query = query.filter(SessionAuditLog.user_id == user_id)
    
    if event_type:
        query = query.filter(SessionAuditLog.event_type == event_type)
    if correlation_id:
        query = query.filter(SessionAuditLog.correlation_id == correlation_id)
    
    logs = query.order_by(SessionAuditLog.timestamp.desc()).limit(limit).all()
    
    return {
        "status": "success",
        "count": len(logs),
        "data": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "session_id": log.session_id,
                "device_id": log.device_id,
                "event_type": log.event_type,
                "reason": log.reason,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "correlation_id": log.correlation_id,
                "timestamp": to_ist_isoformat(log.timestamp)
            }
            for log in logs
        ]
    }

