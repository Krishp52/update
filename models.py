from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    return_rate = db.Column(db.Float, nullable=False)
    investments = db.relationship('Investment', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    family_member = db.Column(db.String(50), nullable=False)
    current_value = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Investment {self.family_member} - {self.current_value}>'

class AppData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    data = db.Column(db.Text, nullable=False)