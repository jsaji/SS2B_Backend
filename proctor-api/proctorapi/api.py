"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""

from flask import Blueprint, jsonify, request, make_response, current_app
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from sqlalchemy import exc
from functools import wraps
from .models import db, User, Exam, ExamRecording, ExamWarning
import jwt
import json

api = Blueprint('api', __name__)

@api.route('/')
def index():
    response = { 'Status': "API is up and running!" }
    return make_response(jsonify(response), 200)


@api.route('/register', methods=('POST',))
def register():
    try:
        data = request.get_json()
        user = User(**data)
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


@api.route('/login', methods=('POST',))
def login():
    data = request.get_json()
    user = User.authenticate(**data)

    if not user:
        return jsonify({ 'message': 'Invalid credentials', 'authenticated': False }), 401

    token = jwt.encode({
        'sub': user.email,
        'iat':str(datetime.utcnow()),
        'exp': str(datetime.utcnow() + timedelta(minutes=30))},
        current_app.config['SECRET_KEY'])
    student_id = User.query.filter_by(email=data['email']).first().student_id
    is_admin = User.query.filter_by(email=data['email']).first().is_admin
    return jsonify({ 'student_id': student_id , 'is_admin': is_admin, 'token': token.decode('UTF-8') }), 200

@api.route('/examiner/exam/create', methods=('POST',))
def create_exam():
    try:
        print("hola")
        # try get data
        # create the model and add to db
        # return successful message
        # return jsonify(u.to_dict()), 201
        return '', 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam/<int:exam_id>', methods=('GET',))
def get_exam():
    try:
        print("hola")
        # try get the exam
        # return successful message ->
        # return jsonify(u.to_dict()), 200
        return '', 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examiner/exam/update', methods=('POST',))
def update_exam():
    try:
        print("hola")
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam/delete/<int:exam_id>', methods=('DELETE',))
def delete_exam():
    try:
        print("hola")
        # try get existing exam
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording/create', methods=('POST',))
def create_exam_recording():
    try:
        print("hola")
        # try get data
        # create the model and add to db
        # return successful message
        # return jsonify(--.to_dict()), 200
        return '', 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording', methods=('GET',))
def get_exam_recording():
    try:
        user_id = request.args.get('user_id', default=-1, type=int)
        exam_id = request.args.get('exam_id', default=-1, type=int)
        if -1 in (user_id, exam_id):
            return jsonify({ 'message': 'Parameters user_id and exam_id are required' }), 404
        print("hola")
        # try get the exam recording
        # return successful message ->
        # return jsonify(u.to_dict()), 200
        return '', 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examinee/exam_recording/update', methods=('POST',))
def update_exam_recording():
    try:
        print("hola")
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_recording/delete', methods=('DELETE',))
def delete_exam_recording():
    try:
        user_id = request.args.get('user_id', default=-1, type=int)
        exam_id = request.args.get('exam_id', default=-1, type=int)
        if -1 in (user_id, exam_id):
            return jsonify({ 'message': 'Parameters user_id and exam_id are required' }), 404
        # try get existing exam recording
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/create', methods=('POST',))
def create_exam_warning():
    try:
        # try get data
        # create the model and add to db
        # return successful message
        # return jsonify(--.to_dict()), 201
        return '', 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning', methods=('GET',))
def get_exam_warning():
    try:
        exam_recording_id = request.args.get('exam_recording_id', default=-1, type=int)
        if exam_recording_id==-1:
            return jsonify({ 'message': 'Parameter exam_recording_id is required' }), 404
        # try get the exam recording
        # return successful message ->
        # return jsonify(u.to_dict()), 200
        return '', 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examiner/exam_warning/update', methods=('POST',))
def update_exam_warning():
    try:
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/delete', methods=('DELETE',))
def delete_exam_warning():
    try:
        exam_warning_id = request.args.get('exam_warning_id', default=-1, type=int)
        if exam_warning_id==-1:
            return jsonify({ 'message': 'Parameter exam_warning_id is required' }), 404
        # try get existing exam recording
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


# This is a decorator function which will be used to protect authentication-sensitive API endpoints
def token_required(f):
    @wraps(f)
    def _verify(*args, **kwargs):
        auth_headers = request.headers.get('Authorization', '').split()

        invalid_msg = {
            'message': 'Invalid token. Registeration and / or authentication required',
            'authenticated': False
        }
        expired_msg = {
            'message': 'Expired token. Reauthentication required.',
            'authenticated': False
        }

        if len(auth_headers) != 2:
            return jsonify(invalid_msg), 401

        try:
            token = auth_headers[1]
            data = jwt.decode(token, current_app.config['SECRET_KEY'])
            user = User.query.filter_by(email=data['sub']).first()
            if not user:
                raise RuntimeError('User not found')
            return f(user, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify(expired_msg), 401 # 401 is Unauthorized HTTP status code
        except (jwt.InvalidTokenError, Exception) as e:
            print(e)
            return jsonify(invalid_msg), 401

    return _verify
