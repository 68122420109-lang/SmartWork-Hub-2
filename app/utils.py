from __future__ import annotations

from datetime import datetime, date, time, timedelta, timezone
from functools import wraps
from flask import abort, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog, Employee, SystemSetting, BANGKOK_TZ


def get_bangkok_now() -> datetime:
    """Return timezone-aware current datetime in Bangkok (UTC+7)."""
    return datetime.now(BANGKOK_TZ)


def get_bangkok_today() -> date:
    """Return current date in Bangkok (UTC+7)."""
    return get_bangkok_now().date()


def thai_date_format(d: date | datetime | None, include_time: bool = False) -> str:
    """Format date into Thai readable format (e.g. 12 ต.ค. 2569)."""
    if not d:
        return '-'
    if isinstance(d, datetime):
        # convert naive to bangkok if needed
        dt = d
        if dt.tzinfo is None:
            # Assume UTC stored in DB, convert to Bangkok
            dt = dt.replace(tzinfo=timezone.utc).astimezone(BANGKOK_TZ)
        d_val = dt.date()
        time_str = dt.strftime('%H:%M น.')
    else:
        d_val = d
        time_str = ''

    thai_months = [
        '', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
        'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'
    ]
    thai_year = d_val.year + 543
    month_str = thai_months[d_val.month]
    base_str = f"{d_val.day} {month_str} {thai_year}"
    if include_time and time_str:
        return f"{base_str} {time_str}"
    return base_str


def thai_time_format(dt: datetime | time | None) -> str:
    """Format time into Thai format (HH:MM น.)."""
    if not dt:
        return '-'
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(BANGKOK_TZ)
        return dt.strftime('%H:%M น.')
    if isinstance(dt, time):
        return dt.strftime('%H:%M น.')
    return '-'


def log_audit(action: str, target_type: str | None = None, target_id: int | None = None, details: str | None = None):
    """Record an audit log entry."""
    try:
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        ip_addr = request.remote_addr if request else None
        audit = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_addr,
            created_at=datetime.utcnow()
        )
        db.session.add(audit)
        db.session.commit()
    except Exception:
        db.session.rollback()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def hr_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_hr_or_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def get_current_employee() -> Employee | None:
    """Get the Employee profile linked to the current logged-in user."""
    if not current_user.is_authenticated:
        return None
    return Employee.query.filter_by(user_id=current_user.id).first()


def calculate_late_minutes(check_in_dt: datetime, work_start_str: str = '09:00', grace_minutes: int = 15) -> int:
    """
    Calculate late minutes given check-in datetime and work start time (HH:MM).
    Takes grace period into account.
    """
    if not check_in_dt:
        return 0
    # Bangkok local time
    if check_in_dt.tzinfo is None:
        local_dt = check_in_dt.replace(tzinfo=timezone.utc).astimezone(BANGKOK_TZ)
    else:
        local_dt = check_in_dt.astimezone(BANGKOK_TZ)

    try:
        start_hour, start_min = map(int, work_start_str.split(':'))
    except Exception:
        start_hour, start_min = 9, 0

    scheduled_dt = local_dt.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    grace_cutoff = scheduled_dt + timedelta(minutes=grace_minutes)

    if local_dt > grace_cutoff:
        diff = local_dt - scheduled_dt
        return int(diff.total_seconds() // 60)
    return 0


def seed_defaults():
    """Ensure baseline departments, system settings, and employee link exist."""
    from app.models import Department, SystemSetting, Employee, User

    # 1. System Settings
    settings = {
        'company_name': ('SmartWork Hub Co., Ltd.', 'ชื่อบริษัท'),
        'grace_period_minutes': ('15', 'เวลาผ่อนผันการมาสาย (นาที)'),
        'default_work_start': ('09:00', 'เวลาเริ่มงานมาตรฐาน (HH:MM)'),
        'default_work_end': ('18:00', 'เวลาเลิกงานมาตรฐาน (HH:MM)'),
        'annual_vacation_quota': ('10', 'โควตาลากิจ/พักร้อนต่อปี (วัน)'),
        'sick_leave_quota': ('30', 'โควตาลาป่วยต่อปี (วัน)'),
        'personal_leave_quota': ('6', 'โควตาลากิจส่วนตัวต่อปี (วัน)')
    }
    for key, (val, desc) in settings.items():
        if not SystemSetting.query.filter_by(key=key).first():
            db.session.add(SystemSetting(key=key, value=val, description=desc))

    # 2. Departments
    if Department.query.count() == 0:
        default_depts = [
            Department(code='IT', name='เทคโนโลยีสารสนเทศ (IT)', description='ฝ่ายพัฒนาระบบและโครงสร้างพื้นฐานไอที'),
            Department(code='HR', name='ทรัพยากรบุคคล (Human Resources)', description='ฝ่ายบริหารและพัฒนาบุคลากร'),
            Department(code='MKT', name='การตลาดและประชาสัมพันธ์ (Marketing)', description='ฝ่ายการตลาด การขาย และแบรนด์'),
            Department(code='ACC', name='การเงินและบัญชี (Finance & Accounting)', description='ฝ่ายบริหารการเงินและการบัญชี'),
            Department(code='OPS', name='ปฏิบัติการ (Operations)', description='ฝ่ายบริหารงานปฏิบัติการและบริการลูกค้า')
        ]
        db.session.add_all(default_depts)
        db.session.commit()

    # 3. Ensure admin user has an employee profile if not linked
    admin_user = User.query.filter_by(role='admin').first()
    if admin_user:
        emp = Employee.query.filter_by(user_id=admin_user.id).first()
        if not emp:
            it_dept = Department.query.filter_by(code='IT').first()
            emp = Employee(
                employee_code='ADM001',
                first_name=admin_user.full_name.split()[0] if admin_user.full_name else 'Admin',
                last_name=admin_user.full_name.split()[-1] if len(admin_user.full_name.split()) > 1 else 'System',
                email=admin_user.email,
                phone='02-123-4567',
                department_id=it_dept.id if it_dept else None,
                position='System Administrator',
                hire_date=date.today(),
                work_start_time='09:00',
                work_end_time='18:00',
                status='Active',
                user_id=admin_user.id
            )
            db.session.add(emp)
            db.session.commit()

