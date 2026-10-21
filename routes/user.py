import os
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort)
from flask_login import current_user, login_required
from extensions import db
from models import Complaint, Comment, Notification, VALID_CATEGORIES, VALID_PRIORITIES
from services.complaint_service import add_history, allowed_file, safe_filename
from services.complaint_service import notify_user
from routes.auth_utils import login_required_role

user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/dashboard')
@login_required_role('user')
def dashboard():
    uid = current_user.id
    total = Complaint.query.filter_by(created_by=uid).count()
    pending = Complaint.query.filter_by(created_by=uid).filter(
        Complaint.status.in_(['Submitted', 'Acknowledged', 'Assigned', 'Reopened'])
    ).count()
    in_progress = Complaint.query.filter_by(created_by=uid, status='In Progress').count()
    resolved = Complaint.query.filter_by(created_by=uid).filter(
        Complaint.status.in_(['Resolved', 'Closed'])
    ).count()
    recent = (Complaint.query.filter_by(created_by=uid)
              .order_by(Complaint.created_at.desc()).limit(5).all())
    unread_count = Notification.query.filter_by(user_id=uid, is_read=0).count()
    return render_template('user_dashboard.html',
                           total=total, pending=pending,
                           in_progress=in_progress, resolved=resolved,
                           recent=recent, unread_count=unread_count)


@user_bp.route('/complaints/new', methods=['GET', 'POST'])
@login_required_role('user')
def new_complaint():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        building = request.form.get('building', '').strip()
        floor_ = request.form.get('floor', '').strip()
        room = request.form.get('room_number', '').strip()

        errors = []
        if not title:
            errors.append('Complaint title is required.')
        if not description:
            errors.append('Description is required.')
        if category not in VALID_CATEGORIES:
            errors.append('Please select a valid category.')
        if not building:
            errors.append('Building / Block is required.')

        image_path = None
        file = request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
                errors.append('Invalid image type. Allowed: png, jpg, jpeg, gif, webp.')
            else:
                fname = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_filename(file.filename)}"
                upload_dir = os.path.join(current_app.root_path,
                                          current_app.config['UPLOAD_FOLDER'])
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, fname))
                image_path = fname

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('submit_complaint.html',
                                   categories=VALID_CATEGORIES,
                                   form_data=request.form)

        complaint = Complaint(
            title=title, description=description,
            category=category, building=building,
            floor=floor_, room_number=room,
            priority='Medium', status='Submitted',
            created_by=current_user.id,
            image_path=image_path,
        )
        db.session.add(complaint)
        db.session.flush()  # get complaint.id

        add_history(complaint, current_user.id,
                    new_status='Submitted',
                    note='Complaint submitted.')
        db.session.commit()
        flash(f'Complaint {complaint.complaint_id} submitted successfully!', 'success')
        return redirect(url_for('user.my_complaints'))

    return render_template('submit_complaint.html', categories=VALID_CATEGORIES, form_data={})


@user_bp.route('/complaints')
@login_required_role('user')
def my_complaints():
    uid = current_user.id
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Complaint.query.filter_by(created_by=uid)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if q:
        query = query.filter(
            Complaint.title.ilike(f'%{q}%') | Complaint.description.ilike(f'%{q}%')
        )
    complaints = query.order_by(Complaint.created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )

    total = Complaint.query.filter_by(created_by=uid).count()
    pending = Complaint.query.filter_by(created_by=uid).filter(
        Complaint.status.in_(['Submitted', 'Acknowledged', 'Assigned', 'Reopened'])
    ).count()
    in_progress = Complaint.query.filter_by(created_by=uid, status='In Progress').count()
    resolved = Complaint.query.filter_by(created_by=uid).filter(
        Complaint.status.in_(['Resolved', 'Closed'])
    ).count()
    unread_count = Notification.query.filter_by(user_id=uid, is_read=0).count()

    return render_template('my_complaints.html',
                           complaints=complaints,
                           categories=VALID_CATEGORIES,
                           total=total, pending=pending,
                           in_progress=in_progress, resolved=resolved,
                           unread_count=unread_count,
                           status_filter=status_filter,
                           category_filter=category_filter, q=q)


@user_bp.route('/complaints/<int:complaint_id>')
@login_required_role('user')
def complaint_detail(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    if c.created_by != current_user.id:
        abort(403)
    public_comments = (Comment.query
                       .filter_by(complaint_id=c.id, visibility='public')
                       .order_by(Comment.created_at.asc()).all())
    history = (c.history.order_by('created_at').all())
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=0).count()
    return render_template('complaint_detail.html',
                           complaint=c,
                           comments=public_comments,
                           history=history,
                           unread_count=unread_count)


@user_bp.route('/complaints/<int:complaint_id>/comment', methods=['POST'])
@login_required_role('user')
def add_comment(complaint_id):
    c = Complaint.query.get_or_404(complaint_id)
    if c.created_by != current_user.id:
        abort(403)
    message = request.form.get('message', '').strip()
    if not message:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('user.complaint_detail', complaint_id=complaint_id))
    comment = Comment(complaint_id=c.id, user_id=current_user.id,
                      message=message, visibility='public')
    db.session.add(comment)
    db.session.commit()
    flash('Comment added.', 'success')
    return redirect(url_for('user.complaint_detail', complaint_id=complaint_id))


@user_bp.route('/notifications')
@login_required_role('user')
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc())
              .limit(50).all())
    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=0).update({'is_read': 1})
    db.session.commit()
    return render_template('notifications.html', notifications=notifs, unread_count=0)
