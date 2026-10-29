from database.db import db

class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    website = db.Column(db.String(200), nullable=True)
    industry = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Company {self.company_name}>"
