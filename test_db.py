import os
import unittest
from datetime import datetime, date, timezone
from sqlalchemy.exc import IntegrityError
from app import create_app
from database.db import db
from models import (
    User, Student, Faculty, Company, Internship, Document,
    TimelineEvent, ProgressReport, Deadline, Evaluation, Notification
)

class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        """
        Sets up an isolated, in-memory testing context.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create all tables dynamically based on loaded metadata
        db.create_all()

    def tearDown(self):
        """
        Cleans up database sessions and drops schema tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_tables_created(self):
        """
        Verifies that all 11 tables defined in requirements exist.
        """
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        required_tables = [
            'users', 'students', 'faculty', 'companies', 'internships',
            'documents', 'timeline_events', 'progress_reports', 'deadlines',
            'evaluations', 'notifications'
        ]
        for table in required_tables:
            self.assertIn(table, tables, f"Database table '{table}' is missing.")

    def test_user_creation_and_constraints(self):
        """
        Tests email unique constraints on the users table.
        """
        user = User(
            name="Alice Smith",
            email="alice@example.com",
            password_hash="hashedpassword123",
            role="student"
        )
        db.session.add(user)
        db.session.commit()
        
        # Test unique email constraint
        duplicate_user = User(
            name="Bob Smith",
            email="alice@example.com",
            password_hash="hashedpassword123",
            role="student"
        )
        db.session.add(duplicate_user)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_foreign_keys_and_cascades(self):
        """
        Tests one-to-one references and cascade-on-delete between User and Student.
        """
        user = User(
            name="Student User",
            email="student@example.com",
            password_hash="pwd",
            role="student"
        )
        db.session.add(user)
        db.session.commit()
        
        student = Student(
            user_id=user.id,
            roll_no="STU001",
            course="Computer Science",
            semester=3,
            phone="1234567890"
        )
        db.session.add(student)
        db.session.commit()
        
        # Verify relationship mapping
        self.assertEqual(user.student, student)
        
        # Verify cascade delete: deleting the User must remove the Student
        db.session.delete(user)
        db.session.commit()
        
        deleted_student = Student.query.filter_by(roll_no="STU001").first()
        self.assertIsNone(deleted_student, "Student record was not cascade deleted with User.")

    def test_bad_foreign_key_raises_error(self):
        """
        Confirms that the SQLite connection event listener enforces foreign keys.
        Inserting a student with an invalid user_id must throw an IntegrityError.
        """
        student_with_bad_fk = Student(
            user_id=9999,  # Bad Reference
            roll_no="STU999",
            course="Informatics",
            semester=1
        )
        db.session.add(student_with_bad_fk)
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_internship_relations_and_cascade(self):
        """
        Tests internship references and timeline cascade deletions.
        """
        # Create user + student
        user = User(name="Student A", email="studa@example.com", password_hash="pwd", role="student")
        db.session.add(user)
        db.session.commit()
        
        student = Student(user_id=user.id, roll_no="STU002", course="IT", semester=5)
        company = Company(company_name="Tech Corp")
        db.session.add_all([student, company])
        db.session.commit()
        
        # Create internship
        internship = Internship(
            student_id=student.id,
            company_id=company.id,
            role="Developer Intern",
            status="pending"
        )
        db.session.add(internship)
        db.session.commit()
        
        # Create associated event
        event = TimelineEvent(
            internship_id=internship.id,
            title="Kickoff Meeting",
            event_date=datetime.now(timezone.utc),
            status="pending"
        )
        db.session.add(event)
        db.session.commit()
        
        # Confirm relations mapping
        self.assertEqual(internship.student, student)
        self.assertEqual(internship.company, company)
        self.assertIn(event, internship.timeline_events)
        
        # Test cascade delete: removing the internship should remove the timeline event
        db.session.delete(internship)
        db.session.commit()
        
        deleted_event = TimelineEvent.query.filter_by(title="Kickoff Meeting").first()
        self.assertIsNone(deleted_event, "TimelineEvent was not cascade deleted with Internship.")

if __name__ == '__main__':
    unittest.main()
