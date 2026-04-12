# Frontend API Routes Documentation - EduMind-AI

## Overview
This document documents the API endpoints that are called from the frontend (HTML templates and JavaScript) for AJAX requests, form submissions, and data fetching.

---

## Grade Management APIs

### Update Grade Inline
**Endpoint:** `POST /api/update_grade/<int:grade_id>`

**Purpose:** Update a grade directly from the grade table without page reload

**JavaScript Example:**
```javascript
fetch(`/api/update_grade/${gradeId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ score: newScore })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    // Update UI
  }
});
```

**Request Body:**
```json
{
  "score": 8.5
}
```

**Response:**
```json
{
  "success": true,
  "score": 8.5
}
```

**Used in:** `student_grades.html` - Inline grade editing

---

## Chatbot APIs

### Send Chat Message
**Endpoint:** `POST /api/chatbot`

**Purpose:** Send message to AI chatbot and get response

**JavaScript Example:**
```javascript
fetch('/api/chatbot', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: userInput })
})
.then(response => response.json())
.then(data => {
  // Display data.response and data.buttons
});
```

**Request Body:**
```json
{
  "message": "Tìm học sinh Nguyễn Văn A"
}
```

**Response:**
```json
{
  "response": "**📊 Thông tin học sinh: Nguyễn Văn A**\n\n• **Mã số:** 12345\n• **Lớp:** 12 Tin...",
  "buttons": [
    {
      "label": "📊 Xem học bạ",
      "payload": "/student/123/transcript"
    }
  ]
}
```

**Used in:** `chatbot.html` - Main chatbot interface

---

### Clear Chat Session
**Endpoint:** `POST /api/chatbot/clear`

**Purpose:** Start a new chat session (clear history)

**JavaScript Example:**
```javascript
fetch('/api/chatbot/clear', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
.then(response => response.json())
.then(data => {
  // Refresh chat interface
});
```

**Response:**
```json
{
  "status": "success",
  "message": "Chat đã được làm mới"
}
```

**Used in:** `chatbot.html` - Clear chat button

---

### Assistant Chatbot
**Endpoint:** `POST /api/assistant_chatbot`

**Purpose:** Multi-purpose assistant with intent detection

**JavaScript Example:**
```javascript
fetch('/api/assistant_chatbot', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: userInput })
})
.then(response => response.json())
.then(data => {
  // Display data.response with category
});
```

**Request Body:**
```json
{
  "message": "Quy định về đi muộn là gì?"
}
```

**Response:**
```json
{
  "response": "Theo quy định nhà trường, học sinh đi muộn sẽ bị trừ 2 điểm...",
  "category": "nội quy"
}
```

**Used in:** `assistant_chatbot.html` - Assistant interface

---

## AI Report Generation APIs

### Generate Student Report
**Endpoint:** `POST /api/generate_report/<int:student_id>`

**Purpose:** Generate AI report for student's conduct

**JavaScript Example:**
```javascript
fetch(`/api/generate_report/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ week: selectedWeek })
})
.then(response => response.json())
.then(data => {
  // Display data.report
});
```

**Request Body:**
```json
{
  "week": 5
}
```

**Response:**
```json
{
  "report": "Em Nguyễn Văn A có điểm nề nếp 85/100 trong tuần 5..."
}
```

**Used in:** `student_detail.html` - Generate report button

---

### Generate Parent Report
**Endpoint:** `POST /api/generate_parent_report/<int:student_id>`

**Purpose:** Generate comprehensive parent report

**JavaScript Example:**
```javascript
fetch(`/api/generate_parent_report/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    semester: 1,
    school_year: "2025-2026"
  })
})
.then(response => response.json())
.then(data => {
  // Display data.report
});
```

**Request Body:**
```json
{
  "semester": 1,
  "school_year": "2025-2026"
}
```

**Response:**
```json
{
  "report": "Con Nguyễn Văn A có GPA 7.5/10 trong học kỳ 1..."
}
```

**Used in:** `parent_report.html` - Parent report generation

---

### Generate Chart Comments
**Endpoint:** `POST /api/generate_chart_comments/<int:student_id>`

**Purpose:** Generate AI comments for student charts

**JavaScript Example:**
```javascript
fetch(`/api/generate_chart_comments/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    gpa: 7.5,
    avg_score: 7.2,
    highest_score: 9.0,
    lowest_score: 6.0,
    strong_subjects: ["Toán", "Lý"],
    weak_subjects: ["Hóa"],
    total_subjects: 8,
    conduct_score: 85,
    total_violations: 2,
    semester: 1
  })
})
.then(response => response.json())
.then(data => {
  // Display data.comments
});
```

**Request Body:**
```json
{
  "gpa": 7.5,
  "avg_score": 7.2,
  "highest_score": 9.0,
  "lowest_score": 6.0,
  "strong_subjects": ["Toán", "Lý"],
  "weak_subjects": ["Hóa"],
  "total_subjects": 8,
  "conduct_score": 85,
  "total_violations": 2,
  "semester": 1
}
```

**Response:**
```json
{
  "comments": "Dựa trên biểu đồ học tập, em Nguyễn Văn A có điểm Toán và Lý khá tốt..."
}
```

**Used in:** `parent_report.html` - Chart comments generation

---

## OCR Grade Entry APIs

### Process OCR Image
**Endpoint:** `POST /api/ocr-grades`

**Purpose:** Upload grade sheet image and extract grades using OCR

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('image', imageFile);

fetch('/api/ocr-grades', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  // Display data.results in editable table
});
```

**Request Body (multipart/form-data):**
- `image` (file) - Image file of grade sheet

**Response:**
```json
{
  "results": [
    {
      "rowId": "1",
      "student_code": "34 TOAN - 001035",
      "student_name": "Nguyễn Văn A",
      "date_of_birth": "15/08/2008",
      "roll_number": "1",
      "score": "8.5",
      "grade_type": "TX"
    }
  ],
  "metadata": {
    "total_detected": 10
  }
}
```

**Used in:** `ocr_grades.html` - OCR grade processing

---

### Confirm OCR Grades
**Endpoint:** `POST /api/confirm-ocr-grades`

**Purpose:** Save OCR-verified grades to database

**JavaScript Example:**
```javascript
fetch('/api/confirm-ocr-grades', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    subject_id: subjectId,
    class_filter: selectedClass,
    semester: 1,
    grades: editedGrades
  })
})
.then(response => response.json())
.then(data => {
  // Show success/error messages
});
```

**Request Body:**
```json
{
  "subject_id": 1,
  "class_filter": "12 Tin",
  "semester": 1,
  "grades": [
    {
      "rowId": "1",
      "student_code": "34 TOAN - 001035",
      "student_name": "Nguyễn Văn A",
      "date_of_birth": "15/08/2008",
      "roll_number": "1",
      "score": "8.5",
      "grade_type": "TX",
      "column_index": 1
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "success_count": 10,
  "errors": [],
  "item_results": [
    {
      "rowId": "1",
      "status": "success",
      "message": "Đã lưu"
    }
  ]
}
```

**Used in:** `ocr_grades.html` - Confirm and save grades

---

## Student Portal APIs

### Generate AI Advice
**Endpoint:** `POST /student/api/generate_ai_advice`

**Purpose:** Generate AI advice for student dashboard

**JavaScript Example:**
```javascript
fetch('/student/api/generate_ai_advice', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
.then(response => response.json())
.then(data => {
  // Display data.advice
});
```

**Response:**
```json
{
  "advice": "Dựa trên kết quả học tập và nề nếp của em trong tuần này..."
}
```

**Used in:** `student_dashboard.html` - Generate advice button

---

## Analytics APIs

### Analyze Class Statistics
**Endpoint:** `POST /api/analyze_class_stats`

**Purpose:** Generate AI analysis for class statistics

**JavaScript Example:**
```javascript
fetch('/api/analyze_class_stats', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin",
    weeks: [1, 2, 3, 4, 5]
  })
})
.then(response => response.json())
.then(data => {
  // Display data.analysis
});
```

**Request Body:**
```json
{
  "class_name": "12 Tin",
  "weeks": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "analysis": "Lớp 12 Tin có xu hướng cải thiện nề nếp qua 5 tuần gần đây..."
}
```

**Used in:** `dashboard.html` - Class analysis button

---

## Form Submissions (POST)

### Delete Grade
**Endpoint:** `POST /delete_grade/<int:grade_id>`

**Purpose:** Delete a grade record

**HTML Form:**
```html
<form method="POST" action="/delete_grade/{{ grade.id }}">
  <button type="submit">Xóa</button>
