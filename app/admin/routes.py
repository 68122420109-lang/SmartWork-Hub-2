from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import SystemSettingsForm
from app.models import Attendance, Employee, LeaveRequest, SystemSetting, Task, User
from app.utils import hr_or_admin_required

admin_bp = Blueprint('admin', __name__)


def admin_required(func):
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role != 'admin':
            abort(403)
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_tasks = Task.query.count()
    tasks_in_progress = Task.query.filter(Task.status == 'In Progress').count()
    tasks_completed = Task.query.filter(Task.status == 'Completed').count()
    tasks_pending = Task.query.filter(Task.status == 'Pending').count()
    recent_tasks = Task.query.order_by(Task.updated_at.desc()).limit(8).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_tasks=total_tasks,
        tasks_in_progress=tasks_in_progress,
        tasks_completed=tasks_completed,
        tasks_pending=tasks_pending,
        recent_tasks=recent_tasks,
        recent_users=recent_users,
    )


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@hr_or_admin_required
def settings():
    form = SystemSettingsForm()
    setting_fields = (
        'company_name', 'grace_period_minutes', 'default_work_start',
        'default_work_end', 'annual_vacation_quota', 'sick_leave_quota',
        'personal_leave_quota',
    )
    if form.validate_on_submit():
        previous_start = SystemSetting.get_val('default_work_start', '09:00')
        previous_end = SystemSetting.get_val('default_work_end', '18:00')
        for key in setting_fields:
            value = str(getattr(form, key).data)
            record = SystemSetting.query.filter_by(key=key).first()
            if record:
                record.value = value
            else:
                db.session.add(SystemSetting(key=key, value=value, description=key))
        if form.default_work_start.data != previous_start:
            Employee.query.filter_by(work_start_time=previous_start).update(
                {Employee.work_start_time: form.default_work_start.data},
                synchronize_session=False,
            )
        if form.default_work_end.data != previous_end:
            Employee.query.filter_by(work_end_time=previous_end).update(
                {Employee.work_end_time: form.default_work_end.data},
                synchronize_session=False,
            )
        db.session.commit()
        flash('บันทึกการตั้งค่าระบบแล้ว', 'success')
        return redirect(url_for('admin.settings'))
    if request.method == 'GET':
        for key in setting_fields:
            field = getattr(form, key)
            stored = SystemSetting.get_val(key, '')
            if stored:
                field.data = int(stored) if key in {
                    'grace_period_minutes', 'annual_vacation_quota',
                    'sick_leave_quota', 'personal_leave_quota',
                } else stored
    return render_template('admin/settings.html', form=form)


@admin_bp.route('/reports')
@login_required
@hr_or_admin_required
def reports():
    return render_template(
        'admin/reports.html',
        employee_count=Employee.query.count(),
        attendance_count=Attendance.query.count(),
        late_count=Attendance.query.filter_by(status='Late').count(),
        leave_count=LeaveRequest.query.count(),
    )


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
    return render_template('admin/user_detail.html', user=user, tasks=tasks)


@admin_bp.route('/tasks')
@login_required
@admin_required
def tasks():
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return render_template('admin/tasks.html', tasks=tasks)


@admin_bp.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
@admin_required
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'In Progress', 'Completed']:
        task.status = new_status
        db.session.commit()
        flash('เปลี่ยนสถานะงานสำเร็จ', 'success')
    else:
        flash('สถานะไม่ถูกต้อง', 'danger')
    return redirect(url_for('admin.tasks'))


@admin_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('ลบงานสำเร็จ', 'success')
    return redirect(url_for('admin.tasks'))


@admin_bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
@login_required
@admin_required
def toggle_user_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('ไม่สามารถเปลี่ยนสิทธิ์บัญชีของตัวเองได้', 'warning')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    user.role = 'user' if user.role in {'admin', 'hr', 'manager'} else 'admin'
    db.session.commit()
    flash('อัปเดตสิทธิ์ผู้ใช้งานสำเร็จ', 'success')
    return redirect(url_for('admin.user_detail', user_id=user.id))
