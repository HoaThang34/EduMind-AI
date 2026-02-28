import random
from app import app
from models import db, Teacher

ho = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
dem_nam = ["Văn", "Hữu", "Đình", "Xuân", "Ngọc", "Hoàng", "Quang", "Công", "Minh", "Thành", "Đức"]
dem_nu = ["Thị", "Ngọc", "Bảo", "Thùy", "Thu", "Mai", "Kiều", "Tuyết", "Xuân", "Kim", "Hồng"]
ten_nam = ["Anh", "Dũng", "Đạt", "Hải", "Hiếu", "Hoà", "Hưng", "Khang", "Khánh", "Long", "Minh", "Nam", "Phong", "Phúc", "Quân", "Tân", "Thái", "Thành", "Thiên", "Thịnh", "Tiến", "Toàn", "Trí", "Trường", "Tuấn", "Tùng", "Vinh", "Việt", "Bảo", "Cường", "Đức"]
ten_nu = ["An", "Anh", "Châm", "Chi", "Diệp", "Dung", "Hà", "Hân", "Hoa", "Hương", "Huyền", "Linh", "Mai", "My", "Nga", "Ngọc", "Nhi", "Nhung", "Oanh", "Phương", "Quyên", "Quỳnh", "Thảo", "Thư", "Thủy", "Trâm", "Trang", "Tú", "Uyên", "Vân", "Vy", "Yến"]

def generate_random_name():
    is_male = random.choice([True, False])
    first = random.choice(ho)
    
    if is_male:
        middle = random.choice(dem_nam)
        last = random.choice(ten_nam)
    else:
        middle = random.choice(dem_nu)
        last = random.choice(ten_nu)
        
    return f"{first} {middle} {last}"

def run():
    with app.app_context():
        teachers = Teacher.query.filter(Teacher.role != 'admin').all()
        
        count = 0
        for teacher in teachers:
            teacher.full_name = generate_random_name()
            count += 1
            
        db.session.commit()
        print(f"Đã cập nhật họ tên ngẫu nhiên cho {count} giáo viên.")

if __name__ == '__main__':
    run()
