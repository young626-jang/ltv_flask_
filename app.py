# app.py (최종 통합 버전)

import os
import re
import logging
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from collections import defaultdict
from datetime import datetime, timezone
import fitz # PDF 텍스트 추출을 위해 fitz(PyMuPDF) 임포트
import json
import subprocess
import threading
import requests


# --- 우리가 만든 헬퍼 파일들 임포트 ---
from utils import parse_korean_number, calculate_ltv_limit, convert_won_to_manwon, calculate_principal_from_ratio, auto_convert_loan_amounts, calculate_individual_ltv_limits
from ltv_map import region_map
from region_ltv_map import get_region_grade, get_ltv_standard
from history_manager_flask import fetch_all_customers, fetch_customer_details, create_new_customer, update_customer, delete_customer
# --- ▼▼▼ pdf_parser.py에서 모든 필요한 함수를 가져오도록 수정합니다 ▼▼▼ ---
from pdf_parser import (
    extract_address,
    extract_search_address,
    extract_area,
    extract_property_type,
    extract_owner_info,
    extract_viewing_datetime,
    check_registration_age,
    extract_owner_shares_with_birth,
    extract_rights_info,
    extract_construction_date,
    extract_last_transfer_info,
    extract_seizure_info,
    extract_restriction_info,
    check_land_ownership_right
)
from kb_scraper import get_kb_info

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask 앱 설정 ---
app = Flask(__name__)

# 배포 환경에서는 /tmp 사용, 로컬에서는 uploads 사용
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp' if os.path.exists('/tmp') else 'uploads')

# 데이터베이스 설정
DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///loan_review_data.db')
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
    SQLALCHEMY_DATABASE_URI=DB_PATH,
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# SQLAlchemy 초기화
db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 데이터베이스 모델 정의 ---
class LoanReviewData(db.Model):
    """대출 심사 현황 관리 데이터"""
    __tablename__ = 'loan_review_data'

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    birth_date = db.Column(db.String(20))
    collateral_value = db.Column(db.Integer)  # 담보평가액 (만원)
    loan_amount = db.Column(db.Integer)       # 신청금액 (만원)
    status = db.Column(db.String(50), default='접수')  # 진행상태
    credit_check_date = db.Column(db.String(20))       # 신용조회
    contract_schedule_date = db.Column(db.String(20))  # 자서예정일
    contract_complete_date = db.Column(db.String(20))  # 자서완료일
    remit_date = db.Column(db.String(20))              # 송금일
    manager = db.Column(db.String(50))                 # 담당자

    # JSON 형태로 저장할 복잡한 데이터들
    status_history = db.Column(db.Text)  # 상태 변경 히스토리 (JSON)
    memo_history = db.Column(db.Text)    # 메모 히스토리 (JSON)

    # 메타데이터
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """모델을 딕셔너리로 변환"""
        return {
            'id': self.id,
            'customerName': self.customer_name,
            'phone': self.phone,
            'birthDate': self.birth_date,
            'collateralValue': self.collateral_value,
            'loanAmount': self.loan_amount,
            'status': self.status,
            'creditCheckDate': self.credit_check_date,
            'contractScheduleDate': self.contract_schedule_date,
            'contractCompleteDate': self.contract_complete_date,
            'remitDate': self.remit_date,
            'manager': self.manager,
            'statusHistory': json.loads(self.status_history) if self.status_history else [],
            'memoHistory': json.loads(self.memo_history) if self.memo_history else [],
            'createdAt': self.created_at.isoformat() if self.created_at else '',
            'updatedAt': self.updated_at.isoformat() if self.updated_at else ''
        }

    @staticmethod
    def from_dict(data):
        """딕셔너리로부터 모델 생성"""
        record = LoanReviewData()
        record.customer_name = data.get('customerName', '')
        record.phone = data.get('phone', '')
        record.birth_date = data.get('birthDate', '')
        record.collateral_value = data.get('collateralValue')
        record.loan_amount = data.get('loanAmount')
        record.status = data.get('status', '접수')
        record.credit_check_date = data.get('creditCheckDate', '')
        record.contract_schedule_date = data.get('contractScheduleDate', '')
        record.contract_complete_date = data.get('contractCompleteDate', '')
        record.remit_date = data.get('remitDate', '')
        record.manager = data.get('manager', '')
        record.status_history = json.dumps(data.get('statusHistory', []))
        record.memo_history = json.dumps(data.get('memoHistory', []))
        return record

# --- 템플릿 필터 및 에러 핸들러 (기존과 동일) ---
@app.template_filter()
def format_thousands(value):
    try: return f"{int(value):,}"
    except (ValueError, TypeError): return value

@app.errorhandler(413)
def too_large(e): return jsonify({"success": False, "error": "파일 크기가 너무 큽니다 (최대 16MB)"}), 413
@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"success": False, "error": "서버 내부 오류가 발생했습니다"}), 500

# --- 페이지 라우트 (기존과 동일) ---
@app.route('/')
def main_calculator_page():
    return render_template('entry.html', region_map=region_map)

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

# --- 대출심사 현황관리 라우트 ---
@app.route('/loan-review')
def loan_review_page():
    customer_name = request.args.get('name', '')
    birth_date = request.args.get('birth', '')
    return render_template('loan_review_system.html', customer_name=customer_name, birth_date=birth_date)

# --- ▼▼▼ PDF 업로드 API를 대폭 업그레이드합니다 ▼▼▼ ---
@app.route('/api/upload', methods=['POST'])
def upload_and_parse_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 1. PDF 텍스트 추출
    try:
        doc = fitz.open(filepath)
        full_text = "".join(page.get_text("text") for page in doc)
        doc.close()
    except Exception as e:
        return jsonify({'error': f'PDF Parsing failed: {str(e)}'}), 500

    # 2. PDF 내부 데이터 파싱 (순수 텍스트 분석)
    viewing_dt = extract_viewing_datetime(full_text)
    extracted_address = extract_address(full_text)
    extracted_area = extract_area(full_text)
    property_type_info = extract_property_type(full_text)
    rights_info = extract_rights_info(full_text)
    owner_info = extract_owner_info(full_text)

    # [확인] 준공일 & 소유권 이전일 함수 호출
    construction_date = extract_construction_date(full_text) # 준공일
    transfer_info = extract_last_transfer_info(full_text)    # 소유권 이전 내역 (날짜, 원인, 가액)

    # [신규] 압류/가압류 정보 추출
    seizure_info = extract_seizure_info(full_text)

    # [신규] 금지사항등기(전매제한/거주의무) 정보 추출
    restriction_info = extract_restriction_info(full_text)

    # [신규] 소유권대지권 확인
    has_land_ownership_right = check_land_ownership_right(full_text)

    # KB API로 세대수/준공일/시세/단지번호 한 번에 조회
    print(f"\n===== KB API 조회 시작 =====")
    print(f"추출된 주소: {extracted_address}")
    area_val = 0.0
    try:
        area_str = extracted_area.replace('㎡', '').strip() if extracted_area else ''
        area_val = float(area_str) if area_str else 0.0
    except Exception:
        pass
    try:
        kb_info = get_kb_info(extracted_address, area_val if area_val > 0 else None)
        print(f"KB API 결과: {kb_info}")
    except Exception as e:
        print(f"KB API 조회 중 에러: {e}")
        import traceback
        traceback.print_exc()
        kb_info = {'success': False, 'kb_price': 0, 'kb_price_high': 0, 'kb_price_low': 0,
                   'total_households': 0, 'completion_date': '', 'complex_no': '', 'complex_name': '', 'area_m2': 0.0}
    print(f"===== KB API 조회 종료 =====\n")

    # building_info 호환 형식으로 변환 (기존 프론트 코드 유지)
    building_info = {
        'success': kb_info['total_households'] > 0 or bool(kb_info['completion_date']),
        'total_households': kb_info['total_households'],
        'completion_date': kb_info['completion_date'],
        'raw_completion_date': kb_info['completion_date'],
        'buildings': []
    }

    # 3. 결과 정리 및 반환
    search_address = extract_search_address(extracted_address)

    scraped_data = {
        'address': extracted_address,
        'search_address': search_address,  # [신규] KB시세 검색용 축약 주소
        'area': extracted_area,
        'property_type': property_type_info.get('detail', 'Unknown'),
        'property_category': property_type_info.get('type', 'Unknown'),
        'customer_name': owner_info,
        'viewing_datetime': viewing_dt,
        'age_check': check_registration_age(viewing_dt),

        # [추가됨] 준공일 및 소유권 정보
        'construction_date': construction_date,          # 준공일
        'transfer_date': transfer_info.get('date', ''),  # 소유권 이전일
        'transfer_reason': transfer_info.get('reason', ''),  # 이전 원인 (매매/상속 등)
        'transfer_price': transfer_info.get('price', ''),  # 거래가액

        'owner_shares': extract_owner_shares_with_birth(full_text),
        'has_land_ownership_right': has_land_ownership_right,  # [신규] 소유권대지권 여부
        'floor': int(re.search(r'제?(\d+)층', extracted_address).group(1)) if re.search(r'제?(\d+)층', extracted_address) else None,
    }

    return jsonify({
        "success": True,
        "scraped_data": scraped_data,
        "rights_info": rights_info,
        "seizure_info": seizure_info,
        "restriction_info": restriction_info,
        "building_info": building_info,
        "kb_info": {
            "kb_price": kb_info['kb_price'],
            "kb_price_high": kb_info['kb_price_high'],
            "kb_price_low": kb_info['kb_price_low'],
            "complex_no": kb_info['complex_no'],
            "complex_name": kb_info['complex_name'],
            "area_m2": kb_info['area_m2'],
            "rcns_info": kb_info.get('rcns_info'),
            "error": kb_info.get('error', ''),
        }
    })

