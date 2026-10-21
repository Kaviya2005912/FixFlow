import os
from flask import Flask, render_template, redirect, url_for
from flask_login import current_user
from config import Config, BASE_DIR
from extensions import db, login_manager, csrf
from models import User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance folder and uploads using absolute paths
    os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Enable SQLite foreign key enforcement
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    import sqlite3

    @event.listens_for(Engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.admin import admin_bp
    from routes.staff import staff_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)

    # Root redirect
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            if current_user.role == 'staff':
                return redirect(url_for('staff.dashboard'))
            return redirect(url_for('user.dashboard'))
        return redirect(url_for('auth.login'))

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # Template context processors
    @app.context_processor
    def inject_globals():
        from models import Notification
        unread = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=0).count()
        return dict(unread_notifications=unread)

    return app


app = create_app()


def _seed_data():
    """Create default admin + demo data if the DB is empty."""

    from models import User, Complaint, Comment, ComplaintHistory
    from datetime import datetime, timedelta

    if User.query.count() > 0:
        return  # already seeded

    # Admin
    admin = User(full_name='Administrator', email='admin@fixflow.edu', role='admin')
    admin.set_password('Admin@1234')
    db.session.add(admin)

    # Faculty user
    student = User(full_name='Alex Morgan', email='alex@fixflow.edu', role='user')
    student.set_password('Student@1234')
    db.session.add(student)

    # Maintenance staff
    staff1 = User(full_name='Daniel Joseph', email='daniel@fixflow.edu', role='staff')
    staff1.set_password('Staff@1234')
    db.session.add(staff1)

    staff2 = User(full_name='Meera Nair', email='meera@fixflow.edu', role='staff')
    staff2.set_password('Staff@1234')
    db.session.add(staff2)

    db.session.flush()

    now = datetime.utcnow()

    complaints_data = [
        dict(title='Classroom fan not working', description='The ceiling fan in room 204 is not rotating. Students are uncomfortable.',
             category='Electrical', building='Block B', floor='2', room_number='204',
             priority='Medium', status='Submitted', created_by=student.id),
        dict(title='Water leakage near washroom', description='There is a persistent water leak near the Block A first-floor washroom.',
             category='Plumbing & Water Supply', building='Block A', floor='1', room_number='',
             priority='High', status='Assigned', created_by=student.id, assigned_to=staff2.id),
        dict(title='Broken laboratory chair', description='Chair in Lab 3 is broken and poses a safety risk.',
             category='Furniture', building='Block C', floor='2', room_number='Lab 3',
             priority='Low', status='In Progress', created_by=student.id, assigned_to=staff1.id),
        dict(title='Projector not turning on', description='The projector in the seminar hall refuses to power on.',
             category='Classroom Equipment', building='Main Block', floor='1', room_number='Seminar Hall',
             priority='Medium', status='Resolved', created_by=student.id, assigned_to=staff1.id,
             resolved_at=now - timedelta(days=1)),
        dict(title='Corridor light not working', description='Light in Block B corridor (Floor 3) is out.',
             category='Electrical', building='Block B', floor='3', room_number='Corridor',
             priority='Medium', status='Closed', created_by=student.id,
             resolved_at=now - timedelta(days=5), closed_at=now - timedelta(days=3)),
    ]

    for i, cd in enumerate(complaints_data):
        c = Complaint(
            created_at=now - timedelta(days=len(complaints_data) - i),
            updated_at=now - timedelta(hours=i),
            **cd
        )
        db.session.add(c)
        db.session.flush()

        hist = ComplaintHistory(
            complaint_id=c.id, changed_by=student.id,
            new_status='Submitted', note='Complaint submitted.',
            created_at=c.created_at,
        )
        db.session.add(hist)

        if c.status in ('Assigned', 'In Progress', 'Resolved', 'Closed'):
            db.session.add(ComplaintHistory(
                complaint_id=c.id, changed_by=admin.id,
                old_status='Submitted', new_status='Assigned',
                note='Complaint assigned to staff.',
                created_at=c.created_at + timedelta(hours=2),
            ))

        if c.status in ('In Progress', 'Resolved', 'Closed'):
            db.session.add(ComplaintHistory(
                complaint_id=c.id, changed_by=staff1.id,
                old_status='Assigned', new_status='In Progress',
                note='Started working on the issue.',
                created_at=c.created_at + timedelta(hours=4),
            ))

        if c.status in ('Resolved', 'Closed'):
            db.session.add(ComplaintHistory(
                complaint_id=c.id, changed_by=staff1.id,
                old_status='In Progress', new_status='Resolved',
                note='Issue has been fixed and verified.',
                created_at=c.resolved_at,
            ))
            db.session.add(Comment(
                complaint_id=c.id, user_id=staff1.id,
                message='[Resolution] Issue resolved successfully.',
                visibility='public', created_at=c.resolved_at,
            ))

    db.session.commit()
    print('✅ Demo data seeded successfully.')
    print('   Admin:   admin@fixflow.edu / Admin@1234')
    print('   User:    alex@fixflow.edu  / Student@1234')
    print('   Staff:   daniel@fixflow.edu / Staff@1234')
    print('   Staff:   meera@fixflow.edu  / Staff@1234')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        _seed_data()
    app.run(debug=True, host='0.0.0.0', port=5000)
