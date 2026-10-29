# Rencana Uji Website Street N Brew

## Tujuan

Dokumen ini berisi skenario pengujian manual dan dasar untuk otomatisasi Playwright pada website lokal Street N Brew. Skenario di bawah adalah rencana uji, bukan klaim bahwa pengujian telah dijalankan atau lulus.

## Persiapan Pengujian

1. Jalankan aplikasi lokal dan pastikan halaman utama dapat dibuka.
2. Gunakan database uji, bukan database transaksi aktif. Beberapa skenario membuat pesanan atau mengubah status pembayaran.
3. Siapkan akun kasir uji yang aktif.
4. Siapkan beberapa produk dengan varian Hot/Ice serta pesanan berstatus menunggu pembayaran dan selesai.
5. Catat untuk setiap skenario: status `Lulus`, `Gagal`, atau `Tidak berlaku`, hasil aktual, URL, langkah reproduksi, dan pesan error.
6. Untuk pengujian tampilan, siapkan ukuran viewport desktop, tablet, dan ponsel.

## 1. E-Menu dan Katalog

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| MENU-01 | Buka halaman utama `/`. | Katalog tampil tanpa error. |
| MENU-02 | Periksa produk dengan dan tanpa gambar. | Gambar tampil; produk tanpa gambar tetap memiliki tampilan yang wajar. |
| MENU-03 | Klik **Tambah Pesanan**, lalu pilih varian Hot atau Ice. | Varian yang dipilih masuk ke keranjang dengan harga yang sesuai. |
| MENU-04 | Pilih varian yang sama berulang kali. | Jumlah item bertambah; subtotal dan total diperbarui dengan benar. |
| MENU-05 | Tambahkan varian berbeda dari produk yang sama. | Setiap varian tercatat sebagai item terpisah. |
| MENU-06 | Buka modal varian lalu tutup tanpa memilih. | Tidak ada item yang ditambahkan. |
| MENU-07 | Klik Dashboard Kasir dari E-Menu beberapa kali. | Perilaku tab sesuai kebutuhan; tab kasir digunakan kembali, bukan terus bertambah. |
| MENU-08 | Uji gambar produk dengan URL tidak valid. | Halaman tetap dapat digunakan dan layout tidak rusak. |

## 2. Current Order dan Keranjang

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| CART-01 | Buka halaman saat keranjang kosong. | Pesan “Belum ada item dipilih” tampil tanpa error. |
| CART-02 | Tambahkan satu item. | Item, varian, harga, jumlah, subtotal, dan total tampil benar. |
| CART-03 | Tambahkan beberapa item atau varian. | Semua item tampil dan total merupakan penjumlahan subtotalnya. |
| CART-04 | Tekan `+`. | Jumlah naik satu; subtotal dan total ikut naik. |
| CART-05 | Tekan `−` saat jumlah lebih dari satu. | Jumlah turun satu; subtotal dan total ikut turun. |
| CART-06 | Tekan `−` saat jumlah satu. | Item terhapus atau mengikuti aturan aplikasi; jumlah nol/negatif tidak tersimpan. |
| CART-07 | Hapus satu item dengan ikon tempat sampah. | Hanya item tersebut terhapus dan total dihitung ulang. |
| CART-08 | Klik **Kosongkan**, lalu pilih batal. | Keranjang tetap utuh. |
| CART-09 | Klik **Kosongkan**, lalu konfirmasi. | Seluruh item terhapus dan total menjadi nol/kosong. |
| CART-10 | Uji daftar panjang di panel keranjang. | Daftar bisa digulir; formulir dan tombol pembayaran tetap dapat diakses. |
| CART-11 | Uji gambar thumbnail item gagal dimuat. | Fallback tampil atau ruang gambar tidak merusak tampilan. |
| CART-12 | Tambahkan item, lalu muat ulang halaman dalam sesi yang sama. | Isi keranjang tetap tersedia. |
| CART-13 | Buka `/cart`. | Tabel keranjang, jumlah, subtotal, dan total cocok dengan Current Order. |
| CART-14 | Klik **Lanjut ke Pembayaran** dari `/cart`. | Checkout terbuka sesuai desain. Catatan: route `checkout` saat ini hanya menerima POST, tetapi tautan di `cart.html` mengarah dengan GET; kemungkinan menghasilkan `405 Method Not Allowed`. Verifikasi dan catat sebagai temuan jika terjadi. |

