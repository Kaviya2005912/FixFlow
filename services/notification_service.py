"""Notification helper used by route modules."""
from services.complaint_service import notify_user  # re-export for convenience

__all__ = ['notify_user']
