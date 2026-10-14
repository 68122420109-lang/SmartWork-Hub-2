from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app.extensions import db
from app.forms import LoginForm, RegisterForm
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            full_name=form.full_name.data.strip(),
            role='user',
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        user = User.query.filter((User.username == identifier) | (User.email == identifier.lower())).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            flash(f'ยินดีต้อนรับ {user.full_name}', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.home'))
        flash('ชื่อผู้ใช้/อีเมลหรือรหัสผ่านไม่ถูกต้อง', 'danger')
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('ออกจากระบบเรียบร้อยแล้ว', 'info')
    return redirect(url_for('main.home'))
