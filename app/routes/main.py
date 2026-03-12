from flask import Blueprint, render_template, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _
from ..extensions import db
from ..models import Match, Player, User, TodayPartner, Betting, League, PlayerPointLog
from ..utils import _get_summary_rankings_data, get_player_ranks, attach_rank
from datetime import datetime
from zoneinfo import ZoneInfo

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    # --- 1. 기본 정보 조회 (랭킹, 최근 경기, 오늘의 상대) ---
    categories = [
        ('승리', 'win_order', 'win_count'), ('승률', 'rate_order', 'rate_count'),
        ('경기', 'match_order', 'match_count'), ('베팅', 'betting_order', 'betting_count'),
    ]
    

    rankings_data = {}
    for title, order_field, value_field in categories:
        top_players = Player.query.join(Player.user).filter(Player.is_valid == True, User.is_admin == False).order_by(getattr(Player, order_field).asc(), Player.name.asc()).limit(3).all()
        top_ranks = sorted(list(set(getattr(p, order_field) for p in top_players if getattr(p, order_field) is not None)))
        current_player = current_user.player
        my_rank_info = {'rank': getattr(current_player, order_field), 'value': getattr(current_player, value_field)}
        rankings_data[title] = {
            'players': [{'name': p.name, 'rank': p.rank, 'value': getattr(p, value_field), 'actual_rank': getattr(p, order_field)} for p in top_players],
            'my_rank': my_rank_info,
            'top_ranks': top_ranks
        }
    my_recent_matches = Match.query.filter((Match.winner == current_user.player_id) | (Match.loser == current_user.player_id)).order_by(Match.timestamp.desc()).limit(5).all()
    today_partner_info = None
    today_match = TodayPartner.query.filter((TodayPartner.p1_id == current_user.player_id) | (TodayPartner.p2_id == current_user.player_id)).order_by(TodayPartner.id.desc()).first()
    if today_match:
        opponent_id = today_match.p2_id if today_match.p1_id == current_user.player_id else today_match.p1_id
        opponent_name = today_match.p2_name if today_match.p1_id == current_user.player_id else today_match.p1_name
        approval_status = None
        if today_match.submitted:
            most_recent_match = Match.query.filter(((Match.winner == current_user.player_id) & (Match.loser == opponent_id)) | ((Match.winner == opponent_id) & (Match.loser == current_user.player_id))).order_by(Match.timestamp.desc()).first()
            seoul_tz = ZoneInfo("Asia/Seoul")
            today = datetime.now(seoul_tz).date()
            if most_recent_match and most_recent_match.timestamp.astimezone(seoul_tz).date() == today:
                approval_status = 'approved' if most_recent_match.approved else 'pending'
            else:
                today_match.submitted = False
                db.session.commit()
        today_partner_info = {'date': datetime.now(ZoneInfo("Asia/Seoul")).strftime('%m.%d'), 'opponent_name': opponent_name, 'submitted': today_match.submitted, 'approval_status': approval_status}

    # --- 2. 베팅 정보 조회 ---
    ongoing_bettings = Betting.query.filter_by(is_closed=False).order_by(Betting.id.desc()).all()
    betting_data = []
    for bet in ongoing_bettings:
        if current_user.player_id not in [bet.p1_id, bet.p2_id]:
            betting_data.append(bet)

    # --- 3. 나의 리그 정보 조회 ---
    my_league_info = None
    my_name = current_user.player.name
    my_leagues = League.query.filter(
        (League.p1 == my_name) | (League.p2 == my_name) | (League.p3 == my_name) |
        (League.p4 == my_name) | (League.p5 == my_name) | (League.p6 == my_name)
    ).order_by(League.id.desc()).all()
    
    my_league = next((l for l in my_leagues if not l.is_completed), None)

    if my_league:
        player_names = my_league.player_names_list
        n = len(player_names)
        standings_data = []
        for i, name in enumerate(player_names):
            wins, losses = 0, 0
            for j in range(n):
                if i == j: continue
                if getattr(my_league, f'p{i+1}p{j+1}', None) is not None: wins += 1
                if getattr(my_league, f'p{j+1}p{i+1}', None) is not None: losses += 1
            total_games = wins + losses
            win_rate = (wins / total_games) * 100 if total_games > 0 else 0.0
            standings_data.append({'name': name, 'wins': wins, 'losses': losses, 'win_rate': win_rate})

        sorted_standings = sorted(standings_data, key=lambda x: (x['wins'], x['win_rate'], -x['losses']), reverse=True)

        my_rank, my_wins, my_losses = 0, 0, 0
        last_criteria, current_rank = (-1, -1, -1), 0
        for i, stats in enumerate(sorted_standings):
            current_criteria = (stats['wins'], stats['win_rate'], stats['losses'])
            if current_criteria != last_criteria:
                current_rank = i + 1
            last_criteria = current_criteria

            if stats['name'] == my_name:
                my_rank = current_rank
                my_wins = stats['wins']
                my_losses = stats['losses']
                break

        my_league_info = {
            'league': my_league, 'wins': my_wins,
            'losses': my_losses, 'rank': my_rank
        }

    # --- 4. 최종 렌더링 ---
    return render_template(
        'index.html',
        global_texts=current_app.config['GLOBAL_TEXTS'],
        rankings=rankings_data,
        my_recent_matches=my_recent_matches,
        today_partner_info=today_partner_info,
        ongoing_bettings=betting_data,
        my_league_info=my_league_info
    )


