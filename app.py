print("import modules...")

import json
import os
from flask import Flask, redirect, request, url_for, render_template, session
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests
from modules.user import User, Department
import socket
from time import sleep
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
from threading import Thread


print("set default parameters...")

cred = credentials.Certificate("scale-363204-firebase-adminsdk-92cgd-94fab70d54.json")
firebase_admin.initialize_app(cred)

HOST = 'localhost'
PORT = 5000

env = json.load(open('secret_key.json', 'r'))
web = env['web']
DOMAIN, _, DOMAIN_AUTH = web['redirect_uris']

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', web['client_id'])
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET', web['client_secret'])
GOOGLE_DISCOVERY_URL = (
    'https://accounts.google.com/.well-known/openid-configuration'
)

client = WebApplicationClient(GOOGLE_CLIENT_ID)

def send_notification(target, title, content, image=None):

    message = messaging.Message(
        notification = messaging.Notification(
            title=title,
            body=content,
            image=image
        ),
        token=target,
    )
    try:
        response = messaging.send(message)
    except Exception as e:
        print(e)
        return
    print('Successfully sent message:', response)

async def socket_send(data):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    send = {
        'identify': 'web',
        'data': data
    }
    try:
        await client_socket.send(json.dumps(send).encode())
    except Exception as e:
        print(e)
    sleep(0.5);
    client_socket.close()

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def revoke_token():
    if session.get("token"):
        res = requests.post('https://accounts.google.com/o/oauth2/revoke',
                            params={'token': session['token']},
                            headers={'content-type': 'application/x-www-form-urlencoded'})

print("server initialization...")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.unauthorized_handler
def unauthorized():
    return render_template("signin.html")

@login_manager.user_loader
def load_user(user_id):
    print(user_id)
    return User.get(user_id)

@app.route('/noti', methods=['GET'])
@login_required
def test():
    token = request.args.get('token')
    if token != current_user.noti_token:
        current_user.set_noti_token(token)
    return 'test'

@app.route('/login')
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=DOMAIN_AUTH,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@app.route('/add_locker')
def add_locker():
    data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    socket_send(data)
    return data[0]

@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=f"{DOMAIN}{request.full_path}",
        redirect_url=DOMAIN_AUTH,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    token = token_response.json()
    session['token'] = token['access_token']
    client.parse_request_body_response(json.dumps(token))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.status_code != 200:
        return redirect("/msg/login_error")

    userinfo_json = userinfo_response.json()
    print(userinfo_json)
    if not userinfo_json.get("email_verified"):
        revoke_token()
        return redirect("/msg/login_error")

    unique_id = userinfo_json["sub"]
    users_email = userinfo_json["email"]
    if not users_email.endswith("@gachon.ac.kr"):
        revoke_token()
        return redirect("/msg/email_error")
    user = User.get(unique_id)

    if not user:
        picture = userinfo_json["picture"]
        users_name = userinfo_json["family_name"]
        region = userinfo_json["given_name"].replace('/', '')
        dep_id = Department.get_id_by_name(region)
        # Create a user in our db with the information provided
        # by Google
        User.create(unique_id, dep_id, users_name, users_email, picture)
        user = User(
            id_=unique_id, dep_id=dep_id, name=users_name, email=users_email, profile_pic=picture
        )
    # Begin user session by logging the user in
    login_user(user)
    # Send user back to homepage
    return redirect('/')

@app.route("/msg/<type_id>")
def msg(type_id):
    if type_id == 'login_error':
        return render_template("message.html", title="오류", message="로그인 중에 오류가 발생하였습니다.")
    elif type_id == 'email_error':
        return render_template("message.html", title="가입 불가", message="해당 이메일은 가천대학교 이메일이 아닙니다.")

@app.route("/logout")
@login_required
def logout():
    logout_user()

    return redirect('/')

@app.route('/')
def main():
    print(request.user_agent.string)
    if current_user.is_authenticated:
        if token:=current_user.noti_token:
            thread = Thread(target=send_notification, args=(token, "로그인 성공", "로그인에 성공하였습니다.", current_user.profile_pic))
            thread.start()

        return render_template(
            'index.html',
            name=current_user.name,
            email=current_user.get_departure_name(),
            pic=current_user.profile_pic,
            path="main",
            notis=[]
        )
    return render_template("signin.html")

@app.route('/render/')
@login_required
def render_main():
    return render_template("render/main.html")

@app.route('/render/<path>')
@login_required
def render_path(path):
    try:
        return render_template(f"render/{path}.html")
    except Exception as e:
        print(e)
    return render_template("render/404.html")

@app.route('/<path>')
@login_required
def require_handler(path):
    return render_template(
        'index.html',
        name=current_user.name,
        email=current_user.get_departure_name(),
        pic=current_user.profile_pic,
        path=path,
        notis=[]
    )

@app.errorhandler(404)
def page_not_found(error):
    return render_template("message.html", title="오류", message="존재하지 않는 페이지입니다."), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
