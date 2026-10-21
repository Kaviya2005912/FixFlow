import os
import re
import unicodedata
from datetime import datetime
from models import (
    db, Complaint, ComplaintHistory, Notification,
    VALID_STATUSES, VALID_PRIORITIES, VALID_CATEGORIES, STATUS_TRANSITIONS
)


def add_history(complaint, changed_by_id, old_status=None, new_status=None,
                old_priority=None, new_priority=None, note=None):
    """Append an audit-trail entry for a complaint."""
    entry = ComplaintHistory(
        complaint_id=complaint.id,
        changed_by=changed_by_id,
        old_status=old_status,
        new_status=new_status,
        old_priority=old_priority,
        new_priority=new_priority,
        note=note,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)
    return entry


def notify_user(user_id, complaint_id, message):
    """Create an in-app notification."""
    notif = Notification(
        user_id=user_id,
        complaint_id=complaint_id,
        message=message,
        created_at=datetime.utcnow(),
    )
    db.session.add(notif)
    return notif


def safe_filename(filename):
    """Return a safe ASCII filename, preserving the extension."""
    filename = unicodedata.normalize('NFKD', filename)
    filename = filename.encode('ascii', 'ignore').decode('ascii')
    filename = re.sub(r'[^\w.\-]', '_', filename)
    return filename


def allowed_file(filename, allowed_extensions):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in allowed_extensions
    )


def transition_allowed(current_status, new_status, role):
    """Return True if the role is allowed to move complaint from current_status to new_status."""
    allowed = STATUS_TRANSITIONS.get(role, {}).get(current_status, [])
    return new_status in allowed
