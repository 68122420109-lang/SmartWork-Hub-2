from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import AttendanceAdjustmentForm
from app.models import Attendance, Department, Employee, SystemSetting
from app.utils import (
    BANGKOK_TZ,
    admin_required,
    calculate_late_minutes,
    get_bangkok_now,
    get_bangkok_today,
    get_current_employee,
    hr_or_admin_required,
    log_audit,
    thai_date_format,
    thai_time_format,
)
from app.attendance import attendance_bp


@attendance_bp.route('/check-in-out')
@login_required
def check_in_out():
    employee = get_current_employee()
    today = get_bangkok_today()

    today_attendance = None
    if employee:
        today_attendance = Attendance.query.filter_by(employee_id=employee.id, date=today).first()

    # Get grace period and work schedule
    grace_minutes = int(SystemSetting.get_val('grace_period_minutes', '15'))
    work_start = employee.work_start_time if employee else SystemSetting.get_val('default_work_start', '09:00')
    work_end = employee.work_end_time if employee else SystemSetting.get_val('default_work_end', '18:00')

    # Quick recent records for this employee (last 5)
    recent_records = []
    if employee:
        recent_records = Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.date.desc()).limit(5).all()

    return render_template(
        'attendance/check_in_out.html',
        employee=employee,
        today=today,
        today_attendance=today_attendance,
        grace_minutes=grace_minutes,
        work_start=work_start,
        work_end=work_end,
        recent_records=recent_records
    )


@attendance_bp.route('/check-in', methods=['POST'])
@login_required
def check_in():
    employee = get_current_employee()
    if not employee:
        flash('ไม่พบบัญชีพนักงานที่เชื่อมโยงกับผู้ใช้นี้ กรุณาติดต่อผู้ดูแลระบบ', 'danger')
        return redirect(url_for('attendance.check_in_out'))

    if employee.status == 'Resigned':
        flash('สถานะพนักงานของคุณคือลาออกแล้ว ไม่สามารถลงเวลาทำงานได้', 'danger')
        return redirect(url_for('attendance.check_in_out'))

    today = get_bangkok_today()
    existing = Attendance.query.filter_by(employee_id=employee.id, date=today).first()
    if existing and existing.check_in:
        flash('คุณได้ลงเวลาเข้างานของวันนี้ไปเรียบร้อยแล้ว', 'warning')
        return redirect(url_for('attendance.check_in_out'))

    server_now = get_bangkok_now()
    grace_minutes = int(SystemSetting.get_val('grace_period_minutes', '15'))
    work_start = employee.work_start_time or SystemSetting.get_val('default_work_start', '09:00')
    late_mins = calculate_late_minutes(server_now, work_start, grace_minutes)

    status = 'Late' if late_mins > 0 else 'Present'

    if not existing:
        attendance = Attendance(
            employee_id=employee.id,
            date=today,
            check_in=datetime.now(timezone.utc).replace(tzinfo=None),
            status=status,
            work_status='Working',
            late_minutes=late_mins
        )
        db.session.add(attendance)
    else:
        existing.check_in = datetime.now(timezone.utc).replace(tzinfo=None)
        existing.status = status
        existing.work_status = 'Working'
        existing.late_minutes = late_mins

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('ระบบมีรายการลงเวลาของวันนี้แล้ว กรุณาตรวจสอบประวัติอีกครั้ง', 'warning')
        return redirect(url_for('attendance.check_in_out'))
    log_audit('CHECK_IN', 'Attendance', employee.id, f"พนักงาน {employee.employee_code} ลงเวลาเข้างาน สถานะ: {status} (สาย {late_mins} นาที)")

    if late_mins > 0:
        flash(f'บันทึกเวลาเข้างานเรียบร้อย ({server_now.strftime("%H:%M:%S")}) — คุณมาสาย {late_mins} นาที', 'warning')
    else:
        flash(f'บันทึกเวลาเข้างานเรียบร้อย ({server_now.strftime("%H:%M:%S")}) — ตรงเวลา', 'success')

    return redirect(url_for('attendance.check_in_out'))