# --- (이하 나머지 모든 API 라우트 및 앱 실행 코드는 기존과 완벽하게 동일합니다) ---

@app.route('/view_pdf/<filename>')
def view_pdf(filename):
    # ... (기존 코드)
    pass

def format_manwon(value):
    """만원 단위로 포맷팅하는 헬퍼 함수"""
    try:
        val = int(parse_korean_number(value))
        return f"{val:,}만" if val != 0 else "0만"
    except:
        return str(value)

def get_region_from_address(address):
    """주소에서 지역(서울/경기/인천) 추출"""
    if not address or not address.strip():
        return None

    # 지역명 확인 (우선순위: 서울 > 인천 > 경기)
    if '서울' in address:
        return '서울'
    elif '인천' in address:
        return '인천'
    elif '경기' in address:
        return '경기'

    return None


def auto_calculate_ltv(address, area, is_senior=True, kb_price=None, property_type="APT", completion_date=None, is_meritz_pledge=True):
    """
    메리츠캐피탈 기준에 따라 주소와 면적으로 자동 LTV 계산

    Args:
        address (str): 주소
        area (float): 면적 (㎡ 단위)
        is_senior (bool): True=선순위, False=후순위
        kb_price (int): KB 시세 (만원 단위, 15억 초과 시 5% 차감 적용)
        property_type (str): 'APT' 또는 'Non-APT'
        completion_date (str): 준공일자 (YYYY-MM 형식, 예: 1980-01)
        is_meritz_pledge (bool): 메리츠 질권 적용 여부 (True일 때만 광역시 3군 인정)

    Returns:
        float: 자동 계산된 LTV (%), Non-APT 2군/3군 취급불가 시 None
    """
    if not address or not area or area <= 0:
        return None

    try:
        # 1. 주소에서 급지 자동 판단 (메리츠 질권 여부에 따라 광역시 3군 인정)
        region_grade = get_region_grade(address, is_meritz_pledge=is_meritz_pledge)

        if region_grade == "미분류":
            logger.warning(f"급지 미분류: {address}")
            return None

        # 2. 급지, 물건유형, 면적, 선후순위에 따른 LTV 기준값 조회
        ltv_standard = get_ltv_standard(region_grade, float(area), is_senior, property_type)

        # Non-APT 2군/3군 취급불가
        if ltv_standard is None:
            logger.warning(f"Non-APT {region_grade} 취급불가: {address}")
            return None

        # 3. 시세 15억(150000만원) 초과 시 5% 차감
        if kb_price and kb_price > 150000:
            ltv_standard = max(0, ltv_standard - 5.0)  # 음수가 되지 않도록 처리
            logger.info(f"시세 15억 초과 - LTV 5% 차감 적용: {ltv_standard}% (시세: {kb_price}만원)")

        # 5. 40년 이상 노후주택 LTV 60% 제한
        if completion_date and completion_date.strip():
            try:
                # 준공일자 파싱 (YYYY-MM 형식)
                completion_parts = completion_date.strip().split('-')
                if len(completion_parts) >= 2:
                    completion_year = int(completion_parts[0])
                    completion_month = int(completion_parts[1])

                    # 현재 날짜
                    from datetime import datetime
                    today = datetime.now()
                    current_year = today.year
                    current_month = today.month

                    # 경과 년수 계산 (월 고려)
                    years_elapsed = current_year - completion_year
                    if current_month < completion_month:
                        years_elapsed -= 1  # 아직 준공월이 지나지 않았으면 1년 차감

                    # 40년 이상이면 LTV 60% 제한
                    if years_elapsed >= 40:
                        if ltv_standard > 60:
                            ltv_standard = 60.0
                            logger.info(f"40년 이상 노후주택 - LTV 60% 제한 적용: {completion_date} (경과: {years_elapsed}년)")
            except (ValueError, IndexError) as e:
                logger.warning(f"준공일자 파싱 실패: {completion_date}, 오류: {e}")

        # 6. 현재 LTV 상한선 79% 적용 (임시)
        LTV_MAX_CAP = 79.0
        if ltv_standard > LTV_MAX_CAP:
            ltv_standard = LTV_MAX_CAP
            logger.info(f"LTV 상한선 {LTV_MAX_CAP}% 적용")

        return ltv_standard
    except Exception as e:
        logger.error(f"LTV 자동 계산 중 오류 (주소: {address}, 면적: {area}): {e}")
        return None

