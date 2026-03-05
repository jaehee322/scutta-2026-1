function createLeague() {
    const nameInput = document.getElementById("new-league-name");
    const leagueName = nameInput ? nameInput.value.trim() : "";
    const input = prompt("선수 4~6명의 이름을 공백으로 구분하여 입력하세요.");
    if (!input) return;

    const playerNames = input.trim().split(/\s+/);

    if (playerNames.length < 4 || playerNames.length > 6) {
        alert("4명에서 6명 사이의 선수를 입력해야 합니다.");
        return;
    }

    fetch('/create_league', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: leagueName,
            players: playerNames
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert(data.error || '리그전 생성에 실패했습니다.');
            }
        })
        .catch(error => console.error('Error:', error));
}