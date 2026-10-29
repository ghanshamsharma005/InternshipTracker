import unittest
import os
from datetime import date, timedelta
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Document, ProgressReport
from werkzeug.security import generate_password_hash

class TestFacultyModule(unittest.TestCase):
    def setUp(self):
        """
        Setup database tables and mock roles.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-2026'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_data()

    def tearDown(self):
        """
        Clean up resources.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_data(self):
        hashed = generate_password_hash('password123')
        
        # Student A
        self.user_s1 = User(name='Student Alpha', email='studenta@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_s1)
        db.session.commit()
        self.student_a = Student(user_id=self.user_s1.id, roll_no='ROLL_A', course='CS', semester=6)
        db.session.add(self.student_a)
        db.session.commit()
        
        # Student B
        self.user_s2 = User(name='Student Beta', email='studentb@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_s2)
        db.session.commit()
        self.student_b = Student(user_id=self.user_s2.id, roll_no='ROLL_B', course='CS', semester=6)
        db.session.add(self.student_b)
        db.session.commit()

        # Faculty User
        self.user_f = User(name='Faculty Advisor', email='faculty@test.com', password_hash=hashed, role='faculty')
        db.session.add(self.user_f)
        db.session.commit()
        self.faculty = Faculty(user_id=self.user_f.id, department='Computer Science', employee_id='EMP001')
        db.session.add(self.faculty)
        db.session.commit()
        
        # Company
        self.company = Company(company_name='Nexus Corp')
        db.session.add(self.company)
        db.session.commit()
        
        # Internship for Student Alpha (Pending)
        self.internship_a = Internship(
            student_id=self.student_a.id,
            company_id=self.company.id,
            role='Frontend Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='pending'
        )
        db.session.add(self.internship_a)
        db.session.commit()

        # Internship for Student Beta (Active)
        self.internship_b = Internship(
            student_id=self.student_b.id,
            company_id=self.company.id,
            role='Backend Developer',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='active'
        )
        db.session.add(self.internship_b)
        db.session.commit()
        
    def login(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def test_faculty_role_access_authorization(self):
        """
        Verify that student accounts cannot access faculty pages,
        and faculty accounts cannot access admin pages.
        """
        # 1. Student attempts to access faculty dashboard -> 403 Forbidden
        self.login('studenta@test.com')
        response = self.client.get('/faculty/dashboard')
        self.assertEqual(response.status_code, 403)
        
        # 2. Faculty attempts to access admin dashboard -> 403 Forbidden
        self.login('faculty@test.com')
        response_admin = self.client.get('/admin/dashboard')
        self.assertEqual(response_admin.status_code, 403)

    def test_faculty_dashboard_stats(self):
        """
        Verify dashboard displays dynamic stats counts from DB.
        """
        self.login('faculty@test.com')
        response = self.client.get('/faculty/dashboard')
        self.assertEqual(response.status_code, 200)
        
        # Student Alpha (Pending), Student Beta (Active)
        # Total Students = 2
        # Pending Approvals = 1
        # Active Placements = 1
        self.assertIn(b'2', response.data)  # Total students counter
        self.assertIn(b'Pending Approvals (1)', response.data)

    def test_student_search_and_filter(self):
        """
        Verify search query filtering on faculty students page.
        """
        self.login('faculty@test.com')
        
        # Search for "Alpha" -> returns Student Alpha
        response = self.client.get('/faculty/students?search=Alpha')
        self.assertIn(b'Student Alpha', response.data)
        self.assertNotIn(b'Student Beta', response.data)
        
        # Filter by status "active" -> returns Student Beta
        response_filter = self.client.get('/faculty/students?status=active')
        self.assertIn(b'Student Beta', response_filter.data)
        self.assertNotIn(b'Student Alpha', response_filter.data)

    def test_placement_approvals_and_rejections(self):
        """
        Verify that faculty can approve or reject pending placements.
        """
        self.login('faculty@test.com')
        
        # Approve placement for Student Alpha
        response_app = self.client.post(f'/faculty/internship/approve/{self.internship_a.id}', follow_redirects=True)
        db.session.refresh(self.internship_a)
        self.assertEqual(self.internship_a.status, 'approved')
        
        # Reset to pending for rejection test
        self.internship_a.status = 'pending'
        db.session.commit()
        
        # Reject placement
        response_rej = self.client.post(f'/faculty/internship/reject/{self.internship_a.id}', follow_redirects=True)
        db.session.refresh(self.internship_a)
        self.assertEqual(self.internship_a.status, 'rejected')

    def test_verify_reject_documents(self):
        """
        Verify faculty can review documents.
        """
        # Seed document for Student Beta
        doc = Document(
            internship_id=self.internship_b.id,
            student_id=self.student_b.id,
            document_type='ID Proof',
            file_path='test_id.png',
            status='pending'
        )
        db.session.add(doc)
        db.session.commit()
        
        self.login('faculty@test.com')
        
        # Verify document
        response_v = self.client.post(f'/faculty/document/verify/{doc.id}', follow_redirects=True)
        db.session.refresh(doc)
        self.assertEqual(doc.status, 'verified')
        
        # Reset and Reject document
        doc.status = 'pending'
        db.session.commit()
        response_r = self.client.post(f'/faculty/document/reject/{doc.id}', follow_redirects=True)
        db.session.refresh(doc)
        self.assertEqual(doc.status, 'rejected')

    def test_progress_logs_comments_feedback(self):
        """
        Verify faculty can post feedback remarks on progress logs.
        """
        # Seed progress log for Student Beta
        log = ProgressReport(
            internship_id=self.internship_b.id,
            student_id=self.student_b.id,
            week_number=1,
            tasks_completed='Backend APIs set up',
            hours_worked=35.0,
            status='submitted'
        )
        db.session.add(log)
        db.session.commit()
        
        self.login('faculty@test.com')
        
        # Post feedback
        data = {'feedback': 'Excellent progress on databases.'}
        response = self.client.post(f'/faculty/progress/comment/{log.id}', data=data, follow_redirects=True)
        
        # Check database
        db.session.refresh(log)
        self.assertEqual(log.feedback, 'Excellent progress on databases.')
        self.assertEqual(log.status, 'approved')

if __name__ == '__main__':
    unittest.main()
