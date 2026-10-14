from __future__ import annotations

from datetime import datetime, date, time, timezone, timedelta
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

BANGKOK_TZ = timezone(timedelta(hours=7))


def get_bangkok_now() -> datetime:
    """Returns current datetime in Bangkok timezone."""
    return datetime.now(BANGKOK_TZ)


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user', index=True)  # 'admin', 'hr', 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks = db.relationship('Task', back_populates='user', cascade='all, delete-orphan')

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_hr_or_admin(self) -> bool:
        return self.role in ['admin', 'hr', 'manager']

    @property
    def role_display(self) -> str:
        roles_map = {
            'admin': 'ผู้ดูแลระบบ',
            'hr': 'ฝ่ายบุคคล',
            'manager': 'ผู้จัดการ',
            'user': 'พนักงาน'
        }
        return roles_map.get(self.role, self.role)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employees = db.relationship('Employee', back_populates='department')

    def __repr__(self):
        return f'<Department {self.name}>'


class Position(db.Model):
    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Position {self.name}>'


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    position = db.Column(db.String(100), nullable=False, index=True)
    hire_date = db.Column(db.Date, nullable=False, default=date.today)
    work_start_time = db.Column(db.String(5), nullable=False, default='09:00')  # HH:MM
    work_end_time = db.Column(db.String(5), nullable=False, default='18:00')    # HH:MM
    status = db.Column(db.String(30), nullable=False, default='Active', index=True)  # 'Active', 'Probation', 'Resigned'
    avatar_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    department = db.relationship('Department', back_populates='employees')
    user = db.relationship('User', backref=db.backref('employee', uselist=False))
    attendances = db.relationship('Attendance', back_populates='employee', cascade='all, delete-orphan', lazy='dynamic')
    leave_requests = db.relationship('LeaveRequest', back_populates='employee', cascade='all, delete-orphan', lazy='dynamic')
    leave_balances = db.relationship('LeaveBalance', back_populates='employee', cascade='all, delete-orphan')

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'

    @property
    def initials(self) -> str:
        f = self.first_name[:1].upper() if self.first_name else 'E'
        l = self.last_name[:1].upper() if self.last_name else ''
        return f"{f}{l}"

    @property
    def status_display(self) -> str:
        status_map = {
            'Active': 'ทำงานอยู่',
            'Probation': 'ทดลองงาน',
            'Resigned': 'ลาออก'
        }
        return status_map.get(self.status, self.status)

    @property
    def status_badge_class(self) -> str:
        status_badges = {
            'Active': 'badge-success-soft',
            'Probation': 'badge-warning-soft',
            'Resigned': 'badge-secondary-soft'
        }
        return status_badges.get(self.status, 'badge-secondary-soft')

    def __repr__(self):
        return f'<Employee {self.employee_code} - {self.full_name}>'