@main_bp.route('/rankings_page')
@login_required
def rankings_page():
    players = Player.query.join(Player.user).filter(
        Player.is_valid == True, 
        User.is_admin == False
    ).all()
    
    # 랭킹 페이지용 실시간 순위 계산 (1위, 1위, 3위 방식)
    attach_rank(players, 'win_count', 'real_win_rank')
    attach_rank(players, 'rate_count', 'real_rate_rank')
    attach_rank(players, 'match_count', 'real_match_rank')
    attach_rank(players, 'opponent_count', 'real_opponent_rank')
    attach_rank(players, 'achieve_count', 'real_achieve_rank')
    attach_rank(players, 'betting_count', 'real_betting_rank')
    attach_rank(players, 'scutta_count', 'real_scutta_rank')

    return render_template('rankings.html', players=players)


@main_bp.route('/mypage')
@login_required
def mypage():
    player_info = current_user.player
    if not player_info:
        flash(_('선수 정보를 찾을 수 없습니다.'), 'error')
        return redirect(url_for('main.index'))

    recent_matches = Match.query.filter(
        (Match.winner == player_info.id) | (Match.loser == player_info.id)
    ).order_by(Match.timestamp.desc()).limit(10).all()

    return render_template('mypage.html', player=player_info, matches=recent_matches)


@main_bp.route('/point_history')
@login_required
def point_history():
    logs = PlayerPointLog.query.filter_by(player_id=current_user.player_id)\
                               .order_by(PlayerPointLog.timestamp.desc())\
                               .all()

    return render_template('point_history.html', logs=logs)


@main_bp.route('/player/<int:player_id>', methods=['GET'])
@login_required
def player_detail(player_id):
    if current_user.player_id == player_id:
        return redirect(url_for('main.mypage'))

    player = Player.query.get_or_404(player_id)

    # 실시간 순위 정보 계산 및 할당
    ranks = get_player_ranks(player)
    player.win_order = ranks['win_order']
    player.loss_order = ranks['loss_order']
    player.rate_order = ranks['rate_order']
    player.match_order = ranks['match_order']
    player.opponent_order = ranks['opponent_order']
    player.achieve_order = ranks['achieve_order']
    player.betting_order = ranks['betting_order']
    player.scutta_order = ranks['scutta_order']

    point_logs = PlayerPointLog.query.filter_by(player_id=player_id)\
                                     .order_by(PlayerPointLog.timestamp.desc()).all()

    recent_matches = Match.query.filter(
        (Match.winner == player.id) | (Match.loser == player.id)
    ).order_by(Match.timestamp.desc()).limit(10).all()

    return render_template('player_detail.html',
                           player=player,
                           point_logs=point_logs,
                           matches=recent_matches)


@main_bp.route('/health', methods=['GET'])
def health_check():
    response = current_app.response_class(
        response="OK",
        status=200,
        mimetype='text/plain'
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@main_bp.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('favicon.ico')


@main_bp.route('/partner')
@login_required
def partner():
    partners = TodayPartner.query.order_by(TodayPartner.id).all()

    # 배치 조회: 모든 파트너의 player_id를 한 번에 로드
    all_player_ids = set()
    for p in partners:
        all_player_ids.add(p.p1_id)
        all_player_ids.add(p.p2_id)
    players_map = {p.id: p for p in Player.query.filter(Player.id.in_(all_player_ids)).all()}

    indexed_partners = []
    for idx, pr in enumerate(partners):
        p1 = players_map.get(pr.p1_id)
        p2 = players_map.get(pr.p2_id)
        indexed_partners.append({
            'index': idx,
            'partner': pr,
            'p1_rank': p1.rank if p1 else None,
            'p2_rank': p2.rank if p2 else None
        })
    return render_template('partner.html', partners=indexed_partners, global_texts=current_app.config['GLOBAL_TEXTS'])
