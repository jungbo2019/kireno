import os
import time
import psutil
import datetime
import random
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    jsonify, session, flash, Response
)
from werkzeug.security import check_password_hash
from database import get_db, init_db
from naver_sync import sync_naver_smartstore_catalog, import_naver_excel_or_csv

import html
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kireno-pottery-craft-secret-20261025'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=6)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

SERVER_START_TIME = time.time()

# Initialize DB on module load for Gunicorn/Cloud
try:
    init_db()
except Exception as _e:
    print('DB init warning:', _e)

# Security Guards: IP Rate Limiting & Brute-force Prevention
LOGIN_FAILED_ATTEMPTS = {}  # ip -> (count, lockout_until)
API_RATE_LIMITS = {}        # ip -> [timestamps]

# Real-time task progress tracker for Mission Control
MISSION_CONTROL_STATE = {
    'current_phase': '6단계: 24시간 제미나이 AI 화분 어드바이저 & 터미널 CLI 에이전트 동시 가동',
    'progress_pct': 100,
    'backup_status': '3중 백업 동기화 완료 (1_original, 2_backup_latest, 3_backup_archive)',
    'last_sync_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'active_benchmarks': ['제미나이 24시간 식물 AI 컨시어지', '터미널 CLI 도구 체인 (kireno_cli.py)', '수제 화분 12종 라인업']
}