@attendance_bp.route('/check-out', methods=['POST'])
@login_required
def check_out():
    employee = get_current_employee()
    if not employee:
        flash('ไม่พบบัญชีพนักงานที่เชื่อมโยงกับผู้ใช้นี้', 'danger')
        return redirect(url_for('attendance.check_in_out'))

    today = get_bangkok_today()
    existing = Attendance.query.filter_by(employee_id=employee.id, date=today).first()

    if not existing or not existing.check_in:
        flash('ไม่พบประวัติการเข้างานของวันนี้ กรุณาลงเวลาเข้างานก่อนลงเวลาออกงาน', 'danger')
        return redirect(url_for('attendance.check_in_out'))

    if existing.check_out:
        flash('คุณได้ลงเวลาออกงานของวันนี้ไปเรียบร้อยแล้ว', 'warning')
        return redirect(url_for('attendance.check_in_out'))

    server_now = get_bangkok_now()
    existing.check_out = datetime.now(timezone.utc).replace(tzinfo=None)
    existing.calculate_work_hours()
    existing.work_status = 'Completed'

    db.session.commit()
    log_audit('CHECK_OUT', 'Attendance', existing.id, f"พนักงาน {employee.employee_code} ลงเวลาออกงาน รวมทำงาน {existing.work_hours} ชม.")

    flash(f'บันทึกเวลาออกงานเรียบร้อย ({server_now.strftime("%H:%M:%S")}) — ชั่วโมงการทำงานรวม {existing.work_hours} ชั่วโมง', 'success')
    return redirect(url_for('attendance.check_in_out'))


@attendance_bp.route('/my-history')
@login_required
def my_history():
    employee = get_current_employee()
    if not employee:
        flash('คุณยังไม่มีข้อมูลพนักงานเชื่อมโยงกับบัญชีนี้', 'info')
        return redirect(url_for('main.home'))

    page = request.args.get('page', 1, type=int)
    month = request.args.get('month', '', type=str)
    year = request.args.get('year', '', type=str)

    query = Attendance.query.filter_by(employee_id=employee.id)

    if month:
        if not month.isdigit() or not 1 <= int(month) <= 12:
            flash('กรุณาเลือกเดือนให้ถูกต้อง', 'warning')
            return redirect(url_for('attendance.my_history'))
        query = query.filter(db.extract('month', Attendance.date) == int(month))
    if year:
        if not year.isdigit():
            flash('กรุณาระบุปี พ.ศ. เป็นตัวเลข', 'warning')
            return redirect(url_for('attendance.my_history'))
        year_value = int(year)
        if year_value > 2400:
            year_value -= 543
        query = query.filter(db.extract('year', Attendance.date) == year_value)

    attendances = query.order_by(Attendance.date.desc()).paginate(page=page, per_page=15, error_out=False)

    # Statistics for employee
    total_days = query.count()
    present_days = query.filter_by(status='Present').count()
    late_days = query.filter_by(status='Late').count()
    total_late_minutes = sum(a.late_minutes for a in query.all())
    total_hours = sum(a.work_hours for a in query.all())

    return render_template(
        'attendance/my_history.html',
        employee=employee,
        attendances=attendances,
        month=month,
        year=year,
        total_days=total_days,
        present_days=present_days,
        late_days=late_days,
        total_late_minutes=total_late_minutes,
        total_hours=round(total_hours, 1)
    )


