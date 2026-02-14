from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from flask_babel import _, ngettext
from sqlalchemy import case, func
from ..extensions import db
from ..models import Match, Player, User, UpdateLog, Betting, BettingParticipant, TodayPartner, PlayerPointLog
from ..utils import add_point_log, update_player_orders_by_match, update_player_orders_by_point
from ..models import GenderEnum, FreshmanEnum
from datetime import datetime
from zoneinfo import ZoneInfo

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/approval')
@login_required
def approval():
    if not current_user.is_admin:
        flash(_('관리자만 접근할 수 있는 페이지입니다.'), 'error')
        return redirect(url_for('main.index'))
    return render_template('approval.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@admin_bp.route('/assignment')
@login_required
def assignment():
    if not current_user.is_admin:
        flash(_('관리자만 접근할 수 있는 페이지입니다.'), 'error')
        return redirect(url_for('main.index'))
    return render_template('assignment.html', global_texts=current_app.config['GLOBAL_TEXTS'])


@admin_bp.route('/settings')
@login_required
def settings():
    if not current_user.is_admin:
        flash(_('관리자만 접근할 수 있는 페이지입니다.'), 'error')
        return redirect(url_for('main.index'))
    players = Player.query.filter_by(is_valid=True).order_by(Player.name).all()
    return render_template('settings.html', players=players, global_texts=current_app.config['GLOBAL_TEXTS'])


# assignment.js API

@admin_bp.route('/get_assignment_players', methods=['GET'])
@login_required
def get_assignment_players():
    search_query = request.args.get('search', '').strip()
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    query = Player.query.filter(Player.is_valid == True).order_by(Player.name.asc())
    if search_query:
        query = query.filter(Player.name.ilike(f"%{search_query}%"))
    if not show_all and not search_query:
        query = query.limit(10)
    players = query.all()
    response_data = []
    for player in players:
        response_data.append({
            'id': player.id, 'name': player.name, 'rank': player.rank,
            'gender': player.gender.value if player.gender else None,
            'is_freshman': player.is_she_or_he_freshman.value if player.is_she_or_he_freshman else None,
            'match_count': player.match_count,
            'achieve_count': player.achieve_count, 'betting_count': player.betting_count
        })
    return jsonify(response_data)


@admin_bp.route('/update_player_points', methods=['POST'])
@login_required
def update_player_points():
    data = request.get_json()
    player_id = data.get('player_id')
    point_type = data.get('point_type')
    value = data.get('value')
    player = Player.query.get(player_id)
    if not player:
        return jsonify({'success': False, 'error': '선수를 찾을 수 없습니다.'}), 404
    try:
        point_value = int(value)
        reason = "수동 조정"
        if point_type == 'achieve':
            change = point_value - player.achieve_count
            player.achieve_count = point_value
            add_point_log(player_id, achieve_change=change, reason=reason)
        elif point_type == 'betting':
            change = point_value - player.betting_count
            player.betting_count = point_value
            add_point_log(player_id, betting_change=change, reason=reason)
        else:
            return jsonify({'success': False, 'error': '잘못된 포인트 타입입니다.'}), 400
        db.session.commit()
        return jsonify({'success': True, 'message': '포인트가 업데이트되었습니다.'})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '유효한 숫자 값을 입력해주세요.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/update_player_rank', methods=['POST'])
@login_required
def update_player_rank():
    data = request.get_json()
    player_id = data.get('player_id')
    new_rank_str = data.get('rank')
    if player_id is None:
        return jsonify({'success': False, 'error': '선수 ID가 없습니다.'}), 400
    player = Player.query.get(player_id)
    if not player:
        return jsonify({'success': False, 'error': '선수를 찾을 수 없습니다.'}), 404
    try:
        player.rank = int(new_rank_str) if new_rank_str else None
        db.session.commit()
        return jsonify({'success': True, 'message': '부수가 성공적으로 업데이트되었습니다.'})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '유효한 부수(숫자)를 입력해주세요.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/save_all_assignment_changes', methods=['POST'])
