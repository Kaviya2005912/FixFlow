import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email or not EMAIL_RE.match(email):
            errors.append('A valid email address is required.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('register.html', full_name=full_name, email=email)

        user = User(full_name=full_name, email=email, role='user')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully. Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.active:
                flash('Your account has been deactivated. Contact an administrator.', 'error')
                return render_template('login.html')
            login_user(user, remember=bool(request.form.get('remember')))
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return _redirect_by_role(user.role)
        else:
            flash('Invalid email or password. Please try again.', 'error')

    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))


def _redirect_by_role(role):
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    if role == 'staff':
        return redirect(url_for('staff.dashboard'))
    return redirect(url_for('user.dashboard'))