def auto_calculate_ltv_with_reasons(address, area, is_senior=True, kb_price=None, property_type="APT", completion_date=None, is_meritz_pledge=True):
    """
    메리츠캐피탈 기준에 따라 주소와 면적으로 자동 LTV 계산 (적용 사유 포함)

    Args:
        address (str): 주소
        area (float): 면적 (㎡ 단위)
        is_senior (bool): True=선순위, False=후순위
        kb_price (int): KB 시세 (만원 단위, 15억 초과 시 5% 차감 적용)
        property_type (str): 'APT' 또는 'Non-APT'
        completion_date (str): 준공일자 (YYYY-MM 형식, 예: 1980-01)
        is_meritz_pledge (bool): 메리츠 질권 적용 여부 (True일 때만 광역시 3군 인정)

    Returns:
        dict: {
            'ltv': float,  # 최종 LTV (%)
            'reasons': list[str],  # 적용 사유 리스트
            'error': str or None  # 오류 메시지
        }
    """
    reasons = []

    if not address or not area or area <= 0:
        return {'ltv': None, 'reasons': [], 'error': '주소 또는 면적이 유효하지 않습니다'}

    try:
        # 1. 주소에서 급지 자동 판단 (메리츠 질권 여부에 따라 광역시 3군 인정)
        region_grade = get_region_grade(address, is_meritz_pledge=is_meritz_pledge)

        if region_grade == "미분류":
            return {'ltv': None, 'reasons': [], 'error': '급지를 판단할 수 없습니다'}

        loan_type = "선순위" if is_senior else "후순위"
        type_label = "Non-APT" if property_type == "Non-APT" else "APT"
        reasons.append(f"급지: {region_grade} | {loan_type} | {type_label}")

        # 2. 급지, 물건유형, 면적, 선후순위에 따른 LTV 기준값 조회
        ltv_standard = get_ltv_standard(region_grade, float(area), is_senior, property_type)

        # Non-APT 2군/3군 취급불가
        if ltv_standard is None:
            return {'ltv': None, 'reasons': reasons, 'error': f'Non-APT {region_grade} 취급불가'}

        # 기본 LTV 표시
        original_ltv = ltv_standard
        reasons.append(f"기본 LTV: {original_ltv}%")

        # 면적 정보 추가
        if float(area) > 135:
            reasons.append(f"⚠️ 전용면적 135㎡ 초과 ({area}㎡)")
            if is_senior and ltv_standard > 60:
                reasons.append("  → 선순위 최대 60% 제한 적용")
            elif not is_senior and ltv_standard > 70:
                reasons.append("  → 후순위 최대 70% 제한 적용")
        else:
            reasons.append(f"전용면적: {area}㎡")

        # 3. 시세 15억(150000만원) 초과 시 5% 차감
        if kb_price and kb_price > 150000:
            kb_price_billion = kb_price / 10000  # 만원 → 억원
            old_ltv = ltv_standard
            ltv_standard = max(0, ltv_standard - 5.0)
            reasons.append(f"⚠️ 시세 15억 초과 ({kb_price_billion:.1f}억) → 5% 차감 ({old_ltv}% → {ltv_standard}%)")

        # 5. 40년 이상 노후주택 LTV 60% 제한
        if completion_date and completion_date.strip():
            try:
                # 준공일자 파싱 (YYYY-MM 형식)
                completion_parts = completion_date.strip().split('-')
                if len(completion_parts) >= 2:
                    completion_year = int(completion_parts[0])
                    completion_month = int(completion_parts[1])

                    # 현재 날짜
                    from datetime import datetime
                    today = datetime.now()
                    current_year = today.year
                    current_month = today.month

                    # 경과 년수 계산 (월 고려)
                    years_elapsed = current_year - completion_year
                    if current_month < completion_month:
                        years_elapsed -= 1

                    # 40년 이상이면 LTV 60% 제한
                    if years_elapsed >= 40:
                        if ltv_standard > 60:
                            old_ltv = ltv_standard
                            ltv_standard = 60.0
                            reasons.append(f"⚠️ 40년 이상 노후주택 ({years_elapsed}년) → 60% 제한 ({old_ltv}% → 60%)")
                        else:
                            reasons.append(f"40년 이상 노후주택 ({years_elapsed}년, 현재 LTV는 60% 이하)")
                    else:
                        reasons.append(f"준공연도: {completion_year}년 (경과 {years_elapsed}년)")
            except (ValueError, IndexError) as e:
                reasons.append(f"⚠️ 준공일자 파싱 오류: {completion_date}")

        # 6. 현재 LTV 상한선 79% 적용 (임시)
        LTV_MAX_CAP = 79.0
        if ltv_standard > LTV_MAX_CAP:
            reasons.append(f"⚠️ 최종 LTV {ltv_standard}% → 현재 LTV 상한선 {LTV_MAX_CAP}% 적용")
            ltv_standard = LTV_MAX_CAP

        # 최종 LTV 표시
        reasons.append(f"✅ 최종 LTV: {ltv_standard}%")

        return {'ltv': ltv_standard, 'reasons': reasons, 'error': None}
    except Exception as e:
        logger.error(f"LTV 자동 계산 중 오류 (주소: {address}, 면적: {area}): {e}")
        return {'ltv': None, 'reasons': reasons, 'error': str(e)}

def _to_customer_rate(cost_rate):
    """질권사 원가금리 + 마진 4% → 고객 최소 적용금리 (X.9% 올림)"""
    return int(cost_rate + 4) + 0.9

def get_hope_collateral_interest_rate(region, ltv_rate, region_grade=None, is_meritz=False, property_type='', is_senior=True):
    """
    질권사 원가금리 + 마진 4% 기준으로 최소금리를 계산하고,
    최소금리부터 14.9%까지 선택 가능한 금리 목록 반환
    """
    if not ltv_rate:
        return None

    try:
        ltv = float(ltv_rate)
    except (ValueError, TypeError):
        return None

    ALL_RATES = [10.9, 11.9, 12.9, 13.9, 14.9]

    if is_meritz:
        # 메리츠 원가금리 (2026.03 기준)
        is_apt = '아파트' in property_type or '주상복합' in property_type
        if is_apt:
            if ltv <= 75:
                cost = 6.70
            elif ltv <= 85:
                cost = 7.70
            else:
                cost = 9.20
        else:
            if ltv <= 75:
                cost = 8.90
            elif ltv <= 85:
                cost = 9.90
            else:
                cost = 11.40
    else:
        # 아이엠 기본금리 (2026.06.15 기준 — 인상: 7.0/7.2/7.6 → 7.3/7.5/7.9)
        if is_senior:
            cost = 7.3 if ltv <= 70 else None
        else:
            if ltv <= 70:
                cost = 7.3
            elif ltv <= 75:
                cost = 7.5
            elif ltv <= 80:
                cost = 7.9
            else:
                cost = None

        if cost is None:
            return None

    min_rate = _to_customer_rate(cost)
    available = [r for r in ALL_RATES if r >= min_rate]
    if not available:
        return f"{min_rate:.1f}% 선택"
    return " / ".join(f"{r:.1f}%" for r in available) + " 선택"

def _generate_memo_header(inputs):
    """메모의 헤더 부분(소유자, 주소, 면적, 시세 정보)을 생성합니다."""
    memo_lines = []
    
    # 고객명
    customer_name = inputs.get('customer_name', '')
    if customer_name.strip():
        memo_lines.append(f"소유자: {customer_name}")

    # 주소와 면적
    address = inputs.get('address', '')
    area_str = f"면적: {inputs.get('area', '')}" if inputs.get('area') else ""
    address_area_parts = []
    if address.strip(): address_area_parts.append(f"주소: {address}")
    if area_str: address_area_parts.append(area_str)
    if address_area_parts: memo_lines.append(" | ".join(address_area_parts))

    # KB시세, 시세적용, 방공제
    kb_price_raw = inputs.get('kb_price', '')
    kb_price_val = parse_korean_number(kb_price_raw)
    kb_price_str = f"KB시세: {format_manwon(kb_price_val)}" if kb_price_val > 0 else ""
    
    deduction_amount_raw = inputs.get('deduction_amount', '')
    deduction_amount_val = parse_korean_number(deduction_amount_raw)
    deduction_region_text = inputs.get('deduction_region_text', '')
    deduction_str = ""
    if deduction_amount_val > 0 and deduction_region_text and deduction_region_text.strip() and deduction_region_text != "지역 선택...":
        deduction_str = f"방공제: {format_manwon(deduction_amount_val)}"

    price_info_parts = []
    if kb_price_str: price_info_parts.append(kb_price_str)
    
    property_type = inputs.get('property_type', '')
    price_type = get_price_type_from_address(address, property_type)
    if price_type: price_info_parts.append(price_type)
    if deduction_str: price_info_parts.append(deduction_str)
    if price_info_parts: memo_lines.append(" | ".join(price_info_parts))

    return memo_lines, kb_price_val, deduction_amount_val

