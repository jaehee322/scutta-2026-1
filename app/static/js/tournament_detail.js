// static/js/tournament_detail.js

function requestPasswordModal() {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.style.position = 'fixed';
        modal.style.top = '0';
        modal.style.left = '0';
        modal.style.width = '100vw';
        modal.style.height = '100vh';
        modal.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        modal.style.display = 'flex';
        modal.style.justifyContent = 'center';
        modal.style.alignItems = 'center';
        modal.style.zIndex = '2000';

        const form = document.createElement('div');
        form.style.backgroundColor = 'white';
        form.style.padding = '20px';
        form.style.borderRadius = '10px';
        form.style.textAlign = 'center';
        form.innerHTML = `
            <p>토너먼트를 삭제하려면 비밀번호를 입력하세요.</p><br>
            <input type="password" id="passwordInput" style="padding: 5px; width: 80%; border: 1px solid #ccc; border-radius: 5px;"><br><br>
            <button id="cancelButton" style="padding: 5px 10px; border-radius: 5px;">취소</button>
            <button id="confirmButton" style="margin-left: 20px; padding: 5px 10px; border-radius: 5px; background-color: #374151; color: white;">확인</button>
        `;

        modal.appendChild(form);
        document.body.appendChild(modal);

        document.getElementById('passwordInput').focus();

        document.getElementById('confirmButton').addEventListener('click', () => {
            const password = document.getElementById('passwordInput').value;
            document.body.removeChild(modal);
            resolve(password);
        });

        document.getElementById('cancelButton').addEventListener('click', () => {
            document.body.removeChild(modal);
            resolve(null);
        });
    });
}


async function deleteTournament(tournamentId) {
    const password = await requestPasswordModal();
    if (password === null) return;

    if (password !== 'yeong6701') {
        alert('비밀번호가 올바르지 않습니다.');
        return;
    }

    if (!confirm('정말로 이 토너먼트를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
        return;
    }

    fetch(`/tournament/delete/${tournamentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.href = '/tournament';
        } else {
            alert('오류: ' + data.error);
        }
    });
}