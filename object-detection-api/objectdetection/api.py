"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""
from flask import Blueprint, jsonify, request, make_response, current_app, render_template, Response
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage
from urllib3.exceptions import MaxRetryError
import requests
from dateutil import parser
from sqlalchemy import exc, func
from functools import wraps
from .models import db, User, Exam, ExamRecording, ExamWarning, required_fields
from .services.misc import generate_exam_code, confirm_examiner, pre_init_check, InvalidPassphrase, MissingModelFields, datetime_to_str, parse_datetime
from six.moves.urllib.request import urlopen
from six import BytesIO
from PIL import Image
from PIL import ImageColor
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps
import jwt
import json
import math
import cv2
import os
import numpy as np
import pickle
import tensorflow as tf
import tensorflow_hub as hub
import matplotlib.pyplot as plt
import tempfile
import time

api = Blueprint('api', __name__)

ODAPI_URL = 'http://127.0.0.1:8000/'

# globally load detector to reduce inference time on repeated requests
module_handle = "https://tfhub.dev/google/faster_rcnn/openimages_v4/inception_resnet_v2/1" #@param ["https://tfhub.dev/google/openimages_v4/ssd/mobilenet_v2/1", "https://tfhub.dev/google/faster_rcnn/openimages_v4/inception_resnet_v2/1"]

detector = hub.load(module_handle).signatures['default']



@api.route('/')
def index():
    """
    API health check
    """
    response = { 'Status': "API is up and running!" }
    return make_response(jsonify(response), 200)


# Returns JSON with classes found in images
@api.route('/detect', methods=['POST'])
def get_detections():
    try:
        downloaded_image_path = download_and_resize_image(image_url, 640, 480, True)

        response = run_detector(detector, downloaded_image_path)

        #remove temporary images
        for name in image_names:
            os.remove(name)
        
        try:
            return jsonify(response), 200
        except FileNotFoundError:
            abort(404)
        
    except tf.errors.InvalidArgumentError as e:
        return jsonify({'message':'Wrong file type used'}), 400
    except FileNotFoundError as e:
        return jsonify({'message':e.args}), 404


# Returns image with detections on it
@api.route('/image', methods= ['POST'])
def get_image():
    try:
        image = request.files["images"]
        image_name = image.filename
        image.save(os.path.join(os.getcwd(), image_name))
        img_raw = tf.image.decode_image(
            open(image_name, 'rb').read(), channels=3)
        img = tf.expand_dims(img_raw, 0)
        img = transform_images(img, SIZE)

        t1 = time.time()
        boxes, scores, classes, nums = yolo(img)
        t2 = time.time()
        
        print('time: {}'.format(t2 - t1))

        print('detections:')
        for i in range(nums[0]):
            print('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                            np.array(scores[0][i]),
                                            np.array(boxes[0][i])))

        img = save_image(img_raw, 0, (boxes, scores, classes, nums), return_img=True)
        # prepare image for response
        _, img_encoded = cv2.imencode('.png', img)
        response = img_encoded.tostring()
        
        #remove temporary image
        os.remove(image_name)

        try:
            return Response(response=response, status=200, mimetype='image/png')
        except FileNotFoundError:
            abort(404)
    except tf.errors.InvalidArgumentError as e:
        return jsonify({'message':'Wrong file type used'}), 400
    except FileNotFoundError as e:
        return jsonify({'message':e.args}), 404


def save_image(raw_img, num, outputs, return_img=False):
    img = cv2.cvtColor(raw_img.numpy(), cv2.COLOR_RGB2BGR)
    img = draw_outputs(img, outputs, class_names, unallowed_class_names)
    cv2.imwrite(OUTPUT_PATH + 'detection' + str(num) + '.jpg', img)
    print('output saved to: {}'.format(OUTPUT_PATH + 'detection' + str(num) + '.jpg'))
    if return_img:
        return img
    return None


