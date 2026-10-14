from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DateTimeField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError

from app.models import Employee, Position, User


class LoginForm(FlaskForm):
    identifier = StringField('ชื่อผู้ใช้หรืออีเมล', validators=[DataRequired(message='กรุณากรอกชื่อผู้ใช้หรืออีเมล')])
    password = PasswordField('รหัสผ่าน', validators=[DataRequired(message='กรุณากรอกรหัสผ่าน')])
    submit = SubmitField('เข้าสู่ระบบ')


class RegisterForm(FlaskForm):
    username = StringField('ชื่อผู้ใช้', validators=[DataRequired(message='กรุณากรอกชื่อผู้ใช้'), Length(min=3, max=80, message='ชื่อผู้ใช้ต้องมี 3–80 ตัวอักษร')])
    email = StringField('อีเมล', validators=[DataRequired(message='กรุณากรอกอีเมล'), Email(message='กรุณากรอกอีเมลให้ถูกต้อง'), Length(max=120, message='อีเมลต้องไม่เกิน 120 ตัวอักษร')])
    full_name = StringField('ชื่อ-นามสกุล', validators=[DataRequired(message='กรุณากรอกชื่อ-นามสกุล'), Length(min=2, max=120, message='ชื่อต้องมี 2–120 ตัวอักษร')])
    password = PasswordField('รหัสผ่าน', validators=[DataRequired(message='กรุณากรอกรหัสผ่าน'), Length(min=6, max=128, message='รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร')])
    confirm_password = PasswordField('ยืนยันรหัสผ่าน', validators=[DataRequired(), EqualTo('password', message='รหัสผ่านไม่ตรงกัน')])
    submit = SubmitField('สมัครสมาชิก')

    def validate_username(self, username):
        if User.query.filter_by(username=username.data.strip()).first():
            raise ValidationError('ชื่อผู้ใช้นี้ถูกใช้งานแล้ว กรุณาเลือกชื่ออื่น')

    def validate_email(self, email):
        if User.query.filter_by(email=email.data.strip().lower()).first():
            raise ValidationError('อีเมลนี้ถูกใช้งานแล้ว กรุณาใช้อีเมลอื่น')


