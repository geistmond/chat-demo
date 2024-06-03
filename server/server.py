from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user

# , join_namespace, leave_namespace
from flask_socketio import SocketIO, emit, Namespace

from flask_sqlalchemy import SQLAlchemy

from pydantic import BaseModel

from oauthlib.oauth2 import WebApplicationClient

import redis
from rq import Queue

r = redis.Redis(host="localhost", port=6379, password='my_redis_password')
q = Queue(connection=r)

app = Flask(__name__)

# Replace with your configurations
app.config['SECRET_KEY'] = 'my_secret_key'  # update
# update
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/chat_db'

app.config['REDIS_URL'] = 'redis://localhost:6379'

app.config['GOOGLE_CLIENT_ID'] = 'my_google_client_id'  # update
app.config['GOOGLE_CLIENT_SECRET'] = 'my_google_client_secret'  # update

# Flask-Login and User Model
login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):

    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

# Example usage


def create_user(db, full_name, username, email, password, avatar=None):
    new_user = User(fullName=full_name, username=username,
                    email=email, password=password, avatar=avatar)
    db.add(new_user)
    db.commit()
    return new_user


def get_user_by_username(db, username):
    return db.query(User).filter(User.username == username).first()


@classmethod
def get(cls, id):
    return db.session.query(User).filter_by(id=id).first()


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# Database (SQLAlchemy connecting to Postres)
db = SQLAlchemy(app)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"<Message {self.id} - {self.channel}: {self.username} - {self.message[:20]}..."


# Redis connection
redis_client = redis.from_url(app.config['REDIS_URL'])

# Google OAuth Setup
google_client = WebApplicationClient(app.config['GOOGLE_CLIENT_ID'])

# SocketIO
socketio = SocketIO(app, message_queue=app.config['REDIS_URL'])

# Routes


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('chat.html', username=current_user.username)
    else:
        return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        # Implement logic to check email and password against database (e.g., using Flask-Login)
        # Replace with actual user lookup based on email and password
        user = User.get(1)
        if user:
            login_user(user)
            return redirect(url_for('index'))
        else:
            # Handle unsuccessful login attempt
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/login/google')
def google_login():
    google_authorize_url = google_client.prepare_request_uri(
        'https://oauth2.googleapis.com/auth/openid',
        redirect_uri=url_for('google_auth', _external=True),
        scope=['openid', 'profile', 'email']
    )
    return redirect(google_authorize_url)


@app.route('/login/google/authorized', methods=['GET'])
def google_auth(auth_code):
    auth_code = request.args.get(auth_code)
    return redirect(url_for('/chat'))


@app.route('/<string:username>')
def main_chat(username):
    return render_template('chat.html', async_mode=socketio.async_mode)


@app.route("/signup/")
def signup_email():
    return True


@app.route("/oauth2/")
def oauth2():
    return True


@socketio.on('follow', namespace='/follow')
def follow(value: str, user: str, friend: str):
    if value == "follow":
        emit('followed', (user, friend))  # fix to update db
    if value == "unfollow":
        emit('unfollowed', (user, friend))  # fix to update db
    else:
        emit(None)


@socketio.on('notify', namespace='/notify')
def notify(username: str, notification: str):
    emit('notify', (username, notification))


