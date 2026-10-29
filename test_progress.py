import unittest
import os
from datetime import date, datetime, timedelta
from io import BytesIO
from app import create_app
from database.db import db
from models import User, Student, Company, Internship, TimelineEvent, ProgressReport
from werkzeug.security import generate_password_hash

class TestWeeklyProgressTracking(unittest.TestCase):
    def setUp(self):
        """
        Setup database tables and mock student accounts.
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
        Clean up resources after tests.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_data(self):
        hashed = generate_password_hash('password123')
        
        # Student A
        self.user_a = User(name='Student A', email='studenta@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_a)
        db.session.commit()
        self.student_a = Student(user_id=self.user_a.id, roll_no='ROLLA', course='CS', semester=6)
        db.session.add(self.student_a)
        db.session.commit()
        
        # Student B
        self.user_b = User(name='Student B', email='studentb@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_b)
        db.session.commit()
        self.student_b = Student(user_id=self.user_b.id, roll_no='ROLLB', course='CS', semester=6)
        db.session.add(self.student_b)
        db.session.commit()
        
        # Company
        self.company = Company(company_name='SuperTech')
        db.session.add(self.company)
        db.session.commit()
        
        # Internship for Student A (Approved so timeline exists)
        self.internship_a = Internship(
            student_id=self.student_a.id,
            company_id=self.company.id,
            role='Software Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='approved'
        )
        db.session.add(self.internship_a)
        db.session.commit()
        
        # Generate initial timeline events for Student A (10 events)
        from routes.student import generate_timeline_events
        generate_timeline_events(self.internship_a)
        
    def login(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def logout(self):
        self.client.get('/logout')

    def test_submit_report_success(self):
        """
        Verify successful submission of progress report, timeline integration,
        and dashboard dynamic percentage update.
        """
        self.login('studenta@test.com')
        
        # Initially 2 events are completed (Registration, Approval) out of 10 -> 20%
        response = self.client.get('/student/dashboard')
        self.assertIn(b'20%', response.data)
        
        # Submit progress report for Week 1
        data = {
            'week_number': '1',
            'hours_worked': '37.5',
            'tasks_completed': 'Created timeline layout and integrated endpoints.',
            'skills_learned': 'Flask, SQLAlchemy',
            'challenges': 'None',
            'report_file': (BytesIO(b'dummy file content'), 'week1.pdf')
        }
        
        response_post = self.client.post('/student/progress', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Weekly report for Week 1 submitted successfully.', response_post.data)
        
        # Check database record is created
        report = ProgressReport.query.filter_by(internship_id=self.internship_a.id, week_number=1).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.hours_worked, 37.5)
        self.assertIn('week1.pdf', report.report_file)
        
        # Check timeline event Week 1 Progress is completed
        event = TimelineEvent.query.filter_by(internship_id=self.internship_a.id, title='Week 1 Progress').first()
        self.assertEqual(event.status, 'completed')
        
        # Check that now 3 events are completed out of 10 -> 30%
        response_dash = self.client.get('/student/dashboard')
        self.assertIn(b'30%', response_dash.data)

    def test_invalid_input_validation(self):
        """
        Verify that negative hours or non-positive week numbers are rejected.
        """
        self.login('studenta@test.com')
        
        # 1. Invalid week number (negative)
        data = {
            'week_number': '-1',
            'hours_worked': '40',
            'tasks_completed': 'Working',
            'skills_learned': '',
            'challenges': ''
        }
        response = self.client.post('/student/progress', data=data, follow_redirects=True)
        self.assertIn(b'Week number must be positive.', response.data)
        
        # 2. Invalid hours (negative)
        data = {
            'week_number': '1',
            'hours_worked': '-10',
            'tasks_completed': 'Working',
            'skills_learned': '',
            'challenges': ''
        }
        response = self.client.post('/student/progress', data=data, follow_redirects=True)
        self.assertIn(b'Hours worked cannot be negative.', response.data)

    def test_edit_progress_report(self):
        """
        Verify that a student can edit their own submitted progress report.
        """
        self.login('studenta@test.com')
        
        # Submit report
        report = ProgressReport(
            internship_id=self.internship_a.id,
            student_id=self.student_a.id,
            week_number=2,
            tasks_completed='Original tasks',
            hours_worked=30.0,
            status='submitted'
        )
        db.session.add(report)
        db.session.commit()
        
        # Edit report
        data = {
            'tasks_completed': 'Updated tasks list',
            'hours_worked': '35.0',
            'skills_learned': 'New skills',
            'challenges': 'None'
        }
        response = self.client.post(f'/student/progress/edit/{report.id}', data=data, follow_redirects=True)
        self.assertIn(b'Weekly report updated successfully.', response.data)
        
        # Check database is updated
        db.session.refresh(report)
        self.assertEqual(report.tasks_completed, 'Updated tasks list')
        self.assertEqual(report.hours_worked, 35.0)

    def test_student_data_isolation(self):
        """
        Verify that Student B cannot access or edit Student A's reports.
        """
        # Create a report for Student A
        report = ProgressReport(
            internship_id=self.internship_a.id,
            student_id=self.student_a.id,
            week_number=1,
            tasks_completed='Student A tasks',
            hours_worked=40.0,
            status='submitted'
        )
        db.session.add(report)
        db.session.commit()
        
        # Log in as Student B
        self.login('studentb@test.com')
        
        # Try to edit Student A's report -> 403 Forbidden
        data = {
            'tasks_completed': 'Attempt to hijack',
            'hours_worked': '20.0'
        }
        response = self.client.post(f'/student/progress/edit/{report.id}', data=data)
        self.assertEqual(response.status_code, 403)
        
if __name__ == '__main__':
    unittest.main()
