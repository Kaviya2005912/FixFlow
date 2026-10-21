from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, current_app, make_response)
from flask_login import current_user
from sqlalchemy import func
from extensions import db
from models import (Complaint, User, Comment, Notification, ComplaintHistory,
                    VALID_STATUSES, VALID_PRIORITIES, VALID_CATEGORIES,
                    STATUS_TRANSITIONS)
from services.complaint_service import add_history, notify_user, transition_allowed
from services.report_service import generate_csv
from routes.auth_utils import login_required_role

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required_role('admin')
def dashboard():
    total = Complaint.query.count()
    submitted = Complaint.query.filter_by(status='Submitted').count()
    pending = Complaint.query.filter(
        Complaint.status.in_(['Submitted', 'Acknowledged', 'Assigned', 'Reopened'])
    ).count()
    in_progress = Complaint.query.filter_by(status='In Progress').count()
    resolved = Complaint.query.filter(
        Complaint.status.in_(['Resolved', 'Closed'])
    ).count()
    high_open = Complaint.query.filter_by(priority='High').filter(
        Complaint.status.notin_(['Resolved', 'Closed'])
    ).count()

    # Category distribution
    cat_counts = (db.session.query(Complaint.category, func.count(Complaint.id))
                  .group_by(Complaint.category).all())
    # Status distribution
    status_counts = (db.session.query(Complaint.status, func.count(Complaint.id))
                     .group_by(Complaint.status).all())

    recent = (Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all())
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    return render_template('admin_dashboard.html',
                           total=total, submitted=submitted, pending=pending,
                           in_progress=in_progress, resolved=resolved,
                           high_open=high_open,
                           cat_counts=cat_counts, status_counts=status_counts,
                           recent=recent, unread_count=unread_count)


