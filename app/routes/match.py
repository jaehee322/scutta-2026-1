from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _
from ..extensions import db
from ..models import Match, Player, User, TodayPartner, UpdateLog, Betting
from ..utils import add_point_log, calculate_opponent_count, update_player_orders_by_match, update_player_orders_by_point
from datetime import datetime
from zoneinfo import ZoneInfo
from ..models import GenderEnum, FreshmanEnum

match_bp = Blueprint('match', __name__)


@match_bp.route('/submitment')
@login_required
def submitment():
    return render_template('submitment.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@match_bp.route('/submit_match_direct', methods=['POST'])
@login_required
def submit_match_direct():
    winner_name = request.form.get('winner_name')
    loser_name = request.form.get('loser_name')
    score = request.form.get('score')

    if not winner_name or not loser_name or not score:
        flash(_('모든 필드를 올바르게 입력해주세요.'), 'error')
        return redirect(url_for('main.index'))

    if winner_name == loser_name:
        flash(_('승리자와 패배자는 다른 사람이어야 합니다.'), 'error')
        return redirect(url_for('main.index'))

    winner = Player.query.filter_by(name=winner_name, is_valid=True).first()
    loser = Player.query.filter_by(name=loser_name, is_valid=True).first()

    if not winner or not loser:
        unknown = []
        if not winner: unknown.append(winner_name)
        if not loser: unknown.append(loser_name)
        names_str = ", ".join(unknown)
        flash(_('등록되지 않은 선수 이름이 있습니다: %(names)s') % {'names': names_str}, 'error')
        return redirect(url_for('main.index'))

    # 1. index 함수와 동일하게, 가장 최신(id가 가장 높은) 파트너 기록을 찾습니다.
    today_partner = TodayPartner.query.filter(
        (
            (TodayPartner.p1_id == winner.id) & (TodayPartner.p2_id == loser.id)
        ) | (
            (TodayPartner.p1_id == loser.id) & (TodayPartner.p2_id == winner.id)
        )
    ).order_by(TodayPartner.id.desc()).first()

    if today_partner:
        today_partner.submitted = True
        # 2. 수정된 정보를 DB 세션에 확실하게 추가합니다.
        db.session.add(today_partner)

    # Match 객체 생성
    new_match = Match(
        winner=winner.id,
        winner_name=winner.name,
        loser=loser.id,
        loser_name=loser.name,
        score=score,
        approved=False
    )
    db.session.add(new_match)

    # 3. 모든 변경사항(파트너 상태, 새 경기)을 한번에 저장합니다.
    db.session.commit()

    flash(_('경기 결과가 성공적으로 제출되었습니다. 관리자 승인 대기 중입니다.'), 'success')
    return redirect(url_for('main.index'))


@match_bp.route('/submit_match')
@login_required
def submit_match_page():
    my_matches = Match.query.filter(
        (Match.winner == current_user.player_id) | (Match.loser == current_user.player_id)
    ).order_by(Match.timestamp.desc()).limit(10).all()

    all_players_objects = Player.query.join(User).filter(
        Player.is_valid == True,
        User.is_admin == False
    ).order_by(Player.name).all()

    all_players_data = [
        {'id': player.id, 'name': player.name}
        for player in all_players_objects
    ]

    return render_template('submit_match.html', matches=my_matches, all_players=all_players_data)


@match_bp.route('/my_submissions')
@login_required
def my_submissions():
    my_matches = Match.query.filter(
        (Match.winner == current_user.player_id) | (Match.loser == current_user.player_id)
    ).order_by(Match.timestamp.desc()).limit(5).all()

    return render_template('my_submissions.html', matches=my_matches)


@match_bp.route('/check_players', methods=['POST'])
def check_players():
    matches = request.json.get('matches', [])
    player_names = set()
    for match in matches:
        player_names.add(match['winner'])
        player_names.add(match['loser'])

    existing_players = {player.name for player in Player.query.filter(Player.name.in_(player_names), Player.is_valid == True).all()}
    unknown_players = list(player_names - existing_players)

    return jsonify({'unknownPlayers': unknown_players})


@match_bp.route('/submit_matches', methods=['POST'])
def submit_matches():
    # 함수 전체를 try...except 블록으로 감싸서 숨겨진 오류를 잡아냅니다.
    try:
        matches = request.get_json()

        if not matches or not isinstance(matches, list):
            return jsonify({"error": "올바른 데이터를 제출해주세요."}), 400

        for match in matches:
            if not isinstance(match, dict):
                return jsonify({"error": "각 경기 데이터는 객체 형식이어야 합니다."}), 400

            winner_name = match.get('winner')
            loser_name = match.get('loser')
            score_value = match.get('score')
            league_tf = match.get('league')

            if not winner_name or not loser_name or not score_value:
                continue

            winner = Player.query.filter_by(name=winner_name).first()
            loser = Player.query.filter_by(name=loser_name).first()

            if not winner or not loser:
                print(f"Player not found, skipping match: Winner={winner_name}, Loser={loser_name}")
                continue

            current_time = datetime.now(ZoneInfo("Asia/Seoul"))

            new_match = Match(
                winner=winner.id,
                winner_name=winner.name,
                loser=loser.id,
                loser_name=loser.name,
                score=score_value,
                timestamp=current_time,
                approved=False
            )
            db.session.add(new_match)

            today_partner = TodayPartner.query.filter_by(p1_name=winner_name, p2_name=loser_name).first()
            if not today_partner:
                today_partner = TodayPartner.query.filter_by(p1_name=loser_name, p2_name=winner_name).first()

            if today_partner:
                today_partner.submitted = True

            if league_tf:
                winner.betting_count += 3
                add_point_log(winner.id, betting_change=3, reason=f"{loser.name} 상대 경기 승리")
                update_player_orders_by_point()

        db.session.commit()
        return jsonify({'success': True, 'message': f"{len(matches)}개의 경기 결과가 제출되었습니다!"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Submit matches error : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': '서버 내부에서 처리되지 않은 심각한 오류 발생', 'message': str(e)}), 500


@match_bp.route('/get_matches', methods=['GET'])
def get_matches():
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 30))
    tab = request.args.get('tab', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Match.query.order_by(Match.approved, Match.timestamp.desc())

    if tab == 'pending':
        query = query.filter(Match.approved == False)
    elif tab == 'approved':
        query = query.filter(Match.approved == True)

    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=00, minute=00, second=00)
            end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Match.timestamp >= start_date, Match.timestamp <= end_date)
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

    matches = query.offset(offset).limit(limit).all()

    response = [
        {
            'id': match.id,
            'winner_name': match.winner_name,
            'loser_name': match.loser_name,
            'score': match.score,
            'approved': match.approved,
            'timestamp': match.timestamp
        }
        for match in matches
    ]
    return jsonify(response)


