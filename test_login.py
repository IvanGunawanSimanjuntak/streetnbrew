"""Full Playwright smoke and workflow tests for the Street N Brew web app.

The suite creates and completes two orders; these test records remain in the
database because the app has no order-deletion route.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import date
from typing import Callable
from urllib.parse import urljoin, urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    sync_playwright,
)


DEFAULT_BASE_URL = "http://127.0.0.1:5000"
TIMEOUT_MS = 10_000


@dataclass
class TestResult:
    name: str
    status: str
    detail: str = ""


class TestSuite:
    def __init__(
        self,
        base_url: str,
        browser: Browser,
        page: Page,
        context: BrowserContext,
        username: str,
        password: str,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.browser = browser
        self.page = page
        self.context = context
        self.username = username
        self.password = password
        self.results: list[TestResult] = []
        self.order_id: str | None = None
        self.authenticated = False
        self.browser_errors: list[str] = []
        self.server_errors: list[str] = []

        context.on("page", self._watch_page)
        self._watch_page(page)

    def _watch_page(self, page: Page) -> None:
        page.on("pageerror", lambda error: self.browser_errors.append(str(error)))
        page.on("response", self._watch_response)

    def _watch_response(self, response) -> None:
        if response.status >= 500 and response.url.startswith(self.base_url):
            self.server_errors.append(f"{response.status} {response.url}")

    def url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def run(self, name: str, action: Callable[[], str | None]) -> None:
        try:
            detail = action() or ""
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.results.append(TestResult(name, "FAIL", detail))
            print(f"\n--- Detail kegagalan: {name} ---", file=sys.stderr)
            traceback.print_exc()
        else:
            self.results.append(TestResult(name, "PASS", detail))

    def require_credentials(self) -> None:
        if not self.username or not self.password:
            raise RuntimeError("Kredensial kasir belum tersedia.")

    def require_authenticated(self) -> None:
        self.require_credentials()
        if not self.authenticated:
            raise RuntimeError("Tes terlindungi tidak dapat berjalan karena login kasir gagal.")

    def open(self, path: str):
        return self.page.goto(self.url(path), wait_until="domcontentloaded")

    def test_customer_pages(self) -> str:
        response = self.open("/")
        assert response is not None and response.status == 200, "Halaman menu tidak merespons 200."
        assert self.page.locator(".menu-card").count() > 0, "Katalog tidak menampilkan produk."
        assert self.page.locator("#orderToggle").count() == 1
        return f"Katalog menampilkan {self.page.locator('.menu-card').count()} produk."

    def test_cart_page(self) -> str:
        response = self.open("/cart")
        assert response is not None and response.status == 200, "Halaman keranjang gagal dibuka."
        assert self.page.get_by_role("heading", name="Keranjang Belanja Anda").is_visible()
        return "Route keranjang dapat dibuka."

    def test_cart_checkout_link(self) -> str:
        test_context = self.browser.new_context()
        try:
            test_page = test_context.new_page()
            test_page.set_default_timeout(TIMEOUT_MS)
            test_page.goto(self.url("/"), wait_until="domcontentloaded")
            variant_action = test_page.locator(
                'form[action^="/add_to_cart/"]'
            ).first.get_attribute("action")
            assert variant_action, "Tidak ada produk/varian untuk menguji keranjang."
            add_response = test_context.request.post(
                self.url(variant_action),
                form={"quantity": "1"},
                max_redirects=0,
            )
            assert add_response.status == 302, (
                f"Tambah item seharusnya redirect; status {add_response.status}."
            )
            test_page.goto(self.url("/cart"), wait_until="domcontentloaded")
            link = test_page.get_by_role("link", name=re.compile("Lanjut ke Pembayaran"))
            assert link.count(), "Tombol checkout tidak tampil pada keranjang berisi item."
            assert link.get_attribute("href") == "/checkout"
            response = test_context.request.get(
                self.url("/checkout"),
                max_redirects=0,
            )
            assert response.status == 200, (
                f"Tautan checkout membuka GET /checkout, tetapi merespons "
                f"{response.status}; halaman checkout tidak dapat dibuka. "
                "Jika kode aplikasi sudah diperbarui, hentikan dan jalankan ulang server Flask."
            )
            assert "Informasi Pemesan" in response.text()
        finally:
            test_context.close()
        return "Route checkout dapat dibuka menggunakan tautan GET dari halaman keranjang."

    def test_empty_checkout(self) -> str:
        response = self.context.request.post(
            self.url("/checkout"),
            form={"customer_name": "Playwright Empty Cart", "payment_method": "Transfer DANA"},
            max_redirects=0,
        )
        assert response.status == 302, (
            f"Checkout keranjang kosong seharusnya dialihkan, status {response.status}."
        )
        assert response.headers.get("location", "").endswith("/")
        self.open("/")
        assert self.page.get_by_role("alert").filter(
            has_text="Keranjang belanja masih kosong!"
        ).is_visible()
        return "Checkout tanpa item ditolak dan menampilkan pesan."

    def test_qr_image(self) -> str:
        response = self.context.request.get(self.url("/payment/dana-qr.png"))
        assert response.status == 200, f"QR DANA merespons {response.status}."
        assert response.headers.get("content-type", "").startswith("image/png")
        assert response.body().startswith(b"\x89PNG"), "Respons bukan file PNG yang valid."
        return "Endpoint QR menghasilkan PNG yang valid."

    def test_responsive_menu(self) -> str:
        for width, height in ((1440, 900), (768, 1024), (390, 844)):
            self.page.set_viewport_size({"width": width, "height": height})
            self.open("/")
            assert self.page.locator(".menu-card").first.is_visible()
            assert self.page.locator("#orderToggle").is_visible()
        self.page.set_viewport_size({"width": 1440, "height": 900})
        return "Menu dan kontrol Current Order terlihat pada desktop, tablet, dan ponsel."

    def test_unauthenticated_routes(self) -> str:
        unauth_context = self.browser.new_context()
        try:
            unauth_page = unauth_context.new_page()
            for path in (
                "/kasir/pos",
                "/kasir/dashboard",
                "/kasir/laporan",
                "/kasir/laporan/pdf",
                "/kasir/cetak_struk/1",
            ):
                response = unauth_page.goto(self.url(path), wait_until="domcontentloaded")
                assert response is not None
                assert unauth_page.url.startswith(self.url("/login")), (
                    f"{path} tidak dialihkan ke halaman login (URL: {unauth_page.url})."
                )
        finally:
            unauth_context.close()
        return "Semua route kasir yang diperiksa meminta login."

    def test_invalid_login(self) -> str:
        self.open("/login")
        self.page.locator('input[name="username"]').fill("playwright-invalid-user")
        self.page.locator('input[name="password"]').fill("invalid-password-for-test")
        self.page.get_by_role("button", name=re.compile("Masuk")).click()
        assert self.page.get_by_role("alert").filter(
            has_text="Username atau password salah."
        ).is_visible(), "Pesan login gagal tidak muncul."
        return "Satu percobaan login gagal ditolak dengan pesan yang sesuai."

    def login(self) -> str:
        self.require_credentials()
        response = self.open("/login?next=/kasir/dashboard")
        assert response is not None and response.status == 200
        self.page.locator('input[name="username"]').fill(self.username)
        self.page.locator('input[name="password"]').fill(self.password)
        self.page.get_by_role("button", name=re.compile("Masuk")).click()
        self.page.wait_for_url(re.compile(r"/kasir/(dashboard|pos)$"))
        assert self.page.locator("table tbody").is_visible(), "Daftar pesanan tidak tampil."
        self.authenticated = True
        return f"Login berhasil; diarahkan ke {urlparse(self.page.url).path}."

    def test_dashboard_links_and_orders(self) -> str:
        self.require_authenticated()
        self.open("/kasir/dashboard")
        assert self.page.get_by_role("heading", name="Manajemen Pesanan Masuk").is_visible()
        assert self.page.get_by_role("link", name=re.compile("E-Menu Pelanggan")).count() >= 1
        assert self.page.locator("#liveTime").is_visible()
        assert self.page.locator("#liveDate").is_visible()
        return "Dashboard pesanan, tautan E-Menu, jam, dan tanggal tampil."

    def test_report_filters(self) -> str:
        self.require_authenticated()
        for period in ("minggu_ini", "bulan_ini", "semua"):
            response = self.context.request.get(
                self.url(f"/kasir/laporan?periode={period}")
            )
            assert response.status == 200, f"Filter {period} merespons {response.status}."

        today = date.today().isoformat()
        response = self.context.request.get(
            self.url(
                f"/kasir/laporan?periode=custom&tanggal_mulai={today}"
                f"&tanggal_akhir={today}"
            )
        )
        assert response.status == 200, "Filter satu hari gagal."

        response = self.context.request.get(
            self.url("/kasir/laporan?periode=custom&tanggal_mulai=invalid&tanggal_akhir=invalid")
        )
        assert response.status == 400, f"Tanggal invalid merespons {response.status}, bukan 400."

        response = self.context.request.get(
            self.url("/kasir/laporan?periode=custom&tanggal_mulai=2026-10-29&tanggal_akhir=2026-10-28")
        )
        assert response.status == 400, "Rentang tanggal terbalik tidak ditolak."

        response = self.context.request.get(self.url("/kasir/laporan?periode=tidak_valid"))
        assert response.status == 400, "Periode tidak dikenal tidak ditolak."
        return "Semua filter periode valid diterima; input tanggal/periode salah ditolak."

    def test_report_pdf(self) -> str:
        self.require_authenticated()
        response = self.context.request.get(self.url("/kasir/laporan/pdf?periode=semua"))
        assert response.status == 200, f"Ekspor PDF merespons {response.status}."
        assert response.headers.get("content-type", "").startswith("application/pdf")
        assert response.body().startswith(b"%PDF"), "Respons bukan dokumen PDF valid."
        return "Ekspor menghasilkan dokumen PDF yang valid."

    def test_csrf_protection(self) -> str:
        self.require_authenticated()
        responses = (
            self.context.request.post(self.url("/logout")),
            self.context.request.post(self.url("/clear_cart")),
            self.context.request.post(self.url("/kasir/pesanan/1/selesai")),
        )
        assert all(response.status == 400 for response in responses), (
            "POST tanpa CSRF token seharusnya ditolak dengan 400; "
            f"status aktual: {[response.status for response in responses]}."
        )
        return "Logout, kosongkan keranjang, dan konfirmasi pembayaran menolak CSRF kosong."

    def test_unknown_records(self) -> str:
        self.require_authenticated()
        missing_order = self.context.request.get(self.url("/kasir/cetak_struk/999999999"))
        assert missing_order.status == 404, (
            f"Struk pesanan tidak dikenal merespons {missing_order.status}."
        )
        missing_variant = self.context.request.post(
            self.url("/add_to_cart/999999999"),
            form={"quantity": "1"},
        )
        assert missing_variant.status == 404, (
            f"Varian tidak dikenal merespons {missing_variant.status}."
        )
        self.open("/")
        variant_action = self.page.locator('form[action^="/add_to_cart/"]').first.get_attribute("action")
        assert variant_action, "Form tambah pesanan tidak ditemukan."
        malformed_quantity = self.context.request.post(
            self.url(variant_action),
            form={"quantity": "bukan-angka"},
        )
        assert malformed_quantity.status in (400, 422), (
            f"Quantity non-numerik seharusnya ditolak dengan 400/422, "
            f"tetapi mendapat {malformed_quantity.status}."
        )
        return "ID pesanan dan varian yang tidak ada menghasilkan 404."

    def test_write_workflows(self) -> str:
        self.require_authenticated()
        self.open("/")
        assert self.page.locator(".menu-card").count() > 0, "Tidak ada produk untuk diuji."

        product = self.page.locator(".menu-card").first
        product_name = product.locator(".card-title").inner_text().strip()
        product.get_by_role("button", name=re.compile("Tambah Pesanan")).click()
        
        # Menunggu modal varian muncul dengan aman
        modal = self.page.locator(".modal.show")
        modal.wait_for(state="visible")
        
        add_buttons = modal.locator('button[type="submit"]')
        assert add_buttons.count() > 0, "Tidak ada pilihan varian Hot/Ice."
        add_buttons.first.click()
        
        self.page.wait_for_load_state("domcontentloaded")
        assert self.page.locator(".order-items .list-group-item").count() == 1

        first_item = self.page.locator(".order-items .list-group-item").first
        first_item.locator('button[name="action"][value="increase"]').click()
        first_item = self.page.locator(".order-items .list-group-item").first
        assert first_item.locator(".quantity-value").inner_text().strip() == "2"
        first_item.locator('button[name="action"][value="decrease"]').click()
        first_item = self.page.locator(".order-items .list-group-item").first
        assert first_item.locator(".quantity-value").inner_text().strip() == "1"

        self.page.once("dialog", lambda dialog: dialog.dismiss())
        self.page.locator('button.btn-outline-danger, button:has-text("Kosongkan")').first.click()
        assert self.page.locator(".order-items .list-group-item").count() == 1
        
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator('button.btn-outline-danger, button:has-text("Kosongkan")').first.click()
        assert self.page.get_by_text("Belum ada item dipilih").is_visible()

        product = self.page.locator(".menu-card").first
        product.get_by_role("button", name=re.compile("Tambah Pesanan")).click()
        modal = self.page.locator(".modal.show")
        modal.wait_for(state="visible")
        modal.locator('button[type="submit"]').first.click()
        self.page.wait_for_load_state("domcontentloaded")

        name_input = self.page.locator('input[name="customer_name"]')
        name_input.fill("")
        assert not name_input.evaluate("(input) => input.form.checkValidity()"), (
            "Form checkout mengizinkan nama kosong."
        )
        name_input.fill("Playwright Test")
        self.page.locator('label[for="payment-dana"]').click()
        assert self.page.locator("#payment-dana").is_checked()
        self.page.get_by_role("button", name=re.compile("Proceed to Payment")).click()
        self.page.wait_for_url(re.compile(r"/order/success/\d+$"))
        self.order_id = self.page.url.rsplit("/", 1)[-1]
        assert self.page.get_by_text("Playwright Test").is_visible()
        assert self.page.get_by_role("heading", name="Transfer DANA").is_visible()
        assert self.page.locator('img[alt*="Kode QR"]').is_visible()

        complete_button = self.page.get_by_role("button", name=re.compile("Selesai"))
        assert complete_button.is_visible(), "Tombol konfirmasi kasir tidak tampil."
        complete_button.click()
        self.page.wait_for_url(re.compile(r"/order/success/\d+$"))
        assert self.page.get_by_role("heading", name="Pembayaran Berhasil").is_visible()

        receipt = self.context.request.get(
            self.url(f"/kasir/cetak_struk/{self.order_id}")
        )
        assert receipt.status == 200
        assert "text/html" in receipt.headers.get("content-type", "")
        assert "Playwright Test" in receipt.text()

        self.open("/")
        product = self.page.locator(".menu-card").first
        product.get_by_role("button", name=re.compile("Tambah Pesanan")).click()
        modal = self.page.locator(".modal.show")
        modal.wait_for(state="visible")
        modal.locator('button[type="submit"]').first.click()
        self.page.wait_for_load_state("domcontentloaded")
        self.page.locator('input[name="customer_name"]').fill("Playwright Test Tunai")
        self.page.locator('label[for="payment-cash"]').click()
        assert self.page.locator("#payment-cash").is_checked()
        self.page.get_by_role("button", name=re.compile("Proceed to Payment")).click()
        self.page.wait_for_url(re.compile(r"/order/success/\d+$"))
        cash_order_id = self.page.url.rsplit("/", 1)[-1]
        assert self.page.get_by_role("heading", name="Pesanan Berhasil Dibuat!").is_visible()
        assert self.page.locator('img[alt*="Kode QR"]').count() == 0

        self.page.get_by_role("button", name=re.compile("Selesai")).click()
        self.page.wait_for_url(re.compile(r"/order/success/\d+$"))
        assert self.page.get_by_role("heading", name="Pembayaran Berhasil").is_visible()

        cash_receipt = self.context.request.get(
            self.url(f"/kasir/cetak_struk/{cash_order_id}")
        )
        assert cash_receipt.status == 200
        assert "Playwright Test Tunai" in cash_receipt.text()

        self.open("/kasir/dashboard")
        assert self.page.get_by_role("cell", name=re.compile(r"^Playwright Test$")).first.is_visible()
        assert self.page.get_by_role("cell", name="Playwright Test Tunai").first.is_visible()
        return (
            "Keranjang, kuantitas, hapus, checkout DANA/Tunai, QR, konfirmasi, "
            f"dashboard, dan struk lulus (order {self.order_id}, {cash_order_id}; "
            f"produk {product_name})."
        )

    def test_logout(self) -> str:
        self.require_authenticated()
        csrf = self.page.locator('form[action="/logout"] input[name="csrf_token"]').get_attribute("value")
        assert csrf, "Token CSRF logout tidak ditemukan."
        self.page.locator('form[action="/logout"] button[type="submit"]').click()
        self.page.wait_for_url(re.compile(r"/login$"))
        self.authenticated = False
        response = self.page.goto(self.url("/kasir/dashboard"), wait_until="domcontentloaded")
        assert response is not None
        assert self.page.url.startswith(self.url("/login")), "Sesi tetap aktif setelah logout."
        return "Logout berhasil; dashboard kembali meminta login."

    def print_summary(self) -> int:
        print("\n--- Hasil Uji Street N Brew ---")
        for result in self.results:
            suffix = f" — {result.detail}" if result.detail else ""
            print(f"[{result.status:4}] {result.name}{suffix}")

        if self.browser_errors:
            print("\n--- JavaScript errors ---")
            for error in dict.fromkeys(self.browser_errors):
                print(f"[ERROR] {error}")
        if self.server_errors:
            print("\n--- Respons server 5xx ---")
            for error in dict.fromkeys(self.server_errors):
                print(f"[ERROR] {error}")

        passed = sum(result.status == "PASS" for result in self.results)
        failed = sum(result.status == "FAIL" for result in self.results)
        print(f"\nRingkasan: {passed} berhasil, {failed} gagal.")
        if self.browser_errors or self.server_errors:
            print("Ada error browser/server yang perlu ditinjau.")
            failed += 1
        return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jalankan pengujian Playwright untuk fitur website Street N Brew."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("STREETNBREW_BASE_URL", DEFAULT_BASE_URL),
        help=f"URL aplikasi (default: {DEFAULT_BASE_URL}, atau STREETNBREW_BASE_URL).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Tampilkan browser saat tes berjalan.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    username = os.getenv("STAFF_USERNAME", "")
    password = os.getenv("STAFF_PASSWORD", "")
    if not username:
        username = input("Username kasir: ").strip()
    if not password:
        password = getpass.getpass("Password kasir: ")
    if not username or not password:
        print("Username dan password wajib diisi; pengujian dibatalkan.")
        return 2

    base_url = args.base_url.rstrip("/") + "/"

    print(f"Target aplikasi: {base_url}")
    print("Mode: pengujian penuh.")
    print(
        "PERINGATAN: pengujian checkout membuat dua pesanan lokal dan "
        "mengonfirmasinya selesai. Data tersebut akan tetap ada di database."
    )

    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.set_default_timeout(TIMEOUT_MS)
        page = context.new_page()
        suite = TestSuite(
            base_url=base_url,
            browser=browser,
            page=page,
            context=context,
            username=username,
            password=password,
        )

        suite.run("Halaman katalog pelanggan", suite.test_customer_pages)
        suite.run("Halaman keranjang", suite.test_cart_page)
        suite.run("Tautan checkout dari keranjang", suite.test_cart_checkout_link)
        suite.run("Endpoint QR DANA", suite.test_qr_image)
        suite.run("Responsivitas halaman menu", suite.test_responsive_menu)
        suite.run("Checkout saat keranjang kosong", suite.test_empty_checkout)
        suite.run("Perlindungan route kasir tanpa login", suite.test_unauthenticated_routes)
        suite.run("Login dengan kredensial salah", suite.test_invalid_login)
        suite.run("Login kasir valid dan dashboard", suite.login)
        suite.run("Dashboard pesanan dan navigasi", suite.test_dashboard_links_and_orders)
        suite.run("Filter laporan dan validasi tanggal", suite.test_report_filters)
        suite.run("Ekspor laporan PDF", suite.test_report_pdf)
        suite.run("Perlindungan CSRF", suite.test_csrf_protection)
        suite.run("Penanganan ID data yang tidak ada", suite.test_unknown_records)
        suite.run("Alur tulis keranjang sampai pembayaran", suite.test_write_workflows)
        suite.run("Logout dan invalidasi sesi", suite.test_logout)

        exit_code = suite.print_summary()
        context.close()
        browser.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())