from __future__ import annotations
import pytest
from app import app, db

@pytest.fixture
def client():
    """Membuat client testing khusus untuk Flask."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"  # Pakai database RAM yang bersih untuk tes
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()  # Buat tabel sementara untuk testing
        yield client

def test_home_endpoint(client):
    """Menguji apakah halaman utama (katalog) merespons dengan sukses (200 OK)."""
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "Street N Brew" in response.text, "Judul aplikasi tidak ditemukan di halaman."

def test_cart_endpoint(client):
    """Menguji apakah endpoint keranjang dapat diakses."""
    response = client.get("/cart")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

def test_dana_qr_endpoint(client):
    """Menguji apakah endpoint QR DANA menghasilkan gambar PNG yang valid."""
    response = client.get("/payment/dana-qr.png")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.headers.get("content-type", "").startswith("image/png"), "Bukan format gambar PNG."
    assert response.data.startswith(b"\x89PNG"), "Header binary bukan file PNG valid."

def test_invalid_quantity_handling(client):
    """Negative Testing: Mengirim quantity non-numerik harus ditolak."""
    from app import db, Product, ProductVariant  # Menggunakan kelas yang benar dari app.py
    
    with client.application.app_context():
        # 1. Buat kategori dummy jika belum ada (opsional, tapi bagus untuk relasi)
        from app import Category
        category = db.session.get(Category, 1)
        if not category:
            category = Category(id=1, name="Coffee")
            db.session.add(category)
            db.session.commit()

        # 2. Buat Product dummy jika ID 1 belum ada
        if not db.session.get(Product, 1):
            dummy_product = Product(id=1, name="Kopi Dummy", category_id=1)
            db.session.add(dummy_product)
            db.session.commit()
            
        # 3. Buat ProductVariant dummy dengan ID 1 agar rute /add_to_cart/1 bisa menemukannya
        if not db.session.get(ProductVariant, 1):
            dummy_variant = ProductVariant(id=1, product_id=1, variant_name="Hot", price=15000)
            db.session.add(dummy_variant)
            db.session.commit()

    # 4. Kirim request POST dengan quantity non-numerik
    response = client.post(
        "/add_to_cart/1",
        data={"quantity": "bukan-angka"},
        follow_redirects=False
    )
    assert response.status_code in (400, 422, 302), (
        f"Seharusnya ditolak, tetapi mendapat status {response.status_code}"
    )

def test_unauthenticated_cashier_redirect(client):
    """Menguji keamanan: Mengakses halaman kasir tanpa login harus dialihkan (302)."""
    response = client.get("/kasir/dashboard", follow_redirects=False)
    assert response.status_code == 302, f"Seharusnya redirect 302, tetapi mendapat status {response.status_code}"
    assert "/login" in response.headers.get("Location", ""), "Redirect bukan menuju halaman login."