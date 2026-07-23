from flask import *
from barber import barber_bp
from client import client_bp

app = Flask(__name__)

app.register_blueprint(barber_bp)
app.register_blueprint(client_bp)

app.secret_key = "SBUAdigwefwefyiugweuigfuifweugi"

@app.route('/')
def index():
    return render_template("index.html")

@app.errorhandler(404)
def errorpage(err):
    return render_template("404.html")



if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')
