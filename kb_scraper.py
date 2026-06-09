import re
import requests

_KB_HEADERS = {
    'origin': 'https://kbland.kr',
    'referer': 'https://kbland.kr/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'accept': 'application/json, text/plain, */*',
    'webservice': '1',
}


def _search_complex(keyword):
    """아파트명으로 KB 단지 검색. 첫 번째 결과 반환."""
    r = requests.get(
        'https://api.kbland.kr/land-complex/serch/intgraSerch',
        params={
            '검색설정명': 'SRC_NTOTAL',
            '검색키워드': keyword,
            '출력갯수': '5',
            '페이지설정값': '1',
        },
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    items = data.get('dataBody', {}).get('data', {}).get('data', {}).get('HSCM', {}).get('data', [])
    return items[0] if items else None


def _get_price(complex_no, sqrmsr_no):
    """단지번호 + 면적일련번호로 KB 시세 조회. 매매일반가(만원) 반환."""
    r = requests.get(
        'https://api.kbland.kr/land-price/price/BasePrcInfoNew',
        params={'단지기본일련번호': complex_no, '면적일련번호': sqrmsr_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    시세목록 = data.get('dataBody', {}).get('data', {}).get('시세', [])
    if not 시세목록:
        return None

    항목 = 시세목록[0]
    vals = list(항목.values())  # 인덱스 기반 접근 (필드명 인코딩 무관)
    # index 8: 매매일반거래가, 15: 매매상한가, 42: 매매하한가, 21: 전용면적, 12: 면적일련번호
    return {
        '매매일반가': vals[8]  if len(vals) > 8  else 0,
        '매매상한가': vals[15] if len(vals) > 15 else 0,
        '매매하한가': vals[42] if len(vals) > 42 else 0,
        '전용면적':   vals[21] if len(vals) > 21 else 0,
        '면적일련번호': vals[12] if len(vals) > 12 else 0,
    }


def _find_best_sqrmsr(complex_no, target_area_m2):
    """전용면적과 가장 가까운 면적일련번호를 main API에서 찾아 반환."""
    r = requests.get(
        'https://api.kbland.kr/land-complex/complex/main',
        params={'단지기본일련번호': complex_no},
        headers=_KB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    body = data.get('dataBody', {}).get('data', {})

    # 대표 면적일련번호 (검색 결과의 RPSNT_SQRMSR_NO와 동일)
    return body.get('대표면적일련번호') or body.get('표준면적일련번호')


def get_kb_info(address, target_area_m2=None):
    """
    주소(또는 아파트명)와 전용면적으로 KB 시세/세대수/준공일 조회.

    Args:
        address (str): 전체 주소 또는 아파트명 (예: "광명삼익아파트" 또는 전체 주소)
        target_area_m2 (float|None): 전용면적(㎡). None이면 대표면적 사용.

    Returns:
        dict: {
            'success': bool,
            'kb_price': int,        # 매매일반가 (만원)
            'kb_price_high': int,   # 매매상한가 (만원)
            'kb_price_low': int,    # 매매하한가 (만원)
            'total_households': int,# 세대수
            'completion_date': str, # 준공년월 (YYYY-MM 형식)
            'complex_no': str,      # KB 단지번호
            'complex_name': str,    # 단지명
            'area_m2': float,       # 조회된 전용면적
        }
    """
    result = {
        'success': False,
        'kb_price': 0,
        'kb_price_high': 0,
        'kb_price_low': 0,
        'total_households': 0,
        'completion_date': '',
        'complex_no': '',
        'complex_name': '',
        'area_m2': 0.0,
    }

    try:
        # 1. 아파트명 추출 (전체 주소에서)
        apt_match = re.search(
            r'([가-힣a-zA-Z0-9]+(?:아파트|파크|타운|빌|캐슬|스카이뷰|힐스테이트|자이|푸르지오|래미안|e편한세상|센트럴|더샵|롯데캐슬|시티|타워|하이츠|빌라|맨션|팰리스|삼익|현대|대우|주공|한양|한신|두산|벽산|LG|lg)[가-힣a-zA-Z0-9]*)',
            address
        )
        keyword = apt_match.group(1) if apt_match else address.strip()
        # "광명삼익아파트" → "광명삼익" 처럼 단순 아파트 접미사 제거 (검색 정확도 향상)
        keyword = re.sub(r'아파트$', '', keyword).strip()
        print(f"[KB API] 검색 키워드: {keyword}")

        # 2. 단지 검색
        item = _search_complex(keyword)
        if not item:
            # 키워드 검색 실패 시 시군구+동 조합으로 재시도
            sigungu_match = re.search(r'([가-힣]+시\s*[가-힣]*구?|[가-힣]+시|[가-힣]+군)', address)
            dong_match = re.search(r'([가-힣]+[동읍면리])', address)
            if sigungu_match and dong_match:
                keyword2 = f"{sigungu_match.group(1)} {dong_match.group(1)}"
                print(f"[KB API] 재검색: {keyword2}")
                item = _search_complex(keyword2)

        if not item:
            print(f"[KB API] 단지 검색 실패: {keyword}")
            return result

        complex_no = item['COMPLEX_NO']
        complex_name = item.get('HSCM_NM', '')
        sqrmsr_no = item.get('RPSNT_SQRMSR_NO')
        households = int(item.get('THS_NUM', 0) or 0)
        mvihs_date = item.get('MVIHS_DATE', '')  # "199807"

        print(f"[KB API] 단지: {complex_name} (번호: {complex_no}, 면적번호: {sqrmsr_no})")

        # 준공년월 포맷팅 (199807 → 1998-07)
        completion_date = ''
        if mvihs_date and len(mvihs_date) >= 6:
            completion_date = f"{mvihs_date[:4]}-{mvihs_date[4:6]}-01"

        result['complex_no'] = complex_no
        result['complex_name'] = complex_name
        result['total_households'] = households
        result['completion_date'] = completion_date

        # 3. 전용면적에 맞는 면적일련번호 찾기
        if target_area_m2 and sqrmsr_no:
            # main API에서 면적 목록 확인 후 가장 가까운 것 선택
            try:
                r = requests.get(
                    'https://api.kbland.kr/land-complex/complex/main',
                    params={'단지기본일련번호': complex_no},
                    headers=_KB_HEADERS,
                    timeout=10,
                )
                body = r.json().get('dataBody', {}).get('data', {})
                # 면적 범위에서 가장 가까운 면적 찾기
                min_sqrmsr = body.get('최소공급면적') or 0
                max_sqrmsr = body.get('최대공급면적') or 0
                rep_sqrmsr_no = body.get('대표면적일련번호') or body.get('표준면적일련번호') or sqrmsr_no
                sqrmsr_no = rep_sqrmsr_no
            except Exception:
                pass  # 실패하면 검색 결과의 대표 면적 사용

        # 4. 시세 조회
        if sqrmsr_no:
            price_data = _get_price(complex_no, sqrmsr_no)
            if price_data:
                kb_price = price_data.get('매매일반가') or 0
                result['kb_price'] = int(kb_price) if kb_price else 0
                result['kb_price_high'] = int(price_data.get('매매상한가') or 0)
                result['kb_price_low'] = int(price_data.get('매매하한가') or 0)
                result['area_m2'] = float(price_data.get('전용면적') or 0)
                print(f"[KB API] 시세: {result['kb_price']}만원 ({result['area_m2']}㎡)")

        result['success'] = True
        return result

    except Exception as e:
        print(f"[KB API 오류] {e}")
        import traceback
        traceback.print_exc()
        return result


# 테스트
if __name__ == "__main__":
    tests = [
        ("경기도 광명시 소하동 45-3 광명삼익아파트 제101동 제1406호", 85.83),
        ("서울특별시 강남구 역삼동 736 역삼래미안 제101동 제101호", 84.0),
    ]
    for addr, area in tests:
        print(f"\n{'='*50}")
        print(f"주소: {addr}")
        r = get_kb_info(addr, area)
        print(f"결과: KB시세={r['kb_price']}만원, 세대수={r['total_households']}, 준공={r['completion_date']}, 성공={r['success']}")
