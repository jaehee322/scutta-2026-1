function createLeague() {
    const nameInput = document.getElementById("new-league-name");
    const leagueName = nameInput ? nameInput.value.trim() : "";
    const playerNames = prompt("선수 5명을 입력하세요.").trim().split(" ");

    if (playerNames.length !== 5) {
        alert("정확히 5명을 입력하세요.");
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