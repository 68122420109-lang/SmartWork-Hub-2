from datetime import timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Attendance, AuditLog, Employee, LeaveRequest, Task
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
def task_list():
    page = request.args.get('page', 1, type=int)
    query_value = request.args.get('q', '').strip()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Task.query
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
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('tasks/task_detail.html', task=task)


@main_bp.route('/profile')
@login_required
def profile():
    user_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    return render_template('profile.html', user_tasks=user_tasks)


@main_bp.route('/my-tasks')
@login_required
def my_tasks():
    page = request.args.get('page', 1, type=int)
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).paginate(page=page, per_page=8, error_out=False)
    return render_template('tasks/my_tasks.html', tasks=tasks)
