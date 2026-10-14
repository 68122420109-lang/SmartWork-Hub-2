"""Add HR management tables without replacing existing data.

Revision ID: 5e12d18f6a90
Revises: 1806035be67c
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = '5e12d18f6a90'
down_revision = '1806035be67c'
branch_labels = None
depends_on = None


def _create_if_missing(name, *columns, **kwargs):
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, **kwargs)


def upgrade():
    _create_if_missing(
        'departments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    _create_if_missing(
        'positions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    _create_if_missing(
        'employees',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_code', sa.String(50), nullable=False, unique=True),
        sa.Column('first_name', sa.String(60), nullable=False),
        sa.Column('last_name', sa.String(60), nullable=False),
        sa.Column('email', sa.String(120), nullable=False, unique=True),
        sa.Column('phone', sa.String(30)),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id', ondelete='SET NULL')),
        sa.Column('position', sa.String(100), nullable=False),
        sa.Column('hire_date', sa.Date(), nullable=False),
        sa.Column('work_start_time', sa.String(5), nullable=False, server_default='09:00'),
        sa.Column('work_end_time', sa.String(5), nullable=False, server_default='18:00'),
        sa.Column('status', sa.String(30), nullable=False, server_default='Active'),
        sa.Column('avatar_url', sa.String(255)),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    _create_if_missing(
        'attendances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('check_in', sa.DateTime()),
        sa.Column('check_out', sa.DateTime()),
        sa.Column('status', sa.String(30), nullable=False, server_default='Present'),
        sa.Column('work_status', sa.String(30), nullable=False, server_default='Working'),
        sa.Column('late_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('work_hours', sa.Float(), nullable=False, server_default='0'),
        sa.Column('notes', sa.String(255)),
        sa.Column('adjusted_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('employee_id', 'date', name='uq_employee_attendance_date'),
    )
    _create_if_missing(
        'leave_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('leave_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('days_count', sa.Float(), nullable=False, server_default='1'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('attachment_url', sa.String(255)),
        sa.Column('status', sa.String(30), nullable=False, server_default='Pending'),
        sa.Column('action_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action_at', sa.DateTime()),
        sa.Column('action_notes', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    _create_if_missing(
        'leave_balances',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False, server_default='2026'),
        sa.Column('leave_type', sa.String(50), nullable=False),
        sa.Column('total_days', sa.Float(), nullable=False, server_default='10'),
        sa.Column('used_days', sa.Float(), nullable=False, server_default='0'),
        sa.UniqueConstraint('employee_id', 'year', 'leave_type', name='uq_employee_leave_balance'),
    )
    _create_if_missing(
        'system_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(50), nullable=False, unique=True),
        sa.Column('value', sa.String(255), nullable=False),
        sa.Column('description', sa.String(255)),
    )
    _create_if_missing(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_type', sa.String(50)),
        sa.Column('target_id', sa.Integer()),
        sa.Column('details', sa.Text()),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    bind = op.get_bind()
    departments = sa.Table('departments', sa.MetaData(), autoload_with=bind)
    if not bind.execute(sa.select(departments.c.id).limit(1)).first():
        bind.execute(departments.insert(), [
            {'code': 'IT', 'name': 'เทคโนโลยีสารสนเทศ (IT)', 'description': 'ฝ่ายพัฒนาระบบและโครงสร้างพื้นฐานไอที', 'created_at': datetime.utcnow()},
            {'code': 'HR', 'name': 'ทรัพยากรบุคคล (Human Resources)', 'description': 'ฝ่ายบริหารและพัฒนาบุคลากร', 'created_at': datetime.utcnow()},
            {'code': 'MKT', 'name': 'การตลาดและประชาสัมพันธ์ (Marketing)', 'description': 'ฝ่ายการตลาด การขาย และแบรนด์', 'created_at': datetime.utcnow()},
            {'code': 'ACC', 'name': 'การเงินและบัญชี (Finance & Accounting)', 'description': 'ฝ่ายบริหารการเงินและการบัญชี', 'created_at': datetime.utcnow()},
            {'code': 'OPS', 'name': 'ปฏิบัติการ (Operations)', 'description': 'ฝ่ายบริหารงานปฏิบัติการและบริการลูกค้า', 'created_at': datetime.utcnow()},
        ])
    positions = sa.Table('positions', sa.MetaData(), autoload_with=bind)
    employees = sa.Table('employees', sa.MetaData(), autoload_with=bind)
    existing_positions = {row[0] for row in bind.execute(sa.select(positions.c.name))}
    legacy_positions = {
        row[0].strip()
        for row in bind.execute(sa.select(employees.c.position).distinct())
        if row[0] and row[0].strip()
    } - existing_positions
    if legacy_positions:
        bind.execute(positions.insert(), [{'name': name} for name in sorted(legacy_positions)])
    settings = sa.Table('system_settings', sa.MetaData(), autoload_with=bind)
    defaults = [
        ('company_name', 'SmartWork Hub', 'ชื่อบริษัท'),
        ('grace_period_minutes', '15', 'เวลาผ่อนผันการมาสาย (นาที)'),
        ('default_work_start', '09:00', 'เวลาเริ่มงานมาตรฐาน'),
        ('default_work_end', '18:00', 'เวลาเลิกงานมาตรฐาน'),
        ('annual_vacation_quota', '10', 'โควตาลาพักร้อนต่อปี'),
        ('sick_leave_quota', '30', 'โควตาลาป่วยต่อปี'),
        ('personal_leave_quota', '6', 'โควตาลากิจต่อปี'),
    ]
    for key, value, description in defaults:
        if not bind.execute(sa.select(settings.c.id).where(settings.c.key == key).limit(1)).first():
            bind.execute(settings.insert().values(key=key, value=value, description=description))


def downgrade():
    # This migration may adopt tables that predate Alembic; preserve their data.
    pass
