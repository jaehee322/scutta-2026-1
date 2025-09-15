// static/js/create_betting.js 파일 전체를 교체해주세요.

document.getElementById('create-betting-form').addEventListener('submit', function(event) {
    event.preventDefault();

    const player1 = document.getElementById('player1').value.trim();
    const player2 = document.getElementById('player2').value.trim();
    const point = parseInt(document.getElementById('point').value, 10);
    const participantsText = document.getElementById('participants').value;
    const participants = participantsText.split('\n').map(name => name.trim()).filter(name => name);

    // ▼▼▼ 여기가 수정된 부분입니다 ▼▼▼
    // 드롭다운 기본값 확인 대신, 입력값이 비어있는지 확인하도록 변경했습니다.
    if (player1 === '' || player2 === '') {
        alert('선수 1과 선수 2의 이름을 모두 입력해야 합니다.');
        return;
    }
    // ▲▲▲ 수정 완료 ▲▲▲

    if (player1 === player2) {
        alert('서로 다른 선수를 선택해야 합니다.');
        return;
    }

    if (isNaN(point) || point <= 0) {
        alert('기본 포인트는 0보다 큰 숫자여야 합니다.');
        return;
    }

    const data = {
        players: [player1, player2],
        point: point,
        participants: participants
    };

    fetch('/create_betting', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            alert(result.message);
            // 성공 시, 관리자용 상세 페이지로 이동합니다.
            window.location.href = `/betting/${result.betting_id}/admin`;
        } else {
            alert('오류: ' + result.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('베팅 생성 중 오류가 발생했습니다.');
    });
});