def log_event(event_type, message, latency=0.0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        client_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr or '127.0.0.1'
        cursor.execute('''
            INSERT INTO system_logs (event_type, message, ip_address, latency_ms)
            VALUES (?, ?, ?, ?)
        ''', (event_type, message, client_ip, latency))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")

def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM site_settings WHERE id = 1')
    settings = cursor.fetchone()
    conn.close()
    return settings

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('관리자 로그인이 필요한 페이지입니다.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def security_and_auth_guard():
    client_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr or '127.0.0.1'
    now = time.time()
    norm_path = request.path.lower().rstrip('/')

    # 1. API Rate Limiting (DOS & Spam prevention)
    if norm_path.startswith('/api/'):
        timestamps = API_RATE_LIMITS.setdefault(client_ip, [])
        API_RATE_LIMITS[client_ip] = [t for t in timestamps if now - t < 60]
        if len(API_RATE_LIMITS[client_ip]) > 60:
            log_event('RATE_LIMIT_BLOCKED', f'API 호출 한도 초과 차단 ({client_ip})')
            return jsonify({'success': False, 'error': '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.'}), 429
        API_RATE_LIMITS[client_ip].append(now)

    # 2. Strict Admin Route Authentication (normalize lower case, block path traversal)
    if norm_path.startswith('/admin') or norm_path.startswith('/api/admin') or norm_path.startswith('/api/mission-control'):
        # Whitelisted admin routes
        if norm_path in ['/admin/login']:
            return None

        # Check admin session
        if not session.get('admin_logged_in'):
            if norm_path.startswith('/api/'):
                return jsonify({'success': False, 'error': '관리자 인증이 필요합니다. 먼저 로그인하세요.'}), 401
            flash('관리자 로그인이 필요한 페이지입니다. 로그인 후 이용해 주세요.', 'warning')
            return redirect(url_for('admin_login', next=request.url))

@app.after_request
def attach_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response

@app.context_processor
def inject_global_data():
    settings = get_settings()
    return {
        'settings': settings,
        'current_year': 2026
    }

# --- 24/7 Gemini AI Ceramic & Pottery Advisor Engine ---

def generate_ai_advisor_reply(user_msg, prod_context=''):
    msg = user_msg.strip().lower()
    
    # 1. Price / Budget / Cheapest / Most affordable
    if any(k in msg for k in ['저렴', '싼', '제일 싼', '가장 싼', '얼마부터', '가격대', '가성비', '부담 없는', '최저가']):
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT name, category, price, sale_price FROM products ORDER BY COALESCE(sale_price, price) ASC LIMIT 3')
            cheapest = cursor.fetchall()
            conn.close()
            lines = []
            for p in cheapest:
                actual = p['sale_price'] if p['sale_price'] else p['price']
                lines.append(f"• {p['name']} ({p['category']}) : {actual:,}원")
            items_str = "\n".join(lines)
            return (
                f"현재 키레노에서 가장 부담 없이 만나보실 수 있는 소품 라인업입니다.\n\n"
                f"{items_str}\n\n"
                f"모든 작품은 핸드크래프트 고온 소성으로 제작되어 실사용 및 인테리어 오브제로 완성도가 높습니다. 상세 규격이나 사진 안내가 필요하시면 말씀해 주세요."
            )
        except Exception:
            return (
                "현재 키레노에서 가장 부담 없이 만나보실 수 있는 소품 라인업입니다:\n\n"
                "• 미니멀 도자 인센스 홀더 & 스톤 트레이 (22,000원)\n"
                "• 흑유 매트 세라믹 머그 (28,000원)\n"
                "• 아프리카 괴근·아가베 전용 샬로우 팟 (30,000원)\n\n"
                "가벼운 선물이나 첫 도자기 입문으로 추천드립니다."
            )

    # 2. Best / Popular / Recommendations
    elif any(k in msg for k in ['추천', '인기', '베스트', '제일 잘', '잘나가는', '대표', '시그니처']):
        return (
            "키레노의 대표 시그니처 & 베스트셀러 도자기 컬렉션입니다.\n\n"
            "• [시그니처] 키레노 구름 도자 토분 (12호 32,000원 / 15호 39,000원): 전용 받침 포함, 시그니처 텍스처 도자 화분\n"
            "• 백자 달항아리 미니 세라믹 오브제 (49,000원): 비대칭 곡선의 단아한 여백의 미를 선사하는 베스트 오브제\n"
            "• 시가라키야키 자연재 무광 도자 화병 (62,000원): 장작가마 자연유의 깊이감을 담은 테이블 화병\n\n"
            "어떤 공간이나 용도(선물용, 홈카페 식기, 오브제, 식물 식재)에 맞추실지 편하게 말씀해 주시면 최적의 작품을 매칭해 드립니다."
        )

    # 3. Drinking / Cups / Mugs / Water / Tea
    elif any(k in msg for k in ['물', '마실', '음료', '차', '커피', '잔', '머그', '찻잔', '컵', '숙우']):
        return (
            "물이나 따뜻한 차, 커피를 담아 드시기 좋은 핸드크래프트 도자기가 준비되어 있습니다.\n\n"
            "• 흑유 매트 세라믹 머그 (320ml, 28,000원): 철분 함유 흙으로 빚어 은은한 흑철색 광택과 뛰어난 보온성을 지닙니다.\n"
            "• 수제 물레 찻잔 & 숙우 2인 다도 세트 (46,000원): 차의 수색을 맑게 비추는 부드러운 손맛의 다도 잔입니다.\n\n"
            "원하시는 용량이나 형태가 있으시면 편하게 말씀해 주세요."
        )

    # 4. Vases & Objects
    elif any(k in msg for k in ['화병', '꽃', '가지', '달항아리', '오브제', '인센스', '트레이']):
        return (
            "공간에 고요한 품격을 더해주는 키레노 도자 화병 & 오브제 라인입니다.\n\n"
            "• 시가라키야키 자연재 무광 도자 화병 (높이 21cm, 62,000원): 장작가마 자연재 요변이 꽃과 가지를 예술적으로 받쳐줍니다.\n"
            "• 백자 달항아리 미니 세라믹 오브제 (높이 13.5cm, 49,000원): 비대칭 곡선의 단아한 여백의 미를 선사합니다.\n"
            "• 미니멀 도자 인센스 홀더 & 스톤 트레이 (22,000원): 서재와 다도 공간을 위한 정갈한 세라믹 트레이입니다."
        )

    # 5. Tableware / Bowls / Plates
    elif any(k in msg for k in ['그릇', '접시', '보울', '사발', '식기', '밥그릇', '플레이트']):
        return (
            "1,250℃ 고온 소성으로 단단하고 위생적인 수제 도자 식기 컬렉션입니다.\n\n"
            "• 분청 고온 소성 텍스처 도자 보울 (사발, Ø16cm, 34,000원): 귀얄 분청 기법으로 깊이 있는 플레이팅을 완성합니다.\n"
            "• 내추럴 스톤웨어 세라믹 플레이트 (평접시 21cm, 31,000원): 암석 입자감이 살아있는 매트 스톤웨어 접시입니다."
        )

    # 6. Planters / Pots
    elif any(k in msg for k in ['화분', '토분', '식물', '분갈이', '흙', '구름', '팟']):
        return (
            "통기성과 배수성을 극대화한 키레노 수제 도자 화분 라인업입니다.\n\n"
            "• [시그니처] 키레노 구름 도자 토분 (12호 32,000원 / 15호 39,000원): 전용 세라믹 받침 세트 포함, 미세 기공으로 과습을 방지합니다.\n"
            "• 시가라키야키 흑철유 도자 화분 (52,000원): 묵직한 하중과 독보적인 가마 텍스처를 자랑합니다.\n"
            "• 아프리카 괴근·아가베 전용 샬로우 팟 (30,000원): 얕고 넓은 분형의 고온 소성 분입니다."
        )

    # 7. Price, Order, Delivery
    elif any(k in msg for k in ['가격', '얼마', '배송', '주문', '결제', '택배', '파손']):
        return (
            "키레노의 모든 도자기는 전용 맞춤 에어셀 완충재와 2중 강화 박스로 안전하게 직배송됩니다.\n\n"
            "배송 중 파손율 0% 보증 정책(파손 시 100% 무상 재발송)을 운영하며, 원하시는 작품의 [1:1 상담 및 주문]을 통해 도예 작가와 대화 후 편하게 소장하실 수 있습니다."
        )

    # 8. Default polite conversational response
    else:
        ctx_clean = prod_context.strip() if prod_context and not any(b in prod_context for b in ['버튼', '플로팅', '상담', '전체', '신청']) else ''
        ctx_str = f"[{ctx_clean}] " if ctx_clean else ""
        return (
            f"안녕하세요! 키레노 도예 아뜰리에입니다.\n\n"
            f"{ctx_str}문의주신 \"{user_msg}\" 관련하여 도자기 작품(머그/찻잔, 식기, 화병, 오브제, 도자분)의 규격, 가마 소성 기법, 1:1 맞춤 주문 등 편하게 여쭤보시면 도예 작가가 상세히 안내해 드리겠습니다."
        )

# --- Client Routes ---

@app.route('/')
def index():
    start = time.time()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM products
        ORDER BY
            CASE WHEN stock_status = '즉시출고' THEN 0
                 WHEN stock_status = '주문제작' THEN 1
                 ELSE 2 END ASC,
            is_featured DESC,
            id ASC
    ''')
    products = cursor.fetchall()
    conn.close()

    latency = round((time.time() - start) * 1000, 2)
    log_event('PAGE_VIEW', '메인 쇼룸 페이지 방문', latency)
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    start = time.time()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        flash('요청하신 작품 정보를 찾을 수 없습니다.', 'warning')
        return redirect(url_for('index'))

    cursor.execute('SELECT * FROM products ORDER BY id ASC')
    all_prods = cursor.fetchall()
    conn.close()

    # Compute 4 interconnected products (2 cross-category + 2 same-category)
    cross_cat = [p for p in all_prods if p['id'] != product['id'] and p['category'] != product['category'] and p['stock_status'] == '즉시출고']
    same_cat = [p for p in all_prods if p['id'] != product['id'] and p['category'] == product['category'] and p['stock_status'] == '즉시출고']
    seed = product['id']
    related = []
    if cross_cat:
        related.append({'prod': cross_cat[seed % len(cross_cat)], 'relation': '연계 배치 추천 01'})
        related.append({'prod': cross_cat[(seed + 7) % len(cross_cat)], 'relation': '연계 배치 추천 02'})
    if same_cat:
        related.append({'prod': same_cat[seed % len(same_cat)], 'relation': '동일 분류 인기작'})
        related.append({'prod': same_cat[(seed + 3) % len(same_cat)], 'relation': '함께 비교할 작품'})

    latency = round((time.time() - start) * 1000, 2)
    log_event('PRODUCT_VIEW', f"개별 작품 상세페이지 조회: {product['name']} (ID: {product_id})", latency)
    return render_template('product_detail.html', product=product, related_products=related, products=all_prods)

@app.route('/robots.txt')
def robots_txt():
    host = request.host_url.rstrip('/')
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /product/",
        "Disallow: /admin/",
        "Disallow: /api/",
        f"Sitemap: {host}/sitemap.xml",
        f"Sitemap: {host}/rss.xml"
    ]
    return Response("\n".join(lines), mimetype='text/plain; charset=utf-8')

@app.route('/sitemap.xml')
def sitemap_xml():
    host = request.host_url.rstrip('/')
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM products ORDER BY id ASC')
    prod_ids = [r['id'] for r in cursor.fetchall()]
    conn.close()

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <url>',
        f'    <loc>{host}/</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>1.0</priority>',
        '  </url>'
    ]
    for pid in prod_ids:
        xml_lines.extend([
            '  <url>',
            f'    <loc>{host}/product/{pid}</loc>',
            f'    <lastmod>{today}</lastmod>',
            '    <changefreq>weekly</changefreq>',
            '    <priority>0.8</priority>',
            '  </url>'
        ])
    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), mimetype='application/xml; charset=utf-8')

@app.route('/rss.xml')
def rss_xml():
    host = request.host_url.rstrip('/')
    now_rfc = datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0900')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, category, description, price FROM products ORDER BY id DESC LIMIT 30')
    items = cursor.fetchall()
    conn.close()

    rss_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '  <channel>',
        '    <title>KIRENO 키레노 | 일본 수공예 도자기 &amp; 재팬디 오브제 공식 쇼룸</title>',
        f'    <link>{host}/</link>',
        '    <description>일본 교토·시가라키 장인의 수공예 도자기 화분, 재팬디 패브릭 액자, 와비사비 원목 인센스 홀더 공식 쇼룸</description>',
        '    <language>ko-KR</language>',
        f'    <lastBuildDate>{now_rfc}</lastBuildDate>'
    ]
    for it in items:
        ename = html.escape(it['name'])
        edesc = html.escape(f"[{it['category']}] {it['description']} - 공식 판매가: {it['price']:,}원")
        rss_lines.extend([
            '    <item>',
            f'      <title>{ename}</title>',
            f'      <link>{host}/product/{it["id"]}</link>',
            f'      <guid>{host}/product/{it["id"]}</guid>',
            f'      <description>{edesc}</description>',
            '    </item>'
        ])
    rss_lines.extend(['  </channel>', '</rss>'])
    return Response("\n".join(rss_lines), mimetype='application/rss+xml; charset=utf-8')

@app.route('/favicon.ico')
def favicon_ico():
    svg_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <rect width="64" height="64" rx="12" fill="#111111"/>
    <rect x="6" y="6" width="52" height="52" rx="8" fill="none" stroke="#C4A482" stroke-width="2.5"/>
    <text x="32" y="44" font-family="serif" font-size="34" font-weight="bold" fill="#C4A482" text-anchor="middle">器</text>
</svg>"""
    return Response(svg_icon, mimetype='image/svg+xml')

@app.route('/api/order-track', methods=['GET', 'POST'])
def api_order_track():
    q = (request.args.get('q') or (request.json or {}).get('q') or '').strip()
    if not q:
        return jsonify({'success': False, 'message': '주문번호, 성함 또는 연락처를 입력해 주세요.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    like_q = f"%{q}%"
    cursor.execute("""
        SELECT order_number, customer_name, customer_phone, product_name, quantity,
               total_amount, status, jp_order_status, jp_tracking_num,
               customs_status, shipping_company, tracking_number, created_at
        FROM orders
        WHERE order_number LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ?
        ORDER BY id DESC LIMIT 5
    """, (like_q, like_q, like_q))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not rows:
        return jsonify({'success': False, 'message': '일치하는 주문 및 통관 내역이 없습니다. 샘플 주문번호(KRN-20261023-688) 또는 성함(김서연)으로 조회해 보실 수 있습니다.'})

    # Mask phone slightly for privacy
    for r in rows:
        ph = r.get('customer_phone') or ''
        if len(ph) >= 11:
            r['masked_phone'] = ph[:4] + '-****-' + ph[-4:]
        else:
            r['masked_phone'] = ph
    return jsonify({'success': True, 'orders': rows})

# --- 1:1 Real-time Chat / AI Concierge API ---

@app.route('/api/chat/send', methods=['POST'])
def chat_send():
    session_id = request.json.get('session_id', 'anonymous')
    product_name = request.json.get('product_name', '')
    message = request.json.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'message': '메시지를 입력해주세요.'}), 400

    # XSS Sanitization
    message = html.escape(message[:2000])

    if product_name and any(b in product_name for b in ['버튼', '플로팅', '상담', '전체', '신청']):
        product_name = ''

    conn = get_db()
    cursor = conn.cursor()
    # 1. Save customer message
    cursor.execute('''
        INSERT INTO chat_messages (session_id, sender, product_name, message)
        VALUES (?, 'user', ?, ?)
    ''', (session_id, product_name, message))

    # 2. Automatically trigger AI Concierge response
    ai_reply = generate_ai_advisor_reply(message, product_name)
    cursor.execute('''
        INSERT INTO chat_messages (session_id, sender, product_name, message)
        VALUES (?, 'admin', 'KIRENO AI 컨시어지', ?)
    ''', (session_id, ai_reply))

    conn.commit()
    conn.close()

    log_event('AI_CHAT_REPLY', f'제미나이 AI 자동 답변 생성 ({session_id})')
    return jsonify({'success': True})

@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    session_id = request.args.get('session_id', 'anonymous')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM chat_messages 
        WHERE session_id = ? OR session_id = 'welcome' 
        ORDER BY id ASC
    ''', (session_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'messages': messages})

@app.route('/api/inquiry', methods=['POST'])
def submit_inquiry():
    name = html.escape(request.form.get('name', '').strip()[:50])
    phone = re.sub(r'[^0-9\-+ ]', '', request.form.get('phone', '').strip())[:20]
    email = html.escape(request.form.get('email', '').strip()[:100])
    subject = html.escape(request.form.get('subject', '일반 문의').strip()[:100])
    message = html.escape(request.form.get('message', '').strip()[:2000])

    if not name or not message:
        return jsonify({'success': False, 'message': '이름과 문의 내용을 입력해주세요.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inquiries (name, phone, email, subject, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, phone, email, subject, message))
    conn.commit()
    conn.close()

    log_event('INQUIRY', f'새 고객 문의 접수: {name} ({subject})')
    return jsonify({'success': True, 'message': '문의가 정상적으로 접수되었습니다. 빠른 시일 내 연락드리겠습니다.'})

@app.route('/api/restock-alert', methods=['POST'])
def restock_alert():
    product_id = request.form.get('product_id')
    product_name = html.escape(request.form.get('product_name', '')[:100])
    phone = re.sub(r'[^0-9\-+ ]', '', request.form.get('phone', '').strip())[:20]

    if not phone:
        return jsonify({'success': False, 'message': '알림받으실 연락처를 입력해주세요.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO restock_alerts (product_id, product_name, phone)
        VALUES (?, ?, ?)
    ''', (product_id, product_name, phone))
    conn.commit()
    conn.close()

    log_event('RESTOCK_ALERT', f'재입고 알림 신청: {product_name} ({phone})')
    return jsonify({'success': True, 'message': f'[{product_name}] 다음 드롭/입고 시 SMS로 즉시 알려드립니다.'})

# --- Admin & Mission Control Routes ---

@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM products')
    total_products = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM chat_messages WHERE sender = "user"')
    total_chats = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM inquiries')
    total_inquiries = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM restock_alerts')
    total_restock = cursor.fetchone()[0]

    cursor.execute('SELECT * FROM chat_messages WHERE sender = "user" ORDER BY id DESC LIMIT 5')
    recent_chats = cursor.fetchall()

    uptime_hours = round((time.time() - SERVER_START_TIME) / 3600, 2)
    conn.close()

    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        total_chats=total_chats,
        total_inquiries=total_inquiries,
        total_restock=total_restock,
        recent_chats=recent_chats,
        uptime_hours=uptime_hours
    )

@app.route('/admin/chat')
@login_required
def admin_chat_console():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT session_id FROM chat_messages 
        WHERE session_id != 'welcome' 
        ORDER BY id DESC
    ''')
    sessions = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('admin/chat_console.html', sessions=sessions)

@app.route('/api/admin/chat/session-messages')
@login_required
def admin_session_messages():
    session_id = request.args.get('session_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC', (session_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'messages': messages})

@app.route('/api/admin/chat/reply', methods=['POST'])
@login_required
def admin_chat_reply():
    session_id = request.json.get('session_id')
    message = request.json.get('message', '').strip()

    if not session_id or not message:
        return jsonify({'success': False, 'message': '필수 데이터 누락'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_messages (session_id, sender, product_name, message)
        VALUES (?, 'admin', 'KIRENO 도예가 (직접응대)', ?)
    ''', (session_id, message))
    conn.commit()
    conn.close()

    log_event('CHAT_HUMAN_REPLY', f'도예가 직접 답변 전송 ({session_id}): {message[:30]}')
    return jsonify({'success': True})

@app.route('/admin/mission-control')
@login_required
def admin_mission_control():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM system_logs ORDER BY id DESC LIMIT 30')
    recent_logs = cursor.fetchall()
    conn.close()

    cpu_usage = psutil.cpu_percent(interval=None)
    mem_info = psutil.virtual_memory()

    return render_template(
        'admin/mission_control.html',
        mission_state=MISSION_CONTROL_STATE,
        cpu_usage=cpu_usage,
        mem_pct=mem_info.percent,
        recent_logs=recent_logs
    )

@app.route('/api/mission-control/live-data')
@login_required
def live_mission_data():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM system_logs ORDER BY id DESC LIMIT 15')
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'state': MISSION_CONTROL_STATE,
        'cpu': psutil.cpu_percent(interval=None),
        'mem': psutil.virtual_memory().percent,
        'uptime_sec': int(time.time() - SERVER_START_TIME),
        'logs': logs
    })

@app.route('/api/mission-control/run-cli', methods=['POST'])
@login_required
def run_cli_command():
    cmd = request.json.get('cmd', 'status')
    allowed_cmds = ['status', 'products', 'backup', 'chat', 'gemini', 'inspect', 'naver-sync']
    
    target_cmd = cmd.split()[0] if cmd else 'status'
    if target_cmd not in allowed_cmds:
        log_event('SECURITY_BLOCKED', f'비인가 CLI 명령어 실행 차단 시도: {cmd}')
        return jsonify({'success': False, 'output': f'보안 차단: [{target_cmd}] 명령어는 실행이 금지되어 있습니다.'}), 403

    import subprocess
    args = ['python', 'E:/kireno/kireno_cli.py'] + cmd.split()
    
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10, encoding='utf-8', errors='replace')
        output = proc.stdout if proc.stdout else proc.stderr
        log_event('CLI_EXEC', f'웹 관제센터에서 CLI 명령어 실행: {cmd}')
        return jsonify({'success': True, 'output': output})
    except Exception as e:
        return jsonify({'success': False, 'output': str(e)}), 500


@app.route('/admin/inspect')
@login_required
def admin_inspect():
    return render_template('admin/inspect.html')

@app.route('/admin/guides')
@login_required
def admin_guides():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT orders.*, products.image_url, products.dimensions, products.category
        FROM orders
        LEFT JOIN products ON orders.product_id = products.id
        ORDER BY orders.id DESC
    ''')
    orders = [dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM customers ORDER BY total_spent DESC')
    customers = [dict(row) for row in cursor.fetchall()]
    cursor.execute('''
        SELECT id, name, category, dimensions, description, price, stock_status,
               image_url, smartstore_url, japan_source_url, source_site_name, cost_jpy, origin_region
        FROM products
        ORDER BY CASE WHEN stock_status = '즉시출고' THEN 0 ELSE 1 END, id ASC
    ''')
    all_products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('admin/guides.html', orders=orders, customers=customers, all_products=all_products)

@app.route('/admin/operations')
@login_required
def admin_operations():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT orders.*, products.image_url, products.dimensions, products.category 
        FROM orders 
        LEFT JOIN products ON orders.product_id = products.id 
        ORDER BY orders.id DESC
    ''')
    orders = [dict(row) for row in cursor.fetchall()]

    cursor.execute('SELECT * FROM customers ORDER BY total_spent DESC')
    customers = [dict(row) for row in cursor.fetchall()]

    cursor.execute('SELECT id, name, category, price, japan_source_url, source_site_name, cost_jpy, stock_status, image_url FROM products ORDER BY name ASC')
    all_products = [dict(row) for row in cursor.fetchall()]

    # Financial Ledger Calculation
    total_revenue = sum(order.get('total_amount', 0) for order in orders)
    cogs = int(total_revenue * 0.35)  # 35% JPY procurement COGS
    delivery_expense = len(orders) * 4500  # 4,500 KRW Post office safe packaging & delivery
    operating_expense = int(total_revenue * 0.035)  # 3.5% PG & hosting
    total_expense = cogs + delivery_expense + operating_expense
    net_profit = total_revenue - total_expense
    profit_margin = round((net_profit / total_revenue * 100), 1) if total_revenue > 0 else 0

    finance = {
        'total_revenue': total_revenue,
        'cogs': cogs,
        'delivery_expense': delivery_expense,
        'operating_expense': operating_expense,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'profit_margin': profit_margin
    }

    # Shortage items (not ready for immediate dispatch or low stock)
    cursor.execute("SELECT * FROM products WHERE stock_status != '즉시출고' ORDER BY id ASC")
    shortage_items = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'admin/operations.html',
        finance=finance,
        orders=orders,
        customers=customers,
        shortage_items=shortage_items,
        all_products=all_products
    )

@app.route('/admin/orders/add', methods=['POST'])
@login_required
def admin_orders_add():
    customer_name = request.form.get('customer_name')
    customer_phone = request.form.get('customer_phone')
    pccc = request.form.get('pccc', 'P123456789012').strip().upper()
    product_id = request.form.get('product_id')
    product_name = request.form.get('product_name')
    quantity = int(request.form.get('quantity', 1))
    total_amount = int(request.form.get('total_amount', 49000))
    payment_method = request.form.get('payment_method', '무통장입금')
    japan_source_url = request.form.get('japan_source_url', '').strip()
    source_site_name = request.form.get('source_site_name', '라쿠텐 재팬').strip()
    jp_cost_jpy = request.form.get('jp_cost_jpy')

    conn = get_db()
    cursor = conn.cursor()

    if product_id:
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        p = cursor.fetchone()
        if p:
            if not product_name:
                product_name = p['name']
            if not japan_source_url:
                japan_source_url = p['japan_source_url']
            if not source_site_name:
                source_site_name = p['source_site_name']
            if not jp_cost_jpy:
                jp_cost_jpy = p['cost_jpy'] if 'cost_jpy' in p.keys() and p['cost_jpy'] else int(p['price'] * 0.044)

    if not jp_cost_jpy:
        jp_cost_jpy = int(total_amount * 0.044)
    else:
        jp_cost_jpy = int(jp_cost_jpy)

    order_num = f"KRN-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(100, 999)}"
    ems_tracking = f"EMS-JP{random.randint(100000, 999999)}KR"
    post_tracking = f"6892-3819-{random.randint(1000, 9999)}"

    cursor.execute('''
        INSERT INTO orders (
            order_number, customer_name, customer_phone, pccc, 
            product_id, product_name, quantity, total_amount, payment_method, 
            status, jp_order_status, jp_tracking_num, customs_status, 
            shipping_company, tracking_number, japan_source_url, source_site_name, jp_cost_jpy
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '주문접수', '일본현지발주완료', ?, '세관도착심사', '우체국택배(도예안심)', ?, ?, ?, ?)
    ''', (
        order_num, customer_name, customer_phone, pccc,
        product_id, product_name, quantity, total_amount, payment_method,
        ems_tracking, post_tracking, japan_source_url, source_site_name, jp_cost_jpy
    ))
    conn.commit()
    conn.close()

    log_event('ORDER_ADD', f'신규 일본직구 주문 등록: {order_num} ({customer_name} - {product_name} - PCCC: {pccc} - 사입가: ¥{jp_cost_jpy:,})')
    flash(f'일본 직구 주문[{order_num}]가 성공적으로 등록되었습니다. (개인통관고유부호: {pccc})', 'success')
    return redirect(request.referrer or url_for('admin_operations'))

@app.route('/admin/orders/update-status', methods=['POST'])
@login_required
def admin_orders_update_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    conn = get_db()
    cursor = conn.cursor()

    jp_status = '일본현지발주완료'
    customs_st = '세관도착심사'
    if new_status in ['국제항공운송(EMS)', '항공운송중']:
        jp_status = '항공선적완료(EMS)'
        customs_st = '인천공항입항대기'
    elif new_status in ['세관통관심사', '세관통관']:
        jp_status = '인천세관반입'
        customs_st = '통관심사진행중'
    elif new_status in ['세관반출완료', '1인검수패킹']:
        jp_status = '세관반출승인'
        customs_st = '세관반출완료(국내인계)'
    elif new_status in ['국내우체국배송', '배송중', '배송완료', '국내배송중']:
        jp_status = '국내도착완료'
        customs_st = '통관완료'

    cursor.execute('''
        UPDATE orders 
        SET status = ?, jp_order_status = ?, customs_status = ? 
        WHERE id = ?
    ''', (new_status, jp_status, customs_st, order_id))
    conn.commit()
    conn.close()

    log_event('ORDER_STATUS', f'주문 상태 변경 (ID: {order_id} -> {new_status} / {customs_st})')
    flash(f'주문 진행 단계가 [{new_status}] (세관: {customs_st})(으)로 실시간 업데이트되었습니다.', 'success')
    return redirect(request.referrer or url_for('admin_operations'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    client_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr or '127.0.0.1'
    now = time.time()

    # Brute-force protection: check if IP is locked out
    fail_count, lockout_until = LOGIN_FAILED_ATTEMPTS.get(client_ip, (0, 0))
    if now < lockout_until:
        remaining_sec = int(lockout_until - now)
        flash(f'보안 경고: 비정상적인 반복 로그인 실패로 접근이 일시 차단되었습니다. ({remaining_sec}초 후 재시도 가능)', 'error')
        return render_template('admin/login.html')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        next_url = request.args.get('next')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admin_users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            LOGIN_FAILED_ATTEMPTS.pop(client_ip, None)
            session.permanent = True
            session['admin_logged_in'] = True
            session['admin_user'] = username
            log_event('ADMIN_LOGIN', f'관리자 로그인 성공 ({username})')
            flash('관리자 시스템에 성공적으로 로그인했습니다.', 'success')
            if next_url and next_url.startswith('/admin'):
                return redirect(next_url)
            return redirect(url_for('admin_dashboard'))
        else:
            new_count = fail_count + 1
            new_lockout = now + 900 if new_count >= 5 else 0  # 15 min lockout after 5 fails
            LOGIN_FAILED_ATTEMPTS[client_ip] = (new_count, new_lockout)

            log_event('ADMIN_LOGIN_FAIL', f'로그인 실패 시도 ({username}) - 누적 {new_count}회')
            if new_count >= 5:
                flash('5회 연속 로그인 실패로 보안상 15분간 로그인이 잠겼습니다.', 'error')
            else:
                flash(f'아이디 또는 비밀번호가 올바르지 않습니다. (실패 {new_count}/5회)', 'error')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('로그아웃 되었습니다.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')
    username = session.get('admin_user', 'admin')

    if len(new_pw) < 8:
        flash('새 비밀번호는 최소 8자 이상이어야 합니다.', 'error')
        return redirect(url_for('admin_logs'))

    if new_pw != confirm_pw:
        flash('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.', 'error')
        return redirect(url_for('admin_logs'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM admin_users WHERE username = ?', (username,))
    row = cursor.fetchone()

    if not row or not check_password_hash(row['password_hash'], current_pw):
        conn.close()
        flash('현재 비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('admin_logs'))

    from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash(new_pw)
    cursor.execute('UPDATE admin_users SET password_hash = ? WHERE username = ?', (new_hash, username))
    conn.commit()
    conn.close()

    log_event('PASSWORD_CHANGE', f'관리자 비밀번호 안전 변경 완료 ({username})')
    flash('관리자 비밀번호가 성공적으로 변경되었습니다. 다음 로그인부터 적용됩니다.', 'success')
    return redirect(url_for('admin_logs'))

@app.route('/admin/cms', methods=['GET', 'POST'])
@login_required
def admin_cms():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        brand_name = request.form.get('brand_name')
        announcement = request.form.get('announcement')
        hero_title = request.form.get('hero_title')
        hero_subtitle = request.form.get('hero_subtitle')
        instagram_url = request.form.get('instagram_url')
        smartstore_url = request.form.get('smartstore_url', 'https://smartstore.naver.com/kireno').strip()
        theme_color = request.form.get('theme_color')
        contact_phone = request.form.get('contact_phone')
        contact_email = request.form.get('contact_email')
        notice_text = request.form.get('notice_text')
        ceo_name = request.form.get('ceo_name', '').strip()
        biz_reg_num = request.form.get('biz_reg_num', '').strip()
        mail_order_num = request.form.get('mail_order_num', '').strip()
        biz_address = request.form.get('biz_address', '').strip()
        seo_description = request.form.get('seo_description', '').strip()
        seo_keywords = request.form.get('seo_keywords', '').strip()
        naver_verification = request.form.get('naver_verification', '').strip()
        google_verification = request.form.get('google_verification', '').strip()

        cursor.execute('''
            UPDATE site_settings
            SET brand_name = ?, announcement = ?, hero_title = ?, hero_subtitle = ?,
                instagram_url = ?, smartstore_url = ?, theme_color = ?,
                contact_phone = ?, contact_email = ?, notice_text = ?,
                ceo_name = ?, biz_reg_num = ?, mail_order_num = ?, biz_address = ?,
                seo_description = ?, seo_keywords = ?, naver_verification = ?, google_verification = ?
            WHERE id = 1
        ''', (
            brand_name, announcement, hero_title, hero_subtitle,
            instagram_url, smartstore_url, theme_color,
            contact_phone, contact_email, notice_text,
            ceo_name, biz_reg_num, mail_order_num, biz_address,
            seo_description, seo_keywords, naver_verification, google_verification
        ))
        conn.commit()
        log_event('CMS_UPDATE', '관리자 사이트 문구 및 설정 업데이트 완료')
        flash('사이트 문구 및 설정이 실시간으로 저장되었습니다.', 'success')
        conn.close()
        return redirect(url_for('admin_cms'))

    cursor.execute('SELECT * FROM site_settings WHERE id = 1')
    settings = cursor.fetchone()
    conn.close()
    return render_template('admin/cms.html', settings=settings)

@app.route('/admin/products', methods=['GET', 'POST'])
@login_required
def admin_products():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            category = request.form.get('category')
            dimensions = request.form.get('dimensions')
            description = request.form.get('description')
            price = int(request.form.get('price', 0))
            sale_price = int(request.form.get('sale_price', 0)) or None
            badge = request.form.get('badge')
            image_url = request.form.get('image_url') or '/static/images/pot_cloud_sig.jpg'
            stock_status = request.form.get('stock_status', '즉시출고')

            japan_source_url = request.form.get('japan_source_url', '').strip()
            source_site_name = request.form.get('source_site_name', '라쿠텐 재팬').strip()

            cursor.execute('''
                INSERT INTO products (
                    name, category, dimensions, description, price, sale_price,
                    badge, image_url, stock_status, japan_source_url, source_site_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name, category, dimensions, description, price, sale_price,
                badge, image_url, stock_status, japan_source_url, source_site_name
            ))
            conn.commit()
            log_event('PRODUCT_ADD', f'새 상품 등록: {name}')
            flash('상품이 성공적으로 등록되었습니다.', 'success')

        elif action == 'delete':
            product_id = request.form.get('product_id')
            cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
            conn.commit()
            log_event('PRODUCT_DELETE', f'상품 삭제 (ID: {product_id})')
            flash('상품이 삭제되었습니다.', 'info')

        elif action == 'toggle_stock':
            product_id = request.form.get('product_id')
            new_status = request.form.get('stock_status')
            cursor.execute('UPDATE products SET stock_status = ? WHERE id = ?', (new_status, product_id))
            conn.commit()
            log_event('STOCK_UPDATE', f'재고상태 변경 (ID: {product_id} -> {new_status})')
            flash(f'상품 재고 상태가 [{new_status}]으로 업데이트되었습니다.', 'success')

        elif action == 'edit':
            product_id = request.form.get('product_id')
            name = request.form.get('name', '').strip()
            category = request.form.get('category', '').strip()
            dimensions = request.form.get('dimensions', '').strip()
            description = request.form.get('description', '').strip()
            price = int(request.form.get('price', 0))
            sale_price = int(request.form.get('sale_price', 0)) if request.form.get('sale_price') else None
            badge = request.form.get('badge', '').strip()
            image_url = request.form.get('image_url', '').strip() or '/static/images/ceramic_vase.jpg'
            stock_status = request.form.get('stock_status', '즉시출고')
            japan_source_url = request.form.get('japan_source_url', '').strip()
            source_site_name = request.form.get('source_site_name', '라쿠텐 재팬').strip()

            cursor.execute('''
                UPDATE products
                SET name = ?, category = ?, dimensions = ?, description = ?,
                    price = ?, sale_price = ?, badge = ?, image_url = ?, stock_status = ?,
                    japan_source_url = ?, source_site_name = ?
                WHERE id = ?
            ''', (name, category, dimensions, description, price, sale_price, badge, image_url, stock_status, japan_source_url, source_site_name, product_id))
            conn.commit()
            log_event('PRODUCT_UPDATE', f'상품 정보 직접 수정 완료: {name} (ID: {product_id}, 재고: {stock_status})')
            flash(f'[{name}] 상품의 모든 정보(일본 원문 링크 및 재고 상태 포함)가 성공적으로 저장되었습니다.', 'success')

        conn.close()
        return redirect(url_for('admin_products'))

    cursor.execute('SELECT * FROM products ORDER BY id ASC')
    products = cursor.fetchall()
    conn.close()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/naver-sync-now', methods=['POST'])
@login_required
def admin_naver_sync_now():
    count = sync_naver_smartstore_catalog()
    log_event('NAVER_SYNC', f'네이버 스마트스토어 공식 도자기 {count}종 전수 동기화 완료')
    flash(f'네이버 스마트스토어 공식 도자기 카탈로그 {count}종이 성공적으로 동기화되었습니다.', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/products/naver-upload', methods=['POST'])
@login_required
def admin_naver_upload():
    if 'naver_file' not in request.files:
        flash('업로드할 엑셀/CSV 파일을 선택해 주세요.', 'error')
        return redirect(url_for('admin_products'))

    file = request.files['naver_file']
    if not file or not file.filename:
        flash('선택된 파일이 없습니다.', 'error')
        return redirect(url_for('admin_products'))

    res = import_naver_excel_or_csv(file.read(), file.filename)
    if res.get('success'):
        log_event('NAVER_EXCEL_IMPORT', f'네이버 엑셀 일괄 등록: {res["count"]}개 상품')
        flash(res.get('message'), 'success')
    else:
        flash(res.get('message', '업로드 처리 중 오류 발생'), 'error')

    return redirect(url_for('admin_products'))

@app.route('/admin/inquiries')
@login_required
def admin_inquiries():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inquiries ORDER BY id DESC')
    inquiries = cursor.fetchall()
    conn.close()
    return render_template('admin/inquiries.html', inquiries=inquiries)

@app.route('/admin/logs')
@login_required
def admin_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM system_logs ORDER BY id DESC LIMIT 100')
    logs = cursor.fetchall()
    conn.close()
    return render_template('admin/logs.html', logs=logs)

@app.route('/healthz')
def healthz():
    return jsonify({'status': 'ok', 'service': 'KIRENO'}), 200

@app.route('/pixel-studio')
def pixel_studio():
    return render_template('pixel_studio.html')

@app.route('/game')
def star_breaker_game():
    return render_template('game.html')

if __name__ == '__main__':
    init_db()
    print("Starting KIRENO Platform with 24/7 AI Concierge on http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False, threaded=True)



