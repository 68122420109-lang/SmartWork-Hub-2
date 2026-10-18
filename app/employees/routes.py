from __future__ import annotations

from datetime import date
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import EmployeeForm, PositionForm
from app.models import Attendance, Department, Employee, LeaveBalance, LeaveRequest, Position, SystemSetting, User
from app.utils import admin_required, hr_or_admin_required, log_audit
from app.employees import employees_bp


@employees_bp.route('/')
@login_required
def index():
    if not current_user.is_hr_or_admin:
        employee = Employee.query.filter_by(user_id=current_user.id).first()
        if employee:
            return redirect(url_for('employees.detail', emp_id=employee.id))
        flash('บัญชีนี้ยังไม่ได้เชื่อมโยงกับข้อมูลพนักงาน', 'info')
        return redirect(url_for('main.home'))

    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    dept_id = request.args.get('department_id', '', type=str)
    status_filter = request.args.get('status', '').strip()
    position_filter = request.args.get('position', '').strip()

    query = Employee.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            (Employee.employee_code.ilike(search_pattern)) |
            (Employee.first_name.ilike(search_pattern)) |
            (Employee.last_name.ilike(search_pattern)) |
            (Employee.email.ilike(search_pattern)) |
            (Employee.position.ilike(search_pattern))
        )

    if dept_id and dept_id.isdigit():
        query = query.filter(Employee.department_id == int(dept_id))

    if status_filter:
        query = query.filter(Employee.status == status_filter)

    if position_filter:
        query = query.filter(Employee.position == position_filter)

    employees_paginated = query.order_by(Employee.employee_code.asc()).paginate(
        page=page, per_page=10, error_out=False
    )

    departments = Department.query.order_by(Department.name.asc()).all()
    all_positions = [r[0] for r in db.session.query(Employee.position).distinct().order_by(Employee.position).all()]

    # Summary statistics
    total_employees = Employee.query.count()
    active_count = Employee.query.filter_by(status='Active').count()
    probation_count = Employee.query.filter_by(status='Probation').count()
    resigned_count = Employee.query.filter_by(status='Resigned').count()

    dept_stats = []
    for dept in departments:
        count = Employee.query.filter_by(department_id=dept.id).count()
        dept_stats.append({'name': dept.name, 'code': dept.code, 'count': count})

    return render_template(
        'employees/index.html',
        employees=employees_paginated,
        departments=departments,
        positions=all_positions,
        search=search,
        selected_dept=int(dept_id) if dept_id and dept_id.isdigit() else None,
        selected_status=status_filter,
        selected_position=position_filter,
        total_employees=total_employees,
        active_count=active_count,
        probation_count=probation_count,
        resigned_count=resigned_count,
        dept_stats=dept_stats
    )


