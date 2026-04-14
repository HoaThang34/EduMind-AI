# Frontend API Routes Documentation - EduMind-AI

## Tổng Quan

Tài liệu này ghi chép API endpoints được gọi từ frontend (HTML templates và JavaScript) cho AJAX requests, form submissions, và data fetching.

---

## AI Chatbot APIs

### Send Chat Message
**Endpoint:** `POST /api/chatbot`

**JavaScript Example:**
```javascript
fetch('/api/chatbot', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: userInput })
})
.then(response => response.json())
.then(data => {
  displayMessage(data.response);
  if (data.buttons) {
    data.buttons.forEach(btn => addActionButton(btn.label, btn.payload));
  }
});
```

**Request Body:**
```json
{ "message": "Tìm học sinh Nguyễn Văn A" }
```

**Response:**
```json
{
  "response": "**📊 Thông tin học sinh: Nguyễn Văn A**\n\n• **Mã số:** 12345\n• **Lớp:** 12 Tin...",
  "buttons": [{ "label": "📊 Xem học bạ", "payload": "/student/123/transcript" }]
}
```

---

### Clear Chat Session
**Endpoint:** `POST /api/chatbot/clear`

```javascript
fetch('/api/chatbot/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
.then(response => response.json())
.then(data => { clearChatUI(); });
```

---

### Assistant Chatbot
**Endpoint:** `POST /api/assistant_chatbot`

```javascript
fetch('/api/assistant_chatbot', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: userInput })
})
.then(response => response.json())
.then(data => {
  displayMessage(data.response);
  showCategory(data.category);
});
```

**Intent Categories:** nội quy, ứng xử, trợ giúp GV, general

---

## AI Report Generation APIs

### Generate Student Report
**Endpoint:** `POST /api/generate_report/<int:student_id>`

```javascript
fetch(`/api/generate_report/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ week: selectedWeek })
})
.then(response => response.json())
.then(data => { displayReport(data.report); });
```

---

### Generate Parent Report
**Endpoint:** `POST /api/generate_parent_report/<int:student_id>`

```javascript
fetch(`/api/generate_parent_report/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ semester: 1, school_year: "2025-2026" })
})
.then(response => response.json())
.then(data => { displayReport(data.report); });
```

---

### Generate Chart Comments
**Endpoint:** `POST /api/generate_chart_comments/<int:student_id>`

```javascript
fetch(`/api/generate_chart_comments/${studentId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    gpa: 7.5, avg_score: 7.2, highest_score: 9.0, lowest_score: 6.0,
    strong_subjects: ["Toán", "Lý"], weak_subjects: ["Hóa"],
    total_subjects: 8, conduct_score: 85, total_violations: 2, semester: 1
  })
})
.then(response => response.json())
.then(data => { displayComments(data.comments); });
```

---

### Analyze Class Statistics
**Endpoint:** `POST /api/analyze_class_stats`

```javascript
fetch('/api/analyze_class_stats', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ class_name: "12 Tin", weeks: [1, 2, 3, 4, 5] })
})
.then(response => response.json())
.then(data => { displayAnalysis(data.analysis); });
```

---

### Student AI Advice
**Endpoint:** `POST /student/api/generate_ai_advice`

```javascript
fetch('/student/api/generate_ai_advice', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
.then(response => response.json())
.then(data => { showAdvice(data.advice); });
```

---

## OCR Grade Entry APIs

### Process OCR Image
**Endpoint:** `POST /api/ocr-grades`

```javascript
const formData = new FormData();
formData.append('image', imageFile);

fetch('/api/ocr-grades', { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  data.results.forEach(row => addEditableRow(row));
});
```

**Response:**
```json
{
  "results": [
    {
      "rowId": "1", "student_code": "34 TOAN - 001035",
      "student_name": "Nguyễn Văn A", "score": "8.5", "grade_type": "TX"
    }
  ],
  "metadata": { "total_detected": 10 }
}
```

---

### Confirm OCR Grades
**Endpoint:** `POST /api/confirm-ocr-grades`

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
  if (data.success) showSuccess(`Đã lưu ${data.success_count} điểm`);
  else showErrors(data.errors);
});
```

---

## Grade Management APIs

### Update Grade Inline
**Endpoint:** `POST /api/update_grade/<int:grade_id>`

```javascript
fetch(`/api/update_grade/${gradeId}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ score: newScore })
})
.then(response => response.json())
.then(data => {
  if (data.success) updateCellDisplay(gradeId, data.score);
});
```

---

## Attendance APIs

### Face Recognition Check-in
**Endpoint:** `POST /api/attendance/face_checkin`

```javascript
const formData = new FormData();
formData.append('image', capturedImage);
formData.append('class_name', className);
formData.append('attendance_date', date);

