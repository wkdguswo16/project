# http://flask.pocoo.org/docs/1.0/tutorial/database/
import sqlite3
import pymysql
import click
from flask import current_app, g
from flask.cli import with_appcontext
import json

env = json.load(open('secret_key.json', 'r'))['sql']


def get_db():
    print("quering...")
    conn = pymysql.connect(host=env['link'], user=env['account'],
                            password=env['password'], db=env['db'], charset='utf8')
    if "db" not in g:
        g.conn = conn
        g.db = conn.cursor()
    return g.db

def commit():
    g.conn.commit()

def close_db(e=None):
    db = g.pop("db", None)
    conn = g.pop("conn", None)
    if db is not None:
        db.close()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    # init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