def _approve_single_match(match):
    winner = Player.query.get(match.winner)
    loser = Player.query.get(match.loser)
    if not winner or not loser:
        return

    match.approved = True

    winner.match_count += 1
    winner.win_count += 1
    winner.rate_count = round((winner.win_count / winner.match_count) * 100, 2)
    winner_previous_opponent = winner.opponent_count
    winner.opponent_count = calculate_opponent_count(winner.id)

    winner.betting_count += 1
    add_point_log(winner.id, betting_change=1, reason='경기 결과 제출')

    loser.match_count += 1
    loser.loss_count += 1
    loser.rate_count = round((loser.win_count / loser.match_count) * 100, 2)
    loser_previous_opponent = loser.opponent_count
    loser.opponent_count = calculate_opponent_count(loser.id)

    loser.betting_count += 1
    add_point_log(loser.id, betting_change=1, reason='경기 결과 제출')

    if winner.match_count == 30:
        winner.betting_count += 10
        winner.achieve_count += 5
        add_point_log(winner.id, betting_change=10, reason='30경기 달성!')
        add_point_log(winner.id, achieve_change=5, reason='30경기 달성!')
    if winner.match_count == 50:
        winner.betting_count += 20
        winner.achieve_count += 10
        add_point_log(winner.id, betting_change=20, reason='50경기 달성!')
        add_point_log(winner.id, achieve_change=10, reason='50경기 달성!')
    if winner.match_count == 70:
        winner.betting_count += 40
        winner.achieve_count += 20
        add_point_log(winner.id, betting_change=40, reason='70경기 달성!')
        add_point_log(winner.id, achieve_change=20, reason='70경기 달성!')

    if winner.match_count == 100:
        winner.betting_count += 60
        winner.achieve_count += 30
        add_point_log(winner.id, betting_change=60, reason='100경기 달성!')
        add_point_log(winner.id, achieve_change=30, reason='100경기 달성!')

    if winner.win_count == 20:
        winner.betting_count += 20
        winner.achieve_count += 10
        add_point_log(winner.id, betting_change=20, reason='누적 20승 달성!')
        add_point_log(winner.id, achieve_change=10, reason='누적 20승 달성!')

    if winner.win_count == 35:
        winner.betting_count += 40
        winner.achieve_count += 20
        add_point_log(winner.id, betting_change=40, reason='누적 35승 달성!')
        add_point_log(winner.id, achieve_change=20, reason='누적 35승 달성!')

    if winner.win_count == 50:
        winner.betting_count += 60
        winner.achieve_count += 30
        add_point_log(winner.id, betting_change=60, reason='누적 50승 달성!')
        add_point_log(winner.id, achieve_change=30, reason='누적 50승 달성!')

    if winner_previous_opponent == 9 and winner.opponent_count == 10:
        winner.betting_count += 10
        winner.achieve_count += 5
        add_point_log(winner.id, betting_change=10, reason='누적 상대 수 10명 달성!')
        add_point_log(winner.id, achieve_change=5, reason='누적 상대 수 10명 달성!')

    if winner_previous_opponent == 24 and winner.opponent_count == 25:
        winner.betting_count += 40
        winner.achieve_count += 20
        add_point_log(winner.id, betting_change=40, reason='누적 상대 수 25명 달성!')
        add_point_log(winner.id, achieve_change=20, reason='누적 상대 수 25명 달성!')

    if winner_previous_opponent == 39 and winner.opponent_count == 40:
        winner.betting_count += 60
        winner.achieve_count += 30
        add_point_log(winner.id, betting_change=60, reason='누적 상대 수 40명 달성!')
        add_point_log(winner.id, achieve_change=30, reason='누적 상대 수 40명 달성!')

    if loser.match_count == 30:
        loser.betting_count += 10
        loser.achieve_count += 5
        add_point_log(loser.id, betting_change=10, reason='30경기 달성!')
        add_point_log(loser.id, achieve_change=5, reason='30경기 달성!')

    if loser.match_count == 50:
        loser.betting_count += 20
        loser.achieve_count += 10
        add_point_log(loser.id, betting_change=20, reason='50경기 달성!')
        add_point_log(loser.id, achieve_change=10, reason='50경기 달성!')

    if loser.match_count == 70:
        loser.betting_count += 40
        loser.achieve_count += 20
        add_point_log(loser.id, betting_change=40, reason='70경기 달성!')
        add_point_log(loser.id, achieve_change=20, reason='70경기 달성!')

    if loser.match_count == 100:
        loser.betting_count += 60
        loser.achieve_count += 30
        add_point_log(loser.id, betting_change=60, reason='100경기 달성!')
        add_point_log(loser.id, achieve_change=30, reason='100경기 달성!')

    if loser.loss_count == 20:
        loser.betting_count += 10
        loser.achieve_count += 10
        add_point_log(loser.id, betting_change=10, reason='누적 20패 달성!')
        add_point_log(loser.id, achieve_change=10, reason='누적 20패 달성!')

    if loser.loss_count == 35:
        loser.betting_count += 20
        loser.achieve_count += 20
        add_point_log(loser.id, betting_change=20, reason='누적 35패 달성!')
        add_point_log(loser.id, achieve_change=20, reason='누적 35패 달성!')

    if loser.loss_count == 50:
        loser.betting_count += 30
        loser.achieve_count += 30
        add_point_log(loser.id, betting_change=30, reason='누적 50패 달성!')
        add_point_log(loser.id, achieve_change=30, reason='누적 50패 달성!')

    if loser_previous_opponent == 9 and loser.opponent_count == 10:
        loser.betting_count += 10
        loser.achieve_count += 5
        add_point_log(loser.id, betting_change=10, reason='누적 상대 수 10명 달성!')
        add_point_log(loser.id, achieve_change=5, reason='누적 상대 수 10명 달성!')

    if loser_previous_opponent == 24 and loser.opponent_count == 25:
        loser.betting_count += 40
        loser.achieve_count += 20
        add_point_log(loser.id, betting_change=40, reason='누적 상대 수 25명 달성!')
        add_point_log(loser.id, achieve_change=20, reason='누적 상대 수 25명 달성!')

    if loser_previous_opponent == 39 and loser.opponent_count == 40:
        loser.betting_count += 60
        loser.achieve_count += 30
        add_point_log(loser.id, betting_change=60, reason='누적 상대 수 40명 달성!')
        add_point_log(loser.id, achieve_change=30, reason='누적 상대 수 40명 달성!')

    today_partner = TodayPartner.query.filter_by(p1_id=match.winner, p2_id=match.loser, submitted=True).first()
    if not today_partner:
        today_partner = TodayPartner.query.filter_by(p1_id=match.loser, p2_id=match.winner, submitted=True).first()

    if today_partner:
        winner.betting_count += 5
        winner.achieve_count += 1
        add_point_log(winner.id, betting_change=5, reason='오늘의 상대 경기 결과 제출!')
        add_point_log(winner.id, achieve_change=1, reason='오늘의 상대 경기 결과 제출!')
        loser.betting_count += 5
        loser.achieve_count += 1
        add_point_log(loser.id, betting_change=5, reason='오늘의 상대 경기 결과 제출!')
        add_point_log(loser.id, achieve_change=1, reason='오늘의 상대 경기 결과 제출!')

    if match.timestamp.weekday() == 6:
        winner.achieve_count += 1; winner.betting_count += 3
        loser.achieve_count += 1; loser.betting_count += 3
        add_point_log(winner.id, betting_change=3, reason='안 쉬세요??')
        add_point_log(winner.id, achieve_change=1, reason='안 쉬세요??')
        add_point_log(loser.id, betting_change=3, reason='안 쉬세요??')
        add_point_log(loser.id, achieve_change=1, reason='안 쉬세요??')

    if winner.is_she_or_he_freshman == FreshmanEnum.YES and winner.match_count == 16:
        if winner.gender == GenderEnum.MALE:
            winner.rank = 5
        elif winner.gender == GenderEnum.FEMALE:
            winner.rank = 7


    if loser.is_she_or_he_freshman == FreshmanEnum.YES and loser.match_count == 16:
        if loser.gender == GenderEnum.MALE:
            loser.rank = 5
        elif loser.gender == GenderEnum.FEMALE:
            loser.rank = 7


