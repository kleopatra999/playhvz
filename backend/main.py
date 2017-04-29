# [START app]
import logging

from firebase import firebase
from flask import Flask, jsonify, request
import flask_cors
from google.appengine.ext import ndb
import google.auth.transport.requests
import google.oauth2.id_token
import requests_toolbelt.adapters.appengine
import time

import constants

requests_toolbelt.adapters.appengine.monkeypatch()
HTTP_REQUEST = google.auth.transport.requests.Request()

app = Flask(__name__)
auth = firebase.FirebaseAuthentication(constants.FIREBASE_SECRET,
                                       constants.FIREBASE_EMAIL, admin=True)
firebase = firebase.FirebaseApplication('https://trogdors-29fa4.firebaseio.com', authentication=auth)
flask_cors.CORS(app)

class AppError(Exception):
  status_code = 500
  def __init__(self, message, status_code=None, payload=None):
    Exception.__init__(self)
    self.message = message
    if status_code is not None:
      self.status_code = status_code
      self.payload = payload

  def to_dict(self):
    rv = dict(self.payload or ())
    rv['message'] = self.message
    return rv


class InvalidInputError(AppError):
  pass


def ValidateInputs(present, valid):
  """Validate args.

  Args:
    present: These args must be present in the requst.
    valid: These args must already exist in the DB.
  """
  request_data = request.get_json()

  if any(a not in request_data for a in present):
    raise InvalidInputError('Missing required input. Required: %s' % ', '.join(present))

  request_data = request.get_json()
  for a in valid:
    data = request_data[a]
    if a == 'gameId':
      if not firebase.get('/games/%s/name' % data, None):
        raise InvalidInputError('Game %s not found.' % data)
    elif a in ('playerId', 'otherPlayerId'):
      if not firebase.get('/games/%s/players/%s/name' % (request_data['gameId'], data), None):
        raise InvalidInputError('Player %s not found.' % data)
    elif a == 'gunId':
      if not firebase.get('/guns', data):
        raise InvalidInputError('Gun %s not found.' % data)
    elif a == 'missionId':
      if not firebase.get('/missions/%s/name' % data, None):
        raise InvalidInputError('Mission %s not found.' % data)
    elif a == 'chatRoomId':
      if not firebase.get('/chatRooms/%s/name' % data, None):
        raise InvalidInputError('Chat room %s not found.' % data)
    elif a == 'allegianceFilter':
      if data not in ('horde', 'resistance', 'none'):
        raise InvalidInputError('Allegiance %s is not valid.' % data)
    else:
      raise AppError('Unhandled arg validation: %s' % a)


@app.route('/')
def index():
  return "<h1>Welcome To Google HVZ (backend)!</h1>"


@app.route('/test', methods=['GET'])
def get_testdata():
  testdata = firebase.get('testdata', None)
  return jsonify(testdata)


@app.route('/register', methods=['POST'])
def register():
  try:
    request_data = request.get_json()
    userId = request_data['userToken']
    put_data = {
        'registered': True
    }
    firebase.put('/users', userId, put_data)
    return ''
  except:
    return AppError("There was an app error")


@app.route('/creategame', methods=['POST'])
def new_game():
  request_data = request.get_json()
  game = request_data['gameId']
  adminUser = request_data['adminUserId']
  name = request_data.get('name', '')
  rulesUrl = request_data.get('rulesUrl', '')
  stunTimer = request_data.get('stunTimer', '')

  put_data = {
    'name': name,
    'rulesUrl': rulesUrl,
    'stunTimer': stunTimer,
    'active': True
  }
  return jsonify(firebase.put('/games', game, put_data))


@app.route('/createPlayer', methods=['POST'])
def create_player():
  """Generate a player to be assigned to a user and added to a game."""
  request_data = request.get_json()
  game = request_data['gameId']
  player = request_data['playerId']
  user_id = request_data['userId']
  name = request_data.get('name', '')
  need_gun = request_data.get('needGun', False)
  profile_image_url = request_data.get('profileImageUrl', '')
  start_as_zombie = request_data.get('startAsZombie', False)
  volunteer = request_data.get('volunteer', False)
  be_secret_zombie = request_data.get('beSecretZombie', False)

  player_info = {
    'gameId': game
  }
  firebase.put('/users/%s/players' % user_id, player, player_info)

  game_info = {
    'name': name,
    'needGun' : need_gun,
    'profileImageUrl' : profile_image_url,
    'startAsZombie' : start_as_zombie,
    'user_id' : user_id,
    'volunteer' : volunteer
  }

  return jsonify(firebase.put('/games/%s/players' % game, player, game_info))


