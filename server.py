from crypt import methods
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def main():
    return render_template("blank.html")


@app.route("/raspage", methods=['GET', 'POST'])
def rascallback():
    return "callback"

if __name__ == "__main__":
    app.run('0.0.0.0', port=80)