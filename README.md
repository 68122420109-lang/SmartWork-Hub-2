# SmartWork Hub

SmartWork-Hub เป็นเว็บไซต์จัดการข้อมูลการทำงานแบบ CRUD Full-Stack สำหรับแผนกหรือทีมงาน โดยมี Frontend และ Admin Dashboard แยกกันชัดเจน และใช้ Python Flask + MySQL ในการจัดการข้อมูลจริง

## ฟีเจอร์หลัก

- เว็บ Frontend สำหรับแสดงข้อมูลและรายการงาน
- ระบบสมาชิกและ Login / Register
- Role-based access control: admin, HR/manager และพนักงาน
- CRUD สำหรับงาน (Task)
- ค้นหา/กรองข้อมูลตามหมวดหมู่และสถานะ
- Pagination
- CRUD ข้อมูลพนักงานและตำแหน่งงาน
- ลงเวลาเข้า-ออก คำนวณการมาสาย และประวัติการทำงาน
- ยื่น/พิจารณาคำขอลา พร้อมประวัติและรายงาน CSV
- แดชบอร์ด HR และรายงานจากฐานข้อมูลจริง
- ตั้งค่าเวลาเริ่มงานและนโยบายวันลา
- Responsive Thai UI สำหรับ Desktop และ Mobile
- ระบบแจ้งเตือนแบบ Flash Message
- Error handling 403 / 404 / 500

## โครงสร้างโปรเจกต์

```text
smartwork-hub/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── forms.py
│   ├── models.py
│   ├── admin/
│   │   └── routes.py
│   ├── auth/
│   │   └── routes.py
│   ├── main/
│   │   └── routes.py
│   ├── tasks/
│   │   └── routes.py
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
│       ├── auth/
│       ├── admin/
│       ├── tasks/
│       ├── errors/
│       ├── base.html
│       ├── home.html
│       └── profile.html
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
├── README.md
└── migrations/
```

## การตั้งค่า MySQL

1. สร้างฐานข้อมูล `general`

```sql
CREATE DATABASE general CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. สร้าง user สำหรับแอปพลิเคชัน (หรือใช้ root สำหรับการทดสอบ แต่ไม่แนะนำในระบบจริง)

```sql
CREATE USER 'smartwork_user'@'localhost' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON general.* TO 'smartwork_user'@'localhost';
FLUSH PRIVILEGES;
```

## การตั้งค่า Environment Variables

คัดลอกไฟล์ `.env.example` เป็น `.env` แล้วปรับค่าให้ถูกต้อง

```bash
copy .env.example .env
```

ตัวอย่างค่าใน `.env`

```env
SECRET_KEY=change-this-to-a-random-secret-key
DB_HOST=localhost
DB_PORT=3306
DB_NAME=general
DB_USER=smartwork_user
DB_PASSWORD=your_strong_password
```

## การติดตั้ง Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## อัปเดตฐานข้อมูลด้วย Migration

กำหนดค่าการเชื่อมต่อฐานข้อมูลใน `.env` หรือ `DATABASE_URL` ก่อนอัปเกรด โครงการมี migration สำหรับ schema ปัจจุบันอยู่แล้ว และ migration เพิ่มเติมจะสร้างตาราง HR โดยไม่ลบข้อมูลเดิม

```powershell
flask --app run.py db upgrade
```

ไม่ต้องเรียก `flask db init` หรือสร้าง migration ใหม่สำหรับการติดตั้งปกติ

หากระบบไม่ผูกกับ MySQL หรือฐานข้อมูลไม่พร้อม ให้ตรวจสอบค่า DB_HOST, DB_PORT, DB_USER, DB_PASSWORD และตรวจว่า MySQL Server กำลังทำงานอยู่

## การสร้างบัญชี Admin อย่างปลอดภัย

```bash
flask --app run.py create-admin --username admin --email admin@example.com --password your_secure_password --full-name "System Administrator"
```

คำสั่งนี้จะสร้างผู้ใช้งานที่มี role เป็น admin โดยไม่ต้องปล่อยรหัสผ่านไว้ใน source code

## การรันเว็บไซต์

```bash
python run.py
```

หรือรันตรงผ่านไฟล์ `run.py`

```bash
python run.py
```

เว็บไซต์จะอยู่ที่:

- http://127.0.0.1:5000/

## หมายเหตุสำคัญ

- โค้ดนี้ออกแบบให้เชื่อมต่อ MySQL จริงตาม DB_NAME=general เท่านั้น
- ไม่ใช้ SQLite หรือ LocalStorage เป็นฐานข้อมูลหลัก
- รหัสผ่านจะถูกเข้ารหัสด้วย Werkzeug Security ก่อนบันทึกลงฐานข้อมูล
- การตรวจสอบสิทธิ์ Route ทั้งหมดทำจากฝั่ง Backend เพื่อความปลอดภัย

## การ Deploy บนเซิร์ฟเวอร์ภายนอก

- ใช้ Python runtime ที่รองรับ Flask
- ตั้งค่า Environment Variables ตาม `.env`
- ตั้งค่า MySQL external host/port ให้ถูกต้อง
- ใช้ WSGI server เช่น Gunicorn หรือ uWSGI ใน Production

ตัวอย่าง:

```bash
gunicorn --bind 0.0.0.0:8000 run:app
```

## การทดสอบระบบ

```powershell
python -m unittest discover -s tests -v
```

หน้าที่แนะนำให้ทดสอบหลังเข้าสู่ระบบ:

- `/` แดชบอร์ด
- `/employees/` รายชื่อและค้นหาพนักงาน (Admin/HR)
- `/employees/new` เพิ่มพนักงาน (Admin/HR)
- `/employees/positions` จัดการตำแหน่ง (Admin/HR)
- `/attendance/check-in-out` ลงเวลาเข้า-ออก
- `/attendance/my-history` ประวัติลงเวลาของฉัน
- `/attendance/records` รายงานเวลาและส่งออก CSV (Admin/HR)
- `/leave/` ยื่นคำขอ/อนุมัติคำขอลา
- `/admin/reports` ภาพรวมรายงาน (Admin/HR)
- `/admin/settings` ตั้งค่าเวลาทำงานและนโยบายลา (Admin/HR)
- `/login` และ `/register` เข้าสู่ระบบ/สมัครสมาชิก

การลงเวลาและยื่นลาต้องเชื่อมบัญชีผู้ใช้กับข้อมูลพนักงานจากหน้าแก้ไข/สร้างพนักงานก่อน
