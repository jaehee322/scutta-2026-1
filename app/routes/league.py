from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _
from sqlalchemy.orm.attributes import flag_modified
from ..extensions import db
from ..models import Match, Player, User, League, Tournament
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
        player_names = [l.p1, l.p2, l.p3, l.p4, l.p5]
        is_participant = current_user.player.name in player_names
        league_data.append({
            'league': l,
            'is_participant': is_participant
        })

    return render_template('league.html', league_data=league_data)


@league_bp.route('/league/<int:league_id>', methods=['GET'])
@login_required
def league_detail(league_id):
    league = League.query.get_or_404(league_id)
    player_names = [league.p1, league.p2, league.p3, league.p4, league.p5]

    players_info = []
    player_objects = Player.query.filter(Player.name.in_(player_names)).all()
    player_map = {p.name: p for p in player_objects}
    for name in player_names:
        p = player_map.get(name)
        if p:
            players_info.append({
                'name': p.name, 'rank': p.rank,
                'win_count': p.win_count, 'rate_count': p.rate_count
            })

    standings_data = []
    for i, name in enumerate(player_names):
        wins, losses = 0, 0
        for j in range(5):
            if i == j: continue
            if getattr(league, f'p{i+1}p{j+1}') is not None: wins += 1
            if getattr(league, f'p{j+1}p{i+1}') is not None: losses += 1

        total_games = wins + losses
        win_rate = (wins / total_games) * 100 if total_games > 0 else 0.0

        standings_data.append({'name': name, 'wins': wins, 'losses': losses, 'win_rate': win_rate})

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

            my_score = getattr(league, f'p{my_idx+1}p{opponent_idx+1}')
            opponent_score = getattr(league, f'p{opponent_idx+1}p{my_idx+1}')

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
        for i in range(5):
            for j in range(5):
                if i == j: continue
                if getattr(league, f'p{i+1}p{j+1}') is not None:
                    winner_name = player_names[i]
                    loser_name = player_names[j]
                    match_history.append({'winner': winner_name, 'loser': loser_name})

    return render_template('league_detail.html',
                        league=league,
                        players_info=players_info,
                        standings=ranked_standings,
                        is_participant=is_participant,
                        my_matches=my_matches,
                        match_history=match_history)


@league_bp.route('/league/<int:league_id>/revert', methods=['POST'])
@login_required
def revert_league_match(league_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('league.league_detail', league_id=league_id))

    league = League.query.get_or_404(league_id)
    winner_name = request.form.get('winner')
    loser_name = request.form.get('loser')

    player_names = [league.p1, league.p2, league.p3, league.p4, league.p5]

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
    return render_template('tournament_detail.html', tournament=tournament)


@league_bp.route('/tournament/<int:tournament_id>/submit_results')
@login_required
def submit_tournament_results_page(tournament_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('league.tournament_detail', tournament_id=tournament_id))

    tournament = Tournament.query.get_or_404(tournament_id)
    return render_template('submit_tournament_results.html', tournament=tournament)


@league_bp.route('/tournament/<int:tournament_id>/submit_results', methods=['POST'])
@login_required
def submit_tournament_results(tournament_id):
    if not current_user.is_admin:
        return redirect(url_for('main.index'))

    tournament = Tournament.query.get_or_404(tournament_id)
    bracket = tournament.bracket_data

    submitted_matches = 0
    for key, winner_name in request.form.items():
        if '_winner' in key and winner_name:
            match_id = key.replace('_winner', '')
            score = request.form.get(f"{match_id}_score", "2:0")

            for round_matches in bracket['rounds']:
                for match in round_matches:
                    if match.get('id') == match_id and not match.get('winner'):
                        p1 = match.get('p1')
                        p2 = match.get('p2')
                        loser_name = p2 if winner_name == p1 else p1

                        winner_player = Player.query.filter_by(name=winner_name).first()
                        loser_player = Player.query.filter_by(name=loser_name).first()

                        if winner_player and loser_player:
                            new_match = Match(
                                winner=winner_player.id, winner_name=winner_name,
                                loser=loser_player.id, loser_name=loser_name,
                                score=score, approved=False
                            )
                            db.session.add(new_match)
                            submitted_matches += 1

                        match['winner'] = winner_name

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
            message = _('1 개의 경기 결과가 제출되어 승인 대기 중입니다.')
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


# league.js API

@league_bp.route('/create_league', methods=['POST'])
@login_required
def create_league():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '관리자만 리그를 생성할 수 있습니다.'}), 403

    data = request.get_json()
    players = data.get('players', [])
    if len(players) != 5:
        return jsonify({'error': '정확히 5명의 선수를 입력해야 합니다.'}), 400

    for name in players:
        player = Player.query.filter_by(name=name, is_valid=True).first()
        if not player:
            return jsonify({'success': False, 'error': f'선수 "{name}"를 찾을 수 없습니다.'}), 400

    league_count = League.query.count()
    new_league_name = f"League {chr(ord('A') + league_count)}"

    new_league = League(
        name=new_league_name,
        p1=players[0], p2=players[1], p3=players[2], p4=players[3], p5=players[4]
    )
    db.session.add(new_league)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{new_league_name}가 생성되었습니다.', 'league_id': new_league.id})


# league_detail.js API

@league_bp.route('/save_league/<int:league_id>', methods=['POST'])
def save_league(league_id):
    data = request.get_json()
    league = League.query.get_or_404(league_id)

    scores = data.get('scores', {})
    for key, value in scores.items():
        if hasattr(league, key):
            setattr(league, key, value)

    db.session.commit()
    return jsonify({'success': True, 'message': '리그전이 저장되었습니다.'})


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


@league_bp.route('/league/<int:league_id>/submit/<int:opponent_id>')
@login_required
def league_submit_match_page(league_id, opponent_id):
    league = League.query.get_or_404(league_id)
    opponent = Player.query.get_or_404(opponent_id)

    player_names = [league.p1, league.p2, league.p3, league.p4, league.p5]
    if current_user.player.name not in player_names or opponent.name not in player_names:
        flash(_('잘못된 접근입니다.'), 'error')
        return redirect(url_for('league.league_detail', league_id=league_id))

    return render_template('league_submit_match.html', league=league, opponent=opponent)


@league_bp.route('/league/<int:league_id>/submit', methods=['POST'])
@login_required
def submit_league_match(league_id):
    league = League.query.get_or_404(league_id)

    winner_id = int(request.form.get('winner_id'))
    score = request.form.get('score')
    opponent_id = int(request.form.get('opponent_id'))

    me = current_user.player
    opponent = Player.query.get_or_404(opponent_id)

    winner = me if winner_id == me.id else opponent
    loser = opponent if winner_id == me.id else me

    new_match = Match(
        winner=winner.id, winner_name=winner.name,
        loser=loser.id, loser_name=loser.name,
        score=score, approved=False
    )
    db.session.add(new_match)

    player_names = [league.p1, league.p2, league.p3, league.p4, league.p5]
    winner_idx = player_names.index(winner.name) + 1
    loser_idx = player_names.index(loser.name) + 1

    setattr(league, f'p{winner_idx}p{loser_idx}', 1)

    db.session.commit()

    flash('%(opponent_name)s 님과의 리그 경기가 제출되었습니다. 관리자 승인을 기다립니다.' % {'opponent_name': opponent.name}, 'success')
    return redirect(url_for('league.league_detail', league_id=league_id))