class TaskForm(FlaskForm):
    title = StringField('ชื่องาน', validators=[DataRequired(message='กรุณากรอกชื่องาน'), Length(min=3, max=200, message='ชื่องานต้องมี 3–200 ตัวอักษร')])
    description = TextAreaField('รายละเอียดงาน', validators=[DataRequired(message='กรุณากรอกรายละเอียดงาน'), Length(min=5, max=4000, message='รายละเอียดต้องมี 5–4,000 ตัวอักษร')])
    category = StringField('หมวดหมู่', validators=[DataRequired(message='กรุณากรอกหมวดหมู่'), Length(min=2, max=80, message='หมวดหมู่ต้องมี 2–80 ตัวอักษร')])
    assignee = StringField('ผู้รับผิดชอบ', validators=[DataRequired(message='กรุณากรอกชื่อผู้รับผิดชอบ'), Length(min=2, max=120, message='ชื่อผู้รับผิดชอบต้องมี 2–120 ตัวอักษร')])
    status = SelectField('สถานะงาน', choices=[('Pending', 'รอดำเนินการ'), ('In Progress', 'กำลังทำ'), ('Completed', 'เสร็จสิ้น')], validators=[DataRequired()])
    start_date = DateField('วันที่เริ่มต้น', format='%Y-%m-%d', validators=[Optional()])
    due_date = DateField('วันกำหนดส่ง', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('บันทึกงาน')


class EmployeeForm(FlaskForm):
    employee_code = StringField('รหัสพนักงาน', validators=[DataRequired(message='กรุณากรอกรหัสพนักงาน'), Length(min=2, max=50, message='รหัสพนักงานต้องมี 2–50 ตัวอักษร')])
    first_name = StringField('ชื่อ', validators=[DataRequired(message='กรุณากรอกชื่อ'), Length(min=2, max=60, message='ชื่อต้องมี 2–60 ตัวอักษร')])
    last_name = StringField('นามสกุล', validators=[DataRequired(message='กรุณากรอกนามสกุล'), Length(min=2, max=60, message='นามสกุลต้องมี 2–60 ตัวอักษร')])
    email = StringField('อีเมลติดต่อ', validators=[DataRequired(message='กรุณากรอกอีเมล'), Email(message='กรุณากรอกอีเมลให้ถูกต้อง'), Length(max=120, message='อีเมลต้องไม่เกิน 120 ตัวอักษร')])
    phone = StringField('เบอร์โทรศัพท์', validators=[Optional(), Length(max=30, message='เบอร์โทรศัพท์ต้องไม่เกิน 30 ตัวอักษร')])
    department_id = SelectField('แผนก', coerce=int, validators=[Optional()])
    position = StringField('ตำแหน่งงาน', validators=[DataRequired(message='กรุณาเลือกหรือกรอกตำแหน่งงาน'), Length(min=2, max=100, message='ตำแหน่งงานต้องมี 2–100 ตัวอักษร')])
    hire_date = DateField('วันที่เริ่มงาน', format='%Y-%m-%d', validators=[DataRequired(message='กรุณาระบุวันที่เริ่มงาน')])
    work_start_time = StringField('เวลาเริ่มงาน', default='09:00', validators=[DataRequired(message='กรุณาระบุเวลาเริ่มงาน'), Regexp(r'^(?:[01]\d|2[0-3]):[0-5]\d$', message='กรุณาระบุเวลาในรูปแบบ 24 ชั่วโมง เช่น 09:00')])
    work_end_time = StringField('เวลาเลิกงาน', default='18:00', validators=[DataRequired(message='กรุณาระบุเวลาเลิกงาน'), Regexp(r'^(?:[01]\d|2[0-3]):[0-5]\d$', message='กรุณาระบุเวลาในรูปแบบ 24 ชั่วโมง เช่น 18:00')])
    status = SelectField('สถานะการทำงาน', choices=[
        ('Active', 'ทำงานอยู่'),
        ('Probation', 'ทดลองงาน'),
        ('Resigned', 'ลาออก')
    ], default='Active', validators=[DataRequired(message='กรุณาเลือกสถานะการทำงาน')])
    user_id = SelectField('เชื่อมโยงบัญชีผู้ใช้', coerce=int, validators=[Optional()])
    submit = SubmitField('บันทึกข้อมูลพนักงาน')

    def __init__(self, original_code=None, original_email=None, original_position=None, *args, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)
        self.original_code = original_code
        self.original_email = original_email
        self.original_position = original_position

    def validate_employee_code(self, employee_code):
        if self.original_code and employee_code.data.strip() == self.original_code:
            return
        if Employee.query.filter_by(employee_code=employee_code.data.strip()).first():
            raise ValidationError('รหัสพนักงานนี้มีอยู่ในระบบแล้ว')

    def validate_email(self, email):
        if self.original_email and email.data.strip().lower() == self.original_email:
            return
        if Employee.query.filter_by(email=email.data.strip().lower()).first():
            raise ValidationError('อีเมลนี้ถูกใช้งานโดยพนักงานท่านอื่นแล้ว')

    def validate_position(self, position):
        value = position.data.strip()
        if value == self.original_position or Position.query.filter_by(name=value).first():
            return
        raise ValidationError('กรุณาเลือกตำแหน่งที่มีอยู่ หรือสร้างตำแหน่งในหน้าจัดการตำแหน่งก่อน')


class PositionForm(FlaskForm):
    name = StringField('ชื่อตำแหน่ง', validators=[DataRequired(message='กรุณากรอกชื่อตำแหน่ง'), Length(min=2, max=100, message='ชื่อตำแหน่งต้องมี 2–100 ตัวอักษร')])
    description = StringField('รายละเอียดตำแหน่ง', validators=[Optional(), Length(max=255, message='รายละเอียดต้องไม่เกิน 255 ตัวอักษร')])
    submit = SubmitField('บันทึกตำแหน่ง')

    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        value = name.data.strip()
        if value != self.original_name and Position.query.filter_by(name=value).first():
            raise ValidationError('ชื่อตำแหน่งนี้มีอยู่แล้ว')


class LeaveRequestForm(FlaskForm):
    leave_type = SelectField('ประเภทการลา', choices=[
        ('Sick', 'ลาป่วย'),
        ('Personal', 'ลากิจ'),
        ('Vacation', 'ลาพักร้อน'),
        ('Other', 'ลาอื่น ๆ')
    ], validators=[DataRequired(message='กรุณาเลือกประเภทการลา')])
    start_date = DateField('วันที่เริ่มลา', format='%Y-%m-%d', validators=[DataRequired(message='กรุณาระบุวันที่เริ่มลา')])
    end_date = DateField('วันที่สิ้นสุดลา', format='%Y-%m-%d', validators=[DataRequired(message='กรุณาระบุวันที่สิ้นสุดลา')])
    reason = TextAreaField('เหตุผลการลา', validators=[DataRequired(message='กรุณาระบุเหตุผลการลา'), Length(min=5, max=1000, message='เหตุผลต้องมี 5–1,000 ตัวอักษร')])
    submit = SubmitField('ยื่นคำขอลา')

    def validate_end_date(self, end_date):
        if self.start_date.data and end_date.data and end_date.data < self.start_date.data:
            raise ValidationError('วันที่สิ้นสุดลาต้องไม่น้อยกว่าวันที่เริ่มลา')


class AttendanceAdjustmentForm(FlaskForm):
    date = DateField('วันที่', format='%Y-%m-%d', validators=[DataRequired(message='กรุณาระบุวันที่')])
    check_in = StringField('เวลาเข้างาน', validators=[Optional()])
    check_out = StringField('เวลาออกงาน', validators=[Optional()])
    status = SelectField('สถานะ', choices=[
        ('Present', 'ตรงเวลา'),
        ('Late', 'มาสาย'),
        ('On Leave', 'ลางาน'),
        ('Absent', 'ขาดงาน')
    ], validators=[DataRequired(message='กรุณาเลือกสถานะ')])
    work_status = SelectField('สถานะการทำงาน', choices=[
        ('Working', 'กำลังทำงาน'),
        ('Completed', 'เสร็จสิ้นการทำงาน')
    ], validators=[DataRequired(message='กรุณาเลือกสถานะการทำงาน')])
    late_minutes = IntegerField('นาทีที่สาย', default=0, validators=[NumberRange(min=0, message='จำนวนนาทีต้องไม่ติดลบ')])
    notes = StringField('หมายเหตุการแก้ไข', validators=[Optional(), Length(max=255, message='หมายเหตุต้องไม่เกิน 255 ตัวอักษร')])
    submit = SubmitField('บันทึกการแก้ไข')


class DepartmentForm(FlaskForm):
    code = StringField('รหัสแผนก', validators=[DataRequired(message='กรุณากรอกรหัสแผนก'), Length(min=2, max=20, message='รหัสแผนกต้องมี 2–20 ตัวอักษร')])
    name = StringField('ชื่อแผนก', validators=[DataRequired(message='กรุณากรอกชื่อแผนก'), Length(min=2, max=120, message='ชื่อแผนกต้องมี 2–120 ตัวอักษร')])
    description = StringField('คำอธิบายแผนก', validators=[Optional(), Length(max=255, message='คำอธิบายต้องไม่เกิน 255 ตัวอักษร')])
    submit = SubmitField('บันทึกแผนก')


class SystemSettingsForm(FlaskForm):
    company_name = StringField('ชื่อบริษัท / องค์กร', validators=[DataRequired(message='กรุณากรอกชื่อบริษัท'), Length(max=100, message='ชื่อต้องไม่เกิน 100 ตัวอักษร')])
    grace_period_minutes = IntegerField('เวลาผ่อนผันการมาสาย (นาที)', validators=[DataRequired(message='กรุณาระบุเวลาผ่อนผัน'), NumberRange(min=0, max=120, message='เวลาผ่อนผันต้องอยู่ระหว่าง 0–120 นาที')])
    default_work_start = StringField('เวลาเริ่มงานมาตรฐาน', validators=[DataRequired(message='กรุณาระบุเวลาเริ่มงาน'), Regexp(r'^(?:[01]\d|2[0-3]):[0-5]\d$', message='กรุณาระบุเวลาในรูปแบบ 24 ชั่วโมง เช่น 09:00')])
    default_work_end = StringField('เวลาเลิกงานมาตรฐาน', validators=[DataRequired(message='กรุณาระบุเวลาเลิกงาน'), Regexp(r'^(?:[01]\d|2[0-3]):[0-5]\d$', message='กรุณาระบุเวลาในรูปแบบ 24 ชั่วโมง เช่น 18:00')])
    annual_vacation_quota = IntegerField('สิทธิ์ลาพักร้อนต่อปี (วัน)', validators=[DataRequired(message='กรุณาระบุสิทธิ์วันลา'), NumberRange(min=0, max=60, message='จำนวนวันลาต้องอยู่ระหว่าง 0–60 วัน')])
    sick_leave_quota = IntegerField('สิทธิ์ลาป่วยต่อปี (วัน)', validators=[DataRequired(message='กรุณาระบุสิทธิ์วันลา'), NumberRange(min=0, max=60, message='จำนวนวันลาต้องอยู่ระหว่าง 0–60 วัน')])
    personal_leave_quota = IntegerField('สิทธิ์ลากิจต่อปี (วัน)', validators=[DataRequired(message='กรุณาระบุสิทธิ์วันลา'), NumberRange(min=0, max=60, message='จำนวนวันลาต้องอยู่ระหว่าง 0–60 วัน')])
    submit = SubmitField('บันทึกการตั้งค่าระบบ')
