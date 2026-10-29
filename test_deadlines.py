import unittest
import os
from datetime import date, datetime, timedelta, timezone
from app import create_app
from database.db import db
from models import User, Student, Company, Internship, Deadline, Notification
from werkzeug.security import generate_password_hash
from routes.student import get_deadline_status_and_days, check_approaching_deadlines

class TestDeadlinesAndNotifications(unittest.TestCase):
    def setUp(self):
        """
        Setup database tables and mock records.
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
        
        # Internship for Student A
        self.internship_a = Internship(
            student_id=self.student_a.id,
            company_id=self.company.id,
            role='Software Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='pending'
        )
        db.session.add(self.internship_a)
        db.session.commit()

        # Internship for Student B
        self.internship_b = Internship(
            student_id=self.student_b.id,
            company_id=self.company.id,
            role='QA Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='approved'
        )
        db.session.add(self.internship_b)
        db.session.commit()
        
    def login(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def test_deadline_generation_upon_approval(self):
        """
        Verify that 4 deadlines are automatically created when the internship is approved.
        """
        # Approved via client simulation
        self.login('studenta@test.com')
        response = self.client.post('/student/timeline/demo-trigger', data={'action': 'approve'}, follow_redirects=True)
        self.assertIn(b'Timeline Active', response.data)
        
        # Verify 4 deadlines exist in the DB
        deadlines = Deadline.query.filter_by(internship_id=self.internship_a.id).all()
        self.assertEqual(len(deadlines), 4)
        
        # Check titles
        titles = {d.title for d in deadlines}
        self.assertEqual(titles, {"Weekly Progress Log", "Final Report", "Faculty Evaluation", "Completion Certificate"})
        
        # Verify notification was generated
        notif = Notification.query.filter_by(user_id=self.user_a.id, title="Internship Approved").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.message, "Your internship has been approved.")

    def test_deadline_status_calculation(self):
        """
        Verify status logic: Pending, Due Today, Overdue, Completed based on dates.
        """
        # 1. Pending (due in 5 days)
        dl_pending = Deadline(
            internship_id=self.internship_b.id,
            title="Test Pending",
            due_date=datetime.combine(date.today() + timedelta(days=5), datetime.min.time()),
            status="pending"
        )
        # 2. Due Today
        dl_today = Deadline(
            internship_id=self.internship_b.id,
            title="Test Due Today",
            due_date=datetime.combine(date.today(), datetime.min.time()),
            status="pending"
        )
        # 3. Overdue (due 5 days ago, incomplete)
        dl_overdue = Deadline(
            internship_id=self.internship_b.id,
            title="Test Overdue",
            due_date=datetime.combine(date.today() - timedelta(days=5), datetime.min.time()),
            status="pending"
        )
        # 4. Completed
        dl_completed = Deadline(
            internship_id=self.internship_b.id,
            title="Test Completed",
            due_date=datetime.combine(date.today() - timedelta(days=2), datetime.min.time()),
            status="completed",
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add_all([dl_pending, dl_today, dl_overdue, dl_completed])
        db.session.commit()
        
        # Assert computed status and days
        s, d = get_deadline_status_and_days(dl_pending)
        self.assertEqual(s, "Pending")
        self.assertEqual(d, 5)
        
        s, d = get_deadline_status_and_days(dl_today)
        self.assertEqual(s, "Due Today")
        self.assertEqual(d, 0)
        
        s, d = get_deadline_status_and_days(dl_overdue)
        self.assertEqual(s, "Overdue")
        self.assertEqual(d, -5)
        
        s, d = get_deadline_status_and_days(dl_completed)
        self.assertEqual(s, "Completed")
        self.assertEqual(d, 0)

    def test_approaching_deadline_notification(self):
        """
        Verify warning notifications are generated when incomplete deadlines are due in <= 3 days.
        """
        # Create deadline due in 3 days
        dl = Deadline(
            internship_id=self.internship_b.id,
            title="Final Report",
            due_date=datetime.combine(date.today() + timedelta(days=3), datetime.min.time()),
            status="pending"
        )
        db.session.add(dl)
        db.session.commit()
        
        # Run check
        check_approaching_deadlines(self.student_b.id)
        
        # Verify notification created
        notif = Notification.query.filter_by(user_id=self.user_b.id, title="Deadline Approaching").first()
        self.assertIsNotNone(notif)
        self.assertIn("final report is due in 3 days", notif.message.lower())

    def test_mark_notifications_as_read(self):
        """
        Verify notifications read and read-all endpoints.
        """
        self.login('studentb@test.com')
        
        notif1 = Notification(user_id=self.user_b.id, title="N1", message="Message 1")
        notif2 = Notification(user_id=self.user_b.id, title="N2", message="Message 2")
        db.session.add_all([notif1, notif2])
        db.session.commit()
        
        # Mark 1 as read
        response1 = self.client.post(f'/student/notifications/read/{notif1.id}', follow_redirects=True)
        db.session.refresh(notif1)
        self.assertTrue(notif1.is_read)
        self.assertFalse(notif2.is_read)
        
        # Mark all as read
        response2 = self.client.post('/student/notifications/read-all', follow_redirects=True)
        db.session.refresh(notif2)
        self.assertTrue(notif2.is_read)

    def test_notification_data_isolation(self):
        """
        Verify Student A cannot mark Student B's notification as read.
        """
        # Student B's notification
        notif = Notification(user_id=self.user_b.id, title="B's Notif", message="Secrets")
        db.session.add(notif)
        db.session.commit()
        
        # Student A logs in
        self.login('studenta@test.com')
        
        # Attempt to read B's notification -> 403 Forbidden
        response = self.client.post(f'/student/notifications/read/{notif.id}')
        self.assertEqual(response.status_code, 403)
        db.session.refresh(notif)
        self.assertFalse(notif.is_read)

if __name__ == '__main__':
    unittest.main()