@app.route('/addGun', methods=['POST'])
def add_gun():
  request_data = request.get_json()
  gun = request_data['gunId']

  put_data = {
    'playerId': '',
  }
  return jsonify(firebase.put('/guns', gun, put_data))


@app.route('/gun', methods=['GET'])
def get_gun():
  gun = request.args['gunId']
  return jsonify(firebase.get('/guns', gun))


@app.route('/assignGun', methods=['POST'])
def assign_gun():
  args = ['gameId', 'playerId', 'gunId']
  ValidateInputs(args, args)

  request_data = request.get_json()
  game = request_data['gameId']
  gun = request_data['gunId']
  player = request_data['playerId']

  put_data = {
    'playerId': player,
    'gameId': game,
  }
  return jsonify(firebase.put('/guns', gun, put_data))


@app.route('/updatePlayer', methods=['POST'])
def update_player():
  args = ['gameId', 'playerId']
  ValidateInputs(args, args)

  request_data = request.get_json()
  player = request_data['playerId']
  game = request_data['gameId']

  put_data = {}
  for property in ['name', 'needGun', 'profileImageUrl', 'startAsZombie', 'volunteer']:
    if property in request_data:
      put_data[property] = request_data[property]

  path = '/games/%s/players/%s' % (game, player)
  return jsonify(firebase.patch(path, put_data))


@app.route('/addMission', methods=['POST'])
def add_mission():
  ValidateInputs(['missionId'], [])

  request_data = request.get_json()
  mission = request_data['missionId']

  put_data = {
    'name': request_data['name'],
    'begin': request_data['begin'],
    'end': request_data['end'],
    'url': request_data['url'],
    'allegiance': request_data['allegiance'],
  }

  return jsonify(firebase.put('/missions', mission, put_data))


@app.route('/updateMission', methods=['POST'])
def update_mission():
  args = ['missionId']
  try:
    ValidateInputs(args, args)
  except Exception as e:
    return e.message

  request_data = request.get_json()
  mission = request_data['missionId']

  put_data = {}
  for property in ['name', 'begin', 'end', 'url', 'allegiance']:
    if property in request_data:
      put_data[property] = request_data[property]

  return jsonify(firebase.patch('/missions/%s' % mission, put_data))


@app.route('/addPlayerToChat', methods=['POST'])
def add_player_to_chat():
  """Add a new player to a chat room.

  Must be done by a player already in the chat room.

  Args:
    gameId: The game ID.
    chatRoomId: The chat room ID to add the player to.
    otherPlayerId: The player being added.
    playerId: The player doing the adding.
  """
  valid_args = ['gameId', 'chatRoomId', 'playerId', 'otherPlayerId']
  required_args = list(valid_args)
  ValidateInputs(required_args, valid_args)

  request_data = request.get_json()
  game = request_data['gameId']
  chat = request_data['chatRoomId']
  player = request_data['playerId']
  otherPlayer = request_data['otherPlayerId']

  # Validate player is in the chat room
  if firebase.get('/chatRooms/%s/memberships/%s' % (chat, player), None) is None:
    raise InvalidInputError('You are not a member of that chat room.')
  # Validate otherPlayer is not in the chat room
  if firebase.get('/chatRooms/%s/memberships' % chat, otherPlayer) is not None:
    raise InvalidInputError('Other player is already in the chat.')
  # Check allegiance?

  return jsonify(firebase.put('/chatRooms/%s/memberships' % chat, otherPlayer, ""))


@app.route('/sendChatMessage', methods=['POST'])
def send_chat_message():
  """Send a message to a chat room.

  Must be done by a player already in the chat room.

  Args:
    gameId: The game ID.
    chatRoomId: The chat room to update.
    playerId: The player sending the message.
    messageId: The ID of the new message.
    message: The message to add (string).
  """
  valid_args = ['gameId', 'chatRoomId', 'playerId']
  required_args = list(valid_args)
  required_args.extend(['messageId', 'message'])
  ValidateInputs(required_args, valid_args)

  request_data = request.get_json()
  game = request_data['gameId']
  chat = request_data['chatRoomId']
  player = request_data['playerId']
  messageId = request_data['messageId']
  message = request_data['message']

  if not messageId.startswith('message-'):
    raise InvalidInputError('Message ID is not valid.')
  # Validate player is in the chat room
  if firebase.get('/chatRooms/%s/memberships/%s' % (chat, player), None) is None:
    raise InvalidInputError('You are not a member of that chat room.')

  # Compute the message index to use -- reimplement auto IDs ;)
  index = 1

  message_data = {
    'index': index,
    'message': message,
    'playerId': player,
    'time': int(time.time()),
  }

  return jsonify(firebase.put('/chatRooms/%s/messages' % chat, messageId, message_data))


# vim:ts=2:sw=2:expandtab
