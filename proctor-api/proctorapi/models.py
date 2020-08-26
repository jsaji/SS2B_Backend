"""
models.py
- Data classes for the quantumapi application
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_imageattach.entity import Image, image_attachment
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(191), nullable=False)
    last_name = db.Column(db.String(191), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    confirm_examiner = db.Column(db.String(255), nullable=True)
    auth_image = db.Column(db.String(255), nullable = False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow)
    

    exams = relationship("Exam")

    def __init__(self, user_id, first_name, last_name, password, confirm_examiner):
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.password = generate_password_hash(password, method='sha256')
        self.confirm_examiner = generate_password_hash(confirm_admin, method='sha256')
    
       @classmethod
           def authenticate(cls, **kwargs):
               email = kwargs.get('email')
               password = kwargs.get('password')
  
       if not email or not password:
         return None

         user = cls.query.filter_by(email=email).first()
      if not user or not check_password_hash(user.password, password):
         return None

       return user

     def to_dict(self):
      return dict(id=self.user_id, email=self.email)

class Exam(db.Model):
    __tablename__ = 'exam'
    
    exam_id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer)
    exam_name = db.Column(db.String(500), nullable=False)
    login_code = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, default=datetime.utcnow)
    duration = db.Column(db.Integer )

    def __init__(self, exam_id, exam_name, subject_id, login_code):
        self.exam_id = exam_id
        self.exam_name = exam_name
        self.subject_id = subject_id
        self.login_code = login_code

class ExamRecording(db.Model):
    __tablename__ = 'examRecording'
    
    exam_id = db.column(db.Integer, ForeignKey('exam.id'), primary_key=True)
    user_id = db.column (db.Integer, ForeignKey('user.id'), primary_key=True)
    examrecording_id = db.column (db.Integer, nullable = False)
    time_started = db.Column(db.DateTime, default=datetime.utcnow)
    time_ended = db.Column(db.DateTime, default=datetime.utcnow)
    misconduct_count = db.Column(db.Integer, nullable = False)
    video_link = db.Column(db.String(255), nullable = False)

class ExamWarning(db.Model):
    __tablename__ = 'examWarning'
    
    warning_id = db.column (db.Integer, primary_key=True)
    exam_id = db.column(db.Integer, ForeignKey('exam.id'))
    user_id = db.column (db.Integer, ForeignKey('user.id'))
    examrecording_id = db.column (db.Integer, ForeignKey('examrecording.id'))
    warning_time = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.column(db.String(500), nullable = False)