from datetime import datetime
from database.db import db

class Deadline(db.Model):
    __tablename__ = 'deadlines'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, completed, overdue
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationship
    internship = db.relationship('Internship', backref=db.backref('deadlines', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Deadline '{self.title}' (Due: {self.due_date})>"
