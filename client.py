from flask import *
from database_conn import connection
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash,check_password_hash
import re
from functools import wraps
import pytz
from datetime import datetime,timedelta

# print(pytz.timezone('Africa/Addis_Ababa'))

client_bp = Blueprint('client', __name__, url_prefix='/client')

def isbooked(timestamp,barber,service):
    sql = "SELECT * FROM bookings WHERE time = %s AND barber = %s AND service = %s"
    args = (timestamp,barber,service,)
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(sql,args)
        data = cur.fetchone()
    return bool(data)

def add_days_ethiopian_time(n: int) -> str:
    # 1. Define the Ethiopian timezone (EAT - East Africa Time)
    ethiopia_tz = pytz.timezone('Africa/Addis_Ababa')
    
    # 2. Get the current time localized to Ethiopia
    current_time_in_ethiopia = datetime.now(ethiopia_tz)
    
    # 3. Add n days using timedelta
    future_time_in_ethiopia = current_time_in_ethiopia + timedelta(days=n)
    
    # 4. Format the result to YYYY-MM-DD
    return future_time_in_ethiopia.strftime('%Y-%m-%d')

def convert_to_24h(time_12h: str) -> str:
    # Strip any extra spaces and convert to uppercase for consistency
    time_str = str(time_12h).strip().upper()
    
    # Parse the 12-hour time and format it to 24-hour time
    parsed_time = datetime.strptime(time_str, "%I:%M %p")
    return parsed_time.strftime("%H:%M")