def _delete_single_match(match):
    was_approved = match.approved
    if match.approved:
        winner = Player.query.get(match.winner)
        loser = Player.query.get(match.loser)

        if not winner or not loser:
            db.session.delete(match)
            return 'approved'

        # --- 승인된 경기의 모든 스탯 되돌리기 ---
        winner.match_count -= 1
        winner.win_count -= 1
        winner.rate_count = round((winner.win_count / winner.match_count) * 100, 2) if winner.match_count > 0 else 0
        winner_previous_opponent = winner.opponent_count
        winner.opponent_count = calculate_opponent_count(winner.id)

        winner.betting_count -= 1
        add_point_log(winner.id, betting_change=-1, reason='경기 결과 제출 취소')

        loser.match_count -= 1
        loser.loss_count -= 1
        loser.rate_count = round((loser.win_count / loser.match_count) * 100, 2) if loser.match_count > 0 else 0
        loser_previous_opponent = loser.opponent_count
        loser.opponent_count = calculate_opponent_count(loser.id)

        loser.betting_count -= 1
        add_point_log(loser.id, betting_change=-1, reason='경기 결과 제출 취소')

        if winner.match_count == 29:
            winner.betting_count -= 10
            winner.achieve_count -= 5
            add_point_log(winner.id, betting_change=-10, reason='누적 30경기 달성 취소')
            add_point_log(winner.id, achieve_change=-5, reason='누적 30경기 달성 취소')
        if winner.match_count == 49:
            winner.betting_count -= 20
            winner.achieve_count -= 10
            add_point_log(winner.id, betting_change=-20, reason='누적 50경기 달성 취소')
            add_point_log(winner.id, achieve_change=-10, reason='누적 50경기 달성 취소')
        if winner.match_count == 69:
            winner.betting_count -= 40
            winner.achieve_count -= 20
            add_point_log(winner.id, betting_change=-40, reason='누적 70경기 달성 취소')
            add_point_log(winner.id, achieve_change=-20, reason='누적 70경기 달성 취소')
        if winner.match_count == 99:
            winner.betting_count -= 60
            winner.achieve_count -= 30
            add_point_log(winner.id, betting_change=-60, reason='누적 100경기 달성 취소')
            add_point_log(winner.id, achieve_change=-30, reason='누적 100경기 달성 취소')
        if winner.win_count == 19:
            winner.betting_count -= 20
            winner.achieve_count -= 10
            add_point_log(winner.id, betting_change=-20, reason='누적 20승 달성 취소')
            add_point_log(winner.id, achieve_change=-10, reason='누적 20승 달성 취소')
        if winner.win_count == 34:
            winner.betting_count -= 40
            winner.achieve_count -= 20
            add_point_log(winner.id, betting_change=-40, reason='누적 35승 달성 취소')
            add_point_log(winner.id, achieve_change=-20, reason='누적 35승 달성 취소')
        if winner.win_count == 49:
            winner.betting_count -= 60
            winner.achieve_count -= 30
            add_point_log(winner.id, betting_change=-60, reason='누적 50승 달성 취소')
            add_point_log(winner.id, achieve_change=-30, reason='누적 50승 달성 취소')
        if winner_previous_opponent == 10 and winner.opponent_count == 9:
            winner.betting_count -= 10
            winner.achieve_count -= 5
            add_point_log(winner.id, betting_change=-10, reason='누적 상대 10명 달성 취소')
            add_point_log(winner.id, achieve_change=-5, reason='누적 상대 10명 달성 취소')
        if winner_previous_opponent == 25 and winner.opponent_count == 24:
            winner.betting_count -= 40
            winner.achieve_count -= 20
            add_point_log(winner.id, betting_change=-40, reason='누적 상대 25명 달성 취소')
            add_point_log(winner.id, achieve_change=-20, reason='누적 상대 25명 달성 취소')
        if winner_previous_opponent == 40 and winner.opponent_count == 39:
            winner.betting_count -= 60
            winner.achieve_count -= 30
            add_point_log(winner.id, betting_change=-60, reason='누적 상대 40명 달성 취소')
            add_point_log(winner.id, achieve_change=-30, reason='누적 상대 40명 달성 취소')
        if loser.match_count == 29:
            loser.betting_count -= 10
            loser.achieve_count -= 5
            add_point_log(loser.id, betting_change=-10, reason='누적 30경기 달성 취소')
            add_point_log(loser.id, achieve_change=-5, reason='누적 30경기 달성 취소')
        if loser.match_count == 49:
            loser.betting_count -= 20
            loser.achieve_count -= 10
            add_point_log(loser.id, betting_change=-10, reason='누적 50경기 달성 취소')
            add_point_log(loser.id, achieve_change=-5, reason='누적 50경기 달성 취소')
        if loser.match_count == 69:
            loser.betting_count -= 40
            loser.achieve_count -= 20
            add_point_log(loser.id, betting_change=-40, reason='누적 70경기 달성 취소')
            add_point_log(loser.id, achieve_change=-20, reason='누적 70경기 달성 취소')
        if loser.match_count == 99:
            loser.betting_count -= 60
            loser.achieve_count -= 30
            add_point_log(loser.id, betting_change=-60, reason='누적 100경기 달성 취소')
            add_point_log(loser.id, achieve_change=-30, reason='누적 100경기 달성 취소')
        if loser.loss_count == 19:
            loser.betting_count -= 10
            loser.achieve_count -= 10
            add_point_log(loser.id, betting_change=-10, reason='누적 20패 달성 취소')
            add_point_log(loser.id, achieve_change=-10, reason='누적 20패 달성 취소')
        if loser.loss_count == 34:
            loser.betting_count -= 20
            loser.achieve_count -= 20
            add_point_log(loser.id, betting_change=-20, reason='누적 35패 달성 취소')
            add_point_log(loser.id, achieve_change=-20, reason='누적 35패 달성 취소')
        if loser.loss_count == 49:
            loser.betting_count -= 30
            loser.achieve_count -= 30
            add_point_log(loser.id, betting_change=-30, reason='누적 50패 달성 취소')
            add_point_log(loser.id, achieve_change=-30, reason='누적 50패 달성 취소')
        if loser_previous_opponent == 10 and loser.opponent_count == 9:
            loser.betting_count -= 10
            loser.achieve_count -= 5
            add_point_log(loser.id, betting_change=-10, reason='누적 상대수 10명 달성 취소')
            add_point_log(loser.id, achieve_change=-5, reason='누적 상대수 10명 달성 취소')
        if loser_previous_opponent == 25 and loser.opponent_count == 24:
            loser.betting_count -= 40
            loser.achieve_count -= 20
            add_point_log(loser.id, betting_change=-40, reason='누적 상대수 25명 달성 취소')
            add_point_log(loser.id, achieve_change=-20, reason='누적 상대수 25명 달성 취소')
        if loser_previous_opponent == 40 and loser.opponent_count == 39:
            loser.betting_count -= 60
            loser.achieve_count -= 30
            add_point_log(loser.id, betting_change=-60, reason='누적 상대수 40명 달성 취소')
            add_point_log(loser.id, achieve_change=-30, reason='누적 상대수 40명 달성 취소')

        today_partner = TodayPartner.query.filter_by(p1_id=match.winner, p2_id=match.loser, submitted=True).first()
        if not today_partner:
            today_partner = TodayPartner.query.filter_by(p1_id=match.loser, p2_id=match.winner, submitted=True).first()

        if today_partner:
            winner.betting_count -= 5
            loser.betting_count -= 5
            add_point_log(winner.id, betting_change=-5, reason='오늘의 상대 제출 취소')
            add_point_log(loser.id, betting_change=-5, reason='오늘의 상대 제출 취소')

        if match.timestamp.weekday() == 6:
            winner.achieve_count -= 1; winner.betting_count -= 3
            loser.achieve_count -= 1; loser.betting_count -= 3
            add_point_log(winner.id, betting_change=-3, reason='안 쉬세요?? 취소')
            add_point_log(winner.id, achieve_change=-1, reason='안 쉬세요?? 취소')
            add_point_log(loser.id, achieve_change=-1, reason='안 쉬세요?? 취소')
            add_point_log(loser.id, betting_change=-3, reason='안 쉬세요?? 취소')

        if winner.is_she_or_he_freshman == FreshmanEnum.YES and winner.match_count == 15:
            if winner.gender == GenderEnum.MALE or winner.gender == GenderEnum.FEMALE:
                winner.rank = 8
        if loser.is_she_or_he_freshman == FreshmanEnum.YES and loser.match_count == 15:
            if loser.gender == GenderEnum.MALE or loser.gender == GenderEnum.FEMALE:
                loser.rank = 8
    else:
        today_partner = TodayPartner.query.filter(
            (
                (TodayPartner.p1_id == match.winner) & (TodayPartner.p2_id == match.loser)
            ) | (
                (TodayPartner.p1_id == match.loser) & (TodayPartner.p2_id == match.winner)
            ),
            TodayPartner.submitted == True
        ).order_by(TodayPartner.id.desc()).first()

        if today_partner:
            today_partner.submitted = False

    db.session.delete(match)
    return 'approved' if was_approved else 'pending'


