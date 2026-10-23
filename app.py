import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'gizli_anahtar_kelime'  # Oturum yönetimi için güvenli bir anahtar

# Veritabanı Ayarları (Render veya yerel ortam için)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///asi.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class VaccineEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vaccine_name = db.Column(db.String(50), nullable=False)
    stock_qty = db.Column(db.Integer, default=0)
    requested_qty = db.Column(db.Integer, default=0)
    user = db.relationship('User', backref=db.backref('entries', lazy=True))

# Sabit Aşı Listesi (Excel dosyanızdaki sıralamaya göre)
VACCINE_LIST = [
    "HEXAXİM", "TETRAXİM", "KPA", "TD", "TDAB", 
    "HEPATİT A", "HEPATİT B", "KKK", "SUÇİÇEĞİ", "MENİNGOKOK"
]

# --- ROTALAR (ROUTES) ---

@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('user_panel'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            if user.is_admin:
                return redirect(url_for('admin_panel'))
            return redirect(url_for('user_panel'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
            
    return render_template('login.html')

@app.route('/panel', methods=['GET', 'POST'])
def user_panel():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        # Eski kayıtları temizle ve yeni girilenleri kaydet
        VaccineEntry.query.filter_by(user_id=user_id).delete()
        
        for vaccine in VACCINE_LIST:
            stock = request.form.get(f'stock_{vaccine}', 0)
            requested = request.form.get(f'requested_{vaccine}', 0)
            
            entry = VaccineEntry(
                user_id=user_id,
                vaccine_name=vaccine,
                stock_qty=int(stock) if stock else 0,
                requested_qty=int(requested) if requested else 0
            )
            db.session.add(entry)
        
        db.session.commit()
        flash('Verileriniz başarıyla kaydedildi!', 'success')
        return redirect(url_for('user_panel'))
    
    # Kullanıcının daha önce girdiği verileri forma yansıtmak için çekelim
    existing_entries = {e.vaccine_name: e for e in VaccineEntry.query.filter_by(user_id=user_id).all()}
    return render_template('index.html', vaccines=VACCINE_LIST, entries=existing_entries)

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    
    users = User.query.filter_by(is_admin=False).all()
    
    # Kim veri girdi kim girmedi kontrolü ve toplam rakamlar
    user_status = []
    for u in users:
        has_entered = VaccineEntry.query.filter_by(user_id=u.id).first() is not None
        user_status.append({'username': u.username, 'has_entered': has_entered})
        
    # Aşı bazında toplamlar
    totals = {}
    for vaccine in VACCINE_LIST:
        total_stock = db.session.query(db.func.sum(VaccineEntry.stock_qty)).filter_by(vaccine_name=vaccine).scalar() or 0
        total_requested = db.session.query(db.func.sum(VaccineEntry.requested_qty)).filter_by(vaccine_name=vaccine).scalar() or 0
        totals[vaccine] = {'stock': total_stock, 'requested': total_requested}

    return render_template('admin.html', user_status=user_status, totals=totals)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Veritabanını ve ilk admin/kullanıcı hesaplarını oluşturma
with app.app_context():
    db.create_all()
    # Eğer hiç kullanıcı yoksa test için 1 admin ve 1 kullanıcı oluşturalım
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
        normal_user = User(username='asm1', password=generate_password_hash('123456'), is_admin=False)
        db.session.add(admin_user)
        db.session.add(normal_user)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)