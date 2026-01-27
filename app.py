from flask import Flask, render_template, request, jsonify
import requests
import json

app = Flask(__name__)

# ========== PortOne API 설정 ==========
PORTONE_API_KEY = "4311564636646666"
PORTONE_API_SECRET = "wRLUx3QyApChAeizglLdwuWFIPzy4aBCfY1iBiNkk3TljGAgBIK8smKMHqkhSHllCWTULpyq2x39PEF9"
PORTONE_TOKEN_URL = "https://api.iamport.kr/users/getToken"
PORTONE_VBANK_URL = "https://api.iamport.kr/vbanks/holder"

# ========== 국세청 API 설정 ==========
SERVICE_KEY = "B6F8mdWu8MpnYUwgzs84AWBmkZG3B2l+ItDSFbeL64CxbxJORed+4LpR5uMHxebO/v7LSHBXm1FHFJ8XE6UHqA=="
STATUS_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"

# ========== 은행 코드 매핑 ==========
BANK_CODES = {
    "국민": "004",
    "우리": "020",
    "신한": "088",
    "농협": "011",
    "하나": "081",
    "씨티": "027",
    "대구": "031",
    "부산": "032",
    "광주": "034",
    "제주": "035",
    "전북": "037",
    "경남": "039",
    "산업": "002",
    "수협": "007",
    "우체국": "012",
    "카카오": "090",
    "토스": "092",
    "케이뱅크": "089",
    "NH농협": "011",
    "IBK기업": "001",
    "KB국민": "004",
    "SC제일": "023",
    "DGB대구": "031",
    "BNK부산": "032",
    "KDB산업": "002",
    "SH수협": "007",
    "JB전북": "037",
    "KN경남": "039",
    "GWB광주": "034",
    "JJ제주": "035",
    "CITI씨티": "027",
    "우리카드": "071",
    "신한카드": "080",
    "삼성카드": "082",
    "현대카드": "084",
    "BC카드": "086",
    "롯데카드": "076",
    "이마트카드": "077",
    "농협카드": "012",
    "제주카드": "035",
    "광주카드": "034",
    "전주카드": "037",
    "경남카드": "039",
    "대구카드": "031",
    "부산카드": "032",
    "수협카드": "007",
    "우체국카드": "012",
    "한국은행": "001",
    "하나카드": "083",
    "K뱅크": "089",
    "카카오뱅크": "090",
    "토스뱅크": "092",
    "오픈뱅킹": "097",
    "메가뱅크": "057",
    "BBBank": "057",
    "신영증권": "024",
    "NH투자": "005",
    "삼성증권": "003",
    "한투증권": "010",
    "미래에셋": "006",
    "대신증권": "009",
    "이베스트": "018",
    "한화증권": "023",
    "SK증권": "025",
    "현대차증권": "028",
    "기업은행": "003",
    "기업": "003",
    "한국개발": "030",
    "한국마이칼": "029",
    "한국금융": "028",
    "새마을금고": "045",
    "신협": "048",
    "우리저축": "050",
    "현대저축": "051",
    "경남저축": "052",
    "부산저축": "053",
    "광주저축": "054",
    "전주저축": "055",
    "제주저축": "056",
    "대구저축": "057",
    "우리저축은행": "050",
    "경남저축은행": "052",
    "부산저축은행": "053",
    "광주저축은행": "054",
    "전주저축은행": "055",
    "제주저축은행": "056",
    "대구저축은행": "057",
}

# ========== 사업자 상태 코드 매핑 ==========
STATUS_MAPPING = {
    "01": "영업",
    "02": "휴업",
    "03": "폐업"
}

# ========== 세금 유형 코드 매핑 ==========
TAX_TYPE_MAPPING = {
    "01": "일반과세자",
    "02": "간이과세자",
    "03": "면세사업자"
}


def determine_business_type(business_no):
    """사업자등록번호의 가운데 2자리로 법인/개인 구분"""
    business_no_clean = business_no.replace("-", "").strip()

    if len(business_no_clean) < 5:
        return "알 수 없음", "-"

    middle_two = business_no_clean[3:5]

    # 법인사업자
    if middle_two in ["80", "81", "85", "86", "87", "89"]:
        if middle_two == "80":
            return "법인사업자", "아파트 관리사무소/다단계판매원"
        elif middle_two in ["81", "86", "87"]:
            return "법인사업자", "영리법인"
        elif middle_two == "85":
            return "법인사업자", "영리법인 지점"
        elif middle_two == "89":
            return "법인사업자", "종교단체"

    # 개인사업자
    elif middle_two in [f"{i:02d}" for i in range(1, 80)] or middle_two in [f"{i:02d}" for i in range(90, 100)]:
        if "90" <= middle_two <= "99":
            return "개인사업자", "면세사업자"
        else:
            return "개인사업자", "과세사업자"

    return "알 수 없음", "-"


def get_bank_code(bank_name):
    """은행명으로 코드 조회 (자동 정리)"""
    bank_name_clean = bank_name.replace("은행", "").replace("뱅크", "").replace("카드", "").strip()
    return BANK_CODES.get(bank_name_clean)