@match_bp.route('/approve_matches', methods=['POST'])
def approve_matches():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'error': '승인할 경기가 선택되지 않았습니다.'}), 400

    matches = Match.query.filter(Match.id.in_(ids), Match.approved == False).all()

    for match in matches:
        _approve_single_match(match)

    db.session.commit()
    update_player_orders_by_match()
    update_player_orders_by_point()
    return jsonify({'success': True, 'message': f'{len(matches)}개의 경기가 승인되었습니다.'})


@match_bp.route('/approve_selected_matches', methods=['POST'])
@login_required
def approve_selected_matches():
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('admin.approval'))

    ids = request.form.getlist('match_ids')
    if not ids:
        flash(_('승인할 경기를 선택해주세요.'), 'warning')
        return redirect(url_for('admin.approval'))

    matches = Match.query.filter(Match.id.in_(ids), Match.approved == False).all()
    for match in matches:
        _approve_single_match(match)

    db.session.commit()
    update_player_orders_by_match()
    update_player_orders_by_point()

    flash(f'{len(matches)}개의 경기가 승인되었습니다.', 'success')
    return redirect(url_for('admin.approval'))


@match_bp.route('/approve_match/<int:match_id>', methods=['POST'])
@login_required
def approve_match(match_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('admin.approval'))

    match = Match.query.filter_by(id=match_id, approved=False).first()
    if match:
         _approve_single_match(match)
         db.session.commit()
         flash('경기가 승인되었습니다.', 'success')
    else:
         flash('해당 경기를 찾을 수 없거나 이미 승인되었습니다.', 'error')

    update_player_orders_by_match()
    update_player_orders_by_point()
    return redirect(url_for('admin.approval'))


