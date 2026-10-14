import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import Attendance, Department, Employee, LeaveBalance, LeaveRequest, Position, SystemSetting, User
from app.utils import calculate_late_minutes


class HRWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(test_config={
            'SQLALCHEMY_DATABASE_URI': 'sqlite://',
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'LOGIN_DISABLED': False,
        })
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
            db.session.remove()

    def setUp(self):
        with self.app.app_context():
            for model in (Attendance, LeaveRequest, LeaveBalance, Employee, Position, Department, SystemSetting, User):
                db.session.query(model).delete()
            db.session.commit()
            department = Department(code='IT', name='เทคโนโลยีสารสนเทศ')
            admin = User(username='admin', email='admin@example.com', full_name='Admin User', role='admin')
            admin.set_password('secret123')
            employee_user = User(username='employee', email='employee@example.com', full_name='Employee User', role='user')
            employee_user.set_password('secret123')
            hr = User(username='hr', email='hr@example.com', full_name='HR User', role='hr')
            hr.set_password('secret123')
            db.session.add_all([department, admin, employee_user, hr])
            db.session.flush()
            employee = Employee(
                employee_code='EMP001',
                first_name='Employee',
                last_name='User',
                email='employee.work@example.com',
                department_id=department.id,
                position='นักพัฒนาซอฟต์แวร์',
                hire_date=date.today(),
                user_id=employee_user.id,
            )
            db.session.add(employee)
            db.session.add_all([
                SystemSetting(key='default_work_start', value='09:00'),
                SystemSetting(key='default_work_end', value='18:00'),
                SystemSetting(key='grace_period_minutes', value='15'),
            ])
            db.session.flush()
            db.session.add(LeaveBalance(
                employee_id=employee.id,
                year=date.today().year,
                leave_type='Sick',
                total_days=30,
                used_days=0,
            ))
            db.session.commit()
            self.employee_id = employee.id
            self.employee_user_id = employee_user.id
            self.hr_user_id = hr.id
            self.department_id = department.id
        self.client = self.app.test_client()

    def login(self, username, password='secret123'):
        return self.client.post('/login', data={'identifier': username, 'password': password}, follow_redirects=True)

    def test_registration_login_and_role_access(self):
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'full_name': 'New User',
            'password': 'secret123',
            'confirm_password': 'secret123',
        }, follow_redirects=True)
        self.assertIn('สมัครสมาชิกสำเร็จ'.encode(), response.data)
        response = self.login('newuser')
        self.assertIn('แดชบอร์ด'.encode(), response.data)
        self.assertEqual(self.client.get('/employees/').status_code, 302)
        with self.client:
            self.client.get('/logout')
            self.login('employee')
            self.assertEqual(self.client.get('/admin/settings').status_code, 403)
            self.assertEqual(self.client.get(f'/employees/{self.employee_id}').status_code, 200)

    def test_employee_and_position_crud(self):
        self.login('admin')
        response = self.client.post('/employees/positions', data={
            'name': 'นักวิเคราะห์ข้อมูล',
            'description': 'วิเคราะห์ข้อมูลธุรกิจ',
        }, follow_redirects=True)
        self.assertIn('นักวิเคราะห์ข้อมูล'.encode(), response.data)
        with self.app.app_context():
            position_id = Position.query.filter_by(name='นักวิเคราะห์ข้อมูล').one().id

        employee_form = {
            'employee_code': 'EMP002',
            'first_name': 'New',
            'last_name': 'Member',
            'email': 'new.member@example.com',
            'phone': '0812345678',
            'department_id': str(self.department_id),
            'position': 'นักวิเคราะห์ข้อมูล',
            'hire_date': '2026-01-05',
            'work_start_time': '09:00',
            'work_end_time': '18:00',
            'status': 'Active',
            'user_id': '0',
        }
        response = self.client.post('/employees/new', data=employee_form, follow_redirects=True)
        self.assertIn('New Member'.encode(), response.data)
        with self.app.app_context():
            created = Employee.query.filter_by(employee_code='EMP002').one()
            created_id = created.id
            self.assertEqual(created.position, 'นักวิเคราะห์ข้อมูล')

        employee_form.update({'first_name': 'Updated', 'employee_code': 'EMP002'})
        response = self.client.post(f'/employees/{created_id}/edit', data=employee_form, follow_redirects=True)
        self.assertIn('Updated Member'.encode(), response.data)
        response = self.client.get('/employees/')
        self.assertIn(b'EMP002', response.data)
        response = self.client.post(f'/employees/positions/{position_id}/edit', data={
            'name': 'นักวิเคราะห์ธุรกิจ',
            'description': 'วิเคราะห์ข้อมูลเชิงธุรกิจ',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(Employee, created_id).position, 'นักวิเคราะห์ธุรกิจ')
        response = self.client.post(f'/employees/positions/{position_id}/delete', follow_redirects=True)
        self.assertIn('ลบตำแหน่งนี้ไม่ได้'.encode(), response.data)
        self.client.post(f'/employees/{created_id}/delete', follow_redirects=True)
        self.client.post(f'/employees/positions/{position_id}/delete', follow_redirects=True)
        with self.app.app_context():
            self.assertIsNone(Employee.query.filter_by(employee_code='EMP002').first())
            self.assertIsNone(db.session.get(Position, position_id))

    def test_attendance_clock_actions_and_late_calculation(self):
        arrival = datetime(2026, 10, 12, 9, 20, tzinfo=timezone(timedelta(hours=7)))
        self.assertEqual(calculate_late_minutes(arrival, '09:00', 15), 20)
        self.login('employee')
        response = self.client.get('/attendance/check-in-out')
        self.assertEqual(response.status_code, 200)
        self.client.post('/attendance/check-out', follow_redirects=True)
        with self.app.app_context():
            self.assertEqual(Attendance.query.count(), 0)
        with patch(
            'app.attendance.routes.get_bangkok_now',
            return_value=datetime(2026, 10, 12, 9, 20, tzinfo=timezone(timedelta(hours=7))),
        ), patch('app.attendance.routes.get_bangkok_today', return_value=date.today()):
            self.client.post('/attendance/check-in', follow_redirects=True)
        self.client.post('/attendance/check-in', follow_redirects=True)
        with self.app.app_context():
            record = Attendance.query.filter_by(employee_id=self.employee_id, date=date.today()).one()
            self.assertEqual(Attendance.query.filter_by(employee_id=self.employee_id, date=date.today()).count(), 1)
            self.assertEqual(record.status, 'Late')
            self.assertEqual(record.late_minutes, 20)
            self.assertIsNotNone(record.check_in)
        response = self.client.post('/attendance/check-out', follow_redirects=True)
        self.assertIn('ชั่วโมงการทำงานรวม'.encode(), response.data)
        with self.app.app_context():
            record = Attendance.query.filter_by(employee_id=self.employee_id, date=date.today()).one()
            self.assertIsNotNone(record.check_out)
            self.assertEqual(record.work_status, 'Completed')
            self.assertGreaterEqual(record.work_hours, 0)
        self.assertEqual(self.client.get('/attendance/my-history').status_code, 200)
        self.login('admin')
        self.assertEqual(self.client.get('/attendance/records').status_code, 200)
        date_filter = date.today().isoformat()
        self.assertEqual(self.client.get(f'/attendance/records?date_from={date_filter}&date_to={date_filter}').status_code, 200)
        response = self.client.get(f'/attendance/export/csv?date_from={date_filter}&date_to={date_filter}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EMP001', response.data)

    def test_leave_submission_approval_and_reports(self):
        self.login('employee')
        leave_dates = date.today() + timedelta(days=3)
        response = self.client.post('/leave/', data={
            'leave_type': 'Sick',
            'start_date': leave_dates.isoformat(),
            'end_date': (leave_dates + timedelta(days=1)).isoformat(),
            'reason': 'นัดพบแพทย์และพักฟื้น',
        }, follow_redirects=True)
        self.assertIn('ส่งคำขอลาเรียบร้อยแล้ว'.encode(), response.data)
        with self.app.app_context():
            leave_id = LeaveRequest.query.one().id
            self.assertEqual(LeaveRequest.query.one().days_count, 2)

        self.client.get('/logout')
        self.login('hr')
        self.assertEqual(self.client.get('/leave/').status_code, 200)
        filtered = self.client.get(f'/leave/?date_from={leave_dates.isoformat()}&date_to={leave_dates.isoformat()}')
        self.assertIn('นัดพบแพทย์'.encode(), filtered.data)
        response = self.client.post(f'/leave/{leave_id}/decision', data={'decision': 'Approved'}, follow_redirects=True)
        self.assertIn('อนุมัติคำขอลาแล้ว'.encode(), response.data)
        report = self.client.get(
            f'/leave/report.csv?date_from={leave_dates.isoformat()}&date_to={leave_dates.isoformat()}'
        )
        self.assertEqual(report.status_code, 200)
        self.assertIn('นัดพบแพทย์'.encode(), report.data)
        with self.app.app_context():
            leave = db.session.get(LeaveRequest, leave_id)
            balance = LeaveBalance.query.filter_by(employee_id=self.employee_id, leave_type='Sick').one()
            self.assertEqual(leave.status, 'Approved')
            self.assertEqual(balance.used_days, 2)

    def test_dashboard_settings_and_reports_render(self):
        self.login('admin')
        for path in ('/', '/admin/settings', '/admin/reports', '/attendance/records', '/employees/positions'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
        response = self.client.post('/admin/settings', data={
            'company_name': 'SmartWork',
            'grace_period_minutes': '10',
            'default_work_start': '08:30',
            'default_work_end': '17:30',
            'annual_vacation_quota': '12',
            'sick_leave_quota': '30',
            'personal_leave_quota': '6',
        }, follow_redirects=True)
        self.assertIn('บันทึกการตั้งค่าระบบแล้ว'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(SystemSetting.get_val('default_work_start'), '08:30')
            self.assertEqual(db.session.get(Employee, self.employee_id).work_start_time, '08:30')


if __name__ == '__main__':
    unittest.main()
