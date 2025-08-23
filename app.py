import os
import re
import logging
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from collections import defaultdict

# --- 우리가 만든 헬퍼 파일들 임포트 ---
from utils import parse_korean_number, calculate_ltv_limit, convert_won_to_manwon, calculate_principal_from_ratio, auto_convert_loan_amounts
from ltv_map import region_map
from pdf_parser import parse_pdf_for_ltv
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

# --- API 라우트 ---
@app.route('/api/upload', methods=['POST'])
def upload_and_parse_pdf():
    """PDF 업로드 및 파싱 처리"""
    logger.info("PDF 업로드 요청 수신")
    
    try:
        # 파일 존재 확인
        if 'pdf_file' not in request.files:
            logger.warning("요청에 'pdf_file'이 없음")
            return jsonify({"success": False, "error": "요청에 파일이 없습니다."}), 400
        
        file = request.files['pdf_file']
        
        # 파일명 확인
        if not file.filename:
            logger.warning("파일명이 비어있음")
            return jsonify({"success": False, "error": "선택된 파일이 없습니다."}), 400
        
        # 파일 확장자 확인
        if not allowed_file(file.filename):
            logger.warning(f"허용되지 않은 파일 형식: {file.filename}")
            return jsonify({"success": False, "error": "PDF 파일만 업로드 가능합니다."}), 400
        
        # 파일 저장
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        logger.info(f"파일 저장 시도: {filepath}")
        file.save(filepath)
        logger.info("파일 저장 완료")
        
        # PDF 파싱
        logger.info("PDF 파싱 시작")
        scraped_data = parse_pdf_for_ltv(filepath)
        logger.info(f"PDF 파싱 완료. 추출된 데이터 키 개수: {len(scraped_data) if scraped_data else 0}")
        
        return jsonify({
            "success": True, 
            "filename": filename, 
            "scraped_data": scraped_data
        })

    except Exception as e:
        logger.error(f"PDF 업로드 처리 중 오류: {e}", exc_info=True)
        return jsonify({
            "success": False, 
            "error": f"서버 처리 중 오류 발생: {str(e)}"
        }), 500

@app.route('/view_pdf/<filename>')
def view_pdf(filename):
    """업로드된 PDF 파일 보기"""
    # 파일명 보안 검증
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        logger.warning(f"요청된 파일이 존재하지 않음: {filepath}")
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404
    
    return send_file(filepath, mimetype='application/pdf')

def generate_memo(data):
    """
    하나의 함수로 통합된 메모 생성 로직.
    (메모 상단 양식 수정)
    """
    try:
        inputs = data.get('inputs', {})
        loans = data.get('loans', [])
        fees = data.get('fees', {})

        # --- 금액 포맷팅 헬퍼 함수 (콤마 추가) ---
        def format_manwon(value):
            num_val = parse_korean_number(str(value))
            if num_val == 0:
                return "0"
            manwon_val = convert_won_to_manwon(num_val)
            return f"{manwon_val:,}만"

        # --- 1. 계산 로직 ---
        address = inputs.get('address', '')
        floor_match = re.findall(r"제(\d+)층", address)
        floor_num = int(floor_match[-1]) if floor_match else None
        
        price_type = ""
        if floor_num is not None:
            price_type = "하안가" if floor_num <= 2 else "일반가"

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
        memo_lines = []

        if inputs and (inputs.get('customer_name') or inputs.get('address')):
            # 고객명 라인
            memo_lines.append(f"고객명: {inputs.get('customer_name', '')}")
            
            # 주소 및 기타 정보 라인
            area_str = f"면적: {inputs.get('area', '')}㎡" if inputs.get('area') else ""
            
            # KB시세 문자열 생성 (시세 적용 타입 포함)
            kb_price_str = ""
            if total_value > 0:
                price_info = f" ({price_type})" if price_type else ""
                kb_price_str = f"KB시세: {format_manwon(total_value)}{price_info}"
            
            deduction_str = f"방공제: {format_manwon(deduction)}" if deduction > 0 else ""
            
            # 주소 파트 조립 및 "주소 :" 접두사 추가
            address_parts = [inputs.get('address', ''), area_str, kb_price_str, deduction_str]
            full_address_line = " | ".join(part for part in address_parts if part)
            if full_address_line:
                memo_lines.append(f"주소 : {full_address_line}")
            
            memo_lines.append("")

        # (이하 로직은 이전과 동일)
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
            ltv_memo = [f"{res.get('loan_type', '기타')} 한도 LTV {res.get('ltv_rate', 0)}% {format_manwon(res.get('limit', 0))} 가용 {format_manwon(res.get('available', 0))}" for res in ltv_results if isinstance(res, dict) and (res.get('limit', 0) > 0 or res.get('available', 0) > 0)]
            if ltv_memo:
                memo_lines.extend(ltv_memo)

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
            memo_lines.append("")
            for status in order:
                if status_sums[status]:
                    total_status_sum = sum(data['sum'] for data in status_sums[status].values())
                    memo_lines.append(f"{status}")
                    for lender, data in status_sums[status].items():
                        memo_lines.append(f"{lender} {data['count']}건 {format_manwon(data['sum'])}")
                    memo_lines.append(f"총 {format_manwon(total_status_sum)}")
            memo_lines.append("--------------------------------------------------")

        if fees and isinstance(fees, dict):
            consult_amt = parse_korean_number(fees.get('consult_amt', '0'))
            bridge_amt = parse_korean_number(fees.get('bridge_amt', '0'))

            if consult_amt > 0 or bridge_amt > 0:
                consult_rate = float(fees.get('consult_rate', '0') or 0)
                consult_fee = int(consult_amt * consult_rate / 100)
                bridge_rate = float(fees.get('bridge_rate', '0') or 0)
                bridge_fee = int(bridge_amt * bridge_rate / 100)
                total_fee = consult_fee + bridge_fee
                fee_memo = []
                if consult_amt > 0: fee_memo.append(f"필요금 {format_manwon(consult_amt)} 컨설팅비용({consult_rate}%): {format_manwon(consult_fee)}")
                if bridge_amt > 0: fee_memo.append(f"브릿지 {format_manwon(bridge_amt)} 브릿지비용({bridge_rate}%): {format_manwon(bridge_fee)}")
                if total_fee > 0: fee_memo.append(f"총 컨설팅 합계: {format_manwon(total_fee)}")
                if fee_memo:
                    if memo_lines and memo_lines[-1]: memo_lines.append("")
                    memo_lines.extend(fee_memo)
        
        memo_text = "\n".join(memo_lines).strip()
        return {"memo": memo_text, "price_type": price_type}

    except Exception as e:
        logger.error(f"메모 생성 중 오류 발생: {e}", exc_info=True)
        return {"memo": "", "price_type": ""}

