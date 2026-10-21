import csv
import io
from datetime import datetime
from models import Complaint, User


def generate_csv(complaints):
    """Return a CSV string for the given list of Complaint objects."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Complaint ID', 'Title', 'Category', 'Priority', 'Status',
        'Building', 'Floor', 'Room', 'Submitted By', 'Assigned To',
        'Submitted At', 'Updated At', 'Resolved At',
    ])
    for c in complaints:
        assignee_name = c.assignee.full_name if c.assignee else ''
        submitter_name = c.submitter.full_name if c.submitter else ''
        # Prevent CSV formula injection
        def safe(val):
            val = str(val) if val is not None else ''
            if val.startswith(('=', '+', '-', '@')):
                val = "'" + val
            return val

        writer.writerow([
            safe(c.complaint_id),
            safe(c.title),
            safe(c.category),
            safe(c.priority),
            safe(c.status),
            safe(c.building),
            safe(c.floor),
            safe(c.room_number),
            safe(submitter_name),
            safe(assignee_name),
            safe(c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''),
            safe(c.updated_at.strftime('%Y-%m-%d %H:%M') if c.updated_at else ''),
            safe(c.resolved_at.strftime('%Y-%m-%d %H:%M') if c.resolved_at else ''),
        ])
    return output.getvalue()
