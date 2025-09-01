// 모바일 터치 인터랙션 개선 스크립트

document.addEventListener('DOMContentLoaded', function() {
    
    // 터치 피드백 개선
    function addTouchFeedback() {
        const touchElements = document.querySelectorAll('.btn, .form-control, .form-select, .md-btn, .md-ltv-btn');
        
        touchElements.forEach(element => {
            // 터치 시작 시 피드백
            element.addEventListener('touchstart', function(e) {
                this.style.transform = 'scale(0.98)';
                this.style.opacity = '0.8';
                this.style.transition = 'all 0.1s ease';
            });
            
            // 터치 종료 시 원복
            element.addEventListener('touchend', function(e) {
                setTimeout(() => {
                    this.style.transform = '';
                    this.style.opacity = '';
                }, 150);
            });
            
            // 터치 취소 시 원복
            element.addEventListener('touchcancel', function(e) {
                this.style.transform = '';
                this.style.opacity = '';
            });
        });
    }
    
    // 모바일에서 드래그 앤 드롭 개선
    function improveMobileDragDrop() {
        const uploadSection = document.getElementById('upload-section');
        if (!uploadSection) return;
        
        // 터치 기반 파일 선택
        uploadSection.addEventListener('touchstart', function(e) {
            e.preventDefault();
            this.style.borderColor = 'var(--primary-accent)';
            this.style.backgroundColor = 'rgba(212, 70, 239, 0.1)';
        });
        
        uploadSection.addEventListener('touchend', function(e) {
            e.preventDefault();
            this.style.borderColor = '';
            this.style.backgroundColor = '';
            
            // 파일 선택 다이얼로그 열기
            const fileInput = document.getElementById('file-input');
            if (fileInput) {
                fileInput.click();
            }
        });
    }
    
    // 스크롤 성능 개선
    function improveScrollPerformance() {
        const scrollableElements = document.querySelectorAll('.form-column, .pdf-viewer-column');
        
        scrollableElements.forEach(element => {
            // 스크롤 시 성능 최적화
            element.style.willChange = 'scroll-position';
            element.style.webkitOverflowScrolling = 'touch';
            
            // 스크롤 이벤트 최적화
            let scrollTimeout;
            element.addEventListener('scroll', function() {
                if (scrollTimeout) {
                    clearTimeout(scrollTimeout);
                }
                
                scrollTimeout = setTimeout(() => {
                    // 스크롤이 끝났을 때 will-change 제거로 메모리 최적화
                    this.style.willChange = 'auto';
                    
                    // 다음 스크롤을 위해 다시 설정
                    setTimeout(() => {
                        this.style.willChange = 'scroll-position';
                    }, 100);
                }, 150);
            });
        });
    }
    
    // 키보드 높이 감지 및 대응 (iOS)
    function handleKeyboardResize() {
        const initialViewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
        
        function onViewportChange() {
            const currentHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
            const keyboardHeight = initialViewportHeight - currentHeight;
            
            if (keyboardHeight > 100) { // 키보드가 올라온 상태
                document.body.classList.add('keyboard-open');
                
                // 활성 입력 필드를 화면에 보이도록 스크롤
                const activeElement = document.activeElement;
                if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
                    setTimeout(() => {
                        activeElement.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                        });
                    }, 300);
                }
            } else {
                document.body.classList.remove('keyboard-open');
            }
        }
        
        if (window.visualViewport) {
            window.visualViewport.addEventListener('resize', onViewportChange);
        } else {
            window.addEventListener('resize', onViewportChange);
        }
    }
    
    // 더블 탭 줌 방지
    function preventDoubleZoom() {
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            const now = (new Date()).getTime();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, { passive: false });
    }
    
    // 햅틱 피드백 (지원되는 브라우저에서)
    function addHapticFeedback() {
        const hapticElements = document.querySelectorAll('.btn, .md-btn');
        
        hapticElements.forEach(element => {
            element.addEventListener('click', function() {
                // 햅틱 피드백 (iOS Safari에서 지원)
                if ('vibrate' in navigator) {
                    navigator.vibrate(10); // 10ms 진동
                }
            });
        });
    }
    
    // Pull-to-refresh 방지
    function preventPullToRefresh() {
        let startY = 0;
        
        document.addEventListener('touchstart', function(e) {
            startY = e.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', function(e) {
            const currentY = e.touches[0].clientY;
            const scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
            
            // 상단에서 아래로 스크롤 시도하는 경우 방지
            if (scrollTop === 0 && currentY > startY) {
                e.preventDefault();
            }
        }, { passive: false });
    }
    
    // 모바일 디바이스 감지
    function isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768);
    }
    
    // PWA 설치 상태 감지 및 UI 조정
    function handlePWAMode() {
        if (window.matchMedia('(display-mode: standalone)').matches || 
            window.navigator.standalone === true) {
            document.body.classList.add('pwa-mode');
            
            // PWA 모드에서 추가적인 네이티브 앱 같은 느낌 제공
            document.body.style.userSelect = 'none';
            
            // 입력 필드는 선택 허용
            const inputs = document.querySelectorAll('input, textarea, [contenteditable]');
            inputs.forEach(input => {
                input.style.userSelect = 'text';
                input.style.webkitUserSelect = 'text';
            });
        }
    }
    
    // 모바일 전용 기능들 초기화
    if (isMobile()) {
        addTouchFeedback();
        improveMobileDragDrop();
        improveScrollPerformance();
        handleKeyboardResize();
        preventDoubleZoom();
        addHapticFeedback();
        preventPullToRefresh();
        handlePWAMode();
        
        // 모바일 전용 CSS 클래스 추가
        document.body.classList.add('mobile-device');
        
        console.log('Mobile touch optimizations loaded');
    }
});

// 키보드 관련 CSS 추가
const keyboardStyles = `
    .keyboard-open {
        /* 키보드가 열렸을 때 화면 조정 */
        position: fixed;
        width: 100%;
        height: 100%;
        overflow: hidden;
    }
    
    .keyboard-open .main-container {
        height: 100vh;
        height: 100svh;
        overflow: hidden;
    }
    
    .keyboard-open .form-column {
        /* 키보드가 열렸을 때 스크롤 영역 조정 */
        max-height: calc(100vh - 200px);
        overflow-y: auto;
    }
    
    .pwa-mode {
        /* PWA 모드 전용 스타일 */
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        -khtml-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    @media (max-width: 768px) {
        .mobile-device .btn {
            /* 모바일에서 버튼 터치 영역 확대 */
            position: relative;
        }
        
        .mobile-device .btn::after {
            content: '';
            position: absolute;
            top: -5px;
            left: -5px;
            right: -5px;
            bottom: -5px;
            z-index: -1;
        }
        
        /* 터치 하이라이트 색상 커스터마이징 */
        .mobile-device * {
            -webkit-tap-highlight-color: rgba(212, 70, 239, 0.2);
        }
    }
`;

// 동적 스타일 추가
const styleSheet = document.createElement("style");
styleSheet.textContent = keyboardStyles;
document.head.appendChild(styleSheet);