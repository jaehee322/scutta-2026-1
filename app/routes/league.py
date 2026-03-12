from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _
from sqlalchemy.orm.attributes import flag_modified
from ..extensions import db
from ..models import Match, Player, User, League, Tournament
from ..utils import add_point_log, update_player_orders_by_point, update_player_orders_by_match
from datetime import datetime
from zoneinfo import ZoneInfo
import random

league_bp = Blueprint('league', __name__)


@league_bp.route('/league_or_tournament')
@login_required
def league_or_tournament():
    return render_template('league_or_tournament.html')


@league_bp.route('/league')
@login_required
def league():
    leagues = League.query.order_by(League.id.desc()).all()

    league_data = []
    for l in leagues:
        player_names = l.player_names_list
        is_participant = current_user.player.name in player_names
        
        is_completed = l.is_completed
        
        league_data.append({
            'league': l,
            'is_participant': is_participant,
            'is_completed': is_completed,
            'league_size': l.player_count,
            'completed_matches': l.completed_match_pairs,
            'total_matches': l.total_match_pairs
        })

    return render_template('league.html', league_data=league_data)


@league_bp.route('/league/<int:league_id>', methods=['GET'])
@login_required
def league_detail(league_id):
    league = League.query.get_or_404(league_id)
    player_names = league.player_names_list
    n = len(player_names)

    players_info = []
    player_objects = Player.query.filter(Player.name.in_(player_names)).all()
    player_map = {p.name: p for p in player_objects}
    for name in player_names:
        p = player_map.get(name)
        if p:
            players_info.append({
                'name': p.name, 'rank': p.rank,
                'win_count': p.win_count, 'rate_count': p.rate_count,
                'player_id': p.id
            })

    is_completed = league.is_completed

    standings_data = []
    for i, name in enumerate(player_names):
        wins, losses = 0, 0
        for j in range(n):
            if i == j: continue
            if getattr(league, f'p{i+1}p{j+1}', None) is not None: wins += 1
            if getattr(league, f'p{j+1}p{i+1}', None) is not None: losses += 1

        total_games = wins + losses
        win_rate = (wins / total_games) * 100 if total_games > 0 else 0.0

        p = player_map.get(name)
        standings_data.append({'name': name, 'wins': wins, 'losses': losses, 'win_rate': win_rate, 'player_id': p.id if p else 0})

    sorted_standings = sorted(standings_data, key=lambda x: (x['wins'], x['win_rate'], -x['losses']), reverse=True)

    ranked_standings = []
    current_rank = 0
    last_criteria = (-1, -1, -1)

    for i, player_stats in enumerate(sorted_standings):
        current_criteria = (player_stats['wins'], player_stats['win_rate'], player_stats['losses'])
        if current_criteria != last_criteria:
            current_rank = i + 1

        player_stats['rank'] = current_rank
        ranked_standings.append(player_stats)

        last_criteria = current_criteria

    is_participant = current_user.player.name in player_names

    my_matches = []
    if is_participant:
        my_name = current_user.player.name
        my_idx = player_names.index(my_name)
        for opponent_idx, opponent_name in enumerate(player_names):
            if my_idx == opponent_idx: continue

            my_score = getattr(league, f'p{my_idx+1}p{opponent_idx+1}', None)
            opponent_score = getattr(league, f'p{opponent_idx+1}p{my_idx+1}', None)

            status = 'Submitted' if my_score is not None or opponent_score is not None else 'Not Submitted'
            opponent_player = player_map.get(opponent_name)
            if opponent_player:
                my_matches.append({
                    'opponent_name': opponent_name,
                    'status': status,
                    'opponent_id': opponent_player.id
                })
    match_history = []
    if current_user.is_admin:
        for i in range(n):
            for j in range(n):
                if i == j: continue
                if getattr(league, f'p{i+1}p{j+1}', None) is not None:
                    winner_name = player_names[i]
                    loser_name = player_names[j]
                    match_history.append({'winner': winner_name, 'loser': loser_name})

    matches = []
    for i in range(n):
        for j in range(i + 1, n):
            p1_name = player_names[i]
            p2_name = player_names[j]
            p1_player = player_map.get(p1_name)
            p2_player = player_map.get(p2_name)
            
            if not p1_player or not p2_player:
                continue
                
            p1_score_val = getattr(league, f'p{i+1}p{j+1}', None)
            p2_score_val = getattr(league, f'p{j+1}p{i+1}', None)
            
            status = 'pending'
            winner_id = None
            score_p1 = ''
            score_p2 = ''
            
            if p1_score_val is not None or p2_score_val is not None:
                status = 'completed'
                if p1_score_val is not None and p2_score_val is None:
                    winner_id = p1_player.id
                    score_p1 = 'Win'
                    score_p2 = 'Lose'
                elif p2_score_val is not None and p1_score_val is None:
                    winner_id = p2_player.id
                    score_p1 = 'Lose'
                    score_p2 = 'Win'
                    
                match_record = Match.query.filter(
                    db.or_(
                        db.and_(Match.winner == p1_player.id, Match.loser == p2_player.id),
                        db.and_(Match.winner == p2_player.id, Match.loser == p1_player.id)
                    )
                ).order_by(Match.timestamp.desc()).first()
                if match_record and match_record.score:
                    score_parts = match_record.score.split(':')
                    if len(score_parts) == 2:
                        if winner_id == p1_player.id:
                            score_p1 = score_parts[0]
                            score_p2 = score_parts[1]
                        else:
                            score_p1 = score_parts[1]
                            score_p2 = score_parts[0]
            
            matches.append({
                'id': f"{i+1}_{j+1}",
                'status': status,
                'p1_id': p1_player.id,
                'p1_name': p1_name,
                'p2_id': p2_player.id,
                'p2_name': p2_name,
                'winner_id': winner_id,
                'score_p1': score_p1,
                'score_p2': score_p2
            })

    return render_template('league_detail.html',
                        league=league,
                        players_info=players_info,
                        standings=ranked_standings,
                        is_participant=is_participant,
                        my_matches=my_matches,
                        match_history=match_history,
                        matches=matches,
                        is_completed=is_completed)