</form>
```

**Used in:** `student_grades.html` - Delete grade button

---

### Add Violation
**Endpoint:** `POST /add_violation`

**Purpose:** Add a new violation record

**HTML Form:**
```html
<form method="POST" action="/add_violation">
  <input type="text" name="violation_type">
  <input type="number" name="points_deducted">
  <input type="date" name="date_committed">
  <select name="student_id">
    <!-- Student options -->
  </select>
  <button type="submit">Lưu</button>
</form>
```

**Used in:** `add_violation.html` - Add violation form

---

### Add Bonus
**Endpoint:** `POST /add_bonus`

**Purpose:** Add bonus points to student

**HTML Form:**
```html
<form method="POST" action="/add_bonus">
  <select name="bonus_type">
    <!-- Bonus type options -->
  </select>
  <input type="text" name="reason">
  <select name="student_id">
    <!-- Student options -->
  </select>
  <button type="submit">Lưu</button>
</form>
```

**Used in:** `add_bonus.html` - Add bonus form

---

### Add Teacher
**Endpoint:** `POST /add_teacher`

**Purpose:** Add new teacher account

**HTML Form:**
```html
<form method="POST" action="/add_teacher">
  <input type="text" name="username">
  <input type="password" name="password">
  <input type="text" name="full_name">
  <select name="role">
    <option value="homeroom_teacher">Giáo viên chủ nhiệm</option>
    <option value="subject_teacher">Giáo viên bộ môn</option>
  </select>
  <button type="submit">Lưu</button>
