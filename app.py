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

env = json.load(open('secret_key.json', 'r'))['web']
DOMAIN, _, DOMAIN_AUTH = env['redirect_uris']

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', env['client_id'])
GOOGLE_CLIENT_SECRET = os.environ.get(
    'GOOGLE_CLIENT_SECRET', env['client_secret'])
GOOGLE_DISCOVERY_URL = (
    'https://accounts.google.com/.well-known/openid-configuration'
)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def revoke_token():
    if session.get("token"):
        res = requests.post('https://accounts.google.com/o/oauth2/revoke',
                            params={'token': session['token']},
                            headers={'content-type': 'application/x-www-form-urlencoded'})


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    return render_template("signin.html")


# try:
#     init_db_command()
# except sqlite3.OperationalError:
#     # Assume it's already been created
#     pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)


@login_manager.user_loader
def load_user(user_id):
    print(user_id)
    return User.get(user_id)


@app.route('/')
def main():
    print(request.user_agent.string)
    if current_user.is_authenticated:
        return render_template(
            'index.html',
            name=current_user.name,
            email=current_user.get_departure_name(),
            pic=current_user.profile_pic
        )
    return render_template("signin.html")

@app.route('/test')
@login_required
def test():
    return redirect("elements.html")

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
    # return redirect('/404')


@app.route("/logout")
@login_required
def logout():
    logout_user()

    return redirect('/')


@app.route('/raspage', methods=['GET', 'POST'])
def rascallback():
    return 'callback'


@app.errorhandler(404)
def page_not_found(error):
    return render_template("message.html", title="오류", message="존재하지 않는 페이지입니다.")


if __name__ == '__main__':
    app.run('0.0.0.0', port=8000)
