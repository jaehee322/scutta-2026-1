// static/js/script.js 파일의 전체 내용입니다.

// --- Global helper functions (HTML onclick에서 직접 호출) ---

function navigateTo(page) {
    window.location.href = page;
}

function confirmNavigation() {
    if (confirm("관리 페이지를 나가시겠습니까?")) {
        window.location.href = '/';
    }
}

// --- DOMContentLoaded: 페이지 로드가 완료된 후 실행 ---

document.addEventListener('DOMContentLoaded', function() {
    
    // ===================================
    // 메뉴 관련 기능 (수정/추가된 부분)
    // ===================================
    const menuToggle = document.getElementById('menu-toggle');
    const menu = document.getElementById('menu');
    const menuOverlay = document.getElementById('menu-overlay');

    function openMenu() {
        if (menu && menuOverlay) {
            menu.classList.add('active');
            menuOverlay.classList.add('active');
        }
    }

    function closeMenu() {
        if (menu && menuOverlay) {
            menu.classList.remove('active');
            menuOverlay.classList.remove('active');
        }
    }

    // 페이지 로드 시 혹시 메뉴가 열려있으면 닫기
    closeMenu();

    if (menuToggle) {
        menuToggle.addEventListener('click', function(event) {
            event.stopPropagation();
            if (menu.classList.contains('active')) {
                closeMenu();
            } else {
                openMenu();
            }
        });
    }

    if (menuOverlay) {
        // 메뉴 바깥의 어두운 배경 클릭 시 닫기 (요청하신 기능)
        menuOverlay.addEventListener('click', closeMenu);
    }
    
    if (menu) {
        // 메뉴 자체를 클릭했을 때는 닫히지 않도록 이벤트 전파 중단
        menu.addEventListener('click', function(event) {
            event.stopPropagation();
        });
    }

    // ===================================
    // 헤더 스크롤 기능 (기존 기능 보존)
    // ===================================
    const header = document.querySelector('header');
    if (header) {
        const headerHeight = header.offsetHeight;
        let lastScrollTop = 0;

        window.addEventListener('scroll', function() {
            let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            if (scrollTop > lastScrollTop && scrollTop > headerHeight) {
                header.style.top = `-${headerHeight}px`; // Hide
            } else {
                header.style.top = '0'; // Show
            }
            lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
        });
    }

    // ===================================
    // 외부 클릭 시 Input 포커스 해제 기능 (기존 기능 보존)
    // ===================================
    let inputFocused = false;

    function handleOutsideClick(event) {
        const inputs = document.querySelectorAll('input');
        if (!event.target.closest('input') && inputFocused) {
            inputs.forEach(input => input.blur());
        }
    }

    document.addEventListener('focusin', (event) => {
        if (event.target.tagName === 'INPUT') {
            inputFocused = true;
            document.addEventListener('click', handleOutsideClick);
        }
    });

    document.addEventListener('focusout', (event) => {
        if (event.target.tagName === 'INPUT') {
            inputFocused = false;
            document.removeEventListener('click', handleOutsideClick);
        }
    });
});