def generate_memo(data):
    """텍스트 메모 생성 함수"""
    try:
        inputs = data.get('inputs', {})
        loans = data.get('loans', [])
        fees = data.get('fees', {})
        
        # 시세 정보 추출
        kb_price_raw = inputs.get('kb_price', '')
        kb_price_val = parse_korean_number(kb_price_raw)
        kb_price_str = f"KB시세: {format_manwon(kb_price_val)}" if kb_price_val > 0 else ""
        # 1. 헤더 정보 생성 (리팩토링된 함수 호출)
        memo_lines, kb_price_val, deduction_amount_val = _generate_memo_header(inputs)
        
        # 방공제 정보 처리
        deduction_amount_raw = inputs.get('deduction_amount', '')
        deduction_amount_val = parse_korean_number(deduction_amount_raw)
        deduction_region_text = inputs.get('deduction_region_text', '')
        deduction_str = ""
        if deduction_amount_val > 0 and deduction_region_text:
            if deduction_region_text.strip() and deduction_region_text != "지역 선택...":
                deduction_str = f"방공제: {format_manwon(deduction_amount_val)}"
        
        # 면적 정보 처리
        area_str = f"면적: {inputs.get('area', '')}" if inputs.get('area') else ""
        
        # 기본 정보 라인 생성
        memo_lines = []
        
        # 고객명 정보 추가 (메모 맨 위에 표시)
        customer_name = inputs.get('customer_name', '')
        if customer_name.strip():
            memo_lines.append(f"소유자: {customer_name}")
        
        # 주소, 물건유형, 면적을 한 줄에 표시
        address = inputs.get('address', '')
        address_area_parts = []
        if address.strip():
            address_area_parts.append(f"주소: {address}")

        # 물건유형 추가
        property_type = inputs.get('property_type', '')
        if property_type and property_type.strip():
            address_area_parts.append(property_type)

        # LTV 계산용 물건유형 분류 (APT/Non-APT)
        APT_TYPES = ['아파트', 'APT']
        property_type_for_ltv = 'APT' if any(t in property_type for t in APT_TYPES) else 'Non-APT'

        # 세대수 100 미만 APT는 Non-APT 기준 적용 (팝업과 동일 로직)
        unit_count_raw = inputs.get('unit_count', '')
        try:
            unit_count_val = int(str(unit_count_raw).replace(',', '').strip()) if unit_count_raw else 0
        except (ValueError, TypeError):
            unit_count_val = 0
        if property_type_for_ltv == 'APT' and 0 < unit_count_val < 100:
            property_type_for_ltv = 'Non-APT'

        if area_str:
            address_area_parts.append(area_str)

        # 세대수 추가
        unit_count = inputs.get('unit_count', '')
        if unit_count:
            try:
                unit_count_val = int(str(unit_count).replace(',', '').strip())
                if unit_count_val > 0:
                    address_area_parts.append(f"세대수: {unit_count_val}")
            except (ValueError, TypeError):
                pass

        # KB시세 정보를 주소 라인에 합치기
        if kb_price_str:
            address_area_parts.append(kb_price_str)

        # 시세적용 정보 추가 (오피스텔이면 층수 무관 하안가, 아파트 등은 층수 기준)
        price_type = get_price_type_from_address(address, property_type)
        if price_type:
            address_area_parts.append(price_type)

        if deduction_str:
            address_area_parts.append(deduction_str)

        if address_area_parts:
            memo_lines.append(" | ".join(address_area_parts))

        # 기본 정보와 대출 정보 사이에 빈 줄 추가
        if memo_lines:
            memo_lines.append("")

        valid_loans = []
        if loans and isinstance(loans, list):
            valid_loans = [l for l in loans if isinstance(l, dict) and (parse_korean_number(l.get('max_amount', '0')) > 0 or parse_korean_number(l.get('principal', '0')) > 0)]
            loan_memo = []
            for i, item in enumerate(valid_loans, 1):
                # 설정일자, 설정자, 채무자, 설정금액, 비율, 원금, 구분 순서로 표시
                setup_date = item.get('setup_date', '')
                lender = item.get('lender', '/')
                debtor = item.get('debtor', '')
                max_amount = format_manwon(item.get('max_amount', '0'))
                ratio = item.get('ratio', '')
                ratio_str = f"{ratio}%" if ratio and ratio != '/' else '/'
                principal = format_manwon(item.get('principal', '0'))
                status = item.get('status', '/')
                rank = item.get('rank', '') or str(i)

                # 포맷: 3. 2015-06-30 | 신한은행 | 홍길동 | 채권최고액: 1,000만 | 120% | 원금: 833만 | 유지
                parts = [f"{rank}."]
                if setup_date:
                    parts.append(setup_date)
                parts.append(lender)
                if debtor:
                    parts.append(debtor)
                parts.append(f"채권최고액: {max_amount}")
                parts.append(ratio_str)
                parts.append(f"원금: {principal}")
                parts.append(status)
                loan_memo.append(" | ".join(parts))
            if loan_memo:
                memo_lines.extend(loan_memo)
                memo_lines.append("")

        # --- ▼▼▼ LTV 계산 로직 (메리츠/아이엠/기본값) ▼▼▼ ---
        ltv_results = []
        ltv_lines_exist = False

        # 대출 상태 분석 (선순위/후순위 판단)
        maintain_sum, replace_sum, exit_sum, principal_sum = 0, 0, 0, 0

        for item in valid_loans:
            status = item.get('status', '').strip()
            principal = parse_korean_number(item.get('principal', '0'))
            max_amount = parse_korean_number(item.get('max_amount', '0'))

            if status in ['유지', '동의', '비동의']:
                maintain_sum += max_amount if max_amount > 0 else principal
            elif status == '대환':
                replace_sum += principal
            elif status == '선말소':
                replace_sum += principal
            elif status == '퇴거자금':
                exit_sum += principal

        principal_sum = replace_sum + exit_sum
        is_senior = maintain_sum == 0  # 유지 채권이 없으면 선순위
        loan_type = "선순위" if is_senior else "후순위"

        # 체크박스 상태 확인
        hope_collateral_checked = inputs.get('hope_collateral_checked', False)
        meritz_collateral_checked = inputs.get('meritz_collateral_checked', False)

        # 자동 LTV 계산 (메리츠 또는 아이엠 기준)
        auto_ltv = None
        auto_source = None

        if kb_price_val > 0:
            # ✅ 케이스 1: 메리츠 체크 → 메리츠 기준 (주소+면적 기반)
            if meritz_collateral_checked:
                area = inputs.get('area', '')
                # 면적은 소수점을 포함한 float로 파싱 (㎡ 단위 제거 후 변환)
                try:
                    area_val = float(str(area).replace("㎡", "").replace(",", "").strip()) if area else None
                except (ValueError, TypeError):
                    area_val = None

                # 준공일자 가져오기
                completion_date = inputs.get('completion_date', '')

                auto_ltv = auto_calculate_ltv(address, area_val, is_senior, kb_price=kb_price_val, property_type=property_type_for_ltv, completion_date=completion_date)
                auto_source = "메리츠 기준"

                if auto_ltv is not None:
                    region_grade = get_region_grade(address, is_meritz_pledge=True)

            # ✅ 케이스 2: 아이엠 체크 → 아이엠 기준 (서울/경기/인천만 진행, 선후순위 구분)
            elif hope_collateral_checked:
                region = get_region_from_address(address)
                if region in ['서울', '경기', '인천']:
                    # 선순위: 70% 자동 설정
                    # 후순위: 자동값 없음 (사용자가 수동으로 70%, 75%, 80% 조정)
                    if is_senior:
                        auto_ltv = 70
                        auto_source = "아이엠 기준 (선순위)"
                    else:
                        # 후순위는 자동 LTV 없음 - 사용자 입력만 사용
                        auto_ltv = None
                        auto_source = None
                else:
                    # 서울/경기/인천 외 지역은 아이엠 질권 취급 안함
                    auto_ltv = None
                    auto_source = None

        # 자동 계산된 LTV 추가
        if auto_ltv is not None:
            limit, available = calculate_ltv_limit(kb_price_val, deduction_amount_val, principal_sum, maintain_sum, auto_ltv, is_senior)
            ltv_results.append({
                'loan_type': loan_type,
                'ltv_rate': auto_ltv,
                'limit': limit,
                'available': available,
                'auto_calculated': True,
                'source': auto_source
            })

        # 사용자 입력 LTV가 있으면 함께 처리 — 메리츠 체크 + 자동계산 성공 시 무시
        ltv1_raw = inputs.get('ltv_rates', [None])[0] if isinstance(inputs.get('ltv_rates'), list) and len(inputs.get('ltv_rates', [])) > 0 else None

        # 명확한 검증: 빈 문자열이나 None 제외
        meritz_auto_success = meritz_collateral_checked and auto_ltv is not None
        if ltv1_raw is not None and not meritz_auto_success:
            ltv_str = str(ltv1_raw).strip()
            if ltv_str and ltv_str != "":
                try:
                    user_ltv = float(ltv_str)
                    if user_ltv > 0 and user_ltv != auto_ltv:  # 자동값과 다를 때만 추가
                        limit, available = calculate_ltv_limit(kb_price_val, deduction_amount_val, principal_sum, maintain_sum, user_ltv, is_senior)
                        ltv_results.append({
                            'loan_type': loan_type,
                            'ltv_rate': user_ltv,
                            'limit': limit,
                            'available': available,
                            'auto_calculated': False,
                            'source': '사용자 입력'
                        })
                except (ValueError, TypeError):
                    pass
        # --- ▲▲▲ LTV 계산 완료 ▲▲▲ ---

        # ✅ [신규] 필요금액이 입력되면 한도 대신 필요금액 사용
        required_amount_raw = inputs.get('required_amount', '')
        required_amount_val = parse_korean_number(required_amount_raw) if required_amount_raw else 0

        if ltv_results and isinstance(ltv_results, list):
            ltv_memo = []
            for res in ltv_results:
                if isinstance(res, dict):
                    loan_type = res.get('loan_type', '기타')
                    ltv_rate = int(res.get('ltv_rate', 0)) if res.get('ltv_rate', 0) else '/'
                    limit = res.get('limit', 0)
                    available = res.get('available', 0)

                    # ✅ [핵심] 필요금액이 입력되면 한도/가용/LTV 역산값으로 덮어쓰기
                    if required_amount_val > 0:
                        limit = required_amount_val
                        available = required_amount_val - principal_sum
                        from utils import calculate_ltv_from_required_amount
                        ltv_rate = calculate_ltv_from_required_amount(kb_price_val, required_amount_val, valid_loans, deduction_amount_val)

                    # 기본 LTV 한도 메시지 생성 (메리츠 체크 시 급지 정보 앞에 붙임)
                    if meritz_collateral_checked and auto_ltv is not None:
                        ltv_line = f"급지: {region_grade} {loan_type} 한도: LTV {ltv_rate}% {format_manwon(limit)} 가용 {format_manwon(available)}"
                    else:
                        ltv_line = f"{loan_type} 한도: LTV {ltv_rate}% {format_manwon(limit)} 가용 {format_manwon(available)}"

                    # 아이엠 또는 메리츠 질권 체크 시 적용 금리 추가
                    if hope_collateral_checked or meritz_collateral_checked:
                        _property_type = inputs.get('property_type', '')
                        interest_rate = get_hope_collateral_interest_rate(
                            region=None,
                            ltv_rate=ltv_rate,
                            is_meritz=meritz_collateral_checked,
                            property_type=_property_type,
                            is_senior=is_senior
                        )
                        if interest_rate:
                            ltv_line += f"\n적용 금리 (연이율) {interest_rate}"

                    # 메리츠 질권 체크 + 10억 초과 시 경고 추가 (선순위/후순위 모두)
                    if meritz_collateral_checked and limit > 100000:
                        ltv_line += " 이나 10억 초과 메리츠 질권 진행불가"

                    ltv_memo.append(ltv_line)

            if ltv_memo:
                memo_lines.extend(ltv_memo)
                memo_lines.append("")  # ✅ LTV 한도 뒤에 빈 줄 추가
                ltv_lines_exist = True
        
        # 수수료 계산
        try:
            consult_amt = parse_korean_number(fees.get('consult_amt', '0') or 0)
            bridge_amt = parse_korean_number(fees.get('bridge_amt', '0') or 0)
            
            if consult_amt > 0 or bridge_amt > 0:
                fee_memo = []
                consult_rate = float(fees.get('consult_rate', '0') or 0)
                consult_fee = int(consult_amt * consult_rate / 100)
                bridge_rate = float(fees.get('bridge_rate', '0.7') or 0.7)
                bridge_fee = int(bridge_amt * bridge_rate / 100)
                
                # 수수료 정보 전에 구분선 추가
                memo_lines.append("-----------------------")
                
                # 수수료 정보 추가
                if consult_amt > 0: 
                    fee_memo.append(f"필요금: {format_manwon(consult_amt)} 컨설팅비용:({str(consult_rate) + '%' if consult_rate else '/'}) {format_manwon(consult_fee)}")
                if bridge_amt > 0: 
                    fee_memo.append(f"브릿지: {format_manwon(bridge_amt)} 브릿지비용:({str(bridge_rate) + '%' if bridge_rate else '/'}) {format_manwon(bridge_fee)}")
                
                if fee_memo:
                    memo_lines.extend(fee_memo)
                    
                # 총 컨설팅 합계 추가
                total_fee = consult_fee + bridge_fee
                if total_fee > 0:
                    memo_lines.append(f"총 컨설팅 합계: {format_manwon(total_fee)}")
                    
        except Exception as e:
            logger.warning(f"수수료 계산 중 오류 (무시됨): {e}")

        # ✨ 아이엠/메리츠 질권적용 로직 (둘 다 금리 적용)
        hope_collateral_checked = inputs.get('hope_collateral_checked', False)
        meritz_collateral_checked = inputs.get('meritz_collateral_checked', False)

        # 시세 타입 결정 및 반환 - 층수 기준으로 변경
        # ✨ 아이엠질권적용 또는 메리츠질권적용 시 고정 텍스트 추가 (맨 하단)
        if hope_collateral_checked or meritz_collateral_checked:
            memo_lines.append("*본심사시 한도, 금리 변동될수 있습니다.")
            memo_lines.append("*사업자 담보대출 (사업자필수)")
            memo_lines.append("*중도 3%")
            memo_lines.append("*연체이력 및 권리침해사항 1% 할증")

            # 즉발사업자 정보 추가 (질권 체크 시에만)
            instant_business_checked = inputs.get('instant_business_operator', False)
            if instant_business_checked:
                business_reg_date = inputs.get('business_registration_date', '')
                loan_available_date = inputs.get('loan_available_date', '')
                if business_reg_date and loan_available_date:
                    memo_lines.append(f"*즉발 사업자등록일: {business_reg_date} | 대출가능일: {loan_available_date}")

        memo_text = "\n".join(memo_lines)
        price_type = ""
        
        # 주소에서 층수 추출 (제X층 또는 X층 패턴) - 주소가 있을 때만 실행
        address = inputs.get('address', '')
        if address and address.strip():  # 주소가 비어있지 않을 때만 처리
            floor_match = re.search(r'(?:제)?(\d+)층', address)
            
            if floor_match:
                floor = int(floor_match.group(1))
                if floor <= 2:
                    price_type = "하안가 적용"
                else:
                    price_type = "일반가 적용"
            else:
                price_type = ""  # 층수를 찾을 수 없으면 비워둠
        else:
            price_type = ""  # 주소가 없으면 시세적용 표시 안함
        property_type = inputs.get('property_type', '')
        price_type = get_price_type_from_address(address, property_type)

        return {
            'memo': memo_text,
            'price_type': price_type,
            'ltv_results': ltv_results
        }
        
    except Exception as e:
        logger.error(f"메모 생성 중 오류: {e}", exc_info=True)
        return {
            'memo': f"메모 생성 중 오류가 발생했습니다: {str(e)}",
            'price_type': "",
            'ltv_results': []
        }
    