fetch('/api/attendance/face_checkin', { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  if (data.success) {
    addAttendanceRow(data.student_name, data.status, data.confidence);
    if (data.status === 'Vắng') showViolationAlert(data.student_id);
  }
});
```

**Response:**
```json
{
  "success": true, "student_id": 123, "student_name": "Nguyễn Văn A",
  "confidence": 0.95, "status": "Có mặt"
}
```

---

### QR Code Check-in
**Endpoint:** `POST /api/attendance/qr_checkin`

```javascript
fetch('/api/attendance/qr_checkin', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    qr_data: `EDUATT:${studentId}`,
    class_name: "12 Tin",
    attendance_date: "2025-04-12",
    scan_method: "camera"
  })
})
.then(response => response.json())
.then(data => { handleCheckinResult(data); });
```

---

### Start Monitoring Session
**Endpoint:** `POST /api/attendance/start_session`

```javascript
fetch('/api/attendance/start_session', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ class_name: "12 Tin", session_date: "2025-04-12" })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    sessionId = data.session_id;
    showSessionActive();
  }
});
```

---

### Confirm Session
**Endpoint:** `POST /api/attendance/confirm_session/<int:session_id>`

```javascript
fetch(`/api/attendance/confirm_session/${sessionId}`, { method: 'POST' })
.then(response => response.json())
.then(data => {
  if (data.success) {
    showConfirmSuccess();
    updateViolationCount(data.violations_confirmed);
  }
});
```

---

### Get Sessions
**Endpoint:** `GET /api/attendance/sessions`

```javascript
fetch('/api/attendance/sessions')
.then(response => response.json())
.then(data => {
  data.sessions.forEach(s => addSessionRow(s));
});
```

---

## Timetable APIs

### Generate Timetable from AI
**Endpoint:** `POST /api/timetable/generate`

```javascript
const formData = new FormData();
formData.append('image', timetableImage);
formData.append('class_name', className);
formData.append('school_year', schoolYear);
formData.append('week_number', weekNumber);

