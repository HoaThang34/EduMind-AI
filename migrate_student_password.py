"""
Script migration để thêm cột password vào bảng Student
và set mật khẩu mặc định là "123456" cho tất cả học sinh hiện có.

Chạy script này sau khi cập nhật model Student.
"""

from app import app
from models import db, Student
from werkzeug.security import generate_password_hash
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Kiểm tra xem cột password đã tồn tại chưa
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('student')]

        if 'password' not in columns:
            print("Cột password chưa tồn tại. Đang thêm cột password...")
            try:
                # Thêm cột password bằng SQL trực tiếp
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE student ADD COLUMN password VARCHAR(100)"))
                    conn.commit()
                print("Đã thêm cột password thành công.")
            except Exception as e:
                print(f"Lỗi khi thêm cột password: {e}")
                return
        else:
            print("Cột password đã tồn tại trong database.")

        # Set mật khẩu mặc định cho các học sinh chưa có password
        students_without_password = Student.query.filter(Student.password == None).all()

        if students_without_password:
            print(f"Đang set mật khẩu mặc định '123456' cho {len(students_without_password)} học sinh...")
            for student in students_without_password:
                student.set_password("123456")

            db.session.commit()
            print(f"Đã cập nhật mật khẩu cho {len(students_without_password)} học sinh.")
        else:
            print("Tất cả học sinh đã có mật khẩu.")

if __name__ == "__main__":
    migrate()