def get_price_type_from_address(address, property_type=""):
    """주소 문자열에서 층수를 분석하여 시세 적용 타입을 반환합니다."""
    # 오피스텔이면 층수 무관 하안가
    if property_type and '오피스텔' in property_type:
        return "하안가 적용"

    if not address or not address.strip():
        return ""

    floor_match = re.search(r'(?:제)?(\d+)층', address)
    if not floor_match:
        return ""

    try:
        floor = int(floor_match.group(1))
        return "하안가 적용" if floor <= 2 else "일반가 적용"
    except (ValueError, IndexError):
        return ""

@app.route('/api/generate_text_memo', methods=['POST'])
def generate_text_memo_route():
    data = request.get_json() or {}
    result = generate_memo(data)
    return jsonify(result)

@app.route('/api/convert_loan_amount', methods=['POST'])
def convert_loan_amount_route():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "잘못된 요청 데이터"}), 400
        converted_data = auto_convert_loan_amounts(data)
        return jsonify({"success": True, "converted_data": converted_data})
    except Exception as e:
        logger.error(f"대출 금액 변환 중 오류: {e}")
        return jsonify({"error": "금액 변환 중 오류가 발생했습니다."}), 500

@app.route('/api/auto_calculate_ltv', methods=['POST'])
def auto_calculate_ltv_route():
    """
    메리츠캐피탈 기준으로 주소와 면적에서 자동 LTV 계산
    (선순위/후순위는 메모 생성 시 근저당권 정보로 자동 판단)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400

        address = data.get('address', '').strip()
        area = data.get('area', None)
        is_senior = data.get('is_senior', True)  # 클라이언트에서 전달받은 선순위/후순위 정보
        kb_price_raw = data.get('kb_price', '')  # 클라이언트에서 전달받은 KB 시세
        property_type = data.get('property_type', 'APT')  # 클라이언트에서 전달받은 물건유형

        if not address or not area:
            return jsonify({"error": "주소와 면적이 필요합니다."}), 400

        try:
            area_val = float(area) if area else None
        except (ValueError, TypeError):
            area_val = parse_korean_number(area)

        # KB 시세 변환
        kb_price_val = None
        if kb_price_raw:
            try:
                kb_price_val = int(float(kb_price_raw)) if isinstance(kb_price_raw, str) else int(kb_price_raw)
            except (ValueError, TypeError):
                kb_price_val = parse_korean_number(kb_price_raw)

        # 준공일자 가져오기
        completion_date = data.get('completion_date', '')

        # 자동 LTV 계산 (사유 포함)
        result = auto_calculate_ltv_with_reasons(
            address,
            area_val,
            is_senior=is_senior,
            kb_price=kb_price_val,
            property_type=property_type,
            completion_date=completion_date
        )

        # 오류 처리
        if result['ltv'] is None or result['error']:
            region_grade = get_region_grade(address, is_meritz_pledge=True)
            return jsonify({
                "success": False,
                "error": result['error'] or "LTV 계산 실패",
                "reasons": result['reasons'],
                "address": address,
                "region_grade": region_grade,
                "property_type": property_type,
                "area": area_val
            }), 200

        # 추가 정보
        region_grade = get_region_grade(address, is_meritz_pledge=True)
        return jsonify({
            "success": True,
            "auto_ltv": result['ltv'],
            "reasons": result['reasons'],
            "region_grade": region_grade,
            "is_senior": is_senior,
            "address": address,
            "area": area_val
        })

    except Exception as e:
        logger.error(f"자동 LTV 계산 중 오류: {e}")
        return jsonify({"error": f"계산 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/api/calculate_principal', methods=['POST'])
def calculate_principal_route():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "잘못된 요청 데이터"}), 400
        max_amount = data.get('max_amount', 0)
        ratio = data.get('ratio', 100)
        principal = calculate_principal_from_ratio(max_amount, ratio)
        return jsonify({"success": True, "principal": principal})
    except Exception as e:
        logger.error(f"원금 계산 중 오류: {e}")
        return jsonify({"error": "원금 계산 중 오류가 발생했습니다."}), 500

@app.route('/api/calculate_ltv_from_required_amount', methods=['POST'])
def calculate_ltv_from_required_amount_route():
    """
    필요금액으로부터 LTV를 역산하는 API

    요청 데이터:
    {
        "kb_price": 5000,
        "required_amount": 800,
        "loans": [
            {"max_amount": 2000, "status": "유지"},
            {"max_amount": 1000, "status": "선말소"}
        ],
        "deduction_amount": 0
    }

    응답:
    {
        "ltv": 76,
        "success": true
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400

        # 요청 데이터 파싱
        kb_price = parse_korean_number(data.get('kb_price', '0'))
        required_amount = parse_korean_number(data.get('required_amount', '0'))
        loans = data.get('loans', [])
        deduction_amount = parse_korean_number(data.get('deduction_amount', '0'))

        # utils.py의 함수 호출
        from utils import calculate_ltv_from_required_amount
        calculated_ltv = calculate_ltv_from_required_amount(
            kb_price,
            required_amount,
            loans,
            deduction_amount
        )

        return jsonify({
            "success": True,
            "ltv": calculated_ltv
        })
    except Exception as e:
        logger.error(f"LTV 역산 계산 중 오류: {e}")
        return jsonify({"error": "LTV 계산 중 오류가 발생했습니다."}), 500

KAKAO_API_KEY = "7105bf011f69bc4cb521ec9b1ea496e0"
KAKAO_HEADERS = {'Authorization': f'KakaoAK {KAKAO_API_KEY}'}

@app.route('/api/convert-to-road-address', methods=['POST'])
def convert_to_road_address():
    """지번 주소를 도로명 주소로 변환 (카카오 로컬 API 사용)"""
    try:
        data = request.get_json()
        address = data.get('address', '').strip()

        if not address:
            return jsonify({"success": False, "error": "주소가 입력되지 않았습니다"}), 400

        logger.info(f"[도로명 변환] 원본: {address}")

        # 건물 동번호/호수 추출 — 법정동(작전동, 행신동)과 구분하여 숫자동/영문자동만 추출
        dong_ho_match = re.search(r'제?(\d+)동.*?제?(\d+)층\s*제?(\d+)호', address)
        if not dong_ho_match:
            dong_ho_match = re.search(r'제([가-나라마바사아자차카타파하])동.*?제?(\d+)층\s*제?(\d+)호', address)
        if not dong_ho_match:
            dong_ho_match = re.search(r'제?(\d+)동.*?제?(\d+)호', address)
        if not dong_ho_match:
            dong_ho_match = re.search(r'제([가-나라마바사아자차카타파하])동.*?제?(\d+)호', address)
        floor_ho_match = None
        if not dong_ho_match:
            floor_ho_match = re.search(r'제?(\d+)층\s*제?(\d+)호', address)

        dong_num = ho_num = None
        if dong_ho_match:
            dong_num = dong_ho_match.group(1)
            if dong_ho_match.lastindex >= 3:
                ho_num = dong_ho_match.group(3)
            else:
                ho_num = dong_ho_match.group(2)
        elif floor_ho_match:
            ho_num = floor_ho_match.group(2)

        # 지번 부분만 추출 (건물명/동호수 제외)
        jibun_match = re.search(r'^(.*?[동읍면리가로](?:\d가)?\s*\d+(?:-\d+)?)', address)
        jibun_addr = jibun_match.group(1).strip() if jibun_match else address

        # 건물명 추출 (지번 뒤 ~ 동/층/호수 앞)
        building_name = ''
        bm = re.search(r'[동읍면리가로]\s*\d+(?:-\d+)?\s+(.+?)\s+제?\d+동', address)
        if not bm:
            bm = re.search(r'[동읍면리가로]\s*\d+(?:-\d+)?\s+(.+?)\s+제?\d+층', address)
        if bm:
            building_name = bm.group(1).strip()
        logger.info(f"[도로명 변환] 지번: {jibun_addr}, 건물명: {building_name}")

        road_addr = None
        road_addr_fallback = None
        matched_building = ''
        matched_dong = ''
        fallback_building = ''
        fallback_dong = ''

        # 1단계: 카카오 주소검색으로 지번 검색
        r1 = requests.get('https://dapi.kakao.com/v2/local/search/address.json',
            headers=KAKAO_HEADERS, params={'query': jibun_addr}, timeout=5)
        if r1.status_code == 200:
            docs = r1.json().get('documents', [])
            if docs:
                doc = docs[0]
                ra = doc.get('road_address')
                if ra:
                    kakao_building = ra.get('building_name', '').replace(' ', '').lower()
                    bn_norm = building_name.replace(' ', '').lower()
                    road_addr_fallback = ra.get('address_name', '')
                    fallback_building = ra.get('building_name', '')
                    fallback_dong = ra.get('region_3depth_name', '')
                    # 건물명 일치하거나 건물명 없는 경우 바로 사용
                    if not building_name or bn_norm in kakao_building or kakao_building in bn_norm:
                        road_addr = road_addr_fallback
                        matched_building = ra.get('building_name', '')
                        matched_dong = ra.get('region_3depth_name', '')
                        logger.info(f"[도로명 변환] 1단계 성공: {road_addr}")

        # 2단계: 건물명 + 동명으로 키워드 검색 (번지 제외 — 포함 시 0건)
        if not road_addr and building_name:
            # 번지 숫자만 추출 (지번 매칭용)
            jibun_no_match = re.search(r'\s(\d+(?:-\d+)?)$', jibun_addr)
            jibun_no = jibun_no_match.group(1) if jibun_no_match else ''
            # 동명까지만 추출 (번지 제외)
            dong_only_match = re.search(r'^(.*?[동읍면리가로](?:\d가)?)\s*\d', jibun_addr)
            dong_only = dong_only_match.group(1).strip() if dong_only_match else jibun_addr

            r2 = requests.get('https://dapi.kakao.com/v2/local/search/keyword.json',
                headers=KAKAO_HEADERS, params={'query': f'{building_name} {dong_only}'}, timeout=5)
            if r2.status_code == 200:
                docs2 = r2.json().get('documents', [])
                bn_norm = building_name.replace(' ', '').lower()
                # 단지/차수 제거 후 건물 타입 분리 (예: "뉴서울아파트" → base="뉴서울", btype="아파트")
                core = re.sub(r'\d+단지|\d+차', '', bn_norm).strip()
                btype_match = re.search(r'(아파트|오피스텔|빌라|연립|다세대|주상복합|타워|맨션|빌딩)$', core)
                btype = btype_match.group(1) if btype_match else ''
                base = core.replace(btype, '').strip() if btype else core

                def name_similar(place):
                    # 완전 포함
                    if core in place or place in core:
                        return True
                    # base + btype 각각 포함 (중간에 1차/2차 등이 끼어있어도 매칭)
                    if base and base in place and (not btype or btype in place):
                        return True
                    return False

                for doc in docs2:
                    place = doc.get('place_name', '').replace(' ', '').lower()
                    addr_name = doc.get('address_name', '')
                    road_name = doc.get('road_address_name', '')
                    jibun_ok = jibun_no and jibun_no in addr_name
                    name_ok = name_similar(place)
                    if road_name and jibun_ok and name_ok:
                        road_addr = road_name
                        matched_building = doc.get('place_name', '')
                        # 도로명으로 재검색해서 법정동과 정확한 건물명 보완
                        r3 = requests.get('https://dapi.kakao.com/v2/local/search/address.json',
                            headers=KAKAO_HEADERS, params={'query': road_name}, timeout=5)
                        r3_docs = r3.json().get('documents', [])
                        if r3_docs:
                            r3_ra = r3_docs[0].get('road_address', {})
                            matched_dong = r3_ra.get('region_3depth_name', '')
                            if r3_ra.get('building_name'):
                                matched_building = r3_ra.get('building_name', '')
                        logger.info(f"[도로명 변환] 2단계 성공: {road_addr} ({matched_dong}, {matched_building})")
                        break
        # 2단계 지번 매칭 실패 시 → 1단계 fallback 우선, 없으면 2단계 건물명 매칭
        if not road_addr and road_addr_fallback:
            road_addr = road_addr_fallback
            matched_building = fallback_building
            matched_dong = fallback_dong
            logger.info(f"[도로명 변환] 1단계 fallback 사용: {road_addr}")
        elif not road_addr and building_name:
            # 2단계 결과에서 건물명만 일치하는 첫 번째 결과 사용 (1단계도 없는 경우)
            for doc in docs2:
                place = doc.get('place_name', '').replace(' ', '').lower()
                road_name = doc.get('road_address_name', '')
                if road_name and name_similar(place):
                    road_addr = road_name
                    # 도로명으로 재검색해서 법정동과 정확한 건물명 보완
                    r3b = requests.get('https://dapi.kakao.com/v2/local/search/address.json',
                        headers=KAKAO_HEADERS, params={'query': road_name}, timeout=5)
                    r3b_docs = r3b.json().get('documents', [])
                    if r3b_docs:
                        r3b_ra = r3b_docs[0].get('road_address', {})
                        matched_dong = r3b_ra.get('region_3depth_name', '')
                        matched_building = r3b_ra.get('building_name', '') or doc.get('place_name', '')
                    else:
                        matched_building = doc.get('place_name', '')
                    logger.info(f"[도로명 변환] 2단계 건물명 fallback: {road_addr} ({matched_dong}, {matched_building})")
                    break
            logger.info(f"[도로명 변환] 1단계 fallback 사용: {road_addr}")

        if road_addr:
            # 카카오 API 도 약칭 → 풀네임 변환
            sido_map = {
                '경기 ': '경기도 ', '강원 ': '강원도 ', '충북 ': '충청북도 ', '충남 ': '충청남도 ',
                '전북 ': '전라북도 ', '전남 ': '전라남도 ', '경북 ': '경상북도 ', '경남 ': '경상남도 ', '제주 ': '제주특별자치도 ',
            }
            for abbr, full in sido_map.items():
                if road_addr.startswith(abbr):
                    road_addr = full + road_addr[len(abbr):]
                    break

            # 동/호수 조합
            unit_info = ''
            if dong_num and ho_num:
                unit_info = f"{dong_num}동 {ho_num}호"
            elif ho_num:
                unit_info = f"{ho_num}호"

            # 괄호 내용: (법정동, 건물명) 또는 (건물명) 또는 (법정동)
            bracket_parts = [p for p in [matched_dong, matched_building] if p]
            bracket = f"({', '.join(bracket_parts)})" if bracket_parts else ''

            if unit_info and bracket:
                road_addr = f"{road_addr}, {unit_info} {bracket}"
            elif unit_info:
                road_addr = f"{road_addr}, {unit_info}"
            elif bracket:
                road_addr = f"{road_addr} {bracket}"

            return jsonify({"success": True, "road_address": road_addr, "original_address": address})
        else:
            return jsonify({"success": False, "error": "도로명 주소를 찾을 수 없습니다"})

    except Exception as e:
        logger.error(f"도로명 주소 변환 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/customers')
def get_customers():
    try:
        customers = fetch_all_customers()
        if customers is None:
            return jsonify([])
        return jsonify(customers)
    except Exception as e:
        logger.error(f"고객 목록 조회 오류: {e}", exc_info=True)
        # 오류가 발생해도 빈 배열을 반환해서 UI가 깨지지 않도록
        return jsonify([]), 200
        
@app.route('/api/customer/<page_id>')
def get_customer_details(page_id):
    try:
        details = fetch_customer_details(page_id)
        return jsonify(details) if details else (jsonify({"error": "Customer not found"}), 404)
    except Exception as e:
        logger.error(f"고객 상세 정보 조회 오류: {e}")
        return jsonify({"error": "고객 정보를 불러올 수 없습니다."}), 500

@app.route('/api/customer/new', methods=['POST'])
def save_new_customer_route():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "잘못된 요청 데이터"}), 400
        return jsonify(create_new_customer(data))
    except Exception as e:
        logger.error(f"새 고객 생성 오류: {e}")
        return jsonify({"error": "고객 생성 중 오류가 발생했습니다."}), 500
        