@employees_bp.route('/new', methods=['GET', 'POST'])
@login_required
@hr_or_admin_required
def create():
    form = EmployeeForm()
    positions = Position.query.order_by(Position.name.asc()).all()

    # Populate department choices
    departments = Department.query.order_by(Department.name.asc()).all()
    form.department_id.choices = [(0, '-- เลือกแผนก --')] + [(d.id, f"{d.name} ({d.code})") for d in departments]

    # Populate user choices (users without employee record or with this employee)
    users = User.query.order_by(User.username.asc()).all()
    unlinked_users = [(0, '-- ไม่เชื่อมโยงบัญชี --')]
    for u in users:
        emp = Employee.query.filter_by(user_id=u.id).first()
        if not emp:
            unlinked_users.append((u.id, f"{u.username} ({u.full_name})"))
    form.user_id.choices = unlinked_users

    if request.method == 'GET':
        form.work_start_time.data = SystemSetting.get_val('default_work_start', '09:00')
        form.work_end_time.data = SystemSetting.get_val('default_work_end', '18:00')

    if form.validate_on_submit():
        dept_val = form.department_id.data if form.department_id.data != 0 else None
        user_val = form.user_id.data if form.user_id.data != 0 else None

        employee = Employee(
            employee_code=form.employee_code.data.strip().upper(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip() if form.phone.data else None,
            department_id=dept_val,
            position=form.position.data.strip(),
            hire_date=form.hire_date.data,
            work_start_time=form.work_start_time.data.strip(),
            work_end_time=form.work_end_time.data.strip(),
            status=form.status.data,
            user_id=user_val
        )
        db.session.add(employee)
        db.session.flush()

        # Initialize standard leave balances for current year
        current_year = date.today().year
        vacation_quota = float(SystemSetting.get_val('annual_vacation_quota', '10'))
        sick_quota = float(SystemSetting.get_val('sick_leave_quota', '30'))
        personal_quota = float(SystemSetting.get_val('personal_leave_quota', '6'))

        balances = [
            LeaveBalance(employee_id=employee.id, year=current_year, leave_type='Vacation', total_days=vacation_quota, used_days=0.0),
            LeaveBalance(employee_id=employee.id, year=current_year, leave_type='Sick', total_days=sick_quota, used_days=0.0),
            LeaveBalance(employee_id=employee.id, year=current_year, leave_type='Personal', total_days=personal_quota, used_days=0.0),
        ]
        db.session.add_all(balances)
        db.session.commit()

        log_audit('CREATE_EMPLOYEE', 'Employee', employee.id, f"สร้างข้อมูลพนักงาน {employee.employee_code} ({employee.full_name})")
        flash(f'เพิ่มข้อมูลพนักงาน {employee.full_name} ({employee.employee_code}) สำเร็จแล้ว', 'success')
        return redirect(url_for('employees.detail', emp_id=employee.id))

    return render_template('employees/form.html', form=form, title='เพิ่มพนักงานใหม่', positions=positions)


@employees_bp.route('/<int:emp_id>')
@login_required
def detail(emp_id: int):
    employee = Employee.query.get_or_404(emp_id)

    # Permission check: Normal employees can only view their own profile unless HR/Admin
    if not current_user.is_hr_or_admin:
        if not employee.user_id or employee.user_id != current_user.id:
            abort(403)

    # Recent attendance (last 30 records)
    recent_attendances = Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.date.desc()).limit(15).all()

    # Leave balances for current year
    current_year = date.today().year
    leave_balances = LeaveBalance.query.filter_by(employee_id=employee.id, year=current_year).all()

    # Leave requests
    leave_requests = LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).limit(10).all()

    # Attendance stats for this month
    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    month_attendances = Attendance.query.filter(
        Attendance.employee_id == employee.id,
        Attendance.date >= first_of_month,
        Attendance.date <= today
    ).all()

    month_present = sum(1 for a in month_attendances if a.status == 'Present')
    month_late = sum(1 for a in month_attendances if a.status == 'Late')
    month_late_minutes = sum(a.late_minutes for a in month_attendances)
    month_hours = sum(a.work_hours for a in month_attendances)

    return render_template(
        'employees/detail.html',
        employee=employee,
        recent_attendances=recent_attendances,
        leave_balances=leave_balances,
        leave_requests=leave_requests,
        month_present=month_present,
        month_late=month_late,
        month_late_minutes=month_late_minutes,
        month_hours=round(month_hours, 1)
    )