@match_bp.route('/delete_matches', methods=['POST'])
def delete_matches():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'error': '삭제할 경기가 선택되지 않았습니다.'}), 400

    matches_to_delete = Match.query.filter(Match.id.in_(ids)).all()

    approved_matches_count = 0
    pending_matches_count = 0

    for match in matches_to_delete:
        result = _delete_single_match(match)
        if result == 'approved':
            approved_matches_count += 1
        elif result == 'pending':
            pending_matches_count += 1

    db.session.commit()

    update_player_orders_by_match()
    update_player_orders_by_point()

    return jsonify({'success': True, 'message': f'{approved_matches_count}개의 승인된 경기와 {pending_matches_count}개의 미승인된 경기가 삭제되었습니다.'})


@match_bp.route('/delete_match/<int:match_id>', methods=['POST'])
@login_required
def delete_match_by_admin(match_id):
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('admin.approval'))

    match = Match.query.get(match_id)
    if match:
         _delete_single_match(match)
         db.session.commit()
         update_player_orders_by_match()
         update_player_orders_by_point()
         flash('경기가 삭제되었습니다.', 'success')
    else:
         flash('해당 경기를 찾을 수 없습니다.', 'error')

    return redirect(url_for('admin.approval'))


@match_bp.route('/select_all_matches', methods=['GET'])
def select_all_matches():
    matches = Match.query.filter_by(approved=False).all()
    result = [match.id for match in matches]
    return jsonify({'ids': result})


