import fitz  # PyMuPDF 라이브러리
import re

def extract_address(text):
    """텍스트에서 주소를 추출합니다."""
    match = re.search(r"\[집합건물\]\s*([^\n]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"소재지\s*[:：]?\s*([^\n]+)", text)
    if match:
        return match.group(1).strip()
    return ""

def extract_area(text):
    """텍스트에서 전용 면적을 추출합니다."""
    area_section_match = re.search(r"전유부분의 건물의 표시([\s\S]*?)대지권의 표시", text)
    search_text = area_section_match.group(1) if area_section_match else text
    matches = re.findall(r"(\d+\.\d+)\s*㎡", search_text.replace('\n', ' '))
    return matches[-1] if matches else ""

def extract_owner_info(text):

    summary_section_match = re.search(r"주요 등기사항 요약([\s\S]*)", text)
    if not summary_section_match:
        return ""

    summary_text = summary_section_match.group(1)
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

    owner_details = []
    for i, line in enumerate(lines):
        # '소유자' 또는 '공유자' 키워드가 있는 라인에서 이름(한글)을 찾습니다.
        owner_match = re.search(r"([가-힣]{2,})\s*\(?(소유자|공유자)\)?", line)
        if owner_match and i + 1 < len(lines):
            name = owner_match.group(1)
            
            # 바로 다음 줄에서 'nnnnnn-' 형태의 생년월일을 찾습니다.
            birth_match = re.search(r"(\d{6})-", lines[i+1])
            if birth_match:
                birth = birth_match.group(1)
                owner_details.append(f"{name} {birth}")
    
    return ", ".join(owner_details)

def parse_pdf_for_ltv(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text")
        doc.close()
        
        address = extract_address(full_text)
        area = extract_area(full_text)
        customer_details = extract_owner_info(full_text)
        
        # 고객명에 모든 정보를 담고, 생년월일 필드는 비웁니다.
        return {
            "customer_name": customer_details,
            "birth_date": "", 
            "address": address,
            "area": area
        }
    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return {}
