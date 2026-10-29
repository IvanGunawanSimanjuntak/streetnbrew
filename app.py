import hmac
import os
import qrcode
import secrets
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from functools import wraps
from urllib.parse import urlsplit

from flask import Flask, abort, render_template, request, redirect, send_file, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from collections import defaultdict

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true',
)

# Menggunakan DATABASE_URL dari environment jika ada, jika tidak gunakan PostgreSQL lokal
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'streetnbrew.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 
    f'sqlite:///{db_path}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
LOGIN_FAILURES = {}
DANA_MERCHANT_NUMBER = '081262099033'


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('staff_authenticated'):
            destination = request.path if request.method == 'GET' else url_for('kasir_pos')
            return redirect(url_for('staff_login', next=destination))
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']

    return {'csrf_token': csrf_token}


def valid_csrf_token():
    submitted_token = request.form.get('csrf_token', '')
    expected_token = session.get('csrf_token', '')
    return bool(expected_token) and hmac.compare_digest(submitted_token, expected_token)


def find_active_staff_user(username):
    return StaffUser.query.filter_by(username=username, is_active=True).first()


@app.route('/login', methods=['GET', 'POST'])
def staff_login():
    if session.get('staff_authenticated'):
        return redirect(url_for('kasir_pos'))

    if request.method == 'POST':
        if not valid_csrf_token():
            abort(400)

        attempt_key = request.remote_addr or 'unknown'
        now = time.monotonic()
        attempts = [
            failed_at for failed_at in LOGIN_FAILURES.get(attempt_key, [])
            if now - failed_at < 300
        ]
        if len(attempts) >= 5:
            LOGIN_FAILURES[attempt_key] = attempts
            flash('Terlalu banyak percobaan. Silakan tunggu beberapa menit.', 'danger')
            return render_template('cashier/login.html'), 429

        submitted_username = request.form.get('username', '').strip()
        submitted_password = request.form.get('password', '')

        staff_user = find_active_staff_user(submitted_username)
        password_matches = False
        if staff_user:
            try:
                password_matches = check_password_hash(staff_user.password_hash, submitted_password)
            except (ValueError, TypeError):
                password_matches = False

        if staff_user and password_matches:
            LOGIN_FAILURES.pop(attempt_key, None)
            destination = request.args.get('next', '')
            parsed_destination = urlsplit(destination)
            if (
                not destination.startswith('/')
                or destination.startswith('//')
                or '\\' in destination
                or parsed_destination.scheme
                or parsed_destination.netloc
            ):
                destination = url_for('kasir_pos')
            session.clear()
            session['staff_authenticated'] = True
            session['staff_user_id'] = staff_user.id
            session['staff_username'] = staff_user.username
            session['staff_role'] = staff_user.role
            return redirect(destination)

        attempts.append(now)
        LOGIN_FAILURES[attempt_key] = attempts
        if len(LOGIN_FAILURES) > 5000:
            LOGIN_FAILURES.pop(next(iter(LOGIN_FAILURES)))
        flash('Username atau password salah.', 'danger')

    return render_template('cashier/login.html')


@app.route('/logout', methods=['POST'])
def staff_logout():
    if not valid_csrf_token():
        abort(400)
    session.clear()
    flash('Anda telah keluar dari akun kasir.', 'success')
    return redirect(url_for('staff_login'))

# ==================== DATABASE MODELS ====================
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    variants = db.relationship('ProductVariant', backref='product', lazy=True, cascade="all, delete-orphan")

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    variant_name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    table_number = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='Menunggu Pembayaran')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    variant_name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


class StaffUser(db.Model):
    __tablename__ = 'staff_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cashier')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# ==================== ROUTES ====================

@app.route('/')
def index():
    products = Product.query.all()
    cart = session.get('cart', {})
    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())

    return render_template('customer/index.html',
                           products=products,
                           cart=cart,
                           subtotal=subtotal)

