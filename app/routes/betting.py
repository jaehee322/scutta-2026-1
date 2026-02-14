from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _
from sqlalchemy import func
from ..extensions import db
from ..models import Match, Player, Betting, BettingParticipant, PlayerPointLog
from ..utils import add_point_log, update_player_orders_by_point
from datetime import datetime
from zoneinfo import ZoneInfo

betting_bp = Blueprint('betting', __name__)


@betting_bp.route('/betting')
@login_required
def betting_page():
    bettings = Betting.query.filter_by(submitted=False).order_by(Betting.is_closed, Betting.id.desc()).all()

    betting_data = []
    for bet in bettings:
        p1 = Player.query.get(bet.p1_id)
        p2 = Player.query.get(bet.p2_id)
        is_player = current_user.player_id in [bet.p1_id, bet.p2_id]
        betting_data.append({
            'betting': bet, 'p1_rank': p1.rank if p1 else None,
            'p2_rank': p2.rank if p2 else None, 'is_player': is_player
        })

    return render_template('betting.html', betting_data=betting_data)


@betting_bp.route('/betting/<int:betting_id>/toggle_close', methods=['POST'])
@login_required
def toggle_betting_status(betting_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('betting.betting_page'))

    betting = Betting.query.get_or_404(betting_id)
    betting.is_closed = not betting.is_closed
    db.session.commit()

    status = "마감" if betting.is_closed else "진행중"
    flash(f"'{betting.p1_name} vs {betting.p2_name}' 베팅이 '{status}' 상태로 변경되었습니다.", 'success')
    return redirect(url_for('betting.betting_page'))


@betting_bp.route('/betting_approval')
@login_required
def betting_approval():
    if not current_user.is_admin:
        flash(_('관리자만 접근할 수 있는 페이지입니다.'), 'error')
        return redirect(url_for('main.index'))
    return render_template('betting_approval.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@betting_bp.route('/get_bettings', methods=['GET'])
def get_bettings():
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 30))
    tab = request.args.get('tab', 'all')
    query = Betting.query.filter(Betting.submitted == True).order_by(Betting.approved, Betting.id.desc())
    if tab == 'pending': query = query.filter(Betting.approved == False)
    elif tab == 'approved': query = query.filter(Betting.approved == True)
    bettings = query.offset(offset).limit(limit).all()
    match_ids = [b.result for b in bettings]
    matches = Match.query.filter(Match.id.in_(match_ids)).all()
    match_response = {m.id: {'id': m.id, 'winner_name': m.winner_name, 'winner_id': m.winner, 'loser_name': m.loser_name, 'score': m.score} for m in matches}
    response = []
    for betting in bettings:
        match_info = match_response.get(betting.result)
        if match_info:
            participants = [{'id': p.id, 'participant_name': p.participant_name, 'winner_id': p.winner_id, 'betting_id': p.betting_id} for p in betting.participants]
            win_participants = [p['participant_name'] for p in participants if p['winner_id'] == match_info['winner_id']]
            lose_participants = [p['participant_name'] for p in participants if p['winner_id'] != match_info['winner_id']]
            response.append({'id': betting.id, 'match_id': betting.result, 'participants': participants, 'point': betting.point, 'approved': betting.approved, 'match': match_info, 'win_participants': win_participants, 'lose_participants': lose_participants})
    return jsonify(response)


