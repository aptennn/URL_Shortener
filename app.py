from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, current_user, login_user, login_required, logout_user
import string
import random
import sqlite3
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fdsf34232'

conn = sqlite3.connect("Db.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
db = conn.cursor()

db.execute(
    """CREATE TABLE IF NOT EXISTS users
              (id INTEGER PRIMARY KEY ,
               username TEXT NOT NULL,
               password TEXT NOT NULL)"""
)

db.execute(
    """CREATE TABLE IF NOT EXISTS urls
              (id INTEGER PRIMARY KEY AUTOINCREMENT,
               original_url TEXT NOT NULL,
               short_url TEXT NOT NULL,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               owner_id INTEGER,
               FOREIGN KEY (owner_id) REFERENCES users(id)) 
               """
)
#db.execute("INSERT OR IGNORE INTO  urls (original_url, short_url) VALUES (?,?)", ("test1", "test1"))
#db.execute("INSERT OR IGNORE INTO  users (username, password) VALUES (?,?)", ("test1", "test1"))
conn.commit()

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Авторизуйтесь для доступа к закрытым страницам"
login_manager.login_message_category = "success"


def hash_password(password):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(password.encode('utf-8'))
    return sha256_hash.hexdigest()


def generate_short_url():
    characters = string.ascii_letters + string.digits
    short_url = "".join(random.choice(characters) for _ in range(7))
    return short_url


class UserLogin(UserMixin):

    def __init__(self):
        self.id = None

    def fromDB(self, id):
        try:
            print("id db " + id)
            self.id = id
            db.execute(f"SELECT * FROM users WHERE id = {id} LIMIT 1")
            res = db.fetchone()
            print(res)
            self.__user = res
            if not res:
                print("Пользователь не найден:" + id)

                self.__user = False
                return self
            return self

        except sqlite3.Error as e:
            print("Ошибка получения данных из БД " + str(e))
        return self

    def create(self, user):
        self.__user = user
        return self

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        # return self.id
        return str(self.__user['id'])


@login_manager.user_loader
def load_user(user_id):
    print("load_user")
    return UserLogin().fromDB(user_id)


@app.route("/login", methods=["POST", "GET"])
def login():
    session.pop('_flashes', None)
    print("curuser" + str(current_user))
    print(current_user)

    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        print("nick: " + request.form['email'])
        db.execute(f"SELECT * FROM users WHERE username = '{request.form['email']}' LIMIT 1")
        user = db.fetchone()
        # print(f"{user}  psws  {hash_password(request.form['psw'])}  {user[2]}")

        if user and user[2] == hash_password(request.form['psw']):
            userlogin = UserLogin().create(user)
            login_user(userlogin)
            flash("Вы вошли", "error")
            return redirect(url_for('index'))

        else:
            flash("Неверная пара логин/пароль", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return render_template("index.html", status="Вы уже зарегистрированы, переход на страницу недоступен")

    if request.method == "POST":
        session.pop('_flashes', None)
        if len(request.form['name']) > 2 and request.form['psw'] == request.form['psw2']:

            add = False
            db.execute(f"SELECT COUNT() as `count` FROM users WHERE username LIKE '{request.form['name']}'")
            res = db.fetchone()
            print(res)
            if res['count'] > 0:
                print("Статья с таким url уже существует")
            if res[0] > 0:
                flash("Пользователь с таким username уже существует", "error")

            try:
                db.execute("INSERT INTO users (username, password) VALUES (?,?)",
                           (request.form['name'], hash_password(request.form['psw'])))
                conn.commit()
                add = True
            except sqlite3.IntegrityError:
                pass

            if add:
                flash("Вы успешно зарегистрированы, войдите в аккаунт", "success")

                return render_template("login.html", status_reg="Успешно")
            else:
                flash("Ошибка при добавлении в БД", "error")
        else:
            flash("Неверно заполнены поля", "error")

    return render_template("register.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "success")
    return redirect(url_for('login'))


@app.route("/", methods=["GET", "POST"])
def index():
    return_text = ""

    if not current_user or not current_user.is_authenticated:
        return_text = "Войдите в аккаунт для доступа к истории"
    else:
        return_text = "Вы вошли в аккаунт, доступна история"


    render_template("index.html", login=return_text)

    if request.method == "POST":
        original_url = request.form["original_url"]
        short_url = generate_short_url()

        if current_user.is_authenticated:
            db.execute(
                "INSERT INTO urls (original_url, short_url, owner_id) VALUES (?,?, ?)",
                (original_url, short_url, current_user.id), )
        else:
            db.execute(
                "INSERT INTO urls (original_url, short_url) VALUES (?,?)",
                (original_url, short_url), )

        conn.commit()

        return render_template("index.html", short_url=short_url, login=return_text)

    return render_template("index.html", login=return_text)


@app.route("/<short_url>")
def redirect_to_url(short_url):
    db.execute("SELECT original_url FROM urls WHERE short_url=?", (short_url,))
    result = db.fetchone()

    if result:
        original_url = result[0]
        return redirect(original_url)

    return render_template("index.html")


@app.route("/history")
@login_required
def history():
    db.execute("SELECT original_url, short_url, created_at FROM urls DESC WHERE owner_id=?", (current_user.id,))

    results = db.fetchall()
    return render_template("history.html", results=results)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
