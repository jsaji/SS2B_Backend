"""
models.py
- Data classes for the quantumapi application
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship
#from sqlalchemy.ext.declarative import declarative_base
#from sqlalchemy_imageattach.entity import Image, image_attachment
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(INTEGER(unsigned=True), primary_key=True, unique=True, autoincrement=False)
    first_name = db.Column(db.String(191), nullable=False)
    last_name = db.Column(db.String(191), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_examiner = db.Column(db.Integer)
    auth_image = db.Column(db.String(255), nullable = True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow())
    updated_date = db.Column(db.DateTime, default=datetime.utcnow())
    
    exam_recordings = relationship("ExamRecording", backref="users")

    def __init__(self, user_id, first_name, last_name, password, **kwargs):
        self.user_id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.password = generate_password_hash(password, method='sha256')
        self.is_examiner = 0
    
    @classmethod
    def authenticate(cls, **kwargs):
        user_id = kwargs.get('user_id')
        password = kwargs.get('password')
  
        if not user_id or not password:
            return None

        user = cls.query.filter_by(user_id=user_id).first()
        if not user or not check_password_hash(user.password, password):
            return None

        return user

    def to_dict(self):
        return dict(id=self.user_id)


class Exam(db.Model):
    __tablename__ = 'exams'
    
    exam_id = db.Column(INTEGER(unsigned=True), primary_key=True)
    exam_name = db.Column(db.String(500), nullable=False)
    subject_id = db.Column(db.Integer)
    login_code = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow())
    end_date = db.Column(db.DateTime, default=datetime.utcnow())
    duration = db.Column(db.Integer)

    exam_recordings = relationship('ExamRecording', uselist=False, backref="exams")

    def __init__(self, exam_name, subject_id, login_code, start_date, end_date, duration, **kwargs):
        self.exam_name = exam_name
        self.subject_id = subject_id
        self.login_code = login_code
        self.start_date = start_date
        self.end_date = end_date
        self.duration = duration

    def to_dict(self):
        return {
            'exam_id':self.exam_id,
            'exam_name':self.exam_name,
            'subject_id':self.subject_id,
            'login_code':self.login_code,
            'start_date':self.start_date,
            'end_date':self.end_date,
            'duration':self.duration
        }


class ExamRecording(db.Model):
    __tablename__ = 'examRecordings'
    
    exam_recording_id = db.Column(INTEGER(unsigned=True), primary_key=True)
    exam_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('exams.exam_id'), nullable=False)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('users.user_id'), nullable=False)
    time_started = db.Column(db.DateTime, nullable=True)
    time_ended = db.Column(db.DateTime, nullable=True)
    video_link = db.Column(db.String(255), nullable=True)
    
    warnings = relationship("ExamWarning", backref='examRecordings')

    def __init__(self, exam_id, user_id):
        self.exam_id = exam_id
        self.user_id = user_id

    def to_dict(self):
        return {
            'exam_recording_id':self.exam_recording_id,
            'exam_id':self.exam_id,
            'user_id':self.user_id,
            'time_started':self.time_started,
            'time_ended':self.time_ended,
            'video_link':self.video_link
        }

class ExamWarning(db.Model):
    __tablename__ = 'examWarnings'
    
    warning_id = db.Column(INTEGER(unsigned=True), primary_key=True)
    exam_recording_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('examRecordings.exam_recording_id'), nullable=False)
    warning_time = db.Column(db.DateTime, default=datetime.utcnow())
    description = db.Column(db.String(500), nullable=False)

    def __init__(self, exam_recording_id, warning_time, description):
        self.exam_recording_id = exam_recording_id
        self.warning_time = warning_time
        self.description = description

    def to_dict(self):
        return {
            'warning_id':self.warning_id,
            'exam_recording_id':self.exam_recording_id,
            'warning_time':self.warning_time,
            'description':self.description
        }
