import io
import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import numpy as np

from app import create_app
from app.extensions import db
from app.models import (
    Attendance,
    Department,
    Employee,
    FaceEnrollment,
    LeaveBalance,
    LeaveRequest,
    Position,
    SystemSetting,
    Task,
    User,
)
import app.face_service as fs


class SmartWorkFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(test_config={
            'SQLALCHEMY_DATABASE_URI': 'sqlite://',
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'LOGIN_DISABLED': False,
            'SECRET_KEY': 'test-secret-key-smartwork',
        })
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.drop_all()
            db.session.remove()

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            for model in (Attendance, FaceEnrollment, LeaveRequest, LeaveBalance, Task, Employee, Position, Department, SystemSetting, User):
                db.session.query(model).delete()
            db.session.commit()

            # Department & Position
            dept = Department(code='DEV', name='ฝ่ายพัฒนา')
            pos = Position(name='วิศวกรซอฟต์แวร์')
            db.session.add_all([dept, pos])

            # Settings
            db.session.add_all([
                SystemSetting(key='default_work_start', value='09:00'),
                SystemSetting(key='default_work_end', value='18:00'),
                SystemSetting(key='grace_period_minutes', value='15'),
            ])

            # Users: Admin, Employee 1, Employee 2
            admin = User(username='admin', email='admin@test.com', full_name='ผู้ดูแล ระบบ', role='admin')
            admin.set_password('pass123')

            user1 = User(username='emp1', email='emp1@test.com', full_name='สมชาย ใจดี', role='user')
            user1.set_password('pass123')

            user2 = User(username='emp2', email='emp2@test.com', full_name='สมหญิง รักงาน', role='user')
            user2.set_password('pass123')

            db.session.add_all([admin, user1, user2])
            db.session.flush()

            # Employees
            self.employee1 = Employee(
                employee_code='EMP001',
                first_name='สมชาย',
                last_name='ใจดี',
                email='emp1.work@test.com',
                department_id=dept.id,
                position=pos.name,
                hire_date=date.today(),
                user_id=user1.id,
                status='Active',
                work_start_time='09:00',
                work_end_time='18:00',
            )
            self.employee2 = Employee(
                employee_code='EMP002',
                first_name='สมหญิง',
                last_name='รักงาน',
                email='emp2.work@test.com',
                department_id=dept.id,
                position=pos.name,
                hire_date=date.today(),
                user_id=user2.id,
                status='Active',
                work_start_time='09:00',
                work_end_time='18:00',
            )
            db.session.add_all([self.employee1, self.employee2])
            db.session.flush()

            # Tasks
            self.task1 = Task(
                title='งานของสมชาย',
                description='รายละเอียดงานสมชาย',
                category='พัฒนา',
                assignee='สมชาย',
                status='Pending',
                user_id=user1.id,
            )
            self.task2 = Task(
                title='งานของสมหญิง',
                description='รายละเอียดงานสมหญิง',
                category='ทดสอบ',
                assignee='สมหญิง',
                status='Pending',
                user_id=user2.id,
            )
            db.session.add_all([self.task1, self.task2])
            db.session.commit()

            self.admin_id = admin.id
            self.user1_id = user1.id
            self.user2_id = user2.id
            self.emp1_id = self.employee1.id
            self.emp2_id = self.employee2.id
            self.task1_id = self.task1.id
            self.task2_id = self.task2.id

    def login(self, username, password='pass123'):
        return self.client.post('/login', data={'identifier': username, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_data_isolation_between_employees(self):
        """Test B.1: Employees cannot access each other's private data via URL or request."""
        # 1. Login as emp1
        self.login('emp1')

        # emp1 viewing emp1's own profile: OK (200)
        res = self.client.get(f'/employees/{self.emp1_id}')
        self.assertEqual(res.status_code, 200)

        # emp1 attempting to view emp2's employee detail: 403 Forbidden!
        res = self.client.get(f'/employees/{self.emp2_id}')
        self.assertEqual(res.status_code, 403)

        # emp1 viewing emp1's own task: OK (200)
        res = self.client.get(f'/tasks/{self.task1_id}')
        self.assertEqual(res.status_code, 200)

        # emp1 attempting to view emp2's task detail: 403 Forbidden!
        res = self.client.get(f'/tasks/{self.task2_id}')
        self.assertEqual(res.status_code, 403)

        # emp1 attempting to edit emp2's task: 403 Forbidden!
        res = self.client.get(f'/tasks/{self.task2_id}/edit')
        self.assertEqual(res.status_code, 403)

        # emp1 attempting to delete emp2's task: 403 Forbidden!
        res = self.client.post(f'/tasks/{self.task2_id}/delete')
        self.assertEqual(res.status_code, 403)

        self.logout()

        # 2. Login as Admin: can view both
        self.login('admin')
        res = self.client.get(f'/employees/{self.emp1_id}')
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f'/employees/{self.emp2_id}')
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f'/tasks/{self.task1_id}')
        self.assertEqual(res.status_code, 200)
        res = self.client.get(f'/tasks/{self.task2_id}')
        self.assertEqual(res.status_code, 200)

    def test_profile_update_and_avatar(self):
        """Test B.2: Profile editing and avatar upload/removal."""
        self.login('emp1')

        # 1. Update personal details
        res = self.client.post('/profile', data={
            'full_name': 'สมชาย ใจดีพัฒนา',
            'phone': '0891234567'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            user = db.session.get(User, self.user1_id)
            self.assertEqual(user.full_name, 'สมชาย ใจดีพัฒนา')
            emp = db.session.get(Employee, self.emp1_id)
            self.assertEqual(emp.phone, '0891234567')

        # 2. Upload avatar
        img_byte_arr = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        res = self.client.post('/profile', data={
            'full_name': 'สมชาย ใจดีพัฒนา',
            'phone': '0891234567',
            'avatar': (img_byte_arr, 'test_avatar.jpg')
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            emp = db.session.get(Employee, self.emp1_id)
            self.assertIsNotNone(emp.avatar_url)
            self.assertTrue(emp.avatar_url.startswith('uploads/avatars/'))

        # 3. Remove avatar
        res = self.client.post('/profile', data={'action': 'remove_avatar'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            emp = db.session.get(Employee, self.emp1_id)
            self.assertIsNone(emp.avatar_url)

    def test_leave_attachment_and_authorization(self):
        """Test B.5: Leave request with attachment file and strict access control."""
        self.login('emp1')

        # Create dummy PDF file
        pdf_bytes = b"%PDF-1.4 dummy pdf document content"
        pdf_file = (io.BytesIO(pdf_bytes), 'doctor_certificate.pdf')

        res = self.client.post('/leave/', data={
            'leave_type': 'Sick',
            'start_date': (date.today() + timedelta(days=5)).isoformat(),
            'end_date': (date.today() + timedelta(days=6)).isoformat(),
            'reason': 'มีอาการป่วยเป็นไข้หวัดใหญ่',
            'attachment': pdf_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            leave = LeaveRequest.query.filter_by(employee_id=self.emp1_id).first()
            self.assertIsNotNone(leave)
            self.assertIsNotNone(leave.attachment_url)
            leave_id = leave.id

        # emp1 can view own leave attachment: OK (200)
        res = self.client.get(f'/leave/attachment/{leave_id}')
        self.assertEqual(res.status_code, 200)

        self.logout()

        # emp2 attempts to view emp1's attachment: 403 Forbidden!
        self.login('emp2')
        res = self.client.get(f'/leave/attachment/{leave_id}')
        self.assertEqual(res.status_code, 403)

        self.logout()

        # admin can view attachment: OK (200)
        self.login('admin')
        res = self.client.get(f'/leave/attachment/{leave_id}')
        self.assertEqual(res.status_code, 200)

    def test_face_biometric_enrollment_and_consent(self):
        """Test B.3: Face enrollment requires PDPA consent and validates image."""
        self.login('emp1')

        # 1. Attempt enrollment without consent -> 400
        res = self.client.post('/attendance/face-enroll', json={
            'image_data': 'dummy-base64',
            'consent': False
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn('PDPA', data['error'])

        # 2. Attempt enrollment with invalid image data -> 400
        res = self.client.post('/attendance/face-enroll', json={
            'image_data': 'not-a-valid-image',
            'consent': True
        })
        self.assertEqual(res.status_code, 400)

        # 3. Successful enrollment with mock face detection
        fake_bgr = np.zeros((150, 150, 3), dtype=np.uint8)
        fake_crop = np.zeros((128, 128), dtype=np.uint8)
        fake_feat = np.ones((384,), dtype=np.float32)

        with patch('app.attendance.routes.decode_base64_image', return_value=(True, "OK", fake_bgr)), \
             patch('app.attendance.routes.detect_face_in_image', return_value=(True, "OK", (10, 10, 100, 100))), \
             patch('app.attendance.routes.extract_face_features', return_value=(fake_crop, fake_feat)):
            res = self.client.post('/attendance/face-enroll', json={
                'image_data': 'data:image/jpeg;base64,mock',
                'consent': True
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])

        with self.app.app_context():
            enroll = FaceEnrollment.query.filter_by(user_id=self.user1_id).first()
            self.assertIsNotNone(enroll)
            self.assertTrue(enroll.consent_given)
            self.assertIsNotNone(enroll.consent_at)

        # 4. Revoke consent & delete face data
        res = self.client.post('/attendance/face-delete', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            enroll = FaceEnrollment.query.filter_by(user_id=self.user1_id).first()
            self.assertIsNone(enroll)

    def test_face_attendance_verification_and_rules(self):
        """Test B.3 & B.4: Anti-replay challenge, server face verification, duplicate prevention, and checkout rules."""
        self.login('emp1')

        # 1. Attempt check-in without face enrollment -> Rejected (need_enroll: True)
        res = self.client.post('/attendance/verify-check-in', json={
            'image_data': 'mock',
            'challenge_token': 'mock'
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertTrue(data.get('need_enroll'))

        # Now enroll mock face
        with self.app.app_context():
            enroll = FaceEnrollment(
                user_id=self.user1_id,
                employee_id=self.emp1_id,
                consent_given=True,
                consent_at=datetime.utcnow(),
                reference_photo='uploads/face_records/test_ref.jpg',
                is_active=True
            )
            db.session.add(enroll)
            db.session.commit()

        # 2. Get active challenge
        res = self.client.get('/attendance/challenge')
        self.assertEqual(res.status_code, 200)
        challenge_data = res.get_json()
        token = challenge_data['challenge_token']

        # 3. Test invalid challenge token -> 400
        res = self.client.post('/attendance/verify-check-in', json={
            'image_data': 'mock',
            'challenge_token': 'fake:token:invalid:sig'
        })
        self.assertEqual(res.status_code, 400)

        # 4. Test Face mismatch -> 400
        fake_bgr = np.zeros((150, 150, 3), dtype=np.uint8)
        fake_crop = np.zeros((128, 128), dtype=np.uint8)
        fake_feat = np.ones((384,), dtype=np.float32)

        with patch('app.attendance.routes.verify_liveness_challenge', return_value=(True, "OK", "blink")), \
             patch('app.attendance.routes.decode_base64_image', return_value=(True, "OK", fake_bgr)), \
             patch('app.attendance.routes.detect_face_in_image', return_value=(True, "OK", (10, 10, 100, 100))), \
             patch('app.attendance.routes.extract_face_features', return_value=(fake_crop, fake_feat)), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('cv2.imread', return_value=fake_bgr), \
             patch('app.attendance.routes.compare_faces', return_value=(False, 0.45, "ใบหน้าไม่ตรงกับข้อมูลที่ลงทะเบียน")):
            res = self.client.post('/attendance/verify-check-in', json={
                'image_data': 'mock',
                'challenge_token': token
            })
            self.assertEqual(res.status_code, 400)
            data = res.get_json()
            self.assertFalse(data['success'])
            self.assertIn('ใบหน้าไม่ตรง', data['error'])

        # 5. Successful face verification & check-in
        with patch('app.attendance.routes.verify_liveness_challenge', return_value=(True, "OK", "blink")), \
             patch('app.attendance.routes.decode_base64_image', return_value=(True, "OK", fake_bgr)), \
             patch('app.attendance.routes.detect_face_in_image', return_value=(True, "OK", (10, 10, 100, 100))), \
             patch('app.attendance.routes.extract_face_features', return_value=(fake_crop, fake_feat)), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('cv2.imread', return_value=fake_bgr), \
             patch('app.attendance.routes.compare_faces', return_value=(True, 0.88, "ยืนยันตัวตนสำเร็จ")):
            res = self.client.post('/attendance/verify-check-in', json={
                'image_data': 'mock',
                'challenge_token': token
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])

        with self.app.app_context():
            today = date.today()
            att = Attendance.query.filter_by(employee_id=self.emp1_id, date=today).first()
            self.assertIsNotNone(att)
            self.assertIsNotNone(att.check_in)
            self.assertEqual(att.work_status, 'Working')

        # 6. Duplicate check-in prevention -> 400
        res = self.client.post('/attendance/verify-check-in', json={
            'image_data': 'mock',
            'challenge_token': token
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('ลงเวลาเข้างานของวันนี้ไปเรียบร้อยแล้ว', res.get_json()['error'])

        # 7. Check-out
        res = self.client.post('/attendance/check-out', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            today = date.today()
            att = Attendance.query.filter_by(employee_id=self.emp1_id, date=today).first()
            self.assertIsNotNone(att.check_out)
            self.assertEqual(att.work_status, 'Completed')

        # 8. Duplicate check-out prevention
        res = self.client.post('/attendance/check-out', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn('คุณได้ลงเวลาออกงานของวันนี้ไปเรียบร้อยแล้ว'.encode('utf-8'), res.data)


if __name__ == '__main__':
    unittest.main()
