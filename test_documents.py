import unittest
import os
from datetime import date, timedelta
from io import BytesIO
from app import create_app
from database.db import db
from models import User, Student, Company, Internship, Document
from werkzeug.security import generate_password_hash

class TestDocumentManagement(unittest.TestCase):
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
        
        self.setup_data()

    def tearDown(self):
        """
        Closes context and drops tables.
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
            status='approved'
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

    def test_upload_document_success(self):
        """
        Verify successful upload of a valid document type and dashboard counter updates.
        """
        self.login('studenta@test.com')
        
        # Initial count on dashboard is 0
        response_dash = self.client.get('/student/dashboard')
        self.assertIn(b'0 / 6 Submitted', response_dash.data)
        
        # Upload offer letter
        data = {
            'document_type': 'Offer Letter',
            'document_file': (BytesIO(b'pdf file content mock'), 'offer_letter.pdf')
        }
        
        response = self.client.post('/student/documents', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Document Offer Letter uploaded successfully.', response.data)
        
        # Check database
        doc = Document.query.filter_by(internship_id=self.internship_a.id, document_type='Offer Letter').first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.status, 'pending')
        
        # Check dashboard updates to 1
        response_dash2 = self.client.get('/student/dashboard')
        self.assertIn(b'1 / 6 Submitted', response_dash2.data)

    def test_invalid_file_type_rejected(self):
        """
        Verify that executable scripts and invalid extensions are blocked.
        """
        self.login('studenta@test.com')
        
        # Uploading script
        data = {
            'document_type': 'ID Proof',
            'document_file': (BytesIO(b'import os; os.system("bad things")'), 'hack.py')
        }
        response = self.client.post('/student/documents', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Only PDF, DOC, DOCX, PNG, and JPG/JPEG files are allowed.', response.data)
        
        # Uploading exe
        data2 = {
            'document_type': 'Offer Letter',
            'document_file': (BytesIO(b'binary'), 'malware.exe')
        }
        response2 = self.client.post('/student/documents', data=data2, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Only PDF, DOC, DOCX, PNG, and JPG/JPEG files are allowed.', response2.data)

    def test_large_file_size_rejected(self):
        """
        Verify file size constraint of 5MB is respected.
        """
        self.login('studenta@test.com')
        
        # Create a file exactly 6MB in size
        six_mb_content = b'x' * (6 * 1024 * 1024)
        data = {
            'document_type': 'Joining Letter',
            'document_file': (BytesIO(six_mb_content), 'huge_doc.pdf')
        }
        response = self.client.post('/student/documents', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'File size exceeds the 5MB limit.', response.data)

    def test_replace_document(self):
        """
        Verify replacing an existing document updates its database record and resets status to pending.
        """
        self.login('studenta@test.com')
        
        # Pre-seed a verified document for Student A
        doc = Document(
            internship_id=self.internship_a.id,
            student_id=self.student_a.id,
            document_type='ID Proof',
            file_path='old_id.png',
            status='verified'
        )
        db.session.add(doc)
        db.session.commit()
        
        # Replace document
        data = {
            'document_type': 'ID Proof',
            'document_file': (BytesIO(b'new file content'), 'new_id_card.png')
        }
        response = self.client.post('/student/documents', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Document ID Proof uploaded successfully.', response.data)
        
        # Check database: filename is updated and status reset to pending
        db.session.refresh(doc)
        self.assertIn('new_id_card.png', doc.file_path)
        self.assertEqual(doc.status, 'pending')

    def test_student_data_isolation(self):
        """
        Verify that Student B cannot view or download Student A's documents.
        """
        # Upload a document for Student A
        doc = Document(
            internship_id=self.internship_a.id,
            student_id=self.student_a.id,
            document_type='Offer Letter',
            file_path='student_a_offer.pdf',
            status='pending'
        )
        db.session.add(doc)
        db.session.commit()
        
        # Log in as Student B
        self.login('studentb@test.com')
        
        # Download Student A's document -> 403 Forbidden
        response_dl = self.client.get(f'/student/documents/download/{doc.id}')
        self.assertEqual(response_dl.status_code, 403)
        
        # View Student A's document -> 403 Forbidden
        response_view = self.client.get(f'/student/documents/view/{doc.id}')
        self.assertEqual(response_view.status_code, 403)

if __name__ == '__main__':
    unittest.main()