@betting_bp.route('/delete_bettings', methods=['POST'])
def delete_bettings():
    ids = request.json.get('ids', [])
    if not ids: return jsonify({'error': '삭제할 베팅이 선택되지 않았습니다.'}), 400
    bettings_to_delete = Betting.query.filter(Betting.id.in_(ids)).all()
    approved_count = pending_count = 0
    for betting in bettings_to_delete:
        if not betting.approved:
            pending_count += 1; continue
        approved_count += 1
        match = Match.query.get(betting.result)
        if not match: continue
        winner = Player.query.get(match.winner)
        loser = Player.query.get(match.loser)
        if not winner or not loser: continue
        participants = betting.participants
        correct_bettors = [p for p in participants if p.winner_id == winner.id]
        total_sharers = 1 + len(correct_bettors)
        total_pot = betting.point * (2 + len(participants))
        share = total_pot // total_sharers
        winner.betting_count -= share
        add_point_log(winner.id, betting_change=-share, reason=f"베팅({betting.id}) 삭제 (상금 회수)")
        for p in correct_bettors:
            bp = Player.query.get(p.participant_id)
            if bp: bp.betting_count -= share; add_point_log(bp.id, betting_change=-share, reason=f"베팅({betting.id}) 삭제 (상금 회수)")
        winner.betting_count += betting.point
        add_point_log(winner.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")
        loser.betting_count += betting.point
        add_point_log(loser.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")
        for p in participants:
            pp = Player.query.get(p.participant_id)
            if pp: pp.betting_count += betting.point; add_point_log(pp.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")
    if bettings_to_delete:
        BettingParticipant.query.filter(BettingParticipant.betting_id.in_(ids)).delete(synchronize_session=False)
        Betting.query.filter(Betting.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    update_player_orders_by_point()
    return jsonify({'success': True, 'message': f'{approved_count}개의 승인된 베팅과 {pending_count}개의 미승인된 베팅이 삭제되었습니다.'})


@betting_bp.route('/select_all_bettings', methods=['GET'])
def select_all_bettings():
    bettings = Betting.query.filter_by(approved=False).all()
    return jsonify({'ids': [b.id for b in bettings]})


@betting_bp.route('/get_players_ranks', methods=['POST'])
def get_players_ranks():
    data = request.get_json()
    players = data.get('players', [])
    p1 = Player.query.filter_by(name=players[0]).first()
    p2 = Player.query.filter_by(name=players[1]).first()
    if not p1 or not p2: return jsonify({'error': '선수를 찾을 수 없습니다.'}), 400
    rank_gap = abs(p1.rank - p2.rank) if p1.rank is not None and p2.rank is not None else None
    return jsonify({'p1_rank': p1.rank, 'p2_rank': p2.rank, 'rank_gap': rank_gap})


@betting_bp.route('/get_betting_counts', methods=['POST'])
def get_betting_counts():
    data = request.get_json()
    players = data.get('players', [])
    participants = data.get('participants', [])
    p1 = Player.query.filter_by(name=players[0]).first()
    p2 = Player.query.filter_by(name=players[1]).first()
    if not p1 or not p2: return jsonify({'success': False, 'error': '선수를 찾을 수 없습니다.'}), 400
    participant_data = []
    for pn in participants:
        p = Player.query.filter_by(name=pn.strip()).first()
        if p:
            if p.name == p1.name or p.name == p2.name: continue
            participant_data.append({'name': p.name, 'betting_count': p.betting_count})
        else:
            return jsonify({'success': False, 'error': f'베팅 참가자 "{pn}"을/를 찾을 수 없습니다.'}), 400
    return jsonify({'success': True, 'p1': {'name': p1.name, 'betting_count': p1.betting_count}, 'p2': {'name': p2.name, 'betting_count': p2.betting_count}, 'participants': participant_data})


@betting_bp.route('/create_betting', methods=['POST'])
def create_betting():
    data = request.get_json()
    players = data.get('players', [])
    participants = data.get('participants', [])
    point = data.get('point')
    if len(players) != 2: return jsonify({'error': '정확히 2명의 선수를 입력해야 합니다.'}), 400
    if not isinstance(point, int) or point <= 0: return jsonify({'error': '유효한 점수를 입력하세요.'}), 400
    p1 = Player.query.filter_by(name=players[0]).first()
    p2 = Player.query.filter_by(name=players[1]).first()
    if not p1 or not p2: return jsonify({'error': '선수를 찾을 수 없습니다.'}), 400
    new_betting = Betting(p1_id=p1.id, p1_name=p1.name, p2_id=p2.id, p2_name=p2.name, point=point)
    db.session.add(new_betting)
    db.session.flush()
    for pn in participants:
        p = Player.query.filter_by(name=pn.strip()).first()
        if p and p.name != p1.name and p.name != p2.name:
            db.session.add(BettingParticipant(betting_id=new_betting.id, participant_name=pn.strip(), participant_id=p.id))
    db.session.commit()
    return jsonify({'success': True, 'message': '베팅이 생성되었습니다.', 'betting_id': new_betting.id})


@betting_bp.route('/betting/<int:betting_id>/admin')
@login_required
def betting_detail(betting_id):
    if not current_user.is_admin:
        flash(_('관리자만 접근할 수 있는 페이지입니다.'), 'error')
        return redirect(url_for('main.index'))
    betting = Betting.query.get_or_404(betting_id)
    p1 = Player.query.get_or_404(betting.p1_id)
    p2 = Player.query.get_or_404(betting.p2_id)
    all_matches = Match.query.filter(
        ((Match.winner == p1.id) & (Match.loser == p2.id)) |
        ((Match.winner == p2.id) & (Match.loser == p1.id)),
        Match.approved == True
    ).order_by(Match.timestamp.desc()).all()
    p1_wins = sum(1 for m in all_matches if m.winner == p1.id)
    p2_wins = len(all_matches) - p1_wins
    all_players_data = [{'id': p.id, 'name': p.name} for p in Player.query.filter_by(is_valid=True).order_by(Player.name).all()]
    return render_template('betting_detail_admin.html', betting=betting, participants=betting.participants,
                          win_rate={'p1_wins': p1_wins, 'p2_wins': p2_wins}, recent_matches=all_matches, all_players=all_players_data)


@betting_bp.route('/betting/<int:betting_id>/view')
@login_required
def betting_detail_for_user(betting_id):
    betting = Betting.query.get_or_404(betting_id)
    p1 = Player.query.get_or_404(betting.p1_id)
    p2 = Player.query.get_or_404(betting.p2_id)
    all_matches = Match.query.filter(
        ((Match.winner == p1.id) & (Match.loser == p2.id)) |
        ((Match.winner == p2.id) & (Match.loser == p1.id)),
        Match.approved == True
    ).order_by(Match.timestamp.desc()).all()
    p1_wins = sum(1 for m in all_matches if m.winner == p1.id)
    p2_wins = len(all_matches) - p1_wins
    participants = betting.participants
    is_player = current_user.player_id in [betting.p1_id, betting.p2_id]
    my_choice = BettingParticipant.query.filter_by(betting_id=betting_id, participant_id=current_user.player_id).first()
    p1_bettors = sum(1 for p in participants if p.winner_id == betting.p1_id)
    p2_bettors = sum(1 for p in participants if p.winner_id == betting.p2_id)
    total = p1_bettors + p2_bettors
    p1_pct = (p1_bettors / total) * 100 if total > 0 else 50
    betting_stats = {'p1_bettors': p1_bettors, 'p2_bettors': p2_bettors, 'p1_percent': p1_pct, 'p2_percent': 100 - p1_pct}
    return render_template('betting_detail_for_user.html', betting=betting, participants=participants,
                          win_rate={'p1_wins': p1_wins, 'p2_wins': p2_wins}, recent_matches=all_matches,
                          my_choice=my_choice, ranks={'p1_rank': p1.rank, 'p2_rank': p2.rank},
                          is_player=is_player, betting_stats=betting_stats)


@betting_bp.route('/bet/place', methods=['POST'])
@login_required
def place_bet():
    betting_id = request.form.get('betting_id', type=int)
    winner_id = request.form.get('winner_id', type=int)
    betting = Betting.query.get_or_404(betting_id)
    if betting.is_closed:
        flash(_('마감된 베팅에는 참여할 수 없습니다.'), 'error')
        return redirect(url_for('betting.betting_detail_for_user', betting_id=betting_id))
    if current_user.player_id in [betting.p1_id, betting.p2_id]:
        flash(_('자신의 경기에는 베팅할 수 없습니다.'), 'error')
        return redirect(url_for('betting.betting_detail_for_user', betting_id=betting_id))
    if betting.submitted:
        flash(_('이미 경기 결과가 제출된 베팅입니다.'), 'error')
        return redirect(url_for('betting.betting_detail_for_user', betting_id=betting_id))
    record = BettingParticipant.query.filter_by(betting_id=betting_id, participant_id=current_user.player_id).first()
    if record:
        record.winner_id = winner_id
        flash(_('베팅을 성공적으로 변경했습니다.'), 'success')
    else:
        db.session.add(BettingParticipant(betting_id=betting_id, participant_id=current_user.player_id, participant_name=current_user.player.name, winner_id=winner_id))
        flash(_('베팅에 성공적으로 참여했습니다.'), 'success')
    db.session.commit()
    return redirect(url_for('betting.betting_detail_for_user', betting_id=betting_id))


@betting_bp.route('/betting/create')
@login_required
def create_betting_page():
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('betting.betting_page'))
    players = Player.query.filter_by(is_valid=True).order_by(Player.name).all()
    return render_template('create_betting.html', players=players)


@betting_bp.route('/submit_betting_result', methods=['POST'])
@login_required
def submit_betting_result():
    if not current_user.is_admin:
        return jsonify({"error": "권한이 없습니다."}), 403
    data = request.get_json()
    betting_id = data.get('bettingId')
    winner_name = data.get('winnerName')
    score = data.get('score')
    if not (betting_id and winner_name and score):
        return jsonify({"error": "모든 필드를 입력해주세요."}), 400
    betting = Betting.query.get_or_404(betting_id)
    if betting.submitted:
        return jsonify({"error": "이미 결과가 제출된 베팅입니다."}), 400
    loser_name = betting.p2_name if winner_name == betting.p1_name else betting.p1_name
    winner = Player.query.filter_by(name=winner_name).first()
    loser = Player.query.filter_by(name=loser_name).first()
    if not winner or not loser:
        return jsonify({"error": "선수 정보를 찾을 수 없습니다."}), 400
    new_match = Match(winner=winner.id, winner_name=winner.name, loser=loser.id, loser_name=loser.name, score=score, approved=False)
    db.session.add(new_match)
    db.session.flush()
    betting.result = new_match.id
    betting.submitted = True
    betting.is_closed = True
    participants = betting.participants
    win_names = [p.participant_name for p in participants if p.winner_id == winner.id]
    lose_names = [p.participant_name for p in participants if p.winner_id is not None and p.winner_id != winner.id]
    total_sharers = 1 + len(win_names)
    total_pot = betting.point * (2 + len(participants))
    share = total_pot // total_sharers if total_sharers > 0 else 0
    db.session.commit()
    return jsonify({"success": True, "message": "베팅 결과가 성공적으로 처리되었습니다!",
                   "results": {"winnerName": winner.name, "loserName": loser.name, "winParticipants": win_names, "loseParticipants": lose_names, "distributedPoints": share}}), 200


@betting_bp.route('/approve_bettings', methods=['POST'])
def approve_bettings():
    ids = request.json.get('ids', [])
    if not ids: return jsonify({'success': False, 'message': '승인할 베팅이 선택되지 않았습니다.'}), 400
    bettings = Betting.query.filter(Betting.id.in_(ids), Betting.approved == False).all()
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    for betting in bettings:
        match = Match.query.get(betting.result)
        if not match: continue
        actual_winner_id = match.winner
        winner_player = Player.query.get(actual_winner_id)
        loser_player = Player.query.get(match.loser)
        if not winner_player or not loser_player: continue
        betting_reason = f"{winner_player.name} vs {loser_player.name} 베팅"
        winner_player.betting_count -= betting.point
        add_point_log(winner_player.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 주최")
        loser_player.betting_count -= betting.point
        add_point_log(loser_player.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 주최")
        participants = betting.participants
        for p in participants:
            pp = Player.query.get(p.participant_id)
            if pp: pp.betting_count -= betting.point; add_point_log(pp.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 참여")
        correct_bettors = [p for p in participants if p.winner_id == actual_winner_id]
        total_pot = betting.point * (2 + len(participants))
        total_sharers = 1 + len(correct_bettors)
        share = total_pot // total_sharers if total_sharers > 0 else 0
        for p in correct_bettors:
            bp = Player.query.get(p.participant_id)
            if bp: bp.betting_count += share; add_point_log(bp.id, betting_change=share, reason=f"{betting_reason} 성공")
        winner_player.betting_count += share
        add_point_log(winner_player.id, betting_change=share, reason=f"{betting_reason} 경기 승리")
        betting.approved = True
        if today.weekday() == 4:
            all_involved = [winner_player, loser_player] + [Player.query.get(p.participant_id) for p in participants]
            for player in all_involved:
                if not player: continue
                bonus = PlayerPointLog.query.filter(PlayerPointLog.player_id == player.id, PlayerPointLog.reason == "베팅 데이", func.date(PlayerPointLog.timestamp) == today).first()
                if not bonus: player.betting_count += 10; add_point_log(player.id, betting_change=10, reason="베팅 데이")
    db.session.commit()
    update_player_orders_by_point()
    return jsonify({"success": True, "message": "선택한 베팅이 승인되었습니다."})


@betting_bp.route('/add_participants', methods=['POST'])
@login_required
def add_participants():
    if not current_user.is_admin: return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403
    data = request.get_json()
    betting_id = data.get('bettingId')
    player_ids = data.get('playerIds', [])
    if not betting_id or not player_ids: return jsonify({'success': False, 'error': '필수 정보가 누락되었습니다.'}), 400
    betting = Betting.query.get(betting_id)
    if not betting: return jsonify({'success': False, 'error': '해당 베팅을 찾을 수 없습니다.'}), 404
    if betting.submitted: return jsonify({'success': False, 'error': '이미 결과가 제출된 베팅입니다.'}), 400
    added = 0
    for pid in player_ids:
        existing = BettingParticipant.query.filter_by(betting_id=betting_id, participant_id=pid).first()
        pi = Player.query.get(pid)
        if not existing and pi:
            db.session.add(BettingParticipant(betting_id=betting_id, participant_name=pi.name, participant_id=pid))
            added += 1
    db.session.commit()
    return jsonify({'success': True, 'message': f'{added}명의 참가자가 추가되었습니다.'})


@betting_bp.route('/remove_participants', methods=['POST'])
@login_required
def remove_participants():
    if not current_user.is_admin: return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403
    data = request.get_json()
    betting_id = data.get('bettingId')
    player_ids = data.get('playerIds', [])
    if not betting_id or not player_ids: return jsonify({'success': False, 'error': '필수 정보가 누락되었습니다.'}), 400
    betting = Betting.query.get(betting_id)
    if not betting: return jsonify({'success': False, 'error': '해당 베팅을 찾을 수 없습니다.'}), 404
    if betting.submitted: return jsonify({'success': False, 'error': '이미 결과가 제출된 베팅입니다.'}), 400
    n = BettingParticipant.query.filter(BettingParticipant.betting_id == betting_id, BettingParticipant.participant_id.in_(player_ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{n}명의 참가자가 삭제되었습니다.'}) if n > 0 else jsonify({'success': False, 'error': '삭제할 참가자를 찾지 못했습니다.'})


@betting_bp.route('/betting/<int:betting_id>/delete', methods=['POST'])
@login_required
def delete_betting(betting_id):
    if not current_user.is_admin: return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403
    data = request.get_json()
    if data.get('password', '') != 'yeong6701': return jsonify({'success': False, 'error': '비밀번호가 올바르지 않습니다.'}), 403
    betting = Betting.query.get_or_404(betting_id)
    try:
        db.session.delete(betting)
        db.session.commit()
        return jsonify({'success': True, 'message': '베팅이 성공적으로 삭제되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'삭제 중 오류가 발생했습니다: {str(e)}'}), 500


@betting_bp.route('/betting/<int:betting_id>/update', methods=['POST'])
def update_betting(betting_id):
    if not current_user.is_admin: return jsonify({'error': '권한이 없습니다.'}), 403
    betting = Betting.query.get_or_404(betting_id)
    if betting.submitted: return jsonify({'error': '이미 경기 결과가 제출된 베팅은 수정할 수 없습니다.'}), 400
    data = request.get_json()
    new_participants_data = data.get('participants', [])
    try:
        existing_ids = {p.participant_id for p in betting.participants}
        new_ids = {pd.get('id') for pd in new_participants_data}
        to_delete = existing_ids - new_ids
        if to_delete:
            BettingParticipant.query.filter(BettingParticipant.betting_id == betting_id, BettingParticipant.participant_id.in_(to_delete)).delete(synchronize_session=False)
        existing_map = {p.participant_id: p.winner_id for p in betting.participants}
        for pd in new_participants_data:
            pid = pd.get('id')
            new_winner = pd.get('winner')
            if pid in existing_map:
                if existing_map[pid] is not None and existing_map[pid] != new_winner:
                    db.session.rollback()
                    return jsonify({'error': f'이미 저장된 베팅은 수정할 수 없습니다. ({Player.query.get(pid).name}님의 예측)'}), 400
                else:
                    rec = BettingParticipant.query.filter_by(betting_id=betting.id, participant_id=pid).first()
                    if rec and rec.winner_id is None: rec.winner_id = new_winner
            else:
                player = Player.query.get(pid)
                if player: db.session.add(BettingParticipant(betting_id=betting.id, participant_name=player.name, participant_id=player.id, winner_id=new_winner))
        db.session.commit()
        return jsonify({'success': True, 'message': '베팅 참가자가 업데이트되었습니다!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'서버 오류가 발생했습니다: {str(e)}'}), 500
