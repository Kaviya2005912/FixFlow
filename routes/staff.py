from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort)
from flask_login import current_user
from extensions import db
from models import Complaint, Comment, Notification, ComplaintHistory, STATUS_TRANSITIONS
from services.complaint_service import add_history, notify_user, transition_allowed
from routes.auth_utils import login_required_role

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


@staff_bp.route('/dashboard')
@login_required_role('staff')
def dashboard():
    sid = current_user.id
    assigned = Complaint.query.filter_by(assigned_to=sid).filter(
        Complaint.status.notin_(['Resolved', 'Closed'])
    ).count()
    in_progress = Complaint.query.filter_by(assigned_to=sid, status='In Progress').count()
    completed = Complaint.query.filter_by(assigned_to=sid).filter(
        Complaint.status.in_(['Resolved', 'Closed'])
    ).count()
    high_prio = Complaint.query.filter_by(assigned_to=sid, priority='High').filter(
        Complaint.status.notin_(['Resolved', 'Closed'])
    ).count()
    recent = (Complaint.query.filter_by(assigned_to=sid)
              .order_by(Complaint.updated_at.desc()).limit(5).all())
    unread_count = Notification.query.filter_by(user_id=sid, is_read=0).count()

    return render_template('staff_dashboard.html',
                           assigned=assigned, in_progress=in_progress,
                           completed=completed, high_prio=high_prio,
                           recent=recent, unread_count=unread_count)


@staff_bp.route('/assignments')
@login_required_role('staff')
def assignments():
    sid = current_user.id
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)

    query = Complaint.query.filter_by(assigned_to=sid)
    if status_filter:
        query = query.filter_by(status=status_filter)

    from flask import current_app
    complaints = query.order_by(Complaint.updated_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )
    unread_count = Notification.query.filter_by(user_id=sid, is_read=0).count()
    return render_template('assignments.html', complaints=complaints,
                           status_filter=status_filter, unread_count=unread_count)


@staff_bp.route('/complaints/<int:complaint_id>', methods=['GET', 'POST'])
@login_required_role('staff')
def assigned_complaint(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    if c.assigned_to != current_user.id:
        abort(403)

    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'progress':
            if not transition_allowed(c.status, 'In Progress', 'staff'):
                flash(f'Cannot mark In Progress from status: {c.status}.', 'error')
            else:
                old = c.status
                c.status = 'In Progress'
                c.updated_at = datetime.utcnow()
                note = request.form.get('progress_note', '').strip() or 'Work started.'
                add_history(c, current_user.id,
                            old_status=old, new_status='In Progress', note=note)
                comment = Comment(complaint_id=c.id, user_id=current_user.id,
                                  message=note, visibility='public')
                db.session.add(comment)
                notify_user(c.created_by, c.id,
                            f'Work has started on your complaint {c.complaint_id}.')
                db.session.commit()
                flash('Status updated to In Progress.', 'success')

        elif action == 'resolve':
            resolution_note = request.form.get('resolution_note', '').strip()
            if not resolution_note:
                flash('A resolution description is required before marking as Resolved.', 'error')
            elif not transition_allowed(c.status, 'Resolved', 'staff'):
                flash(f'Cannot resolve from status: {c.status}.', 'error')
            else:
                old = c.status
                c.status = 'Resolved'
                c.resolved_at = datetime.utcnow()
                c.updated_at = datetime.utcnow()
                add_history(c, current_user.id,
                            old_status=old, new_status='Resolved',
                            note=f'Resolution: {resolution_note}')
                comment = Comment(complaint_id=c.id, user_id=current_user.id,
                                  message=f'[Resolution] {resolution_note}', visibility='public')
                db.session.add(comment)
                notify_user(c.created_by, c.id,
                            f'Your complaint {c.complaint_id} has been resolved! '
                            f'Resolution: {resolution_note}')
                db.session.commit()
                flash('Complaint marked as Resolved.', 'success')

        elif action == 'note':
            msg = request.form.get('note_message', '').strip()
            if not msg:
                flash('Note cannot be empty.', 'error')
            else:
                comment = Comment(complaint_id=c.id, user_id=current_user.id,
                                  message=msg, visibility='public')
                db.session.add(comment)
                db.session.commit()
                flash('Progress note added.', 'success')

        return redirect(url_for('staff.assigned_complaint', complaint_id=complaint_id))

    # GET
    public_comments = (Comment.query.filter_by(complaint_id=c.id, visibility='public')
                       .order_by(Comment.created_at.asc()).all())
    history = c.history.order_by(ComplaintHistory.created_at.asc()).all()

    return render_template('assigned_complaint.html',
                           complaint=c,
                           comments=public_comments,
                           history=history,
                           unread_count=unread_count,
                           transitions=STATUS_TRANSITIONS.get('staff', {}))
