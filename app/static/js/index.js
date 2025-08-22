document.addEventListener('DOMContentLoaded', () => {
    let currentCategory = 'win_order';
    let sortOrder = 'asc';
    let offset = 0;
    const limit = 30;
    let isLoading = false;
    let isSearching = false;
    let searchTimer;

    const tableBody = document.getElementById('table-body');
    const loadMoreBtn = document.getElementById('load-more-btn');

    // 데이터를 받아서 테이블 행으로 변환하는 함수
    function createPlayerRow(player) {
        const category_value_formatted = currentCategory.includes('rate') ? `${player.category_value}%` : player.category_value;
        const category_value_2_formatted = currentCategory === 'match_order' ? `${player.category_value_2}%` : player.category_value_2;

        return `
            <tr>
                <td class="text-center font-semibold">${player.current_rank}</td>
                <td><a href="/player/${player.id}" class="hover:underline font-semibold">${player.name} (${player.rank})</a></td>
                <td class="text-center">${category_value_formatted}</td>
                <td class="text-center">${category_value_2_formatted}</td>
                <td class="text-center text-sm text-gray-600">${player.last_10_record || ''}</td>
            </tr>
        `;
    }

    // 테이블에 데이터를 표시하는 함수
    function displayData(players, clear) {
        if (clear) {
            tableBody.innerHTML = '';
        }
        if (players.length === 0 && clear) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">검색 결과가 없습니다.</td></tr>';
            return;
        }
        players.forEach(player => {
            tableBody.insertAdjacentHTML('beforeend', createPlayerRow(player));
        });
    }

    // 랭킹 데이터를 서버에서 불러오는 함수
    async function loadRankings(isNew = false) {
        if (isLoading || isSearching) return;
        isLoading = true;
        loadMoreBtn.textContent = '불러오는 중...';

        if (isNew) {
            offset = 0; // 새 카테고리 로드 시 offset 초기화
        }

        const response = await fetch(`/rankings?category=${currentCategory}&sort=${sortOrder}&offset=${offset}&limit=${limit}`);
        const players = await response.json();
        
        displayData(players, isNew);
        
        offset += players.length; // offset을 올바르게 증가시킴
        isLoading = false;
        loadMoreBtn.textContent = '더보기';

        if (players.length < limit) {
            loadMoreBtn.style.display = 'none';
        } else {
            loadMoreBtn.style.display = 'block';
        }
    }

    // 전역(window) 객체에 함수를 할당하여 HTML onclick에서 호출 가능하게 함
    window.selectCategory = (button, category) => {
        document.querySelectorAll('.category-buttons button').forEach(btn => btn.classList.remove('selected'));
        button.classList.add('selected');
        
        currentCategory = category;
        sortOrder = 'asc';
        isSearching = false;
        document.querySelector('input[type="text"]').value = '';

        const headers = {
            'win_order': ['승리', '경기'], 'loss_order': ['패배', '경기'], 'rate_order': ['승률', '경기'],
            'match_order': ['경기', '승률'], 'opponent_order': ['상대', '경기'], 'achieve_order': ['업적', '베팅'],
            'betting_order': ['베팅', '업적']
        };
        document.getElementById('dynamic-column').textContent = headers[category][0];
        document.getElementById('dynamic-column-2').textContent = headers[category][1];
        
        loadRankings(true); // isNew 플래그를 true로 전달
    };

    window.toggleSortOrder = () => {
        sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
        loadRankings(true); // isNew 플래그를 true로 전달
    };

    window.loadMore = () => {
        loadRankings(false); // isNew 플래그를 false로 전달
    };

    window.searchByName = (query) => {
        clearTimeout(searchTimer);

        if (query.length < 2) {
            isSearching = false;
            loadMoreBtn.style.display = 'block';
            if (tableBody.innerHTML.includes('검색 결과가 없습니다')) {
                loadRankings(true);
            }
            return;
        }
        
        isSearching = true;
        loadMoreBtn.style.display = 'none';
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4">검색 중...</td></tr>';
        
        searchTimer = setTimeout(async () => {
            const response = await fetch(`/search_players?query=${encodeURIComponent(query)}&category=${currentCategory}`);
            const players = await response.json();
            displayData(players, true);
        }, 300);
    };

    // 페이지 로드 시 초기 데이터 로딩
    loadRankings(true);
});