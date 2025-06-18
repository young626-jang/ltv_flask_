import os
import re
import requests
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

# --- Flask 앱 설정 ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- 템플릿 필터 ---
@app.template_filter()
def format_thousands(value):
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value

# --- 페이지 라우트 ---
@app.route('/')
def main_calculator_page():
    return render_template('entry.html', region_map=region_map)

# --- API 라우트 ---
# app.py 파일에서 이 함수를 찾아 교체하세요.
@app.route('/api/upload', methods=['POST'])
def upload_and_parse_pdf():
    print("--- [/api/upload] PDF 업로드 요청 수신 ---") # ✨ 진단 로그
    try:
        if 'pdf_file' not in request.files:
            print("[오류] 요청에 'pdf_file'이 없습니다.") # ✨ 진단 로그
            return jsonify({"success": False, "error": "요청에 파일이 없습니다."}), 400
        
        file = request.files['pdf_file']
        
        if file.filename == '':
            print("[오류] 파일명이 비어있습니다.") # ✨ 진단 로그
            return jsonify({"success": False, "error": "선택된 파일이 없습니다."}), 400
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"파일 저장 시도: {filepath}") # ✨ 진단 로그
            file.save(filepath)
            print("파일 저장 완료.") # ✨ 진단 로그
            
            print("PDF 파싱 시작...") # ✨ 진단 로그
            scraped_data = parse_pdf_for_ltv(filepath)
            print("PDF 파싱 완료. 추출된 데이터:", scraped_data) # ✨ 진단 로그
            
            return jsonify({"success": True, "filename": filename, "scraped_data": scraped_data})

    except Exception as e:
        print(f"!!!!! [/api/upload] 심각한 오류 발생: {e}") # ✨ 진단 로그
        import traceback
        traceback.print_exc() # 상세한 오류 원인 출력
        return jsonify({"success": False, "error": f"서버 처리 중 오류 발생: {str(e)}"}), 500
    
    return jsonify({"success": False, "error": "알 수 없는 서버 오류"}), 500

@app.route('/view_pdf/<filename>')
def view_pdf(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='application/pdf')
    return "오류: 파일을 찾을 수 없습니다.", 404

@app.route('/api/generate_text_memo', methods=['POST'])
def generate_text_memo_route():
    data = request.get_json()
    inputs = data.get('inputs', {})
    loans = data.get('loans', [])
    fees = data.get('fees', {})

    address = inputs.get('address', '')
    floor_match = re.findall(r"제(\d+)층", address)
    floor_num = int(floor_match[-1]) if floor_match else None
    
    if floor_num is not None:
        price_type = "📉 하안가" if floor_num <= 2 else "📈 일반가"
    else:
        price_type = ""

    total_value = parse_korean_number(inputs.get("kb_price", "0"))
    deduction = parse_korean_number(inputs.get("deduction_amount", "0"))
    ltv_rates = [rate for rate in inputs.get('ltv_rates', []) if rate and rate.isdigit()]
    
    maintain_maxamt_sum = sum(parse_korean_number(item.get('max_amount', '0')) for item in loans if item.get('status') == '유지')
    sub_principal_sum = sum(parse_korean_number(item.get('principal', '0')) for item in loans if item.get('status') != '유지')
    is_subordinate = any(item.get('status') == '유지' for item in loans)

    ltv_results = []
    for rate_str in ltv_rates:
        ltv = int(rate_str)
        loan_type_info = "후순위" if is_subordinate else "선순위"
        limit, available = calculate_ltv_limit(total_value, deduction, sub_principal_sum, maintain_maxamt_sum, ltv, is_senior=not is_subordinate)
        ltv_results.append({"ltv_rate": ltv, "limit": limit, "available": available, "loan_type": loan_type_info})

    memo = []
    memo.append(f"고객명: {inputs.get('customer_name', '')}")
    area_str = f"면적: {inputs.get('area', '')}㎡"
    kb_price_str = f"KB시세: {format_thousands(total_value)}만"
    deduction_str = f"방공제: {format_thousands(deduction)}만"
    memo.append(f"주소: {address} | {area_str} | {kb_price_str} | {deduction_str}")
    memo.append("")

    for res in ltv_results:
        memo.append(f"LTV {res.get('ltv_rate')}% ({res.get('loan_type')}) 한도: {format_thousands(res.get('limit'))}만 가용: {format_thousands(res.get('available'))}만")

    memo.append("")
    
    for item in loans:
        memo.append(f"{item.get('lender', '-')} | {format_thousands(parse_korean_number(item.get('max_amount', '0')))} | {item.get('ratio', '-')}% | {format_thousands(parse_korean_number(item.get('principal', '0')))} | {item.get('status', '-')}")

    memo.append("")
    
    lender_sum = defaultdict(int)
    for item in loans:
        if item.get('lender', '').strip():
            lender_sum[item['lender']] += parse_korean_number(item.get('principal', '0'))
    if lender_sum:
        memo.append("설정금액별 원금합계")
        for lender, total in lender_sum.items():
            memo.append(f"{lender}: {format_thousands(total)}만")
            
    dh_sum = sum(parse_korean_number(item.get('principal', '0')) for item in loans if item.get('status') == '대환')
    sm_sum = sum(parse_korean_number(item.get('principal', '0')) for item in loans if item.get('status') == '선말소')
    
    if dh_sum > 0: memo.append(f"대환 합계: {format_thousands(dh_sum)}만")
    if sm_sum > 0: memo.append(f"선말소 합계: {format_thousands(sm_sum)}만")

    memo.append("")

    consult_amt = parse_korean_number(fees.get('consult_amt', '0'))
    consult_rate = float(fees.get('consult_rate', '0') or 0)
    consult_fee = int(consult_amt * consult_rate / 100)
    bridge_amt = parse_korean_number(fees.get('bridge_amt', '0'))
    bridge_rate = float(fees.get('bridge_rate', '0') or 0)
    bridge_fee = int(bridge_amt * bridge_rate / 100)
    total_fee = consult_fee + bridge_fee
    
    memo.append(f"대출금 {format_thousands(consult_amt)}만 컨설팅비용: {format_thousands(consult_fee)}만")
    memo.append(f"브릿지 {format_thousands(bridge_amt)}만 브릿지비용: {format_thousands(bridge_fee)}만")
    memo.append(f"총 수수료 합계: {format_thousands(total_fee)}만")

    return jsonify({"memo": "\n".join(memo), "price_type": price_type})


@app.route('/api/customers')
def get_customers(): return jsonify(fetch_all_customers())
@app.route('/api/customer/<page_id>')
def get_customer_details(page_id):
    details = fetch_customer_details(page_id)
    return jsonify(details) if details else (jsonify({"error": "Customer not found"}), 404)
@app.route('/api/customer/new', methods=['POST'])
def save_new_customer_route(): return jsonify(create_new_customer(request.get_json()))
@app.route('/api/customer/update/<page_id>', methods=['POST'])
def update_customer_route(page_id): return jsonify(update_customer(page_id, request.get_json()))
@app.route('/api/customer/delete/<page_id>', methods=['POST'])
def delete_customer_route(page_id): return jsonify(delete_customer(page_id))


# --- 앱 실행 ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
