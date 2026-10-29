import unittest
from datetime import date, datetime, timedelta
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Document, ProgressReport, TimelineEvent, Deadline
from werkzeug.security import generate_password_hash

class TestAdminModule(unittest.TestCase):
    def setUp(self):
        """
        Creates isolated in-memory test database and environment.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-admin'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_users_and_data()

    def tearDown(self):
        """
        Closes context and drops tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_users_and_data(self):
        hashed = generate_password_hash('password123')
        
        # Admin User
        self.user_admin = User(name='System Administrator', email='admin@test.com', password_hash=hashed, role='admin')
        db.session.add(self.user_admin)
        db.session.commit()
        
        # Student User & Profile
        self.user_s = User(name='Bob Student', email='bob@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_s)
        db.session.commit()
        self.student = Student(user_id=self.user_s.id, roll_no='CS201', course='CS', semester=5)
        db.session.add(self.student)
        db.session.commit()

        # Faculty User & Profile
        self.user_f = User(name='Alice Advisor', email='alice@test.com', password_hash=hashed, role='faculty')
        db.session.add(self.user_f)
        db.session.commit()
        self.faculty = Faculty(user_id=self.user_f.id, department='Computer Science', employee_id='FAC888')
        db.session.add(self.faculty)
        db.session.commit()

        # Company
        self.company = Company(company_name='Alphabet Inc', address='Silicon Valley', contact_person='HR Larry')
        db.session.add(self.company)
        db.session.commit()

        # Internship (Pending)
        self.internship = Internship(
            student_id=self.student.id,
            company_id=self.company.id,
            role='Software Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='pending'
        )
        db.session.add(self.internship)
        db.session.commit()

    def login(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def logout(self):
        self.client.get('/logout')

    def test_unauthorized_access_to_admin_routes(self):
        """
        Verify student and faculty roles are blocked from admin routes.
        """
        # 1. Student access blocked
        self.login('bob@test.com')
        for route in ['/admin/dashboard', '/admin/students', '/admin/internships', '/admin/companies']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 403)
        self.logout()

        # 2. Faculty access blocked
        self.login('alice@test.com')
        for route in ['/admin/dashboard', '/admin/students', '/admin/internships', '/admin/companies']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 403)
        self.logout()

    def test_admin_dashboard_statistics(self):
        """
        Verify admin dashboard renders counts and completion rate statistics.
        """
        self.login('admin@test.com')
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        
        # 1 student, 1 internship (pending, not completed)
        self.assertIn(b'1', response.data) # student count
        self.assertIn(b'0.0%', response.data) # completion rate

        # Set internship to completed
        self.internship.status = 'completed'
        db.session.commit()
        
        response_comp = self.client.get('/admin/dashboard')
        self.assertIn(b'100.0%', response_comp.data) # completion rate

    def test_student_crud_and_deactivation(self):
        """
        Verify complete student CRUD workflow: view, search, add, edit, toggle login status, and delete.
        """
        self.login('admin@test.com')
        
        # 1. Add student
        add_data = {
            'name': 'Charlie Student',
            'email': 'charlie@test.com',
            'password': 'password123',
            'roll_no': 'IT301',
            'course': 'IT',
            'semester': '4',
            'phone': '1234567890'
        }
        response_add = self.client.post('/admin/students/add', data=add_data, follow_redirects=True)
        self.assertEqual(response_add.status_code, 200)
        self.assertIn(b'Student Charlie Student registered successfully.', response_add.data)
        
        charlie_user = User.query.filter_by(email='charlie@test.com').first()
        self.assertIsNotNone(charlie_user)
        self.assertEqual(charlie_user.student.roll_no, 'IT301')

        # 2. Edit student
        edit_data = {
            'name': 'Charlie Edited',
            'email': 'charlie@test.com',
            'roll_no': 'IT301',
            'course': 'IT-Security',
            'semester': '5',
            'phone': '0987654321'
        }
        response_edit = self.client.post(f'/admin/students/edit/{charlie_user.student.id}', data=edit_data, follow_redirects=True)
        self.assertIn(b'Student Charlie Edited updated successfully.', response_edit.data)
        
        db.session.refresh(charlie_user)
        self.assertEqual(charlie_user.name, 'Charlie Edited')
        self.assertEqual(charlie_user.student.course, 'IT-Security')
        self.assertEqual(charlie_user.student.semester, 5)

        # 3. Search and filter student
        response_search = self.client.get('/admin/students?search=Charlie')
        self.assertIn(b'Charlie Edited', response_search.data)
        self.assertNotIn(b'Bob Student', response_search.data)

        # 4. Toggle Active Status (Deactivate)
        response_toggle = self.client.post(f'/admin/students/toggle-status/{charlie_user.student.id}', follow_redirects=True)
        self.assertIn(b'has been deactivated.', response_toggle.data)
        
        db.session.refresh(charlie_user)
        self.assertFalse(charlie_user.is_active)
        self.logout()

        # 5. Verify deactivated student cannot log in
        response_login = self.client.post('/login', data={'email': 'charlie@test.com', 'password': 'password123'})
        self.assertIn(b'Your account has been deactivated.', response_login.data)
        
        # 6. Delete student
        self.login('admin@test.com')
        charlie_student_id = charlie_user.student.id
        response_del = self.client.post(f'/admin/students/delete/{charlie_student_id}', follow_redirects=True)
        self.assertIn(b'deleted.', response_del.data)
        
        deleted_user = User.query.filter_by(email='charlie@test.com').first()
        self.assertNone = deleted_user # should be deleted

    def test_internship_review_approvals_and_rejections(self):
        """
        Verify admin can approve or reject placements and edit placement records.
        """
        self.login('admin@test.com')
        
        # 1. Approve internship placement
        response_appr = self.client.post(f'/admin/internships/approve/{self.internship.id}', follow_redirects=True)
        self.assertEqual(response_appr.status_code, 200)
        self.assertIn(b'approved successfully.', response_appr.data)
        
        db.session.refresh(self.internship)
        self.assertEqual(self.internship.status, 'approved')
        
        # Verify that approving placement automatically generated timeline events and deadlines
        timeline_count = TimelineEvent.query.filter_by(internship_id=self.internship.id).count()
        self.assertTrue(timeline_count > 0)
        
        deadline_count = Deadline.query.filter_by(internship_id=self.internship.id).count()
        self.assertTrue(deadline_count > 0)

        # 2. Edit internship record
        edit_internship_data = {
            'role': 'Junior Data Analyst',
            'description': 'Working with databases',
            'start_date': '2026-09-01',
            'end_date': '2026-10-01',
            'internship_type': 'hybrid',
            'supervisor_name': 'Sarah Analyst',
            'supervisor_email': 'sarah@analyst.com',
            'supervisor_phone': '9876543210',
            'company_id': str(self.company.id)
        }
        response_edit = self.client.post(f'/admin/internships/edit/{self.internship.id}', data=edit_internship_data, follow_redirects=True)
        self.assertIn(b'updated successfully.', response_edit.data)
        
        db.session.refresh(self.internship)
        self.assertEqual(self.internship.role, 'Junior Data Analyst')
        self.assertEqual(self.internship.internship_type, 'hybrid')

        # 3. View Internship Details Page
        response_detail = self.client.get(f'/admin/internships/detail/{self.internship.id}')
        self.assertEqual(response_detail.status_code, 200)
        self.assertIn(b'Junior Data Analyst', response_detail.data)

    def test_company_crud_operations(self):
        """
        Verify company CRUD operations (view, add, edit, delete, counts).
        """
        self.login('admin@test.com')
        
        # 1. Add company
        comp_data = {
            'company_name': 'Netflix Corp',
            'address': 'Los Gatos',
            'contact_person': 'HR Reed'
        }
        response_add = self.client.post('/admin/companies/add', data=comp_data, follow_redirects=True)
        self.assertEqual(response_add.status_code, 200)
        self.assertIn(b'Company Netflix Corp registered successfully.', response_add.data)
        
        netflix = Company.query.filter_by(company_name='Netflix Corp').first()
        self.assertIsNotNone(netflix)
        self.assertEqual(netflix.address, 'Los Gatos')

        # 2. Edit company details
        comp_edit = {
            'company_name': 'Netflix Inc',
            'address': 'Silicon Valley',
            'contact_person': 'HR Reed Hastings'
        }
        response_edit = self.client.post(f'/admin/companies/edit/{netflix.id}', data=comp_edit, follow_redirects=True)
        self.assertIn(b'Netflix Inc updated successfully.', response_edit.data)
        
        db.session.refresh(netflix)
        self.assertEqual(netflix.company_name, 'Netflix Inc')
        self.assertEqual(netflix.contact_person, 'HR Reed Hastings')

        # 3. Search companies list and view placement counts
        response_list = self.client.get('/admin/companies?search=Netflix')
        self.assertIn(b'Netflix Inc', response_list.data)
        self.assertIn(b'0 Placements', response_list.data)

        # 4. Delete company
        response_del = self.client.post(f'/admin/companies/delete/{netflix.id}', follow_redirects=True)
        self.assertIn(b'deleted successfully.', response_del.data)
        
        deleted_netflix = Company.query.filter_by(company_name='Netflix Inc').first()
        self.assertIsNone(deleted_netflix)

if __name__ == '__main__':
    unittest.main()
