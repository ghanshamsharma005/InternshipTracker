import unittest
from datetime import date, datetime, timedelta
from app import create_app
from database.db import db
from models import User, Student, Company, Internship, TimelineEvent
from werkzeug.security import generate_password_hash

class TestInternshipTimelineLayer(unittest.TestCase):
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
        
        self.setup_student()

    def tearDown(self):
        """
        Closes context and drops in-memory tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_student(self):
        """
        Sets up student profile and pending internship records.
        """
        hashed = generate_password_hash('password123')
        
        # Create user
        self.user = User(name='Anmol Student', email='anmol@test.com', password_hash=hashed, role='student')
        db.session.add(self.user)
        db.session.commit()
        
        # Create student profile
        self.student = Student(user_id=self.user.id, roll_no='CS101', course='CS', semester=5)
        db.session.add(self.student)
        db.session.commit()
        
        # Log in student
        self.client.post('/login', data={'email': 'anmol@test.com', 'password': 'password123'})

        # Seed company
        self.company = Company(company_name='Alphabet')
        db.session.add(self.company)
        db.session.commit()
        
        # Create placement record
        self.internship = Internship(
            student_id=self.student.id,
            company_id=self.company.id,
            role='Research Intern',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),  # 4 weeks duration
            status='pending'
        )
        db.session.add(self.internship)
        db.session.commit()

    def test_timeline_lifecycle_transitions(self):
        """
        Tests the 6 target timeline validation stages:
        1. Pre-approval empty state.
        2. Post-approval initial stage creations.
        3. Timeline after internship starts.
        4. Timeline after progress submissions.
        5. Timeline after faculty evaluations.
        6. Timeline after final completion.
        """
        # 1. Timeline before approval
        response = self.client.get('/student/timeline')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Awaiting Timeline Activation', response.data)
        
        events_count = TimelineEvent.query.filter_by(internship_id=self.internship.id).count()
        self.assertEqual(events_count, 0)
        
        # 2. Timeline after approval (auto-generation on approval transition)
        response_appr = self.client.post('/student/timeline/demo-trigger', data={'action': 'approve'}, follow_redirects=True)
        self.assertEqual(response_appr.status_code, 200)
        self.assertIn(b'Timeline Active', response_appr.data)
        
        # Should generate: 1 Registration + 1 Approval + 1 Started + 4 Weeks + 1 Final Report + 1 Eval + 1 Comp = 10 events
        events = TimelineEvent.query.filter_by(internship_id=self.internship.id).order_by(TimelineEvent.id).all()
        self.assertEqual(len(events), 10)
        
        self.assertEqual(events[0].title, 'Internship Registration')
        self.assertEqual(events[0].status, 'completed')
        self.assertEqual(events[1].title, 'Internship Approval')
        self.assertEqual(events[1].status, 'completed')
        self.assertEqual(events[2].title, 'Internship Started')
        self.assertEqual(events[2].status, 'pending')
        
        # 3. Timeline after internship starts
        response_start = self.client.post('/student/timeline/demo-trigger', data={'action': 'start'}, follow_redirects=True)
        self.assertIn(b'Internship Started marked completed.', response_start.data)
        
        event_start = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Internship Started').first()
        self.assertEqual(event_start.status, 'completed')
        
        event_w1 = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Week 1 Progress').first()
        self.assertEqual(event_w1.status, 'in_progress')
        
        # 4. Timeline after progress submission (Week 1 Progress completed)
        response_prog1 = self.client.post('/student/timeline/demo-trigger', data={'action': 'progress'}, follow_redirects=True)
        self.assertIn(b'Progress submitted for stage', response_prog1.data)
        self.assertIn(b'Week 1 Progress', response_prog1.data)

        
        event_w1 = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Week 1 Progress').first()
        self.assertEqual(event_w1.status, 'completed')
        
        event_w2 = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Week 2 Progress').first()
        self.assertEqual(event_w2.status, 'in_progress')
        
        # Fast-forward remaining weeks and final report
        self.client.post('/student/timeline/demo-trigger', data={'action': 'progress'}) # Comp Week 2
        self.client.post('/student/timeline/demo-trigger', data={'action': 'progress'}) # Comp Week 3
        self.client.post('/student/timeline/demo-trigger', data={'action': 'progress'}) # Comp Week 4
        self.client.post('/student/timeline/demo-trigger', data={'action': 'progress'}) # Comp Final Report
        
        # Verify Final Report is completed, and Faculty Evaluation is in_progress
        event_rep = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Final Report').first()
        self.assertEqual(event_rep.status, 'completed')
        
        event_eval = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Faculty Evaluation').first()
        self.assertEqual(event_eval.status, 'in_progress')
        
        # 5. Timeline after evaluation
        response_eval = self.client.post('/student/timeline/demo-trigger', data={'action': 'evaluate'}, follow_redirects=True)
        self.assertIn(b'Faculty Evaluation completed.', response_eval.data)
        
        event_eval = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Faculty Evaluation').first()
        self.assertEqual(event_eval.status, 'completed')
        
        event_comp = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Internship Completion').first()
        self.assertEqual(event_comp.status, 'in_progress')
        
        # 6. Timeline after completion
        response_comp = self.client.post('/student/timeline/demo-trigger', data={'action': 'complete'}, follow_redirects=True)
        self.assertIn(b'Internship completed successfully!', response_comp.data)
        
        event_comp = TimelineEvent.query.filter_by(internship_id=self.internship.id, title='Internship Completion').first()
        self.assertEqual(event_comp.status, 'completed')
        
        # Check parent internship record status updated to completed
        db.session.refresh(self.internship)
        self.assertEqual(self.internship.status, 'completed')

if __name__ == '__main__':
    unittest.main()
