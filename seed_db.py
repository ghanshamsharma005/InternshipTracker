"""
Database Seeder Script for InternTrack.
Populates initial sample roles, users, companies, internships, timeline events,
deadlines, and evaluations for instant local demonstration.
"""

from datetime import datetime, date, timedelta, timezone
from werkzeug.security import generate_password_hash
from app import create_app
from config import Config
from database.db import db
from models import (
    User, Student, Faculty, Company, Internship,
    Document, TimelineEvent, ProgressReport, Deadline, Evaluation, Notification
)
from routes.student import generate_timeline_events, generate_deadlines

def seed_database():
    app = create_app(Config)
    with app.app_context():
        print("Re-initializing database schema...")
        db.create_all()
        
        # Check if users already exist
        if User.query.count() > 0:
            print("Database already contains records. Clearing existing records for clean seed...")
            db.drop_all()
            db.create_all()
            
        print("Seeding initial users and data...")
        
        # 1. Create Admin Account
        admin_user = User(
            name="Dr. Eleanor Vance",
            email="admin@interntrack.edu",
            password_hash=generate_password_hash("adminpassword123"),
            role="admin",
            is_active=True
        )
        db.session.add(admin_user)
        
        # 2. Create Faculty Account
        faculty_user = User(
            name="Prof. Alan Turing",
            email="faculty@interntrack.edu",
            password_hash=generate_password_hash("facultypassword123"),
            role="faculty",
            is_active=True
        )
        db.session.add(faculty_user)
        db.session.commit()
        
        faculty_profile = Faculty(
            user_id=faculty_user.id,
            employee_id="FAC-CS-001",
            department="Computer Science & Engineering"
        )
        db.session.add(faculty_profile)
        
        # 3. Create Companies
        comp_quantum = Company(
            company_name="Quantum Dynamics Inc",
            industry="Quantum Computing & AI",
            address="701 Pike St, Seattle, WA 98101",
            website="https://quantumdynamics.io",
            email="hr@quantumdynamics.io",
            contact_person="Sarah Connor",
            phone="+1-206-555-0192"
        )
        comp_google = Company(
            company_name="Google Cloud",
            industry="Software & Cloud Infrastructure",
            address="1600 Amphitheatre Pkwy, Mountain View, CA 94043",
            website="https://cloud.google.com",
            email="campus-interns@google.com",
            contact_person="Sundar Pichai",
            phone="+1-650-253-0000"
        )
        comp_microsoft = Company(
            company_name="Microsoft Research",
            industry="Artificial Intelligence",
            address="One Microsoft Way, Redmond, WA 98052",
            website="https://research.microsoft.com",
            email="msr-hiring@microsoft.com",
            contact_person="Satya Nadella",
            phone="+1-425-882-8080"
        )
        db.session.add_all([comp_quantum, comp_google, comp_microsoft])
        db.session.commit()
        
        # 4. Create Students
        # Student 1: Ada Lovelace (Active, in progress)
        ada_user = User(
            name="Ada Lovelace",
            email="student@interntrack.edu",
            password_hash=generate_password_hash("studentpassword123"),
            role="student",
            is_active=True
        )
        db.session.add(ada_user)
        db.session.commit()
        
        ada_student = Student(
            user_id=ada_user.id,
            roll_no="CS-2026-001",
            course="Computer Science",
            semester=6,
            phone="+1-555-0144"
        )
        db.session.add(ada_student)
        db.session.commit()
        
        today = date.today()
        ada_internship = Internship(
            student_id=ada_student.id,
            company_id=comp_quantum.id,
            role="Quantum Systems Engineering Intern",
            description="Working on superconducting qubit calibration and quantum circuit simulators.",
            start_date=today - timedelta(days=28),
            end_date=today + timedelta(days=56),
            internship_type="hybrid",
            supervisor_name="Dr. Richard Feynman",
            supervisor_email="feynman@quantumdynamics.io",
            supervisor_phone="+1-206-555-0149",
            status="active"
        )
        db.session.add(ada_internship)
        db.session.commit()
        
        # Generate timeline and deadlines for Ada
        generate_timeline_events(ada_internship)
        generate_deadlines(ada_internship)
        
        # Add sample progress report for Ada (Week 1)
        ada_report = ProgressReport(
            internship_id=ada_internship.id,
            student_id=ada_student.id,
            week_number=1,
            tasks_completed="Configured quantum simulation toolchain and benchmarked noise models in Python.",
            skills_learned="Qiskit SDK, Noise mitigation techniques, Unitary operators",
            challenges="Handling high decoherence simulations at scale.",
            hours_worked=40.0,
            status="approved",
            feedback="Outstanding initial work on noise mitigation matrices."
        )
        db.session.add(ada_report)
        
        # Add a notification for Ada
        ada_notif = Notification(
            user_id=ada_user.id,
            title="Welcome to InternTrack",
            message="Your internship at Quantum Dynamics Inc has been approved by Prof. Alan Turing."
        )
        db.session.add(ada_notif)
        
        # Student 2: John von Neumann (Completed Internship)
        john_user = User(
            name="John von Neumann",
            email="john@interntrack.edu",
            password_hash=generate_password_hash("studentpassword123"),
            role="student",
            is_active=True
        )
        db.session.add(john_user)
        db.session.commit()
        
        john_student = Student(
            user_id=john_user.id,
            roll_no="CS-2026-002",
            course="Computer Science",
            semester=6,
            phone="+1-555-0188"
        )
        db.session.add(john_student)
        db.session.commit()
        
        john_internship = Internship(
            student_id=john_student.id,
            company_id=comp_google.id,
            role="Cloud Systems Architecture Intern",
            description="Designed geo-distributed key-value store cache layer.",
            start_date=today - timedelta(days=90),
            end_date=today - timedelta(days=6),
            internship_type="offline",
            supervisor_name="Ken Thompson",
            supervisor_email="ken@google.com",
            supervisor_phone="+1-650-253-0199",
            status="completed"
        )
        db.session.add(john_internship)
        db.session.commit()
        
        generate_timeline_events(john_internship)
        generate_deadlines(john_internship)
        
        # Complete all timeline events for John
        for ev in TimelineEvent.query.filter_by(internship_id=john_internship.id).all():
            ev.status = "completed"
        for dl in Deadline.query.filter_by(internship_id=john_internship.id).all():
            dl.status = "completed"
            
        # Evaluation for John
        john_eval = Evaluation(
            internship_id=john_internship.id,
            student_id=john_student.id,
            faculty_id=faculty_profile.id,
            technical_skills=10,
            communication=9,
            punctuality=10,
            work_quality=10,
            discipline=10,
            feedback="Phenomenal architecting of distributed load balancer infrastructure.",
            overall_score=9.8
        )
        db.session.add(john_eval)
        
        # Student 3: Grace Hopper (Pending Placement Registration)
        grace_user = User(
            name="Grace Hopper",
            email="grace@interntrack.edu",
            password_hash=generate_password_hash("studentpassword123"),
            role="student",
            is_active=True
        )
        db.session.add(grace_user)
        db.session.commit()
        
        grace_student = Student(
            user_id=grace_user.id,
            roll_no="IT-2026-003",
            course="Information Technology",
            semester=6,
            phone="+1-555-0177"
        )
        db.session.add(grace_student)
        db.session.commit()
        
        grace_internship = Internship(
            student_id=grace_student.id,
            company_id=comp_microsoft.id,
            role="Compiler Optimization Intern",
            description="Researching intermediate representation optimization passes.",
            start_date=today + timedelta(days=14),
            end_date=today + timedelta(days=98),
            internship_type="online",
            supervisor_name="Anders Hejlsberg",
            supervisor_email="anders@microsoft.com",
            supervisor_phone="+1-425-882-0122",
            status="pending"
        )
        db.session.add(grace_internship)
        
        db.session.commit()
        print("=" * 60)
        print("DATABASE SEEDED SUCCESSFULLY WITH DEMO DATA!")
        print("=" * 60)
        print("Default Demo Accounts:")
        print("1. Administrator : admin@interntrack.edu   | adminpassword123")
        print("2. Faculty       : faculty@interntrack.edu | facultypassword123")
        print("3. Student (Ada) : student@interntrack.edu | studentpassword123")
        print("4. Student (John): john@interntrack.edu    | studentpassword123")
        print("5. Student(Grace): grace@interntrack.edu   | studentpassword123")
        print("=" * 60)

if __name__ == "__main__":
    seed_database()