@league_bp.route('/league/<int:league_id>/revert', methods=['POST'])
@login_required
def revert_league_match(league_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('league.league_detail', league_id=league_id))

    league = League.query.get_or_404(league_id)
    winner_name = request.form.get('winner')
    loser_name = request.form.get('loser')

    player_names = league.player_names_list

    try:
        winner_idx = player_names.index(winner_name) + 1
        loser_idx = player_names.index(loser_name) + 1

        setattr(league, f'p{winner_idx}p{loser_idx}', None)
        db.session.commit()
        flash(f"'{winner_name} vs {loser_name}' 경기가 제출 이전 상태로 되돌아갔습니다.", 'success')
    except ValueError:
        flash('선수 이름을 찾을 수 없습니다.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'오류 발생: {str(e)}', 'error')

    return redirect(url_for('league.league_detail', league_id=league_id))


@league_bp.route('/tournament')
@login_required
def tournament():
    tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
    return render_template('tournament.html', tournaments=tournaments)


@league_bp.route('/tournament/create')
@login_required
def create_tournament_page():
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('league.tournament'))
    return render_template('create_tournament.html')


@league_bp.route('/tournament/generate', methods=['POST'])
@login_required
def generate_tournament():
    if not current_user.is_admin:
        return redirect(url_for('league.tournament'))

    title = request.form.get('title')
    player_names_str = request.form.get('players')
    player_names = [name.strip() for name in player_names_str.splitlines() if name.strip()]

    # 입력된 선수가 DB에 유효하게 존재하는지 검증
    for name in player_names:
        player = Player.query.filter_by(name=name, is_valid=True).first()
        if not player:
            flash(f'선수 "{name}"를 찾을 수 없습니다. 등록된 이름을 정자로 입력해 주세요.', 'error')
            return redirect(url_for('league.create_tournament_page'))

    random.shuffle(player_names)
    num_players = len(player_names)

    # 1라운드 생성
    next_power_of_2 = 1
    while next_power_of_2 < num_players: next_power_of_2 *= 2
    num_byes = next_power_of_2 - num_players

    round1_matches = []
    bye_players = player_names[:num_byes]
    match_players = player_names[num_byes:]

    match_counter = 1
    for player in bye_players:
        round1_matches.append({'id': f'R1M{match_counter}', 'p1': player, 'p2': '부전승', 'winner': player})
        match_counter += 1

    for i in range(0, len(match_players), 2):
        round1_matches.append({'id': f'R1M{match_counter}', 'p1': match_players[i], 'p2': match_players[i+1], 'winner': None})
        match_counter += 1

    # 이후 라운드 자동 생성
    rounds = [round1_matches]
    num_round = 2
    last_round_matches = round1_matches

    while len(last_round_matches) > 1:
        next_round_matches = []
        match_counter = 1
        for i in range(0, len(last_round_matches), 2):
            p1_placeholder = f"{last_round_matches[i]['id']} 승자"
            p2_placeholder = f"{last_round_matches[i+1]['id']} 승자"
            next_round_matches.append({'id': f'R{num_round}M{match_counter}', 'p1': p1_placeholder, 'p2': p2_placeholder, 'winner': None})
            match_counter += 1
        rounds.append(next_round_matches)
        last_round_matches = next_round_matches
        num_round += 1

    bracket_data = {'rounds': rounds}

    new_tournament = Tournament(title=title, bracket_data=bracket_data, status='진행중')
    db.session.add(new_tournament)
    db.session.commit()

    flash(f"'{title}' 토너먼트가 생성되었습니다!", 'success')
    return redirect(url_for('league.tournament_detail', tournament_id=new_tournament.id))


