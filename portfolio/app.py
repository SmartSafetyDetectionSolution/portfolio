from flask import Flask, render_template, request, jsonify, redirect, Response, session
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from werkzeug.utils import secure_filename
from datetime import datetime
import threading
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = 'portfolio_secret_key_2026'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_PATH = os.path.join(os.path.dirname(__file__), 'messages.db')

# ===== 네이버 이메일 설정 (보안 강화를 위해 465 SSL 권장) =====
SMTP_SERVER = 'smtp.naver.com'
SMTP_PORT = 465 # 기존 587(TLS)에서 465(SSL)로 변경 (네이버에서 더 안정적임)
EMAIL_ADDRESS = 'ky971102@naver.com'       # 본인 네이버 이메일
EMAIL_PASSWORD = '*kang1102*'                   # 네이버 비밀번호 (업데이트됨)

def send_email_notification(name, sender_email, phone, message, file_path=None):
    """새 메시지가 오면 이메일로 알림 전송 (별도 스레드)"""
    if not EMAIL_PASSWORD:
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f'📬 포트폴리오 새 메시지 - {name}님'

        html_body = f"""
        <div style="font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background: #111118; color: #f0f0f5; border-radius: 12px;">
            <h2 style="color: #7c6aef; margin-bottom: 20px;">📬 포트폴리오 새 메시지</h2>
            <div style="background: rgba(124,106,239,0.08); padding: 16px; border-radius: 10px; border-left: 3px solid #7c6aef;">
                <p style="margin: 0 0 8px;"><strong style="color: #34d399;">보낸 사람:</strong> {name}</p>
                <p style="margin: 0 0 8px;"><strong style="color: #34d399;">이메일:</strong> <a href="mailto:{sender_email}" style="color: #7c6aef;">{sender_email}</a></p>
                <p style="margin: 0 0 8px;"><strong style="color: #34d399;">연락처:</strong> {phone if phone else '미입력'}</p>
                <p style="margin: 16px 0 4px;"><strong style="color: #34d399;">메시지:</strong></p>
                <p style="margin: 0; line-height: 1.7; color: #a0a0b8;">{message}</p>
                {f'<p style="margin: 16px 0 0;"><strong style="color: #f59e0b;">📎 첨부파일 포함됨:</strong> {os.path.basename(file_path)}</p>' if file_path else ''}
            </div>
            <p style="margin-top: 16px; font-size: 12px; color: #5a5a72;">이강연 포트폴리오에서 자동 발송된 이메일입니다.</p>
        </div>
        """
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # 첨부파일 처리
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(file_path)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg.attach(part)

        # SMTP_SSL을 사용하여 연결 (465 포트용)
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        server.quit()

        print(f"[EMAIL] ✅ 알림 메일 전송 완료 → {EMAIL_ADDRESS}")
    except Exception as e:
        print(f"[EMAIL] ❌ 전송 실패 상세 정보: {str(e)}")
        # 에러 발생 시 로그 파일에 기록 (디버깅용)
        with open('email_error.log', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {name}님의 메시지 전송 실패: {str(e)}\n")

def get_db():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """데이터베이스 초기화"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            message TEXT NOT NULL,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            youtube_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 댓글 테이블 추가
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
    ''')
    # 기존 테이블에 컬럼이 없는 경우 추가
    try:
        conn.execute('ALTER TABLE posts ADD COLUMN youtube_url TEXT')
    except sqlite3.OperationalError: pass
    
    conn.commit()
    conn.close()


# 앱 시작 시 DB 초기화
init_db()

@app.route('/')
def index():
    """메인 히어로 페이지"""
    return render_template('index.html', active_page='home')

@app.route('/about')
def about():
    """소개 페이지"""
    return render_template('about.html', active_page='about')

@app.route('/skills')
def skills():
    """기술 스택 페이지"""
    return render_template('skills.html', active_page='skills')

@app.route('/projects')
def projects():
    """프로젝트 페이지"""
    return render_template('projects.html', active_page='projects')

@app.route('/experience')
def experience():
    """경험 및 교육 페이지"""
    return render_template('experience.html', active_page='experience')

@app.route('/contact')
def contact_page():
    """연락처 페이지"""
    return render_template('contact_page.html', active_page='contact')


@app.route('/api/contact', methods=['POST'])
def contact():
    """연락처 폼 처리 - 메시지를 DB에 저장 + 이메일 알림 (파일 첨부 지원)"""
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()
    
    attachment = request.files.get('attachment')
    file_path = None

    if not name or not email or not message:
        return jsonify({'success': False, 'message': '모든 필드를 입력해주세요.'}), 400

    try:
        if attachment and attachment.filename:
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attachment.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            attachment.save(file_path)

        conn = get_db()
        conn.execute(
            'INSERT INTO messages (name, email, phone, message, file_path) VALUES (?, ?, ?, ?, ?)',
            (name, email, phone, message, file_path)
        )
        conn.commit()
        conn.close()

        # 이메일 알림을 별도 스레드로 전송
        thread = threading.Thread(
            target=send_email_notification,
            args=(name, email, phone, message, file_path)
        )
        thread.start()

        return jsonify({'success': True, 'message': '메시지가 성공적으로 전송되었습니다!'})
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({'success': False, 'message': '전송 중 오류가 발생했습니다.'}), 500

@app.route('/admin/messages')
def admin_messages():
    """관리자 페이지 - 받은 메시지 확인"""
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')
    conn = get_db()
    messages = conn.execute(
        'SELECT * FROM messages ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('admin_messages.html', messages=messages)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """관리자 로그인 페이지"""
    if session.get('admin_logged_in'):
        return redirect('/admin/messages')
    
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        admin_pw = os.environ.get('ADMIN_PASSWORD', '1234')
        if password == admin_pw:
            session['admin_logged_in'] = True
            return redirect('/admin/messages')
        else:
            error = '비밀번호가 올바르지 않습니다.'
            
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    """관리자 로그아웃"""
    session.pop('admin_logged_in', None)
    return redirect('/')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """업로드된 파일 다운로드/보기"""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/diary')
def diary_redirect():
    """AI 다이어리 메인 페이지로 리다이렉트 (trailing slash 추가로 상대경로 유지)"""
    return redirect('/diary/')

@app.route('/diary/')
@app.route('/diary/<path:path>')
def serve_diary(path=''):
    """React AI 다이어리 정적 파일 서빙"""
    from flask import send_from_directory
    if not path or path.endswith('/'):
        path += 'index.html'
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static', 'diary'), path)

@app.route('/api/messages/<int:msg_id>/read', methods=['POST'])
def mark_read(msg_id):
    """메시지 읽음 처리"""
    conn = get_db()
    conn.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/messages/<int:msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    """메시지 삭제"""
    conn = get_db()
    conn.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ===== 게시판 (Board CRUD) =====

@app.route('/board')
def board_list():
    """게시글 목록조회 (검색 및 정렬 기능 포함)"""
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'created_at') # 기본값: 작성일
    
    conn = get_db()
    if search_query:
        query = f"SELECT * FROM posts WHERE title LIKE ? OR author LIKE ? OR content LIKE ? ORDER BY {sort_by} DESC"
        posts = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = f"SELECT * FROM posts ORDER BY {sort_by} DESC"
        posts = conn.execute(query).fetchall()
    conn.close()
    return render_template('board_list.html', posts=posts, search_query=search_query, sort_by=sort_by)

@app.route('/board/create', methods=['GET', 'POST'])
def board_create():
    """게시글 작성"""
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        content = request.form.get('content')
        youtube_url = request.form.get('youtube_url')
        
        conn = get_db()
        conn.execute(
            'INSERT INTO posts (title, author, content, youtube_url) VALUES (?, ?, ?, ?)',
            (title, author, content, youtube_url)
        )
        conn.commit()
        conn.close()
        return redirect('/board')
    
    return render_template('board_form.html', action='작성', post=None, active_page='board')

@app.route('/board/<int:post_id>')
def board_view(post_id):
    """게시글 상세조회 (댓글 포함)"""
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC', (post_id,)).fetchall()
    conn.close()
    if not post:
        return "게시글을 찾을 수 없습니다.", 404
    return render_template('board_view.html', post=post, comments=comments, active_page='board')

@app.route('/board/<int:post_id>/edit', methods=['GET', 'POST'])
def board_edit(post_id):
    """게시글 수정"""
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        content = request.form.get('content')
        youtube_url = request.form.get('youtube_url')
        
        conn.execute(
            'UPDATE posts SET title = ?, author = ?, content = ?, youtube_url = ?, updated_at = ? WHERE id = ?',
            (title, author, content, youtube_url, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), post_id)
        )
        conn.commit()
        conn.close()
        return redirect(f'/board/{post_id}')
    
    conn.close()
    return render_template('board_form.html', action='수정', post=post, active_page='board')

# ===== 댓글 관련 API =====

@app.route('/board/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    """댓글 추가"""
    author = request.form.get('author')
    content = request.form.get('content')
    
    if not author or not content:
        return redirect(f'/board/{post_id}')

    conn = get_db()
    conn.execute(
        'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
        (post_id, author, content)
    )
    conn.commit()
    conn.close()
    return redirect(f'/board/{post_id}')

@app.route('/board/comments/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    """댓글 삭제"""
    post_id = request.form.get('post_id')
    conn = get_db()
    conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
    conn.commit()
    conn.close()
    return redirect(f'/board/{post_id}')


@app.route('/board/<int:post_id>/delete', methods=['POST'])
def board_delete(post_id):
    """게시글 삭제"""
    conn = get_db()
    conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()
    return redirect('/board')


# ===== AI 챗봇 API (초고도화된 확장형) =====
@app.route('/api/chat', methods=['POST'])
def chat():
    """포트폴리오 AI 챗봇 API (면접 킬러 답변 & 스몰토크 대량 탑재)"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'response': '메시지를 입력해주세요.'})
        
    msg = user_message.replace(" ", "")
    response = ""
    
    # 1. 인사 및 스몰토크
    if any(q in msg for q in ["안녕", "반갑", "ㅎㅇ", "하이", "안냐", "누구", "정체", "이름"]):
        response = "안녕하세요! 이강연 개발자의 분신, AI 챗봇입니다. 🤖\n채용 관련 질문, 기술 스택, 혹은 저의 MBTI나 취미까지 무엇이든 물어보세요! 면접관님의 질문 폭격을 환영합니다."
    elif any(q in msg for q in ["밥", "식사", "점심", "저녁", "먹었"]):
        response = "저는 에러(Error)를 먹고 자라는 AI라 밥은 괜찮습니다! 😋 면접관님은 식사 맛있게 하셨나요? 배부른 상태로 제 코드를 편안하게 감상해 주시면 좋겠습니다."
    elif any(q in msg for q in ["날씨", "덥", "춥", "비", "눈"]):
        response = "날씨가 어떻든 제 코딩 열정은 365일 맑음입니다! ☀️ (농담입니다ㅎㅎ) 언제나 안정적으로 돌아가는 서버처럼 상쾌한 하루 보내시길 바랍니다!"

    # 2. 직무 동기 / 비전공자 어필
    elif any(q in msg for q in ["동기", "왜", "계기", "비전공", "영상", "방송", "전공"]):
        response = "영상/방송 기획을 전공하며 **'무에서 유를 창조하는 과정'**의 매력을 느꼈습니다. 방송 현장에서 프로그램의 뼈대를 잡고 문제를 해결하던 경험이, 백엔드 서버의 인프라를 설계하고 버그를 고치는 개발의 매력과 완전히 맞닿아 있다고 느껴 개발자의 길을 선택했습니다! 비전공자 특유의 전체를 보는 시야가 제 무기입니다. 🎬➡️💻"

    # 3. 핵심 역량 / 장단점
    elif any(q in msg for q in ["장점", "강점", "어필", "잘하는", "매력"]):
        response = "저의 가장 큰 무기는 **'불도저 같은 끈기'**와 **'위기 대처 능력'**입니다! MBN, KBS 생방송 현장에서 터지는 돌발 상황들을 해결하며 단련된 멘탈로, 서버가 다운되거나 알 수 없는 버그가 터져도 원인을 끝까지 추적해 반드시 고쳐냅니다."
    elif any(q in msg for q in ["단점", "약점", "보완", "아쉬운"]):
        response = "가끔 문제 해결에 너무 몰두한 나머지 식사 시간을 잊어버리곤 합니다. 😅 이를 보완하기 위해 뽀모도로 기법(시간 분배)을 활용하여 번아웃을 방지하고, 효율적으로 코드를 작성하는 습관을 기르고 있습니다!"

    # 4. 협업 / 갈등 해결 (면접 킬러 문항)
    elif any(q in msg for q in ["협업", "갈등", "의견", "팀원", "소통", "커뮤니케이션"]):
        response = "개발은 혼자 하는 것이 아니라고 생각합니다. 팀원과 의견 충돌이 있을 때는 **'무엇이 사용자(User)를 위한 최선인가'**라는 공통의 목표로 돌아가 대화합니다. 방송국 조연출 시절, 다양한 부서장들의 이견을 조율하던 소통 스킬이 제 협업의 핵심 자산입니다! 🤝"

    # 5. 기술 스택 깊이 파기
    elif any(q in msg for q in ["파이썬", "python", "왜파이썬", "flask", "플라스크"]):
        response = "Python은 문법이 간결해 비즈니스 로직 구현 속도가 매우 빠르며, 강력한 AI/데이터 생태계를 가지고 있습니다! 저는 Flask 프레임워크를 활용해 가볍고 유연한 REST API 구축하는 것을 선호합니다. 🐍"
    elif any(q in msg for q in ["기술", "스택", "다룰", "언어", "프레임워크", "스킬", "할줄"]):
        response = "주력 무기는 **Python, Flask, SQLite** 이며, 프론트엔드는 **HTML/CSS/JS**를 능숙하게 다룹니다. 추가로 **OpenCV, YOLO**를 활용한 컴퓨터 비전 실시간 탐지 AI 구현 경험 등 폭넓은 기술 스펙트럼을 보유하고 있습니다! 🚀"

    # 6. 난관 극복 / 실패 경험
    elif any(q in msg for q in ["실패", "극복", "에러", "어려웠던", "위기", "힘들"]):
        response = "Vigilance AI 프로젝트 당시, 실시간 영상 프레임 처리 속도가 저하되는 이슈가 있었습니다. 포기하지 않고 cv2의 스레드 처리 방식을 분석하고 캐싱을 도입하여 렌더링 지연을 40% 이상 개선했던 경험이 있습니다. 실패는 그저 **'디버깅'**의 일부분일 뿐입니다! 🛠️"

    # 7. 프로젝트 소개
    elif any(q in msg for q in ["프로젝트", "포폴", "만든거", "결과물", "작품"]):
        response = ("네 가지 핵심 프로젝트가 있습니다!\n\n"
                    "1. **AI Scheduler & Diary (AI 다이어리)**: Gemini AI 비서와 레트로 감성(싸이월드 등)이 결합된 다기능 힐링 일기장 (React, Gemini API, HTML5 Canvas)\n"
                    "2. **MY FIT.LOG (커리어 플랫폼)**: 데이터 분석 기반 커리어 성장 플랫폼 (Flask, SQLite, Scrapy, Pandas)\n"
                    "3. **Vigilance AI (실시간 관제)**: YOLOv8 객체 탐지 데이터를 대시보드로 시각화한 모니터링 시스템 (Flask, JS, OpenCV)\n"
                    "4. **CRUD 게시판**: RESTful 아키텍처 역량 증명 (Flask, SQLite)\n\n"
                    "상단 메뉴의 **[AI 다이어리]** 또는 **[프로젝트]** 탭에서 직접 라이브 데모를 경험해보실 수 있습니다! 🚀")
    
    elif any(q in msg for q in ["다이어리", "scheduler", "diary", "스케줄러", "일기장", "캘린더"]):
        response = ("**AI Scheduler & Diary (AI 다이어리)** 프로젝트는 저의 프론트엔드 역량을 집대성한 결과물입니다! 📔✨\n\n"
                    "• **Gemini AI 비서**: 자연어로 일정을 입력하면 비서가 알아서 일정을 쪼개고 분석해서 캘린더에 추가하고, 기분에 어울리는 BGM도 추천해 줍니다.\n"
                    "• **7종의 감성 테마**: 레트로 싸이월드 감성 테마, 포근한 라벤더 등 고유의 테마를 자유롭게 바꿀 수 있습니다.\n"
                    "• **다채로운 힐링 기능**: 손그림을 그릴 수 있는 HTML5 Canvas 드로잉 패드, YouTube API를 활용한 BGM 플레이어, 집중용 뽀모도로 타이머와 XP 레벨업 시스템까지 모두 싱글 페이지로 매끄럽게 어우러져 있습니다.\n\n"
                    "상단 메뉴의 **[AI 다이어리]** 버튼을 눌러 지금 직접 체험해보실 수 있습니다! 💖")

    # 8. 사적인 질문 (스트레스, 취미, MBTI)
    elif any(q in msg for q in ["취미", "스트레스", "쉬는", "여가"]):
        response = "개발하다 막힐 때는 주로 가벼운 산책을 하거나 영화를 봅니다. 신기하게도 모니터 앞을 떠나서 샤워하거나 산책할 때, 해결되지 않던 코드의 실마리가 번쩍 떠오르더라고요! 💡"
    elif any(q in msg for q in ["mbti", "엠비티아이", "성격", "특징"]):
        response = ("이강연 개발자의 MBTI는 **ISFP(호기심 많은 예술가)**입니다! 🎨✨\n\n"
                    "프론트엔드 개발자로서 ISFP 성향은 정말 강력한 무기가 됩니다:\n\n"
                    "1. **타고난 미적 감각 (Aesthetic)**: 영상 전공자다운 시각적 감수성과 ISFP의 예술가적 기질이 만나, 1px의 오차도 허용하지 않는 **정교하고 아름다운 UI**를 구현합니다.\n"
                    "2. **깊은 사용자 공감 (Empathy)**: '사람' 중심인 ISFP는 사용자가 웹사이트에서 느낄 미세한 불편함을 본능적으로 캐치하여, **가장 편안한 UX**를 설계해냅니다.\n"
                    "3. **유연한 기술 적응력 (Adaptability)**: 새로운 기술을 편견 없이 받아들이고 시각적으로 구현하는 것을 즐기기에, 빠르게 변하는 프론트엔드 트렌드에 최적화되어 있습니다.\n"
                    "4. **조화로운 협업 (Harmony)**: 자신의 성과를 뽐내기보다 팀의 화합과 결과물의 퀄리티를 우선시하는 '겸손한 전문가'로서 최고의 팀 플레이어입니다.\n\n"
                    "이강연 개발자는 단순히 코드를 치는 사람이 아니라, **기술에 감성을 담아 사용자에게 가치를 전달하는 개발자**입니다!")


    # 9. 돌발/조직 적합성 (야근, 연봉, 왜 당신을?)
    elif any(q in msg for q in ["연봉", "돈", "급여", "희망"]):
        response = "(방긋) 💰 제 역량을 마음껏 펼칠 수 있는 인프라와 좋은 동료들이 있는 곳이라면 돈은 부차적인 문제입니다. 회사 내규에 따르겠으며, 최고의 가치를 창출해내겠습니다!"
    elif any(q in msg for q in ["야근", "밤샘", "주말", "초과"]):
        response = "방송국 조연출 시절, 365일 밤낮없이 뛰었습니다! 😎 책임감을 완수하기 위한 야근은 전혀 두렵지 않습니다. 하지만 장기적으로는 코드를 최적화하고 자동화하여, '야근을 안 해도 완벽하게 굴러가는 시스템'을 만드는 것이 제 목표입니다."
    elif any(q in msg for q in ["왜뽑", "채용", "이유", "마지막", "각오"]):
        response = "**'성장에 대한 갈증'**과 **'끝단까지 파고드는 집요함'** 때문입니다. 저는 단순히 주어진 기능만 찍어내는 코더가 아니라, 왜 이 기술을 써야 하는지 고민하고, 서비스에 가치를 더하는 든든한 백엔드 엔지니어로 성장할 확신이 있습니다! 👍"

    # 10. 연락처 정보
    elif any(q in msg for q in ["연락", "번호", "전화", "이메일", "폰", "주소", "메일"]):
        response = "언제든 환영입니다! \n📞 010-5387-4879 \n📧 ky971102@naver.com\n페이지 하단의 폼을 통해 메시지를 남겨주셔도 제 네이버 메일로 실시간 알림이 옵니다!"

    # 11. 예외 (치트키)
    else:
        num = len(user_message)
        if num < 2:
            response = "한 글자만 치셨군요! ㅎㅎ 무엇이든 편하게 물어보세요."
        else:
            response = f"앗, 질문하신 내용('{user_message}')은 너무 날카로우셔서 제 AI 데이터베이스를 벗어났습니다! 😅\n대신 이런 질문들은 어떠신가요?\n👉 **'단점이 뭐야?', '팀원과 갈등이 생기면?', '야근 가능해?', 'MBTI가 뭐야?'**"
        
    import time
    time.sleep(0.7) # 사람이 타이핑하는 듯한 딜레이 (감성 추가)
    
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
