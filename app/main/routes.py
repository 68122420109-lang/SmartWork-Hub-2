import time
from datetime import timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image

from app.extensions import db
from app.forms import ProfileForm
from app.models import Attendance, AuditLog, Employee, FaceEnrollment, LeaveRequest, Task
from app.utils import get_bangkok_today

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    if not current_user.is_authenticated:
        return render_template('home.html', dashboard=False)

    today = get_bangkok_today()
    total_employees = Employee.query.count()
    attendance_today = Attendance.query.filter_by(date=today).count()
    late_today = Attendance.query.filter_by(date=today, status='Late').count()
    pending_leaves = LeaveRequest.query.filter_by(status='Pending').count()
    week_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    week_records = db.session.query(
        Attendance.date,
        Attendance.status,
        db.func.count(),
    ).filter(
        Attendance.date >= week_days[0],
        Attendance.date <= week_days[-1],
        Attendance.status.in_(['Present', 'Late']),
    ).group_by(Attendance.date, Attendance.status).all()
    week_counts = {(record_date, status): count for record_date, status, count in week_records}
    attendance_chart = [
        {
            'label': day.strftime('%d/%m'),
            'present': week_counts.get((day, 'Present'), 0),
            'late': week_counts.get((day, 'Late'), 0),
        }
        for day in week_days
    ]
    recent_activities = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(6).all()
        if current_user.is_hr_or_admin else []
    )

    return render_template(
        'home.html',
        dashboard=True,
        total_employees=total_employees,
        attendance_today=attendance_today,
        late_today=late_today,
        pending_leaves=pending_leaves,
        attendance_chart=attendance_chart,
        recent_activities=recent_activities,
        today=today,
    )


@main_bp.route('/tasks')
@login_required
def task_list():
    page = request.args.get('page', 1, type=int)
    query_value = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Task.query
    # Non-HR/Admin employees can only see their own tasks
    if not current_user.is_hr_or_admin:
        query = query.filter(Task.user_id == current_user.id)

    if query_value:
        query = query.filter(
            (Task.title.ilike(f'%{query_value}%')) |
            (Task.description.ilike(f'%{query_value}%')) |
            (Task.assignee.ilike(f'%{query_value}%'))
        )
    if category_filter:
        query = query.filter(Task.category == category_filter)
    if status_filter:
        query = query.filter(Task.status == status_filter)

    tasks = query.order_by(Task.created_at.desc()).paginate(page=page, per_page=8, error_out=False)
    categories = [row[0] for row in db.session.query(Task.category).distinct().order_by(Task.category).all()]
    statuses = ['Pending', 'In Progress', 'Completed']

    return render_template(
        'tasks/task_list.html',
        tasks=tasks,
        categories=categories,
        statuses=statuses,
        query_value=query_value,
        category_filter=category_filter,
        status_filter=status_filter,
    )


@main_bp.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    # Permission check: normal employees can only view their own tasks
    if not current_user.is_hr_or_admin and task.user_id != current_user.id:
        abort(403)
    return render_template('tasks/task_detail.html', task=task)


@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    employee = current_user.employee
    form = ProfileForm(obj=current_user)

    if request.method == 'GET' and employee and employee.phone:
        form.phone.data = employee.phone

    # Handle remove avatar request
    if request.method == 'POST' and request.form.get('action') == 'remove_avatar':
        if employee and employee.avatar_url:
            try:
                old_file = Path(current_app.config['BASE_DIR']) / 'app' / 'static' / employee.avatar_url
                if old_file.exists():
                    old_file.unlink()
            except Exception:
                pass
            employee.avatar_url = None
            db.session.commit()
            flash('ลบรูปภาพโปรไฟล์เรียบร้อยแล้ว', 'info')
        return redirect(url_for('main.profile'))

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        if employee:
            parts = form.full_name.data.strip().split(' ', 1)
            employee.first_name = parts[0]
            employee.last_name = parts[1] if len(parts) > 1 else ''
            if form.phone.data:
                employee.phone = form.phone.data.strip()

        # Handle avatar file upload
        avatar_file = form.avatar.data
        if avatar_file:
            try:
                pil_img = Image.open(avatar_file.stream)
                pil_img.verify()
                avatar_file.stream.seek(0)
                pil_img = Image.open(avatar_file.stream).convert('RGB')

                # Crop square from center
                w, h = pil_img.size
                min_dim = min(w, h)
                left = (w - min_dim) // 2
                top = (h - min_dim) // 2
                cropped = pil_img.crop((left, top, left + min_dim, top + min_dim))
                resized = cropped.resize((256, 256), Image.Resampling.LANCZOS)

                avatar_filename = f"avatar_u{current_user.id}_{int(time.time())}.jpg"
                avatar_folder = Path(current_app.config['BASE_DIR']) / 'app' / 'static' / 'uploads' / 'avatars'
                avatar_folder.mkdir(parents=True, exist_ok=True)
                resized.save(avatar_folder / avatar_filename, 'JPEG', quality=90)

                if employee:
                    employee.avatar_url = f"uploads/avatars/{avatar_filename}"
                flash('อัปเดตรูปโปรไฟล์สำเร็จแล้ว', 'success')
            except Exception as e:
                flash(f'เกิดข้อผิดพลาดในการประมวลผลรูปภาพ: {str(e)}', 'danger')

        db.session.commit()
        flash('บันทึกข้อมูลส่วนตัวสำเร็จ', 'success')
        return redirect(url_for('main.profile'))

    face_enrollment = FaceEnrollment.query.filter_by(user_id=current_user.id, is_active=True).first()
    user_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template(
        'profile.html',
        user_tasks=user_tasks,
        employee=employee,
        form=form,
        face_enrollment=face_enrollment
    )


@main_bp.route('/my-tasks')
@login_required
def my_tasks():
    page = request.args.get('page', 1, type=int)
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).paginate(page=page, per_page=8, error_out=False)
    return render_template('tasks/my_tasks.html', tasks=tasks)

