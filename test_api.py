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