class WebChat(Namespace):
    def on_connect(self):
        global thread
        clients.append(request.sid)
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)

    def on_register(self, message):
        users[message['user']] = request.sid
        all_chat[message['user']] = []

        emit('user_response', {
            'type': 'connect',
            'message': '{0} is connected to the server'.format(message['user']),
            'data': {
                'users': users,
                'rooms': room_lists,
            },
        }, broadcast=True)

    def on_pm(self, message):
        user = get_username(request.sid)
        if message['user'] not in all_chat[user]:
            emit('message_response', {
                'type': 'private',
                'message': '',
                'data': {
                    'user': message['user'],
                },
            })
            all_chat[user].append(message['user'])

        def on_pm_send(self, message):
            user = get_username(request.sid)
            if user not in all_chat[message['friend']]:
                all_chat[message['friend']].append(user)
                result = ('message_response', {
                    'type': 'new_private',
                    'message': '',
                    'data': {
                        'user': user
                    }
                })
                r.lpush(q, result)  # Push to queue to persist
                emit(result, room=users[message['friend']])
        private_act = 'pm'

        if 'act' in message:
            private_act = 'disconnect'
            result = ('message_response', {
                'type': 'private_message',
                'act': private_act,
                'data': {
                        'text': message['text'],
                        'from': user,
                }
            })
            r.lpush(q, result)  # Push to queue to persist
            emit(result, room=users[message['friend']])

        def on_room_send(self, message):
            user = get_username(request.sid)

            # because room id from the html start with rooms_ then get room name
            temp_room_name = message['friend'].split('_')
            room_name = '_'.join(temp_room_name[1:len(temp_room_name)])
            emit('message_response', {
                'type': 'room_message',
                'data': {
                    'text': message['text'],
                    'room': room_name,
                    'from': user,
                }
            }, room=room_name)

        def on_close_chat(self, message):
            user = get_username(request.sid)
            if message['user'] in all_chat[user]:
                emit('message_response', {
                    'type': 'private_close',
                    'message': '',
                    'data': {
                        'user': message['user']
                    }
                })
                all_chat[user].remove(message['user'])

        def on_create_room(self, message):
            # If the room is not exist, append new room to rooms object, also set the admin and initial user
            if message['room'] not in room_lists:
                room_lists[message['room']] = {}
                user = get_username(request.sid)
                room_lists[message['room']]['admin'] = user
                room_lists[message['room']]['users'] = [user]
                join_room(message['room'])
                emit('feed_response', {
                    'type': 'rooms',
                    'message': '{0} created room {1}'.format(room_lists[message['room']]['admin'], message['room']),
                    'data': room_lists
                }, broadcast=True)

                emit('message_response', {
                    'type': 'open_room',
                    'data': {
                        'room': message['room'],
                    },
                })
            else:
                emit('feed_response', {
                    'type': 'feed',
                    'message': 'Room is exist, please use another room',
                    'data': False,
                })

        def on_get_room_users(self, message):
            if message['room'] in room_lists:
                emit('feed_response', {
                    'type': 'room_users',
                    'message': '',
                    'data': room_lists[message['room']]['users'],
                    'rooms': room_lists,
                })

    def on_join_room(self, message):
        if message['room'] in room_lists:
            user = get_username(request.sid)
            if user in room_lists[message['room']]['users']:
                emit('feed_response', {
                    'type': 'feed',
                    'message': 'You have already joined the room',
                    'data': False
                })
            else:
                # Join room
                join_room(message['room'])
                # Append to room's users array
                room_lists[message['room']]['users'].append(user)

                # Announce user join
                emit('feed_response', {
                    'type': 'new_joined_users',
                    'message': '{0} joined room {1}'.format(user, message['room']),
                    'data': room_lists[message['room']]['users'],
                    'room': message['room'],
                    'user_action': user,
                    'welcome_message': '{0} join the room'.format(user),
                }, room=message['room'])

                # Update news feed for user join
                emit('feed_response', {
                    'type': 'rooms',
                    'message': '',
                    'data': room_lists
                }, broadcast=True)

                # Send message to frontend for join
                emit('message_response', {
                    'type': 'open_room',
                    'data': {
                        'room': message['room'],
                    },
                })

    def on_close_room(self, message):
        user = get_username(request.sid)
        temp_room_name = message['room'].split('_')
        room_name = '_'.join(temp_room_name[1:len(temp_room_name)])

        if user == room_lists[room_name]['admin']:
            emit('message_response', {
                'type': 'room_feed',
                'data': {
                    'text': '{0} (Admin) is closing the room'.format(user),
                    'room': room_name,
                    'from': user,
                }
            }, room=room_name)

            # Update room feed
            emit('feed_response', {
                'type': 'update_room_users',
                'message': '',
                'data': room_lists[room_name]['users'],
                'room': room_name,
                'user_action': user,
                'act': 'close',
            }, broadcast=True)

            # Close room
            close_room(room_name)
            # Remove room from list
            room_lists.pop(room_name)

            # Send message to feed
            emit('feed_response', {
                'type': 'rooms',
                'message': '{0} is closing room {1}'.format(user, room_name),
                'data': room_lists
            }, broadcast=True)
        else:
            # if not admin, leave room
            # broadcast to users in room
            emit('message_response', {
                'type': 'room_feed',
                'data': {
                    'text': '{0} is leaving the room'.format(user),
                    'room': room_name,
                    'from': user,
                }
            }, room=room_name)

            # update room user list
            emit('feed_response', {
                'type': 'update_room_users',
                'message': '',
                'data': room_lists[room_name]['users'],
                'room': room_name,
                'user_action': user,
                'act': 'leave',
            }, room=room_name)

            # leave room
            leave_room(room_name)
            # remove user from room
            room_lists[room_name]['users'].remove(user)

            # broadcast to users in room that there is user leaving the room
            emit('feed_response', {
                'type': 'rooms',
                'message': '{0} is leaving room {1}'.format(user, room_name),
                'data': room_lists
            }, broadcast=True)

    def on_disconnect(self):
        if request.sid in clients:
            # remove sid from clients
            clients.remove(request.sid)
            user = get_username(request.sid)
            # if user is exist
            if user:
                # create temporary array, so it won't affect the rooms list when it changes
                all_rooms = [i for i in room_lists]
                for room in all_rooms:
                    # if user is admin in a room or user exist in a room, call close room function, logic handled by the function
                    if room_lists[room]['admin'] == user or user in room_lists[room]['users']:
                        self.on_close_room({
                            'room': 'rooms_{0}'.format(room)
                        })

                        # broadcast to all chat friend that the user is disconnecting
                for friend in all_chat[user]:
                    self.on_private_send({
                        'friend': friend,
                        'text': '{0} is offline'.format(user),
                        'act': 'disconnect',
                    })

                    # remove user chat state
                all_chat.pop(user)

                # remove from users list
                users.pop(user)

                # append to news feed
                emit('user_response', {
                    'type': 'connect',
                    'message': '{0} is disconnected from the server'.format(user),
                    'data': {
                        'users': users,
                        'rooms': room_lists,
                    },
                }, broadcast=True)

        print('Client disconnected {}'.format(request.sid))

    def on_my_ping(self):
        emit('my_pong')


socketio.on_namespace(WebChat('/chat'))

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