def get_portone_token():
    """PortOne 액세스 토큰 획득"""
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "imp_key": PORTONE_API_KEY,
            "imp_secret": PORTONE_API_SECRET
        }
        response = requests.post(PORTONE_TOKEN_URL, json=data, headers=headers)

        if response.status_code != 200:
            return None

        result = response.json()
        if result.get("code") == 0:
            return result.get("response", {}).get("access_token")
        return None

    except Exception as e:
        print(f"토큰 획득 오류: {str(e)}")
        return None


@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


@app.route('/api/check-account', methods=['POST'])
def check_account():
    """예금주 조회 API"""
    try:
        data = request.json
        bank_name = data.get('bank_name', '').strip()
        account_num = data.get('account_num', '').strip().replace('-', '')  # 하이픈 제거

        if not bank_name or not account_num:
            return jsonify({"success": False, "message": "은행명과 계좌번호를 입력하세요"}), 400

        # 은행 코드 조회
        bank_code = get_bank_code(bank_name)
        if not bank_code:
            return jsonify({"success": False, "message": f"지원하지 않는 은행: {bank_name}"}), 400

        # PortOne 토큰 획득
        access_token = get_portone_token()
        if not access_token:
            return jsonify({"success": False, "message": "API 인증 실패"}), 500

        # 예금주 조회
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "bank_code": bank_code,
            "bank_num": account_num
        }

        response = requests.get(PORTONE_VBANK_URL, headers=headers, params=params)

        if response.status_code != 200:
            print(f"[DEBUG] PortOne API 호출 실패 - Status: {response.status_code}")
            print(f"[DEBUG] Response: {response.text}")
            return jsonify({"success": False, "message": f"API 호출 실패 (상태코드: {response.status_code})"}), 500

        result = response.json()
        print(f"[DEBUG] PortOne API 응답: {result}")

        if result.get("code") != 0:
            message = result.get("message", "계좌 정보를 찾을 수 없습니다")
            return jsonify({"success": False, "message": message}), 404

        holder_name = result.get("response", {}).get("bank_holder")

        if not holder_name:
            return jsonify({"success": False, "message": "예금주 정보를 찾을 수 없습니다"}), 404

        return jsonify({
            "success": True,
            "message": "조회 성공",
            "data": {
                "bank_name": bank_name,
                "account_num": account_num,
                "holder_name": holder_name
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"오류: {str(e)}"}), 500


@app.route('/api/check-business', methods=['POST'])
def check_business():
    """사업자 상태 조회 API"""
    try:
        data = request.json
        business_no = data.get('business_no', '').strip()

        if not business_no:
            return jsonify({"success": False, "message": "사업자등록번호를 입력하세요"}), 400

        # 사업자등록번호 검증
        business_no_clean = business_no.replace("-", "").strip()

        if not business_no_clean.isdigit() or len(business_no_clean) != 10:
            return jsonify({"success": False, "message": "사업자등록번호는 10자리 숫자여야 합니다"}), 400

        # 국세청 API 호출
        headers = {"Content-Type": "application/json"}
        request_data = {"b_no": [business_no_clean]}
        params = {"serviceKey": SERVICE_KEY}

        response = requests.post(STATUS_URL, json=request_data, headers=headers, params=params)

        if response.status_code != 200:
            return jsonify({"success": False, "message": "API 호출 실패"}), 500

        result = response.json()

        # 조회 결과 확인
        if result.get("match_cnt", 0) == 0:
            return jsonify({"success": False, "message": "국세청에 등록되지 않은 사업자등록번호입니다"}), 404

        data_list = result.get("data", [])
        if not data_list:
            return jsonify({"success": False, "message": "조회 결과가 없습니다"}), 404

        business_info = data_list[0]

        # 법인/개인 구분
        business_type, business_detail = determine_business_type(business_no_clean)

        # 상태 코드 매핑
        b_stt_cd = business_info.get("b_stt_cd", "-")
        b_stt = STATUS_MAPPING.get(b_stt_cd, business_info.get("b_stt", "-"))
        tax_type_cd = business_info.get("tax_type_cd", "-")
        tax_type = TAX_TYPE_MAPPING.get(tax_type_cd, business_info.get("tax_type", "-"))

        return jsonify({
            "success": True,
            "message": "조회 성공",
            "data": {
                "business_no": business_info.get("b_no", "-"),
                "business_type": business_type,
                "business_detail": business_detail,
                "status": b_stt,
                "tax_type": tax_type,
                "end_dt": business_info.get("end_dt", "-"),
                "invoice_apply_dt": business_info.get("invoice_apply_dt", "-"),
                "rbf_tax_type": business_info.get("rbf_tax_type", "-")
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"오류: {str(e)}"}), 500


if __name__ == '__main__':
    print("Flask 웹 서버 시작: http://localhost:5000")
    app.run(debug=True, host='localhost', port=5000)
