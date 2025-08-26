import os
import re
import logging
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from collections import defaultdict

# --- 우리가 만든 헬퍼 파일들 임포트 ---
from utils import parse_korean_number, calculate_ltv_limit, convert_won_to_manwon, calculate_principal_from_ratio, auto_convert_loan_amounts, calculate_individual_ltv_limits
from ltv_map import region_map
from pdf_parser import parse_pdf_for_ltv, extract_owner_shares_with_birth
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
app.config.update(
    UPLOAD_FOLDER='uploads',
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB 제한
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
)

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 허용된 파일 확장자
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """파일 확장자 검증"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 템플릿 필터 ---
@app.template_filter()
def format_thousands(value):
    """숫자를 천 단위 콤마로 포맷팅"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value

# --- 에러 핸들러 ---
@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "파일 크기가 너무 큽니다 (최대 16MB)"}), 413

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"success": False, "error": "서버 내부 오류가 발생했습니다"}), 500

# --- 페이지 라우트 ---
@app.route('/')
def main_calculator_page():
    return render_template('entry.html', region_map=region_map)

# --- API 라우트 (upload, view_pdf 등은 이전과 동일) ---
@app.route('/api/upload', methods=['POST'])
def upload_and_parse_pdf():
    logger.info("PDF 업로드 요청 수신")
    try:
        if 'pdf_file' not in request.files: return jsonify({"success": False, "error": "요청에 파일이 없습니다."}), 400
        file = request.files['pdf_file']
        if not file.filename: return jsonify({"success": False, "error": "선택된 파일이 없습니다."}), 400
        if not allowed_file(file.filename): return jsonify({"success": False, "error": "PDF 파일만 업로드 가능합니다."}), 400
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        scraped_data = parse_pdf_for_ltv(filepath)
        owner_shares = extract_owner_shares_with_birth(filepath)
        scraped_data["owner_shares"] = owner_shares
        return jsonify({"success": True, "scraped_data": scraped_data})
    except Exception as e:
        logger.error(f"PDF 업로드 처리 중 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"서버 처리 중 오류 발생: {str(e)}"}), 500

@app.route('/view_pdf/<filename>')
def view_pdf(filename):
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath): return jsonify({"error": "파일을 찾을 수 없습니다."}), 404
    return send_file(filepath, mimetype='application/pdf')