## 3. Checkout dan Pembuatan Pesanan

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| CHECK-01 | Checkout dengan nama valid, item, dan DANA. | Pesanan tercatat; halaman konfirmasi menampilkan nama, metode, dan total yang tepat. |
| CHECK-02 | Checkout dengan nama valid dan Tunai. | Pesanan tercatat dengan metode Tunai dan total yang tepat. |
| CHECK-03 | Isi nomor meja. | Nomor meja tersimpan pada pesanan. |
| CHECK-04 | Kosongkan nomor meja. | Checkout tetap berhasil; aplikasi menyimpan nilai default yang ditentukan. |
| CHECK-05 | Kosongkan nama pemesan. | Browser menolak formulir; pesanan tidak dibuat. |
| CHECK-06 | Coba checkout ketika keranjang kosong. | Pesanan tidak dibuat; pesan keranjang kosong tampil. |
| CHECK-07 | Ubah jumlah item sebelum checkout. | Total pesanan sama dengan jumlah harga × kuantitas seluruh item. |
| CHECK-08 | Tekan tombol checkout berulang kali dengan cepat. | Tidak tercipta pesanan duplikat yang tidak diinginkan. |
| CHECK-09 | Refresh halaman konfirmasi setelah pesanan dibuat. | Refresh tidak membuat pesanan baru. |
| CHECK-10 | Checkout menggunakan metode DANA. | Instruksi DANA dan gambar QR tampil; informasi total sama dengan pesanan. |
| CHECK-11 | Akses URL konfirmasi dengan ID pesanan yang tidak ada. | Respons 404, bukan error server. |
| CHECK-12 | Masukkan teks panjang atau karakter khusus pada nama/meja. | Data ditangani aman, tampilan tidak rusak, dan teks tidak dieksekusi sebagai HTML. |

## 4. Login dan Akses Kasir

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| AUTH-01 | Buka `/login`. | Form login kasir tampil. |
| AUTH-02 | Login dengan kredensial valid. | Berhasil masuk ke dashboard pesanan. |
| AUTH-03 | Login dengan password salah. | Login ditolak dengan pesan gagal; dashboard tidak terbuka. |
| AUTH-04 | Login dengan username tidak terdaftar. | Login ditolak tanpa membocorkan apakah username ada. |
| AUTH-05 | Kirim username/password kosong. | Ditolak dengan aman. |
| AUTH-06 | Lakukan lima percobaan gagal dalam jangka pembatasan. | Percobaan berikutnya dibatasi sementara sesuai implementasi. |
| AUTH-07 | Login berhasil setelah percobaan gagal. | Pembatasan kegagalan untuk alamat tersebut direset. |
| AUTH-08 | Akses `/kasir/pos` tanpa login. | Dialihkan ke login. |
| AUTH-09 | Akses `/kasir/dashboard` tanpa login. | Dialihkan ke login. |
| AUTH-10 | Akses `/kasir/laporan` dan `/kasir/laporan/pdf` tanpa login. | Dialihkan ke login. |
| AUTH-11 | Akses `/kasir/cetak_struk/<id>` tanpa login. | Dialihkan ke login. |
| AUTH-12 | Login lalu logout. | Sesi dihapus dan pengguna kembali ke login. |
| AUTH-13 | Tekan tombol kembali browser setelah logout. | Halaman kasir tidak dapat digunakan tanpa autentikasi aktif. |
| AUTH-14 | Login dengan akun nonaktif. | Login ditolak. |
| AUTH-15 | Uji redirect `next` setelah login. | Path lokal valid diikuti; URL eksternal atau format berbahaya tidak diikuti. |