@employees_bp.route('/<int:emp_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_or_admin_required
def edit(emp_id: int):
    employee = Employee.query.get_or_404(emp_id)
    form = EmployeeForm(
        original_code=employee.employee_code,
        original_email=employee.email,
        original_position=employee.position,
        obj=employee,
    )

    # Populate departments
    departments = Department.query.order_by(Department.name.asc()).all()
    form.department_id.choices = [(0, '-- เลือกแผนก --')] + [(d.id, f"{d.name} ({d.code})") for d in departments]

    # Populate users (current linked user or unlinked users)
    users = User.query.order_by(User.username.asc()).all()
    user_choices = [(0, '-- ไม่เชื่อมโยงบัญชี --')]
    for u in users:
        emp = Employee.query.filter_by(user_id=u.id).first()
        if not emp or emp.id == employee.id:
            user_choices.append((u.id, f"{u.username} ({u.full_name})"))
    form.user_id.choices = user_choices

    if request.method == 'GET':
        form.department_id.data = employee.department_id or 0
        form.user_id.data = employee.user_id or 0

    if form.validate_on_submit():
        dept_val = form.department_id.data if form.department_id.data != 0 else None
        user_val = form.user_id.data if form.user_id.data != 0 else None

        employee.employee_code = form.employee_code.data.strip().upper()
        employee.first_name = form.first_name.data.strip()
        employee.last_name = form.last_name.data.strip()
        employee.email = form.email.data.strip().lower()
        employee.phone = form.phone.data.strip() if form.phone.data else None
        employee.department_id = dept_val
        employee.position = form.position.data.strip()
        employee.hire_date = form.hire_date.data
        employee.work_start_time = form.work_start_time.data.strip()
        employee.work_end_time = form.work_end_time.data.strip()
        employee.status = form.status.data
        employee.user_id = user_val

        db.session.commit()
        log_audit('UPDATE_EMPLOYEE', 'Employee', employee.id, f"แก้ไขข้อมูลพนักงาน {employee.employee_code} ({employee.full_name})")
        flash(f'บันทึกการแก้ไขข้อมูลพนักงาน {employee.full_name} สำเร็จแล้ว', 'success')
        return redirect(url_for('employees.detail', emp_id=employee.id))

    positions = Position.query.order_by(Position.name.asc()).all()
    return render_template('employees/form.html', form=form, title='แก้ไขข้อมูลพนักงาน', employee=employee, positions=positions)


@employees_bp.route('/<int:emp_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(emp_id: int):
    employee = Employee.query.get_or_404(emp_id)
    emp_code = employee.employee_code
    emp_name = employee.full_name

    db.session.delete(employee)
    db.session.commit()

    log_audit('DELETE_EMPLOYEE', 'Employee', emp_id, f"ลบข้อมูลพนักงาน {emp_code} ({emp_name})")
    flash(f'ลบข้อมูลพนักงาน {emp_name} ({emp_code}) ออกจากระบบเรียบร้อยแล้ว', 'success')
    return redirect(url_for('employees.index'))


@employees_bp.route('/positions', methods=['GET', 'POST'])
@login_required
@hr_or_admin_required
def positions():
    form = PositionForm()
    if form.validate_on_submit():
        position = Position(name=form.name.data.strip(), description=form.description.data.strip() or None)
        db.session.add(position)
        db.session.commit()
        flash('เพิ่มตำแหน่งงานเรียบร้อยแล้ว', 'success')
        return redirect(url_for('employees.positions'))

    return render_template('employees/positions.html', form=form, positions=Position.query.order_by(Position.name.asc()).all())


@employees_bp.route('/positions/<int:position_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_or_admin_required
def edit_position(position_id: int):
    position = Position.query.get_or_404(position_id)
    form = PositionForm(original_name=position.name, obj=position)
    if form.validate_on_submit():
        old_name = position.name
        new_name = form.name.data.strip()
        position.name = new_name
        position.description = form.description.data.strip() or None
        if new_name != old_name:
            Employee.query.filter_by(position=old_name).update(
                {Employee.position: new_name},
                synchronize_session=False,
            )
        db.session.commit()
        flash('แก้ไขตำแหน่งงานเรียบร้อยแล้ว', 'success')
        return redirect(url_for('employees.positions'))
    return render_template('employees/position_form.html', form=form, title='แก้ไขตำแหน่งงาน')


@employees_bp.route('/positions/<int:position_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_position(position_id: int):
    position = Position.query.get_or_404(position_id)
    assigned_count = Employee.query.filter_by(position=position.name).count()
    if assigned_count:
        flash(f'ลบตำแหน่งนี้ไม่ได้ เนื่องจากมีพนักงาน {assigned_count} คนใช้งานอยู่', 'warning')
        return redirect(url_for('employees.positions'))
    db.session.delete(position)
    db.session.commit()
    flash('ลบตำแหน่งงานเรียบร้อยแล้ว', 'success')
    return redirect(url_for('employees.positions'))