fetch('/api/timetable/generate', { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  data.results.forEach(slot => addTimetableRow(slot));
});
```

---

### Confirm Timetable
**Endpoint:** `POST /api/timetable/confirm`

```javascript
fetch('/api/timetable/confirm', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026", week_number: 15,
    slots: timetableSlots
  })
})
.then(response => response.json())
.then(data => {
  if (data.success) showSuccess(`Đã lưu ${data.saved_count} ô TKB`);
});
```

---

### Save Timetable Cell
**Endpoint:** `POST /api/timetable/cell/save`

```javascript
fetch('/api/timetable/cell/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026",
    week_number: 1, day_of_week: 2, period_number: 1,
    subject_id: 1, room: "A101"
  })
})
.then(response => response.json())
.then(data => { if (data.success) showSaved(); });
```

---

## Lesson Book APIs

### Save Lesson Book Week
**Endpoint:** `POST /api/lesson_book/week/save`

```javascript
fetch('/api/lesson_book/week/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026",
    week_number: 1, semester: 1,
    teacher_notes: "Tuần nghỉ lễ"
  })
})
.then(response => response.json())
.then(data => { if (data.success) showWeekSaved(); });
```

---

### Save Lesson Book Slot
**Endpoint:** `POST /api/lesson_book/slot/save`

```javascript
fetch('/api/lesson_book/slot/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    week_id: 1, day_of_week: 2, period_number: 1,
    subject_name: "Toán", topic: "Đạo hàm",
    objectives: "Hiểu khái niệm", teaching_method: "Thuyết trình",
    evaluation: "Trắc nghiệm", homework: "Bài 1-10",
    attendance_present: 40, attendance_absent: 0
  })
})
.then(response => response.json())
.then(data => { if (data.success) showSlotSaved(); });
```

---

### Get Lesson Book Slots
**Endpoint:** `GET /api/lesson_book/slots/<int:week_id>`

```javascript
fetch(`/api/lesson_book/slots/${weekId}`)
.then(response => response.json())
.then(data => {
  data.slots.forEach(slot => populateSlotCell(slot));
});
```

---

## Messaging APIs

### Send Group Message
**Endpoint:** `POST /api/messaging/group/send`

```javascript
fetch('/api/messaging/group/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: "Hello everyone" })
})
.then(response => response.json())
.then(data => { if (data.success) addMessageToUI(data.message_id); });
```

---

### Send Private Message
**Endpoint:** `POST /api/messaging/private/send`

```javascript
fetch('/api/messaging/private/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ receiver_id: 5, message: "Hello" })
})
.then(response => response.json())
.then(data => { if (data.success) addPrivateMessage(data.message_id); });
```

---

### Mark Message as Read
**Endpoint:** `POST /api/messaging/mark_read/<int:message_id>`

```javascript
fetch(`/api/messaging/mark_read/${messageId}`, { method: 'POST' })
.then(response => response.json())
.then(data => { updateReadStatus(messageId); });
```

---

### Send Notification
**Endpoint:** `POST /api/notifications/send`

```javascript
fetch('/api/notifications/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    title: "Thông báo", message: "Sẽ có họp lớp",
    target_role: "homeroom_teacher", notification_type: "announcement"
  })
})
.then(response => response.json())
.then(data => { if (data.success) showSent(); });
```

---

### Get Unread Count
**Endpoint:** `GET /api/notifications/unread_count`

```javascript
fetch('/api/notifications/unread_count')
.then(response => response.json())
.then(data => { updateBadge(data.count); });
```

---

### Mark Notification Read
**Endpoint:** `POST /api/notifications/<int:notif_id>/read`

```javascript
fetch(`/api/notifications/${notifId}/read`, { method: 'POST' });
```

---

## Violation APIs

### Import Violations from Excel
**Endpoint:** `POST /api/import_violations`

```javascript
const formData = new FormData();
formData.append('file', excelFile);

fetch('/api/import_violations', { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  if (data.success) showSuccess(`Nhập thành công ${data.imported} vi phạm`);
  else showErrors(data.errors);
});
```

---

### Add Bulk Violations
**Endpoint:** `POST /api/add_violation_bulk`

```javascript
fetch('/api/add_violation_bulk', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    student_ids: [1, 2, 3],
    violation_type_id: 1,
    week_number: 5,
    lesson_book_entry_id: null
  })
})
.then(response => response.json())
.then(data => {
  if (data.success) showSuccess(`Đã thêm ${data.count} vi phạm`);
});
```

---

## Class Fund APIs

### Add Collection
**Endpoint:** `POST /api/class_fund/collection`

```javascript
fetch('/api/class_fund/collection', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026",
    amount_vnd: 500000, purpose: "Quỹ lớp tháng 4",
    payer_name: "Nguyễn Văn B", collection_date: "2025-04-12"
  })
})
.then(response => response.json())
.then(data => { if (data.success) refreshFundTable(); });
```

---

### Add Expense
**Endpoint:** `POST /api/class_fund/expense`

```javascript
fetch('/api/class_fund/expense', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026",
    amount_vnd: 300000, title: "Mua nước uống",
    expense_date: "2025-04-12"
  })
})
.then(response => response.json())
.then(data => { if (data.success) refreshFundTable(); });
```

---

## Class Subjects APIs

### Save Class Subjects
**Endpoint:** `POST /api/class_subjects/save`

```javascript
fetch('/api/class_subjects/save', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    class_name: "12 Tin", school_year: "2025-2026",
    subjects: [
      { subject_id: 1, is_compulsory: true, periods_per_week: 5 },
      { subject_id: 2, is_compulsory: true, periods_per_week: 4 }
    ]
  })
})
.then(response => response.json())
.then(data => { if (data.success) showSaved(); });
```

---

## Student Management APIs

### Import Students
**Endpoint:** `POST /api/import_students`

```javascript
const formData = new FormData();
formData.append('file', excelFile);

fetch('/api/import_students', { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  if (data.success) showSuccess(`Nhập thành công ${data.imported} học sinh`);
});
```

---

### Upload Student Photo
**Endpoint:** `POST /upload_student_photo/<int:student_id>`

```javascript
const formData = new FormData();
formData.append('photo', photoFile);

