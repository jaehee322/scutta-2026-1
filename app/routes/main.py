from flask import Blueprint, render_template, redirect, url_for, session, current_app
from flask_login import current_user, login_required
from flask_babel import _
from ..extensions import db
from ..models import Match, Player, User, TodayPartner, Betting, League, PlayerPointLog
from ..utils import _get_summary_rankings_data
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
    my_league = League.query.filter(
        (League.p1 == my_name) | (League.p2 == my_name) | (League.p3 == my_name) |
        (League.p4 == my_name) | (League.p5 == my_name)
    ).order_by(League.id.desc()).first()

    if my_league:
        player_names = [my_league.p1, my_league.p2, my_league.p3, my_league.p4, my_league.p5]
        standings_data = []
        for i, name in enumerate(player_names):
            wins, losses = 0, 0
            for j in range(5):
                if i == j: continue
                if getattr(my_league, f'p{i+1}p{j+1}') is not None: wins += 1
                if getattr(my_league, f'p{j+1}p{i+1}') is not None: losses += 1
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


@main_bp.route('/intro')
@login_required
def intro():
    seoul_tz = ZoneInfo("Asia/Seoul")
    now = datetime.now(seoul_tz)

    SEASON_START = current_app.config['SEASON_START']
    SEMESTER_DEADLINE = current_app.config['SEMESTER_DEADLINE']

    is_ended = now >= SEMESTER_DEADLINE

    remaining_time = None
    if not is_ended:
        diff = SEMESTER_DEADLINE - now
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        remaining_time = {'days': days, 'hours': hours, 'minutes': minutes, 'seconds': seconds}

    player = current_user.player
    my_stats = {
        'name': player.name,
        'match_count': player.match_count,
        'win_count': player.win_count,
        'rate_count': player.rate_count,
        'rank': player.rank
    }

    my_id = current_user.player.id

    special_awards = {}
    my_matches = Match.query.filter(
        ((Match.winner == my_id) | (Match.loser == my_id)) &
        (Match.approved == True) &
        (Match.timestamp >= SEASON_START)
    ).all()

    opponents = {}
    for m in my_matches:
        is_winner = (m.winner == my_id)
        if is_winner:
            opponent_id = m.loser
            opponent_name = m.loser_name
        else:
            opponent_id = m.winner
            opponent_name = m.winner_name

        if not opponent_id or not opponent_name or opponent_id == my_id: continue

        if opponent_id not in opponents:
            opponents[opponent_id] = {'name': opponent_name, 'total': 0, 'wins': 0, 'losses': 0}

        opponents[opponent_id]['total'] += 1
        if is_winner: opponents[opponent_id]['wins'] += 1
        else: opponents[opponent_id]['losses'] += 1

    if opponents:
        rival_id = max(opponents, key=lambda x: opponents[x]['total'])
        special_awards['rival'] = opponents[rival_id]

    wins_only = {k: v for k, v in opponents.items() if v['wins'] > 0}
    if wins_only:
        prey_id = max(wins_only, key=lambda x: wins_only[x]['wins'])
        special_awards['prey'] = wins_only[prey_id]

    losses_only = {k: v for k, v in opponents.items() if v['losses'] > 0}
    if losses_only:
        nemesis_id = max(losses_only, key=lambda x: losses_only[x]['losses'])
        special_awards['nemesis'] = losses_only[nemesis_id]

    timeline = []

    timeline.append({
        'date': SEASON_START,
        'title': _('2학기 시즌 오픈'),
        'desc': _('전설의 시작 🌱'),
        'icon': '🏁'
    })

    first_match = Match.query.filter(
        ((Match.winner == my_id) | (Match.loser == my_id)) &
        (Match.approved == True) & (Match.timestamp >= SEASON_START)
    ).order_by(Match.timestamp.asc()).first()

    if first_match:
        match_date_kst = first_match.timestamp.astimezone(seoul_tz)
        opponent = first_match.loser_name if first_match.winner == my_id else first_match.winner_name

        timeline.append({
            'date': match_date_kst,
            'title': _('두근두근 첫 경기'),
            'desc': _('vs %(name)s') % {'name': opponent},
            'icon': 'start_match'
        })

        first_win = Match.query.filter(
            (Match.winner == my_id) & (Match.approved == True) & (Match.timestamp >= SEASON_START)
        ).order_by(Match.timestamp.asc()).first()

        if first_win:
                win_date_kst = first_win.timestamp.astimezone(seoul_tz)
                timeline.append({
                'date': win_date_kst,
                'title': _('감격의 첫 승리!'),
                'desc': _('제물: %(name)s 🤭') % {'name': first_win.loser_name},
                'icon': 'first_win'
            })

    # ✅ [수정] 업적 로그 중복 제거 로직 추가 (achieve_change > 0)
    achievement_logs = PlayerPointLog.query.filter(
        (PlayerPointLog.player_id == my_id) &
        (PlayerPointLog.reason.like('%달성%')) &
        (PlayerPointLog.timestamp >= SEASON_START) &
        (PlayerPointLog.achieve_change > 0)  # 👈 여기가 핵심!
    ).all()

    for log in achievement_logs:
        log_date_kst = log.timestamp.astimezone(seoul_tz)
        timeline.append({
            'date': log_date_kst,
            'title': _('업적 잠금 해제'),
            'desc': log.reason,
            'icon': 'achievement'
        })

    timeline.sort(key=lambda x: x['date'])

    last_node_title = _('시즌 종료') if is_ended else _('현재')
    last_node_desc = _('수고하셨습니다! 👏') if is_ended else _('우리는 여전히 달리는 중 🏃‍♂️')
    last_node_icon = '🏁' if is_ended else '📍'

    timeline.append({
        'date': now, 'title': last_node_title, 'desc': last_node_desc, 'icon': last_node_icon
    })

    season_rankings = {}
    if is_ended:
        categories = [
            (_('🏆 다승왕'), Player.win_count.desc(), 'win_count', _('승')),
            (_('🔥 승률왕'), Player.rate_count.desc(), 'rate_count', '%'),
            (_('🏓 최다 경기'), Player.match_count.desc(), 'match_count', _('전')),
            (_('🤝 마당발'), Player.opponent_count.desc(), 'opponent_count', _('명')),
            (_('🏅 업적왕'), Player.achieve_count.desc(), 'achieve_count', 'pt'),
            (_('💸 베팅왕'), Player.betting_count.desc(), 'betting_count', 'pt'),
            (_('💀 최다 패배'), Player.loss_count.desc(), 'loss_count', _('패'))
        ]

        for title, criteria, attr, unit in categories:
            top5 = Player.query.join(User).filter(
                Player.is_valid == True, User.is_admin == False
            ).order_by(criteria, Player.name).limit(5).all()

            season_rankings[title] = {'players': top5, 'unit': unit, 'attr': attr}

    top_players = []
    if is_ended:
        top_players = Player.query.join(User).filter(
            Player.is_valid == True, User.is_admin == False
        ).order_by(Player.win_count.desc(), Player.rate_count.desc(), Player.match_count.desc()).limit(5).all()

    # [중요] index.html의 '방문 도장' 찍기
    session['visited_intro'] = True

    return render_template('intro.html',
                            is_ended=is_ended,
                            remaining_time=remaining_time,
                            my_stats=my_stats,
                            top_players=top_players,
                            special_awards=special_awards,
                            timeline=timeline,
                            season_rankings=season_rankings,
                            getattr=getattr)


