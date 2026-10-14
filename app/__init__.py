from __future__ import annotations

import click
from flask import Flask, redirect, render_template, url_for
from flask.cli import with_appcontext
from flask_login import LoginManager

from app.extensions import csrf, db, login_manager, migrate
from app.models import Task, User
from app.utils import get_bangkok_now, get_bangkok_today, thai_date_format, thai_time_format
from app.config import Config


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    # Ensure upload folder exists
    app.config['UPLOAD_FOLDER'] = app.config['UPLOAD_FOLDER']
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit
    Config.init_upload_folder(app)
    if test_config:
        app.config.update(test_config)

    app.add_template_filter(thai_date_format, 'thai_date')
    app.add_template_filter(lambda value: thai_date_format(value, include_time=True), 'thai_datetime')
    app.add_template_filter(thai_time_format, 'thai_time')

    @app.context_processor
    def thai_local_time():
        now = get_bangkok_now()
        return {
            'bangkok_now': now,
            'thai_today': thai_date_format(get_bangkok_today()),
            'thai_clock': thai_time_format(now),
        }

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'กรุณาเข้าสู่ระบบก่อนใช้งาน'
    login_manager.login_message_category = 'warning'

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for('auth.login'))

    from app.admin.routes import admin_bp
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.tasks.routes import tasks_bp
    from app.employees import employees_bp
    from app.attendance import attendance_bp
    from app.leave import leave_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(employees_bp, url_prefix='/employees')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(leave_bp)

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template('errors/500.html'), 500

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='ชื่อผู้ใช้แอดมิน')
    @click.option('--email', prompt=True, help='อีเมลแอดมิน')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='รหัสผ่านแอดมิน')
    @click.option('--full-name', prompt=True, help='ชื่อเต็มแอดมิน')
    @with_appcontext
    def create_admin(username: str, email: str, password: str, full_name: str):
        if User.query.filter((User.username == username) | (User.email == email)).first():
            raise click.ClickException('ชื่อผู้ใช้หรืออีเมลถูกใช้งานแล้ว')

        admin = User(username=username, email=email, full_name=full_name, role='admin')
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f'สร้างบัญชีแอดมิน {username} เรียบร้อยแล้ว')

    return app
