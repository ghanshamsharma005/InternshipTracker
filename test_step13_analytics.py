import unittest
from datetime import date, datetime, timedelta, timezone
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Evaluation
from werkzeug.security import generate_password_hash
import json

class TestStep13Analytics(unittest.TestCase):
    def setUp(self):
        """
        Creates isolated in-memory test database and environment.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-step13'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_users()

    def tearDown(self):
        """
        Closes context and drops tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_users(self):
        hashed = generate_password_hash('password123')
        
        # Admin User
        self.user_admin = User(name='Admin Officer', email='admin@test.com', password_hash=hashed, role='admin')
        db.session.add(self.user_admin)
        
        # Student Users
        self.user_s1 = User(name='Alice CSE', email='alice@test.com', password_hash=hashed, role='student')
        self.user_s2 = User(name='Bob ECE', email='bob@test.com', password_hash=hashed, role='student')
        db.session.add_all([self.user_s1, self.user_s2])
        db.session.commit()
        
        self.student1 = Student(user_id=self.user_s1.id, roll_no='CSE101', course='B.Tech CSE', semester=6)
        self.student2 = Student(user_id=self.user_s2.id, roll_no='ECE201', course='B.Tech ECE', semester=6)
        db.session.add_all([self.student1, self.student2])

        # Faculty User
        self.user_f = User(name='Dr. Professor', email='faculty@test.com', password_hash=hashed, role='faculty')
        db.session.add(self.user_f)
        db.session.commit()

        self.faculty = Faculty(user_id=self.user_f.id, department='Computer Science', employee_id='FAC101')
        db.session.add(self.faculty)

        # Companies
        self.company_google = Company(company_name='Google LLC')
        self.company_meta = Company(company_name='Meta Platforms')
        self.company_apple = Company(company_name='Apple Inc')
        db.session.add_all([self.company_google, self.company_meta, self.company_apple])
        db.session.commit()

    def login(self, email, password='password123'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_access_control_analytics_dashboard(self):
        """
        Tests role protection on /admin/dashboard.
        """
        # 1. Unauthenticated -> 302 Redirect to login
        res_guest = self.client.get('/admin/dashboard')
        self.assertEqual(res_guest.status_code, 302)
        self.assertIn('/login', res_guest.headers['Location'])

        # 2. Student -> 403 Forbidden
        self.login('alice@test.com')
        res_student = self.client.get('/admin/dashboard')
        self.assertEqual(res_student.status_code, 403)
        self.logout()

        # 3. Faculty -> 403 Forbidden
        self.login('faculty@test.com')
        res_faculty = self.client.get('/admin/dashboard')
        self.assertEqual(res_faculty.status_code, 403)
        self.logout()

        # 4. Admin -> 200 OK
        self.login('admin@test.com')
        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'Interactive Placement Analytics', res_admin.data)
        self.assertIn(b'Chart.js', res_admin.data)

    def test_empty_database_analytics(self):
        """
        Tests that 0 internships render safely without division errors.
        """
        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'0.0%', response.data)
        self.assertIn(b'statusChart', response.data)
        self.assertIn(b'completionChart', response.data)
        self.assertIn(b'monthlyChart', response.data)
        self.assertIn(b'companyChart', response.data)

    def test_status_chart_calculation(self):
        """
        Tests status breakdown calculation (Pending, Approved, Active, Completed, Rejected).
        """
        # Create 1 pending, 2 approved, 3 active, 4 completed, 1 rejected
        internships = [
            Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Dev', status='pending'),
            Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Dev', status='approved'),
            Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Dev', status='approved'),
            Internship(student_id=self.student1.id, company_id=self.company_meta.id, role='Dev', status='active'),
            Internship(student_id=self.student1.id, company_id=self.company_meta.id, role='Dev', status='active'),
            Internship(student_id=self.student1.id, company_id=self.company_meta.id, role='Dev', status='active'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Dev', status='completed'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Dev', status='completed'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Dev', status='completed'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Dev', status='completed'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Dev', status='rejected'),
        ]
        db.session.add_all(internships)
        db.session.commit()

        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        # Verify status data in serialized JSON payload: [1, 2, 3, 4, 1]
        self.assertIn('"status": {"data": [1, 2, 3, 4, 1], "labels": ["Pending", "Approved", "Active", "Completed", "Rejected"]}', html)

    def test_company_chart_and_popular_metrics(self):
        """
        Tests company placement count and top companies calculation.
        """
        # Google: 3 placements, Meta: 2 placements, Apple: 1 placement
        internships = [
            Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Backend Eng', status='active'),
            Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Frontend Eng', status='completed'),
            Internship(student_id=self.student2.id, company_id=self.company_google.id, role='DevOps Eng', status='completed'),
            Internship(student_id=self.student1.id, company_id=self.company_meta.id, role='ML Eng', status='active'),
            Internship(student_id=self.student2.id, company_id=self.company_meta.id, role='Security Eng', status='pending'),
            Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='iOS Eng', status='active'),
        ]
        db.session.add_all(internships)
        db.session.commit()

        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('Google LLC (3)', html)
        self.assertIn('Meta Platforms (2)', html)
        self.assertIn('Apple Inc (1)', html)
        # Verify company chart payload
        self.assertIn('"company": {"data": [3, 2, 1], "labels": ["Google LLC", "Meta Platforms", "Apple Inc"]}', html)

    def test_completion_rate_calculation(self):
        """
        Tests completion rate formula: (completed / total) * 100.
        """
        # 10 total internships: 3 completed, 7 non-completed -> 30.0%
        for i in range(3):
            db.session.add(Internship(student_id=self.student1.id, company_id=self.company_google.id, role=f'Role {i}', status='completed'))
        for i in range(7):
            db.session.add(Internship(student_id=self.student2.id, company_id=self.company_meta.id, role=f'Active {i}', status='active'))
        db.session.commit()

        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('30.0%', html)
        self.assertIn('"completion": {"data": [3, 7], "labels": ["Completed", "Not Completed"]}', html)

    def test_monthly_registration_chart(self):
        """
        Tests grouping of internship registrations by month.
        """
        dt_jan = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        dt_feb = datetime(2026, 2, 20, 11, 0, 0, tzinfo=timezone.utc)
        dt_mar = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)

        i1 = Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Role 1', status='active', created_at=dt_jan)
        i2 = Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Role 2', status='active', created_at=dt_jan)
        i3 = Internship(student_id=self.student2.id, company_id=self.company_meta.id, role='Role 3', status='active', created_at=dt_feb)
        i4 = Internship(student_id=self.student2.id, company_id=self.company_apple.id, role='Role 4', status='completed', created_at=dt_mar)
        db.session.add_all([i1, i2, i3, i4])
        db.session.commit()

        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('"monthly": {"data": [2, 1, 1], "labels": ["Jan 2026", "Feb 2026", "Mar 2026"]}', html)

    def test_additional_useful_metrics(self):
        """
        Tests average duration and average evaluation score calculations.
        """
        # Duration test: Internship 1 (30 days), Internship 2 (60 days) -> Avg = 45.0 days (~6.4 weeks)
        start1 = date(2026, 1, 1)
        end1 = date(2026, 1, 31)  # 30 days
        start2 = date(2026, 2, 1)
        end2 = date(2026, 4, 2)   # 60 days

        i1 = Internship(student_id=self.student1.id, company_id=self.company_google.id, role='Role 1', status='completed', start_date=start1, end_date=end1)
        i2 = Internship(student_id=self.student2.id, company_id=self.company_meta.id, role='Role 2', status='completed', start_date=start2, end_date=end2)
        db.session.add_all([i1, i2])
        db.session.commit()

        # Evaluation test: Overall score 8.0 and 9.4 -> Avg = 8.7
        eval1 = Evaluation(
            internship_id=i1.id,
            student_id=self.student1.id,
            faculty_id=self.faculty.id,
            technical_skills=8,
            communication=8,
            punctuality=8,
            work_quality=8,
            discipline=8,
            overall_score=8.0
        )
        eval2 = Evaluation(
            internship_id=i2.id,
            student_id=self.student2.id,
            faculty_id=self.faculty.id,
            technical_skills=9,
            communication=10,
            punctuality=10,
            work_quality=9,
            discipline=9,
            overall_score=9.4
        )
        db.session.add_all([eval1, eval2])
        db.session.commit()

        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)

        html = response.get_data(as_text=True)
        self.assertIn('45.0', html) # Average days
        self.assertIn('~6.4 wks', html) # Average weeks
        self.assertIn('8.7', html) # Average evaluation score (8.70)

    def test_course_filter_analytics(self):
        """
        Tests that selecting a course filter filters internships, charts, and metrics accordingly.
        """
        # Student 1 is 'B.Tech CSE', Student 2 is 'B.Tech ECE'
        i_cse = Internship(student_id=self.student1.id, company_id=self.company_google.id, role='CSE Intern', status='completed')
        i_ece = Internship(student_id=self.student2.id, company_id=self.company_meta.id, role='ECE Intern', status='active')
        db.session.add_all([i_cse, i_ece])
        db.session.commit()

        self.login('admin@test.com')
        
        # 1. Filter B.Tech CSE -> only 1 placement (completed), 100% completion rate
        res_cse = self.client.get('/admin/dashboard?course=B.Tech+CSE')
        self.assertEqual(res_cse.status_code, 200)
        html_cse = res_cse.get_data(as_text=True)
        self.assertIn('100.0%', html_cse)
        self.assertIn('"company": {"data": [1], "labels": ["Google LLC"]}', html_cse)

        # 2. Filter B.Tech ECE -> only 1 placement (active), 0.0% completion rate
        res_ece = self.client.get('/admin/dashboard?course=B.Tech+ECE')
        self.assertEqual(res_ece.status_code, 200)
        html_ece = res_ece.get_data(as_text=True)
        self.assertIn('0.0%', html_ece)
        self.assertIn('"company": {"data": [1], "labels": ["Meta Platforms"]}', html_ece)

if __name__ == '__main__':
    unittest.main()
