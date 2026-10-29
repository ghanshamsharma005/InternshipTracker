from datetime import datetime, timezone
from database.db import db

class TimelineEvent(db.Model):
    __tablename__ = 'timeline_events'

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internships.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # completed, in_progress, pending, overdue
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    internship = db.relationship('Internship', backref=db.backref('timeline_events', cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<TimelineEvent '{self.title}' (Status: {self.status})>"