## 5. Dashboard Kasir dan Pesanan

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| POS-01 | Buka daftar pesanan saat ada data. | ID, waktu, pelanggan, item, metode bayar, total, dan status tampil. |
| POS-02 | Buka daftar pesanan tanpa data. | Pesan kosong tampil; tabel tidak rusak. |
| POS-03 | Periksa pesanan dengan banyak item. | Seluruh item dan jumlah dapat dibaca pada tabel responsif. |
| POS-04 | Klik **Cetak**. | Halaman struk terbuka dan dialog cetak tampil. |
| POS-05 | Tutup dialog cetak atau tekan Cetak Ulang. | Struk dapat dicetak ulang dan datanya sesuai pesanan. |
| POS-06 | Cetak struk untuk pesanan yang tidak ada. | Respons 404, bukan error server. |
| POS-07 | Tandai pesanan belum selesai sebagai selesai dengan sesi kasir. | Status menjadi Selesai dan terlihat di daftar, laporan, serta halaman konfirmasi. |
| POS-08 | Tandai pesanan yang sudah selesai lagi. | Tidak terjadi perubahan atau efek duplikat yang salah. |
| POS-09 | Kirim konfirmasi pembayaran tanpa CSRF token atau dengan token salah. | Permintaan ditolak dengan 400. |
| POS-10 | Klik E-Menu dari sidebar desktop berulang kali. | E-Menu mengikuti perilaku satu-tab yang diharapkan dan tidak membuat tab baru. |
| POS-11 | Ulangi uji E-Menu pada sidebar mobile/offcanvas. | Perilakunya sama seperti sidebar desktop. |
| POS-12 | Kirim logout tanpa CSRF token valid. | Permintaan ditolak; sesi tidak berubah melalui request tidak valid. |

## 6. Laporan dan Ekspor PDF

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| REPORT-01 | Buka laporan dengan periode default. | Ringkasan, grafik, dan riwayat tampil. |
| REPORT-02 | Pilih **Minggu Ini**. | Data hanya mencakup minggu berjalan sesuai batas tanggal aplikasi. |
| REPORT-03 | Pilih **Bulan Ini**. | Data hanya mencakup bulan berjalan. |
| REPORT-04 | Pilih **Semua**. | Semua transaksi tampil. |
| REPORT-05 | Pilih rentang tanggal kustom dengan data. | Transaksi pada tanggal awal dan akhir ikut masuk. |
| REPORT-06 | Gunakan tanggal mulai sama dengan tanggal akhir. | Laporan untuk satu hari tampil dengan benar. |
| REPORT-07 | Isi tanggal mulai setelah tanggal akhir. | Permintaan ditolak dengan 400 dan pesan yang sesuai. |
| REPORT-08 | Kirim tanggal kosong/tidak valid pada periode kustom. | Permintaan ditolak dengan 400. |
| REPORT-09 | Kirim periode tidak dikenal. | Permintaan ditolak dengan 400. |
| REPORT-10 | Bandingkan pendapatan dengan transaksi selesai. | Pendapatan hanya menjumlah pesanan berstatus Selesai. |
| REPORT-11 | Bandingkan jumlah transaksi dengan daftar. | Semua status dihitung sebagai transaksi; jumlah selesai hanya menghitung pesanan selesai. |
| REPORT-12 | Ekspor PDF untuk semua periode. | PDF terunduh, terbuka, dan berisi ringkasan serta tabel transaksi. |
| REPORT-13 | Ekspor PDF untuk periode kustom. | PDF mengikuti filter tanggal di halaman. |
| REPORT-14 | Ekspor PDF tanpa login. | Dialihkan ke login. |
| REPORT-15 | Uji periode tanpa transaksi. | Ringkasan nol dan keadaan kosong tampil tanpa error. |

## 7. Halaman Pendukung dan Navigasi

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| NAV-01 | Klik logo/tautan kembali dari halaman pelanggan. | Kembali ke E-Menu. |
| NAV-02 | Buka `/order/success/<id>` untuk pesanan valid. | Status, nama, metode, total, dan instruksi sesuai pesanan. |
| NAV-03 | Buka `/payment/dana-qr.png`. | Respons berupa gambar PNG yang dapat dibaca. |
| NAV-04 | Buka endpoint QR saat server/database tidak tersedia. | Kegagalan ditangani tanpa halaman sukses palsu. |
| NAV-05 | Uji tautan sidebar dari POS dan laporan. | Setiap tautan menuju halaman benar; tidak ada tab duplikat yang tidak diinginkan. |
| NAV-06 | Uji tombol kembali browser di setiap alur. | Tidak kehilangan data atau mengulang transaksi secara tak terduga. |

## 8. Keamanan dan Validasi Dasar

