from datetime import datetime, timezone
from database.db import db

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, verified, rejected
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # Relationships
    internship = db.relationship('Internship', backref=db.backref('documents', cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('documents', cascade='all, delete-orphan'))
    verifier = db.relationship('User', foreign_keys=[verified_by], backref='verified_documents')

    def __repr__(self):
        return f"<Document {self.document_type} (Status: {self.status})>"
