import json
import os
from flask import Flask, redirect, request, url_for, render_template, session, current_app
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests
from modules.user import *
from modules.redis_handler import RedisHandler
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
from threading import Thread
from modules.token import gen_token
print("import modules...")


print("set default parameters...")

cred = credentials.Certificate(
    "scale-363204-firebase-adminsdk-92cgd-94fab70d54.json")
firebase_admin.initialize_app(cred)

env = json.load(open('secret_key.json', 'r'))
env_web = env['web']
env_redis = env['redis']
DOMAIN, _, DOMAIN_AUTH = env_web['redirect_uris']

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', env_web['client_id'])
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET', env_web['client_secret'])
GOOGLE_DISCOVERY_URL = (
    'https://accounts.google.com/.well-known/openid-configuration'
)


rs_server = RedisHandler(
    env_redis['host'], env_redis['port'], db=0, password=env_redis['password'])


def open_via_raspberry(lock_info: LockInfo):
    res = json.dumps({"target": lock_info.own_id, "action": "open"})
    rs_server.publish(lock_info.reg_id, res)


def enable_usage(lock_info: LockInfo):
    token = gen_token()
    LockUsage.create(token, lock_info, current_user)
    usage = LockUsage.get(token)
    res = json.dumps({"target": lock_info.own_id, "action": "aes:"+usage.uuid})
    rs_server.publish(lock_info.reg_id, res)


def disable_usage(usage: LockUsage):
    lock_info = usage.get_locker_info()
    res = json.dumps({"target": lock_info.own_id, "action": "purge"})
    rs_server.publish(lock_info.reg_id, res)
    usage.disable()


def redis_handle(channel: str, data):
    data = json.loads(data)
    print(data)
    if state := data.get("door_state"):
        state = int(state)
        title = "문 {0}"
        content = "문이 {0}습니다."
        if state == LockLog.OPENED:
            title = title.format("열림")
            content = content.format("열렸")
        elif state == LockLog.CLOSED:
            title = title.format("닫힘")
            content = content.format("닫혔")
        elif state == LockLog.INVALID_OPEN:
            title = title.format("경고")
            content = content.format("강제적으로 열렸")
        else:
            return
        send_notification(data['noti_token'], title, content)


client = WebApplicationClient(GOOGLE_CLIENT_ID)


def send_notification(target, title, content, image=None):

    message = messaging.Message(
        notification=messaging.Notification(
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
def noti_token_get():
    token = request.args.get('token')
    if token != current_user.noti_token:
        current_user.set_noti_token(token)
    usage = current_user.get_lock_usage()
    # print("noti_token", usage.uuid)
    if usage:
        return {"uuid": usage.uuid}
    return ""
@app.route('/open', methods=['GET'])
@login_required
def open_door():
    usage = current_user.get_lock_usage()
    locker = usage.get_locker_info()
    open_via_raspberry(locker)
    return "complete"


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


# @app.route('/add_locker')
# def add_locker():
#     usage = current_user.get_lock_usage()
#     if not usage.token:
#         return render_template("/add_locker.html")
#     else:
#         return render_template(
#             'index.html',
#             name=current_user.name,
#             email=current_user.get_departure_name(),
#             pic=current_user.profile_pic,
#             path="/",
#             notis=[]
#         )


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
def refer():
    print(request.user_agent.string)
    if current_user.is_authenticated:
        # locker = LockInfo.get("53677848")
        # open_via_raspberry(locker)
        return render_template(
            'index.html',
            name=current_user.name,
            email=current_user.get_departure_name(),
            pic=current_user.profile_pic,
            path="/",
            notis=[]
        )
    return render_template("signin.html")


@app.route('/render/', methods=['POST'])
@login_required
def render_main():
    params = json.loads(request.get_data())
    print(params)
    if data:=params.get("data"):
        if "addLocker_" in data:
            enable_usage(LockInfo.get(data.split("_")[1]))
        elif "removeLocker_" in data:
            usage = LockUsage.get(data.split("_")[1])
            disable_usage(usage)
    usage = current_user.get_lock_usage()
    print(usage)
    if usage is None:
        regions = LockRegion.get_by_departure(current_user.dep_id)

        lockers_formatted = list()
        for region in regions:
            lockers = region.get_lockers()
            lockers_formatted += [{'name': locker.pos, 'place': region.name, 'own_id': locker.own_id} for locker in lockers if locker.use == 0]
        print(lockers_formatted)
        return render_template("render/empty.html", lockers=lockers_formatted)
    locker = usage.get_locker_info()
    print(usage)
    logs = [{"is_open": log.is_open, 'time': log.create_time}
            for log in usage.get_logs()]
    if len(logs) == 0:
        state = LockLog.CLOSED
    else:
        state = logs[0]['is_open']
        print(state)
    return render_template("render/main.html", lock_name=locker.get_pos_str(), logs=logs[:4], is_open=state, length = len(logs), token=usage.token)


@app.route('/render/<path>', methods=['POST'])
@login_required
def render_path(path):
    params = json.loads(request.get_data())
    print(params)
    if path=="log":
        usage = current_user.get_lock_usage()
        logs = [{"is_open": log.is_open, 'time': log.create_time}
            for log in usage.get_logs()]
        return render_template(f"render/log.html", logs=logs)
    try:
        return render_template(f"render/{path}.html", params=params)
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
    rs_server.listen("server", func=redis_handle)
    app.run(host='0.0.0.0', port=8000)
