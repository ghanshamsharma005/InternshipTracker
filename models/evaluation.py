from datetime import datetime, timezone
from database.db import db

class Evaluation(db.Model):
    __tablename__ = 'evaluations'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id', ondelete='CASCADE'), nullable=False)
    
    # Grading rubrics
    technical_skills = db.Column(db.Integer, nullable=False)  # Score scale
    communication = db.Column(db.Integer, nullable=False)
    punctuality = db.Column(db.Integer, nullable=False)
    work_quality = db.Column(db.Integer, nullable=False)
    discipline = db.Column(db.Integer, nullable=False)
    
    feedback = db.Column(db.Text, nullable=True)
    overall_score = db.Column(db.Float, nullable=False)
    evaluated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    internship = db.relationship('Internship', backref=db.backref('evaluations', cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('evaluations', cascade='all, delete-orphan'))
    faculty = db.relationship('Faculty', backref=db.backref('evaluations', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Evaluation (Overall: {self.overall_score}) for Internship ID {self.internship_id}>"
