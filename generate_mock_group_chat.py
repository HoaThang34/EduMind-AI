import random
import datetime
from app import app
from models import db, Teacher, GroupChatMessage

mock_messages = [
    "Chào mọi người, tuần này nhớ nhắc các em học sinh nộp sổ đầu bài nhé.",
    "Lịch kiểm tra chung khối 12 tuần sau đã có chưa ạ?",
    "Các thầy cô cho hỏi phòng in ấn có đang hoạt động không ạ, em kẹt giấy báo điểm.",
    "Bạn nào đi ăn trưa không, nay nhà ăn có món bún chả.",
    "Xin lỗi mọi người, tuần này lớp mình quên nộp sổ đoàn đúng hạn.",
    "Có thầy cô nào tuần vừa rồi dạy thay em, cho em xin lại chút thông tin với ạ.",
    "Xin chào các anh chị em.",
    "Điểm giữa kỳ của các bạn nhìn chung có vẻ ổn hơn năm ngoái đúng không mọi người?",
    "Chúc mọi người một tuần làm việc hiệu quả nhé!",
    "Chị Hoa ơi, nộp bảng điểm ở đâu ạ?",
    "Cảm ơn mọi người đã hỗ trợ tuần thi vừa qua.",
    "Tuần sau mình sẽ họp hội đồng để báo cáo kết quả tháng nha các thầy cô."
]

def run():
    with app.app_context():
        teachers = Teacher.query.all()
        
        if not teachers:
            print("Không có giáo viên nào trong CSDL để gửi tin nhắn.")
            return

        # Optional: delete old messages
        GroupChatMessage.query.delete()
        
        base_date = datetime.datetime.now() - datetime.timedelta(days=7)
        count = 0
        
        # generate ~30 messages over the last 7 days
        for i in range(30):
            sender = random.choice(teachers)
            message = random.choice(mock_messages)
            
            # create somewhat ascending times
            msg_date = base_date + datetime.timedelta(hours=i*5 + random.randint(1, 4))
            
            chat_msg = GroupChatMessage(
                sender_id=sender.id,
                message=message,
                created_at=msg_date
            )
            db.session.add(chat_msg)
            count += 1
            
        db.session.commit()
        print(f"Đã tạo ngẫu nhiên {count} tin nhắn trong phòng chat chung.")

if __name__ == '__main__':
    run()
