// static/js/index.js 파일의 전체 내용입니다.

document.addEventListener('DOMContentLoaded', () => {
    // --- 상태 관리 변수 ---
    let offset = 0;
    const limit = 30;
    let isLoading = false;
    let currentCategory = 'win_count'; // _order 접미사 없이 사용
    let searchTimer;

    // --- DOM 요소 ---
    const tableHeader = document.getElementById('table-header');
    const tableBody = document.getElementById('table-body');
    const loadMoreBtn = document.getElementById('load-more-btn');
    const searchInput = document.getElementById('player-search-input');
    const categoryButtonsContainer = document.querySelector('.category-buttons');

    // --- 데이터 및 설정 ---
    const columnConfig = {
        win_count: { name: '승리', suffix: '' },
        loss_count: { name: '패배', suffix: '' },
        rate_count: { name: '승률', suffix: '%' },
        match_count: { name: '경기', suffix: '' },
        opponent_count: { name: '상대', suffix: '' },
        achieve_count: { name: '업적', suffix: '' },
        betting_count: { name: '베팅', suffix: '' },
    };
    let columnOrder = Object.keys(columnConfig);

    /**
     * 테이블 헤더를 다시 그리는 함수
     */
    // static/js/index.js 파일에서 이 함수를 찾아 아래 내용으로 교체해주세요.

/**
 * 테이블 헤더를 현재 열 순서에 맞게 다시 그리는 함수
 */
    function renderHeader() {
        if (!tableHeader) return;
        tableHeader.innerHTML = '';
        const tr = document.createElement('tr');
        
        // ▼▼▼ '순위'와 '이름' 헤더를 먼저 추가하도록 수정했습니다. ▼▼▼
        let headerHTML = `
            <th class="whitespace-nowrap px-4 py-2">순위</th>
            <th class="whitespace-nowrap px-4 py-2">이름</th>
        `;

        // 그 다음에 동적인 랭킹 지표 헤더들을 추가합니다.
        columnOrder.forEach(key => {
            const isCurrent = key === currentCategory;
            headerHTML += `<th class="whitespace-nowrap px-4 py-2 cursor-pointer ${isCurrent ? 'text-blue-600 font-bold' : ''}" onclick="selectCategory('${key}')">${columnConfig[key].name}</th>`;
        });
        
        tr.innerHTML = headerHTML;
        tableHeader.appendChild(tr);
    }

    /**
     * 테이블 본문을 다시 그리는 함수
     */
    function renderBody(players, clear = false) {
        if (!tableBody) return;
        if (clear) {
            tableBody.innerHTML = '';
        }
        if (players.length === 0 && clear) {
            tableBody.innerHTML = `<tr><td colspan="9" class="text-center py-4">표시할 데이터가 없습니다.</td></tr>`;
            return;
        }

        players.forEach(player => {
            const tr = document.createElement('tr');
            let rowHTML = `
                <td class="text-center font-semibold whitespace-nowrap">${player.current_rank}</td>
                <td class="whitespace-nowrap"><a href="/player/${player.id}" class="hover:underline font-semibold">${player.name} (${player.rank})</a></td>
            `;

            columnOrder.forEach(key => {
                const isCurrent = key === currentCategory;
                const value = player.stats[key] + (columnConfig[key].suffix || '');
                rowHTML += `<td class="text-center whitespace-nowrap ${isCurrent ? 'font-bold' : ''}">${value}</td>`;
            });
            
            tr.innerHTML = rowHTML;
            tableBody.appendChild(tr);
        });
    }

    /**
     * 서버에서 랭킹 데이터를 불러오는 함수
     */
    async function loadRankings(isNew = false) {
        if (isLoading) return;
        isLoading = true;
        if(loadMoreBtn) loadMoreBtn.textContent = '불러오는 중...';
        if (isNew) offset = 0;

        const query = searchInput.value.trim();
        // JS는 win_count, 서버는 win_order를 사용하므로 맞춰서 보냅니다.
        const categoryForURL = currentCategory.replace('_count', '_order');
        const url = query.length >= 2 
            ? `/search_players?query=${encodeURIComponent(query)}&category=${categoryForURL}&offset=${offset}&limit=${limit}`
            : `/rankings?category=${categoryForURL}&offset=${offset}&limit=${limit}`;
        
        try {
            const response = await fetch(url);
            const players = await response.json();
            renderBody(players, isNew);
            offset += players.length;
            if(loadMoreBtn) loadMoreBtn.style.display = (players.length < limit || query.length >= 2) ? 'none' : 'block';
        } catch (error) {
            console.error("Error loading rankings:", error);
            if(tableBody) tableBody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-red-500">데이터를 불러오는 데 실패했습니다.</td></tr>';
        } finally {
            isLoading = false;
            if(loadMoreBtn) loadMoreBtn.textContent = '더보기';
        }
    }
    
    /**
     * 카테고리 버튼을 생성하는 함수
     */
    function createCategoryButtons() {
        if (!categoryButtonsContainer) return;
        categoryButtonsContainer.innerHTML = '';
        Object.keys(columnConfig).forEach(key => {
            const button = document.createElement('button');
            button.className = `px-4 py-1 border rounded text-sm`;
            if (key === currentCategory) {
                button.classList.add('selected');
            }
            button.textContent = columnConfig[key].name;
            button.onclick = () => selectCategory(key);
            categoryButtonsContainer.appendChild(button);
        });
    }
    
    /**
     * 카테고리 선택 시 실행되는 함수
     */
    function selectCategory(categoryKey) {
        currentCategory = categoryKey;
        columnOrder = [categoryKey, ...Object.keys(columnConfig).filter(k => k !== categoryKey)];
        
        createCategoryButtons();
        renderHeader();
        loadRankings(true);
};

    // --- 이벤트 리스너 ---
    if(loadMoreBtn) loadMoreBtn.addEventListener('click', () => loadRankings(false));
    if(searchInput) searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => loadRankings(true), 300);
    });

    // --- 페이지 초기화 ---
    selectCategory('win_count');
});