@app.route('/api/customer/update/<page_id>', methods=['POST'])
def update_customer_route(page_id):
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "잘못된 요청 데이터"}), 400
        return jsonify(update_customer(page_id, data))
    except Exception as e:
        logger.error(f"고객 정보 업데이트 오류: {e}")
        return jsonify({"error": "고객 정보 업데이트 중 오류가 발생했습니다."}), 500

@app.route('/api/customer/delete/<page_id>', methods=['POST'])
def delete_customer_route(page_id):
    try: return jsonify(delete_customer(page_id))
    except Exception as e:
        logger.error(f"고객 삭제 오류: {e}")
        return jsonify({"error": "고객 삭제 중 오류가 발생했습니다."}), 500

@app.route('/api/kb_search', methods=['POST'])
def kb_search():
    """주소로 KB 단지번호 조회 → complex_no 반환"""
    data = request.get_json()
    address = data.get('address', '').strip()
    if not address:
        return jsonify({'success': False, 'complex_no': ''})
    try:
        kb = get_kb_info(address)
        if kb.get('success') and kb.get('complex_no'):
            return jsonify({'success': True, 'complex_no': kb['complex_no']})
    except Exception as e:
        print(f"[KB search] 오류: {e}")
    return jsonify({'success': False, 'complex_no': ''})