def login_required(f):
    @wraps(f)  # Preserves the original function's metadata
    def decorated_function(*args, **kwargs):
        # Check your session variable here
        if "user" not in session:
            # Redirect to login and track where they tried to go
            return redirect(url_for("client.home", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def is_strong_password(password):
    # Regex for: 1+ lowercase, 1+ uppercase, 1+ digit, 1+ special char, 8+ total length
    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    
    # re.fullmatch ensures the entire string conforms to the rule
    if re.fullmatch(pattern, password):
        return True
    return False

def calculaterating(barberid):
    with connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Select all stars for the given barber
        cur.execute("SELECT star FROM public.ratings WHERE barber = %s", (barberid,))
        ratings = cur.fetchall()
        
        # If there are no ratings yet, return 0 average and 0 count
        if not ratings:
            return {
                "average_rating": 0.0,
                "total_reviews": 0
            }
        
        # Calculate the average from the list of rows
        total_stars = sum(row['star'] for row in ratings)
        total_reviews = len(ratings)
        average_rating = round(total_stars / total_reviews, 1)
        
        return {
            "average_rating": average_rating,
            "total_reviews": total_reviews
        }
    
def israted(userid,barber):
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ratings WHERE client = %s AND barber = %s",(userid,barber,))
        data = cur.fetchone()
    return bool(data)
    

def getgender(userid):
    sql = 'SELECT gender FROM clients WHERE id = %s'
    conn = connection()
    cur = conn.cursor()
    cur.execute(sql,(userid,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    return data

@client_bp.route("/")
def home():
    if 'user' in session:
        return redirect(url_for('client.dashboard'))
    return render_template("client/index.html")

@client_bp.errorhandler(404)
def errorpage(err):
    return render_template("client/404.html")

@client_bp.route("/signup",methods=['POST'])
def signup():
    try:
        fullname = request.form['fullname']
        gender = request.form['gender']
        tel = request.form['tel']
        password = request.form['pass']
        query = "INSERT INTO clients(fullname,gender,tel,password) VALUES(%s,%s,%s,%s)"
        args = (fullname,gender,tel,generate_password_hash(password))
        if not is_strong_password(password):
            raise ValueError("Your password must contain atleast one capital one small letter and at least one special character and 8 character long")
        with connection() as conn:
            cur = conn.cursor()
            cur.execute(query,args)
            conn.commit()
        flash("You are registered welcome on board!","success")
        return redirect(url_for('client.home'))
    except Exception as e:
        print(e)
        flash(f"{e}",'error')
        return redirect(url_for('client.home'))
    
@client_bp.route('/login',methods=['POST'])
def login():
    try:
        tel = request.form['tel']
        password = request.form['pass']
        query = "SELECT id,password FROM clients WHERE tel = %s"
        args = (tel,)
        with connection() as conn:
            cur = conn.cursor()
            cur.execute(query,args)
            user = cur.fetchone()
        if user:
            if check_password_hash(user[1],password):
                session['user'] = user[0]
                flash("Logged in successfully!",'success')
                return redirect(url_for('client.dashboard'))
            else:
                raise ValueError("Invalid password",'error')
        else:
            raise ValueError("User not found")
    except Exception as e:
        print(e)
        flash(f"{e}",'error')
        return redirect(url_for('client.home'))
    
@client_bp.route("/dashboard")
@login_required
def dashboard():
    gender = getgender(session['user'])
    # print(gender[0])
    with connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM barbers WHERE type = %s OR type = %s",(gender[0],'both'))
        barbers = cur.fetchall()
    return render_template("client/dash.html",barbers=barbers)

@client_bp.route("/barber/<barberid>")
@login_required
def barber_info(barberid):
    with connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM barbers WHERE barberid = %s",(barberid,))
        data = cur.fetchone()
    if not data:
        return abort(404)
    return render_template("client/barber_info.html",data=data,rating=calculaterating)

@client_bp.route("/review/<barberid>",methods=['POST'])
@login_required
def reviewbarber(barberid):
    try:
        rating = int(request.form['rating'])
        comment = request.form['comment']
        if not israted(session['user'],barberid):
            with connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO ratings(client,comment,star,barber) VALUES(%s,%s,%s,%s)",(session['user'],comment,rating,barberid))
                conn.commit()
            flash("Successfully rated!",'success')
            return redirect(url_for('client.dashboard'))
        else:
            with connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE ratings SET comment = %s,star = %s,barber = %s WHERE client = %s",(comment,rating,barberid,session['user']))
                conn.commit()
            flash("Successfully rated!",'success')
            return redirect(url_for('client.dashboard'))
    except Exception as e:
        print(e)
        flash(f'{e}','error')
        return redirect(url_for('client.dashboard'))
    
@client_bp.route("/book/<barberid>",methods=['GET','POST'])
@login_required
def book(barberid):
    if request.method == 'GET':
        with connection() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM services WHERE barber = %s",(barberid,))
            services = cur.fetchall()
        if not services:
            flash("This barber doesnt have any services",'error')
            return redirect(url_for('client.dashboard'))
        return render_template('client/book.html',services=services,barberid=barberid)
    elif request.method == 'POST':
        try:
            # hour = convert_to_24h({request.form["hour"]})
            timestamp = f'{add_days_ethiopian_time(n=int(request.form['date']))} {request.form["hour"]}:00'
            print(timestamp)
            service = request.form['service_id']
            if isbooked(timestamp,barberid,service):
                raise Exception("Cant book because it's already booked")
            sql = "INSERT INTO bookings(client,barber,time,service) VALUES(%s,%s,%s,%s)"
            args = (session['user'],barberid,timestamp,service)
            with connection() as conn:
                cur = conn.cursor()
                cur.execute(sql,args)
                conn.commit()
            flash("Booked successfully!",'success')
            return redirect(url_for('client.dashboard'))
        except Exception as e:
            flash(f"Error : {e}")
            print(e)
            return redirect(url_for('client.dashboard'))
    else:
        return abort(405)
    
@client_bp.route("/bookings")
@login_required
def bookings():
    sql = """
    SELECT barbers.name,
    barbers.address,
    bookings.time,
    bookings.id,
    services.service,
    services.price
    FROM bookings
    JOIN barbers ON bookings.barber = barbers.barberid
    JOIN services ON bookings.service = services.id WHERE bookings.client = %s
"""
    with connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql,(session['user'],))
        booking_list = cur.fetchall()
    return render_template("client/booking.html",bookings=booking_list)

@client_bp.route("/delete/booking/<bookingid>",methods=['POST'])
@login_required
def deletebooking(bookingid):
    try:
        with connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM bookings WHERE id = %s AND client = %s",(bookingid,session['user'],))
            conn.commit()
        flash("Booking cancelled successfully!",'success')
        return redirect(url_for("client.bookings"))
    except Exception as e:
        flash(f"Error : {e}")
        return redirect(url_for("client.bookings"))
    
@client_bp.route("/products")
@login_required
def products():
    sql = '''
SELECT merches.merch,
merches.image,
barbers.tel FROM merches 
JOIN barbers ON merches.barber = barbers.barberid
'''
    with connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql)
        products = cur.fetchall()
    return render_template("client/prod.html",products=products)

    
@client_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('client.home'))