@attendance_bp.route('/records')
@login_required
@hr_or_admin_required
def records():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    dept_id = request.args.get('department_id', '', type=str)
    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = Attendance.query.join(Employee, Attendance.employee_id == Employee.id)

    if search:
        pattern = f'%{search}%'
        query = query.filter(
            (Employee.employee_code.ilike(pattern)) |
            (Employee.first_name.ilike(pattern)) |
            (Employee.last_name.ilike(pattern))
        )

    if dept_id and dept_id.isdigit():
        query = query.filter(Employee.department_id == int(dept_id))

    if status_filter:
        query = query.filter(Attendance.status == status_filter)

    try:
        d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
        d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None
    except ValueError:
        flash('รูปแบบวันที่รายงานไม่ถูกต้อง', 'danger')
        return redirect(url_for('attendance.records'))
    if d_from and d_to and d_from > d_to:
        flash('วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด', 'danger')
        return redirect(url_for('attendance.records'))
    if d_from:
        query = query.filter(Attendance.date >= d_from)
    if d_to:
        query = query.filter(Attendance.date <= d_to)

    records_paginated = query.order_by(Attendance.date.desc(), Attendance.id.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    departments = Department.query.order_by(Department.name.asc()).all()

    # Quick summary stats
    today = get_bangkok_today()
    today_present = Attendance.query.filter_by(date=today, status='Present').count()
    today_late = Attendance.query.filter_by(date=today, status='Late').count()
    today_on_leave = Attendance.query.filter_by(date=today, status='On Leave').count()

    form = AttendanceAdjustmentForm()

    return render_template(
        'attendance/records.html',
        records=records_paginated,
        departments=departments,
        search=search,
        selected_dept=int(dept_id) if dept_id and dept_id.isdigit() else None,
        selected_status=status_filter,
        date_from=date_from,
        date_to=date_to,
        today_present=today_present,
        today_late=today_late,
        today_on_leave=today_on_leave,
        form=form
    )


@attendance_bp.route('/<int:att_id>/adjust', methods=['POST'])
@login_required
@hr_or_admin_required
def adjust(att_id: int):
    record = Attendance.query.get_or_404(att_id)
    form = AttendanceAdjustmentForm()

    new_status = request.form.get('status')
    new_work_status = request.form.get('work_status')
    late_mins = request.form.get('late_minutes', type=int) or 0
    notes = request.form.get('notes', '').strip()

    if new_status in ['Present', 'Late', 'On Leave', 'Absent']:
        record.status = new_status
    if new_work_status in ['Working', 'Completed']:
        record.work_status = new_work_status
    record.late_minutes = late_mins
    record.notes = notes
    record.adjusted_by_id = current_user.id

    db.session.commit()
    log_audit('ADJUST_ATTENDANCE', 'Attendance', record.id, f"ปรับแก้ข้อมูลเวลา วันที่ {record.date} สถานะใหม่: {record.status} โดย {current_user.username}")
    flash(f'ปรับปรุงข้อมูลการลงเวลาของ {record.employee.full_name} สำเร็จ', 'success')
    return redirect(request.referrer or url_for('attendance.records'))


@attendance_bp.route('/export/csv')
@login_required
@hr_or_admin_required
def export_csv():
    dept_id = request.args.get('department_id', '', type=str)
    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = Attendance.query.join(Employee, Attendance.employee_id == Employee.id)

    if dept_id and dept_id.isdigit():
        query = query.filter(Employee.department_id == int(dept_id))
    if status_filter:
        query = query.filter(Attendance.status == status_filter)
    try:
        d_from = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None
        d_to = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None
    except ValueError:
        flash('รูปแบบวันที่รายงานไม่ถูกต้อง', 'danger')
        return redirect(url_for('attendance.records'))
    if d_from and d_to and d_from > d_to:
        flash('วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด', 'danger')
        return redirect(url_for('attendance.records'))
    if d_from:
        query = query.filter(Attendance.date >= d_from)
    if d_to:
        query = query.filter(Attendance.date <= d_to)

    records = query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()

    # Generate CSV with UTF-8 BOM for Microsoft Excel compatibility
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow([
        'ลำดับ', 'รหัสพนักงาน', 'ชื่อ-นามสกุล', 'แผนก', 'ตำแหน่ง',
        'วันที่', 'เวลาเข้างาน', 'เวลาออกงาน', 'สถานะ', 'มาสาย (นาที)', 'ชั่วโมงทำงาน', 'หมายเหตุ'
    ])

    for idx, r in enumerate(records, start=1):
        dept_name = r.employee.department.name if r.employee.department else '-'
        check_in_str = thai_time_format(r.check_in) if r.check_in else '-'
        check_out_str = thai_time_format(r.check_out) if r.check_out else '-'
        writer.writerow([
            idx,
            r.employee.employee_code,
            r.employee.full_name,
            dept_name,
            r.employee.position,
            r.date.strftime('%Y-%m-%d'),
            check_in_str,
            check_out_str,
            r.status_display,
            r.late_minutes,
            r.work_hours,
            r.notes or ''
        ])

    csv_data = '\ufeff' + si.getvalue()
    filename = f"attendance_report_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )
