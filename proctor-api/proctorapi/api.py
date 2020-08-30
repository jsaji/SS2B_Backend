"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""

from flask import Blueprint, jsonify, request, make_response, current_app, render_template, Response
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from sqlalchemy import exc
from functools import wraps
from PIL import Image
from .models import db, User
import cv2
import time
import jwt
import os
import numpy
import pickle

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

@api.route('/video-capture', methods=('POST',))
def video_capture():

    data = request.get_json()
    user = User.authenticate(**data)

    if not user:
        return jsonify({ 'message': 'Invalid credentials', 'authenticated': False }), 401

    student_id = User.query.filter_by(email=data['email']).first().student_id

    face_cascade = cv2.CascadeClassifier('cascades/haarcascade_frontalface_alt2.xml')
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.write("trainer.yml")

    video = cv2.VideoCapture(0)     #Access camera
    count = 0                       #Search fail count, total 3 allowed
    while count < 3 and video.isOpened():

        status, image = video.read()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.5, minNeighbors=5)

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y + h, x:x + w]

            color = (0, 255, 0)
            stroke = 2
            cv2.rectangle(image, (x, y), (x + w, y + h), color, stroke)

            y_labels = []
            x_train = []
            current_id = 0
            label_ids = {}

            for root, dirs, files in os.walk('images/' + str(student_id)):
                for file in files:
                    if file.endswith("png") or file.endswith("jpg"):

                        path = os.path.join(root, file)
                        label = os.path.basename(root).replace(" ", "-").lower()
                        if label in label_ids:
                            pass
                        else:
                            label_ids[label] = current_id
                            current_id += 1
                        id_ = label_ids[label]

                        pil_image = Image.open(path).convert("L")  # grayscale
                        image_array = numpy.array(pil_image, "uint8")

                        roi = image_array[y:y + h, x:x + w]
                        x_train.append(roi)
                        y_labels.append(id_)  # verify image, convert to NUMPY arr and gray

                        recognizer.train(x_train, numpy.array(y_labels))
                        recognizer.write("trainer.yml")
                        recognizer.read("trainer.yml")

                        id_, conf = recognizer.predict(roi_gray)
                        if conf >= 45 and conf <= 85:
                            print(True)
                            return jsonify({ 'student_id': student_id, 'positive_id': True }), 200

            with open("label.pickle", 'wb') as f:
                pickle.dump(label_ids, f)

        count += 1

    return jsonify({ 'message': 'Student not found', 'positive_id': False }), 500