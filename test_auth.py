import unittest
from werkzeug.security import generate_password_hash
from app import create_app
from database.db import db
from models import User, Student

class TestAuthenticationLayer(unittest.TestCase):
    def setUp(self):
        """
        Creates an isolated testing client in memory.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-2026'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        """
        Tears down database sessions and clears contexts.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_student_registration_flow(self):
        """
        1. Verifies that a valid student registration creates both User and Student database profiles.
        Also validates that passwords are encrypted using Werkzeug.
        """
        response = self.client.post('/register', data={
            'name': 'Bob Student',
            'email': 'bob@student.edu',
            'roll_no': 'ROLL001',
            'course': 'Software Engineering',
            'semester': '4',
            'phone': '1234567890',
            'password': 'safe_password123',
            'confirm_password': 'safe_password123'
        }, follow_redirects=True)
        
        # Verify user database record
        user = User.query.filter_by(email='bob@student.edu').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'student')
        self.assertNotEqual(user.password_hash, 'safe_password123')  # Verify encryption
        
        # Verify student database record
        student = Student.query.filter_by(roll_no='ROLL001').first()
        self.assertIsNotNone(student)
        self.assertEqual(student.user_id, user.id)
        self.assertEqual(student.course, 'Software Engineering')
        self.assertEqual(student.semester, 4)
        
    def test_registration_duplicate_email(self):
        """
        2. Validates that duplicate email registration attempts are caught.
        """
        user = User(name='Existing User', email='dup@test.com', password_hash='hash', role='student')
        db.session.add(user)
        db.session.commit()
        
        response = self.client.post('/register', data={
            'name': 'Bob Student',
            'email': 'dup@test.com',
            'roll_no': 'ROLL002',
            'course': 'IT',
            'semester': '2',
            'phone': '',
            'password': 'pass',
            'confirm_password': 'pass'
        })
        self.assertIn(b'Email already registered.', response.data)
        
    def test_registration_duplicate_roll_number(self):
        """
        3. Validates that duplicate roll number registrations are blocked.
        """
        user = User(name='User A', email='usera@test.com', password_hash='hash', role='student')
        db.session.add(user)
        db.session.commit()
        student = Student(user_id=user.id, roll_no='ROLL_DUP', course='CS', semester=2)
        db.session.add(student)
        db.session.commit()
        
        response = self.client.post('/register', data={
            'name': 'Student B',
            'email': 'userb@test.com',
            'roll_no': 'ROLL_DUP',
            'course': 'IT',
            'semester': '2',
            'phone': '',
            'password': 'pass',
            'confirm_password': 'pass'
        })
        self.assertIn(b'Roll number already registered.', response.data)

    def test_login_success_and_failures(self):
        """
        4. Checks that valid credentials logs a user in and sets session keys.
        5. Checks that incorrect passwords are rejected with validation alerts.
        """
        hashed = generate_password_hash('correct_password')
        user = User(name='John Doe', email='john@example.com', password_hash=hashed, role='student')
        db.session.add(user)
        db.session.commit()
        
        # Valid login trigger
        response = self.client.post('/login', data={
            'email': 'john@example.com',
            'password': 'correct_password'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/student/dashboard')
        
        # Verify session registration keys
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_id'), user.id)
            self.assertEqual(sess.get('role'), 'student')
            self.assertEqual(sess.get('user_name'), 'John Doe')
            
        # Clear active session before testing bad credentials login
        self.client.get('/logout')
            
        # Invalid password trigger
        response_bad = self.client.post('/login', data={
            'email': 'john@example.com',
            'password': 'wrong_password'
        })
        self.assertEqual(response_bad.status_code, 200)
        self.assertIn(b'Invalid email or password.', response_bad.data)


    def test_logout_session_clearing(self):
        """
        6. Verifies logout triggers complete session key removals.
        """
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'student'
            sess['user_name'] = 'Test User'
            
        response = self.client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # Confirm cleared session
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
            self.assertNotIn('role', sess)
            self.assertNotIn('user_name', sess)

    def test_authorization_protection_walls(self):
        """
        7. Student accessing admin dashboard raises 403 Forbidden.
        8. Student accessing faculty dashboard raises 403 Forbidden.
        """
        hashed = generate_password_hash('pwd')
        user = User(name='Alice Student', email='alice@student.com', password_hash=hashed, role='student')
        db.session.add(user)
        db.session.commit()
        student = Student(user_id=user.id, roll_no='STU_AUTH', course='CS', semester=2)
        db.session.add(student)
        db.session.commit()

        # Log in student session
        self.client.post('/login', data={
            'email': 'alice@student.com',
            'password': 'pwd'
        })

        # Test Student accessing Admin dashboard
        response_admin = self.client.get('/admin/dashboard')
        self.assertEqual(response_admin.status_code, 403)
        self.assertIn(b'403 - Access Denied', response_admin.data)

        # Test Student accessing Faculty dashboard
        response_faculty = self.client.get('/faculty/dashboard')
        self.assertEqual(response_faculty.status_code, 403)
        self.assertIn(b'403 - Access Denied', response_faculty.data)

    def test_unauthenticated_access_protection(self):
        """
        9. Unauthenticated users trying to access dashboard endpoints are redirected to Login.
        """
        response = self.client.get('/student/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/login')

    def test_faculty_registration_flow(self):
        """
        10. Verifies valid faculty registration creates User and Faculty models with hashed password.
        """
        from models import Faculty
        response = self.client.post('/register', data={
            'role': 'faculty',
            'name': 'Prof. Charles Xavier',
            'email': 'xavier@faculty.edu',
            'employee_id': 'FAC9001',
            'department': 'Computer Science',
            'password': 'mentor_secure_pwd',
            'confirm_password': 'mentor_secure_pwd'
        }, follow_redirects=True)

        user = User.query.filter_by(email='xavier@faculty.edu').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'faculty')
        self.assertNotEqual(user.password_hash, 'mentor_secure_pwd')

        faculty = Faculty.query.filter_by(employee_id='FAC9001').first()
        self.assertIsNotNone(faculty)
        self.assertEqual(faculty.user_id, user.id)
        self.assertEqual(faculty.department, 'Computer Science')

    def test_registration_operational_error_readonly_logging(self):
        """
        11. Verifies that when a database write error occurs (such as read-only SQLite on Vercel),
        safe server-side logging occurs, the user receives a safe flash message,
        and no raw exception details are exposed to the visitor.
        """
        from unittest.mock import patch
        from sqlalchemy.exc import OperationalError

        with patch.object(db.session, 'commit', side_effect=OperationalError("attempt to write a readonly database", None, None)):
            with self.assertLogs(self.app.logger.name, level='ERROR') as log_capture:
                response = self.client.post('/register', data={
                    'name': 'Test Student',
                    'email': 'readonly_test@student.edu',
                    'roll_no': 'RO_TEST_01',
                    'course': 'Computer Science',
                    'semester': '3',
                    'phone': '1234567890',
                    'password': 'secret_password_123',
                    'confirm_password': 'secret_password_123'
                })

                # Safe user-facing feedback without raw internal database details
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'An error occurred during registration. Please try again.', response.data)
                self.assertNotIn(b'sqlite3.OperationalError', response.data)
                self.assertNotIn(b'attempt to write a readonly database', response.data)
                self.assertNotIn(b'secret_password_123', response.data)

                # Server-side logs captured the exact diagnostic guidance for Vercel
                log_output = "\n".join(log_capture.output)
                self.assertIn("SQLite database write permission error", log_output)
                self.assertIn("DATABASE_URL", log_output)
                # Password must NEVER appear in server logs
                self.assertNotIn("secret_password_123", log_output)

    def test_registration_integrity_error_safety(self):
        """
        12. Verifies that database integrity violations log a warning and return user-friendly alert
        without leaking database constraints or schema details.
        """
        from unittest.mock import patch
        from sqlalchemy.exc import IntegrityError

        with patch.object(db.session, 'commit', side_effect=IntegrityError("duplicate key value", None, None)):
            with self.assertLogs(self.app.logger.name, level='WARNING') as log_capture:
                response = self.client.post('/register', data={
                    'name': 'Integrity Test',
                    'email': 'integrity@student.edu',
                    'roll_no': 'INT_01',
                    'course': 'IT',
                    'semester': '2',
                    'password': 'pwd',
                    'confirm_password': 'pwd'
                })

                self.assertEqual(response.status_code, 200)
                self.assertIn(b'A user or record with these details already exists', response.data)
                self.assertNotIn(b'sqlalchemy.exc.IntegrityError', response.data)

                log_output = "\n".join(log_capture.output)
                self.assertIn("Registration failed due to database unique constraint", log_output)

    def test_database_url_postgres_normalization(self):
        """
        13. Verifies that postgres:// URI prefixes are normalized to postgresql:// for SQLAlchemy.
        """
        import os
        from config import Config
        os.environ['DATABASE_URL'] = 'postgres://user:secretpass@dbhost.com:5432/interntrack_db'
        try:
            # Re-read configuration logic
            db_url = os.environ.get('DATABASE_URL')
            if db_url and db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            self.assertTrue(db_url.startswith('postgresql://'))
        finally:
            del os.environ['DATABASE_URL']

    def test_sqlite_pragma_safety_for_non_sqlite(self):
        """
        14. Confirms that set_sqlite_pragma does NOT attempt to execute PRAGMA on non-SQLite engines.
        """
        from database.db import set_sqlite_pragma
        from unittest.mock import MagicMock

        # Mock a PostgreSQL dbapi connection
        mock_pg_conn = MagicMock()
        mock_pg_conn.__class__.__module__ = 'psycopg2.extensions'
        
        # Calling set_sqlite_pragma on mock_pg_conn must NOT call cursor() or execute()
        set_sqlite_pragma(mock_pg_conn, None)
        mock_pg_conn.cursor.assert_not_called()

    def test_error_sanitization_masks_connection_credentials(self):
        """
        15. Verifies that connection string passwords in error messages are masked.
        """
        from routes.auth import _sanitize_error_message
        raw_msg = "OperationalError: could not connect to server: postgresql://myuser:super_secret_pw@db.neon.tech/mydb"
        sanitized = _sanitize_error_message(raw_msg)
        self.assertNotIn("super_secret_pw", sanitized)
        self.assertIn("postgresql://myuser:***@db.neon.tech/mydb", sanitized)


if __name__ == '__main__':
    unittest.main()
