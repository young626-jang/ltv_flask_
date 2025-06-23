import os
import re
import logging
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from collections import defaultdict

# --- 우리가 만든 헬퍼 파일들 임포트 ---
from utils import parse_korean_number, calculate_ltv_limit
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

@app.route('/api/generate_text_memo', methods=['POST'])
def generate_text_memo_route():
    """메모 생성 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "잘못된 요청 데이터"}), 400
            
        inputs = data.get('inputs', {})
        loans = data.get('loans', [])
        fees = data.get('fees', {})

        memo_content = generate_memo_content(inputs, loans, fees)
        
        return jsonify(memo_content)
        
    except Exception as e:
        logger.error(f"메모 생성 중 오류: {e}", exc_info=True)
        return jsonify({"error": "메모 생성 중 오류가 발생했습니다."}), 500

def generate_memo_content(inputs, loans, fees):
    """메모 내용 생성 로직 분리"""
    address = inputs.get('address', '')
    floor_match = re.findall(r"제(\d+)층", address)
    floor_num = int(floor_match[-1]) if floor_match else None
    
    price_type = ""
    if floor_num is not None:
        price_type = "📉 하안가" if floor_num <= 2 else "📈 일반가"

    total_value = parse_korean_number(inputs.get("kb_price", "0"))
    deduction = parse_korean_number(inputs.get("deduction_amount", "0"))
    ltv_rates = [rate for rate in inputs.get('ltv_rates', []) if rate and rate.isdigit()]
    
    # 대출 정보 계산
    maintain_maxamt_sum = sum(
        parse_korean_number(item.get('max_amount', '0')) 
        for item in loans if item.get('status') == '유지'
    )
    sub_principal_sum = sum(
        parse_korean_number(item.get('principal', '0')) 
        for item in loans if item.get('status') != '유지'
    )
    is_subordinate = any(item.get('status') == '유지' for item in loans)

    # LTV 계산
    ltv_results = []
    for rate_str in ltv_rates:
        ltv = int(rate_str)
        loan_type_info = "후순위" if is_subordinate else "선순위"
        limit, available = calculate_ltv_limit(
            total_value, deduction, sub_principal_sum, 
            maintain_maxamt_sum, ltv, is_senior=not is_subordinate
        )
        ltv_results.append({
            "ltv_rate": ltv, 
            "limit": limit, 
            "available": available, 
            "loan_type": loan_type_info
        })

    # 메모 생성
    memo = build_memo_text(inputs, loans, fees, ltv_results, total_value, deduction)
    
    return {"memo": memo, "price_type": price_type}

def build_memo_text(inputs, loans, fees, ltv_results, total_value, deduction):
    """메모 텍스트 구성"""
    memo = []
    
    # 고객 기본 정보
    memo.append(f"고객명: {inputs.get('customer_name', '')}")
    area_str = f"면적: {inputs.get('area', '')}㎡"
    kb_price_str = f"KB시세: {format_thousands(total_value)}만"
    deduction_str = f"방공제: {format_thousands(deduction)}만"
    memo.append(f"주소: {inputs.get('address', '')} | {area_str} | {kb_price_str} | {deduction_str}")
    memo.append("")

    # LTV 정보
    for res in ltv_results:
        memo.append(
            f"LTV {res['ltv_rate']}% ({res['loan_type']}) "
            f"한도: {format_thousands(res['limit'])}만 "
            f"가용: {format_thousands(res['available'])}만"
        )
    memo.append("")
    
    # 대출 정보
    for item in loans:
        memo.append(
            f"{item.get('lender', '-')} | "
            f"{format_thousands(parse_korean_number(item.get('max_amount', '0')))} | "
            f"{item.get('ratio', '-')}% | "
            f"{format_thousands(parse_korean_number(item.get('principal', '0')))} | "
            f"{item.get('status', '-')}"
        )
    memo.append("")
    
    # 대출기관별 합계 (선순위일 때만 표시)
    is_subordinate = any(item.get('status') == '유지' for item in loans)
    
    if not is_subordinate:  # 선순위일 때만 표시
        lender_sum = defaultdict(int)
        for item in loans:
            if item.get('lender', '').strip():
                lender_sum[item['lender']] += parse_korean_number(item.get('principal', '0'))
        
        if lender_sum:
            memo.append("설정금액별 원금합계")
            for lender, total in lender_sum.items():
                memo.append(f"{lender}: {format_thousands(total)}만")
            
    # 대환/선말소 합계
    dh_sum = sum(
        parse_korean_number(item.get('principal', '0')) 
        for item in loans if item.get('status') == '대환'
    )
    sm_sum = sum(
        parse_korean_number(item.get('principal', '0')) 
        for item in loans if item.get('status') == '선말소'
    )
    
    if dh_sum > 0: 
        memo.append(f"대환 합계: {format_thousands(dh_sum)}만")
    if sm_sum > 0: 
        memo.append(f"선말소 합계: {format_thousands(sm_sum)}만")
    memo.append("")

    # 수수료 정보
    consult_amt = parse_korean_number(fees.get('consult_amt', '0'))
    consult_rate = float(fees.get('consult_rate', '0') or 0)
    consult_fee = int(consult_amt * consult_rate / 100)
    bridge_amt = parse_korean_number(fees.get('bridge_amt', '0'))
    bridge_rate = float(fees.get('bridge_rate', '0') or 0)
    bridge_fee = int(bridge_amt * bridge_rate / 100)
    total_fee = consult_fee + bridge_fee
    
    memo.extend([
        f"대출금 {format_thousands(consult_amt)}만 컨설팅비용: {format_thousands(consult_fee)}만",
        f"브릿지 {format_thousands(bridge_amt)}만 브릿지비용: {format_thousands(bridge_fee)}만",
        f"총 수수료 합계: {format_thousands(total_fee)}만"
    ])

    return "\n".join(memo)

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
