import csv
import io
import os
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Response, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from PIL import Image

from app.extensions import db
from app.forms import LeaveRequestForm
from app.models import Employee, LeaveBalance, LeaveRequest
from app.utils import get_current_employee, hr_or_admin_required
from app.leave import leave_bp


@leave_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    employee = get_current_employee()
    is_hr = current_user.is_hr_or_admin
    if not is_hr and not employee:
        flash('บัญชีนี้ยังไม่ได้เชื่อมโยงกับข้อมูลพนักงาน', 'warning')
        return redirect(url_for('main.home'))

    form = LeaveRequestForm()
    if form.validate_on_submit():
        if not employee:
            flash('กรุณาเชื่อมโยงบัญชีพนักงานก่อนยื่นคำขอลา', 'danger')
            return redirect(url_for('leave.index'))

        # Process multiple attachments
        uploaded_files = []
        if form.attachments.data:
            for file_storage in form.attachments.data:
                if not file_storage or not getattr(file_storage, 'filename', None):
                    continue
                filename_orig = file_storage.filename.lower()
                ext = filename_orig.rsplit('.', 1)[-1] if '.' in filename_orig else ''
                if ext not in {'jpg', 'jpeg', 'png', 'webp', 'pdf'}:
                    flash('ชนิดไฟล์แนบไม่ได้รับอนุญาต (รองรับเฉพาะ JPG, PNG, WEBP, PDF)', 'danger')
                    return redirect(url_for('leave.index'))

                # Validate real file content
                try:
                    raw_head = file_storage.stream.read(1024)
                    file_storage.stream.seek(0)
                    if ext == 'pdf':
                        if not raw_head.startswith(b'%PDF'):
                            flash('ไฟล์ PDF ไม่ถูกต้องหรือถูกแก้ไขนามสกุล', 'danger')
                            return redirect(url_for('leave.index'))
                    else:
                        pil_img = Image.open(file_storage.stream)
                        pil_img.verify()
                        file_storage.stream.seek(0)
                except Exception:
                    flash('ไฟล์แนบเสียหายหรือไม่ถูกต้องตามมาตรฐานความปลอดภัย', 'danger')
                    return redirect(url_for('leave.index'))

                upload_dir = Path(current_app.config['BASE_DIR']) / 'app' / 'static' / 'uploads' / 'leave_attachments'
                upload_dir.mkdir(parents=True, exist_ok=True)
                safe_name = f"leave_emp{employee.id}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
                file_storage.save(upload_dir / safe_name)
                uploaded_files.append(f"uploads/leave_attachments/{safe_name}")

        leave = LeaveRequest(
            employee_id=employee.id,
            leave_type=form.leave_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            days_count=(form.end_date.data - form.start_date.data).days + 1,
            reason=form.reason.data.strip(),
        )
        db.session.add(leave)
        db.session.commit()

        # Save attachment records with associated dates
        attachment_dates = request.form.getlist('attachment_dates')
        for idx, file_path in enumerate(uploaded_files):
            try:
                attached_date = date.fromisoformat(attachment_dates[idx]) if idx < len(attachment_dates) else leave.start_date
            except Exception:
                attached_date = leave.start_date
            attachment = LeaveAttachment(
                leave_request_id=leave.id,
                file_path=file_path,
                attached_date=attached_date,
            )
            db.session.add(attachment)
        db.session.commit()

        flash('ส่งคำขอลาเรียบร้อยแล้ว', 'success')
        return redirect(url_for('leave.index'))

    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    query = LeaveRequest.query.join(Employee)
    if not is_hr:
        query = query.filter(LeaveRequest.employee_id == employee.id)
    if status_filter in {'Pending', 'Approved', 'Rejected'}:
        query = query.filter(LeaveRequest.status == status_filter)
    try:
        start_filter = date.fromisoformat(date_from) if date_from else None
        end_filter = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        flash('รูปแบบวันที่รายงานไม่ถูกต้อง', 'danger')
        return redirect(url_for('leave.index'))
    if start_filter and end_filter and start_filter > end_filter:
        flash('วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด', 'danger')
        return redirect(url_for('leave.index'))
    if start_filter:
        query = query.filter(LeaveRequest.end_date >= start_filter)
    if end_filter:
        query = query.filter(LeaveRequest.start_date <= end_filter)
    requests_list = query.order_by(LeaveRequest.created_at.desc()).limit(200).all()
    pending_count = LeaveRequest.query.filter_by(status='Pending').count() if is_hr else 0
    return render_template(
        'leave/index.html',
        form=form,
        leave_requests=requests_list,
        employee=employee,
        is_hr=is_hr,
        pending_count=pending_count,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )


