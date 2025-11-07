# 메리츠캐피탈 급지 분류 및 LTV 기준 시스템

# 1. 급지 분류 (1군, 2군, 3군)
REGION_CLASSIFICATION = {
    "1군": {
        "서울": [
            "강남구", "서초구", "송파구", "강동구", "마포구", "서대문구",
            "종로구", "중구", "용산구", "영등포구", "동작구", "관악구",
            "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구",
            "노원구", "도봉구", "은평구", "서북구", "양천구", "구로구"
        ],
        "인천": ["계양구", "부평구", "연수구", "미추홀구"],
        "경기": [
            "용인", "과천", "광명", "구리", "군포", "부천", "성남",
            "수원", "안양", "의왕", "하남", "김포", "남양주"
        ]
    },
    "2군": {
        "인천": ["남동구", "서구", "동구", "중구"],
        "경기": [
            "시흥", "안산", "화성", "의정부", "양주", "고양",
            "광주", "동두천", "오산", "이천", "파주"
        ]
    },
    "3군": {
        "경기": ["평택", "안성", "여주", "포천"]
    }
}

# 유의지역 (1군에 속하지만 LTV 80% 제한)
CAUTION_REGIONS = {
    "서울": ["중랑구", "관악구", "강북구", "성북구", "노원구", "도봉구"],
    "경기": ["구리", "남양주"],
    "인천": ["계양구", "부평구", "연수구", "미추홀구"]
}

# 2. LTV 기준 테이블 (급지별, 면적별, 선후순위별)
LTV_STANDARDS = {
    "1군": {
        "선순위": {
            "95.9": 80.0,      # 95.9㎡ 이하
            "135": 75.0,       # 95.9㎡ 초과 ~ 135㎡ 이하
            "135+": 60.0       # 135㎡ 초과
        },
        "후순위": {
            "95.9": 80.0,
            "135": 80.0,
            "135+": 70.0
        }
    },
    "2군": {
        "선순위": {
            "95.9": 75.0,
            "135": 70.0,
            "135+": 55.0
        },
        "후순위": {
            "95.9": 80.0,
            "135": 75.0,
            "135+": 65.0
        }
    },
    "3군": {
        "선순위": {
            "95.9": 70.0,
            "135": 65.0,
            "135+": 50.0
        },
        "후순위": {
            "95.9": 75.0,
            "135": 70.0,
            "135+": 60.0
        }
    }
}


def get_region_grade(address):
    """
    주소에서 급지(1군, 2군, 3군) 자동 판단

    Args:
        address (str): 주소 문자열

    Returns:
        str: '1군', '2군', '3군', 또는 '미분류'
    """
    if not address:
        return "미분류"

    address = address.upper()

    # 3군 확인
    for city, districts in REGION_CLASSIFICATION.get("3군", {}).items():
        for district in districts:
            if district.upper() in address or district in address:
                return "3군"

    # 2군 확인
    for city, districts in REGION_CLASSIFICATION.get("2군", {}).items():
        for district in districts:
            if district.upper() in address or district in address:
                return "2군"

    # 1군 확인
    for city, districts in REGION_CLASSIFICATION.get("1군", {}).items():
        if city.upper() in address or city in address:
            for district in districts:
                if district.upper() in address or district in address:
                    return "1군"

    return "미분류"

def is_caution_region(address):
    """
    유의지역 여부 확인 (LTV 80% 제한)

    Args:
        address (str): 주소 문자열

    Returns:
        bool: 유의지역이면 True
    """
    if not address:
        return False

    for city, districts in CAUTION_REGIONS.items():
        if city in address:
            for district in districts:
                if district in address:
                    return True
    return False

def get_ltv_standard(region_grade, area, is_senior):
    """
    급지, 면적, 선후순위에 따른 LTV 기준값 반환

    Args:
        region_grade (str): '1군', '2군', '3군'
        area (float): 면적 (㎡ 단위)
        is_senior (bool): True=선순위, False=후순위

    Returns:
        float: LTV 기준값 (%)
    """
    if region_grade not in LTV_STANDARDS:
        return 60.0  # 기본값

    position = "선순위" if is_senior else "후순위"
    area_standards = LTV_STANDARDS[region_grade][position]

    if area is None or area <= 0:
        area = 95.9

    # 면적에 따른 기준값 선택
    if area <= 95.9:
        return area_standards["95.9"]
    elif area <= 135:
        return area_standards["135"]
    else:
        return area_standards["135+"]

