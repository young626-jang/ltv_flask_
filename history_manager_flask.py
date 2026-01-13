import os
import requests
import logging
from typing import Dict, List, Optional, Any
from functools import wraps
from utils import parse_korean_number

# 로깅 설정
logger = logging.getLogger(__name__)

# --- Notion API 설정 ---
# **하드코딩된 기본값 모두 제거**
NOTION_TOKEN = os.getenv('NOTION_TOKEN') 
CUSTOMER_DB_ID = os.getenv('CUSTOMER_DB_ID')
LOAN_DB_ID = os.getenv('LOAN_DB_ID')

# Notion DB 속성 이름
CUSTOMER_DB_TITLE_PROPERTY = "고객명"
LOAN_DB_RELATION_PROPERTY = "고객명"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 요청 제한 및 재시도 설정
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

def handle_notion_errors(func):
    """Notion API 에러 처리 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.Timeout:
                logger.warning(f"{func.__name__} 시도 {attempt + 1}: 타임아웃")
                if attempt == MAX_RETRIES - 1:
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"{func.__name__} 시도 {attempt + 1}: HTTP 오류 - {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
            except Exception as e:
                logger.error(f"{func.__name__} 시도 {attempt + 1}: 예상치 못한 오류 - {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
        return None
    return wrapper

# --- Notion 데이터 파싱 헬퍼 함수 ---
def get_rich_text(props: Dict, name: str) -> str:
    """Rich text 속성에서 텍스트 추출"""
    prop = props.get(name, {})
    rich_text = prop.get("rich_text", [])
    return rich_text[0].get("text", {}).get("content", "") if rich_text else ""

def get_title(props: Dict, name: str) -> str:
    """Title 속성에서 텍스트 추출"""
    prop = props.get(name, {})
    title = prop.get("title", [])
    return title[0].get("text", {}).get("content", "") if title else ""

def get_number(props: Dict, name: str) -> Optional[float]:
    """Number 속성에서 숫자 추출"""
    return props.get(name, {}).get("number")

def get_share_rate(props: Dict, name: str) -> Optional[float]:
    """지분율 속성에서 숫자 추출 (텍스트 형식도 지원)"""
    # 먼저 Number 타입 시도
    number_val = props.get(name, {}).get("number")
    if number_val is not None:
        return number_val
    
    # Number 타입이 없으면 Rich Text 타입에서 파싱 시도
    text_val = get_rich_text(props, name)
    if text_val:
        # '지분율 8/10 (80.0%)' 형식 파싱
        import re
        # 괄호 안의 퍼센트 값 추출
        percent_match = re.search(r'\((\d+\.?\d*)\s*%\)', text_val)
        if percent_match:
            return float(percent_match.group(1))
        
        # 분수 형식 추출 (예: 8/10)
        fraction_match = re.search(r'(\d+)/(\d+)', text_val)
        if fraction_match:
            numerator = float(fraction_match.group(1))
            denominator = float(fraction_match.group(2))
            return (numerator / denominator) * 100
        
        # 단순 퍼센트 값 추출 (예: 80.0%)
        simple_percent = re.search(r'(\d+\.?\d*)\s*%', text_val)
        if simple_percent:
            return float(simple_percent.group(1))
    
    return None

def safe_number_conversion(value: Any) -> int:
    """안전한 숫자 변환"""
    try:
        if isinstance(value, str):
            return int(float(value)) if value.strip() else 0
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0

def parse_share_rate_for_save(value: Any) -> float:
    """저장용 지분율 파싱 - 다양한 형식의 지분율을 숫자로 변환"""
    if value is None:
        return 0.0
    
    # 이미 숫자인 경우
    if isinstance(value, (int, float)):
        return float(value)
    
    # 문자열인 경우 파싱 시도
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return 0.0
        
        # 단순 숫자인 경우
        try:
            return float(value)
        except ValueError:
            pass
        
        # '지분율 8/10 (80.0%)' 형식 파싱
        import re
        # 괄호 안의 퍼센트 값 추출
        percent_match = re.search(r'\((\d+\.?\d*)\s*%\)', value)
        if percent_match:
            return float(percent_match.group(1))
        
        # 분수 형식 추출 (예: 8/10)
        fraction_match = re.search(r'(\d+)/(\d+)', value)
        if fraction_match:
            numerator = float(fraction_match.group(1))
            denominator = float(fraction_match.group(2))
            return (numerator / denominator) * 100
        
        # 단순 퍼센트 값 추출 (예: 80.0%)
        simple_percent = re.search(r'(\d+\.?\d*)\s*%', value)
        if simple_percent:
            return float(simple_percent.group(1))
    
    return 0.0

# --- Notion DB 조회 함수 ---
@handle_notion_errors
def fetch_all_customers() -> List[Dict]:
    """모든 고객 목록 조회"""
    customers = []
    query_url = f"https://api.notion.com/v1/databases/{CUSTOMER_DB_ID}/query"
    has_more = True
    next_cursor = None
    
    while has_more:
        payload = {"page_size": 100}
        if next_cursor:
            payload["start_cursor"] = next_cursor
            
        response = requests.post(
            query_url, 
            headers=NOTION_HEADERS, 
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        
        for page in data.get("results", []):
            props = page.get("properties", {})
            customer_name = get_title(props, CUSTOMER_DB_TITLE_PROPERTY)
            if customer_name:
                customers.append({
                    "id": page["id"], 
                    "name": customer_name.strip()
                })
        
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    
    logger.info(f"총 {len(customers)}명의 고객 조회 완료")
    return customers

@handle_notion_errors
def fetch_customer_details(page_id: str) -> Optional[Dict]:
    """고객 상세 정보 조회"""
    if not page_id:
        logger.warning("페이지 ID가 제공되지 않음")
        return None
    
    # 고객 기본 정보 조회
    customer_response = requests.get(
        f"https://api.notion.com/v1/pages/{page_id}", 
        headers=NOTION_HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    customer_response.raise_for_status()
    
    props = customer_response.json().get("properties", {})
    
    customer_details = {
        "customer_name": get_title(props, CUSTOMER_DB_TITLE_PROPERTY),
        "address": get_rich_text(props, "주소"),
        "birth_date": get_rich_text(props, "생년월일"),
        "kb_price": get_number(props, "KB시세"),
        "area": get_rich_text(props, "전용면적"),
        "unit_count": get_rich_text(props, "세대수"),
        "completion_date": get_rich_text(props, "준공일자"),
        "ownership_transfer_date": get_rich_text(props, "소유권이전일"),
        "instant_business_operator": get_checkbox(props, "즉발사업자"),
        "business_issue_date": get_rich_text(props, "사업자발급일"),
        "business_registration_date": get_rich_text(props, "사업자등록일자"),
        "loan_available_date": get_rich_text(props, "대출가능일자"),
        "deduction_region": get_rich_text(props, "방공제지역"),
        "ltv1": get_rich_text(props, "LTV비율1"),
        "ltv2": get_rich_text(props, "LTV비율2"),
        "share_rate1": get_share_rate(props, "공유자 1 지분율"),
        "share_rate2": get_share_rate(props, "공유자 2 지분율"),
        "consult_amt": get_number(props, "컨설팅금액"),
        "consult_rate": get_number(props, "컨설팅수수료율"),
        "bridge_amt": get_number(props, "브릿지금액"),
        "bridge_rate": get_number(props, "브릿지수수료율"),
    }
    
    # 대출 정보 조회
    loan_query_url = f"https://api.notion.com/v1/databases/{LOAN_DB_ID}/query"
    loan_payload = {
        "filter": {
            "property": LOAN_DB_RELATION_PROPERTY,
            "relation": {"contains": page_id}
        },
        "sorts": [
            {
                "timestamp": "created_time",
                "direction": "ascending"
            }
        ]
    }
    
    loan_response = requests.post(
        loan_query_url, 
        headers=NOTION_HEADERS, 
        json=loan_payload,
        timeout=REQUEST_TIMEOUT
    )
    loan_response.raise_for_status()
    
    loan_items = []
    for item in loan_response.json().get("results", []):
        loan_props = item.get("properties", {})
        loan_items.append({
            "lender": get_title(loan_props, "설정자"),
            "status": get_rich_text(loan_props, "진행구분"),
            "max_amount": get_number(loan_props, "채권최고액"),
            "principal": get_number(loan_props, "원금"),
            "ratio": get_number(loan_props, "설정비율"),
        })
    
    customer_details["loans"] = loan_items
    logger.info(f"고객 '{customer_details['customer_name']}' 상세 정보 조회 완료 (대출 {len(loan_items)}건)")
    
    return customer_details

# --- 데이터 포맷팅 함수 ---
def format_properties_payload(data: Dict) -> Dict:
    """고객 데이터를 Notion 속성 형식으로 변환"""
    inputs = data.get('inputs', {})
    fees = data.get('fees', {})
    ltv_rates = inputs.get("ltv_rates", [""])

    # LTV 비율 안전 처리
    ltv1 = ltv_rates[0] if len(ltv_rates) > 0 else ""
    
    return {
        CUSTOMER_DB_TITLE_PROPERTY: {
            "title": [{"text": {"content": inputs.get("customer_name", "").strip()}}]
        },
        "주소": {
            "rich_text": [{"text": {"content": inputs.get("address", "").strip()}}]
        },
        "KB시세": {
            "number": parse_korean_number(inputs.get("kb_price", "0"))
        },
        "전용면적": {
            "rich_text": [{"text": {"content": inputs.get("area", "").strip()}}]
        },
        "세대수": {
            "rich_text": [{"text": {"content": str(inputs.get("unit_count", "")).strip()}}]
        },
        "준공일자": {
            "rich_text": [{"text": {"content": inputs.get("completion_date", "").strip()}}]
        },
        "소유권이전일": {
            "rich_text": [{"text": {"content": inputs.get("ownership_transfer_date", "").strip()}}]
        },
        "즉발사업자": {
            "checkbox": inputs.get("instant_business_operator", False)
        },
        "사업자발급일": {
            "rich_text": [{"text": {"content": inputs.get("business_issue_date", "").strip()}}]
        },
        "사업자등록일자": {
            "rich_text": [{"text": {"content": inputs.get("business_registration_date", "").strip()}}]
        },
        "대출가능일자": {
            "rich_text": [{"text": {"content": inputs.get("loan_available_date", "").strip()}}]
        },
        "방공제지역": {
            "rich_text": [{"text": {"content": inputs.get("deduction_region_text", "").strip()}}]
        },
        "LTV비율1": {
            "rich_text": [{"text": {"content": str(ltv1).strip()}}]
        },
        "공유자 1 지분율": {
            "rich_text": [{"text": {"content": str(inputs.get("share_rate1", "")).strip()}}]
        },
        "공유자 2 지분율": {
            "rich_text": [{"text": {"content": str(inputs.get("share_rate2", "")).strip()}}]
        },
        "컨설팅금액": {
            "number": parse_korean_number(fees.get("consult_amt", "0"))
        },
        "컨설팅수수료율": {
            "number": float(fees.get("consult_rate", "0") or 0)
        },
        "브릿지금액": {
            "number": parse_korean_number(fees.get("bridge_amt", "0"))
        },
        "브릿지수수료율": {
            "number": float(fees.get("bridge_rate", "0") or 0)
        },
    }

@handle_notion_errors
def archive_existing_loans(customer_page_id: str) -> bool:
    """기존 대출 정보를 아카이브 처리"""
    loan_query_url = f"https://api.notion.com/v1/databases/{LOAN_DB_ID}/query"
    payload = {
        "filter": {
            "property": LOAN_DB_RELATION_PROPERTY,
            "relation": {"contains": customer_page_id}
        }
    }
    
    response = requests.post(
        loan_query_url, 
        headers=NOTION_HEADERS, 
        json=payload,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    
    archived_count = 0
    for page in response.json().get("results", []):
        archive_response = requests.patch(
            f"https://api.notion.com/v1/pages/{page['id']}", 
            headers=NOTION_HEADERS, 
            json={"archived": True},
            timeout=REQUEST_TIMEOUT
        )
        if archive_response.ok:
            archived_count += 1
    
    logger.info(f"기존 대출 정보 {archived_count}건 아카이브 완료")
    return True

@handle_notion_errors
def save_loan_items(customer_page_id: str, loans_data: List[Dict]) -> bool:
    """대출 정보 저장"""
    if not customer_page_id:
        logger.error("고객 페이지 ID가 없음")
        return False
    
    # 기존 대출 정보 아카이브
    archive_existing_loans(customer_page_id)
    
    # 새 대출 정보 저장
    saved_count = 0
    for loan in loans_data:
        lender = loan.get("lender", "").strip()
        if not lender:
            continue
        
        loan_payload = {
            "parent": {"database_id": LOAN_DB_ID},
            "properties": {
                "설정자": {
                    "title": [{"text": {"content": lender}}]
                },
                "채권최고액": {
                    "number": parse_korean_number(loan.get("max_amount", "0"))
                },
                "설정비율": {
                    "number": safe_number_conversion(loan.get("ratio"))
                },
                "원금": {
                    "number": parse_korean_number(loan.get("principal", "0"))
                },
                "진행구분": {
                    "rich_text": [{"text": {"content": loan.get("status", "유지")}}]
                },
                LOAN_DB_RELATION_PROPERTY: {
                    "relation": [{"id": customer_page_id}]
                }
            }
        }
        
        loan_response = requests.post(
            "https://api.notion.com/v1/pages", 
            headers=NOTION_HEADERS, 
            json=loan_payload,
            timeout=REQUEST_TIMEOUT
        )
        
        if loan_response.ok:
            saved_count += 1
        else:
            logger.error(f"대출 정보 저장 실패: {lender} - {loan_response.text}")
    
    logger.info(f"새 대출 정보 {saved_count}건 저장 완료")
    return True

# --- CRUD 함수 ---
def create_new_customer(data: Dict) -> Dict:
    """새 고객 생성"""
    customer_name = data.get("inputs", {}).get("customer_name", "").strip()
    
    if not customer_name:
        return {"success": False, "message": "고객명이 입력되지 않았습니다."}
    
    try:
        # 중복 고객명 확인
        existing_customers = fetch_all_customers()
        if existing_customers and any(c['name'] == customer_name for c in existing_customers):
            return {"success": False, "message": f"'{customer_name}' 이름의 고객이 이미 존재합니다."}
        
        # 고객 정보 생성
        properties = format_properties_payload(data)
        payload = {
            "parent": {"database_id": CUSTOMER_DB_ID}, 
            "properties": properties
        }
        
        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=NOTION_HEADERS,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        # 에러 응답 로깅
        if response.status_code != 200:
            logger.error(f"Notion API 에러 응답: {response.status_code}")
            logger.error(f"에러 내용: {response.text}")

        response.raise_for_status()
        
        new_page_id = response.json().get("id")
        if new_page_id:
            # 대출 정보 저장
            loans_data = data.get("loans", [])
            if loans_data:
                save_loan_items(new_page_id, loans_data)
        
        logger.info(f"새 고객 '{customer_name}' 생성 완료")
        return {"success": True, "message": f"'{customer_name}' 고객 정보가 새로 저장되었습니다."}
        
    except Exception as e:
        logger.error(f"신규 고객 생성 실패: {e}")
        return {"success": False, "message": f"신규 저장 실패: {str(e)}"}

def update_customer(page_id: str, data: Dict) -> Dict:
    """고객 정보 업데이트"""
    customer_name = data.get("inputs", {}).get("customer_name", "").strip()
    
    if not customer_name:
        return {"success": False, "message": "고객명이 입력되지 않았습니다."}
    
    if not page_id:
        return {"success": False, "message": "유효하지 않은 고객 ID입니다."}
    
    try:
        # 고객 기본 정보 업데이트
        properties = format_properties_payload(data)
        response = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}", 
            headers=NOTION_HEADERS, 
            json={"properties": properties},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        # 대출 정보 업데이트
        loans_data = data.get("loans", [])
        save_loan_items(page_id, loans_data)
        
        logger.info(f"고객 '{customer_name}' 정보 업데이트 완료")
        return {"success": True, "message": f"'{customer_name}' 고객 정보가 수정되었습니다."}
        
    except Exception as e:
        logger.error(f"고객 정보 업데이트 실패: {e}")
        return {"success": False, "message": f"수정 실패: {str(e)}"}

def delete_customer(page_id: str) -> Dict:
    """고객 삭제 (아카이브)"""
    if not page_id:
        return {"success": False, "message": "유효하지 않은 고객 ID입니다."}
    
    try:
        # 관련 대출 정보 아카이브
        archive_existing_loans(page_id)
        
        # 고객 정보 아카이브
        response = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}", 
            headers=NOTION_HEADERS, 
            json={"archived": True},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        logger.info(f"고객 (ID: {page_id}) 삭제 완료")
        return {"success": True, "message": "고객 정보가 삭제(보관)되었습니다."}
        
    except Exception as e:
        logger.error(f"고객 삭제 실패: {e}")
        return {"success": False, "message": f"고객 삭제 실패: {str(e)}"}

# --- 설정 검증 함수 ---
def validate_notion_config() -> bool:
    """Notion 설정 유효성 검증"""
    if not NOTION_TOKEN or not CUSTOMER_DB_ID or not LOAN_DB_ID:
        logger.error("Notion API 설정이 완전하지 않습니다.")
        return False
    
    try:
        # 간단한 API 호출로 연결 테스트
        response = requests.get(
            f"https://api.notion.com/v1/databases/{CUSTOMER_DB_ID}",
            headers=NOTION_HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        logger.info("Notion API 연결 확인 완료")
        return True
        
    except Exception as e:
        logger.error(f"Notion API 연결 실패: {e}")
        return False

# 초기화 시 설정 검증
if __name__ == "__main__":
    validate_notion_config()