class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True, default=date.today)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Present', index=True)  # 'Present', 'Late', 'On Leave', 'Absent'
    work_status = db.Column(db.String(30), nullable=False, default='Working', index=True)  # 'Working', 'Completed'
    late_minutes = db.Column(db.Integer, nullable=False, default=0)
    work_hours = db.Column(db.Float, nullable=False, default=0.0)
    notes = db.Column(db.String(255), nullable=True)
    adjusted_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = db.relationship('Employee', back_populates='attendances')
    adjusted_by = db.relationship('User', foreign_keys=[adjusted_by_id])

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uq_employee_attendance_date'),
    )

    @property
    def status_display(self) -> str:
        s_map = {
            'Present': 'ตรงเวลา',
            'Late': 'มาสาย',
            'On Leave': 'ลางาน',
            'Absent': 'ขาดงาน'
        }
        return s_map.get(self.status, self.status)

    @property
    def status_badge_class(self) -> str:
        s_badges = {
            'Present': 'badge-success-soft',
            'Late': 'badge-danger-soft',
            'On Leave': 'badge-info-soft',
            'Absent': 'badge-dark-soft'
        }
        return s_badges.get(self.status, 'badge-secondary-soft')

    @property
    def work_status_display(self) -> str:
        ws_map = {
            'Working': 'กำลังทำงาน',
            'Completed': 'เสร็จสิ้นการทำงาน'
        }
        return ws_map.get(self.work_status, self.work_status)

    def calculate_work_hours(self):
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            hours = delta.total_seconds() / 3600.0
            self.work_hours = round(max(0.0, hours), 2)
        else:
            self.work_hours = 0.0

    def __repr__(self):
        return f'<Attendance {self.employee_id} {self.date} {self.status}>'


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    leave_type = db.Column(db.String(50), nullable=False, index=True)  # 'Sick', 'Personal', 'Vacation', 'Other'
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    days_count = db.Column(db.Float, nullable=False, default=1.0)
    reason = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Pending', index=True)  # 'Pending', 'Approved', 'Rejected'
    action_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action_at = db.Column(db.DateTime, nullable=True)
    action_notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = db.relationship('Employee', back_populates='leave_requests')
    action_by = db.relationship('User', foreign_keys=[action_by_id])

    @property
    def leave_type_display(self) -> str:
        lt_map = {
            'Sick': 'ลาป่วย',
            'Personal': 'ลากิจ',
            'Vacation': 'ลาพักร้อน',
            'Other': 'ลาอื่นๆ'
        }
        return lt_map.get(self.leave_type, self.leave_type)

    @property
    def status_display(self) -> str:
        st_map = {
            'Pending': 'รออนุมัติ',
            'Approved': 'อนุมัติแล้ว',
            'Rejected': 'ปฏิเสธ'
        }
        return st_map.get(self.status, self.status)

    @property
    def status_badge_class(self) -> str:
        st_badges = {
            'Pending': 'badge-warning-soft',
            'Approved': 'badge-success-soft',
            'Rejected': 'badge-danger-soft'
        }
        return st_badges.get(self.status, 'badge-secondary-soft')

    def __repr__(self):
        return f'<LeaveRequest {self.employee_id} {self.leave_type} {self.status}>'


class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, default=2026, index=True)
    leave_type = db.Column(db.String(50), nullable=False)  # 'Sick', 'Personal', 'Vacation'
    total_days = db.Column(db.Float, nullable=False, default=10.0)
    used_days = db.Column(db.Float, nullable=False, default=0.0)

    employee = db.relationship('Employee', back_populates='leave_balances')

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'year', 'leave_type', name='uq_employee_leave_balance'),
    )

    @property
    def remaining_days(self) -> float:
        return max(0.0, round(self.total_days - self.used_days, 1))

    @property
    def leave_type_display(self) -> str:
        lt_map = {
            'Sick': 'ลาป่วย',
            'Personal': 'ลากิจ',
            'Vacation': 'ลาพักร้อน',
            'Other': 'ลาอื่นๆ'
        }
        return lt_map.get(self.leave_type, self.leave_type)

    def __repr__(self):
        return f'<LeaveBalance {self.employee_id} {self.leave_type} {self.remaining_days}/{self.total_days}>'


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=True)

    @classmethod
    def get_val(cls, key: str, default: str = '') -> str:
        record = cls.query.filter_by(key=key).first()
        return record.value if record else default

    @classmethod
    def set_val(cls, key: str, value: str, description: str = ''):
        record = cls.query.filter_by(key=key).first()
        if record:
            record.value = value
            if description:
                record.description = description
        else:
            record = cls(key=key, value=value, description=description)
            db.session.add(record)
        db.session.commit()

    def __repr__(self):
        return f'<SystemSetting {self.key}={self.value}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.action} by User {self.user_id}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False, index=True)
    assignee = db.Column(db.String(120), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default='Pending', index=True)
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='tasks')

    @property
    def status_display(self) -> str:
        return {
            'Pending': 'รอดำเนินการ',
            'In Progress': 'กำลังดำเนินการ',
            'Completed': 'เสร็จสิ้น',
        }.get(self.status, self.status)

    def __repr__(self):
        return f'<Task {self.title}>'
