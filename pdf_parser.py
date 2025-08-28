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
    return f"{matches[-1]}㎡" if matches else ""

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

def extract_owner_shares_linewise(pdf_path):
    """
    PDF에서 각 라인별로 소유자 이름, 주민등록번호, 지분율을 추출합니다.
    기존 함수들과 독립적으로 동작합니다.
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join([page.get_text("text") for page in doc])
        doc.close()

        # "주요 등기사항 요약" 이후 부분만 사용
        summary_match = re.search(r"주요 등기사항 요약([\s\S]*)", full_text)
        if not summary_match:
            return []

        summary_text = summary_match.group(1)
        lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

        results = []
        for line in lines:
            # 이름 + 주민번호 + 지분율이 한 줄에 있는 경우 매칭
            match = re.search(
                r"([가-힣]{2,})\s*\(공유자\)\s*(\d{6}-\*+|\d{6}-\d{7})\s*지분\s*(\d+)분의\s*(\d+)",
                line
            )
            if match:
                name = match.group(1)
                rrn = match.group(2)
                denom, num = int(match.group(3)), int(match.group(4))
                percent = round(num / denom * 100, 2)
                results.append({
                    "이름": name,
                    "주민번호": rrn,
                    "지분": f"{num}/{denom}",
                    "지분율": f"{percent}%"
                })
        return results
    
    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return []


def extract_owner_shares_with_birth(pdf_path):
    """
    PDF에서 '이름 생년월일 지분율' 형태로 추출합니다.
    (예: '이승욱 810319 지분율 1/2 (50.0%)')
    """
    try:
        import fitz, re
        doc = fitz.open(pdf_path)
        full_text = "\n".join([page.get_text("text") for page in doc])
        doc.close()

        results = []
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        
        # 소유자 정보를 찾기 위한 패턴들
        owner_info = {}
        
        for i, line in enumerate(lines):
            # 이름과 공유자 패턴 찾기
            name_match = re.search(r"([가-힣]{2,})\s*\(공유자\)", line)
            if name_match:
                name = name_match.group(1)
                
                # 다음 줄에서 주민번호 찾기
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    birth_match = re.search(r"(\d{6})-", next_line)
                    if birth_match:
                        birth = birth_match.group(1)
                        
                        # 그 다음 줄에서 지분 정보 찾기
                        if i + 2 < len(lines):
                            share_line = lines[i + 2]
                            share_match = re.search(r"(\d+)분의\s*(\d+)", share_line)
                            if share_match:
                                denom = int(share_match.group(1))
                                num = int(share_match.group(2))
                                percent = round(num / denom * 100, 1)
                                results.append(f"{name} {birth}  지분율 {num}/{denom} ({percent}%)")
                            else:
                                # 지분이 명시되지 않은 경우 공동소유로 가정
                                owner_info[name] = birth
        
        # 지분 정보가 명확하지 않은 경우 공동소유로 처리
        if not results and owner_info:
            num_owners = len(owner_info)
            if num_owners > 1:
                for name, birth in owner_info.items():
                    percent = round(100 / num_owners, 1)
                    results.append(f"{name} {birth}  지분율 1/{num_owners} ({percent}%)")
        
        return results

    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return []