</form>
```

**Used in:** `add_teacher.html` - Add teacher form

---

### Add Subject
**Endpoint:** `POST /add_subject`

**Purpose:** Add new subject

**HTML Form:**
```html
<form method="POST" action="/add_subject">
  <input type="text" name="name">
  <input type="text" name="code">
  <input type="number" name="num_tx_columns">
  <input type="number" name="num_gk_columns">
  <input type="number" name="num_hk_columns">
  <button type="submit">Lưu</button>
</form>
```

**Used in:** `subjects_mgmt.html` - Add subject form

---

## File Upload APIs

### Upload Student Photo
**Endpoint:** `POST /upload_student_photo/<int:student_id>`

**Purpose:** Upload student portrait photo

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('photo', photoFile);

fetch(`/upload_student_photo/${studentId}`, {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  // Update photo display
});
```

**Used in:** Student management pages

---

### Upload Class Photo
**Endpoint:** `POST /upload_class_photo`

**Purpose:** Upload class group photo

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('photo', photoFile);

fetch('/upload_class_photo', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  // Update photo display
});
```

**Used in:** Class management pages

---

## Attendance APIs

### Face Recognition Check-in
**Endpoint:** `POST /api/attendance/face_checkin`

**Purpose:** Check in student using face recognition

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('image', capturedImage);
formData.append('class_name', className);
formData.append('attendance_date', date);

fetch('/api/attendance/face_checkin', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  // Process attendance result
});
```

**Request Body (multipart/form-data):**
- `image` (file) - Captured face image
- `class_name` (string) - Class name
- `attendance_date` (string) - Date string

**Response:**
```json
{
  "success": true,
  "student_id": 123,
  "student_name": "Nguyễn Văn A",
  "confidence": 0.95,
  "status": "Có mặt"
}
```

**Used in:** Attendance management pages

---

### QR Code Check-in
**Endpoint:** `POST /api/attendance/qr_checkin`

**Purpose:** Check in student using QR code

**JavaScript Example:**
```javascript
fetch('/api/attendance/qr_checkin', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    qr_data: "EDUATT:123",
    class_name: "12 Tin",
    attendance_date: "2025-04-12",
    scan_method: "camera"
  })
})
.then(response => response.json())
.then(data => {
  // Process attendance result
});
```

**Request Body:**
```json
{
  "qr_data": "EDUATT:123",
  "class_name": "12 Tin",
  "attendance_date": "2025-04-12",
  "scan_method": "camera"
}
```

