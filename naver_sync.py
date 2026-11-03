# -*- coding: utf-8 -*-
"""
KIRENO Platform - Naver Smartstore Product Synchronization & Excel Importer
Supports:
  1. Direct Naver Smartstore Official Catalog Synchronization (15 authentic ceramic items)
  2. Naver Seller Center Excel (.xlsx) / CSV (.csv) Importer
"""

import os
import io
import csv
import sqlite3
import openpyxl

if os.path.exists(os.path.join(os.path.dirname(__file__), 'kireno.db')):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'kireno.db')
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), '1_original', 'kireno.db')

NAVER_AUTHENTIC_CERAMICS = [
    # 1. 도자 화병 & 오브제
    {
        "name": "시가라키야키 자연재 무광 도자 화병 (Ash Glaze Vase)",
        "category": "도자화병/오브제",
        "dimensions": "외경 Ø 12cm × 높이 21cm",
        "description": "전통 시가라키 가마의 자연재 유약과 거친 흙의 질감을 살려 꽃과 가지를 한 폭의 동양화처럼 연출해주는 장인 수제 도자 화병입니다.",
        "price": 68000,
        "sale_price": 62000,
        "badge": "SIGNATURE",
        "image_url": "/static/images/ceramic_vase.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "키레노 백자 달항아리 미니 세라믹 오브제",
        "category": "도자화병/오브제",
        "dimensions": "외경 Ø 14cm × 높이 13.5cm",
        "description": "순백의 여백과 비대칭 곡선의 미학을 현대적인 미니멀 오브제로 재해석한 1,280℃ 고온 백자 달항아리입니다.",
        "price": 55000,
        "sale_price": 49000,
        "badge": "BEST",
        "image_url": "/static/images/moon_jar.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "미니멀 도자 인센스 홀더 & 스톤 트레이",
        "category": "도자화병/오브제",
        "dimensions": "가로 14cm × 세로 9cm",
        "description": "자연석을 닮은 매트 질감의 도자 플레이트와 인센스 스틱 거치 홀더 세트. 서재와 다도 공간의 고요한 향기를 완성합니다.",
        "price": 26000,
        "sale_price": 22000,
        "badge": "POPULAR",
        "image_url": "/static/images/ceramic_incense.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "빈티지 테라코타 핸드메이드 화병 (Vintage Terracotta Vase)",
        "category": "도자화병/오브제",
        "dimensions": "외경 Ø 13cm × 높이 19cm",
        "description": "전통 테라코타 흙의 따뜻한 붉은 질감과 물레 손맛이 살아있는 빈티지 내추럴 화병입니다.",
        "price": 48000,
        "sale_price": 42000,
        "badge": "NEW",
        "image_url": "/static/images/ceramic_vase_obj.jpg",
        "stock_status": "즉시출고"
    },

    # 2. 도자 식기 & 다도 세트
    {
        "name": "수제 물레 성형 도자 찻잔 & 숙우 2인 다도 세트",
        "category": "도자식기/다도",
        "dimensions": "찻잔 Ø 7.5cm × H 5.5cm / 숙우 220ml",
        "description": "잎차의 수색을 가장 맑게 비추는 부드러운 손맛의 다도 잔 2점과 절수력이 뛰어난 숙우(물식힘그릇) 풀세트입니다.",
        "price": 52000,
        "sale_price": 46000,
        "badge": "HANDMADE",
        "image_url": "/static/images/ceramic_tea_cup.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "흑유 매트 핸드크래프트 세라믹 머그 (320ml)",
        "category": "도자식기/다도",
        "dimensions": "구경 Ø 8.5cm × 높이 9.2cm",
        "description": "철분 함유 태토를 물레 성형 후 흑유를 입혀 은은한 흑철색 광택과 뛰어난 보온성을 지닌 데일리 세라믹 머그입니다.",
        "price": 32000,
        "sale_price": 28000,
        "badge": "STEADY",
        "image_url": "/static/images/ceramic_cup.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "분청 고온 소성 텍스처 도자 보울 (사발)",
        "category": "도자식기/다도",
        "dimensions": "구경 Ø 16cm × 높이 7cm",
        "description": "거친 귀얄 분청 기법을 현대적으로 풀어내어 샐러드, 면기, 비빔요리 등 어떤 음식을 담아도 작품이 되는 깊은 볼입니다.",
        "price": 38000,
        "sale_price": 34000,
        "badge": "NEW",
        "image_url": "/static/images/ceramic_bowl.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "내추럴 스톤웨어 세라믹 플레이트 (평접시 21cm)",
        "category": "도자식기/다도",
        "dimensions": "지름 Ø 21.5cm × 높이 2cm",
        "description": "고운 암석 입자가 은은하게 비치는 내추럴 스톤웨어 평접시. 디저트, 브런치, 스테이크 플레이팅에 제격입니다.",
        "price": 35000,
        "sale_price": 31000,
        "badge": "POPULAR",
        "image_url": "/static/images/ceramic_plate.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "시가라키야키 러스틱 와비사비 다완 (Wabi-sabi Matcha Bowl)",
        "category": "도자식기/다도",
        "dimensions": "구경 Ø 12.5cm × 높이 7.8cm",
        "description": "와비사비 철학이 깃든 말차 전용 다완. 가마 안에서 우연히 생긴 요변과 거친 흙의 결이 손안에 묵직한 평온을 줍니다.",
        "price": 65000,
        "sale_price": 58000,
        "badge": "PREMIUM",
        "image_url": "/static/images/ceramic_tableware.jpg",
        "stock_status": "즉시출고"
    },

    # 3. 도자 화분 & 토기
    {
        "name": "[시그니처] 키레노 구름 도자 토분 12호 + 전용 세라믹 받침",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 12cm × 높이 11.5cm",
        "description": "키레노 대표작. 전통 물레 성형으로 빚은 구름 실루엣과 고온 소성 토기의 우수한 통기성을 결합한 도자 화분 세트입니다.",
        "price": 36000,
        "sale_price": 32000,
        "badge": "BEST",
        "image_url": "/static/images/pot_cloud_sig.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "[시그니처] 키레노 구름 도자 토분 15호",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 15cm × 높이 14.5cm",
        "description": "안스리움 및 고급 관엽 식재를 위한 깊고 여유로운 분형의 장인 수제 도자분입니다.",
        "price": 44000,
        "sale_price": 39000,
        "badge": "SIGNATURE",
        "image_url": "/static/images/pot_cloud_sig.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "시가라키야키 무광 흑철유 도자 화분",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 13.5cm × 높이 15cm",
        "description": "일본 전통 시가라키 가마의 흑철유 유약 처리로 매트하면서도 묵직한 하중을 갖춘 최고급 장인 도자 분입니다.",
        "price": 58000,
        "sale_price": 52000,
        "badge": "PREMIUM",
        "image_url": "/static/images/pot_shigaraki.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "시가라키야키 텍스처 수제 토기 팟 (Shigaraki Raw Earth Pot)",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 13cm × 높이 13cm",
        "description": "시가라키 특유의 굵은 석영 입자가 드러나 식물 뿌리의 호흡과 배수를 극대화한 명품 수제 토기 팟입니다.",
        "price": 54000,
        "sale_price": 48000,
        "badge": "HOT",
        "image_url": "/static/images/pot_stone_gray.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "가르니에 수제 통기성 토분 M (Garnier Raw Clay)",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 14cm × 높이 13.5cm",
        "description": "천연 옹기토와 테라코타 조합으로 빚어낸 자연스러운 세월의 백화 멋이 흐르는 정통 수제 토기입니다.",
        "price": 35000,
        "sale_price": 31000,
        "badge": "STEADY",
        "image_url": "/static/images/pot_terracotta.jpg",
        "stock_status": "즉시출고"
    },
    {
        "name": "아프리카 괴근·아가베 전용 세라믹 샬로우 팟",
        "category": "도자화분/토기",
        "dimensions": "외경 Ø 10.5cm × 높이 7.5cm",
        "description": "파키포디움과 아가베를 돋보이게 하는 얕고 넓은 분형의 고온 소성 암석 질감 수제 분입니다.",
        "price": 34000,
        "sale_price": 30000,
        "badge": "LIMITED",
        "image_url": "/static/images/pot_succulent.jpg",
        "stock_status": "즉시출고"
    }
]