def save_image(image, fn):
    final_img = Image.fromarray(image)
    final_img.save('{0}.png'.format(fn))


def download_and_resize_image(url, new_width=256, new_height=256,
                              display=False):
    _, filename = tempfile.mkstemp(suffix=".jpg")
    response = urlopen(url)
    image_data = response.read()
    image_data = BytesIO(image_data)
    pil_image = Image.open(image_data)
    pil_image = ImageOps.fit(pil_image, (new_width, new_height), Image.ANTIALIAS)
    pil_image_rgb = pil_image.convert("RGB")
    pil_image_rgb.save(filename, format="JPEG", quality=90)
    print("Image downloaded to %s." % filename)

    return filename


def draw_bounding_box_on_image(image,
                               ymin,
                               xmin,
                               ymax,
                               xmax,
                               color,
                               font,
                               thickness=4,
                               display_str_list=()):
    """Adds a bounding box to an image."""
    draw = ImageDraw.Draw(image)
    im_width, im_height = image.size
    (left, right, top, bottom) = (xmin * im_width, xmax * im_width,
                                ymin * im_height, ymax * im_height)
    draw.line([(left, top), (left, bottom), (right, bottom), (right, top),
             (left, top)],
            width=thickness,
            fill=color)

    # If the total height of the display strings added to the top of the bounding
    # box exceeds the top of the image, stack the strings below the bounding box
    # instead of above.
    display_str_heights = [font.getsize(ds)[1] for ds in display_str_list]
    # Each display_str has a top and bottom margin of 0.05x.
    total_display_str_height = (1 + 2 * 0.05) * sum(display_str_heights)

    if top > total_display_str_height:
        text_bottom = top
    else:
        text_bottom = top + total_display_str_height
        # Reverse list and print from bottom to top.
        for display_str in display_str_list[::-1]:
            text_width, text_height = font.getsize(display_str)
            margin = np.ceil(0.05 * text_height)
            draw.rectangle([(left, text_bottom - text_height - 2 * margin),
                            (left + text_width, text_bottom)],
                           fill=color)
            draw.text((left + margin, text_bottom - text_height - margin),
                      display_str,
                      fill="black",
                      font=font)
            text_bottom -= text_height - 2 * margin


def draw_boxes(image, boxes, class_names, scores, max_boxes=10, min_score=0.10):
  """Overlay labeled boxes on an image with formatted scores and label names."""
  colors = list(ImageColor.colormap.values())
  font = ImageFont.load_default()
  preds = []
  objects = {}
  for i in range(min(boxes.shape[0], max_boxes)):
    if scores[i] >= min_score:
      ymin, xmin, ymax, xmax = tuple(boxes[i])
      display_str = "{}: {}%".format(class_names[i].decode("ascii"),
                                     int(100 * scores[i]))
      
      objects.append({
        "class": class_names[i].decode("ascii"),
        "confidence": int(100 * scores[i]),
        "bounding box": [ymin, xmin, ymax, xmax]
        })

      color = colors[hash(class_names[i]) % len(colors)]
      image_pil = Image.fromarray(np.uint8(image)).convert("RGB")
      draw_bounding_box_on_image(
          image_pil,
          ymin,
          xmin,
          ymax,
          xmax,
          color,
          font,
          display_str_list=[display_str])
      np.copyto(image, np.array(image_pil))
    preds.append(objects)

  return image, preds


def load_img(path):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    return img


def run_detector(detector, path, fn):
  img = load_img(path)

  converted_img  = tf.image.convert_image_dtype(img, tf.float32)[tf.newaxis, ...]
  start_time = time.time()
  result = detector(converted_img)
  end_time = time.time()

  result = {key:value.numpy() for key,value in result.items()}

  image_with_boxes, preds = draw_boxes(
      img.numpy(), result["detection_boxes"],
      result["detection_class_entities"], result["detection_scores"])

  return preds

if __name__ == '__main__':
    app.run(debug=True, host = '0.0.0.0', port=8000)