@leave_bp.route('/<int:leave_id>/decision', methods=['POST'])
@login_required
@hr_or_admin_required
def decision(leave_id: int):
    leave = LeaveRequest.query.get_or_404(leave_id)
    decision_value = request.form.get('decision')
    if leave.status != 'Pending':
        flash('คำขอนี้ได้รับการพิจารณาแล้ว', 'warning')
        return redirect(url_for('leave.index'))
    if decision_value not in {'Approved', 'Rejected'}:
        flash('สถานะการพิจารณาไม่ถูกต้อง', 'danger')
        return redirect(url_for('leave.index'))

    leave.status = decision_value
    leave.action_by_id = current_user.id
    leave.action_at = datetime.now(timezone.utc).replace(tzinfo=None)
    leave.action_notes = request.form.get('action_notes', '').strip()[:255] or None
    if decision_value == 'Approved':
        balance = LeaveBalance.query.filter_by(
            employee_id=leave.employee_id,
            year=leave.start_date.year,
            leave_type=leave.leave_type,
        ).first()
        if balance and balance.remaining_days < leave.days_count:
            db.session.rollback()
            flash('ยอดวันลาคงเหลือไม่เพียงพอ จึงไม่สามารถอนุมัติคำขอนี้ได้', 'warning')
            return redirect(url_for('leave.index'))
        if balance:
            balance.used_days += leave.days_count
    db.session.commit()
    flash('อนุมัติคำขอลาแล้ว' if decision_value == 'Approved' else 'ปฏิเสธคำขอลาแล้ว', 'success')
    return redirect(url_for('leave.index'))


@leave_bp.route('/report.csv')
@login_required
@hr_or_admin_required
def report_csv():
    start_value = request.args.get('date_from', '').strip()
    end_value = request.args.get('date_to', '').strip()
    query = LeaveRequest.query.join(Employee)
    try:
        if start_value:
            query = query.filter(LeaveRequest.end_date >= date.fromisoformat(start_value))
        if end_value:
            query = query.filter(LeaveRequest.start_date <= date.fromisoformat(end_value))
    except ValueError:
        flash('รูปแบบวันที่รายงานไม่ถูกต้อง', 'danger')
        return redirect(url_for('leave.index'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['รหัสพนักงาน', 'ชื่อ-นามสกุล', 'ประเภทการลา', 'วันที่เริ่ม', 'วันที่สิ้นสุด', 'จำนวนวัน', 'เหตุผล', 'สถานะ'])
    for leave in query.order_by(LeaveRequest.start_date.desc()).all():
        writer.writerow([
            leave.employee.employee_code, leave.employee.full_name, leave.leave_type_display,
            leave.start_date.isoformat(), leave.end_date.isoformat(), leave.days_count,
            leave.reason, leave.status_display,
        ])
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=leave_report_{date.today():%Y%m%d}.csv'},
    )


@leave_bp.route('/attachment/<int:attachment_id>')
@login_required
def download_attachment(attachment_id: int):
    attachment = LeaveAttachment.query.get_or_404(attachment_id)
    employee = get_current_employee()
    # Permission check: HR/Admin or owner of the leave request
    if not current_user.is_hr_or_admin:
        if not employee or attachment.leave_request.employee_id != employee.id:
            abort(403)
    upload_dir = Path(current_app.config['BASE_DIR']) / 'app' / 'static' / 'uploads' / 'leave_attachments'
    filename = os.path.basename(attachment.file_path)
    target_file = upload_dir / filename
    if not target_file.exists():
        abort(404)
    return send_from_directory(upload_dir, filename)