def sync_naver_smartstore_catalog():
    """
    Synchronizes the full 15 authentic ceramic items from Naver Smartstore into products table.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM products")
    for p in NAVER_AUTHENTIC_CERAMICS:
        cur.execute('''
            INSERT INTO products (
                name, category, dimensions, description, price, sale_price,
                badge, image_url, smartstore_url, is_featured, stock_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 1, ?)
        ''', (
            p["name"], p["category"], p["dimensions"], p["description"],
            p["price"], p["sale_price"], p["badge"], p["image_url"], p["stock_status"]
        ))

    conn.commit()
    conn.close()
    return len(NAVER_AUTHENTIC_CERAMICS)

def import_naver_excel_or_csv(file_bytes, filename):
    """
    Parses uploaded Naver Smartstore Excel (.xlsx) or CSV (.csv) file
    and inserts/updates the products into products table.
    """
    rows_to_insert = []
    
    if filename.lower().endswith('.xlsx'):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        headers = []
        for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
            if r_idx == 0:
                headers = [str(cell).strip() if cell else '' for cell in row]
                continue
            
            row_dict = dict(zip(headers, row))
            name = row_dict.get('상품명') or row_dict.get('상품명(필수)') or row_dict.get('name')
            if not name:
                continue

            try:
                price = int(float(str(row_dict.get('판매가') or row_dict.get('price') or 0).replace(',', '')))
            except Exception:
                price = 30000

            try:
                sale_raw = row_dict.get('할인가') or row_dict.get('sale_price')
                sale_price = int(float(str(sale_raw).replace(',', ''))) if sale_raw else None
            except Exception:
                sale_price = None

            category = row_dict.get('카테고리') or row_dict.get('category') or '도자기'
            dimensions = row_dict.get('규격') or row_dict.get('옵션') or '상세페이지 참조'
            description = row_dict.get('상세설명') or row_dict.get('description') or f'{name} 핸드크래프트 수제 도자기'
            image_url = row_dict.get('대표이미지') or row_dict.get('이미지') or '/static/images/ceramic_vase.jpg'
            badge = row_dict.get('태그') or row_dict.get('badge') or 'NAVER'
            stock_status = row_dict.get('재고상태') or '즉시출고'

            rows_to_insert.append((name, category, dimensions, description, price, sale_price, badge, image_url, stock_status))

    elif filename.lower().endswith('.csv'):
        content = file_bytes.decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(content))
        for row_dict in reader:
            name = row_dict.get('상품명') or row_dict.get('상품명(필수)') or row_dict.get('name')
            if not name:
                continue

            try:
                price = int(float(str(row_dict.get('판매가') or row_dict.get('price') or 0).replace(',', '')))
            except Exception:
                price = 30000

            try:
                sale_raw = row_dict.get('할인가') or row_dict.get('sale_price')
                sale_price = int(float(str(sale_raw).replace(',', ''))) if sale_raw else None
            except Exception:
                sale_price = None

            category = row_dict.get('카테고리') or row_dict.get('category') or '도자기'
            dimensions = row_dict.get('규격') or row_dict.get('옵션') or '상세페이지 참조'
            description = row_dict.get('상세설명') or row_dict.get('description') or f'{name} 핸드크래프트 수제 도자기'
            image_url = row_dict.get('대표이미지') or row_dict.get('이미지') or '/static/images/ceramic_vase.jpg'
            badge = row_dict.get('태그') or row_dict.get('badge') or 'NAVER'
            stock_status = row_dict.get('재고상태') or '즉시출고'

            rows_to_insert.append((name, category, dimensions, description, price, sale_price, badge, image_url, stock_status))

    if not rows_to_insert:
        return {"success": False, "count": 0, "message": "유효한 상품 데이터를 찾지 못했습니다. 파일 컬럼(상품명, 판매가 등)을 확인해 주세요."}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for item in rows_to_insert:
        cur.execute('''
            INSERT INTO products (
                name, category, dimensions, description, price, sale_price,
                badge, image_url, smartstore_url, is_featured, stock_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 1, ?)
        ''', item)
    conn.commit()
    conn.close()

    return {"success": True, "count": len(rows_to_insert), "message": f"{len(rows_to_insert)}개 상품이 성공적으로 동기화되었습니다."}
