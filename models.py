from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False, default='user')  # user | admin | staff
    is_active = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    submitted_complaints = db.relationship(
        'Complaint', foreign_keys='Complaint.created_by',
        backref='submitter', lazy='dynamic'
    )
    assigned_complaints = db.relationship(
        'Complaint', foreign_keys='Complaint.assigned_to',
        backref='assignee', lazy='dynamic'
    )
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic')
    history_entries = db.relationship('ComplaintHistory', backref='actor', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def active(self):
        return bool(self.is_active)

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'


VALID_STATUSES = [
    'Submitted', 'Acknowledged', 'Assigned',
    'In Progress', 'Resolved', 'Closed', 'Reopened'
]

VALID_PRIORITIES = ['Low', 'Medium', 'High']

VALID_CATEGORIES = [
    'Electrical',
    'Plumbing & Water Supply',
    'Classroom Equipment',
    'Furniture',
    'Laboratory Equipment',
    'Cleaning & Sanitation',
    'Internet & Networking',
    'Civil Maintenance',
    'Other Facilities',
]

# Allowed status transitions per role
STATUS_TRANSITIONS = {
    'admin': {
        'Submitted':   ['Acknowledged', 'Assigned', 'Closed'],
        'Acknowledged': ['Assigned', 'Closed'],
        'Assigned':    ['Acknowledged', 'In Progress', 'Closed'],
        'In Progress': ['Resolved', 'Assigned', 'Closed'],
        'Resolved':    ['Closed', 'Reopened'],
        'Closed':      ['Reopened'],
        'Reopened':    ['Acknowledged', 'Assigned'],
    },
    'staff': {
        'Assigned':    ['In Progress'],
        'In Progress': ['Resolved'],
    },
    'user': {
        'Resolved': ['Reopened'],
        'Closed':   ['Reopened'],
    },
}


class Complaint(db.Model):
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False)
    building = db.Column(db.Text, nullable=False)
    floor = db.Column(db.Text, nullable=True)
    room_number = db.Column(db.Text, nullable=True)
    priority = db.Column(db.Text, nullable=False, default='Medium')
    status = db.Column(db.Text, nullable=False, default='Submitted')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    image_path = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    history = db.relationship('ComplaintHistory', backref='complaint',
                              lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='complaint',
                               lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='complaint',
                                    lazy='dynamic', cascade='all, delete-orphan')

    @property
    def complaint_id(self):
        return f'FF-{self.created_at.year}-{self.id:04d}'

    def __repr__(self):
        return f'<Complaint {self.id}: {self.title}>'


class ComplaintHistory(db.Model):
    __tablename__ = 'complaint_history'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    old_status = db.Column(db.Text, nullable=True)
    new_status = db.Column(db.Text, nullable=True)
    old_priority = db.Column(db.Text, nullable=True)
    new_priority = db.Column(db.Text, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<History complaint={self.complaint_id} {self.old_status}->{self.new_status}>'


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    visibility = db.Column(db.Text, nullable=False, default='public')  # public | internal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Comment {self.id} on complaint {self.complaint_id}>'


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id} for user {self.user_id}>'
