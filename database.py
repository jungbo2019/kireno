import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'kireno.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Site Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY,
            brand_name TEXT NOT NULL,
            announcement TEXT,
            hero_title TEXT,
            hero_subtitle TEXT,
            instagram_url TEXT,
            smartstore_url TEXT,
            theme_color TEXT DEFAULT 'earth',
            contact_phone TEXT,
            contact_email TEXT,
            notice_text TEXT
        )
    ''')

    # 2. Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            dimensions TEXT,
            description TEXT,
            price INTEGER NOT NULL,
            sale_price INTEGER,
            badge TEXT,
            image_url TEXT,
            smartstore_url TEXT,
            is_featured INTEGER DEFAULT 1,
            stock_status TEXT DEFAULT '즉시출고'
        )
    ''')

    # 3. 1:1 Real-time Chat / Consultation Messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            product_name TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0
        )
    ''')

    # 4. Inquiries
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT '접수완료'
        )
    ''')

    # 5. Restock Alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restock_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT '대기중'
        )
    ''')

    # 6. System Logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            ip_address TEXT,
            latency_ms REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Admin Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Update site settings focused on CERAMICS (도자기) without wiping CMS customizations
    cursor.execute('SELECT COUNT(*) FROM site_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO site_settings (
                id, brand_name, announcement, hero_title, hero_subtitle,
                instagram_url, smartstore_url, theme_color,
                contact_phone, contact_email, notice_text
            ) VALUES (
                1,
                'KIRENO 키레노',
                'KIRENO 도예 아뜰리에 | 흙과 불, 시간으로 빚어낸 수제 도자기(Ceramics) 1:1 맞춤 상담 쇼룸',
                '흙과 불의 결, 일상에 스며드는 수제 도자기',
                '장인의 물레 성형과 고온 장작가마 소성으로 완성한 프리미엄 도자 식기, 화병, 오브제 & 도자분 컬렉션',
                'https://www.instagram.com/p/Dcc5jYzGD-c/',
                'https://smartstore.naver.com/kireno',
                'earth',
                '010-2345-6789',
                'contact@kireno.kr',
                '모든 키레노 도자기는 1,250도 이상의 고온에서 소성되어 단단한 내구성과 천연 유약의 고유한 크랙/요변을 품고 있습니다. 1:1 상담을 통해 작품의 디테일과 맞춤 주문을 안내해 드립니다.'
            )
        ''')

    # Ensure SEO & E-Commerce Legal Business Columns exist in site_settings
    cursor.execute("PRAGMA table_info(site_settings)")
    existing_cols = {r[1] for r in cursor.fetchall()}
    extra_settings_cols = {
        'ceo_name': "TEXT DEFAULT '우상준'",
        'company_name': "TEXT DEFAULT '모엔드(MOEND)'",
        'biz_reg_num': "TEXT DEFAULT '740-02-03832'",
        'mail_order_num': "TEXT DEFAULT '2026-서울구로-1158 호'",
        'biz_address': "TEXT DEFAULT '대한민국 · 일본 교토/시가라키 공방 직공수 아뜰리에'",
        'seo_description': "TEXT DEFAULT '일본 교토·시가라키 장인의 수공예 도자기 화분, 재팬디 패브릭 액자, 와비사비 원목 인센스 홀더 공식 쇼룸. 인천세관 정식 수입통관 및 1인 대표 전수 육안검수 보장.'",
        'seo_keywords': "TEXT DEFAULT '키레노, KIRENO, 일본 도자기 화분, 시가라키 화분, 괴근식물 화분, 재팬디 인테리어, 패브릭 액자, 원목 인센스 홀더, 달항아리 오브제, 수제 토분'",
        'naver_verification': "TEXT DEFAULT 'kireno_naver_search_advisor_ready'",
        'google_verification': "TEXT DEFAULT 'kireno_google_search_console_ready'",
    }
    for col_name, col_def in extra_settings_cols.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE site_settings ADD COLUMN {col_name} {col_def}")

    cursor.execute("UPDATE site_settings SET smartstore_url = 'https://smartstore.naver.com/kireno' WHERE id = 1 AND (smartstore_url IS NULL OR smartstore_url = '')")

    cursor.execute('SELECT COUNT(*) FROM admin_users')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO admin_users (username, password_hash)
            VALUES (?, ?)
        ''', ('admin', generate_password_hash('admin1234!')))

    # Authentic Ceramic / Pottery Products List (도자기 중심)
    cursor.execute('SELECT COUNT(*) FROM products')
    prod_count = cursor.fetchone()[0]
    if prod_count == 0:
        ceramic_products = [
        # Category: 도자 화병 & 오브제 (Vase & Object)
        (
            '시가라키야키 자연재 무광 도자 화병 (Ash Glaze Vase)',
            '도자화병/오브제',
            '외경 Ø 12cm × 높이 21cm',
            '전통 시가라키 가마의 자연재 유약과 거친 흙의 질감을 살려 꽃과 가지를 한 폭의 동양화처럼 연출해주는 장인 수제 도자 화병입니다.',
            68000,
            62000,
            'SIGNATURE',
            '/static/images/ceramic_vase.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '키레노 백자 달항아리 미니 세라믹 오브제',
            '도자화병/오브제',
            '외경 Ø 14cm × 높이 13.5cm',
            '조선 백자의 담백하고 유려한 비대칭 곡선미를 현대적 공간에 맞게 재해석한 테이블웨어 세라믹 오브제입니다.',
            55000,
            49000,
            'BEST',
            '/static/images/moon_jar.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '미니멀 도자 인센스 홀더 & 스톤 트레이',
            '도자화병/오브제',
            '가로 14cm × 세로 9cm',
            '재가 흩날리지 않도록 홈을 내고 무광 매트 유약으로 마감하여 서재와 다도 공간의 격을 높여주는 수제 도자 인센스 소품입니다.',
            26000,
            22000,
            'POPULAR',
            '/static/images/ceramic_incense.jpg',
            '',
            1,
            '즉시출고'
        ),

        # Category: 수제 도자 식기 & 다도 (Tableware & Tea)
        (
            '수제 물레 성형 도자 찻잔 & 숙우 2인 다도 세트',
            '도자식기/다도',
            '찻잔 Ø 7.5cm × H 5.5cm / 숙우 220ml',
            '손에 감기는 온화한 흙의 질감과 차의 수색을 맑게 비춰주는 천연 재유약 처리의 프리미엄 핸드크래프트 다도 세트입니다.',
            52000,
            46000,
            'HANDMADE',
            '/static/images/ceramic_cup.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '흑유 매트 핸드크래프트 세라믹 머그 (320ml)',
            '도자식기/다도',
            '구경 Ø 8.5cm × 높이 9.2cm',
            '철분 함유 흙을 1,280도 산화 소성하여 은은한 흑철색 광택과 뛰어난 보온성을 지닌 데일리 수제 머그잔입니다.',
            32000,
            28000,
            'STEADY',
            '/static/images/ceramic_cup.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '분청 고온 소성 텍스처 도자 보울 (사발)',
            '도자식기/다도',
            '구경 Ø 16cm × 높이 7cm',
            '투박하면서도 깊이 있는 귀얄 분청 기법을 적용하여 메인 요리와 다과, 수프를 격식 있게 담아내는 도예 식기입니다.',
            38000,
            34000,
            'NEW',
            '/static/images/ceramic_bowl.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '내추럴 스톤웨어 세라믹 플레이트 (평접시 21cm)',
            '도자식기/다도',
            '지름 Ø 21.5cm × 높이 2cm',
            '거친 암석 입자가 은은하게 비치는 매트 스톤웨어 접시로, 브런치와 스테이크, 다식 연출에 탁월합니다.',
            35000,
            31000,
            'POPULAR',
            '/static/images/ceramic_plate.jpg',
            '',
            1,
            '즉시출고'
        ),

        # Category: 수제 도자 화분 & 토기 (Ceramic Planters)
        (
            '[시그니처] 키레노 구름 도자 토분 12호 + 전용 세라믹 받침',
            '도자화분/토기',
            '외경 Ø 12cm × 높이 11.5cm',
            '키레노 대표작. 전통 물레 성형으로 빚은 구름 실루엣과 고온 소성 토기의 우수한 통기성을 결합한 도자 화분 세트입니다.',
            36000,
            32000,
            'BEST',
            '/static/images/pot_cloud_sig.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '[시그니처] 키레노 구름 도자 토분 15호',
            '도자화분/토기',
            '외경 Ø 15cm × 높이 14.5cm',
            '안스리움 및 고급 관엽 식재를 위한 깊고 여유로운 분형의 장인 수제 도자분입니다.',
            44000,
            39000,
            'SIGNATURE',
            '/static/images/pot_cloud_sig.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '시가라키야키 무광 흑철유 도자 화분',
            '도자화분/토기',
            '외경 Ø 13.5cm × 높이 15cm',
            '일본 전통 시가라키 가마의 흑철유 유약 처리로 매트하면서도 묵직한 하중을 갖춘 최고급 장인 도자 분입니다.',
            58000,
            52000,
            'PREMIUM',
            '/static/images/pot_shigaraki.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '가르니에 수제 통기성 토분 M (Garnier Raw Clay)',
            '도자화분/토기',
            '외경 Ø 14cm × 높이 13.5cm',
            '천연 옹기토와 테라코타 조합으로 빚어낸 자연스러운 세월의 백화 멋이 흐르는 정통 수제 토기입니다.',
            35000,
            31000,
            'STEADY',
            '/static/images/pot_terracotta.jpg',
            '',
            1,
            '즉시출고'
        ),
        (
            '아프리카 괴근·아가베 전용 세라믹 샬로우 팟',
            '도자화분/토기',
            '외경 Ø 10.5cm × 높이 7.5cm',
            '파키포디움과 아가베를 돋보이게 하는 얕고 넓은 분형의 고온 소성 암석 질감 수제 분입니다.',
            34000,
            30000,
            'LIMITED',
            '/static/images/pot_succulent.jpg',
            '',
            1,
            '즉시출고'
        )
    ]

        cursor.executemany('''
            INSERT INTO products (
                name, category, dimensions, description, price, sale_price,
                badge, image_url, smartstore_url, is_featured, stock_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ceramic_products)
        print("Database updated with AUTHENTIC CERAMICS CATALOG (12 items).")

    cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = 'welcome'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO chat_messages (session_id, sender, product_name, message)
            VALUES ('welcome', 'admin', 'KIRENO 도예 아뜰리에', '안녕하세요! 키레노 도예 아뜰리에입니다. 수제 도자 식기, 머그/찻잔, 화병, 오브제, 도자 화분에 대해 궁금하신 점을 말씀해주시면 작가와 AI가 실시간으로 1:1 상담해 드립니다.')
        ''')

    conn.commit()
    conn.close()
    print("Database updated with AUTHENTIC CERAMICS CATALOG (12 items).")

if __name__ == '__main__':
    init_db()
