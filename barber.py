from flask import *
from database_conn import connection as conn
from psycopg2.extras import RealDictCursor
from psycopg2 import errors
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
from supabase import create_client,Client
import uuid

barber_bp = Blueprint('barber', __name__, url_prefix='/barber')

def login_required(f):
    @wraps(f)  # Preserves the original function's metadata
    def decorated_function(*args, **kwargs):
        # Check your session variable here
        if "barber" not in session:
            # Redirect to login and track where they tried to go
            return redirect(url_for("barber.home", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Your Supabase credentials (found in Project Settings > API)
url = "https://yssiwrsfyzdcotcijpqy.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inlzc2l3cnNmeXpkY290Y2lqcHF5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MDc1MDg3NCwiZXhwIjoyMDk2MzI2ODc0fQ.dI-qIEEOONl8qLz1HpPv2YzpBkMkOakukYfZ5ve7i4Q" # Use service key for backend uploads

def upload_file(bucket,file,file_content,filename):
    supabase: Client = create_client(url, key)
    bucket_path = f"{filename}"
    try:
            response = supabase.storage.from_(bucket).upload(
                path=bucket_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            # 3. Get the Public URL to save in your PostgreSQL database
            image_url = supabase.storage.from_(bucket).get_public_url(bucket_path)
            
            return image_url
            
    except Exception as e:
        print(e)
        return False
    
def delete_file(image_url):
    # Delete from Supabase Storage
    supabase: Client = create_client(url, key)
    supabase.storage.from_("products").remove(image_url)
    return True

@barber_bp.route("/")
def home():
    return render_template("barber/index.html")

@barber_bp.route("/signup",methods=['POST'])
def signup():
    try:
        shop_name = request.form['shop-name']
        tel = request.form['tel-no']
        shop_add = request.form['shop-add']
        type_ = request.form['type']
        password = request.form['password']
        sql = 'INSERT INTO barbers(name,address,type,password,tel) VALUES(%s,%s,%s,%s,%s)'
        args = (shop_name,shop_add,type_,generate_password_hash(password),tel)
        with conn() as connection:
            cursor = connection.cursor()
            cursor.execute(sql,args)
            connection.commit()
        flash("Barber registered successfully","info")
        return redirect(url_for('barber.home'))
    except errors.UniqueViolation as e:
        print(e)
        flash("This phone number is already in use",'error')
        return redirect(url_for('barber.home'))
    except Exception as e:
        print(e)
        flash(f"Error : {e}",'error')
        return redirect(url_for('barber.home'))
    
@barber_bp.route("/signin",methods=['POST'])
def signin():
    try:
        tel = request.form['tel-no']
        password = request.form['password']
        with conn() as connection:
            cursor = connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM barbers WHERE tel = %s",(tel,))
            data = cursor.fetchone()
        if not data:
            raise ValueError("User data not found!")
        if not check_password_hash(data['password'],password):
            raise ValueError("Incorrect password!")
        if data and check_password_hash(data['password'],password):
            session['barber'] = data['barberid']
            return redirect(url_for('barber.dashboard'))
    except Exception as e:
        print(e)
        flash(f"Error : {e}","error")
        return redirect(url_for('barber.home'))
    
@barber_bp.route('/dashboard')
@login_required
def dashboard():
    with conn() as connection:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM barbers WHERE barberid = %s",(session['barber'],))
        data = cursor.fetchone()
    return render_template("barber/dash.html",datas=data)

@barber_bp.route("/edit-info",methods=['POST'])
@login_required
def editinfo():
    try:
        shop_name = request.form['shop-name']
        shop_add = request.form['shop-add']
        type_ = request.form['type']
        with conn() as connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE barbers SET name = %s,address = %s,type=%s WHERE barberid = %s",(shop_name,shop_add,type_,session['barber']))
            connection.commit()
        flash("Edited successfully!","success")
        return redirect(url_for('barber.dashboard'))
    except Exception as e:
        print(e)
        flash(f"Error : {e}","error")
        return redirect(url_for('barber.dashboard'))
    

@barber_bp.route("/services")
@login_required
def serviceBarbers():
    with conn() as connection:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM services WHERE barber = %s",(session['barber'],))
        service_list = cursor.fetchall()
    return render_template("barber/services.html",services=service_list)


@barber_bp.route("/add-service",methods=['POST'])
@login_required
def add_service():
    try:
        service = request.form['service']
        price = float(request.form['price'])
        details = request.form['details']
        with conn() as connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO services(service,price,barber,details) VALUES (%s,%s,%s,%s)",(service,price,session['barber'],details))
            connection.commit()
        flash("Service added successfully!","success")
        return redirect(url_for("barber.dashboard"))
    except Exception as e:
        flash(f"Error : {e}","error")
        return redirect(url_for("barber.dashboard"))

    
@barber_bp.route("/delete/service/<serviceid>")
@login_required
def delete_service(serviceid):
    try:
        with conn() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM services WHERE id = %s AND barber = %s",(serviceid,session['barber']))
            connection.commit()
            flash("Service deleted!","info")
            return redirect(url_for('barber.dashboard'))
    except Exception as e:
        print(e)
        flash(f"Error : {e}",'error')
        return redirect(url_for("barber.dashboard"))


@barber_bp.route("/beauty-products")
@login_required
def merchs():
    with conn() as connection:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM merches WHERE barber = %s",(session['barber'],))
        merches = cursor.fetchall()
    return render_template("barber/merch.html",products = merches)

@barber_bp.route("/add-product",methods=['POST'])
@login_required
def addproduct():
    try:
        merch = request.form['merch']
        image = request.files['image']
        amt = request.form['amount']
        price = float(request.form['price'])
        sql = "INSERT INTO merches(merch,image,amount,price,barber) VALUES(%s,%s,%s,%s,%s)"
        image_url = upload_file('products',image,image.read(),str(uuid.uuid4()).replace("-",''))
        args = (merch,image_url,amt,price,session['barber'])
        if not image_url:
            raise Exception("Product image not uploaded")
        with conn() as connection:
            cursor = connection.cursor()
            cursor.execute(sql,args)
            connection.commit()
        flash("Product added successfully!",'info')
        return redirect(url_for('barber.dashboard'))
    except Exception as e:
        flash(f"Error : {e}",'error')
        print(e)
        return redirect(url_for('barber.dashboard'))

@barber_bp.route("/delete/merch/<productid>")
@login_required
def deleteMerch(productid):
    try:
        with conn() as connection:
            cur = connection.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM merches WHERE id = %s AND barber = %s",(productid,session['barber']))
            data = cur.fetchone()
        img_url = str(data['image']).split('/')[-1]
        print(img_url)
        delete_file(img_url)
        with conn() as connection:
            cur = connection.cursor()
            cur.execute("DELETE FROm merches WHERE id = %s AND barber = %s",(productid,session['barber']))
            connection.commit()
        flash("Product deleted!","info")
        return redirect(url_for('barber.dashboard'))
    except Exception as e:
        print(e)
        flash(f"Error : {e}")
        return redirect(url_for('barber.dashboard'))

@barber_bp.route("/service/bookings")
@login_required
def bookings():
    query ='''
SELECT clients.tel,
clients.fullname,
bookings.time,
services.service,
services.price,
bookings.ispaid
FROM bookings
JOIN services ON bookings.service = services.id
JOIN clients ON bookings.client = clients.id WHERE bookings.barber = %s
'''
    with conn() as connection:
        cur = connection.cursor(cursor_factory=RealDictCursor)
        cur.execute(query,(session['barber'],))
        bookings = cur.fetchall()
    return render_template('barber/booking.html',bookings=bookings)

@barber_bp.route("/product/orders")
@login_required
def orders():
    sql = '''
SELECT orders.id,
merches.merch,
merches.image,
orders.amount,
orders.totalprice,
orders.ordered_on,
clients.fullname,
clients.tel,
orders.delivered FROM orders
JOIN merches ON orders.merch = merches.id
JOIN clients ON orders.client = clients.id WHERE orders.barber = %s AND paid = %s
'''
    with conn() as connection:
        cur = connection.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql,(session['barber'],'yes'))
        orders = cur.fetchall()
    return render_template('barber/orders.html',orders=orders)


@barber_bp.route("/go-premium")
@login_required
def premium():
    return render_template('barber/premium.html')

@barber_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("barber.home"))