@login_required
def save_all_assignment_changes():
    changes = request.get_json()
    if not changes:
        return jsonify({'success': True, 'message': '변경사항이 없습니다.'})
    try:
        for change in changes:
            player_id = change.get('id')
            player = Player.query.get(player_id)
            if not player: continue
            if 'rank' in change:
                player.rank = int(change['rank']) if change['rank'] else None
            if 'achieve_count' in change:
                new_achieve = int(change['achieve_count'])
                diff = new_achieve - player.achieve_count
                if diff != 0:
                    player.achieve_count = new_achieve
                    add_point_log(player_id, achieve_change=diff, reason="관리자 수동 조정")
            if 'betting_count' in change:
                new_betting = int(change['betting_count'])
                diff = new_betting - player.betting_count
                if diff != 0:
                    player.betting_count = new_betting
                    add_point_log(player_id, betting_change=diff, reason="관리자 수동 조정")
        db.session.commit()
        update_player_orders_by_point()
        return jsonify({'success': True, 'message': '모든 변경사항이 저장되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# assignment.js - rank update

@admin_bp.route('/update_ranks', methods=['POST'])
@login_required
def update_ranks():
    if not current_user.is_admin:
        return jsonify({'error': '권한이 없습니다.'}), 403

    try:
        players = Player.query.filter(Player.match_count >= 5).order_by(
            Player.rate_count.desc(), Player.match_count.desc()
        ).all()

        total_players = len(players)

        for player in players:
            player.previous_rank = player.rank

        rank_boundaries = {
            1: int(total_players * 0.03),
            2: int(total_players * 0.13),
            3: int(total_players * 0.30),
            4: int(total_players * 0.55),
            5: int(total_players * 0.75),
            6: int(total_players * 0.90),
        }

        for i, player in enumerate(players):
            if player.is_she_or_he_freshman == FreshmanEnum.YES and player.match_count < 16:
                continue
            position = i + 1
            if position <= rank_boundaries.get(1, 0): new_rank = 1
            elif position <= rank_boundaries.get(2, 0): new_rank = 2
            elif position <= rank_boundaries.get(3, 0): new_rank = 3
            elif position <= rank_boundaries.get(4, 0): new_rank = 4
            elif position <= rank_boundaries.get(5, 0): new_rank = 5
            elif position <= rank_boundaries.get(6, 0): new_rank = 6
            else: new_rank = 7
            player.rank = new_rank

        for player in players:
            if player.previous_rank is None or player.previous_rank == 0:
                player.rank_change = "New"
            elif player.rank < player.previous_rank:
                player.rank_change = "Up"
            elif player.rank > player.previous_rank:
                player.rank_change = "Down"
            else:
                player.rank_change = None

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
            for player in players
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
        new_log = UpdateLog(title=f"부수 업데이트 - {current_time.date()}", html_content=html_content, timestamp=current_time)
        db.session.add(new_log)

        for player in players:
            player.previous_rank = None
            player.rank_change = None

        db.session.commit()
        return jsonify({'success': True, 'message': f'{total_players}명의 부수가 업데이트되었습니다.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# settings.js API

@admin_bp.route('/reset_partner', methods=['POST'])
def reset_partner():
    try:
        TodayPartner.query.delete()
        db.session.commit()
        return "오늘의 상대 초기화 완료", 200
    except Exception as e:
        print(e)
        return "초기화 실패", 500


@admin_bp.route('/register_partner', methods=['POST'])
def register_partner():
    data = request.json
    old_players = data.get('old_players', [])
    new_players = data.get('new_players', [])
    if not old_players or not new_players:
        return jsonify({"error": "부원 이름이 필요합니다."}), 400
    pairs = []
    old_count = len(old_players)
    for i, new_player in enumerate(new_players):
        old_player = old_players[i % old_count]
        pairs.append({"p1_name": old_player, "p2_name": new_player})
    db.session.commit()
    return jsonify(pairs), 200


@admin_bp.route('/submit_partner', methods=['POST'])
def submit_partner():
    data = request.json
    pairs = data.get('pairs', [])
    try:
        for pair in pairs:
            p1 = Player.query.filter_by(name=pair['p1_name']).first()
            p2 = Player.query.filter_by(name=pair['p2_name']).first()
            if not p1 or not p2:
                return jsonify({"error": f"{pair['p1_name'] if not p1 else pair['p2_name']}의 정보를 찾을 수 없습니다."}), 400
            db.session.add(TodayPartner(p1_id=p1.id, p1_name=p1.name, p2_id=p2.id, p2_name=p2.name))
        db.session.commit()
        return "오늘의 상대 저장 완료", 200
    except Exception as e:
        print(e)
        return jsonify({"error": "저장 중 문제가 발생했습니다."}), 500


@admin_bp.route('/register_players', methods=['POST'])
def register_players():
    data = request.get_json()
    players_data = data.get('players', [])
    added_count = 0
    for player_info in players_data:
        name = player_info.get('name')
        gender_str = player_info.get('gender')
        freshman_str = player_info.get('freshman')
        if not name or not gender_str or not freshman_str: continue
        if not Player.query.filter_by(name=name).first():
            gender_enum = GenderEnum(gender_str)
            freshman_enum = FreshmanEnum(freshman_str)
            initial_rank = None
            if gender_enum == GenderEnum.MALE:
                initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 4
            elif gender_enum == GenderEnum.FEMALE:
                initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 6
            db.session.add(Player(name=name, gender=gender_enum, is_she_or_he_freshman=freshman_enum, rank=initial_rank))
            added_count += 1
    db.session.commit()
    return jsonify({'success': True, 'added_count': added_count})


@admin_bp.route('/toggle_validity', methods=['POST'])
def toggle_validity():
    ids = request.json.get('ids', [])
    if not ids: return jsonify({'success': False, 'error': '선택된 항목이 없습니다.'}), 400
    for player in Player.query.filter(Player.id.in_(ids)).all():
        player.is_valid = not player.is_valid
    db.session.commit()
    update_player_orders_by_match()
    update_player_orders_by_point()
    return jsonify({'success': True, 'message': '선수의 유효/무효 상태가 변경되었습니다.'})


@admin_bp.route('/delete_players', methods=['POST'])
def delete_players():
    ids = request.get_json().get('ids', [])
    Player.query.filter(Player.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    update_player_orders_by_match()
    update_player_orders_by_point()
    return jsonify({'success': True, 'message': '선택한 선수가 삭제되었습니다.'})


@admin_bp.route('/get_player_ids', methods=['POST'])
def get_player_ids():
    names = request.get_json().get('names', [])
    if not names: return jsonify({'success': False, 'error': 'No names provided'}), 400
    players = Player.query.filter(Player.name.in_(names)).all()
    if not players: return jsonify({'success': False, 'error': 'No players found'}), 404
    return jsonify({'success': True, 'player_ids': [p.id for p in players]})


@admin_bp.route('/update_achievement', methods=['POST'])
def update_achievement():
    data = request.get_json()
    player_ids = data.get('player_ids', [])
    additional_achieve = data.get('achieve', 0)
    additional_betting = data.get('betting', 0)
    if not player_ids or (additional_achieve == 0 and additional_betting == 0):
        return jsonify({'success': False, 'error': 'Invalid data provided'}), 400
    players = Player.query.filter(Player.id.in_(player_ids)).all()
    if not players: return jsonify({'success': False, 'error': 'No players found'}), 404
    for player in players:
        if additional_achieve != 0:
            player.achieve_count += additional_achieve
            add_point_log(player.id, achieve_change=additional_achieve, reason='수동 입력')
        if additional_betting != 0:
            player.betting_count += additional_betting
            add_point_log(player.id, betting_change=additional_betting, reason='수동 입력')
    db.session.commit()
    update_player_orders_by_point()
    return jsonify({'success': True})


@admin_bp.route('/admin/delete_players', methods=['POST'])
@login_required
def admin_delete_players():
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403
    player_ids_to_delete = request.json.get('player_ids', [])
    if not player_ids_to_delete:
        return jsonify({'success': False, 'error': '삭제할 선수가 선택되지 않았습니다.'}), 400
    try:
        for player_id_str in player_ids_to_delete:
            player_id = int(player_id_str)
            BettingParticipant.query.filter(
                (BettingParticipant.participant_id == player_id) | (BettingParticipant.winner_id == player_id)
            ).delete(synchronize_session=False)
            bettings_to_delete = Betting.query.filter((Betting.p1_id == player_id) | (Betting.p2_id == player_id)).all()
            for b in bettings_to_delete:
                BettingParticipant.query.filter_by(betting_id=b.id).delete(synchronize_session=False)
                db.session.delete(b)
            matches_to_delete = Match.query.filter((Match.winner == player_id) | (Match.loser == player_id)).all()
            if matches_to_delete:
                match_ids = [m.id for m in matches_to_delete]
                Betting.query.filter(Betting.result.in_(match_ids)).update({"result": None}, synchronize_session=False)
                for m in matches_to_delete:
                    db.session.delete(m)
            PlayerPointLog.query.filter_by(player_id=player_id).delete(synchronize_session=False)
            TodayPartner.query.filter((TodayPartner.p1_id == player_id) | (TodayPartner.p2_id == player_id)).delete(synchronize_session=False)
            user = User.query.filter_by(player_id=player_id).first()
            if user: db.session.delete(user)
            player = Player.query.get(player_id)
            if player: db.session.delete(player)
        db.session.commit()
        recalculate_url = url_for('admin.recalculate_all_stats')
        return jsonify({'success': True, 'message': f'{len(player_ids_to_delete)}명의 선수가 삭제되었습니다. 전체 통계를 재계산합니다.', 'redirect_url': recalculate_url})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting players: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'삭제 중 오류 발생: {str(e)}'}), 500


@admin_bp.route('/admin/recalculate-stats')
@login_required
def recalculate_all_stats():
    if not current_user.is_admin:
        flash(_('권한이 없습니다.', 'error'))
        return redirect(url_for('main.index'))
    try:
        all_players = Player.query.filter_by(is_valid=True).all()
        for player in all_players:
            win_count = Match.query.filter_by(winner=player.id, approved=True).count()
            loss_count = Match.query.filter_by(loser=player.id, approved=True).count()
            match_count = win_count + loss_count
            rate_count = round((win_count / match_count) * 100, 2) if match_count > 0 else 0
            player.win_count = win_count
            player.loss_count = loss_count
            player.match_count = match_count
            player.rate_count = rate_count
        db.session.commit()
        update_player_orders_by_match()
        flash('모든 선수의 전적 통계를 성공적으로 재계산했습니다.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'재계산 중 오류가 발생했습니다: {e}', 'error')
    return redirect(url_for('admin.assignment'))


@admin_bp.route('/admin/reset_password', methods=['GET', 'POST'])
@login_required
def admin_reset_password():
    if not current_user.is_admin:
        flash(_('권한이 없습니다.'), 'error')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        player_id = request.form.get('player_id')
        new_password = request.form.get('new_password')
        if not player_id or not new_password:
            flash(_('부원을 선택하고, 새로운 비밀번호를 입력해주세요.'), 'error')
            return redirect(url_for('admin.admin_reset_password'))
        if len(new_password) < 4:
            flash(_('비밀번호는 4자 이상이어야 합니다.'), 'error')
            return redirect(url_for('admin.admin_reset_password'))
        user_to_update = User.query.filter_by(player_id=player_id).first()
        if user_to_update:
            user_to_update.set_password(new_password)
            db.session.commit()
            flash(f"'{user_to_update.username}' 님의 비밀번호가 성공적으로 초기화되었습니다.", 'success')
        else:
            flash('해당하는 사용자 계정을 찾을 수 없습니다.', 'error')
        return redirect(url_for('admin.admin_reset_password'))
    all_players = Player.query.join(User).filter(User.is_admin == False).order_by(Player.name).all()
    return render_template('admin_reset_password.html', players=all_players)
