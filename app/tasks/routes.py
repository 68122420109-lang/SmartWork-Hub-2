from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import TaskForm
from app.models import Task

tasks_bp = Blueprint('tasks', __name__)


def task_access_required(task_id: int):
    task = Task.query.get_or_404(task_id)
    if not current_user.is_hr_or_admin and task.user_id != current_user.id:
        abort(403)
    return task


@tasks_bp.route('/tasks/new', methods=['GET', 'POST'])
@login_required
def new_task():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            category=form.category.data.strip(),
            assignee=form.assignee.data.strip(),
            status=form.status.data,
            start_date=form.start_date.data or None,
            due_date=form.due_date.data or None,
            user_id=current_user.id,
        )
        db.session.add(task)
        db.session.commit()
        flash('บันทึกงานใหม่สำเร็จ', 'success')
        return redirect(url_for('main.task_detail', task_id=task.id))
    return render_template('tasks/task_form.html', form=form, title='เพิ่มงานใหม่')


@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id: int):
    task = task_access_required(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.description = form.description.data.strip()
        task.category = form.category.data.strip()
        task.assignee = form.assignee.data.strip()
        task.status = form.status.data
        task.start_date = form.start_date.data or None
        task.due_date = form.due_date.data or None
        db.session.commit()
        flash('แก้ไขงานสำเร็จ', 'success')
        return redirect(url_for('main.task_detail', task_id=task.id))
    return render_template('tasks/task_form.html', form=form, title='แก้ไขงาน', task=task)


@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id: int):
    task = task_access_required(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('ลบงานสำเร็จ', 'success')
    return redirect(url_for('main.task_list'))
