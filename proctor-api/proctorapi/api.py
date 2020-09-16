"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""

from flask import Blueprint, jsonify, request, make_response, current_app
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from dateutil import parser
from sqlalchemy import exc, func
from functools import wraps
from .models import db, User, Exam, ExamRecording, ExamWarning, required_fields
from .services.misc import generate_exam_code, confirm_examiner, pre_init_check, InvalidPassphrase, MissingModelFields, datetime_to_str
import jwt
import json
import math

api = Blueprint('api', __name__)

@api.route('/')
def index():
    """
    API health check
    """
    response = { 'Status': "API is up and running!" }
    return make_response(jsonify(response), 200)


@api.route('/register', methods=('POST',))
def register():
    """
    Register new users, examiners or examineers
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['user'], **data)
        user = User(**data)
        if data.get('examiner_passphrase'):
            is_examiner = confirm_examiner(data['examiner_passphrase'])
            if not is_examiner:
                raise InvalidPassphrase()
            user.is_examiner = True
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except (MissingModelFields, InvalidPassphrase) as e:
        return jsonify({ 'message': e.args }), 400
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({ 'message': 'User with user_id {} exists.'.format(data['user_id']) }), 409
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/login', methods=('POST',))
def login():
    """
    Login for existing users
    """
    data = request.get_json()
    user = User.authenticate(**data)

    if not user:
        return jsonify({ 'message': 'Invalid credentials', 'authenticated': False }), 401

    token = jwt.encode({
        'sub': user.user_id,
        'iat':str(datetime.utcnow()),
        'exp': str(datetime.utcnow() + timedelta(minutes=30))},
        current_app.config['SECRET_KEY'])
    user_id = data['user_id']
    user = User.query.get(user_id)
    return jsonify({ 'user': user.to_dict(), 'token': token.decode('UTF-8') }), 200


@api.route('/examiner/exam/create', methods=('POST',))
def create_exam():
    """
    Creates new exam record
    """
    try:
        data = request.get_json()
        # Checks if data has required fields - throws exception if not
        pre_init_check(required_fields['exam'], **data)

        code_found = False
        while not code_found:
            # Generates unique exam code until one is found that does not already exist
            potential_login_code = generate_exam_code()
            code_exists = Exam.query.filter_by(login_code=potential_login_code).first()
            if not code_exists:
                data['login_code'] = potential_login_code
                break
        exam = Exam(**data)
        db.session.add(exam)
        db.session.commit()
        return jsonify(exam.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam', methods=('GET',))
def get_exam():
    """
    Gets existing exam records, can be filtered with exam_id and login_code.
    Returned results are limited by results_length and page_number.
    """
    try:
        # Query to run
        results_query = db.session.query(Exam, func.count(ExamRecording.exam_id)).\
                        outerjoin(Exam, Exam.exam_id==ExamRecording.exam_id).\
                        group_by(ExamRecording.exam_id)
        # Filters query results using request params
        results, next_page_exists = filter_results(results_query, Exam)
        exams = []
        for e, er_count in results:
            exams.append({
                **e.to_dict(),
                'exam_recordings':er_count
            })
        return jsonify({'exams':exams, 'next_page_exists': next_page_exists}), 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examiner/exam/update', methods=('POST',))
def update_exam(): #arpita to do
    """
    Updates an existing exam record, dependent on whether it has already started
    """
    try:
        print("hola")
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        data = request.json()

        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam/delete/<int:exam_id>', methods=('DELETE',))
def delete_exam():
    """
    Deletes an existing exam record, dependent on whether it has already started
    """
    try:
        exam = Exam.query.get(exam_id)
        if exam <= start_date:
            # db.session.delete(exam)
            # db.session.commit()
            print("hola")
            return '', 204
        return jsonify({'message':'Exam with id {} could not be found'}), 404
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


@api.route('/examinee/exam_recording/create', methods=('POST',))
def create_exam_recording():
    """
    Creates new exam recording record
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['examrecording'], **data)
        examRecording = ExamRecording(**data)
        db.session.add(examRecording)
        db.session.commit()
        return jsonify(examRecording.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording', methods=('GET',))
def get_exam_recording():
    """
    Gets exam recordings, can be filtered by user_id, exam_id
    Returned results are limited by results_length and page_number.
    """
    try:
        results_query = db.session.query(User, Exam, ExamRecording, func.count(ExamWarning.exam_recording_id)).\
                        filter(User.user_id==ExamRecording.user_id).\
                        filter(Exam.exam_id==ExamRecording.exam_id).\
                        outerjoin(ExamWarning, ExamWarning.exam_recording_id==ExamRecording.exam_recording_id).\
                        group_by(ExamRecording.exam_recording_id)
                        
        results, next_page_exists = filter_results(results_query, ExamRecording)

        exam_recordings = []
        for u, e, er, ew_count in results:
            exam_recordings.append({
                'user_id':u.user_id,
                'first_name':u.first_name,
                'last_name':u.last_name,
                'exam_id':e.exam_id,
                'exam_name':e.exam_name,
                'subject_id':e.subject_id,
                'time_started':datetime_to_str(er.time_started),
                'time_ended':datetime_to_str(er.time_ended),
                'video_link':er.video_link,
                'warning_count':ew_count
            })
        return jsonify({'exam_recordings':exam_recordings, 'next_page_exists':next_page_exists}), 200

    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examinee/exam_recording/update', methods=('POST',))
def update_exam_recording():
    """
    Updates existing exam recording record, limited by the parameter action (start, end, video_link)
    """
    try:
        
        # Gets action, either start or end
        action = request.args.get('action', default='').lower()
        
        data = request.json()
        # Preliminary checks
        if not data.get('exam_recording_id'):
            return jsonify({'message':'No exam_recording_id included in payload'}), 400
        
        exam_recording_id = data['exam_recording_id']
        exam_recording = ExamRecording.query.get(exam_recording_id)
        if exam_recording is None:
            return jsonify({'message':'Exam recording with exam_recording_id {} not found'.format(exam_recording_id)}), 404
        
        # If start, start the exam recording, if end, end exam recording and save chanegs
        if action == 'start':
            exam_recording.time_started = datetime.utcnow()
        elif action == 'end':
            exam_recording.time_ended = datetime.utcnow()
        elif action == 'video_link':
            if not data.get('video_link'):
                return jsonify({'message':'No video_link included in payload'}), 400
            exam_recording.video_link = data['video_link']
        else:
            return jsonify({'message':'Include parameter action: start, end'}), 400
        
        db.session.commit()
        
        return jsonify({'message':'Exam recording has '+action+'ed for user_id {}'.format(exam_recording.user_id)}), 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_recording/delete/<int:exam_recording_id>', methods=('DELETE',))
def delete_exam_recording(exam_recording_id):
    """
    Deletes existing exam recording record.
    """
    try:
        exam_recording = ExamRecording.query.get(exam_recording_id)
        if exam_recording:
            db.session.delete(exam_recording)
            db.session.commit()
            return '', 204
        return jsonify({'message':'Exam recording with id {} could not be found'}), 404
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


@api.route('/examiner/exam_warning/create', methods=('POST',))
def create_exam_warning():
    """
    Creates new exam warning record
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['examwarning'], **data)
        exam_warning = ExamWarning(**data)
        db.session.add(exam_warning)
        db.session.commit()
        return jsonify(exam_warning.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning', methods=('GET',))
def get_exam_warning():
    """
    Gets existing exam warning records, can be filtered with exam_warning_id, exam_recording_id, warning_time.
    Returned results are limited by results_length and page_number.
    """
    try:

        results_query = db.session.query(User, Exam, ExamRecording, ExamWarning).\
                    filter(User.user_id==ExamRecording.user_id).\
                    filter(Exam.exam_id==ExamRecording.exam_id).\
                    filter(ExamWarning.exam_recording_id==ExamRecording.exam_recording_id).\
                    filter(User.is_examiner==False)

        # Filters results
        results, next_page_exists = filter_results(results_query, ExamWarning)

        payload = []
        
        for u, e, er, ew in results:
            payload.append({
                'user_id':u.user_id,
                'first_name':u.first_name,
                'last_name':u.last_name,
                'exam_id':e.exam_id,
                'exam_name':e.exam_name,
                'subject_id':e.subject_id,
                'exam_recording_id':er.exam_recording_id,
                'time_started':datetime_to_str(er.time_started),
                'time_ended':datetime_to_str(er.time_ended),
                'video_link':er.video_link,
                'exam_warning_id':ew.exam_warning_id,
                'warning_time':datetime_to_str(ew.warning_time),
                'description':ew.description
            })

        return jsonify({'exam_warnings':payload, 'next_page_exists':next_page_exists}), 200
    except exc.SQLAlchemyError as e:
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/update', methods=('POST',))
def update_exam_warning(): #arpita to do
    """
    Updates existing exam warning record.
    """
    try:
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(examwarning.to_dict()), 200
        action = request.args.get('action', default='').lower()

        data = request.json()

        if not data.get('exam_warning_id'):
            return jsonify({'message':'No exam_warning_id included in payload'}), 400

        exam_warning_id = data['exam_warning_id']
        exam_warning = ExamWarning.query.get(exam_warning_id)
        if exam_warning is None:
            return jsonify({'message':'Exam warning with exam_warning_id {} not found'.format(exam_warning_id)}), 404
        
        # update description
        if action == 'description':
            exam_warning.description = data['description']
        
        # update warning time
        if action == 'warning_time':
            exam_warning.warning_time = datetime.utcnow()
        
        # db.session.commit()
        return jsonify({'message':'Exam warning '+action+' has updated for exam_recording_id {}'.format(exam_warning.exam_recording_id)}), 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/delete', methods=('DELETE',))
def delete_exam_warning():
    """
    Deletes existing exam warning record.
    """
    try:
        exam_warning_id = request.args.get('exam_warning_id', default=-1, type=int)
        if exam_warning_id==-1:
            return jsonify({ 'message': 'Parameter exam_warning_id is required' }), 404
        # try get existing exam recording  
        # note from Arpita: if we've gotten the exam_warning_id above and checked that it exists, do we need to do it again?
        # check if we're allowed to delete it
        # if yes,
        if exam_warning_id:
            # db.session.delete(exam_warning_id)
            # db.session.commit()
            print("hola")
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


@api.route('/examiner/examinee', methods=('GET',))
def get_examinee():
    """
    Gets existing user records, can be filtered with user_id, first_name and last_name.
    Returned results are limited by results_length and page_number.
    """
    try:
        results_query = db.session.query(User, func.count(ExamRecording.exam_id), func.count(ExamWarning.exam_recording_id)).\
                        outerjoin(ExamRecording, User.user_id==ExamRecording.user_id).\
                        outerjoin(ExamWarning, ExamWarning.exam_recording_id==ExamRecording.exam_recording_id).\
                        group_by(User.user_id)

        results, next_page_exists = filter_results(results_query, User)
        users = []
        for u, er_count, ew_count in results:
            users.append({
                **u.to_dict(),
                'exam_recordings':er_count,
                'exam_warnings':ew_count
            })
        return jsonify({'users':users, 'next_page_exists':next_page_exists}), 200
    except exc.SQLAlchemyError as e:
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

def get_request_args():
    """
    Gets various request args
    """
    args = {}
    args['user_id'] = request.args.get('user_id', default=None, type=int)
    args['is_examiner'] = request.args.get('is_examiner', default=False, type=bool)
    args['first_name'] = request.args.get('first_name', default=None)
    args['last_name'] = request.args.get('last_name', default=None)

    args['exam_warning_id'] = request.args.get('exam_warning_id', default=None, type=int)
    args['exam_recording_id'] = request.args.get('exam_recording_id', default=None, type=int)
    args['in_progress'] = request.args.get('in_progress', default=None, type=str)
    args['exam_id'] = request.args.get('exam_id', default=None, type=int)
    args['subject_id'] = request.args.get('subject_id', default=None, type=int)
    args['login_code'] = request.args.get('login_code', default=None)
    args['exam_name'] = request.args.get('exam_name', default=None)

    args['warning_count'] = request.args.get('warning_count', default=None, type=int)
    args['min_warnings'] = request.args.get('min_warnings', default=None, type=int)
    args['max_warnings'] = request.args.get('max_warnings', default=None, type=int)

    args['period_start'] = request.args.get('period_start', default=timedelta(days=10))
    args['period_end'] = request.args.get('period_end', default=timedelta(days=10))
    if args['period_start'] == timedelta(days=10): args['period_start'] = None
    if args['period_end'] == timedelta(days=10): args['period_end'] = None
    args['order_by'] = request.args.get('order_by', default='default').lower()
    args['order'] = request.args.get('order', default='desc').lower()
    
    args['page_number'] = request.args.get('page_number', default=1, type=int)
    args['results_length'] = request.args.get('results_length', default=25, type=int)
    if args['page_number'] < 1: args['page_number'] = 1
    if args['results_length'] < 1: args['results_length'] = 1

    return args

def filter_results(results, main_class=None):
    """
    Filters results and orders them - takes in query and main_class to perform specific actions
    """
    # Gets request parameters/arguments
    args = get_request_args()
    # Big block of ifs to filter
    if args['user_id']: results = results.filter(User.user_id==args['user_id'])
    if args['first_name']: results = results.filter(User.first_name.startswith(args['first_name']))
    if args['last_name']: results = results.filter(User.last_name.startswith(args['last_name']))
    if args['is_examiner']: results = results.filter(User.is_examiner==args['is_examiner'])

    if args['exam_warning_id']: results = results.filter(ExamWarning.exam_warning_id==args['exam_warning_id'])
    if args['exam_recording_id']: results = results.filter(ExamRecording.exam_recording_id==args['exam_recording_id'])
    if args['subject_id']: results = results.filter(Exam.subject_id==args['subject_id'])
    if args['exam_name']: results = results.filter(Exam.exam_name.startswith(args['exam_name']))

    if main_class == ExamWarning:
        if args['period_start']: results = results.filter(ExamWarning.warning_time >= args['period_start'])
        if args['period_end']: results = results.filter(ExamWarning.warning_time <= args['period_end'])
        
        if args['order_by'] == 'something':
            pass
        else:
            if args['order'] == 'asc': results = results.order_by(ExamWarning.warning_time.asc())
            else: results = results.order_by(ExamWarning.warning_time.desc())

    elif main_class == ExamRecording:
        if args['exam_id']: results = results.filter(ExamRecording.exam_id==args['exam_id'])
        if args['warning_count']: results = results.having(func.count(ExamWarning.exam_recording_id)==args['warning_count'])
        if args['min_warnings']: results = results.having(func.count(ExamWarning.exam_recording_id)>=args['min_warnings'])
        if args['max_warnings']: results = results.having(func.count(ExamWarning.exam_recording_id)<=args['max_warnings'])
        if args['period_start']: results = results.filter(ExamRecording.time_started >= args['period_start'])
        if args['period_end']: results = results.filter(ExamRecording.time_ended <= args['period_end'])
        if args['in_progress'] is not None:
            if in_progress: results = results.filter(ExamRecording.time_ended is None)
            else: results = results.filter(ExamRecording.time_ended is not None)
        if args['order_by'] == 'time_ended':
            if args['order'] == 'asc': results = results.order_by(ExamRecording.time_ended.asc())
            else: results = results.order_by(ExamRecording.time_ended.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(ExamRecording.time_started.asc())
            else: results = results.order_by(ExamRecording.time_started.desc())

    elif main_class == Exam:
        if args['exam_id']: results = results.filter(Exam.exam_id==args['exam_id'])
        if args['login_code']: results = results.filter(Exam.login_code.startswith(args['login_code']))
        if args['period_start']: results = results.filter(Exam.start_date >= args['period_start'])
        if args['period_end']: results = results.filter(Exam.end_date <= args['period_end'])
        if args['in_progress'] is not None:
            if in_progress: results = results.filter(Exam.end_date >= datetime.utcnow())
            else: results = results.filter(Exam.end_date <= datetime.utcnow())
        if args['order_by'] == 'end_date':
            if args['order'] == 'asc': results = results.order_by(Exam.end_date.asc())
            else: results = results.order_by(Exam.start_date.desc())
        elif args['order_by'] == "exam_name":
            if args['order'] == 'asc': results = results.order_by(Exam.exam_name.asc())
            else: results = results.order_by(Exam.exam_name.desc())
        elif args['order_by'] == "subject_id":
            if args['order'] == 'asc': results = results.order_by(Exam.subject_id.asc())
            else: results = results.order_by(Exam.subject_id.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(Exam.start_date.asc())
            else: results = results.order_by(Exam.start_date.desc())

    elif main_class == User:
        if args['order_by'] == 'first_name':
            if args['order'] == 'asc': results = results.order_by(User.first_name.asc())
            else: results = results.order_by(User.first_name.desc())
        elif args['order_by'] == 'last_name':
            if args['order'] == 'asc': results = results.order_by(User.last_name.asc())
            else: results = results.order_by(User.last_name.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(User.user_id.asc())
            else: results = results.order_by(User.user_id.desc())

    # Calculates offset to limit the number of results returned
    offset = (args['page_number']-1)*args['results_length']
    results = results[offset:offset+args['results_length']+1]
    # Determines if next page exists, and deletes last extra row if it does
    next_page_exists = len(results) == args['results_length']+1
    if next_page_exists: del results[-1]

    return results, next_page_exists
    