import getpass
import re
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app import StaffUser, app, db


username = input('Username staf: ').strip()
if not re.fullmatch(r'[A-Za-z0-9_.-]{3,80}', username):
    raise SystemExit('Username harus 3-80 karakter dan hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung.')

role = input('Role (admin/cashier) [cashier]: ').strip().lower() or 'cashier'
if role not in {'admin', 'cashier'}:
    raise SystemExit('Role harus admin atau cashier.')

password = getpass.getpass('Password (minimal 12 karakter): ')
confirmation = getpass.getpass('Ulangi password: ')
if len(password) < 12:
    raise SystemExit('Password harus minimal 12 karakter.')
if password != confirmation:
    raise SystemExit('Password tidak cocok.')

with app.app_context():
    db.create_all()
    if StaffUser.query.filter_by(username=username).first():
        raise SystemExit('Username tersebut sudah terdaftar.')

    staff_user = StaffUser(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(staff_user)
    db.session.commit()

print(f'Akun {role} "{username}" berhasil dibuat.')