@admin_bp.route('/complaints')
@login_required_role('admin')
def manage_complaints():
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    priority_filter = request.args.get('priority', '')
    assigned_filter = request.args.get('assigned', '')
    q = request.args.get('q', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)

    query = Complaint.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    if assigned_filter == 'unassigned':
        query = query.filter(Complaint.assigned_to.is_(None))
    elif assigned_filter:
        query = query.filter_by(assigned_to=int(assigned_filter))
    if q:
        query = query.filter(
            Complaint.title.ilike(f'%{q}%') | Complaint.description.ilike(f'%{q}%')
        )
    if date_from:
        try:
            query = query.filter(Complaint.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Complaint.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass

    complaints = query.order_by(Complaint.created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )
    staff_list = User.query.filter_by(role='staff', is_active=1).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    return render_template('manage_complaints.html',
                           complaints=complaints, categories=VALID_CATEGORIES,
                           statuses=VALID_STATUSES, priorities=VALID_PRIORITIES,
                           staff_list=staff_list, unread_count=unread_count,
                           status_filter=status_filter,
                           category_filter=category_filter,
                           priority_filter=priority_filter,
                           assigned_filter=assigned_filter,
                           date_from=date_from, date_to=date_to, q=q)


@admin_bp.route('/complaints/<int:complaint_id>', methods=['GET', 'POST'])
@login_required_role('admin')
def manage_complaint(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    staff_list = User.query.filter_by(role='staff', is_active=1).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    if request.method == 'POST':
        action = request.form.get('action', '')

        # --- Change Priority ---
        if action == 'priority':
            new_prio = request.form.get('priority', '')
            if new_prio not in VALID_PRIORITIES:
                flash('Invalid priority.', 'error')
            elif new_prio != c.priority:
                old_prio = c.priority
                c.priority = new_prio
                c.updated_at = datetime.utcnow()
                add_history(c, current_user.id,
                            old_priority=old_prio, new_priority=new_prio,
                            note=f'Priority changed from {old_prio} to {new_prio}.')
                notify_user(c.created_by, c.id,
                            f'Your complaint {c.complaint_id} priority changed to {new_prio}.')
                db.session.commit()
                flash('Priority updated.', 'success')

        # --- Change Status ---
        elif action == 'status':
            new_status = request.form.get('status', '')
            if new_status not in VALID_STATUSES:
                flash('Invalid status.', 'error')
            elif not transition_allowed(c.status, new_status, 'admin'):
                flash(f'Cannot move from {c.status} to {new_status}.', 'error')
            else:
                old_status = c.status
                c.status = new_status
                c.updated_at = datetime.utcnow()
                if new_status in ('Resolved',):
                    c.resolved_at = datetime.utcnow()
                if new_status == 'Closed':
                    c.closed_at = datetime.utcnow()
                note = request.form.get('status_note', '').strip() or f'Status changed to {new_status}.'
                add_history(c, current_user.id,
                            old_status=old_status, new_status=new_status, note=note)
                notify_user(c.created_by, c.id,
                            f'Your complaint {c.complaint_id} status is now: {new_status}.')
                if c.assigned_to:
                    notify_user(c.assigned_to, c.id,
                                f'Complaint {c.complaint_id} status changed to {new_status}.')
                db.session.commit()
                flash('Status updated.', 'success')

        # --- Assign Staff ---
        elif action == 'assign':
            staff_id = request.form.get('staff_id', '')
            if not staff_id:
                # Unassign
                c.assigned_to = None
                c.updated_at = datetime.utcnow()
                add_history(c, current_user.id, note='Complaint unassigned.')
                db.session.commit()
                flash('Assignment cleared.', 'success')
            else:
                staff = User.query.get(int(staff_id))
                if not staff or staff.role != 'staff':
                    flash('Invalid staff member.', 'error')
                else:
                    old_assignee = c.assigned_to
                    c.assigned_to = staff.id
                    c.updated_at = datetime.utcnow()
                    if c.status in ('Submitted', 'Acknowledged', 'Reopened'):
                        c.status = 'Assigned'
                    note = f'Assigned to {staff.full_name}.'
                    add_history(c, current_user.id,
                                old_status=c.status if old_assignee else None,
                                new_status='Assigned' if c.status == 'Assigned' else None,
                                note=note)
                    notify_user(staff.id, c.id,
                                f'You have been assigned complaint {c.complaint_id}: {c.title}.')
                    notify_user(c.created_by, c.id,
                                f'Your complaint {c.complaint_id} has been assigned to {staff.full_name}.')
                    db.session.commit()
                    flash(f'Complaint assigned to {staff.full_name}.', 'success')

        # --- Add Internal Note ---
        elif action == 'note':
            msg = request.form.get('note_message', '').strip()
            if not msg:
                flash('Note cannot be empty.', 'error')
            else:
                comment = Comment(complaint_id=c.id, user_id=current_user.id,
                                  message=msg, visibility='internal')
                db.session.add(comment)
                add_history(c, current_user.id, note=f'[Internal note added]')
                db.session.commit()
                flash('Internal note added.', 'success')

        # --- Add Public Update ---
        elif action == 'update':
            msg = request.form.get('update_message', '').strip()
            if not msg:
                flash('Update cannot be empty.', 'error')
            else:
                comment = Comment(complaint_id=c.id, user_id=current_user.id,
                                  message=msg, visibility='public')
                db.session.add(comment)
                notify_user(c.created_by, c.id,
                            f'Admin added an update to {c.complaint_id}.')
                db.session.commit()
                flash('Public update added.', 'success')

        return redirect(url_for('admin.manage_complaint', complaint_id=complaint_id))

    # GET
    all_comments = (Comment.query.filter_by(complaint_id=c.id)
                    .order_by(Comment.created_at.asc()).all())
    history = c.history.order_by(ComplaintHistory.created_at.asc()).all()

    return render_template('manage_complaint.html',
                           complaint=c, staff_list=staff_list,
                           comments=all_comments, history=history,
                           statuses=VALID_STATUSES, priorities=VALID_PRIORITIES,
                           unread_count=unread_count,
                           transitions=STATUS_TRANSITIONS.get('admin', {}))


@admin_bp.route('/users')
@login_required_role('admin')
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()
    return render_template('manage_users.html', users=users, unread_count=unread_count)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required_role('admin')
def toggle_user(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.manage_users'))
    if u.role == 'admin' and u.is_active:
        active_admins = User.query.filter_by(role='admin', is_active=1).count()
        if active_admins <= 1:
            flash('Cannot deactivate the last active administrator.', 'error')
            return redirect(url_for('admin.manage_users'))
    u.is_active = 0 if u.is_active else 1
    db.session.commit()
    state = 'activated' if u.is_active else 'deactivated'
    flash(f'Account {state}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/staff/new', methods=['GET', 'POST'])
@login_required_role('admin')
def create_staff():
    import re
    EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email or not EMAIL_RE.match(email):
            errors.append('A valid email is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already in use.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('create_staff.html',
                                   unread_count=unread_count,
                                   form_data=request.form)

        staff = User(full_name=full_name, email=email, role='staff')
        staff.set_password(password)
        db.session.add(staff)
        db.session.commit()
        flash(f'Staff account created for {full_name}.', 'success')
        return redirect(url_for('admin.manage_users'))

    return render_template('create_staff.html', unread_count=unread_count, form_data={})


@admin_bp.route('/reports')
@login_required_role('admin')
def reports():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    category_filter = request.args.get('category', '')
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()

    query = Complaint.query
    if date_from:
        try:
            query = query.filter(Complaint.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Complaint.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass
    if category_filter:
        query = query.filter_by(category=category_filter)

    complaints = query.all()

    # Status summary
    status_summary = {}
    for s in VALID_STATUSES:
        status_summary[s] = sum(1 for c in complaints if c.status == s)

    # Category summary
    cat_summary = {}
    for cat in VALID_CATEGORIES:
        cat_summary[cat] = sum(1 for c in complaints if c.category == cat)

    # Priority summary
    prio_summary = {p: sum(1 for c in complaints if c.priority == p) for p in VALID_PRIORITIES}

    # Staff summary
    staff_list = User.query.filter_by(role='staff').all()
    staff_summary = {}
    for s in staff_list:
        staff_summary[s.full_name] = sum(1 for c in complaints if c.assigned_to == s.id)

    # Average resolution time
    resolved_complaints = [c for c in complaints if c.resolved_at and c.created_at]
    if resolved_complaints:
        total_hours = sum(
            (c.resolved_at - c.created_at).total_seconds() / 3600
            for c in resolved_complaints
        )
        avg_resolution_hours = round(total_hours / len(resolved_complaints), 1)
    else:
        avg_resolution_hours = None

    return render_template('reports.html',
                           total=len(complaints),
                           status_summary=status_summary,
                           cat_summary=cat_summary,
                           prio_summary=prio_summary,
                           staff_summary=staff_summary,
                           avg_resolution_hours=avg_resolution_hours,
                           categories=VALID_CATEGORIES,
                           date_from=date_from, date_to=date_to,
                           category_filter=category_filter,
                           unread_count=unread_count)


@admin_bp.route('/reports/export.csv')
@login_required_role('admin')
def export_csv():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')

    query = Complaint.query
    if date_from:
        try:
            query = query.filter(Complaint.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Complaint.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        except ValueError:
            pass
    if category_filter:
        query = query.filter_by(category=category_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    csv_data = generate_csv(complaints)
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=fixflow_report.csv'
    return response
