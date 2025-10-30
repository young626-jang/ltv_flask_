import fitz  # PyMuPDF 라이브러리
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

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
        viewing_date = datetime.strptime(viewing_datetime, "%Y-%m-%d %H:%M:%S")
        current_date = datetime.now()
        
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

def _extract_text_from_pdf(filepath: str) -> str:
    """PDF 파일에서 텍스트를 추출합니다."""
    try:
        doc = fitz.open(filepath)
        full_text = ""
        for page in doc:
            full_text += page.get_text("text")
        doc.close()
        return full_text
    except Exception as e:
        print(f"PDF 텍스트 추출 중 오류 발생: {e}")
        return ""

def parse_pdf_for_ltv(pdf_path):
    try:
        full_text = _extract_text_from_pdf(pdf_path)
        if not full_text:
            return {}

        # 1. 텍스트를 구조화된 섹션으로 분리
        sections = _split_text_into_sections(full_text)

        # 2. 섹션 기반으로 정보 추출
        address = _parse_address(sections.get('full', ''))
        area = _parse_area(sections.get('full', ''))
        customer_details = _parse_owners(sections)

        # 열람일시와 나이 검사 추가
        viewing_datetime = extract_viewing_datetime(full_text)
        age_check = check_registration_age(viewing_datetime)

        # 3. 섹션 기반으로 심사 기준 분석 실행
        eligibility_checks = analyze_eligibility_from_sections(sections)

        return {
            "customer_name": customer_details,
            "birth_date": "",
            "address": address,
            "area": area,
            "viewing_datetime": viewing_datetime,
            "age_check": age_check,
            "eligibility_checks": eligibility_checks
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


def extract_owner_shares_with_birth(full_text):
    """
    등기부등본 텍스트에서 '이름 생년월일 지분율' 형태로 추출합니다.
    (예: '이승욱 810319 지분율 1/2 (50.0%)')

    Args:
        full_text (str): PDF에서 추출된 전체 텍스트

    Returns:
        list: 소유자별 지분 정보 리스트
    """
    try:
        # '주요 등기사항 요약' 섹션으로 검색 범위를 좁혀 정확도 향상
        summary_match = re.search(r"주요 등기사항 요약([\s\S]*)", full_text)
        if not summary_match:
            return []
        summary_text = summary_match.group(1)
        lines = [line.strip() for line in summary_text.splitlines() if line.strip()]

        owner_details = []
        num_owners = 0
        # 먼저 공유자 수를 센다
        for line in lines:
            if re.search(r"([가-힣]{2,})\s*\((소유자|공유자)\)", line):
                num_owners += 1

        results = []
        # 소유자 정보를 순차적으로 파싱
        for i, line in enumerate(lines):
            name_match = re.search(r"([가-힣]{2,})\s*\((소유자|공유자)\)", line)
            if name_match:
                name = name_match.group(1)
                birth = ""
                share_info = ""

                # 다음 줄에서 생년월일 찾기
                if i + 1 < len(lines) and re.search(r"^\d{6}-", lines[i+1]):
                    birth = re.search(r"(\d{6})-", lines[i+1]).group(1)

                # 다음 두 줄 내에서 지분 정보 찾기
                for j in range(i + 1, min(i + 3, len(lines))):
                    share_match = re.search(r"지분\s*(\d+)\s*분의\s*(\d+)", lines[j])
                    if share_match:
                        denom, num = int(share_match.group(1)), int(share_match.group(2))
                        percent = round(num / denom * 100, 1)
                        share_info = f"지분율 {num}/{denom} ({percent}%)"
                        break
                
                # 지분 정보가 없으면 단독/공동 소유에 따라 처리
                if not share_info:
                    if num_owners > 1:
                        percent = round(100 / num_owners, 1)
                        share_info = f"지분율 1/{num_owners} ({percent}%)"
                    else:
                        share_info = "지분율 1/1 (100.0%)"

                if name and birth:
                    results.append(f"{name} {birth}  {share_info}")

        return results

    except Exception as e:
        print(f"PDF 파싱 중 오류 발생: {e}")
        return []
    
# <<< 여기에 근저당권 분석 함수를 추가합니다 >>>
def extract_rights_info(full_text):
    
    # 1. '시작/종료 마커'로 테이블 영역을 정확히 추출
    table_match = re.search(
        r'3\.\s*\([근|전].*?대상소유자([\s\S]*?)\[\s*참\s*고\s*사\s*항\s*\]',
        full_text,
        re.DOTALL
    )
    if not table_match:
        return {"근저당권": []}
    
    table_text = table_match.group(1)

    # 2. 테이블 내용을 '순위번호' 기준으로 모든 항목을 임시 리스트에 저장
    entries = re.split(r'\n\s*(?=(?:\d{1,2}-\d{1,2}|\d{1,2})\s)', table_text)
    
    all_entries = []
    for entry_text in entries:
        clean_text = ' '.join(entry_text.split())
        if not clean_text: continue

        seq_match = re.search(r'^\s*(\d{1,2}(?:-\d{1,2})?)', entry_text)
        if not seq_match: continue
        
        seq = seq_match.group(1)
        main_key = seq.split('-')[0]

        date_match = re.search(r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)', clean_text)
        amount_match = re.search(r'채권최고액\s*금\s*([\d,]+)원', clean_text)
        creditor_match = re.search(r'근저당권자\s*(\S+)', clean_text)

        info_parts = []
        if amount_match:
            info_parts.append(f"채권최고액 금{amount_match.group(1)}원")
        if creditor_match:
            info_parts.append(f"근저당권자 {creditor_match.group(1)}")
        
        if info_parts:
            all_entries.append({
                'main_key': main_key,
                '접수일': date_match.group(1).strip() if date_match else "",
                '주요등기사항': " ".join(info_parts)
            })

    # 3. [수정됨] 이력 덮어쓰기 로직: 누락된 정보를 원본에서 가져와 병합
    final_mortgages = {}
    for entry in reversed(all_entries):
        if entry['main_key'] not in final_mortgages:
            # 원본 항목(보통 채권최고액이 명시된 첫 항목)을 찾음
            original_info = next((item for item in all_entries if item['main_key'] == entry['main_key'] and '채권최고액' in item['주요등기사항']), None)
            
            if original_info:
                # 현재 항목에 '채권최고액'이 없으면 원본에서 가져와 맨 앞에 추가
                if '채권최고액' not in entry['주요등기사항']:
                    amount_part = re.search(r'채권최고액\s*금[\d,]+원', original_info['주요등기사항'])
                    if amount_part:
                        entry['주요등기사항'] = amount_part.group(0) + " " + entry['주요등기사항']
                
                # 현재 항목에 '근저당권자'가 없으면 원본에서 가져와 뒤에 추가
                if '근저당권자' not in entry['주요등기사항']:
                    creditor_part = re.search(r'근저당권자\s*\S+', original_info['주요등기사항'])
                    if creditor_part:
                        entry['주요등기사항'] += " " + creditor_part.group(0)

            final_mortgages[entry['main_key']] = entry
            
    # 4. 원래 순서대로 정렬하여 반환
    sorted_final_list = sorted(list(final_mortgages.values()), key=lambda x: int(x['main_key']))

    return {"근저당권": sorted_final_list}

def extract_ownership_transfer_date(text):
    """
    등기부등본 텍스트의 【갑구】에서 '소유권이전' 항목들의 '접수일'을 정확히 파싱하여
    가장 최신 날짜를 "YYYY-MM-DD" 형식으로 반환합니다.

    [핵심 로직]
    1. '갑구' 섹션 전체를 추출하여 검색 범위를 한정합니다.
    2. '순위번호'를 기준으로 '갑구'를 개별 등기 항목으로 분리합니다.
    3. 각 항목별로 등기 목적이 '소유권이전'인지 명확히 확인합니다.
       - '등기명의인표시변경' 등 다른 목적의 항목은 철저히 배제합니다.
    4. '소유권이전'이 맞는 항목에서만 날짜(접수일)를 추출합니다.
    5. 추출된 모든 '소유권이전' 날짜 중 가장 최신 날짜를 찾아 반환합니다.
    """
    try:
        # 1. 【갑구】 섹션 전체 텍스트를 정확하게 추출합니다.
        kapgu_match = re.search(
            r'【\s*갑\s*구\s*】([\s\S]*?)(?=【\s*을\s*구\s*】|주요 등기사항 요약)',
            text,
            re.DOTALL
        )
        if not kapgu_match:
            print("오류: 【갑구】 섹션을 찾을 수 없습니다.")
            return ""
        kapgu_text = kapgu_match.group(1)

        # 2. '순위번호'를 기준으로 갑구 내용을 개별 등기 항목으로 분리합니다.
        # 순위번호는 라인 시작 부분의 '숫자' 또는 '숫자-숫자' 형식입니다.
        entries = re.split(r'\n\s*(?=\d{1,2}(?:-\d{1,2})?\s)', kapgu_text)

        ownership_dates = []
        date_pattern = r'(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)'

        # 3. 각 등기 항목을 순회하며 분석합니다.
        for entry in entries:
            entry_text = entry.strip()
            if not entry_text:
                continue

            # 3-1. 등기 목적이 '소유권이전'인지 명확히 판별합니다.
            # 항목의 첫 부분에 '소유권이전'이 있는지 확인하고, '표시변경' 등 다른 키워드는 없는지 확인합니다.
            # 여러 줄일 수 있으므로 줄바꿈을 공백으로 합쳐서 분석합니다.
            purpose_check_text = ' '.join(entry_text.splitlines()[:2]) # 보통 목적은 첫 두 줄 안에 있음

            if '소유권이전' in purpose_check_text and '등기명의인표시' not in purpose_check_text:

                # 4. 해당 항목 내에서 날짜(접수일)를 찾습니다.
                date_match = re.search(date_pattern, entry_text)

                if date_match:
                    date_str = date_match.group(1)
                    # 날짜 문자열에서 공백 제거 후 datetime 객체로 변환
                    cleaned_date_str = re.sub(r'\s+', '', date_str)
                    dt_obj = datetime.strptime(cleaned_date_str, "%Y년%m월%d일")
                    ownership_dates.append(dt_obj)

        # 5. 추출된 모든 소유권이전 날짜 중 가장 최신 날짜를 찾아 반환합니다.
        if not ownership_dates:
            print("오류: '소유권이전' 항목에서 유효한 날짜를 찾지 못했습니다.")
            return ""

        latest_date = max(ownership_dates)
        return latest_date.strftime('%Y-%m-%d')

    except Exception as e:
        print(f"소유권 이전일 파싱 중 오류 발생: {e}")
        return ""
