// static/js/cinematic.js

window.addEventListener('scroll', () => {
    // 현재 스크롤 위치 계산 (0 ~ 1 사이의 값)
    const scrollPosition = window.scrollY;
    const maxScroll = document.body.scrollHeight - window.innerHeight;
    const scrollFraction = scrollPosition / maxScroll;

    const titleScene = document.getElementById('scene-title');
    const calendarScene = document.getElementById('scene-calendar');
    const photosScene = document.getElementById('scene-photos');
    const messagesScene = document.getElementById('scene-messages');

    // 모든 장면을 일단 숨김
    document.querySelectorAll('.scene').forEach(s => s.classList.remove('active'));

    // === 스크롤 위치에 따라 장면 전환 ===

    // 1. (0% ~ 20%) 타이틀 보여주기
    if (scrollFraction >= 0 && scrollFraction < 0.2) {
        titleScene.classList.add('active');
    }
    // 2. (20% ~ 40%) 달력 애니메이션
    else if (scrollFraction >= 0.2 && scrollFraction < 0.4) {
        calendarScene.classList.add('active');
        
        // 달력 이미지를 스크롤에 따라 촤라락 넘기기
        const calendarProgress = (scrollFraction - 0.2) / 0.2; // 0~1
        document.getElementById('month-dec').style.opacity = calendarProgress < 0.25 ? 1 : 0;
        document.getElementById('month-nov').style.opacity = calendarProgress >= 0.25 && calendarProgress < 0.5 ? 1 : 0;
        document.getElementById('month-oct').style.opacity = calendarProgress >= 0.5 && calendarProgress < 0.75 ? 1 : 0;
        document.getElementById('month-sep').style.opacity = calendarProgress >= 0.75 ? 1 : 0;
    }
    // 3. (40% ~ 60%) 사진 보여주기
    else if (scrollFraction >= 0.4 && scrollFraction < 0.6) {
        photosScene.classList.add('active');
        // 사진들을 순서대로 보여주기
        document.querySelectorAll('#scene-photos .photo-item').forEach((item, index) => {
            if (scrollFraction > 0.4 + (index * 0.1)) {
                item.classList.add('show');
            }
        });
    }
    // 4. (60% ~ 80%) 멘트 보여주기
    else if (scrollFraction >= 0.6 && scrollFraction < 0.8) {
        messagesScene.classList.add('active');
        if (scrollFraction > 0.65) document.getElementById('message1').classList.add('show');
        if (scrollFraction > 0.7) document.getElementById('message2').classList.add('show');
    }
    // 5. (80% 이상) 인트로 끝내고 본편 보여주기
    else if (scrollFraction >= 0.8) {
        document.getElementById('cinematic-container').style.opacity = '0'; // 인트로 스크린 fade out
        document.getElementById('main-content').style.display = 'block'; // 본편 보여주기
        document.body.style.height = 'auto'; // 인위적으로 늘렸던 body 높이 원상복구
        document.body.style.backgroundColor = '#fff'; // 배경색도 원래대로
    }
});