@app.route('/api/generate_text_memo', methods=['POST'])
def generate_text_memo_route():
    """메모 생성 API"""
    data = request.get_json() or {}
    result = generate_memo(data)
    return jsonify(result)


@app.route('/api/convert_loan_amount', methods=['POST'])
def convert_loan_amount_route():
    """대출 금액 자동 변환 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400
        
        converted_data = auto_convert_loan_amounts(data)
        return jsonify({
            "success": True,
            "converted_data": converted_data
        })
        
    except Exception as e:
        logger.error(f"대출 금액 변환 중 오류: {e}")
        return jsonify({"error": "금액 변환 중 오류가 발생했습니다."}), 500

@app.route('/api/calculate_principal', methods=['POST'])
def calculate_principal_route():
    """원금 계산 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400
            
        max_amount = data.get('max_amount', 0)
        ratio = data.get('ratio', 100)
        
        principal = calculate_principal_from_ratio(max_amount, ratio)
        
        return jsonify({
            "success": True,
            "principal": principal
        })
        
    except Exception as e:
        logger.error(f"원금 계산 중 오류: {e}")
        return jsonify({"error": "원금 계산 중 오류가 발생했습니다."}), 500

# --- 고객 관리 API 라우트 ---
@app.route('/api/customers')
def get_customers():
    """고객 목록 조회"""
    try:
        return jsonify(fetch_all_customers())
    except Exception as e:
        logger.error(f"고객 목록 조회 오류: {e}")
        return jsonify({"error": "고객 목록을 불러올 수 없습니다."}), 500

@app.route('/api/customer/<page_id>')
def get_customer_details(page_id):
    """고객 상세 정보 조회"""
    try:
        details = fetch_customer_details(page_id)
        return jsonify(details) if details else (jsonify({"error": "Customer not found"}), 404)
    except Exception as e:
        logger.error(f"고객 상세 정보 조회 오류: {e}")
        return jsonify({"error": "고객 정보를 불러올 수 없습니다."}), 500

@app.route('/api/customer/new', methods=['POST'])
def save_new_customer_route():
    """새 고객 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400
        return jsonify(create_new_customer(data))
    except Exception as e:
        logger.error(f"새 고객 생성 오류: {e}")
        return jsonify({"error": "고객 생성 중 오류가 발생했습니다."}), 500

@app.route('/api/customer/update/<page_id>', methods=['POST'])
def update_customer_route(page_id):
    """고객 정보 업데이트"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400
        return jsonify(update_customer(page_id, data))
    except Exception as e:
        logger.error(f"고객 정보 업데이트 오류: {e}")
        return jsonify({"error": "고객 정보 업데이트 중 오류가 발생했습니다."}), 500

@app.route('/api/customer/delete/<page_id>', methods=['POST'])
def delete_customer_route(page_id):
    """고객 삭제"""
    try:
        return jsonify(delete_customer(page_id))
    except Exception as e:
        logger.error(f"고객 삭제 오류: {e}")
        return jsonify({"error": "고객 삭제 중 오류가 발생했습니다."}), 500

# --- 앱 실행 ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


