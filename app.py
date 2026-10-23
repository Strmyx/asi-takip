import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'gizli_anahtar_kelime'

# Veritabanı Ayarları
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///asi.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
VACCINE_LIST = [
    "HEXAXİM", "TETRAXİM", "KPA", "TD", "TDAB", 
    "HEPATİT A", "HEPATİT B", "KKK", "SUÇİÇEĞİ", "MENİNGOKOK"
]

# --- HTML ŞABLONLARI (Tek Dosya İçinde) ---

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Aşı Takip - Giriş</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center justify-content-center vh-100">
    <div class="card shadow p-4" style="width: 350px;">
        <h3 class="text-center mb-3">Aşı Takip Girişi</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">Kullanıcı Adı</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Şifre</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary w-100">Giriş Yap</button>
        </form>
    </div>
</body>
</html>
'''

INDEX_HTML = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Aşı Takip ve İstem Formu</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Aşı Takip ve İstem Çizelgesi ({{ session['username'] }})</h2>
            <a href="/logout" class="btn btn-danger btn-sm">Çıkış Yap</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        <form method="POST">
            <table class="table table-bordered bg-white shadow-sm">
                <thead class="table-dark">
                    <tr>
                        <th>AŞILAR</th>
                        <th>ELİMİZDE OLAN</th>
                        <th>İSTENİLEN</th>
                    </tr>
                </thead>
                <tbody>
                    {% for vaccine in vaccines %}
                    <tr>
                        <td><strong>{{ vaccine }}</strong></td>
                        <td><input type="number" name="stock_{{ vaccine }}" value="{{ entries[vaccine].stock_qty if vaccine in entries else 0 }}" class="form-control" min="0"></td>
                        <td><input type="number" name="requested_{{ vaccine }}" value="{{ entries[vaccine].requested_qty if vaccine in entries else 0 }}" class="form-control" min="0"></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <button type="submit" class="btn btn-success btn-lg w-100">Verileri Kaydet / Güncelle</button>
        </form>
    </div>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Yönetici Rapor Paneli</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Yönetici Rapor Paneli</h2>
            <a href="/logout" class="btn btn-danger btn-sm">Çıkış Yap</a>
        </div>
        <div class="row">
            <div class="col-md-4">
                <div class="card shadow-sm mb-4">
                    <div class="card-header bg-primary text-white">Kullanıcı Veri Giriş Durumu</div>
                    <ul class="list-group list-group-flush">
                        {% for u in user_status %}
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            {{ u.username }}
                            {% if u.has_entered %}
                                <span class="badge bg-success">Veri Girdi</span>
                            {% else %}
                                <span class="badge bg-danger">Bekliyor</span>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
            <div class="col-md-8">
                <div class="card shadow-sm">
                    <div class="card-header bg-dark text-white">Genel Toplam Raporu</div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Aşı Adı</th>
                                    <th>Toplam Elimizdeki</th>
                                    <th>Toplam İstenilen</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for vaccine, data in totals.items() %}
                                <tr>
                                    <td><strong>{{ vaccine }}</strong></td>
                                    <td>{{ data.stock }}</td>
                                    <td>{{ data.requested }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

# --- ROTALAR ---

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
    return render_template_string(LOGIN_HTML)

@app.route('/panel', methods=['GET', 'POST'])
def user_panel():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect(url_for('login'))
    user_id = session['user_id']
    if request.method == 'POST':
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
    
    existing_entries = {e.vaccine_name: e for e in VaccineEntry.query.filter_by(user_id=user_id).all()}
    return render_template_string(INDEX_HTML, vaccines=VACCINE_LIST, entries=existing_entries)

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    users = User.query.filter_by(is_admin=False).all()
    user_status = []
    for u in users:
        has_entered = VaccineEntry.query.filter_by(user_id=u.id).first() is not None
        user_status.append({'username': u.username, 'has_entered': has_entered})
        
    totals = {}
    for vaccine in VACCINE_LIST:
        total_stock = db.session.query(db.func.sum(VaccineEntry.stock_qty)).filter_by(vaccine_name=vaccine).scalar() or 0
        total_requested = db.session.query(db.func.sum(VaccineEntry.requested_qty)).filter_by(vaccine_name=vaccine).scalar() or 0
        totals[vaccine] = {'stock': total_stock, 'requested': total_requested}

    return render_template_string(ADMIN_HTML, user_status=user_status, totals=totals)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login')) 
    
with app.app_context():
    db.create_all()
    
    # Yönetici (Admin) hesabı yoksa oluşturalım
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
    
    # 29 Birimin kullanıcı adı listesi
    birim_usernames = [
        'anadolu', 'asiye_dokumcu', 'bolluca', 'bogazkoy', 'deliklikaya', 
        'durusu', 'hadimkoy', 'haracci', 'kasgarli_mahmut', 'merkez', 
        'tayakadin', 'tasoluk', 'imrahor', 'verem_savas_dispanseri', 
        'devlet_hastanesi', 'ozel_avrupa_hospital', 'gocmen_sagligi_merkezi', 
        'hadimkoy_vefa', 'tasoluk_cavit_beskardes', 'nezihe_ozel', 
        '7_nolu_islambey', 'seyfettin_selim', '2_nolu_gocmen_sagligi_merkezi', 
        '8_nolu', 'mustafa_yenigun', '9_nolu', '1_nolu', 
        'abdullah_dokumcu', 'basaksehir_cam_ve_sakura_sehir_hastanesi_egitim'
    ]
    
    for uname in birim_usernames:
        if not User.query.filter_by(username=uname).first():
            user_account = User(username=uname, password=generate_password_hash('123456'), is_admin=False)
            db.session.add(user_account)
            
    db.session.commit()
