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
from region_ltv_map import get_region_grade, get_ltv_standard, is_caution_region
# --- ▼▼▼ pdf_parser.py에서 모든 필요한 함수를 가져오도록 수정합니다 ▼▼▼ ---
from pdf_parser import (
    extract_address,
    extract_area,
    extract_property_type,
    extract_owner_info,
    extract_viewing_datetime,
    check_registration_age,
    extract_owner_shares_with_birth,
    extract_rights_info,  # 근저당권 분석 함수
    extract_construction_date,  # [신규] 준공일자 추출
    extract_last_transfer_info  # [신규] 최근 소유권 이전 정보
)

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

    # 3. 결과 정리 및 반환 (KB 크롤링 제거 - 별도 API 사용)
    scraped_data = {
        'address': extracted_address,
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

        'owner_shares': extract_owner_shares_with_birth(full_text)
    }

    return jsonify({
        "success": True,
        "scraped_data": scraped_data,
        "rights_info": rights_info
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


def auto_calculate_ltv(address, area, is_senior=True, kb_price=None, property_type="APT"):
    """
    메리츠캐피탈 기준에 따라 주소와 면적으로 자동 LTV 계산

    Args:
        address (str): 주소
        area (float): 면적 (㎡ 단위)
        is_senior (bool): True=선순위, False=후순위
        kb_price (int): KB 시세 (만원 단위, 15억 초과 시 5% 차감 적용)
        property_type (str): 'APT' 또는 'Non-APT'

    Returns:
        float: 자동 계산된 LTV (%), Non-APT 2군/3군 취급불가 시 None
    """
    if not address or not area or area <= 0:
        return None

    try:
        # 1. 주소에서 급지 자동 판단
        region_grade = get_region_grade(address)

        if region_grade == "미분류":
            logger.warning(f"급지 미분류: {address}")
            return None

        # 2. 급지, 물건유형, 면적, 선후순위에 따른 LTV 기준값 조회
        ltv_standard = get_ltv_standard(region_grade, float(area), is_senior, property_type)

        # Non-APT 2군/3군 취급불가
        if ltv_standard is None:
            logger.warning(f"Non-APT {region_grade} 취급불가: {address}")
            return None

        # 3. 유의지역이면 LTV 80% 제한 (APT만)
        if property_type == "APT" and is_caution_region(address) and ltv_standard > 80:
            ltv_standard = 80.0

        # 4. 시세 15억(150000만원) 초과 시 5% 차감
        if kb_price and kb_price > 150000:
            ltv_standard = max(0, ltv_standard - 5.0)  # 음수가 되지 않도록 처리
            logger.info(f"시세 15억 초과 - LTV 5% 차감 적용: {ltv_standard}% (시세: {kb_price}만원)")

        return ltv_standard
    except Exception as e:
        logger.error(f"LTV 자동 계산 중 오류 (주소: {address}, 면적: {area}): {e}")
        return None

def get_hope_collateral_interest_rate(region, ltv_rate):
    """
    희망담보상품(아이엠질권) 금리 기준 (KB시세 아파트)

    지역 및 LTV 기준                                           적용 금리 (연이율)
    예외상품: 서울지역 LTV 70% 미만                          9.9% / 10.9%
    A. 서울지역 LTV 75% 미만                                 10.9% / 11.9%
    B. 서울 LTV 80% 미만 OR 경기/인천 LTV 75% 미만          11.9% / 12.9%
    C. 경기/인천 LTV 80% 미만                               12.9% / 13.9%
    D. 서울/경기/인천 LTV 83% 미만                          13.9% / 14.9%
    """
    if not region or not ltv_rate:
        return None

    try:
        ltv = float(ltv_rate)
    except (ValueError, TypeError):
        return None

    # 예외상품: 서울 LTV 70% 미만 (70% 미포함)
    if region == '서울' and ltv < 70:
        return "9.9% / 10.9%"

    # A: 서울 LTV 75% 미만 (75% 미포함)
    if region == '서울' and ltv < 75:
        return "10.9% / 11.9%"

    # B: 서울 LTV 80% 미만, 경기/인천 LTV 75% 미만
    if (region == '서울' and ltv < 80) or (region in ['경기', '인천'] and ltv < 75):
        return "11.9% / 12.9%"

    # C: 경기/인천 LTV 80% 미만 (80% 미포함)
    if region in ['경기', '인천'] and ltv < 80:
        return "12.9% / 13.9%"

    # D: 서울/경기/인천 LTV 83% 이상 포함 (나머지 모든 경우)
    return "13.9% / 14.9%"

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
    
    price_type = get_price_type_from_address(address)
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
        
        # 주소와 면적을 한 줄에 표시
        address = inputs.get('address', '')
        address_area_parts = []
        if address.strip():
            address_area_parts.append(f"주소: {address}")
        if area_str:
            address_area_parts.append(area_str)
        
        if address_area_parts:
            memo_lines.append(" | ".join(address_area_parts))
        
        # KB시세, 시세적용, 방공제를 한 줄에 표시
        price_info_parts = []
        if kb_price_str:
            price_info_parts.append(kb_price_str)
        
        # 시세적용 정보 추가 (층수 기준)
        price_type = ""
        if address and address.strip():
            floor_match = re.search(r'(?:제)?(\d+)층', address)
            if floor_match:
                floor = int(floor_match.group(1))
                price_type = "하안가 적용" if floor <= 2 else "일반가 적용"
        
        if price_type:
            price_info_parts.append(price_type)
        
        if deduction_str:
            price_info_parts.append(deduction_str)
            
        if price_info_parts:
            memo_lines.append(" | ".join(price_info_parts))
        
        # 기본 정보와 대출 정보 사이에 빈 줄 추가
        if memo_lines:
            memo_lines.append("")

        valid_loans = []
        if loans and isinstance(loans, list):
            valid_loans = [l for l in loans if isinstance(l, dict) and (parse_korean_number(l.get('max_amount', '0')) > 0 or parse_korean_number(l.get('principal', '0')) > 0)]
            loan_memo = [f"{i}. {item.get('lender', '/')} | 설정금액: {format_manwon(item.get('max_amount', '0'))} | {item.get('ratio', '') + '%' if item.get('ratio', '') and item.get('ratio', '') != '/' else '/'} | 원금: {format_manwon(item.get('principal', '0'))} | {item.get('status', '/')}" for i, item in enumerate(valid_loans, 1)]
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
                # 면적은 소수점을 포함한 float로 파싱
                try:
                    area_val = float(str(area).replace(",", "").strip()) if area else None
                except (ValueError, TypeError):
                    area_val = None
                auto_ltv = auto_calculate_ltv(address, area_val, is_senior, kb_price=kb_price_val)
                auto_source = "메리츠 기준"

                if auto_ltv is not None:
                    # 메모에 급지 정보 추가 (메리츠일 때만)
                    region_grade = get_region_grade(address)
                    caution_flag = " (유의지역)" if is_caution_region(address) else ""
                    memo_lines.insert(0, f"급지: {region_grade}{caution_flag} | {loan_type}")
                    memo_lines.insert(1, "")

            # ✅ 케이스 2: 아이엠 체크 → 아이엠 기준 (서울/경기/인천만 진행, 선후순위 구분)
            elif hope_collateral_checked:
                region = get_region_from_address(address)
                if region in ['서울', '경기', '인천']:
                    # 선순위: 70%, 후순위: 80%
                    auto_ltv = 70 if is_senior else 80
                    auto_source = "아이엠 기준"
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

        # 사용자 입력 LTV가 있으면 함께 처리 (비교용)
        ltv1_raw = inputs.get('ltv_rates', [None])[0] if isinstance(inputs.get('ltv_rates'), list) and len(inputs.get('ltv_rates', [])) > 0 else None

        # 명확한 검증: 빈 문자열이나 None 제외
        if ltv1_raw is not None:
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

        if ltv_results and isinstance(ltv_results, list):
            ltv_memo = [f"{res.get('loan_type', '기타')} 한도: LTV {int(res.get('ltv_rate', 0)) if res.get('ltv_rate', 0) else '/'}% {format_manwon(res.get('limit', 0))} 가용 {format_manwon(res.get('available', 0))}" for res in ltv_results if isinstance(res, dict)]
            if ltv_memo:
                memo_lines.extend(ltv_memo)
                memo_lines.append("")  # ✅ LTV 한도 뒤에 빈 줄 추가
                ltv_lines_exist = True
        
        # 상태별 합계 계산
        order = ['선말소', '대환', '퇴거자금']
        status_sums = defaultdict(lambda: defaultdict(lambda: {'sum': 0, 'count': 0}))
        has_status_sum = False
        for item in valid_loans:
            status = item.get('status', '')
            if status in order:
                principal_val = parse_korean_number(item.get('principal', '0'))
                if principal_val > 0:
                    status_sums[status]['principal']['sum'] += principal_val
                    status_sums[status]['principal']['count'] += 1
                    has_status_sum = True
        
        if has_status_sum:
            memo_lines.append("-----------------------")  # 구분선 (상태별 합계 앞)
            for status in order:
                if status in status_sums:
                    data = status_sums[status]
                    if data['principal']['sum'] > 0:
                        memo_lines.append(f"{status} 원금: {format_manwon(data['principal']['sum'])}")
            memo_lines.append("-----------------------")  # 구분선 (상태별 합계 뒤)
        
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
                
                # 수수료 정보 전에 구분선 추가 (상태별 합계가 없는 경우)
                if not has_status_sum:
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

        # ✅ 아이엠 또는 메리츠 질권 체크 시 금리 적용
        if hope_collateral_checked or meritz_collateral_checked:
            # ltv_results에서 가장 높은 LTV (사용자 입력값 우선) 선택
            if ltv_results and len(ltv_results) > 0:
                # 사용자 입력 LTV가 있으면 그걸 사용, 없으면 자동값 사용
                ltv_rate = ltv_results[-1].get('ltv_rate')  # 마지막 항목 (사용자입력이 있으면 그것)

                # 주소에서 지역 추출
                address = inputs.get('address', '')
                region = get_region_from_address(address)

                # 지역과 LTV에 따른 금리 구간 조회
                if region and ltv_rate:
                    interest_rate = get_hope_collateral_interest_rate(region, ltv_rate)
                    if interest_rate:
                        memo_lines.append(f"적용 금리 (연이율) {interest_rate}")
                        memo_lines.append("")  # 빈 줄 추가

        # 시세 타입 결정 및 반환 - 층수 기준으로 변경
        # ✨ 아이엠질권적용 또는 메리츠질권적용 시 고정 텍스트 추가 (맨 하단)
        if hope_collateral_checked or meritz_collateral_checked:
            memo_lines.append("*본심사시 금리 변동될수 있습니다.")
            memo_lines.append("*사업자 담보대출 (사업자필수)")
            memo_lines.append("*계약 2년")
            memo_lines.append("*중도 3%")
            memo_lines.append("*환수 92일이내 50%")
            memo_lines.append("*연체이력 및 권리침해사항 1% 할증")

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
        price_type = get_price_type_from_address(address)
        
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
    

def get_price_type_from_address(address):
    """주소 문자열에서 층수를 분석하여 시세 적용 타입을 반환합니다."""
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

        # 자동 LTV 계산 (클라이언트에서 전달받은 is_senior, KB 시세, 물건유형 사용)
        auto_ltv = auto_calculate_ltv(address, area_val, is_senior=is_senior, kb_price=kb_price_val, property_type=property_type)

        # Non-APT 2군/3군 취급불가 처리
        if auto_ltv is None:
            region_grade = get_region_grade(address)
            if property_type == 'Non-APT' and region_grade in ['2군', '3군']:
                return jsonify({
                    "success": False,
                    "error": f"Non-APT {region_grade} 취급불가",
                    "address": address,
                    "region_grade": region_grade,
                    "property_type": property_type
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "급지를 판단할 수 없습니다.",
                    "address": address,
                "area": area_val
            }), 400

        # 추가 정보
        region_grade = get_region_grade(address)
        is_caution = is_caution_region(address)

        return jsonify({
            "success": True,
            "auto_ltv": auto_ltv,
            "region_grade": region_grade,
            "is_caution_region": is_caution,
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
            region_grade = get_region_grade(address)
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

# ==================== KB 시세 조회 API ====================
@app.route('/get_kb_price', methods=['POST'])
def get_kb_price():
    """
    KB부동산 시세 크롤링 API

    Request JSON:
        {
            "address": "서울특별시 강남구 역삼동",
            "area": 84.95
        }

    Response JSON:
        {
            "success": true,
            "kb_price": 53000,  # 만원 단위
            "msg": "성공"
        }
    """
    try:
        data = request.get_json()
        address = data.get('address', '').strip()
        area = data.get('area', 0)

        if not address:
            return jsonify({
                "success": False,
                "kb_price": 0,
                "msg": "주소가 필요합니다"
            }), 400

        logger.info(f"[KB 시세 조회 요청] 주소: {address}, 면적: {area}㎡")

        # KB 크롤링 실행 (재시도 로직 포함)
        result = get_kb_price_with_retry(address, area, max_retries=2)

        logger.info(f"[KB 시세 조회 결과] {result}")

        return jsonify({
            "success": result['kb_price'] > 0,
            "kb_price": result['kb_price'],
            "msg": result['msg']
        }), 200

    except Exception as e:
        logger.error(f"KB 시세 조회 오류: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "kb_price": 0,
            "msg": f"오류 발생: {str(e)}"
        }), 500

# 데이터베이스 초기화 함수
def init_db():
    """데이터베이스 초기화"""
    with app.app_context():
        db.create_all()
        logger.info("데이터베이스 초기화 완료")

if __name__ == '__main__':
    init_db()  # 앱 시작 시 DB 초기화
    app.run(debug=True, host='localhost', port=5001)