@match_bp.route('/log/<int:log_id>', methods=['GET'])
def get_log_detail(log_id):
    log = UpdateLog.query.get(log_id)
    if not log:
        return jsonify({'error': '로그를 찾을 수 없습니다.'}), 404

    return jsonify({'success': True, 'title': log.title, 'html_content': log.html_content})


@match_bp.route('/revert_log', methods=['POST'])
def revert_log():
    try:
        players = Player.query.filter(Player.match_count >= 5).order_by(
            Player.rate_count.desc(), Player.match_count.desc()
        ).all()

        total_players = len(players)

        log = UpdateLog.query.order_by(UpdateLog.timestamp.desc()).first()

        if not log:
            return jsonify({'success': False, 'error': '로그를 찾을 수 없습니다.'})

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(log.html_content, 'html.parser')
        tables = soup.find_all('table')
        if len(tables) > 1:
            target_table = tables[1]
        else:
            target_table = tables[0]
        rows = target_table.find('tbody').find_all('tr')

        rank_map = {}
        for row in rows:
            columns = row.find_all('td')
            name = columns[0].text.strip()
            previous_rank = columns[1].text.strip()
            current_rank = columns[2].text.strip()
            change = columns[4].text.strip()

            if change == "New":
                change = None
            elif change == "Up":
                change = "Down"
            elif change == "Down":
                change = "Up"
            elif change == "":
                change = "New"

            rank_map[name] = {
                'previous_rank': None if current_rank == '무' else int(current_rank),
                'rank': None if previous_rank == '무' else int(previous_rank),
                'rank_change': change
            }

        for player in Player.query.filter(Player.name.in_(rank_map.keys())).all():
            player.previous_rank = rank_map[player.name]['previous_rank']
            player.rank = rank_map[player.name]['rank']
            player.rank_change = rank_map[player.name]['rank_change']

        db.session.commit()

        table_rows = [
            f"""
            <tr>
                <td class="border border-gray-300 p-2">{player.name}</td>
                <td class="border border-gray-300 p-2">{player.previous_rank or '무'}</td>
                <td class="border border-gray-300 p-2">{player.rank or '무'}</td>
                <td class="border border-gray-300 p-2">{player.rate_count}%</td>
                <td class="border border-gray-300 p-2">{player.rank_change or ''}</td>
            </tr>
            """
            for player in Player.query.order_by(Player.rate_count.desc()).filter(Player.name.in_(rank_map.keys())).all()
        ]

        html_content = f"""
        <div class="bg-gray-100">
            <table class="w-full bg-white border-collapse border border-gray-300 text-center">
                <thead class="bg-gray-100">
                    <tr>
                        <th class="border border-gray-300 p-2">{total_players}명</th>
                        <th class="border border-gray-300 p-2">전</th>
                        <th class="border border-gray-300 p-2">후</th>
                        <th class="border border-gray-300 p-2">승률</th>
                        <th class="border border-gray-300 p-2">변동</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>
        """

        current_time = datetime.now(ZoneInfo("Asia/Seoul"))

        new_log = UpdateLog(title=f"복원 - {current_time.date()}", html_content=html_content, timestamp=current_time)
        db.session.add(new_log)

        for player in Player.query.filter(Player.name.in_(rank_map.keys())).all():
            player.previous_rank = None
            player.rank_change = None

        db.session.commit()

        return jsonify({'success': True, 'message': '이전 상태로 복원되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@match_bp.route('/delete_logs', methods=['POST'])
def delete_logs():
    ids = request.json.get('ids', [])
    UpdateLog.query.filter(UpdateLog.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'message': '선택한 로그가 삭제되었습니다.'})
