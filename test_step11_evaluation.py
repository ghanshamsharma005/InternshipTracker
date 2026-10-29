import unittest
from datetime import date, datetime, timedelta, timezone
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Document, ProgressReport, Evaluation, TimelineEvent
from werkzeug.security import generate_password_hash

class TestFacultyEvaluationSystem(unittest.TestCase):
    def setUp(self):
        """
        Setup database tables and seed mock data.
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
        
        # Create Student User & Profile
        self.user_s = User(name='Bob Student', email='bob@test.com', password_hash=hashed, role='student')
        db.session.add(self.user_s)
        db.session.commit()
        self.student = Student(user_id=self.user_s.id, roll_no='CS501', course='CS', semester=6)
        db.session.add(self.student)
        db.session.commit()
        
        # Create Faculty User & Profile
        self.user_f = User(name='Dr. Alice Advisor', email='alice@test.com', password_hash=hashed, role='faculty')
        db.session.add(self.user_f)
        db.session.commit()
        self.faculty = Faculty(user_id=self.user_f.id, department='CS', employee_id='EMP999')
        db.session.add(self.faculty)
        db.session.commit()

        # Create Admin User
        self.user_admin = User(name='Admin Boss', email='admin@test.com', password_hash=hashed, role='admin')
        db.session.add(self.user_admin)
        db.session.commit()

        # Create Company
        self.company = Company(company_name='MicroSoft Tech')
        db.session.add(self.company)
        db.session.commit()
        
        # Create Internship (Active)
        self.internship = Internship(
            student_id=self.student.id,
            company_id=self.company.id,
            role='Data Engineer',
            start_date=date.today(),
            end_date=date.today() + timedelta(weeks=4),
            status='active'
        )
        db.session.add(self.internship)
        db.session.commit()

        # Seed timeline events
        self.ev_eval = TimelineEvent(
            internship_id=self.internship.id,
            title='Faculty Evaluation',
            description='Coordinator review and final grade generation.',
            event_date=datetime.now(timezone.utc) + timedelta(days=7),
            status='in_progress'
        )
        self.ev_comp = TimelineEvent(
            internship_id=self.internship.id,
            title='Internship Completion',
            description='Timeline finalized and certificate issued.',
            event_date=datetime.now(timezone.utc) + timedelta(days=14),
            status='pending'
        )
        db.session.add_all([self.ev_eval, self.ev_comp])
        db.session.commit()

    def login(self, email):
        self.client.post('/login', data={'email': email, 'password': 'password123'})

    def logout(self):
        self.client.get('/logout')

    def test_unauthorized_access_to_evaluation(self):
        """
        Verify that students and admins cannot access the faculty evaluation route.
        """
        # 1. Student access denied (403)
        self.login('bob@test.com')
        response = self.client.get(f'/faculty/evaluation/{self.student.id}')
        self.assertEqual(response.status_code, 403)
        
        response_post = self.client.post(f'/faculty/evaluation/{self.student.id}', data={})
        self.assertEqual(response_post.status_code, 403)
        self.logout()

        # 2. Admin access denied (403)
        self.login('admin@test.com')
        response_admin = self.client.get(f'/faculty/evaluation/{self.student.id}')
        self.assertEqual(response_admin.status_code, 403)
        self.logout()

    def test_valid_scores_submission_and_calculation(self):
        """
        Verify submitting valid scores (0-10) stores them correctly,
        computes the overall score average, and transitions timeline states.
        """
        self.login('alice@test.com')
        
        evaluation_data = {
            'technical_skills': '9',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Great performance overall.'
        }
        
        response = self.client.post(
            f'/faculty/evaluation/{self.student.id}', 
            data=evaluation_data, 
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Evaluation for Bob Student submitted successfully.', response.data)
        
        # Verify db persistence
        evaluation = Evaluation.query.filter_by(internship_id=self.internship.id).first()
        self.assertIsNotNone(evaluation)
        self.assertEqual(evaluation.technical_skills, 9)
        self.assertEqual(evaluation.communication, 8)
        self.assertEqual(evaluation.punctuality, 10)
        self.assertEqual(evaluation.work_quality, 7)
        self.assertEqual(evaluation.discipline, 6)
        self.assertEqual(evaluation.feedback, 'Great performance overall.')
        
        # Calculation: (9 + 8 + 10 + 7 + 6) / 5 = 40 / 5 = 8.0
        self.assertEqual(evaluation.overall_score, 8.0)
        
        # Verify Timeline stage updates
        db.session.refresh(self.ev_eval)
        db.session.refresh(self.ev_comp)
        self.assertEqual(self.ev_eval.status, 'completed')
        self.assertEqual(self.ev_comp.status, 'in_progress')
        
        # Parent internship should NOT be completed because completion conditions are not met
        db.session.refresh(self.internship)
        self.assertNotEqual(self.internship.status, 'completed')

    def test_invalid_scores_submission(self):
        """
        Verify invalid scores (empty, string, out of bounds) are rejected.
        """
        self.login('alice@test.com')
        
        # 1. Out of bounds (negative score)
        data_neg = {
            'technical_skills': '-1',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Bad score'
        }
        response = self.client.post(f'/faculty/evaluation/{self.student.id}', data=data_neg)
        self.assertIn(b'Score for Technical Skills must be between 0 and 10.', response.data)
        
        # 2. Out of bounds (> 10)
        data_high = {
            'technical_skills': '11',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Too high'
        }
        response = self.client.post(f'/faculty/evaluation/{self.student.id}', data=data_high)
        self.assertIn(b'Score for Technical Skills must be between 0 and 10.', response.data)
        
        # 3. Empty score
        data_empty = {
            'technical_skills': '',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Empty'
        }
        response = self.client.post(f'/faculty/evaluation/{self.student.id}', data=data_empty)
        self.assertIn(b'Please enter a score for Technical Skills.', response.data)
        
        # 4. Non-integer score
        data_non_int = {
            'technical_skills': 'abc',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Non-int'
        }
        response = self.client.post(f'/faculty/evaluation/{self.student.id}', data=data_non_int)
        self.assertIn(b'Score for Technical Skills must be a number.', response.data)

        # Confirm nothing was saved in the db
        eval_count = Evaluation.query.filter_by(internship_id=self.internship.id).count()
        self.assertEqual(eval_count, 0)

    def test_student_read_only_access_and_pending_states(self):
        """
        Verify the student can access /student/evaluation in read-only mode,
        and sees pending placeholder if evaluation hasn't been submitted yet.
        """
        self.login('bob@test.com')
        
        # 1. Accessing evaluation before it's submitted
        response = self.client.get('/student/evaluation')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Evaluation Pending', response.data)
        self.assertIn(b'Your faculty advisor has not submitted your placement evaluation yet.', response.data)
        self.logout()

        # Submit valid evaluation as faculty
        self.login('alice@test.com')
        self.client.post(f'/faculty/evaluation/{self.student.id}', data={
            'technical_skills': '9',
            'communication': '8',
            'punctuality': '10',
            'work_quality': '7',
            'discipline': '6',
            'feedback': 'Fantastic work!'
        })
        self.logout()

        # 2. Accessing evaluation as student after submission
        self.login('bob@test.com')
        response_view = self.client.get('/student/evaluation')
        self.assertEqual(response_view.status_code, 200)
        self.assertIn(b'Placement Assessment', response_view.data)
        self.assertIn(b'Overall Score: 8.0/10.', response_view.data or b'8.0 / 10.0')
        self.assertIn(b'Fantastic work!', response_view.data)
        self.assertIn(b'Technical Skills', response_view.data)
        
        # Verify page is read-only (has no forms or submit buttons to change evaluation scores)
        self.assertNotIn(b'<form action="/student/evaluation"', response_view.data)

    def test_completion_conditions_blocks_and_satisfies_completion(self):
        """
        Verify that internship cannot be completed until all required documents
        are uploaded and verified, and evaluation exists.
        """
        self.login('alice@test.com')
        
        # Submit Faculty Evaluation
        self.client.post(f'/faculty/evaluation/{self.student.id}', data={
            'technical_skills': '8',
            'communication': '8',
            'punctuality': '8',
            'work_quality': '8',
            'discipline': '8',
            'feedback': 'Passing grades'
        })
        self.logout()
        
        # Check current state: evaluation exists but no documents verified yet
        self.login('bob@test.com')
        from routes.student import check_completion_conditions
        is_satisfied, missing = check_completion_conditions(self.internship)
        self.assertFalse(is_satisfied)
        self.assertIn("Required document 'Offer Letter' is missing.", missing)
        self.logout()

        # Verify documents & check completion conditions auto-completes internship
        self.login('alice@test.com')
        required_docs = ["Offer Letter", "Joining Letter", "ID Proof", "Weekly Report", "Final Report", "Completion Certificate"]
        for idx, doc_type in enumerate(required_docs):
            doc = Document(
                internship_id=self.internship.id,
                student_id=self.student.id,
                document_type=doc_type,
                file_path=f"file_{idx}.pdf",
                status='pending'
            )
            db.session.add(doc)
            db.session.commit()
            
            # Post verification (for the last one it should trigger auto-completion)
            response_v = self.client.post(f'/faculty/document/verify/{doc.id}', follow_redirects=True)
            self.assertEqual(response_v.status_code, 200)

        # Since all documents are verified and evaluation exists, internship status must transition to 'completed'
        db.session.refresh(self.internship)
        self.assertEqual(self.internship.status, 'completed')
        
        # Verify final timeline stage is also completed
        db.session.refresh(self.ev_comp)
        self.assertEqual(self.ev_comp.status, 'completed')

if __name__ == '__main__':
    unittest.main()