fetch(`/upload_student_photo/${studentId}`, { method: 'POST', body: formData })
.then(response => response.json())
.then(data => {
  if (data.success) updatePhotoPreview(data.filename);
});
```

---

### Send Student Notification
**Endpoint:** `POST /api/student/notification/send`

```javascript
fetch('/api/student/notification/send', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    target_type: "class", target_value: "12 Tin",
    title: "Thông báo", message: "Sẽ có họp lớp vào thứ 6"
  })
})
.then(response => response.json())
.then(data => { if (data.success) showSent(data.sent_count); });
```

---

## Common JavaScript Patterns

### Fetch with Error Handling
```javascript
async function apiCall(url, data, method = 'POST') {
  try {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (data && method !== 'GET') {
      options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    const result = await response.json();
    if (result.success === false) {
      throw new Error(result.error || 'Operation failed');
    }
    return result;
  } catch (error) {
    console.error('API Error:', error);
    showToast('Lỗi: ' + error.message, 'error');
    throw error;
  }
}
```

### File Upload with FormData
```javascript
async function uploadFile(file, endpoint) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(endpoint, { method: 'POST', body: formData });
  return await response.json();
}
```

### Debounce for Search
```javascript
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

const searchInput = document.getElementById('search');
searchInput.addEventListener('input', debounce((e) => {
  performSearch(e.target.value);
}, 300));
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
  options: { responsive: true, scales: { y: { beginAtZero: true } } }
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
  const threshold = 50;
  if (touchEndX - touchStartX > threshold) openSidebar();
  else if (touchStartX - touchEndX > threshold) closeSidebar();
}
```

### QR Scanner Integration
```javascript
// Using html5-qrcode or similar library
const scanner = new Html5Qrcode("qr-reader");

scanner.start(
  { facingMode: "environment" },
  { fps: 10, qrbox: 250 },
  (decodedText) => {
    // Parse EDUATT:student_id format
    if (decodedText.startsWith('EDUATT:')) {
      const studentId = decodedText.split(':')[1];
      fetch('/api/attendance/qr_checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_data: decodedText, class_name: currentClass })
      }).then(r => r.json()).then(handleCheckinResult);
    }
    scanner.pause();
  },
  (errorMessage) => { /* ignore scan errors */ }
);
```

---

## Face Recognition UI

### Capture and Send
```javascript
const video = document.getElementById('camera');
const canvas = document.getElementById('snapshot');
const ctx = canvas.getContext('2d');

function captureAndSend() {
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const imageData = canvas.toDataURL('image/jpeg');

  const formData = new FormData();
  formData.append('image', dataURLtoBlob(imageData));
  formData.append('class_name', currentClass);
  formData.append('attendance_date', today);

  fetch('/api/attendance/face_checkin', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showStudentIdentified(data);
      } else {
        showNotRecognized();
      }
    });
}

function dataURLtoBlob(dataurl) {
  const arr = dataurl.split(',');
  const mime = arr[0].match(/:(.*?);/)[1];
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) u8arr[n] = bstr.charCodeAt(n);
  return new Blob([u8arr], { type: mime });
}
```

---

## Error Handling in Frontend

### Global Error Handler
```javascript
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
});
```

### API Error Handling
```javascript
fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .catch(error => {
    console.error('Fetch error:', error);
    showToast('Lỗi kết nối server', 'error');
  });
```

---

## UI Component Patterns

### Toast Notifications
```javascript
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
```

### Confirm Dialogs
```javascript
function confirmAction(message, callback) {
  if (confirm(message)) callback();
}
```

### Modal Pattern
```javascript
function showModal(modalId) {
  document.getElementById(modalId).classList.add('show');
}

function hideModal(modalId) {
  document.getElementById(modalId).classList.remove('show');
}
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

### Debounce Resize
```javascript
const resizeHandler = debounce(() => {
  // Handle resize
}, 250);
window.addEventListener('resize', resizeHandler);
```

---

## CSRF Token Handling

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

---

## Future Enhancements

### WebSocket Integration (Planned)
```javascript
const socket = new WebSocket('ws://localhost:5000/ws');
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates
};
```
