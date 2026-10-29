from datetime import datetime, timezone
from database.db import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, faculty, admin
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    roll_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    course = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to user
    user = db.relationship('User', backref=db.backref('student', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Student {self.roll_no}>"


class Faculty(db.Model):
    __tablename__ = 'faculty'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)

    # Relationship to user
    user = db.relationship('User', backref=db.backref('faculty', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<Faculty {self.employee_id}>"


class UserProfileImage(db.Model):
    __tablename__ = 'user_profile_images'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mimetype = db.Column(db.String(50), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)  # Stored directly as SQLite BLOB
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to user
    user = db.relationship('User', backref=db.backref('profile_image', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<UserProfileImage for User ID {self.user_id}>"

