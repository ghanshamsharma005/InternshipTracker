from datetime import datetime, timezone
from database.db import db

class Internship(db.Model):
    __tablename__ = 'internships'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True)
    role = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    internship_type = db.Column(db.String(50), nullable=True)  # online, offline, hybrid
    supervisor_name = db.Column(db.String(100), nullable=True)
    supervisor_email = db.Column(db.String(120), nullable=True)
    supervisor_phone = db.Column(db.String(20), nullable=True)

    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, approved, active, completed, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('internships', cascade='all, delete-orphan'))
    company = db.relationship('Company', backref=db.backref('internships'))


    def __repr__(self):
        return f"<Internship {self.role} for Student ID {self.student_id}>"
