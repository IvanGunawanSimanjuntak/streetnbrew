from __future__ import annotations
import requests

BASE_URL = "http://127.0.0.1:5000"

def test_home_endpoint():
    """Menguji apakah halaman utama (katalog) merespons dengan sukses (200 OK)."""
    response = requests.get(BASE_URL + "/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "Street N Brew" in response.text, "Judul aplikasi tidak ditemukan di halaman."


def test_cart_endpoint():
    """Menguji apakah endpoint keranjang dapat diakses."""
    response = requests.get(BASE_URL + "/cart")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_dana_qr_endpoint():
    """Menguji apakah endpoint QR DANA menghasilkan gambar PNG yang valid."""
    response = requests.get(BASE_URL + "/payment/dana-qr.png")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.headers.get("content-type", "").startswith("image/png"), "Bukan format gambar PNG."
    assert response.content.startswith(b"\x89PNG"), "Header binary bukan file PNG valid."


def test_invalid_quantity_handling():
    """Negative Testing: Mengirim quantity non-numerik harus ditolak dengan error 400/422."""
    # Mencoba mengirim form POST dengan quantity ngawur ke varian ID 1
    response = requests.post(
        BASE_URL + "/add_to_cart/1",
        data={"quantity": "bukan-angka"},
        allow_redirects=False
    )
    # Server harus menolak input tidak valid (biasanya status 400 Bad Request atau 422)
    assert response.status_code in (400, 422), (
        f"Seharusnya ditolak dengan 400/422, tetapi server merespons dengan status {response.status_code}"
    )


def test_unauthenticated_cashier_redirect():
    """Menguji keamanan: Mengakses halaman kasir tanpa login harus dialihkan (redirect/302 atau login page)."""
    response = requests.get(BASE_URL + "/kasir/dashboard", allow_redirects=False)
    # Harus diredirect (biasanya 302 ke halaman login)
    assert response.status_code == 302, f"Seharusnya redirect 302, tetapi mendapat status {response.status_code}"
    assert "/login" in response.headers.get("Location", ""), "Redirect bukan menuju halaman login."