@league_bp.route('/tournament/<int:tournament_id>')
@login_required
def tournament_detail(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    
    rounds_dict = {}
    if tournament.bracket_data and 'rounds' in tournament.bracket_data:
        for i, round_matches in enumerate(tournament.bracket_data['rounds']):
            round_num = i + 1
            formatted_matches = []
            for m in round_matches:
                # 템플릿의 변수명(p1_name)과 DB 저장 구조(p1) 매핑
                formatted_match = {
                    'p1_name': m.get('p1', ''),
                    'p2_name': m.get('p2', ''),
                    'winner_name': m.get('winner', ''),
                    'score_p1': '',
                    'score_p2': ''
                }
                # 승자 표시를 템플릿 조건(`winner_id == p1_id`)과 맞추기 위해 꼼수 사용
                if formatted_match['winner_name'] and formatted_match['winner_name'] == formatted_match['p1_name']:
                    formatted_match['winner_id'] = 1
                    formatted_match['p1_id'] = 1
                    formatted_match['p2_id'] = 2
                elif formatted_match['winner_name'] and formatted_match['winner_name'] == formatted_match['p2_name']:
                    formatted_match['winner_id'] = 2
                    formatted_match['p1_id'] = 1
                    formatted_match['p2_id'] = 2
                else:
                    formatted_match['winner_id'] = 0
                    formatted_match['p1_id'] = 1
                    formatted_match['p2_id'] = 2                    
                    
                formatted_matches.append(formatted_match)
            rounds_dict[round_num] = formatted_matches

    return render_template('tournament_detail.html', tournament=tournament, rounds=rounds_dict)


@league_bp.route('/tournament/<int:tournament_id>/submit_results')
@login_required
def submit_tournament_results_page(tournament_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('league.tournament_detail', tournament_id=tournament_id))

    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.status == '완료':
        flash(_('이미 마감된 토너먼트입니다.'), 'error')
        return redirect(url_for('league.tournament_detail', tournament_id=tournament_id))
    
    matches = []
    if tournament.bracket_data and 'rounds' in tournament.bracket_data:
        for round_matches in tournament.bracket_data['rounds']:
            round_len = len(round_matches)
            if round_len == 1:
                round_name = "결승"
            elif round_len == 2:
                round_name = "4강"
            elif round_len == 4:
                round_name = "8강"
            elif round_len == 8:
                round_name = "16강"
            elif round_len == 16:
                round_name = "32강"
            else:
                round_name = f"{round_len * 2}강"

            for match in round_matches:
                # Playable matches only (both players decided, no winner yet)
                if not match.get('winner') and '승자' not in match.get('p1', '') and '승자' not in match.get('p2', ''):
                    matches.append({
                        'id': match['id'],
                        'p1_name': match['p1'],
                        'p2_name': match['p2'],
                        'round_name': round_name
                    })

    return render_template('submit_tournament_results.html', tournament=tournament, matches=matches)


@league_bp.route('/tournament/<int:tournament_id>/submit_results', methods=['POST'])
@login_required
def submit_tournament_results(tournament_id):
    if not current_user.is_admin:
        return redirect(url_for('main.index'))

    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.status == '완료':
        flash(_('이미 마감된 토너먼트입니다.'), 'error')
        return redirect(url_for('league.tournament_detail', tournament_id=tournament_id))

    bracket = tournament.bracket_data

    submitted_matches = 0
    match_ids = request.form.getlist('match_ids[]')

    for match_id in match_ids:
        winner_name = request.form.get(f"{match_id}_winner")
        if not winner_name:
            continue

        score_selected = request.form.get(f"{match_id}_score", "3:0")

        for round_matches in bracket['rounds']:
            for match in round_matches:
                if match.get('id') == match_id and not match.get('winner'):
                    p1 = match.get('p1')
                    p2 = match.get('p2')
                    loser_name = p2 if winner_name == p1 else p1

                    winner_player = Player.query.filter_by(name=winner_name).first()
                    loser_player = Player.query.filter_by(name=loser_name).first()

                    if winner_player and loser_player:
                        score_parts = score_selected.split(':')
                        win_score = score_parts[0]
                        lose_score = score_parts[1]
                        
                        score_p1_str = win_score if winner_name == p1 else lose_score
                        score_p2_str = win_score if winner_name == p2 else lose_score

                        score_formatted = f"{score_p1_str}:{score_p2_str}"

                        new_match = Match(
                            winner=winner_player.id, winner_name=winner_name,
                            loser=loser_player.id, loser_name=loser_name,
                            score=score_formatted, approved=False
                        )
                        db.session.add(new_match)
                        submitted_matches += 1

                    match['winner'] = winner_name
                    match['score_p1'] = score_p1_str
                    match['score_p2'] = score_p2_str

    # 다음 라운드의 플레이스홀더를 실제 승자 이름으로 교체
    for i in range(len(bracket['rounds']) - 1):
        current_round = bracket['rounds'][i]
        next_round = bracket['rounds'][i+1]
        for next_match in next_round:
            if '승자' in next_match['p1']:
                p1_match_id = next_match['p1'].replace(' 승자', '')
                p1_source_match = next((m for m in current_round if m.get('id') == p1_match_id), None)
                if p1_source_match and p1_source_match.get('winner'):
                    next_match['p1'] = p1_source_match['winner']

            if '승자' in next_match['p2']:
                p2_match_id = next_match['p2'].replace(' 승자', '')
                p2_source_match = next((m for m in current_round if m.get('id') == p2_match_id), None)
                if p2_source_match and p2_source_match.get('winner'):
                    next_match['p2'] = p2_source_match['winner']

    final_round = bracket['rounds'][-1]
    if len(final_round) == 1 and final_round[0].get('winner'):
        tournament.status = '완료'

    flag_modified(tournament, "bracket_data")

    db.session.commit()

    if submitted_matches > 0:
        if submitted_matches == 1:
            message = _('단일 경기 결과가 성공적으로 제출되어 승인 대기 중입니다.')
        else:
            message = _('%(num)d 개의 경기 결과가 제출되어 승인 대기 중입니다.') % {'num': submitted_matches}
        flash(message, 'success')
    else:
        flash(_('제출할 새로운 경기 결과가 없습니다.'), 'info')

    return redirect(url_for('league.tournament_detail', tournament_id=tournament_id))


@league_bp.route('/tournament/delete/<int:tournament_id>', methods=['POST'])
@login_required
def delete_tournament(tournament_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403

    tournament = Tournament.query.get_or_404(tournament_id)
    db.session.delete(tournament)
    db.session.commit()
    return jsonify({'success': True, 'message': '토너먼트가 삭제되었습니다.'})

@league_bp.route('/tournament/close/<int:tournament_id>', methods=['POST'])
@login_required
def close_tournament(tournament_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403

    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.status == '완료':
        return jsonify({'success': False, 'error': '이미 마감된 토너먼트입니다.'}), 400

    tournament.status = '완료'
    db.session.commit()
    
    return jsonify({'success': True, 'message': '토너먼트가 성공적으로 마감되었습니다.'})


# league.js API

@league_bp.route('/create_league', methods=['POST'])
@login_required
def create_league():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '관리자만 리그를 생성할 수 있습니다.'}), 403

    data = request.get_json()
    players = data.get('players', [])
    if len(players) < 4 or len(players) > 6:
        return jsonify({'error': '4명에서 6명 사이의 선수를 입력해야 합니다.'}), 400

    for name in players:
        player = Player.query.filter_by(name=name, is_valid=True).first()
        if not player:
            return jsonify({'success': False, 'error': f'선수 "{name}"를 찾을 수 없습니다.'}), 400

    league_count = League.query.count()
    provided_name = data.get('name', '').strip()
    new_league_name = provided_name if provided_name else f"League {chr(ord('A') + league_count)}"

    league_kwargs = {'name': new_league_name}
    for i, name in enumerate(players):
        league_kwargs[f'p{i+1}'] = name

    new_league = League(**league_kwargs)
    db.session.add(new_league)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{new_league_name}가 생성되었습니다.', 'league_id': new_league.id})


# league_detail.js API

@league_bp.route('/close_league/<int:league_id>', methods=['POST'])
@login_required
def close_league(league_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403

    league = League.query.get_or_404(league_id)
    league.is_closed = True

    # --- 스쿠타 포인트 보상 ---
    player_names = league.player_names_list
    n = len(player_names)

    # 순위 계산
    standings_data = []
    for i, name in enumerate(player_names):
        wins, losses = 0, 0
        for j in range(n):
            if i == j: continue
            if getattr(league, f'p{i+1}p{j+1}', None) is not None: wins += 1
            if getattr(league, f'p{j+1}p{i+1}', None) is not None: losses += 1
        total_games = wins + losses
        win_rate = (wins / total_games) * 100 if total_games > 0 else 0.0
        standings_data.append({'name': name, 'wins': wins, 'losses': losses, 'win_rate': win_rate})

    sorted_standings = sorted(standings_data, key=lambda x: (x['wins'], x['win_rate'], -x['losses']), reverse=True)

    # 참여자 전원에게 +2500 스쿠타 포인트
    for stats in sorted_standings:
        player = Player.query.filter_by(name=stats['name']).first()
        if player:
            player.scutta_count = (player.scutta_count or 0) + 2500
            add_point_log(player.id, scutta_change=2500, reason=f"리그전 '{league.display_name}' 참여 보상")

    # 1위에게 추가 +3000
    if len(sorted_standings) >= 1:
        first_name = sorted_standings[0]['name']
        first_player = Player.query.filter_by(name=first_name).first()
        if first_player:
            first_player.scutta_count = (first_player.scutta_count or 0) + 3000
            add_point_log(first_player.id, scutta_change=3000, reason=f"리그전 '{league.display_name}' 1위 보상")

    # 2위에게 추가 +2000
    if len(sorted_standings) >= 2:
        second_name = sorted_standings[1]['name']
        second_player = Player.query.filter_by(name=second_name).first()
        if second_player:
            second_player.scutta_count = (second_player.scutta_count or 0) + 2000
            add_point_log(second_player.id, scutta_change=2000, reason=f"리그전 '{league.display_name}' 2위 보상")

    db.session.commit()
    update_player_orders_by_match()

    return jsonify({'success': True, 'message': '리그전이 마감되고 스쿠타 포인트가 지급되었습니다.'})


@league_bp.route('/delete_league/<int:league_id>', methods=['DELETE'])
def delete_league(league_id):
    league = League.query.get(league_id)

    if not league:
        return jsonify({'success': False, 'error': '리그를 찾을 수 없습니다.'}), 404

    try:
        db.session.delete(league)
        db.session.commit()
        return jsonify({'success': True, 'message': '리그가 성공적으로 삭제되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'리그 삭제 중 오류 발생: {str(e)}'})


@league_bp.route('/league/<int:league_id>/submit/<int:p1_id>/<int:p2_id>')
@login_required
def league_submit_match_page(league_id, p1_id, p2_id):
    league = League.query.get_or_404(league_id)
    p1 = Player.query.get_or_404(p1_id)
    p2 = Player.query.get_or_404(p2_id)

    player_names = league.player_names_list
    if not current_user.is_admin:
        if current_user.player.name not in player_names or current_user.player.id not in [p1_id, p2_id]:
            flash(_('잘못된 접근입니다.'), 'error')
            return redirect(url_for('league.league_detail', league_id=league_id))

    is_completed = league.is_completed
    
    if is_completed:
        flash(_('이미 마감된 리그전입니다.'), 'error')
        return redirect(url_for('league.league_detail', league_id=league_id))

    return render_template('league_submit_match.html', league=league, p1=p1, p2=p2, is_completed=is_completed)


@league_bp.route('/league/<int:league_id>/submit', methods=['POST'])
@login_required
def submit_league_match(league_id):
    league = League.query.get_or_404(league_id)
    
    if league.is_completed:
        flash(_('이미 마감된 리그전입니다.'), 'error')
        return redirect(url_for('league.league_detail', league_id=league_id))

    winner_id = int(request.form.get('winner_id'))
    score = request.form.get('score')
    p1_id = int(request.form.get('p1_id'))
    p2_id = int(request.form.get('p2_id'))

    p1 = Player.query.get_or_404(p1_id)
    p2 = Player.query.get_or_404(p2_id)

    winner = p1 if winner_id == p1.id else p2
    loser = p2 if winner_id == p1.id else p1

    new_match = Match(
        winner=winner.id, winner_name=winner.name,
        loser=loser.id, loser_name=loser.name,
        score=score, approved=False
    )
    db.session.add(new_match)

    player_names = league.player_names_list
    winner_idx = player_names.index(winner.name) + 1
    loser_idx = player_names.index(loser.name) + 1

    setattr(league, f'p{winner_idx}p{loser_idx}', 1)

    db.session.commit()

    flash('%(opponent_name)s 님과의 리그 경기가 제출되었습니다. 관리자 승인을 기다립니다.' % {'opponent_name': loser.name}, 'success')
    return redirect(url_for('league.league_detail', league_id=league_id))
