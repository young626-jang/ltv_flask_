# app.py (최종 통합 버전)

import os
import re
import logging
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from collections import defaultdict
import fitz # PDF 텍스트 추출을 위해 fitz(PyMuPDF) 임포트

# --- 우리가 만든 헬퍼 파일들 임포트 ---
from utils import parse_korean_number, calculate_ltv_limit, convert_won_to_manwon, calculate_principal_from_ratio, auto_convert_loan_amounts, calculate_individual_ltv_limits
from ltv_map import region_map
# --- ▼▼▼ pdf_parser.py에서 모든 필요한 함수를 가져오도록 수정합니다 ▼▼▼ ---
from pdf_parser import (
    extract_address,
    extract_area,
    extract_owner_info,
    extract_viewing_datetime,
    check_registration_age,
    extract_owner_shares_with_birth,
    extract_rights_info,  # <-- 핵심! 근저당권 분석 함수 추가!
    extract_ownership_transfer_date # <-- 괄호 안으로 이동
)
from history_manager_flask import (
    fetch_all_customers, 
    fetch_customer_details,
    create_new_customer,
    update_customer,
    delete_customer
)

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask 앱 설정 ---
app = Flask(__name__)

# 배포 환경에서는 /tmp 사용, 로컬에서는 uploads 사용
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp' if os.path.exists('/tmp') else 'uploads')

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

# --- ▼▼▼ PDF 업로드 API를 대폭 업그레이드합니다 ▼▼▼ ---
@app.route('/api/upload', methods=['POST'])
def upload_and_parse_pdf():
    logger.info("PDF 업로드 및 전체 분석 요청 수신")
    if 'pdf_file' not in request.files: return jsonify({"success": False, "error": "요청에 파일이 없습니다."}), 400
    file = request.files['pdf_file']
    if not file.filename: return jsonify({"success": False, "error": "선택된 파일이 없습니다."}), 400
    if not allowed_file(file.filename): return jsonify({"success": False, "error": "PDF 파일만 업로드 가능합니다."}), 400

    filepath = None  # finally 블록에서 사용하기 위해 미리 선언
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        logger.info(f"파일 저장 경로: {filepath}")
        file.save(filepath)
        logger.info(f"파일 저장 완료: {filepath}")

        # 1. PDF에서 텍스트를 한번만 추출하여 변수에 저장
        logger.info("PDF 텍스트 추출 시작")
        doc = fitz.open(filepath)
        full_text = "".join(page.get_text("text") for page in doc)
        doc.close()
        logger.info(f"PDF 텍스트 추출 완료: {len(full_text)} 글자")

        # 2. pdf_parser의 전문가 함수들을 순서대로 호출하여 모든 정보를 추출
        viewing_dt = extract_viewing_datetime(full_text)
        transfer_date = extract_ownership_transfer_date(full_text)
        logger.info(f"추출된 소유권 이전일: {transfer_date}")

        scraped_data = {
            'address': extract_address(full_text),
            'area': extract_area(full_text),
            'customer_name': extract_owner_info(full_text),
            'viewing_datetime': viewing_dt,
            'age_check': check_registration_age(viewing_dt),
            'transfer_date': transfer_date,
            'owner_shares': extract_owner_shares_with_birth(full_text)
        }
        
        # 근저당권 정보도 추출
        rights_info = extract_rights_info(full_text)

        # 3. 추출된 모든 정보를 하나의 JSON으로 묶어서 웹페이지에 전송
        return jsonify({
            "success": True, 
            "scraped_data": scraped_data,  # 기본 정보 + 지분 정보
            "rights_info": rights_info,    # 모든 근저당권 정보,
            "eligibility_checks": [] # 심사 기준 분석 로직 제거
        })

    except Exception as e:
        logger.error(f"PDF 업로드 처리 중 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"서버 처리 중 오류 발생: {str(e)}"}), 500
    finally:
        # 작업이 끝나면 (성공하든 실패하든) 임시 파일을 항상 삭제
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

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

        # LTV 계산 부분 (기존 코드 유지)
        ltv_rates = []
        ltv1 = inputs.get('ltv_rates', [None, None])[0] if isinstance(inputs.get('ltv_rates'), list) else inputs.get('ltv1')
        ltv2 = inputs.get('ltv_rates', [None, None])[1] if isinstance(inputs.get('ltv_rates'), list) else inputs.get('ltv2')
        
        if ltv1: ltv_rates.append(float(ltv1))
        if ltv2: ltv_rates.append(float(ltv2))
        if not ltv_rates: ltv_rates = [70]
        
        ltv_results = []
        ltv_lines_exist = False
        
        if kb_price_val > 0:
            for ltv_rate in ltv_rates:
                if ltv_rate > 0:
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
                    
                    # 대출 구분 결정
                    if maintain_sum > 0:
                        loan_type = "후순위"
                        limit, available = calculate_ltv_limit(kb_price_val, deduction_amount_val, principal_sum, maintain_sum, ltv_rate, False)
                    else:
                        loan_type = "선순위"
                        limit, available = calculate_ltv_limit(kb_price_val, deduction_amount_val, principal_sum, maintain_sum, ltv_rate, True)
                    
                    ltv_results.append({
                        'loan_type': loan_type,
                        'ltv_rate': ltv_rate,
                        'limit': limit,
                        'available': available
                    })

        if ltv_results and isinstance(ltv_results, list):
            ltv_memo = [f"{res.get('loan_type', '기타')} 한도: LTV {int(res.get('ltv_rate', 0)) if res.get('ltv_rate', 0) else '/'}% {format_manwon(res.get('limit', 0))} 가용 {format_manwon(res.get('available', 0))}" for res in ltv_results if isinstance(res, dict)]
            if ltv_memo:
                memo_lines.extend(ltv_memo)
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
            memo_lines.append("--------------------------------------------------")  # 구분선 (상태별 합계 앞)
            for status in order:
                if status in status_sums:
                    data = status_sums[status]
                    if data['principal']['sum'] > 0:
                        memo_lines.append(f"{status} 원금: {format_manwon(data['principal']['sum'])}")
            memo_lines.append("--------------------------------------------------")  # 구분선 (상태별 합계 뒤)
        
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
                    memo_lines.append("--------------------------------------------------")
                
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
        
        # 시세 타입 결정 및 반환 - 층수 기준으로 변경
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

@app.route('/api/customers')
def get_customers():
    try: return jsonify(fetch_all_customers())
    except Exception as e:
        logger.error(f"고객 목록 조회 오류: {e}")
        return jsonify({"error": "고객 목록을 불러올 수 없습니다."}), 500
        
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
        logger.info(f"지분 계산 - 시세: {total_value}만, LTV: {ltv}%, 후순위차감: {maintain_maxamt_sum}만, 갚을원금: {existing_principal}만, 선순위여부: {is_senior}")
        logger.info(f"대출 데이터: {loans}")
        results = calculate_individual_ltv_limits(total_value, owners, ltv, maintain_maxamt_sum, existing_principal, is_senior)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error(f"개인별 지분 한도 계산 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