def generate_memo(data):
    """
    하나의 함수로 통합된 메모 생성 로직.
    (후순위 대출 시 구분선 누락 오류 수정)
    """
    try:
        inputs = data.get('inputs', {})
        loans = data.get('loans', [])
        fees = data.get('fees', {})

        def format_manwon(value):
            num_val = parse_korean_number(str(value))
            if isinstance(num_val, (int, float)):
                return f"{num_val:,}만"
            return "0만"

        # --- 1. 계산 로직 (이전과 동일) ---
        address = inputs.get('address', '')
        floor_match = re.findall(r"제(\d+)층", address)
        floor_num = int(floor_match[-1]) if floor_match else None
        price_type = "하안가" if floor_num is not None and floor_num <= 2 else "일반가"
        total_value = parse_korean_number(inputs.get("kb_price", "0"))
        deduction = parse_korean_number(inputs.get("deduction_amount", "0"))
        ltv_rates = [rate for rate in inputs.get('ltv_rates', []) if rate and rate.isdigit()]
        maintain_status = ['유지', '동의', '비동의']
        maintain_maxamt_sum = sum(parse_korean_number(item.get('max_amount', '0')) for item in loans if isinstance(item, dict) and item.get('status') in maintain_status)
        refinance_status = ['대환', '선말소', '퇴거자금']
        sub_principal_sum = sum(parse_korean_number(item.get('principal', '0')) for item in loans if isinstance(item, dict) and item.get('status') in refinance_status)
        is_subordinate = any(isinstance(item, dict) and item.get('status') in maintain_status for item in loans)
        ltv_results = []
        for rate_str in ltv_rates:
            ltv = int(rate_str)
            loan_type_info = "후순위" if is_subordinate else "선순위"
            limit, available = calculate_ltv_limit(total_value, deduction, sub_principal_sum, maintain_maxamt_sum, ltv, is_senior=not is_subordinate)
            ltv_results.append({"ltv_rate": ltv, "limit": limit, "available": available, "loan_type": loan_type_info})

        # --- 2. 텍스트 구성 로직 ---
        # 의미있는 입력이 없으면 빈 메모 반환
        has_meaningful_input = (
            (inputs and (inputs.get('customer_name') or inputs.get('address') or total_value > 0 or deduction > 0)) or
            (loans and any(isinstance(item, dict) and (parse_korean_number(item.get('max_amount', '0')) > 0 or parse_korean_number(item.get('principal', '0')) > 0) for item in loans)) or
            (fees and isinstance(fees, dict) and (parse_korean_number(fees.get('consult_amt', '0')) > 0 or parse_korean_number(fees.get('bridge_amt', '0')) > 0))
        )
        
        if not has_meaningful_input:
            return {"memo": "", "price_type": ""}
        
        memo_lines = []
        ltv_lines_exist = False # LTV 라인이 추가되었는지 확인하기 위한 플래그

        if inputs and (inputs.get('customer_name') or inputs.get('address')):
            memo_lines.append(f"고객명: {inputs.get('customer_name', '')}")
            area_str = f"면적: {inputs.get('area', '')}㎡" if inputs.get('area') else ""
            kb_price_str = ""
            if total_value > 0:
                price_info = f" ({price_type})" if price_type else ""
                kb_price_str = f"KB시세: {format_manwon(total_value)}{price_info}"
            deduction_str = f"방공제: {format_manwon(deduction)}" if deduction > 0 else ""
            address_parts = [inputs.get('address', ''), area_str, kb_price_str, deduction_str]
            full_address_line = " | ".join(part for part in address_parts if part)
            if full_address_line: memo_lines.append(f"주소 : {full_address_line}")
            memo_lines.append("")

        valid_loans = []
        if loans and isinstance(loans, list):
            status_order = {'선말소': 0, '대환': 1}
            valid_loans = [l for l in loans if isinstance(l, dict) and (parse_korean_number(l.get('max_amount', '0')) > 0 or parse_korean_number(l.get('principal', '0')) > 0)]
            valid_loans.sort(key=lambda x: status_order.get(x.get('status'), 2))
            loan_memo = [f"{i}. {item.get('lender', '-')} | 설정금액: {format_manwon(item.get('max_amount', '0'))} | {item.get('ratio', '-')}% | 원금: {format_manwon(item.get('principal', '0'))} | {item.get('status', '-')}" for i, item in enumerate(valid_loans, 1)]
            if loan_memo:
                memo_lines.extend(loan_memo)
                memo_lines.append("")

        if ltv_results and isinstance(ltv_results, list):
            ltv_memo = [f"{res.get('loan_type', '기타')} 한도 LTV {res.get('ltv_rate', 0)}% {format_manwon(res.get('limit', 0))} 가용 {format_manwon(res.get('available', 0))}" for res in ltv_results if isinstance(res, dict)]
            if ltv_memo:
                memo_lines.extend(ltv_memo)
                ltv_lines_exist = True
        
        order = ['선말소', '대환', '퇴거자금']
        status_sums = defaultdict(lambda: defaultdict(lambda: {'sum': 0, 'count': 0}))
        has_status_sum = False
        for item in valid_loans:
            status = item.get('status', '')
            principal = parse_korean_number(item.get('principal', '0'))
            if status in order and principal > 0:
                lender = item.get('lender', '기타')
                status_sums[status][lender]['sum'] += principal
                status_sums[status][lender]['count'] += 1
                has_status_sum = True
        
        if has_status_sum:
            memo_lines.append("--------------------------------------------------")
            memo_lines.append("설정금액별 원금 합계")
            is_first_status_block = True
            for status in order:
                if status_sums[status]:
                    if not is_first_status_block: memo_lines.append("")
                    total_status_sum = sum(data['sum'] for data in status_sums[status].values())
                    memo_lines.append(f"{status}")
                    for lender, data in status_sums[status].items():
                        memo_lines.append(f"{lender} {data['count']}건 {format_manwon(data['sum'])}")
                    memo_lines.append(f"총 {format_manwon(total_status_sum)}")
                    is_first_status_block = False
            memo_lines.append("--------------------------------------------------")

        if fees and isinstance(fees, dict):
            consult_amt = parse_korean_number(fees.get('consult_amt', '0'))
            bridge_amt = parse_korean_number(fees.get('bridge_amt', '0'))
            fee_memo = []
            if consult_amt > 0 or bridge_amt > 0:
                consult_rate = float(fees.get('consult_rate', '0') or 0)
                consult_fee = int(consult_amt * consult_rate / 100)
                bridge_rate = float(fees.get('bridge_rate', '0') or 0)
                bridge_fee = int(bridge_amt * bridge_rate / 100)
                total_fee = consult_fee + bridge_fee
                if consult_amt > 0: fee_memo.append(f"필요금 {format_manwon(consult_amt)} 컨설팅비용({consult_rate}%): {format_manwon(consult_fee)}")
                if bridge_amt > 0: fee_memo.append(f"브릿지 {format_manwon(bridge_amt)} 브릿지비용({bridge_rate}%): {format_manwon(bridge_fee)}")
                if total_fee > 0: fee_memo.append(f"총 컨설팅 합계: {format_manwon(total_fee)}")

            if fee_memo:
                # --- *** 수정된 로직 *** ---
                # 만약 '설정금액별 원금 합계' 섹션이 없었고(has_status_sum=False), LTV 라인이 존재했다면(ltv_lines_exist=True),
                # LTV 라인과 비용 라인 사이에 구분선을 추가한다.
                if not has_status_sum and ltv_lines_exist:
                    memo_lines.append("--------------------------------------------------")
                
                memo_lines.extend(fee_memo)
        
        memo_text = "\n".join(memo_lines).strip()
        return {"memo": memo_text, "price_type": price_type}

    except Exception as e:
        logger.error(f"메모 생성 중 오류 발생: {e}", exc_info=True)
        return {"memo": "", "price_type": ""}


# --- 나머지 API 라우트 및 앱 실행 코드는 이전과 동일 ---
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
        total_value = int(data.get("total_value", 0))   # 만원 단위
        ltv = float(data.get("ltv", 70))
        loans = data.get("loans", [])
        owners = data.get("owners", [])
        senior_lien = 0

        # 차감할 대출 (선순위만, 채권최고액 우선, 없으면 원금)
        for loan in loans:
            status = loan.get("status", "").strip()
            # 선순위, 유지, 대환, 선말소만 차감 (후순위는 제외)
            if status in ["선순위", "유지", "대환", "선말소"]:
                max_amt = int(loan.get("max_amount", 0))
                principal = int(loan.get("principal", 0))
                senior_lien += max_amt if max_amt else principal

        # 디버깅용 로그
        logger.info(f"지분 계산 - 시세: {total_value}만, LTV: {ltv}%, 선순위: {senior_lien}만")
        logger.info(f"대출 데이터: {loans}")
        
        # 지분별 한도 계산
        results = calculate_individual_ltv_limits(total_value, owners, ltv, senior_lien)

        return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error(f"개인별 지분 한도 계산 오류: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
