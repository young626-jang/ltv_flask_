import fitz  # PyMuPDF 라이브러리
import re
import datetime

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
    
    # 줄바꿈으로 분리된 면적 처리 (박규생님 등기 등)
    clean_text = re.sub(r'구조(\d+)\s*\n\s*\.', r'구조\1.', search_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    matches = re.findall(r"(\d+\.\d+)\s*㎡", clean_text)
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

def extract_viewing_datetime(text):
    """텍스트에서 열람일시를 추출합니다."""
    patterns = [
        r'열람일시\s*[:：]?\s*(\d{4})년(\d{2})월(\d{2})일\s*(\d{2})시(\d{2})분(\d{2})초',
        r'열람일시\s*[:：]?\s*(\d{4})[년/\-](\d{1,2})[월/\-](\d{1,2})[일]?\s*(\d{1,2})[시:](\d{1,2})[분:](\d{1,2})[초]?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}:{second.zfill(2)}"
    
    return ""

def check_registration_age(viewing_datetime):
    """등기 열람일시가 한 달 이상 오래되었는지 확인"""
    if not viewing_datetime:
        return {"is_old": False, "age_days": 0, "message": "열람일시를 찾을 수 없습니다"}
    
    try:
        # 열람일시를 datetime 객체로 변환
        viewing_date = datetime.datetime.strptime(viewing_datetime, "%Y-%m-%d %H:%M:%S")
        current_date = datetime.datetime.now()
        
        # 날짜 차이 계산 (실제 경과 일수로 계산)
        age_delta = current_date - viewing_date
        age_days = round(age_delta.total_seconds() / 86400)
        
        # 한 달(30일) 이상 차이나는지 확인
        is_old = age_days >= 30
        
        if is_old:
            message = f"⚠️ 주의: 등기가 {age_days}일 전 데이터입니다 (한 달 이상 경과)"
        elif age_days > 7:
            message = f"등기가 {age_days}일 전 데이터입니다"
        else:
            message = f"최신 등기 데이터입니다 ({age_days}일 전)"
            
        return {
            "is_old": is_old,
            "age_days": age_days,
            "message": message,
            "viewing_date": viewing_datetime,
            "current_date": current_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {"is_old": False, "age_days": 0, "message": f"날짜 분석 오류: {str(e)}"}

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
        
        # 열람일시와 나이 검사 추가
        viewing_datetime = extract_viewing_datetime(full_text)
        age_check = check_registration_age(viewing_datetime)
        
        return {
            "customer_name": customer_details,
            "birth_date": "", 
            "address": address,
            "area": area,
            "viewing_datetime": viewing_datetime,
            "age_check": age_check
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
    
# <<< 여기에 근저당권 분석 함수를 추가합니다 >>>
def extract_rights_info(full_text):
    """
    텍스트에서 '주요 등기사항 요약'의 근저당권 정보를 추출하여 최종 상태 목록을 반환합니다.
    """
    table_match = re.search(
        r'3\.\s*\([근|전].*?대상소유자([\s\S]*?)\[\s*참\s*고\s*사\s*항\s*\]',
        full_text,
        re.DOTALL
    )
    if not table_match:
        return {"근저당권": []}
    
    table_text = table_match.group(1)
    entries = re.split(r'\n\s*(?=(?:\d{1,2}-\d{1,2}|\d{1,2})\s)', table_text)
    
    all_entries = []
    for entry_text in entries:
        clean_text = ' '.join(entry_text.split())
        if not clean_text: continue

        seq_match = re.search(r'^\s*(\d{1,2}(?:-\d{1,2})?)', entry_text)
        if not seq_match: continue
        
        seq = seq_match.group(1)
        main_key = seq.split('-')[0]

        amount_match = re.search(r'채권최고액\s*금\s*([\d,]+)원', clean_text)
        creditor_match = re.search(r'근저당권자\s*(\S+)', clean_text)

        info_parts = []
        if amount_match: info_parts.append(f"채권최고액 금{amount_match.group(1)}원")
        if creditor_match: info_parts.append(f"근저당권자 {creditor_match.group(1)}")
        
        if info_parts:
            all_entries.append({
                'main_key': main_key,
                '주요등기사항': " ".join(info_parts)
            })

    final_mortgages = {}
    for entry in reversed(all_entries):
        if entry['main_key'] not in final_mortgages:
            original_info = next((item for item in all_entries if item['main_key'] == entry['main_key'] and '근저당권자' in item['주요등기사항']), None)
            if '근저당권자' not in entry['주요등기사항'] and original_info:
                 creditor_part = re.search(r'근저당권자\s*\S+', original_info['주요등기사항'])
                 if creditor_part:
                     entry['주요등기사항'] += " " + creditor_part.group(0)
            final_mortgages[entry['main_key']] = entry
            
    sorted_final_list = sorted(list(final_mortgages.values()), key=lambda x: int(x['main_key']))
    return {"근저당권": sorted_final_list}