@app.route('/api/calculate_individual_share', methods=['POST'])
def calculate_individual_share():
    try:
        data = request.get_json()
        total_value = int(data.get("total_value", 0))
        ltv = float(data.get("ltv", 70))
        loans = data.get("loans", [])
        owners = data.get("owners", [])

        # ✅ 지분대출 조건 확인: 질권이 체크된 경우에만 수도권 1군 지역 제한
        address = data.get("address", "")
        area = data.get("area")  # 면적 정보 추가
        is_collateral_checked = data.get("is_collateral_checked", False)  # 질권 체크 여부

        if is_collateral_checked and address:
            region_grade = get_region_grade(address, is_meritz_pledge=True)
            if region_grade != "1군":
                return jsonify({
                    "success": False,
                    "error": f"질권 적용 시 지분대출은 수도권 1군 지역 아파트만 취급 가능합니다. (현재: {region_grade})"
                }), 400

        maintain_maxamt_sum = 0
        existing_principal = 0
        subordinate_statuses = ["유지", "동의", "비동의"]
        senior_statuses = ["선순위", "대환", "퇴거자금", "선말소"]
        has_subordinate = False
        for loan in loans:
            status = loan.get("status", "").strip()
            max_amt = int(loan.get("max_amount", 0))
            principal = int(loan.get("principal", 0))
            if status in subordinate_statuses:
                maintain_maxamt_sum += max_amt if max_amt else principal
                has_subordinate = True
            elif status in senior_statuses:
                existing_principal += principal
        is_senior = not has_subordinate
        logger.info(f"지분 계산 - 시세: {total_value}만, 주소: {address}, 면적: {area}㎡, LTV: {ltv}%, 후순위차감: {maintain_maxamt_sum}만, 갚을원금: {existing_principal}만, 선순위여부: {is_senior}, 질권체크: {is_collateral_checked}")
        logger.info(f"대출 데이터: {loans}")
        # 질권 체크 시에만 메리츠 기준 적용
        results = calculate_individual_ltv_limits(total_value, owners, ltv, maintain_maxamt_sum, existing_principal, is_senior, address=address, area=area, is_collateral_checked=is_collateral_checked)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error(f"개인별 지분 한도 계산 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

# --- 대출 심사 현황 관리 API ---
@app.route('/api/loan-review-data', methods=['GET'])
def get_loan_review_data():
    """모든 대출 심사 데이터 조회"""
    try:
        records = LoanReviewData.query.all()
        return jsonify([record.to_dict() for record in records])
    except Exception as e:
        logger.error(f"대출 심사 데이터 조회 오류: {e}")
        return jsonify({"success": False, "error": "데이터 조회 실패"}), 500

@app.route('/api/loan-review-data', methods=['POST'])
def create_loan_review_data():
    """새로운 대출 심사 데이터 저장"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "요청 데이터 없음"}), 400

        # 필수 필드 확인
        if not data.get('customerName') or not data.get('phone'):
            return jsonify({"success": False, "error": "고객명과 휴대폰 정보는 필수입니다"}), 400

        # 새 레코드 생성
        record = LoanReviewData.from_dict(data)
        db.session.add(record)
        db.session.commit()

        logger.info(f"새 대출 심사 데이터 저장: {data.get('customerName')}")
        return jsonify({
            "success": True,
            "message": "데이터가 저장되었습니다",
            "id": record.id,
            "data": record.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"대출 심사 데이터 저장 오류: {e}")
        return jsonify({"success": False, "error": "데이터 저장 실패"}), 500

@app.route('/api/loan-review-data/<int:record_id>', methods=['PUT'])
def update_loan_review_data(record_id):
    """대출 심사 데이터 수정"""
    try:
        record = LoanReviewData.query.get(record_id)
        if not record:
            return jsonify({"success": False, "error": "해당 데이터가 없습니다"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "요청 데이터 없음"}), 400

        # 필드 업데이트
        record.customer_name = data.get('customerName', record.customer_name)
        record.phone = data.get('phone', record.phone)
        record.birth_date = data.get('birthDate', record.birth_date)
        record.collateral_value = data.get('collateralValue', record.collateral_value)
        record.loan_amount = data.get('loanAmount', record.loan_amount)
        record.status = data.get('status', record.status)
        record.credit_check_date = data.get('creditCheckDate', record.credit_check_date)
        record.contract_schedule_date = data.get('contractScheduleDate', record.contract_schedule_date)
        record.contract_complete_date = data.get('contractCompleteDate', record.contract_complete_date)
        record.remit_date = data.get('remitDate', record.remit_date)
        record.manager = data.get('manager', record.manager)

        # 히스토리 업데이트
        if 'statusHistory' in data:
            record.status_history = json.dumps(data.get('statusHistory', []))
        if 'memoHistory' in data:
            record.memo_history = json.dumps(data.get('memoHistory', []))

        db.session.commit()

        logger.info(f"대출 심사 데이터 수정: ID {record_id}")
        return jsonify({
            "success": True,
            "message": "데이터가 수정되었습니다",
            "data": record.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"대출 심사 데이터 수정 오류: {e}")
        return jsonify({"success": False, "error": "데이터 수정 실패"}), 500

@app.route('/api/loan-review-data/<int:record_id>', methods=['DELETE'])
def delete_loan_review_data(record_id):
    """대출 심사 데이터 삭제"""
    try:
        record = LoanReviewData.query.get(record_id)
        if not record:
            return jsonify({"success": False, "error": "해당 데이터가 없습니다"}), 404

        db.session.delete(record)
        db.session.commit()

        logger.info(f"대출 심사 데이터 삭제: ID {record_id}")
        return jsonify({
            "success": True,
            "message": "데이터가 삭제되었습니다"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"대출 심사 데이터 삭제 오류: {e}")
        return jsonify({"success": False, "error": "데이터 삭제 실패"}), 500

# --- NICECREDIT 연동 API ---
@app.route('/api/open-nicecredit', methods=['POST'])
def open_nicecredit():
    """NICECREDIT 애플리케이션 실행"""
    try:
        nicecredit_path = r'C:\Program Files (x86)\nexacro\nicecredit\17.1\nexacro.exe'

        # 파일 존재 확인
        if not os.path.exists(nicecredit_path):
            return jsonify({
                "success": False,
                "error": "NICECREDIT 애플리케이션을 찾을 수 없습니다"
            }), 404

        # 별도 스레드에서 NICECREDIT 실행 (응답을 빠르게 반환하기 위함)
        def run_nicecredit():
            try:
                subprocess.Popen(nicecredit_path, shell=False)
                logger.info("NICECREDIT 애플리케이션 실행됨")
            except Exception as e:
                logger.error(f"NICECREDIT 실행 오류: {e}")

        thread = threading.Thread(target=run_nicecredit)
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "message": "NICECREDIT 애플리케이션이 실행되었습니다"
        }), 200
    except Exception as e:
        logger.error(f"NICECREDIT 실행 오류: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"NICECREDIT 실행 중 오류가 발생했습니다: {str(e)}"
        }), 500

# --- Notion 동기화 API ---
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', '')
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')

def sync_to_notion(loan_data):
    """대출 데이터를 Notion에 동기화"""
    try:
        if not NOTION_API_KEY:
            logger.warning("Notion API 키가 설정되지 않았습니다")
            return None

        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        # Notion 페이지 생성/업데이트 데이터
        notion_page = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "고객명": {"title": [{"text": {"content": loan_data.get('customerName', '')}}]},
                "휴대폰": {"rich_text": [{"text": {"content": loan_data.get('phone', '')}}]},
                "생년월일": {"rich_text": [{"text": {"content": loan_data.get('birthDate', '')}}]},
                "담보평가액": {"number": loan_data.get('collateralValue')},
                "신청금액": {"number": loan_data.get('loanAmount')},
                "진행상태": {"status": {"name": loan_data.get('status', '접수')}},
                "신용조회": {"checkbox": loan_data.get('creditCheckDate') == 'yes'},
                "자서예정일": {"date": {"start": loan_data.get('contractScheduleDate')} if loan_data.get('contractScheduleDate') else None},
                "자서완료일": {"date": {"start": loan_data.get('contractCompleteDate')} if loan_data.get('contractCompleteDate') else None},
                "송금일": {"date": {"start": loan_data.get('remitDate')} if loan_data.get('remitDate') else None},
                "담당자": {"rich_text": [{"text": {"content": loan_data.get('manager', '')}}]}
            }
        }

        # None 값 제거
        notion_page["properties"] = {k: v for k, v in notion_page["properties"].items() if v is not None}

        # Notion API 호출
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=notion_page
        )

        if response.status_code == 200:
            logger.info(f"Notion 동기화 성공: {loan_data.get('customerName')}")
            return response.json()
        else:
            logger.error(f"Notion 동기화 실패: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Notion 동기화 오류: {e}", exc_info=True)
        return None

@app.route('/api/sync-loan-to-notion/<int:record_id>', methods=['POST'])
def sync_loan_to_notion(record_id):
    """특정 대출 심사 데이터를 Notion에 동기화"""
    try:
        record = LoanReviewData.query.get(record_id)
        if not record:
            return jsonify({"success": False, "error": "해당 데이터가 없습니다"}), 404

        # 데이터를 Notion으로 동기화
        result = sync_to_notion(record.to_dict())

        if result:
            return jsonify({
                "success": True,
                "message": "Notion 동기화가 완료되었습니다",
                "notion_page_id": result.get('id')
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Notion 동기화에 실패했습니다"
            }), 500
    except Exception as e:
        logger.error(f"Notion 동기화 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sync-all-to-notion', methods=['POST'])
def sync_all_to_notion():
    """모든 대출 심사 데이터를 Notion에 동기화"""
    try:
        records = LoanReviewData.query.all()
        sync_count = 0
        failed_count = 0

        for record in records:
            result = sync_to_notion(record.to_dict())
            if result:
                sync_count += 1
            else:
                failed_count += 1

        return jsonify({
            "success": True,
            "message": f"Notion 동기화 완료: {sync_count}개 성공, {failed_count}개 실패",
            "sync_count": sync_count,
            "failed_count": failed_count
        }), 200
    except Exception as e:
        logger.error(f"전체 Notion 동기화 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