| ID | Skenario | Hasil yang diharapkan |
|---|---|---|
| SEC-01 | Masukkan tag HTML/script pada nama pelanggan. | Ditampilkan sebagai teks biasa, tidak dieksekusi. |
| SEC-02 | Akses endpoint kasir tanpa sesi. | Semua route yang dilindungi meminta login. |
| SEC-03 | Kirim POST pembayaran atau logout tanpa CSRF token. | Permintaan ditolak. |
| SEC-04 | Kirim POST kosong/aksi tak dikenal ke update keranjang. | Keranjang tidak rusak dan aplikasi tidak memberi respons sukses palsu. |
| SEC-05 | Uji ID produk/varian/order yang tidak ada. | Respons 404 yang wajar. |
| SEC-06 | Uji quantity kosong, nol, negatif, teks, dan angka sangat besar pada tambah keranjang. | Input ditolak atau dibatasi; kuantitas tidak menjadi negatif/tidak masuk akal. |
| SEC-07 | Ubah data checkout dari browser. | Server tetap menghitung total berdasarkan keranjang, bukan nilai total dari klien. |
| SEC-08 | Periksa cookie sesi. | Cookie sesi memakai pengaturan HttpOnly dan SameSite sesuai konfigurasi. |
| SEC-09 | Periksa halaman/error untuk kebocoran kredensial. | Password/hash atau rahasia konfigurasi tidak bocor ke HTML, log yang dibagikan, atau pesan error. |

### Catatan keamanan dari pemeriksaan kode

- Route logout, kosongkan keranjang, dan konfirmasi pembayaran memeriksa CSRF token.
- Route tambah/ubah keranjang dan checkout perlu diuji khusus terhadap CSRF.
- Route tambah keranjang mengonversi jumlah input langsung ke integer; uji input tidak valid dan batas jumlah.
- Verifikasi bahwa nilai harga/total checkout dihitung di server dari isi keranjang.

## 9. Tampilan, Responsivitas, dan Aksesibilitas

Ulangi alur utama di desktop, tablet, dan ponsel:

- Katalog, modal varian, keranjang, checkout, login, POS, dan laporan tidak terpotong.
- Sidebar kasir mobile bisa dibuka; tautan dapat diklik; offcanvas berfungsi sebagaimana mestinya.
- Current Order dapat digulir; form dan tombol checkout tetap dapat dijangkau.
- Tidak ada scroll horizontal yang tidak diharapkan.
- Tombol `+`, `−`, hapus, pembayaran, cetak, dan logout memiliki area klik memadai.
- Form dapat dioperasikan dengan keyboard; fokus terlihat dan label terhubung ke input.
- Tombol penting memiliki nama yang dapat dibaca teknologi bantu.
- Teks dan badge memiliki kontras yang memadai.
- Browser Console tidak menampilkan error JavaScript.
- Tidak ada 404 untuk aset gambar, CSS, font, atau library yang diperlukan.

## 10. Ketahanan dan Konsistensi Data

- Uji sesi keranjang di dua browser/profil berbeda; keranjang tidak boleh tercampur.
- Buat beberapa pesanan berdekatan; masing-masing harus memiliki ID dan item yang benar.
- Putuskan koneksi database saat membaca atau membuat pesanan; aplikasi tidak boleh mengklaim pesanan berhasil.
- Uji pesanan dengan total besar dan banyak item; format rupiah, database, struk, dan laporan tetap konsisten.
- Bandingkan total di keranjang, halaman sukses, daftar POS, struk, dan laporan.
- Jalankan ulang aplikasi dan pastikan pesanan yang tersimpan tetap ada.

## 11. Di Luar Cakupan Fitur Aktif

Template `templates/admin/pos.html` dan `templates/admin/dashboard.html` tampak seperti tampilan simulasi. Route admin terkait tidak terlihat pada daftar route aktif yang diperiksa. Jangan menganggap tombol atau angka di sana sudah terhubung ke database sampai route-nya dikonfirmasi.

## 12. Temuan yang Perlu Diverifikasi

Tautan **Lanjut ke Pembayaran** pada halaman `/cart` mengarah ke route `checkout` dengan metode GET, sedangkan route `checkout` saat ini hanya menerima POST. Uji `CART-14`; jika menghasilkan `405 Method Not Allowed`, catat sebagai bug dan perbaiki alur checkout.

## Catatan Pelaksanaan

Daftar ini adalah rencana uji yang menyeluruh berdasarkan route dan template yang diperiksa. Belum berarti semua skenario telah dijalankan atau lulus. Jangan menjalankan skenario yang membuat atau mengubah transaksi terhadap database produksi.