@main_bp.route('/rankings_page')
@login_required
def rankings_page():
    current_player = current_user.player if current_user.is_authenticated else None
    summary_rankings = _get_summary_rankings_data(current_player)

    translated_headers = {
        'rank': _('순위'),
        'name': _('이름'),
        'win_count': _('승리'),
        'loss_count': _('패배'),
        'rate_count': _('승률'),
        'match_count': _('경기'),
        'opponent_count': _('상대'),
        'achieve_count': _('업적'),
        'betting_count': _('베팅')
    }
    return render_template('rankings.html', summary_rankings=summary_rankings, headers=translated_headers)


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

    if current_user.is_admin:
        point_logs = PlayerPointLog.query.filter_by(player_id=player_id)\
                                         .order_by(PlayerPointLog.timestamp.desc()).all()

        recent_matches = Match.query.filter(
            (Match.winner == player.id) | (Match.loser == player.id)
        ).order_by(Match.timestamp.desc()).limit(10).all()

        return render_template('player_detail_admin.html',
                               player=player,
                               point_logs=point_logs,
                               matches=recent_matches)
    else:
        return render_template('public_player_profile.html', player=player)


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

    p1_ranks = []
    p2_ranks = []
    for p in partners:
        p1 = Player.query.filter_by(id=p.p1_id).first()
        p1_ranks.append(p1.rank if p1 else None)
        p2 = Player.query.filter_by(id=p.p2_id).first()
        p2_ranks.append(p2.rank if p2 else None)

    indexed_partners = [{'index': idx, 'partner': pr, 'p1_rank': p1_rank, 'p2_rank': p2_rank} for idx, (pr, p1_rank, p2_rank) in enumerate(zip(partners, p1_ranks, p2_ranks))]
    return render_template('partner.html', partners=indexed_partners, global_texts=current_app.config['GLOBAL_TEXTS'])
