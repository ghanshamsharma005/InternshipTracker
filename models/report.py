from datetime import datetime, timezone
from database.db import db

class ProgressReport(db.Model):
    __tablename__ = 'progress_reports'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    tasks_completed = db.Column(db.Text, nullable=True)
    skills_learned = db.Column(db.Text, nullable=True)
    challenges = db.Column(db.Text, nullable=True)
    hours_worked = db.Column(db.Float, nullable=True)
    report_file = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='submitted', nullable=False)  # e.g., submitted, approved, rejected
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    feedback = db.Column(db.Text, nullable=True)

    # Relationships
    internship = db.relationship('Internship', backref=db.backref('progress_reports', cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('progress_reports', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<ProgressReport Week {self.week_number} (Internship ID: {self.internship_id})>"