**Response:**
```json
{
  "success": true,
  "student_id": 123,
  "student_name": "Nguyễn Văn A",
  "status": "Có mặt"
}
```

**Used in:** Attendance management pages with QR scanner

---

## Timetable APIs

### Generate Timetable from AI
**Endpoint:** `POST /api/timetable/generate`

**Purpose:** Generate timetable using AI from uploaded image

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('image', timetableImage);
formData.append('class_name', className);
formData.append('school_year', schoolYear);
formData.append('week_number', weekNumber);

fetch('/api/timetable/generate', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  // Display data.results in timetable grid
});
```

**Request Body (multipart/form-data):**
- `image` (file) - Timetable image
- `class_name` (string) - Class name
- `school_year` (string) - School year
- `week_number` (integer) - Week number

**Response:**
```json
{
  "results": [
    {
      "day_of_week": 2,
      "period_number": 1,
      "subject_name": "Toán",
      "room": "A101"
    }
  ]
}
```

**Used in:** `timetable.html` - AI timetable generation

---

### Confirm Timetable
**Endpoint:** `POST /api/timetable/confirm`

**Purpose:** Save AI-generated timetable to database

**JavaScript Example:**
```javascript
fetch('/api/timetable/confirm', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin",
    school_year: "2025-2026",
    week_number: 15,
    slots: timetableSlots
  })
})
.then(response => response.json())
.then(data => {
  // Show success message
});
```

**Request Body:**
```json
{
  "class_name": "12 Tin",
  "school_year": "2025-2026",
  "week_number": 15,
  "slots": [
    {
      "day_of_week": 2,
      "period_number": 1,
      "subject_id": 1,
      "room": "A101"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "saved_count": 30
}
```

**Used in:** `timetable.html` - Confirm timetable

---

## Messaging APIs

### Send Group Message
**Endpoint:** `POST /api/messaging/group/send`

**Purpose:** Send message to group chat

**JavaScript Example:**
```javascript
fetch('/api/messaging/group/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "Hello everyone"
  })
})
.then(response => response.json())
.then(data => {
  // Refresh message list
});
```

**Request Body:**
```json
{
  "message": "Hello everyone"
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 123
}
```

**Used in:** Group chat pages

---

### Send Private Message
**Endpoint:** `POST /api/messaging/private/send`

**Purpose:** Send private message to teacher

**JavaScript Example:**
```javascript
fetch('/api/messaging/private/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    receiver_id: 5,
    message: "Hello"
  })
})
.then(response => response.json())
.then(data => {
  // Refresh message list
});
```

**Request Body:**
```json
{
  "receiver_id": 5,
  "message": "Hello"
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 456
}
```

**Used in:** Private messaging pages

---

### Mark Message as Read
**Endpoint:** `POST /api/messaging/mark_read/<int:message_id>`

**Purpose:** Mark message as read

**JavaScript Example:**
```javascript
fetch(`/api/messaging/mark_read/${messageId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
.then(response => response.json())
.then(data => {
  // Update read status UI
});
```

**Response:**
```json
{
  "success": true
}
```

**Used in:** Messaging pages

---

## Class Fund APIs

### Add Fund Collection
**Endpoint:** `POST /api/class_fund/collection`

**Purpose:** Record fund collection

**JavaScript Example:**
```javascript
fetch('/api/class_fund/collection', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin",
    school_year: "2025-2026",
    amount_vnd: 500000,
    purpose: "Quỹ lớp tháng 4",
    student_id: 123,
    payer_name: "Nguyễn Văn B",
    collection_date: "2025-04-12"
  })
})
.then(response => response.json())
.then(data => {
  // Refresh fund list
});
```

**Request Body:**
```json
{
  "class_name": "12 Tin",
  "school_year": "2025-2026",
  "amount_vnd": 500000,
  "purpose": "Quỹ lớp tháng 4",
  "student_id": 123,
  "payer_name": "Nguyễn Văn B",
  "collection_date": "2025-04-12"
}
```

**Response:**
```json
{
  "success": true,
  "collection_id": 789
}
```

**Used in:** `class_fund.html` - Add collection

---

### Add Fund Expense
**Endpoint:** `POST /api/class_fund/expense`

**Purpose:** Record fund expense

**JavaScript Example:**
```javascript
fetch('/api/class_fund/expense', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin",
    school_year: "2025-2026",
    amount_vnd: 300000,
    title: "Mua nước uống",
    expense_date: "2025-04-12"
  })
})
.then(response => response.json())
.then(data => {
  // Refresh expense list
});
```

**Request Body:**
```json
{
  "class_name": "12 Tin",
  "school_year": "2025-2026",
  "amount_vnd": 300000,
  "title": "Mua nước uống",
  "expense_date": "2025-04-12"
}
```

**Response:**
```json
{
  "success": true,
  "expense_id": 101
}
```

**Used in:** `class_fund.html` - Add expense

---

## Lesson Book APIs

### Save Lesson Book Slot
**Endpoint:** `POST /api/lesson_book/slot/save`

**Purpose:** Save lesson book slot data

**JavaScript Example:**
```javascript
fetch('/api/lesson_book/slot/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    week_id: 1,
    day_of_week: 2,
    period_number: 1,
    subject_name: "Toán",
    topic: "Đạo hàm",
    objectives: "Hiểu khái niệm đạo hàm",
    teaching_method: "Thuyết trình",
    evaluation: "Trắc nghiệm",
    homework: "Bài 1-10",
    attendance_present: 40,
    attendance_absent: 0
  })
})
.then(response => response.json())
.then(data => {
  // Show success message
});
```

**Request Body:**
```json
{
  "week_id": 1,
  "day_of_week": 2,
  "period_number": 1,
  "subject_name": "Toán",
  "topic": "Đạo hàm",
  "objectives": "Hiểu khái niệm đạo hàm",
  "teaching_method": "Thuyết trình",
  "evaluation": "Trắc nghiệm",
  "homework": "Bài 1-10",
  "attendance_present": 40,
  "attendance_absent": 0
}
```

**Response:**
```json
{
  "success": true,
  "slot_id": 555
}
```

**Used in:** `lesson_book.html` - Save lesson slot

---

## Student Notification APIs

### Send Student Notification
**Endpoint:** `POST /api/student/notification/send`

**Purpose:** Send notification to students

**JavaScript Example:**
```javascript
fetch('/api/student/notification/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    target_type: "class",
    target_value: "12 Tin",
    title: "Thông báo",
    message: "Sẽ có họp lớp vào thứ 6"
  })
})
.then(response => response.json())
.then(data => {
  // Show success message
});
```

**Request Body:**
```json
{
  "target_type": "class",
  "target_value": "12 Tin",
  "title": "Thông báo",
  "message": "Sẽ có họp lớp vào thứ 6"
}
```

**Response:**
```json
{
  "success": true,
  "sent_count": 40
}
```

**Used in:** `send_student_notification.html` - Send notification

---

## Common JavaScript Patterns

### Fetch with Error Handling
```javascript
async function apiCall(url, data) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (result.success === false) {
      throw new Error(result.error);
    }
    return result;
  } catch (error) {
    console.error('API Error:', error);
    alert('Lỗi: ' + error.message);
    throw error;
  }
}
```

### File Upload with Progress
```javascript
function uploadFile(file, url) {
  const formData = new FormData();
  formData.append('file', file);

  const xhr = new XMLHttpRequest();
  xhr.upload.addEventListener('progress', (e) => {
    const percent = (e.loaded / e.total) * 100;
    // Update progress bar
  });

  xhr.addEventListener('load', () => {
    const response = JSON.parse(xhr.responseText);
    // Handle response
  });

  xhr.open('POST', url);
  xhr.send(formData);
}
```

### Debounce for Search
```javascript
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Usage
const searchInput = document.getElementById('search');
searchInput.addEventListener('input', debounce((e) => {
  // Perform search
}, 300));
```

---

## Frontend State Management

### Local Storage for Preferences
```javascript
// Save preference
localStorage.setItem('preferredClass', '12 Tin');

// Load preference
const preferredClass = localStorage.getItem('preferredClass');
```

### Session Storage for Temporary Data
```javascript
// Save temporary data
sessionStorage.setItem('draftMessage', 'Hello');

// Load temporary data
const draft = sessionStorage.getItem('draftMessage');
```

---

## UI Component APIs

### Modal Dialogs
```javascript
function showModal(modalId) {
  document.getElementById(modalId).style.display = 'block';
}

function hideModal(modalId) {
  document.getElementById(modalId).style.display = 'none';
}
```

### Toast Notifications
```javascript
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 3000);
}
```

### Confirm Dialogs
```javascript
function confirmAction(message, callback) {
  if (confirm(message)) {
    callback();
  }
}

// Usage
confirmAction('Bạn có chắc muốn xóa?', () => {
  // Perform delete
});
```

---

## Chart.js Integration

### Initialize Chart
```javascript
const ctx = document.getElementById('myChart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'bar',
  data: {
    labels: ['T1', 'T2', 'T3'],
    datasets: [{
      label: 'Điểm trung bình',
      data: [85, 90, 88],
      backgroundColor: 'rgba(54, 162, 235, 0.5)'
    }]
  },
  options: {
    responsive: true,
    scales: {
      y: { beginAtZero: true }
    }
  }
});
```

### Update Chart Data
```javascript
function updateChart(chart, newData) {
  chart.data.datasets[0].data = newData;
  chart.update();
}
```

---

## Mobile-Specific APIs

### Touch Event Handling
```javascript
let touchStartX = 0;
let touchEndX = 0;

document.addEventListener('touchstart', (e) => {
  touchStartX = e.changedTouches[0].screenX;
});

document.addEventListener('touchend', (e) => {
  touchEndX = e.changedTouches[0].screenX;
  handleSwipe();
});

function handleSwipe() {
  const swipeThreshold = 50;
  if (touchEndX - touchStartX > swipeThreshold) {
    // Swipe right - open sidebar
  } else if (touchStartX - touchEndX > swipeThreshold) {
    // Swipe left - close sidebar
  }
}
```

### Responsive Navigation
```javascript
function toggleMobileMenu() {
  const menu = document.getElementById('mobile-menu');
  menu.classList.toggle('active');
}
```

---

## Error Handling in Frontend

### Global Error Handler
```javascript
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
  // Log to server or show user-friendly message
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
});
```

### API Error Handling
```javascript
fetch(url)
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  })
  .catch(error => {
    console.error('Fetch error:', error);
    showToast('Lỗi kết nối server', 'error');
  });
```

---

## Performance Optimization

### Lazy Loading Images
```javascript
const lazyImages = document.querySelectorAll('img[data-src]');

const imageObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const img = entry.target;
      img.src = img.dataset.src;
      imageObserver.unobserve(img);
    }
  });
});

lazyImages.forEach(img => imageObserver.observe(img));
```

### Debounce Resize Events
```javascript
const resizeHandler = debounce(() => {
  // Handle resize
}, 250);

window.addEventListener('resize', resizeHandler);
```

---

## Security Considerations

### CSRF Token Handling
```javascript
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content;
}

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCsrfToken()
  },
  body: JSON.stringify(data)
});
```

### XSS Prevention
```javascript
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Usage
const safeHtml = escapeHtml(userInput);
```

---

## Browser Compatibility

### Feature Detection
```javascript
if ('fetch' in window) {
  // Use fetch API
} else {
  // Fallback to XMLHttpRequest
}

if ('IntersectionObserver' in window) {
  // Use Intersection Observer
} else {
  // Fallback to scroll event
}
```

---

## Debugging

### Console Logging
```javascript
console.log('Debug info:', data);
console.error('Error:', error);
console.warn('Warning:', warning);
console.table(arrayData);
```

### Network Request Logging
```javascript
// Log all fetch requests
const originalFetch = window.fetch;
window.fetch = function(...args) {
  console.log('Fetch:', args[0]);
  return originalFetch.apply(this, args);
};
```

---

## Future Enhancements

### WebSocket Integration
```javascript
const socket = new WebSocket('ws://localhost:5000/ws');

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates
};

socket.onopen = () => {
  console.log('WebSocket connected');
};

socket.onclose = () => {
  console.log('WebSocket disconnected');
};
```

### Service Worker for Offline Support
```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
    .then(registration => {
      console.log('SW registered:', registration);
    })
    .catch(error => {
      console.log('SW registration failed:', error);
    });
}
```