@app.route('/add_to_cart/<int:variant_id>', methods=['POST'])
def add_to_cart(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    product = variant.product
    
    raw_quantity = request.form.get('quantity', 1)
    try:
        quantity = int(raw_quantity)
        if quantity <= 0:
            abort(400)
    except (ValueError, TypeError):
        abort(400)
    
    cart_key = str(variant_id)
    cart = session.get('cart', {})
    
    if cart_key in cart:
        cart[cart_key]['quantity'] += quantity
    else:
        cart[cart_key] = {
            'product_id': product.id,
            'product_name': product.name,
            'variant_id': variant.id,
            'variant_name': variant.variant_name,
            'price': float(variant.price),
            'quantity': quantity,
            'image_url': product.image_url
        }
        
    session['cart'] = cart
    return redirect(url_for('index'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('customer/cart.html', cart=cart, subtotal=subtotal)

@app.route('/update_cart/<cart_key>', methods=['POST'])
def update_cart(cart_key):
    action = request.form.get('action')
    cart = session.get('cart', {})
    
    if cart_key in cart:
        if action == 'increase':
            cart[cart_key]['quantity'] += 1
        elif action == 'decrease':
            cart[cart_key]['quantity'] -= 1
            if cart[cart_key]['quantity'] <= 0:
                del cart[cart_key]
        elif action == 'delete':
            del cart[cart_key]
            
    session['cart'] = cart
    return redirect(url_for('index'))

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    if not valid_csrf_token():
        abort(400)
    session.pop('cart', None)
    return redirect(url_for('index'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Keranjang belanja masih kosong!', 'danger')
        return redirect(url_for('index'))

    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    if request.method == 'GET':
        return render_template('customer/checkout.html', subtotal=subtotal)

    customer_name = request.form.get('customer_name')
    table_number = request.form.get('table_number', '').strip() or 'N/A'
    payment_method = request.form.get('payment_method')

    if not customer_name or not payment_method:
        flash('Mohon lengkapi Nama Pemesan dan Metode Pembayaran.', 'danger')
        return redirect(url_for('index'))

    new_order = Order(
        customer_name=customer_name,
        table_number=table_number,
        payment_method=payment_method,
        total_price=subtotal
    )
    db.session.add(new_order)
    db.session.flush()

    for item in cart.values():
        order_item = OrderItem(
            order_id=new_order.id,
            product_name=item['product_name'],
            variant_name=item['variant_name'],
            price=item['price'],
            quantity=item['quantity']
        )
        db.session.add(order_item)

    db.session.commit()
    session.pop('cart', None)
    return redirect(url_for('order_success', order_id=new_order.id))

@app.route('/order/success/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    wa_number = "6281262099033"
    items_text = "".join([f"\n- {item.product_name} ({item.variant_name}) x{item.quantity}" for item in order.items])
    wa_message = f"Halo Kak, saya {order.customer_name} telah melakukan pesanan via E-Menu dengan metode pembayaran *{order.payment_method}*.\n\nDetail Pesanan:{items_text}\n\nTotal: Rp {int(order.total_price):,}".replace(",", ".")
    
    return render_template(
        'customer/success.html',
        order=order,
        wa_number=wa_number,
        wa_message=wa_message,
        dana_merchant_number=DANA_MERCHANT_NUMBER,
    )


@app.route('/payment/dana-qr.png')
def dana_number_qr():
    qr_image = qrcode.make(DANA_MERCHANT_NUMBER)
    image_buffer = BytesIO()
    qr_image.save(image_buffer, format='PNG')
    image_buffer.seek(0)
    return send_file(image_buffer, mimetype='image/png')


# ==================== ROUTES KASIR / POS ====================

@app.route('/kasir/pos')
@app.route('/kasir/dashboard')
@login_required
def kasir_pos():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('cashier/pos.html', orders=orders)

@app.route('/kasir/pesanan/<int:order_id>/selesai', methods=['POST'])
@login_required
def complete_order_payment(order_id):
    if not valid_csrf_token():
        abort(400)
    order = Order.query.get_or_404(order_id)
    if order.status != 'Selesai':
        order.status = 'Selesai'
        db.session.commit()
        flash('Pembayaran berhasil dikonfirmasi.', 'success')
    return redirect(url_for('order_success', order_id=order.id))

@app.route('/kasir/laporan')
@login_required
def kasir_laporan():
    report = build_report_data()
    return render_template('cashier/laporan.html', **report)


@app.route('/kasir/laporan/pdf')
@login_required
def kasir_laporan_pdf():
    report = build_report_data()
    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title='Laporan Keuangan Street N Brew',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        alignment=TA_LEFT,
        textColor=colors.HexColor('#173f32'),
        spaceAfter=4 * mm,
    ))
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
    ))

    story = [
        Paragraph('Laporan Keuangan - Street N Brew', styles['ReportTitle']),
        Paragraph(f"Periode: {escape(report['period_label'])}", styles['BodyText']),
        Spacer(1, 4 * mm),
        Paragraph(
            f"Pendapatan selesai: Rp {report['total_pendapatan']:,.0f}".replace(',', '.')
            + f" &nbsp;&nbsp; | &nbsp;&nbsp; Pesanan selesai: {report['pesanan_selesai_count']}"
            + f" &nbsp;&nbsp; | &nbsp;&nbsp; Total transaksi: {report['total_pesanan']}",
            styles['BodyText'],
        ),
        Spacer(1, 5 * mm),
    ]
    cell_style = styles['TableCell']
    table_data = [[
        'ID', 'Waktu', 'Pelanggan', 'Metode Pembayaran', 'Total', 'Status',
    ]]
    for order in report['all_orders']:
        table_data.append([
            str(order.id),
            order.created_at.strftime('%d/%m/%Y %H:%M'),
            Paragraph(escape(order.customer_name), cell_style),
            Paragraph(escape(order.payment_method), cell_style),
            f"Rp {order.total_price:,.0f}".replace(',', '.'),
            Paragraph(escape(order.status), cell_style),
        ])

    transactions_table = Table(
        table_data,
        colWidths=[18 * mm, 34 * mm, 52 * mm, 48 * mm, 33 * mm, 38 * mm],
        repeatRows=1,
        hAlign='LEFT',
    )
    transactions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#12372c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#d8e2db')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f8f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(transactions_table)
    document.build(story)
    pdf_buffer.seek(0)
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='laporan-keuangan-street-n-brew.pdf',
    )


@app.route('/kasir/laporan/excel')
@login_required
def kasir_laporan_excel():
    report = build_report_data()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Laporan Keuangan"
    
    header_fill = PatternFill(start_color="12372C", end_color="12372C", fill_type="solid")
    header_font = Font(name="Helvetica", size=10, bold=True, color="FFFFFF")
    title_font = Font(name="Helvetica", size=14, bold=True, color="173F32")
    normal_font = Font(name="Helvetica", size=10)
    
    border_thin = Border(
        left=Side(style='thin', color='D8E2DB'),
        right=Side(style='thin', color='D8E2DB'),
        top=Side(style='thin', color='D8E2DB'),
        bottom=Side(style='thin', color='D8E2DB')
    )

    ws.append(["Laporan Keuangan - Street N Brew"])
    ws.cell(row=1, column=1).font = title_font
    ws.append([f"Periode: {report['period_label']}"])
    ws.append([
        f"Pendapatan Selesai: Rp {int(report['total_pendapatan']):,}".replace(',', '.'),
        f"Pesanan Selesai: {report['pesanan_selesai_count']}",
        f"Total Transaksi: {report['total_pesanan']}"
    ])
    ws.append([])
    
    headers = ['ID', 'Waktu', 'Pelanggan', 'Metode Pembayaran', 'Total Harga', 'Status']
    ws.append(headers)
    
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=5, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for order in report['all_orders']:
        row_data = [
            order.id,
            order.created_at.strftime('%d/%m/%Y %H:%M'),
            order.customer_name,
            order.payment_method,
            float(order.total_price),
            order.status
        ]
        ws.append(row_data)

    for row in range(6, ws.max_row + 1):
        for col in range(1, 7):
            cell = ws.cell(row=row, column=col)
            cell.font = normal_font
            cell.border = border_thin
            if col == 5:
                cell.number_format = '"Rp "#,##0'
                cell.alignment = Alignment(horizontal="right")
            elif col in (1, 2, 6):
                cell.alignment = Alignment(horizontal="center")

    excel_buffer = BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    return send_file(
        excel_buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='laporan-keuangan-street-n-brew.xlsx'
    )


def build_report_data():
    period = request.args.get('periode', 'semua')
    today = date.today()
    start_date = None
    end_date = None

    if period == 'minggu_ini':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'bulan_ini':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'custom' or request.args.get('tanggal_mulai') or request.args.get('tanggal_akhir'):
        period = 'custom'
        try:
            start_date = date.fromisoformat(request.args.get('tanggal_mulai', ''))
            end_date = date.fromisoformat(request.args.get('tanggal_akhir', ''))
        except ValueError:
            abort(400, description='Tanggal mulai dan tanggal akhir harus diisi dengan format yang valid.')
        if end_date < start_date:
            abort(400, description='Tanggal akhir tidak boleh lebih awal dari tanggal mulai.')
    elif period != 'semua':
        abort(400, description='Pilihan periode laporan tidak valid.')

    orders_query = Order.query
    if start_date is not None and end_date is not None:
        start_at = datetime.combine(start_date, datetime.min.time())
        end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        orders_query = orders_query.filter(
            Order.created_at >= start_at,
            Order.created_at < end_at,
        )

    all_orders = orders_query.order_by(Order.created_at.desc()).all()
    orders_selesai = [order for order in all_orders if order.status == 'Selesai']
    total_pendapatan = sum(
        (order.total_price for order in orders_selesai),
        Decimal('0'),
    )

    sales_by_date = defaultdict(float)
    for order in orders_selesai:
        date_str = order.created_at.strftime('%Y-%m-%d')
        sales_by_date[date_str] += float(order.total_price)

    if period == 'minggu_ini':
        period_label = f'Minggu ini ({start_date:%d/%m/%Y} - {end_date:%d/%m/%Y})'
    elif period == 'bulan_ini':
        period_label = f'Bulan ini ({start_date:%d/%m/%Y} - {end_date:%d/%m/%Y})'
    elif period == 'custom':
        period_label = f'{start_date:%d/%m/%Y} - {end_date:%d/%m/%Y}'
    else:
        period_label = 'Semua periode'

    sorted_dates = sorted(sales_by_date.keys())
    return {
        'total_pendapatan': total_pendapatan,
        'total_pesanan': len(all_orders),
        'pesanan_selesai_count': len(orders_selesai),
        'all_orders': all_orders,
        'chart_labels': sorted_dates,
        'chart_data': [sales_by_date[day] for day in sorted_dates],
        'active_period': period,
        'tanggal_mulai': start_date.isoformat() if start_date else '',
        'tanggal_akhir': end_date.isoformat() if end_date else '',
        'period_label': period_label,
    }

# ==================== RUTE CETAK STRUK ====================
@app.route('/kasir/cetak_struk/<int:order_id>')
@login_required
def cetak_struk(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('cashier/struk.html', order=order)


# ==================== MAIN EXECUTION & SEEDER ====================
def ensure_hot_ice_variants(product, default_price):
    variants = ProductVariant.query.filter_by(product_id=product.id).order_by(ProductVariant.id).all()
    hot_variant = next((variant for variant in variants if 'hot' in variant.variant_name.lower()), None)
    ice_variant = next((variant for variant in variants if 'ice' in variant.variant_name.lower()), None)
    unused_variants = [variant for variant in variants if variant not in (hot_variant, ice_variant)]

    if hot_variant is None and unused_variants:
        hot_variant = unused_variants.pop(0)
    if ice_variant is None and unused_variants:
        ice_variant = unused_variants.pop(0)

    base_price = hot_variant.price if hot_variant else ice_variant.price if ice_variant else default_price
    if hot_variant is None:
        db.session.add(ProductVariant(product_id=product.id, variant_name='Hot', price=base_price))
    else:
        hot_variant.variant_name = 'Hot'

    if ice_variant is None:
        db.session.add(ProductVariant(product_id=product.id, variant_name='Ice', price=base_price))
    else:
        ice_variant.variant_name = 'Ice'

    for legacy_variant in unused_variants:
        legacy_variant.variant_name = f'Legacy {legacy_variant.id}'


def seed_catalog():
    coffee_category = Category.query.filter(
        Category.name.in_(['Coffee', 'Kopi Susu', 'Kopi'])
    ).first()
    if coffee_category is None:
        coffee_category = Category(name='Coffee')
        db.session.add(coffee_category)

    non_coffee_category = Category.query.filter(
        Category.name.in_(['Non-Coffee', 'Non-Kopi'])
    ).first()
    if non_coffee_category is None:
        non_coffee_category = Category(name='Non-Coffee')
        db.session.add(non_coffee_category)

    db.session.flush()
    menu_templates = [
        ('Americano', 'Espresso dengan air panas atau es yang menyegarkan.',
         'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=700&q=80', coffee_category, 18000),
        ('Cafe Latte', 'Espresso lembut dengan susu creamy.',
         'https://images.unsplash.com/photo-1570968915860-54d5c301fa9f?auto=format&fit=crop&w=700&q=80', coffee_category, 22000),
        ('Matcha Latte', 'Matcha premium dengan susu yang lembut.',
         'https://images.unsplash.com/photo-1515823064-d6e0c04616a7?auto=format&fit=crop&w=700&q=80', non_coffee_category, 24000),
        ('Chocolate Latte', 'Cokelat kaya rasa dengan susu pilihan.',
         'https://images.unsplash.com/photo-1542990253-0b8be6c4a2c5?auto=format&fit=crop&w=700&q=80', non_coffee_category, 22000),
    ]

    template_names = {menu[0] for menu in menu_templates}
    for name, description, image_url, category, price in menu_templates:
        product = Product.query.filter_by(name=name).first()
        if product is None:
            product = Product(
                name=name,
                description=description,
                image_url=image_url,
                category_id=category.id,
            )
            db.session.add(product)
            db.session.flush()
        ensure_hot_ice_variants(product, price)

    for product in Product.query.all():
        if product.name not in template_names:
            ensure_hot_ice_variants(product, 0)

    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_catalog()

    app.run(host='0.0.0.0', port=5000, debug=False)