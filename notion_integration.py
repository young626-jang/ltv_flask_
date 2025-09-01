from notion_client import Client
import json
from datetime import datetime
from typing import Dict, List, Optional

class NotionAPI:
    def __init__(self, token: str):
        """Notion API 클라이언트 초기화"""
        self.notion = Client(auth=token)
        
    def get_page(self, page_id: str) -> Dict:
        """페이지 정보 가져오기"""
        try:
            page = self.notion.pages.retrieve(page_id)
            return {
                'success': True,
                'data': page
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_page_content(self, page_id: str) -> Dict:
        """페이지 내용 가져오기"""
        try:
            blocks = self.notion.blocks.children.list(block_id=page_id)
            content = []
            
            for block in blocks['results']:
                block_type = block['type']
                block_content = self._extract_block_content(block, block_type)
                if block_content:
                    content.append({
                        'type': block_type,
                        'content': block_content,
                        'id': block['id']
                    })
            
            return {
                'success': True,
                'data': content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_block_content(self, block: Dict, block_type: str) -> str:
        """블록에서 텍스트 내용 추출"""
        text_blocks = ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                      'bulleted_list_item', 'numbered_list_item', 'to_do']
        
        if block_type in text_blocks and block_type in block:
            rich_text = block[block_type].get('rich_text', [])
            return ''.join([t.get('plain_text', '') for t in rich_text])
        return ''
    
    def create_page(self, parent_id: str, title: str, content: str = '') -> Dict:
        """새 페이지 생성"""
        try:
            new_page = self.notion.pages.create(
                parent={'page_id': parent_id},
                properties={
                    'title': {
                        'title': [
                            {
                                'text': {
                                    'content': title
                                }
                            }
                        ]
                    }
                }
            )
            
            # 내용이 있으면 블록 추가
            if content:
                self.add_block(new_page['id'], content)
            
            return {
                'success': True,
                'data': new_page
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_block(self, page_id: str, content: str, block_type: str = 'paragraph') -> Dict:
        """페이지에 블록 추가"""
        try:
            block = self.notion.blocks.children.append(
                block_id=page_id,
                children=[
                    {
                        block_type: {
                            'rich_text': [
                                {
                                    'text': {
                                        'content': content
                                    }
                                }
                            ]
                        }
                    }
                ]
            )
            return {
                'success': True,
                'data': block
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_page(self, page_id: str, properties: Dict) -> Dict:
        """페이지 속성 업데이트"""
        try:
            updated_page = self.notion.pages.update(
                page_id=page_id,
                properties=properties
            )
            return {
                'success': True,
                'data': updated_page
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_pages(self, query: str = '', page_size: int = 10) -> Dict:
        """페이지 검색"""
        try:
            results = self.notion.search(
                query=query,
                page_size=page_size,
                filter={'property': 'object', 'value': 'page'}
            )
            return {
                'success': True,
                'data': results['results']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def backup_page(self, page_id: str, backup_path: str = None) -> Dict:
        """페이지 백업"""
        try:
            # 페이지 정보 가져오기
            page_info = self.get_page(page_id)
            if not page_info['success']:
                return page_info
            
            # 페이지 내용 가져오기
            page_content = self.get_page_content(page_id)
            if not page_content['success']:
                return page_content
            
            # 백업 데이터 구성
            backup_data = {
                'page_info': page_info['data'],
                'page_content': page_content['data'],
                'backup_time': datetime.now().isoformat()
            }
            
            # 파일로 저장
            if backup_path is None:
                backup_path = f"notion_backup_{page_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return {
                'success': True,
                'data': {
                    'backup_path': backup_path,
                    'backup_data': backup_data
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# 사용 예시
if __name__ == "__main__":
    # API 토큰 및 페이지 ID 설정
    TOKEN = os.getenv('NOTION_API_KEY', 'your_notion_token_here')
    PAGE_ID = "257ebdf111b581e08adac5a42e96b84b"
    
    # Notion API 클라이언트 생성
    notion_api = NotionAPI(TOKEN)
    
    print("=== Notion API 테스트 ===")
    
    # 1. 페이지 정보 가져오기 테스트
    print("\n1. 페이지 정보 가져오기:")
    page_result = notion_api.get_page(PAGE_ID)
    if page_result['success']:
        print("[SUCCESS] 페이지 정보 가져오기 성공")
        page = page_result['data']
        print(f"   페이지 ID: {page['id']}")
        print(f"   생성일: {page['created_time']}")
        print(f"   수정일: {page['last_edited_time']}")
    else:
        print("[ERROR] 페이지 정보 가져오기 실패:")
        print(f"   오류: {page_result['error']}")
    
    # 2. 페이지 내용 가져오기 테스트
    print("\n2. 페이지 내용 가져오기:")
    content_result = notion_api.get_page_content(PAGE_ID)
    if content_result['success']:
        print("[SUCCESS] 페이지 내용 가져오기 성공")
        for i, block in enumerate(content_result['data'][:5]):  # 처음 5개만 표시
            print(f"   블록 {i+1} ({block['type']}): {block['content'][:50]}...")
    else:
        print("[ERROR] 페이지 내용 가져오기 실패:")
        print(f"   오류: {content_result['error']}")
    
    # 3. 페이지 검색 테스트
    print("\n3. 페이지 검색:")
    search_result = notion_api.search_pages("LTV")
    if search_result['success']:
        print(f"[SUCCESS] 검색 성공 - {len(search_result['data'])}개 페이지 찾음")
        for page in search_result['data'][:3]:  # 처음 3개만 표시
            title = "제목 없음"
            if 'properties' in page and 'title' in page['properties']:
                title_prop = page['properties']['title']
                if 'title' in title_prop and title_prop['title']:
                    title = title_prop['title'][0]['plain_text']
            print(f"   - {title} (ID: {page['id']})")
    else:
        print("[ERROR] 검색 실패:")
        print(f"   오류: {search_result['error']}")
    
    # 4. 백업 테스트 (페이지에 접근할 수 있는 경우에만)
    print("\n4. 페이지 백업:")
    backup_result = notion_api.backup_page(PAGE_ID)
    if backup_result['success']:
        print("[SUCCESS] 백업 성공")
        print(f"   백업 파일: {backup_result['data']['backup_path']}")
    else:
        print("[ERROR] 백업 실패:")
        print(f"   오류: {backup_result['error']}")
    
    print("\n=== 테스트 완료 ===")
    print("\n[INFO] 참고사항:")
    print("- API 토큰이 유효하지만 특정 페이지에 접근할 수 없다면,")
    print("  Notion에서 해당 페이지를 통합(Integration)과 공유해야 합니다.")
    print("- 페이지 설정 > 연결 > 통합 추가에서 API 토큰의 통합을 추가하세요.")