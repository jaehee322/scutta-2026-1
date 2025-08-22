document.addEventListener('DOMContentLoaded', () => {
    // 랭킹이 있는 페이지에서만 loadRankings를 호출하도록 수정
    if (document.getElementById('table-body')) {
        loadRankings(currentCategory);
    }

    // 메뉴 토글 이벤트 리스너
    const menuToggle = document.getElementById('menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', () => toggleMenu(true));
    }
});

function toggleMenu(show) {
    const menu = document.getElementById('menu');
    const overlay = document.getElementById('menu-overlay');
    if (show) {
        menu.classList.add('active');
        overlay.classList.add('active');
    } else {
        menu.classList.remove('active');
        overlay.classList.remove('active');
    }
}

let inputFocused = false;

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

function handleOutsideClick(event) {
    const inputs = document.querySelectorAll('input');
    if (!event.target.closest('input') && inputFocused) {
        inputs.forEach(input => input.blur());
    }
}

function navigateTo(page) {
    window.location.href = page;
}

function confirmNavigation() {
    if (confirm("관리 페이지를 나가시겠습니까?")) {
        window.location.href = '/';
    }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('menu')?.classList.remove('active');
  document.getElementById('menu-overlay')?.classList.remove('active');
});

document.addEventListener('DOMContentLoaded', function() {
    
    // --- 스크롤에 따라 헤더 숨기기/보이기 (최종 수정본) ---
    const header = document.querySelector('header');

    // 헤더가 없는 페이지에서는 실행하지 않음
    if (!header) {
        return;
    }

    // 헤더의 실제 높이를 동적으로 측정합니다 (3번 문제 해결)
    const headerHeight = header.offsetHeight;
    let lastScrollTop = 0;

    window.addEventListener('scroll', function() {
        let scrollTop = window.pageYOffset || document.documentElement.scrollTop;

        // 아래로 스크롤하고, 스크롤 위치가 헤더 높이보다 클 때만 숨김
        if (scrollTop > lastScrollTop && scrollTop > headerHeight) {
            // Scrolling Down -> Hide
            header.style.top = `-${headerHeight}px`;
        } else {
            // Scrolling Up -> Show
            header.style.top = '0';
        }
        lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
    });

});