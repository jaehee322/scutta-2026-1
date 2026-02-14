function createBetting() {
    const players = prompt("선수 2명을 입력하세요 (공백으로 구분)").trim().split(" ");
    if (players.length !== 2) {
        alert("정확히 2명을 입력하세요.");
        return;
    }

    fetch('get_players_ranks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ players })
    })
        .then(response => response.json())
        .then(data => {
            if (data.rank_gap >= 2) {
                const proceed = confirm(`두 선수의 부수차가 ${data.rank_gap}부입니다.\n진행하시겠습니까?`);
                if (!proceed) {
                    alert("베팅 생성이 취소되었습니다.");
                    return;
                }
            }

            const participants = prompt(`${players[0]} vs ${players[1]}\n\n베팅 참가자들의 이름을 입력하세요 (공백으로 구분)`).trim().split(" ");
            if (participants.length === 0) {
                alert("최소 1명 이상의 베팅 참가자를 입력하세요.");
                return;
            }

            fetch('/get_betting_counts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ players, participants })
            })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        alert(data.error);
                        return;
                    }

                    const playerInfo = `
[선수 정보]
${data.p1.name} : ${data.p1.betting_count}
${data.p2.name} : ${data.p2.betting_count}

[참가자 정보]
${data.participants.map(p => `${p.name} : ${p.betting_count}`).join('\n')}
                    `;

                    const minBettingPoint = Math.min(
                        data.p1.betting_count,
                        data.p2.betting_count,
                        ...data.participants.map(p => p.betting_count)
                    );

                    let point;
                    do {
                        point = prompt(`${playerInfo}\n베팅 점수를 입력하세요. (최대 ${minBettingPoint} 점)`);
                        if (point === null) {
                            alert("베팅 생성이 취소되었습니다.");
                            return;
                        }

                        point = parseInt(point, 10);

                        if (isNaN(point) || point <= 0) {
                            alert("유효한 정수를 입력하세요.");
                        } else if (point > minBettingPoint) {
                            alert(`입력한 점수가 너무 큽니다. ${minBettingPoint} 이하로 입력하세요.`);
                        }
                    } while (isNaN(point) || point <= 0 || point > minBettingPoint);

                    fetch('/create_betting', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ players, participants, point })
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                alert(data.message);
                                window.location.href = '/betting';
                            } else {
                                alert(data.error || '베팅 생성에 실패했습니다.');
                            }
                        })
                        .catch(error => console.error('Error:', error));
                })
                .catch(error => console.error('Error:', error));
        })
        .catch(error => console.error('Error loading players ranks:', error));
}

function deleteBettingWithPassword(bettingId) {
    const password = prompt("삭제를 위해 관리자 비밀번호를 입력하세요:");

    // 사용자가 '취소'를 누르면 아무것도 하지 않음
    if (password === null) {
        return;
    }

    fetch(`/betting/${bettingId}/delete`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ password: password }) // 비밀번호를 JSON 형태로 전송
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);

                window.location.reload(); // 성공 시 페이지 새로고침
            } else {
                alert('오류: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('삭제 중 오류가 발생했습니다.');
        });
}