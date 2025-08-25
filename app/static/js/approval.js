// static/js/approval.js

let currentOffset = 0;
const limit = 30;
let currentTab = 'all';
let startDate = null;
let endDate = null;
let dateFilterInstance;

document.addEventListener('DOMContentLoaded', function() {
    // Flatpickr (날짜 선택기) 초기화
    dateFilterInstance = flatpickr("#date-filter", {
        mode: "range",
        dateFormat: "Y-m-d",
        locale: "ko", // 한국어 설정
        onChange: function(selectedDates) {
            if (selectedDates.length === 2) {
                startDate = selectedDates[0];
                endDate = selectedDates[1];
            } else {
                startDate = null;
                endDate = null;
            }
        }
    });

    // 버튼 이벤트 리스너 등록
    document.getElementById('search-by-date-btn').addEventListener('click', () => {
        currentOffset = 0; // 검색 시 첫 페이지부터
        loadMatches(false);
    });

    document.getElementById('reset-date-btn').addEventListener('click', () => {
        dateFilterInstance.clear(); // 날짜 선택기 초기화
        startDate = null;
        endDate = null;
        currentOffset = 0;
        loadMatches(false);
    });

    document.getElementById('load-more').addEventListener('click', () => loadMatches(true));
    
    // 첫 데이터 로드
    loadMatches();
});

function selectTab(tabElement, tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    tabElement.classList.add('active');
    currentTab = tabName;
    currentOffset = 0;
    loadMatches(false);
}

function loadMatches(append = false) {
    let url = `/get_matches?offset=${currentOffset}&limit=${limit}&tab=${currentTab}`;
    if (startDate && endDate) {
        // 날짜를 YYYY-MM-DD 형식의 문자열로 변환
        const startStr = `${startDate.getFullYear()}-${(startDate.getMonth() + 1).toString().padStart(2, '0')}-${startDate.getDate().toString().padStart(2, '0')}`;
        const endStr = `${endDate.getFullYear()}-${(endDate.getMonth() + 1).toString().padStart(2, '0')}-${endDate.getDate().toString().padStart(2, '0')}`;
        url += `&start_date=${startStr}&end_date=${endStr}`;
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('match-table-body');
            if (!append) {
                tableBody.innerHTML = '';
            }
            data.forEach(match => {
                const row = document.createElement('tr');
                const approvedText = match.approved ? '✔️' : '❌';
                
                // ▼▼▼ 모든 td 태그에 whitespace-nowrap 클래스를 추가하여 줄바꿈 방지 ▼▼▼
                row.innerHTML = `
                    <td class="whitespace-nowrap"><input type="checkbox" class="match-checkbox" value="${match.id}"></td>
                    <td class="whitespace-nowrap">${approvedText}</td>
                    <td class="whitespace-nowrap">${match.winner_name}</td>
                    <td class="whitespace-nowrap">${match.score}</td>
                    <td class="whitespace-nowrap">${match.loser_name}</td>
                    <td class="whitespace-nowrap">${formatTimestamp(match.timestamp)}</td>
                `;
                tableBody.appendChild(row);
            });
            currentOffset += data.length;

            // 더 이상 불러올 데이터가 없으면 '더 보기' 버튼 숨김
            document.getElementById('load-more').style.display = data.length < limit ? 'none' : 'block';
        });
}

function approveMatches() {
    const selectedIds = Array.from(document.querySelectorAll('.match-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('승인할 경기를 선택하세요.');
        return;
    }
    fetch('/approve_matches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedIds })
    }).then(() => location.reload());
}

function deleteMatches() {
    const selectedIds = Array.from(document.querySelectorAll('.match-checkbox:checked')).map(cb => cb.value);
    if (selectedIds.length === 0) {
        alert('삭제할 경기를 선택하세요.');
        return;
    }
    if (confirm('정말로 선택한 경기를 삭제하시겠습니까? 승인된 경기를 삭제하면 관련 통계가 모두 복구됩니다.')) {
        fetch('/delete_matches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: selectedIds })
        }).then(() => location.reload());
    }
}

function approveAllMatches() {
    fetch('/select_all_matches')
        .then(response => response.json())
        .then(data => {
            if (data.ids.length === 0) {
                alert('승인 대기 중인 경기가 없습니다.');
                return;
            }
             if (confirm(`승인 대기 중인 ${data.ids.length}개의 모든 경기를 승인하시겠습니까?`)) {
                fetch('/approve_matches', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids: data.ids })
                }).then(() => location.reload());
            }
        });
}

function toggleSelectAll(source) {
    document.querySelectorAll('.match-checkbox').forEach(checkbox => {
        checkbox.checked = source.checked;
    });
}

function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const year = date.getFullYear().toString().slice(-2);
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}