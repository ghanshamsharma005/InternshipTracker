import unittest
from datetime import date
from app import create_app
from database.db import db
from models import User, Student, Company, Internship
from werkzeug.security import generate_password_hash

class TestInternshipRegistrationLayer(unittest.TestCase):
    def setUp(self):
        """
        Creates isolated in-memory test environment.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-2026'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_users()

    def tearDown(self):
        """
        Closes context and drops in-memory tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_users(self):
        """
        Creates Student A and Student B test profile nodes.
        """
        hashed = generate_password_hash('password123')
        
        # Student A node
        self.user_a = User(name='Student A', email='studenta@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_a)
        db.session.commit()
        self.student_a = Student(user_id=self.user_a.id, roll_no='ROLLA', course='CS', semester=4)
        db.session.add(self.student_a)
        db.session.commit()

        # Student B node
        self.user_b = User(name='Student B', email='studentb@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_b)
        db.session.commit()
        self.student_b = Student(user_id=self.user_b.id, roll_no='ROLLB', course='IT', semester=6)
        db.session.add(self.student_b)
        db.session.commit()

    def login_student(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def logout_student(self):
        self.client.get('/logout')

    def test_dashboard_no_internship(self):
        """
        Verifies dashboard prompts empty registration call-to-actions.
        """
        self.login_student('studenta@test.com')
        
        response = self.client.get('/student/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No Internship Registered', response.data)
        self.assertIn(b'Register Internship', response.data)

    def test_create_internship_success(self):
        """
        Tests successful registration inserts data and updates the dashboard view.
        """
        self.login_student('studenta@test.com')
        
        response = self.client.post('/student/internship', data={
            'company': 'Awesome Tech Inc',
            'company_address': 'Silicon Valley',
            'company_contact': 'HR Recruiter',
            'role': 'QA Intern',
            'description': 'Automating scripts',
            'start_date': '2026-09-01',
            'end_date': '2026-12-01',
            'internship_type': 'online',
            'supervisor_name': 'Sarah Jenkins',
            'supervisor_email': 'sarah@awesome.com',
            'supervisor_phone': '1234567890'
        }, follow_redirects=True)
        
        # Verify database record
        internship = Internship.query.filter_by(student_id=self.student_a.id).first()
        self.assertIsNotNone(internship)
        self.assertEqual(internship.role, 'QA Intern')
        self.assertEqual(internship.status, 'pending')
        self.assertEqual(internship.company.company_name, 'Awesome Tech Inc')
        
        # Verify dashboard update
        self.assertIn(b'Internship submitted successfully. Waiting for approval.', response.data)
        self.assertIn(b'Awesome Tech Inc', response.data)
        self.assertIn(b'QA Intern', response.data)
        self.assertNotIn(b'Register Internship', response.data)

    def test_create_internship_missing_fields(self):
        """
        Verifies missing required fields blocks form submissions.
        """
        self.login_student('studenta@test.com')
        
        response = self.client.post('/student/internship', data={
            'company': 'Awesome Tech Inc',
            'role': '',  # Missing field
            'start_date': '2026-09-01',
            'end_date': '2026-12-01',
            'internship_type': 'online',
            'supervisor_name': 'Sarah Jenkins',
            'supervisor_email': 'sarah@awesome.com'
        })
        self.assertIn(b'Please fill in all required fields.', response.data)

    def test_create_internship_invalid_dates(self):
        """
        Checks date checks fail when end date precedes start date.
        """
        self.login_student('studenta@test.com')
        
        response = self.client.post('/student/internship', data={
            'company': 'Awesome Tech Inc',
            'role': 'QA Intern',
            'start_date': '2026-12-01',
            'end_date': '2026-09-01',  # Invalid end date
            'internship_type': 'online',
            'supervisor_name': 'Sarah Jenkins',
            'supervisor_email': 'sarah@awesome.com'
        })
        self.assertIn(b'End date must be after start date.', response.data)

    def test_create_internship_duplicate_block(self):
        """
        Checks that double-internship registrations are rejected.
        """
        self.login_student('studenta@test.com')
        
        # Pre-seed an internship
        company = Company(company_name='First Co')
        db.session.add(company)
        db.session.commit()
        
        internship = Internship(
            student_id=self.student_a.id,
            company_id=company.id,
            role='Role A',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            status='pending'
        )
        db.session.add(internship)
        db.session.commit()
        
        # Request registration for a second internship
        response = self.client.post('/student/internship', data={
            'company': 'Second Co',
            'role': 'Role B',
            'start_date': '2026-09-01',
            'end_date': '2026-12-01',
            'internship_type': 'online',
            'supervisor_name': 'Sarah Jenkins',
            'supervisor_email': 'sarah@awesome.com'
        }, follow_redirects=True)
        
        self.assertIn(b'You have already registered an internship.', response.data)
        
        # Verify no secondary record exists in db
        count = Internship.query.filter_by(student_id=self.student_a.id).count()
        self.assertEqual(count, 1)

    def test_view_details_ownership_check(self):
        """
        Verifies that Student A cannot access Student B's details and triggers 403.
        """
        # Register internship for Student A
        company = Company(company_name='Company A')
        db.session.add(company)
        db.session.commit()
        internship_a = Internship(
            student_id=self.student_a.id,
            company_id=company.id,
            role='Role A',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 1),
            status='pending'
        )
        db.session.add(internship_a)
        db.session.commit()

        # Log in Student B
        self.login_student('studentb@test.com')
        
        # Student B hits Student A's endpoint -> 403 Access Denied
        response = self.client.get(f'/student/internship/{internship_a.id}/details')
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'403 - Access Denied', response.data)

        # Log in Student A
        self.logout_student()
        self.login_student('studenta@test.com')
        
        # Student A hits own details -> 200 Ok
        response_ok = self.client.get(f'/student/internship/{internship_a.id}/details')
        self.assertEqual(response_ok.status_code, 200)
        self.assertIn(b'Company A', response_ok.data)
        self.assertIn(b'Role A', response_ok.data)

if __name__ == '__main__':
    unittest.main()
