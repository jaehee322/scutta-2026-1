from flask import render_template, jsonify, current_app, request, flash, redirect, url_for
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import distinct, case, func
from sqlalchemy.orm import session
from .extensions import db
from sqlalchemy.orm.attributes import flag_modified
from .models import Match, Player, UpdateLog, League, Betting, BettingParticipant, TodayPartner, GenderEnum, FreshmanEnum, PlayerPointLog, User, Tournament
from datetime import datetime
from zoneinfo import ZoneInfo
import random

def init_routes(app):

    def add_point_log(player_id, achieve_change=0, betting_change=0, reason=""):
        """플레이어 포인트 변경 로그를 기록하는 헬퍼 함수"""
        if achieve_change == 0 and betting_change == 0:
            return
        
        log = PlayerPointLog(
            player_id=player_id,
            achieve_change=achieve_change,
            betting_change=betting_change,
            reason=reason
        )
        db.session.add(log)
   
    @app.route('/get_assignment_players', methods=['GET'])
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
                'id': player.id,
                'name': player.name,
                'rank': player.rank,
                'gender': player.gender.value if player.gender else None,
                'is_freshman': player.is_she_or_he_freshman.value if player.is_she_or_he_freshman else None,
                'match_count': player.match_count,
                # ▼▼▼ 이 두 줄을 추가해야 합니다 ▼▼▼
                'achieve_count': player.achieve_count,
                'betting_count': player.betting_count
            })
        return jsonify(response_data)

    @app.route('/update_player_points', methods=['POST'])
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
        
    @app.route('/update_player_rank', methods=['POST'])
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
            # new_rank가 빈 문자열일 경우 None으로 처리
            player.rank = int(new_rank_str) if new_rank_str else None
            db.session.commit()
            return jsonify({'success': True, 'message': '부수가 성공적으로 업데이트되었습니다.'})
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': '유효한 부수(숫자)를 입력해주세요.'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        
    @app.route('/save_all_assignment_changes', methods=['POST'])
    @login_required
    def save_all_assignment_changes():
        changes = request.get_json()
        if not changes:
            return jsonify({'success': True, 'message': '변경사항이 없습니다.'})

        try:
            for change in changes:
                player_id = change.get('id')
                player = Player.query.get(player_id)
                if not player:
                    continue

                # 부수 변경 처리
                if 'rank' in change:
                    player.rank = int(change['rank']) if change['rank'] else None

                # 업적 포인트 변경 처리 및 로그 기록
                if 'achieve_count' in change:
                    new_achieve = int(change['achieve_count'])
                    diff = new_achieve - player.achieve_count
                    if diff != 0:
                        player.achieve_count = new_achieve
                        add_point_log(player_id, achieve_change=diff, reason="관리자 수동 조정")
                
                # 베팅 포인트 변경 처리 및 로그 기록
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
        
    @app.route('/log/<int:log_id>', methods=['GET']) # JS와 일치하도록 경로 수정
    def get_log_detail(log_id):
        log = UpdateLog.query.get(log_id)
        if not log:
            return jsonify({'error': '로그를 찾을 수 없습니다.'}), 404

        return jsonify({'success': True, 'title': log.title, 'html_content': log.html_content})
    
    @app.route('/admin/recalculate-stats')
    @login_required
    def recalculate_all_stats():
        if not current_user.is_admin:
            flash('권한이 없습니다.', 'error')
            return redirect(url_for('index'))

        try:
            # 모든 유효한 선수들을 불러옵니다.
            all_players = Player.query.filter_by(is_valid=True).all()

            for player in all_players:
                # 1. 승리, 패배 횟수를 Match 테이블에서 직접 다시 계산합니다.
                win_count = Match.query.filter_by(winner=player.id, approved=True).count()
                loss_count = Match.query.filter_by(loser=player.id, approved=True).count()
                
                # 2. 새로운 통계를 계산합니다.
                match_count = win_count + loss_count
                rate_count = round((win_count / match_count) * 100, 2) if match_count > 0 else 0
                
                # 3. Player 객체에 새로운 통계를 업데이트합니다.
                player.win_count = win_count
                player.loss_count = loss_count
                player.match_count = match_count
                player.rate_count = rate_count

            # 4. 모든 변경사항을 데이터베이스에 한 번에 저장합니다.
            db.session.commit()
            
            # 5. 순위 정보를 다시 계산하는 함수를 호출합니다.
            update_player_orders_by_match()

            flash('모든 선수의 전적 통계를 성공적으로 재계산했습니다.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'재계산 중 오류가 발생했습니다: {e}', 'error')
            
        return redirect(url_for('assignment')) # 완료 후 부수/포인트 페이지로 이동
    
    @app.route('/admin/delete_players', methods=['POST'])
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
                
                # 1. BettingParticipant 테이블 정리
                #    - 이 선수가 '참가자'이거나 '승리예측'된 모든 기록을 삭제합니다.
                BettingParticipant.query.filter(
                    (BettingParticipant.participant_id == player_id) |
                    (BettingParticipant.winner_id == player_id)
                ).delete(synchronize_session=False)

                # 2. Betting 테이블 정리
                #    - 이 선수가 p1 또는 p2로 참여한 모든 베팅을 찾습니다.
                bettings_to_delete = Betting.query.filter((Betting.p1_id == player_id) | (Betting.p2_id == player_id)).all()
                for b in bettings_to_delete:
                    #    - 해당 베팅에 속한 모든 참여자 기록을 먼저 삭제합니다.
                    BettingParticipant.query.filter_by(betting_id=b.id).delete(synchronize_session=False)
                    #    - 그 다음 베팅 자체를 삭제합니다.
                    db.session.delete(b)
                
                # 3. Match 테이블 정리
                #    - 이 선수가 승자 또는 패자인 모든 경기를 찾습니다.
                matches_to_delete = Match.query.filter((Match.winner == player_id) | (Match.loser == player_id)).all()
                if matches_to_delete:
                    match_ids = [m.id for m in matches_to_delete]
                    #    - 다른 베팅 기록이 이 경기들을 '결과'로 참고하고 있을 수 있으므로, 그 연결을 먼저 끊습니다. (NULL로 설정)
                    Betting.query.filter(Betting.result.in_(match_ids)).update({"result": None}, synchronize_session=False)
                    #    - 이제 경기를 안전하게 삭제합니다.
                    for m in matches_to_delete:
                        db.session.delete(m)

                # 4. 기타 테이블 정리 (PlayerPointLog, TodayPartner)
                PlayerPointLog.query.filter_by(player_id=player_id).delete(synchronize_session=False)
                TodayPartner.query.filter((TodayPartner.p1_id == player_id) | (TodayPartner.p2_id == player_id)).delete(synchronize_session=False)

                # 5. User -> Player 순서로 최종 삭제
                user = User.query.filter_by(player_id=player_id).first()
                if user:
                    db.session.delete(user)
                
                player = Player.query.get(player_id)
                if player:
                    db.session.delete(player)

            # 모든 플레이어에 대한 작업이 끝난 후, 변경사항을 DB에 최종 반영
            db.session.commit()

            recalculate_url = url_for('recalculate_all_stats')

            return jsonify({
                'success': True, 
                'message': f'{len(player_ids_to_delete)}명의 선수가 삭제되었습니다. 전체 통계를 재계산합니다.',
                'redirect_url': recalculate_url
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting players: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'삭제 중 오류 발생: {str(e)}'}), 500
            
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index')) 
            
        if request.method == 'POST':
            username=request.form.get('username')
            password=request.form.get('password')
            remember_me = True if request.form.get('remember') else False  #자동 로그인
            user=User.query.filter_by(username=username).first()

            if user is None or not user.check_password(password):
                flash('아이디 또는 비밀번호가 올바르지 않습니다.')
                return redirect(url_for('login'))
                
            login_user(user, remember=remember_me)
            return redirect(url_for('index'))
            
        return render_template('login.html', global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))
    
    # app/routes.py의 init_routes(app) 함수 내부에 추가

    @app.route('/admin/batch_add_users', methods=['POST'])
    @login_required
    def batch_add_users():
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        users_data = request.json.get('users', [])
        if not users_data:
            return jsonify({'success': False, 'message': '등록할 사용자 정보가 없습니다.'}), 400

        added_count = 0
        errors = []

        for user_data in users_data:
            name = user_data.get('name')
            
            # 이미 존재하는 사용자인지 확인
            if User.query.filter_by(username=name).first() or Player.query.filter_by(name=name).first():
                errors.append(f"'{name}'는 이미 존재하는 이름입니다.")
                continue

            try:
                # Player 및 User 객체 생성 (기존 add_user 로직과 동일)
                gender_enum = GenderEnum(user_data.get('gender'))
                freshman_enum = FreshmanEnum(user_data.get('freshman'))
                
                initial_rank = None
                if gender_enum == GenderEnum.MALE:
                    initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 5
                elif gender_enum == GenderEnum.FEMALE:
                    initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 7
                
                new_player = Player(
                    name=name,
                    gender=gender_enum,
                    is_she_or_he_freshman=freshman_enum,
                    rank=initial_rank
                )
                
                new_user = User(
                    username=name,
                    is_admin=user_data.get('is_admin', False)
                )
                new_user.set_password(user_data.get('password'))
                new_user.player = new_player
                
                db.session.add(new_player)
                db.session.add(new_user)
                added_count += 1
            except Exception as e:
                errors.append(f"'{name}' 등록 중 오류 발생: {e}")

        if errors:
            db.session.rollback()
            return jsonify({'success': False, 'message': '\n'.join(errors)}), 400
        else:
            db.session.commit()
            return jsonify({'success': True, 'message': f'총 {added_count}명의 회원이 성공적으로 등록되었습니다.'})
    
    @app.route('/health', methods=['GET'])
    def health_check():
        response = current_app.response_class(
            response="OK",
            status=200,
            mimetype='text/plain'
        )
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        return response

    @app.route('/')
    @login_required
    def index():
        all_players= Player.query.join(User).filter(Player.is_valid ==True, User.is_admin == False).order_by(Player.name).all()
        categories = [
            ('승리', Player.win_count.desc(), 'win_count'),
            ('승률', Player.rate_count.desc(), 'rate_count'),
            ('경기', Player.match_count.desc(), 'match_count'),
            ('베팅', Player.betting_count.desc(), 'betting_count'),
        ]
        rankings_data = {}
        for title, order_criteria, value_attr in categories:
            top_players = Player.query.join(Player.user).filter(
                Player.is_valid == True,
                User.is_admin == False
            ).order_by(order_criteria, Player.name).limit(4).all()
            
            rankings_data[title] = [
                {'name': player.name, 'rank': player.rank, 'value': getattr(player, value_attr)}
                for player in top_players
            ]
        return render_template('index.html', global_texts=current_app.config['GLOBAL_TEXTS'], rankings=rankings_data)

    @app.route('/submitment.html')
    @login_required
    def submitment():
        return render_template('submitment.html', global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/submit_match_direct', methods=['POST'])
    @login_required
    def submit_match_direct():
        # ID가 아닌 이름(name)을 직접 받도록 수정합니다.
        winner_name = request.form.get('winner_name')
        loser_name = request.form.get('loser_name')
        score = request.form.get('score')

        if not winner_name or not loser_name or not score:
            flash('모든 필드를 올바르게 입력해주세요.', 'error')
            return redirect(url_for('index'))

        if winner_name == loser_name:
            flash('승리자와 패배자는 다른 사람이어야 합니다.', 'error')
            return redirect(url_for('index'))

        # 이름으로 선수 정보가 유효한지 확인합니다.
        winner = Player.query.filter_by(name=winner_name, is_valid=True).first()
        loser = Player.query.filter_by(name=loser_name, is_valid=True).first()

        if not winner or not loser:
            unknown = []
            if not winner: unknown.append(winner_name)
            if not loser: unknown.append(loser_name)
            flash(f'등록되지 않은 선수 이름이 있습니다: {", ".join(unknown)}', 'error')
            return redirect(url_for('index'))

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
        db.session.commit()

        flash('경기 결과가 성공적으로 제출되었습니다. 관리자 승인 대기 중입니다.', 'success')
        return redirect(url_for('index'))

    @app.route('/submit_match')
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
            {'id' : player.id, 'name' : player.name}
            for player in all_players_objects
        ]

        return render_template('submit_match.html', matches=my_matches, all_players=all_players_data)
   
    @app.route('/my_submissions')
    @login_required
    def my_submissions():
        # 현재 로그인한 사용자가 제출한 최근 10경기를 찾습니다.
        my_matches = Match.query.filter(
            (Match.winner == current_user.player_id) | (Match.loser == current_user.player_id)
        ).order_by(Match.timestamp.desc()).limit(5).all()

        return render_template('my_submissions.html', matches=my_matches)
   
    @app.route('/partner.html')
    @login_required
    def partner():
        partners = TodayPartner.query.order_by(TodayPartner.id).all()
        
        p1_ranks = []
        p2_ranks = []
        for partner in partners:
            p1 = Player.query.filter_by(id=partner.p1_id).first()
            p1_ranks.append(p1.rank)
            p2 = Player.query.filter_by(id=partner.p2_id).first()
            p2_ranks.append(p2.rank)
        
        indexed_partners = [{'index': idx, 'partner': partner, 'p1_rank': p1_rank, 'p2_rank': p2_rank} for idx, (partner, p1_rank, p2_rank) in enumerate(zip(partners, p1_ranks, p2_ranks))]
        return render_template('partner.html', partners=indexed_partners, global_texts=current_app.config['GLOBAL_TEXTS'])
   
    @app.route('/rankings_page')
    @login_required
    def rankings_page():
        return render_template('rankings.html')

    @app.route('/mypage')
    @login_required
    def mypage():
       
        player_info = current_user.player
        if not player_info:
            flash('선수 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('index'))
        
        recent_matches = Match.query.filter(
            (Match.winner == player_info.id) | (Match.loser == player_info.id)
        ).order_by(Match.timestamp.desc()).limit(10).all()
        
        return render_template('mypage.html', player=player_info, matches=recent_matches)

    @app.route('/point_history')
    @login_required
    def point_history():
        logs = PlayerPointLog.query.filter_by(player_id=current_user.player_id)\
                                   .order_by(PlayerPointLog.timestamp.desc())\
                                   .all()
        
        return render_template('point_history.html', logs=logs)
    
    @app.route('/change_password_page')
    @login_required
    def change_password_page():
        return render_template('change_password.html')

    @app.route('/change_password', methods=['POST'])
    @login_required
    def change_password():
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        user_to_update = User.query.get(current_user.id)
        if not user_to_update:
            flash('사용자 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('change_password_page'))
        
        if not user_to_update.check_password(current_password):
            flash('현재 비밀번호가 일치하지 않습니다.', 'error')
            return redirect(url_for('change_password_page'))

        if new_password != confirm_password:
            flash('새로운 비밀번호가 일치하지 않습니다.', 'error')
            return redirect(url_for('change_password_page'))
        
        if len(new_password) < 4:
            flash('새로운 비밀번호는 4자 이상이어야 합니다.', 'error')
            return redirect(url_for('change_password_page'))
        
        user_to_update.set_password(new_password)
        db.session.commit()

        flash('비밀번호가 성공적으로 변경되었습니다.', 'success')
        return redirect(url_for('mypage'))
    
    @app.route('/league.html')
    @login_required
    def league():
        leagues = League.query.order_by(League.id.desc()).all()
        
        p1_ranks = []; p2_ranks = []; p3_ranks = []; p4_ranks = []; p5_ranks = []; 
        for league in leagues:
            p1 = Player.query.filter_by(name=league.p1).first(); p1_ranks.append(p1.rank)
            p2 = Player.query.filter_by(name=league.p2).first(); p2_ranks.append(p2.rank)
            p3 = Player.query.filter_by(name=league.p3).first(); p3_ranks.append(p3.rank)
            p4 = Player.query.filter_by(name=league.p4).first(); p4_ranks.append(p4.rank)
            p5 = Player.query.filter_by(name=league.p5).first(); p5_ranks.append(p5.rank)
        
        indexed_leagues = [{'index': idx, 'league': league, 'p1_rank': p1_rank, 'p2_rank': p2_rank, 'p3_rank': p3_rank, 'p4_rank': p4_rank, 'p5_rank': p5_rank} for idx, (league, p1_rank, p2_rank, p3_rank, p4_rank, p5_rank) in enumerate(zip(leagues, p1_ranks, p2_ranks, p3_ranks, p4_ranks, p5_ranks))]
        return render_template('league.html', leagues=indexed_leagues, global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/betting.html')
    def betting():
        bettings = Betting.query.filter(Betting.submitted == False).order_by(Betting.id.desc()).all()
        
        p1_ranks = []
        p2_ranks = []
        for betting in bettings:
            p1 = Player.query.filter_by(id=betting.p1_id).first()
            p1_ranks.append(p1.rank)
            p2 = Player.query.filter_by(id=betting.p2_id).first()
            p2_ranks.append(p2.rank)
        
        indexed_bettings = [{'index': idx, 'betting': betting, 'p1_rank': p1_rank, 'p2_rank': p2_rank} for idx, (betting, p1_rank, p2_rank) in enumerate(zip(bettings, p1_ranks, p2_ranks))]
        return render_template('betting.html', bettings=indexed_bettings, global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/password.html')
    @login_required
    def password():
        return render_template('password.html', global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/betting_approval.html')
    @login_required
    def betting_approval():
        if not current_user.is_admin:
            flash('관리자만 접근할 수 있는 페이지입니다.', 'error')
            return redirect(url_for('index')) # 관리자 아니면 메인 페이지로 쫓아내기

        return render_template('betting_approval.html', global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/approval.html')
    @login_required
    def approval():
        if not current_user.is_admin:
            flash('관리자만 접근할 수 있는 페이지입니다.', 'error')
            return redirect(url_for('index')) # 관리자 아니면 메인 페이지로 쫓아내기
        
        return render_template('approval.html', global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/assignment.html')
    @login_required
    def assignment():
        if not current_user.is_admin:
            flash('관리자만 접근할 수 있는 페이지입니다.', 'error')
            return redirect(url_for('index')) # 관리자 아니면 메인 페이지로 쫓아내기
        
        logs = UpdateLog.query.order_by(UpdateLog.timestamp.desc()).all()
        return render_template('assignment.html', logs=logs, global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/settings.html')
    @login_required
    def settings():
        if not current_user.is_admin:
            flash('관리자만 접근할 수 있는 페이지입니다.', 'error')
            return redirect(url_for('index')) # 관리자 아니면 메인 페이지로 쫓아내기
        
        players = Player.query.order_by(Player.is_valid.desc(), Player.name).all()
        
        return render_template('settings.html', players=players, config=current_app.config,global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/favicon.ico')
    def favicon():
        return current_app.send_static_file('favicon.ico')

    @app.route('/player/<int:player_id>', methods=['GET'])
    @login_required
    def player_detail(player_id):
        if current_user.player_id == player_id:
            return redirect(url_for('mypage'))

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

    @app.route('/league/<int:league_id>', methods=['GET'])
    @login_required
    def league_detail(league_id):
        league = League.query.get_or_404(league_id)
        players = [league.p1, league.p2, league.p3, league.p4, league.p5]
        
        player_ids = []
        player_ranks = []
        for player_name in players:
            player = Player.query.filter_by(name=player_name).first()
            player_id = player.id if player else None
            player_rank = player.rank
            player_ids.append(player_id)
            player_ranks.append(player_rank)

        indexed_players = [{'index': idx, 'player': player_name, 'player_id': player_id, 'player_rank': player_rank} for idx, (player_name, player_id, player_rank) in enumerate(zip(players, player_ids, player_ranks))]
        
        scores = {}

        for row in range(5):
            for col in range(5):
                if row != col:
                    key = f"p{row + 1}p{col + 1}"
                    scores[key] = getattr(league, key, None)

        return render_template('league_detail.html', league=league, players=indexed_players, scores=scores, global_texts=current_app.config['GLOBAL_TEXTS'])

    @app.route('/betting/<int:betting_id>', methods=['GET'])
    def betting_detail(betting_id):
        betting = Betting.query.get_or_404(betting_id)
        
        p1 = Player.query.filter_by(id=betting.p1_id).first()
        p1_rank = p1.rank
        p2 = Player.query.filter_by(id=betting.p2_id).first()
        p2_rank = p2.rank
        
        matches = Match.query.filter(
            ((Match.winner == betting.p1_id) & (Match.loser == betting.p2_id)) |
            ((Match.winner == betting.p2_id) & (Match.loser == betting.p1_id))
        ).order_by(Match.timestamp.desc()).limit(10).all()

        recent_matches = []
        p1_wins, p2_wins = 0, 0
        for match in matches:
            if match.winner == betting.p1_id:
                p1_wins += 1
                score = match.score
            else:
                p2_wins += 1
                original_score = match.score.split(':')
                score = f"{original_score[1]}:{original_score[0]}"
            recent_matches.append({
                'p1_name': match.winner_name if match.winner == betting.p1_id else match.loser_name,
                'score': score,
                'p2_name': match.loser_name if match.winner == betting.p1_id else match.winner_name
            })
        
        betting_participants = BettingParticipant.query.filter(BettingParticipant.betting_id == betting.id).order_by(BettingParticipant.id).all()
        
        participants = [{
            'name': p.participant_name,
            'id': p.participant_id,
            'winner_id': p.winner_id
        } for p in betting_participants]

        return render_template(
            'betting_detail.html', betting=betting, participants=participants, rank = {'p1_rank': p1_rank, 'p2_rank': p2_rank},
            recent_matches=recent_matches, win_rate={'p1_wins': p1_wins, 'p2_wins': p2_wins},
            global_texts=current_app.config['GLOBAL_TEXTS']
        )

    @app.route('/league_or_tournament')
    @login_required
    def league_or_tournament():
        return render_template('league_or_tournament.html')
   
    @app.route('/tournament')
    @login_required
    def tournament():
        tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
        return render_template('tournament.html', tournaments=tournaments)

    # 2. 토너먼트 생성 페이지
    @app.route('/tournament/create')
    @login_required
    def create_tournament_page():
        if not current_user.is_admin:
            flash('권한이 없습니다.', 'error')
            return redirect(url_for('tournament'))
        return render_template('create_tournament.html')

    # 3. 토너먼트 대진표 생성 (결승까지 자동 생성)
    @app.route('/tournament/generate', methods=['POST'])
    @login_required
    def generate_tournament():
        if not current_user.is_admin:
            return redirect(url_for('tournament'))

        title = request.form.get('title')
        player_names_str = request.form.get('players')
        player_names = [name.strip() for name in player_names_str.splitlines() if name.strip()]
        
        # ... (기존 유효성 검사 코드는 동일) ...
        
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
        return redirect(url_for('tournament_detail', tournament_id=new_tournament.id))

    # 4. 토너먼트 상세 페이지 (대진표 보기)
    @app.route('/tournament/<int:tournament_id>')
    @login_required
    def tournament_detail(tournament_id):
        tournament = Tournament.query.get_or_404(tournament_id)
        return render_template('tournament_detail.html', tournament=tournament)

    # 5. 토너먼트 결과 제출 페이지
    @app.route('/tournament/<int:tournament_id>/submit_results')
    @login_required
    def submit_tournament_results_page(tournament_id):
        if not current_user.is_admin:
            flash('권한이 없습니다.', 'error')
            return redirect(url_for('tournament_detail', tournament_id=tournament_id))
        
        tournament = Tournament.query.get_or_404(tournament_id)
        return render_template('submit_tournament_results.html', tournament=tournament)

    # 6. 토너먼트 결과 처리 및 대진표 업데이트
    @app.route('/tournament/<int:tournament_id>/submit_results', methods=['POST'])
    @login_required
    def submit_tournament_results(tournament_id):
        if not current_user.is_admin:
            return redirect(url_for('index'))
        
        tournament = Tournament.query.get_or_404(tournament_id)
        bracket = tournament.bracket_data
        
        submitted_matches = 0
        # 제출된 form 데이터에서 경기 결과를 읽어옵니다.
        for key, winner_name in request.form.items():
            if '_winner' in key and winner_name:
                match_id = key.replace('_winner', '')
                score = request.form.get(f"{match_id}_score", "2:0")
                
                # 대진표 데이터(bracket)에서 해당 경기를 찾아 승자를 업데이트합니다.
                for round_matches in bracket['rounds']:
                    for match in round_matches:
                        if match.get('id') == match_id and not match.get('winner'):
                            p1 = match.get('p1')
                            p2 = match.get('p2')
                            loser_name = p2 if winner_name == p1 else p1
                            
                            winner_player = Player.query.filter_by(name=winner_name).first()
                            loser_player = Player.query.filter_by(name=loser_name).first()
                            
                            if winner_player and loser_player:
                                # Match 테이블에도 경기 기록을 추가합니다. (승인 대기 상태)
                                new_match = Match(
                                    winner=winner_player.id, winner_name=winner_name,
                                    loser=loser_player.id, loser_name=loser_name,
                                    score=score, approved=False
                                )
                                db.session.add(new_match)
                                submitted_matches += 1
                            
                            match['winner'] = winner_name
        
        # 다음 라운드의 'R1M1 승자' 같은 플레이스홀더를 실제 승자 이름으로 교체합니다.
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
        
        # 결승전이 끝나면 토너먼트 상태를 '완료'로 변경합니다.
        final_round = bracket['rounds'][-1]
        if len(final_round) == 1 and final_round[0].get('winner'):
            tournament.status = '완료'

        flag_modified(tournament, "bracket_data")
        
        db.session.commit()

        if submitted_matches > 0:
            flash(f'{submitted_matches}개의 경기 결과가 제출되어 승인 대기 중입니다.', 'success')
        else:
            flash('제출할 새로운 경기 결과가 없습니다.', 'info')
            
        return redirect(url_for('tournament_detail', tournament_id=tournament_id))
    # 7. 토너먼트 삭제
    @app.route('/tournament/delete/<int:tournament_id>', methods=['POST'])
    @login_required
    def delete_tournament(tournament_id):
        if not current_user.is_admin:
            return jsonify({'success': False, 'error': '권한이 없습니다.'}), 403

        tournament = Tournament.query.get_or_404(tournament_id)
        db.session.delete(tournament)
        db.session.commit()
        return jsonify({'success': True, 'message': '토너먼트가 삭제되었습니다.'})
        
#index.js

    @app.route('/check_players', methods=['POST'])
    def check_players():
        matches = request.json.get('matches', [])
        player_names = set()
        for match in matches:
            player_names.add(match['winner'])
            player_names.add(match['loser'])

        existing_players = {player.name for player in Player.query.filter(Player.name.in_(player_names), Player.is_valid == True).all()}
        unknown_players = list(player_names - existing_players)

        return jsonify({'unknownPlayers': unknown_players})

    def update_player_orders_by_point():
        categories = [
            ('achieve_order', Player.achieve_count.desc()),
            ('betting_order', Player.betting_count.desc()),
        ]

        for order_field, primary_criteria in categories:
            players = Player.query.filter(Player.is_valid == True).order_by(primary_criteria).all()
            
            current_rank = 0
            previous_primary_value = None
            
            primary_field_name = primary_criteria.element.name

            for i, player in enumerate(players, start=1):
                primary_value = getattr(player, primary_field_name)
                if primary_value != previous_primary_value:
                    current_rank = i
                    previous_primary_value = primary_value
                
                setattr(player, order_field, current_rank)

        db.session.commit()

    @app.route('/submit_matches', methods=['POST'])
    def submit_matches():
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
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
            traceback.print_exc() # 상세한 Traceback 정보를 출력합니다.
            # 브라우저에도 최소한의 오류 정보를 전달합니다.
            return jsonify({'error': '서버 내부에서 처리되지 않은 심각한 오류 발생', 'message': str(e)}), 500

    @app.route('/rankings', methods=['GET'])
    def rankings():
        # JS에서 'win_count_order' 같은 형식으로 요청을 보냅니다.
        category_from_req = request.args.get('category', 'win_order')
        
        # ▼▼▼ 핵심 수정: DB에서 사용할 이름('win_order')으로 변환합니다. ▼▼▼
        category = category_from_req.replace('_count', '')

        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 30))
        sort = request.args.get('sort', 'asc')

        valid_categories = ['win_order', 'loss_order', 'match_order', 'rate_order', 'opponent_order', 'achieve_order', 'betting_order']
        if category not in valid_categories:
            return jsonify([])

        secondary_criteria = {
            'win_order': Player.match_count.desc(), 'loss_order': Player.match_count.desc(),
            'match_order': Player.win_count.desc(), 'rate_order': Player.match_count.desc(),
            'opponent_order': Player.match_count.desc(), 'achieve_order': Player.betting_count.desc(),
            'betting_order': Player.achieve_count.desc(),
        }
        
        primary_order = getattr(Player, category)
        if sort == "asc":
            primary_order = primary_order.asc()
        else:
            primary_order = primary_order.desc()
        
        secondary_order = secondary_criteria.get(category, Player.id)
        
        players = Player.query.join(User).filter(
            Player.is_valid == True, User.is_admin == False
        ).order_by(primary_order, secondary_order, Player.id).offset(offset).limit(limit).all()

        response = []
        for player in players:
            response.append({
                'id': player.id,
                'current_rank': getattr(player, category),
                'rank': player.rank or '무',
                'name': player.name,
                'stats': {
                    'win_count': player.win_count, 'loss_count': player.loss_count,
                    'rate_count': player.rate_count, 'match_count': player.match_count,
                    'opponent_count': player.opponent_count, 'achieve_count': player.achieve_count,
                    'betting_count': player.betting_count,
                }
            })
        return jsonify(response)

    @app.route('/search_players', methods=['GET'])
    def search_players():
        query = request.args.get('query', '').strip()
        category_from_req = request.args.get('category', 'win_order')
        
        # ▼▼▼ 핵심 수정: DB에서 사용할 이름으로 변환합니다. ▼▼▼
        category = category_from_req.replace('_count', '')

        if len(query) < 2:
            return jsonify([])

        valid_categories = ['win_order', 'loss_order', 'match_order', 'rate_order', 'opponent_order', 'achieve_order', 'betting_order']
        if category not in valid_categories:
            return jsonify([])

        secondary_criteria = {
            'win_order': Player.match_count.desc(), 'loss_order': Player.match_count.desc(),
            'match_order': Player.win_count.desc(), 'rate_order': Player.match_count.desc(),
            'opponent_order': Player.match_count.desc(), 'achieve_order': Player.betting_count.desc(),
            'betting_order': Player.achieve_count.desc(),
        }

        primary_order = getattr(Player, category)
        secondary_order = secondary_criteria.get(category, Player.id)

        players = Player.query.join(User).filter(
            Player.name.ilike(f"%{query}%"), 
            Player.is_valid == True,
            User.is_admin == False
        ).order_by(primary_order, secondary_order).all()

        response = []
        for player in players:
            response.append({
                'id': player.id,
                'current_rank': getattr(player, category),
                'rank': player.rank or '무',
                'name': player.name,
                'stats': {
                    'win_count': player.win_count, 'loss_count': player.loss_count,
                    'rate_count': player.rate_count, 'match_count': player.match_count,
                    'opponent_count': player.opponent_count, 'achieve_count': player.achieve_count,
                    'betting_count': player.betting_count,
                }
            })
        return jsonify(response)

    # betting_approval.js

    @app.route('/get_bettings', methods=['GET'])
    def get_bettings():
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 30))
        tab = request.args.get('tab', 'all')
        
        query = Betting.query.filter(Betting.submitted == True).order_by(Betting.approved, Betting.id.desc())
        
        if tab == 'pending':
            query = query.filter(Betting.approved == False)
        elif tab == 'approved':
            query = query.filter(Betting.approved == True)
        
        bettings = query.offset(offset).limit(limit).all()
        
        match_ids = [betting.result for betting in bettings]
        matches = Match.query.filter(Match.id.in_(match_ids)).all()
        match_response = {
            match.id: {
                'id': match.id,
                'winner_name': match.winner_name,
                'winner_id': match.winner,
                'loser_name': match.loser_name,
                'score': match.score
            }
            for match in matches
        }
        
        response = []
        for betting in bettings:
            match_info = match_response.get(betting.result)
            if match_info:
                participants = [
                    {
                        'id': participant.id,
                        'participant_name': participant.participant_name,
                        'winner_id': participant.winner_id,
                        'betting_id': participant.betting_id
                    }
                    for participant in betting.participants
                ]
                
                win_participants = [
                    participant['participant_name']
                    for participant in participants
                    if participant['winner_id'] == match_info['winner_id']
                ]
                
                lose_participants = [
                    participant['participant_name']
                    for participant in participants
                    if participant['winner_id'] != match_info['winner_id']
                ]
                
                response.append({
                    'id': betting.id,
                    'match_id': betting.result,
                    'participants': participants,
                    'point': betting.point,
                    'approved': betting.approved,
                    'match': match_info,
                    'win_participants': win_participants,
                    'lose_participants': lose_participants
                })
        
        return jsonify(response)
            
    
    @app.route('/delete_bettings', methods=['POST'])
    def delete_bettings():
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'error': '삭제할 베팅이 선택되지 않았습니다.'}), 400

        bettings_to_delete = Betting.query.filter(Betting.id.in_(ids)).all()
        approved_count = 0
        pending_count = 0

        for betting in bettings_to_delete:
            # '미승인' 베팅은 포인트 변동이 없었으므로 계산 없이 삭제만 합니다.
            if not betting.approved:
                pending_count += 1
                continue

            # '승인된' 베팅은 모든 포인트 거래를 되돌립니다.
            approved_count += 1
            match = Match.query.get(betting.result)
            if not match:
                continue

            winner = Player.query.get(match.winner)
            loser = Player.query.get(match.loser)
            if not winner or not loser:
                continue

            # --- 1단계: 상금 분배량('share')을 승인 시와 동일한 로직으로 다시 계산 ---
            participants = betting.participants
            correct_bettors = [p for p in participants if p.winner_id == winner.id]
            total_sharers = 1 + len(correct_bettors)
            total_pot = betting.point * (2 + len(participants))
            share = total_pot // total_sharers

            # --- 2단계: 지급되었던 상금을 모두 회수 ---
            # 승리 선수에게서 상금 회수
            winner.betting_count -= share
            add_point_log(winner.id, betting_change=-share, reason=f"베팅({betting.id}) 삭제 (상금 회수)")

            # 베팅 성공자들에게서 상금 회수
            for p in correct_bettors:
                bettor_player = Player.query.get(p.participant_id)
                if bettor_player:
                    bettor_player.betting_count -= share
                    add_point_log(bettor_player.id, betting_change=-share, reason=f"베팅({betting.id}) 삭제 (상금 회수)")

            # --- 3단계: 차감되었던 참가비를 모두 환불 ---
            # 경기 주최자 2명에게 참가비 환불
            winner.betting_count += betting.point
            add_point_log(winner.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")
            loser.betting_count += betting.point
            add_point_log(loser.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")

            # 모든 참가자에게 참가비 환불
            for p in participants:
                participant_player = Player.query.get(p.participant_id)
                if participant_player:
                    participant_player.betting_count += betting.point
                    add_point_log(participant_player.id, betting_change=betting.point, reason=f"베팅({betting.id}) 삭제 (참가비 환불)")

        # --- 4단계: 모든 포인트 계산 후, 관련 기록을 DB에서 삭제 ---
        if bettings_to_delete:
            # 자식 테이블인 BettingParticipant 기록을 먼저 삭제
            BettingParticipant.query.filter(BettingParticipant.betting_id.in_(ids)).delete(synchronize_session=False)
            # 부모 테이블인 Betting 기록을 삭제
            Betting.query.filter(Betting.id.in_(ids)).delete(synchronize_session=False)

        db.session.commit()
        update_player_orders_by_point()

        return jsonify({'success': True, 'message': f'{approved_count}개의 승인된 베팅과 {pending_count}개의 미승인된 베팅이 삭제되었습니다.'})


    # approval.js

    @app.route('/get_matches', methods=['GET'])
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

    def calculate_opponent_count(player_id):
        count = (
            db.session.query(
                func.count(distinct(
                    case(
                        (Match.winner == player_id, Match.loser),
                        (Match.loser == player_id, Match.winner)
                    )
                ))
            )
            .filter(
                ((Match.winner == player_id) | (Match.loser == player_id)) & (Match.approved == True)
            )
            .scalar()
        )
        
        return count

    def update_player_orders_by_match():
        categories = [
            ('win_order', Player.win_count.desc()),
            ('loss_order', Player.loss_count.desc()),
            ('match_order', Player.match_count.desc()),
            ('rate_order', Player.rate_count.desc()),
            ('opponent_order', Player.opponent_count.desc()),
        ]

        for order_field, primary_criteria in categories:
            players = Player.query.filter(Player.is_valid == True).order_by(primary_criteria).all()
            
            current_rank = 0
            previous_primary_value = None
            
            primary_field_name = primary_criteria.element.name

            for i, player in enumerate(players, start=1):
                primary_value = getattr(player, primary_field_name)
                if primary_value != previous_primary_value:
                    current_rank = i
                    previous_primary_value = primary_value
                
                setattr(player, order_field, current_rank)

        db.session.commit()
        
    @app.route('/approve_matches', methods=['POST'])
    def approve_matches():
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'error': '승인할 경기가 선택되지 않았습니다.'}), 400
        
        matches = Match.query.filter(Match.id.in_(ids), Match.approved == False).all()

        for match in matches:
            winner = Player.query.get(match.winner)
            loser = Player.query.get(match.loser)
            if not winner or not loser:
                continue
            
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
                add_point_log(winner.id, betting_change=60, reason='누적 상대 수 40명 달성!')
                add_point_log(winner.id, achieve_change=30, reason='누적 상대 수 40명 달성!')
            
            # if winner.rank is not None and loser.rank is not None:
            #     if winner.rank - loser.rank == 8:
            #         winner.betting_count += 30
            #         winner.achieve_count += 30
            #     if loser.rank - winner.rank == 8:
            #         loser.betting_count += 3
            #         loser.achieve_count += 3
            
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
            
        db.session.commit()
        update_player_orders_by_match()
        update_player_orders_by_point()
        return jsonify({'success': True, 'message': f'{len(matches)}개의 경기가 승인되었습니다.'})

    @app.route('/delete_matches', methods=['POST'])
    def delete_matches():
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'error': '삭제할 경기가 선택되지 않았습니다.'}), 400
        
        matches_to_delete = Match.query.filter(Match.id.in_(ids)).all()
        
        approved_matches_count=0
        pending_matches_count=0

        for match in matches_to_delete:
            if match.approved:
                approved_matches_count+=1
                winner=Player.query.get(match.winner)
                loser=Player.query.get(match.loser)

                if not winner or not loser:
                    continue
                
                match.approved = False
                
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
                    add_point_log(loser.id, betting_change=-30, reason='누적 50경기 달성 취소')
                    add_point_log(loser.id, achieve_change=-30, reason='누적 50경기 달성 취소')

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
                
                # if winner.rank is not None and loser.rank is not None:
                #     if winner.rank - loser.rank == 8:
                #         winner.betting_count -= 30
                #         winner.achieve_count -= 30
                #     if loser.rank - winner.rank == 8:
                #         loser.betting_count -= 3
                #         loser.achieve_count -= 3  

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
                    if winner.gender == GenderEnum.MALE:
                        winner.rank = 8
                    elif winner.gender == GenderEnum.FEMALE:
                        winner.rank = 8
                if loser.is_she_or_he_freshman == FreshmanEnum.YES and loser.match_count == 15:
                    if loser.gender == GenderEnum.MALE:
                        loser.rank = 8
                    elif loser.gender == GenderEnum.FEMALE:
                        loser.rank = 8
            else:
                pending_matches_count+=1
        
        if matches_to_delete:
            Match.query.filter(Match.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()

        update_player_orders_by_match()
        update_player_orders_by_point()
        
        return jsonify({'success': True, 'message': f'{approved_matches_count}개의 승인된 경기와 {pending_matches_count}개의 미승인된 경기가 삭제되었습니다.'})

    @app.route('/select_all_matches', methods=['GET'])
    def select_all_matches():
        matches = Match.query.filter_by(approved=False).all()
        result = [match.id for match in matches]
        return jsonify({'ids': result})


    # assignment.js

    # @app.route('/update_ranks', methods=['POST'])
    # def update_ranks():     #부수를 다시 비율에 따라 조정하는 것으로 바뀔 시 주석 해제 후 사용.
    #     try:
    #         players = Player.query.filter(Player.is_valid == True, Player.match_count >= 5).order_by(
    #             Player.rate_count.desc(), Player.match_count.desc()
    #         ).all()

    #         total_players = len(players)
    #         cal_quotas = [round(total_players * p) for p in [0.05, 0.12, 0.21, 0.32, 0.44, 0.57, 0.71, 0.86, 1.00]]
    #         quotas = []
    #         for i in range(9):
    #             result = cal_quotas[i]
    #             if i != 0:
    #                 result = cal_quotas[i] - cal_quotas[i-1]
    #             quotas.append(result)

    #         current_rank = 1
    #         param = 0
    #         cutline = []
    #         for player in players:
    #             if player.previous_rank is None:
    #                 if current_rank != 1:
    #                     previous_cutline = next((entry for entry in cutline if entry['rank'] == current_rank - 1), None)
    #                     if previous_cutline and player.rate_count == previous_cutline['rate_count']:
    #                         param = 1
    #                         while True:
    #                             target_cutline = next(
    #                                 (entry for entry in cutline if entry['rank'] == current_rank - param - 1), None)
    #                             if not target_cutline or player.rate_count != target_cutline['rate_count']:
    #                                 break
    #                             param += 1
    #                 player.previous_rank = current_rank - param
    #                 param = 0
    #                 quotas[current_rank - 1] -= 1
    #                 if quotas[current_rank - 1] == 0:
    #                     cutline.append({'rank': current_rank, 'rate_count': player.rate_count})
    #                     current_rank += 1

    #         for player in Player.query.filter(Player.is_valid == True, Player.match_count < 5).all():
    #             player.previous_rank = None

    #         for player in players:
    #             if player.previous_rank is None:
    #                 player.rank_change = None
    #             elif player.rank is None:
    #                 player.rank_change = 'New'
    #             elif player.previous_rank < player.rank:
    #                 player.rank_change = 'Up'
    #                 if player.rank - player.previous_rank >= 1: player.betting_count += 2; player.achieve_count +=2
    #                 if player.rank - player.previous_rank >= 2: player.betting_count += 3; player.achieve_count +=3
    #             elif player.previous_rank > player.rank:
    #                 player.rank_change = 'Down'
    #                 if player.previous_rank - player.rank >= 2: player.betting_count += 3; player.achieve_count +=3
    #             else:
    #                 player.rank_change = None

    #         update_player_orders_by_point()
            
    #         cutline_table_rows = [
    #             f"""
    #             <tr>
    #                 <td class=\"border border-gray-300 p-2\">{rank_line['rank']}부</td>
    #                 <td class=\"border border-gray-300 p-2\">{rank_line['rate_count']}%</td>
    #             </tr>
    #             """
    #             for rank_line in cutline
    #         ]
            
    #         table_rows = [
    #             f"""
    #             <tr>
    #                 <td class="border border-gray-300 p-2">{p.name}</td>
    #                 <td class="border border-gray-300 p-2">{p.rank or '무'}</td>
    #                 <td class="border border-gray-300 p-2">{p.previous_rank or '무'}</td>
    #                 <td class="border border-gray-300 p-2">{p.rate_count}%</td>
    #                 <td class="border border-gray-300 p-2">{p.rank_change or ''}</td>
    #             </tr>
    #             """
    #             for p in Player.query.filter(Player.is_valid == True, Player.match_count >= 5).order_by(Player.rate_count.desc(), Player.match_count.desc()).all()
    #         ]

    #         html_content = f"""
    #         <div class="bg-gray-100">
    #             <table class="w-full bg-white border-collapse border border-gray-300 text-center mb-4">
    #                 <thead class="bg-gray-100">
    #                     <tr>
    #                         <th class="border border-gray-300 p-2">{total_players}명</th>
    #                         <th class="border border-gray-300 p-2">승률</th>
    #                     </tr>
    #                 </thead>
    #                 <tbody>
    #                     {''.join(cutline_table_rows)}
    #                 </tbody>
    #             </table>
    #             <table class="w-full bg-white border-collapse border border-gray-300 text-center mb-4">
    #                 <thead class="bg-gray-100">
    #                     <tr>
    #                         <th class="border border-gray-300 p-2">{total_players}명</th>
    #                         <th class="border border-gray-300 p-2">전</th>
    #                         <th class="border border-gray-300 p-2">후</th>
    #                         <th class="border border-gray-300 p-2">승률</th>
    #                         <th class="border border-gray-300 p-2">변동</th>
    #                     </tr>
    #                 </thead>
    #                 <tbody>
    #                     {''.join(table_rows)}
    #                 </tbody>
    #             </table>
    #         </div>
    #         """

    #         current_time = datetime.now(ZoneInfo("Asia/Seoul"))
            
    #         log = UpdateLog(title=str(current_time.date()), html_content=html_content, timestamp=current_time)
    #         db.session.add(log)

    #         for player in Player.query.filter(Player.is_valid == True, Player.rank_change.isnot(None)).all():
    #             player.rank = player.previous_rank
                
    #         for player in Player.query.all():
    #             player.previous_rank = None
    #             player.rank_change = None

    #         db.session.commit()
    #         return jsonify({'success': True, 'message': '부수 업데이트가 완료되었습니다.'})
    #     except Exception as e:
    #         return jsonify({'success': False, 'error': str(e)})

        
    @app.route('/revert_log', methods=['POST'])
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
        
    @app.route('/delete_logs', methods=['POST'])
    def delete_logs():
        ids = request.json.get('ids', [])
        UpdateLog.query.filter(UpdateLog.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'success': True, 'message': '선택한 로그가 삭제되었습니다.'})

    # settings.js

    @app.route('/reset_partner', methods=['POST'])
    def reset_partner():
        try:
            TodayPartner.query.delete()
            db.session.commit()
            return "오늘의 상대 초기화 완료", 200
        except Exception as e:
            print(e)
            return "초기화 실패", 500

    @app.route('/register_partner', methods=['POST'])
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

    @app.route('/submit_partner', methods=['POST'])
    def submit_partner():
        data = request.json
        pairs = data.get('pairs', [])

        try:
            for pair in pairs:
                p1_name = pair['p1_name']
                p2_name = pair['p2_name']

                p1 = Player.query.filter_by(name=p1_name).first()
                p2 = Player.query.filter_by(name=p2_name).first()

                if not p1 or not p2:
                    return jsonify({"error": f"{p1_name if not p1 else p2_name}의 정보를 찾을 수 없습니다."}), 400

                today_partner = TodayPartner(
                    p1_id=p1.id,
                    p1_name=p1.name,
                    p2_id=p2.id,
                    p2_name=p2.name
                )
                db.session.add(today_partner)

            db.session.commit()
            return "오늘의 상대 저장 완료", 200
        except Exception as e:
            print(e)
            return jsonify({"error": "저장 중 문제가 발생했습니다."}), 500
        
    # @app.route('/register_players', methods=['POST'])
    # def register_players():
    #     data = request.get_json()
    #     players = data.get('players', [])
    #     added_count = 0

    #     for name in players:
    #         if not Player.query.filter_by(name=name).first():
    #             new_player = Player(name=name)
    #             db.session.add(new_player)
    #             added_count += 1

    #     db.session.commit()
    #     return jsonify({'success': True, 'added_count': added_count})

    @app.route('/register_players', methods=['POST'])
    def register_players():
        data = request.get_json()
        players_data = data.get('players', [])
        added_count = 0

        for player_info in players_data:
            name = player_info.get('name')
            gender_str = player_info.get('gender')
            freshman_str = player_info.get('freshman')

            if not name or not gender_str or not freshman_str:
                continue

            if not Player.query.filter_by(name=name).first():
                # 1. 문자열을 Enum 객체로 명시적으로 변환
                gender_enum = GenderEnum(gender_str)
                freshman_enum = FreshmanEnum(freshman_str)

                # 2. 부수 계산
                initial_rank = None
                if gender_enum == GenderEnum.MALE:
                    initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 5
                elif gender_enum == GenderEnum.FEMALE:
                    initial_rank = 8 if freshman_enum == FreshmanEnum.YES else 7

                # 3. 모든 것이 준비된 상태에서 Player 객체 생성
                new_player = Player(
                    name=name,
                    gender=gender_enum,
                    is_she_or_he_freshman=freshman_enum,
                    rank=initial_rank
                )
                db.session.add(new_player)
                added_count += 1

        db.session.commit()
        return jsonify({'success': True, 'added_count': added_count})

    @app.route('/toggle_validity', methods=['POST'])
    def toggle_validity():
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'success': False, 'error': '선택된 항목이 없습니다.'}), 400

        players = Player.query.filter(Player.id.in_(ids)).all()
        for player in players:
            player.is_valid = not player.is_valid

        db.session.commit()
        update_player_orders_by_match()
        update_player_orders_by_point()
        return jsonify({'success': True, 'message': '선수의 유효/무효 상태가 변경되었습니다.'})

    @app.route('/delete_players', methods=['POST'])
    def delete_players():
        data = request.get_json()
        ids = data.get('ids', [])

        Player.query.filter(Player.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        update_player_orders_by_match()
        update_player_orders_by_point()
        return jsonify({'success': True, 'message': '선택한 선수가 삭제되었습니다.'})

    @app.route('/get_player_ids', methods=['POST'])
    def get_player_ids():
        data = request.get_json()
        names = data.get('names', [])

        if not names:
            return jsonify({'success': False, 'error': 'No names provided'}), 400

        players = Player.query.filter(Player.name.in_(names)).all()
        if not players:
            return jsonify({'success': False, 'error': 'No players found'}), 404

        player_ids = [player.id for player in players]
        return jsonify({'success': True, 'player_ids': player_ids})

    @app.route('/update_achievement', methods=['POST'])
    def update_achievement():
        data = request.get_json()
        player_ids = data.get('player_ids', [])
        additional_achieve = data.get('achieve', 0)
        additional_betting = data.get('betting', 0)

        if not player_ids or (additional_achieve == 0 and additional_betting == 0):
            return jsonify({'success': False, 'error': 'Invalid data provided'}), 400

        players = Player.query.filter(Player.id.in_(player_ids)).all()
        if not players:
            return jsonify({'success': False, 'error': 'No players found'}), 404

        for player in players:
            if additional_achieve != 0:
                player.achieve_count += additional_achieve
                add_point_log(player.id, achieve_change=additional_achieve, reason='수동 입력')
            if additional_betting != 0:
                player.betting_count += additional_betting
                # ▼▼▼ betting_change= 를 추가하여 버그를 수정합니다. ▼▼▼
                add_point_log(player.id, betting_change=additional_betting, reason='수동 입력')
        
        db.session.commit()
        update_player_orders_by_point()

        return jsonify({'success': True})


    # league.js

    @app.route('/create_league', methods=['POST'])
    def create_league():
        data = request.get_json()
        if not data or 'players' not in data:
            return jsonify({'error': '올바른 데이터를 제공해주세요.'}), 400

        players = data.get('players', [])
        if len(players) != 5:
            return jsonify({'error': '정확히 5명의 선수를 입력해야 합니다.'}), 400

        for name in players:
            player = Player.query.filter_by(name=name).first()
            if not player or not player.is_valid:
                return jsonify({'success': False, 'error': f'선수 "{name}"를 찾을 수 없습니다.'}), 400

        new_league = League(
            p1=players[0],
            p2=players[1],
            p3=players[2],
            p4=players[3],
            p5=players[4]
        )
        db.session.add(new_league)
        db.session.commit()

        return jsonify({'success': True, 'message': '리그전이 생성되었습니다.', 'league_id': new_league.id})


    # league_detail.js

    @app.route('/save_league/<int:league_id>', methods=['POST'])
    def save_league(league_id):
        data = request.get_json()
        league = League.query.get_or_404(league_id)

        scores = data.get('scores', {})
        for key, value in scores.items():
            if hasattr(league, key):
                setattr(league, key, value)

        db.session.commit()
        return jsonify({'success': True, 'message': '리그전이 저장되었습니다.'})

    @app.route('/delete_league/<int:league_id>', methods=['DELETE'])
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
        
        
    # betting.js

    @app.route('/get_players_ranks', methods=['POST'])
    def get_players_ranks():
        data = request.get_json()
        players = data.get('players', [])
        
        p1 = Player.query.filter_by(name=players[0]).first()
        p2 = Player.query.filter_by(name=players[1]).first()
        
        if not p1 or not p2:
            return jsonify({'error': '선수를 찾을 수 없습니다.'}), 400
        
        if p1.rank is not None and p2.rank is not None:
            rank_gap = abs(p1.rank - p2.rank)
        else: 
            rank_gap = None
        
        response = {
            'p1_rank': p1.rank,
            'p2_rank': p2.rank,
            'rank_gap': rank_gap
        }
        
        return jsonify(response)

    @app.route('/get_betting_counts', methods=['POST'])
    def get_betting_counts():
        data = request.get_json()
        players = data.get('players', [])
        participants = data.get('participants', [])
        
        p1 = Player.query.filter_by(name=players[0]).first()
        p2 = Player.query.filter_by(name=players[1]).first()

        if not p1 or not p2:
            return jsonify({'success': False, 'error': '선수를 찾을 수 없습니다.'}), 400

        participant_data = []
        for participant_name in participants:
            participant = Player.query.filter_by(name=participant_name.strip()).first()
            if participant:
                if participant.name == p1.name or participant.name == p2.name:
                    continue
                
                participant_data.append({
                    'name': participant.name,
                    'betting_count': participant.betting_count
                })
            else:
                return jsonify({'success': False, 'error': f'베팅 참가자 "{participant.name}"을/를 찾을 수 없습니다.'}), 400

        return jsonify({
            'success': True,
            'p1': {'name': p1.name, 'betting_count': p1.betting_count},
            'p2': {'name': p2.name, 'betting_count': p2.betting_count},
            'participants': participant_data
        })

    @app.route('/create_betting', methods=['POST'])
    def create_betting():
        data = request.get_json()
        players = data.get('players', [])
        participants = data.get('participants', [])
        point = data.get('point')

        if len(players) != 2:
            return jsonify({'error': '정확히 2명의 선수를 입력해야 합니다.'}), 400

        if not isinstance(point, int) or point <= 0:
            return jsonify({'error': '유효한 점수를 입력하세요.'}), 400

        p1 = Player.query.filter_by(name=players[0]).first()
        p2 = Player.query.filter_by(name=players[1]).first()

        if not p1 or not p2:
            return jsonify({'error': '선수를 찾을 수 없습니다.'}), 400

        new_betting = Betting(
            p1_id=p1.id,
            p1_name=p1.name,
            p2_id=p2.id,
            p2_name=p2.name,
            point=point
        )
        db.session.add(new_betting)
        db.session.flush()

        for participant_name in participants:
            participant = Player.query.filter_by(name=participant_name.strip()).first()
            if participant:
                if participant.name == p1.name or participant.name == p2.name:
                    continue
                
                betting_participant = BettingParticipant(
                    betting_id=new_betting.id,
                    participant_name=participant_name.strip(),
                    participant_id=participant.id
                )
                db.session.add(betting_participant)

        db.session.commit()

        return jsonify({'success': True, 'message': '베팅이 생성되었습니다.', 'betting_id': new_betting.id})
    


    # betting_detail.js
    # routes.py 파일에서 이 함수를 찾아 아래 내용으로 교체해주세요.

    @app.route('/submit_betting_result', methods=['POST'])
    def submit_betting_result():
        data = request.get_json()
        betting_id = data.get('bettingId')
        p1_name = data.get('p1Name')
        p2_name = data.get('p2Name')
        winner_name = data.get('winnerName')
        score = data.get('score')

        if not (betting_id and p1_name and p2_name and winner_name):
            return jsonify({"error": "모든 필드를 입력해주세요."}), 400

        betting = Betting.query.get_or_404(betting_id)
        if betting.submitted:
            return jsonify({"error": "이미 결과가 제출된 베팅입니다."}), 400

        # ▼▼▼ 패배자 이름을 정확하게 찾아냅니다. ▼▼▼
        loser_name = p1_name if winner_name == p2_name else p2_name

        # 이름으로 정확한 Player 객체를 찾습니다.
        winner = Player.query.filter_by(name=winner_name).first()
        loser = Player.query.filter_by(name=loser_name).first()
        
        if not winner or not loser:
            return jsonify({"error": "선수 정보를 찾을 수 없습니다."}), 400

        # 경기 결과를 Match 테이블에 기록합니다.
        new_match = Match(
            winner=winner.id, winner_name=winner.name,
            loser=loser.id, loser_name=loser.name,
            score=score, approved=False  # 승인 대기 상태
        )
        db.session.add(new_match)
        db.session.flush() 

        # Betting 테이블에 match_id를 연결하고, 제출됨 상태로 변경합니다.
        betting.result = new_match.id
        betting.submitted = True
        
        # 알림창에 표시할 베팅 성공/실패자 명단을 계산합니다.
        participants = betting.participants
        win_participants_names = [p.participant_name for p in participants if p.winner_id == winner.id]
        lose_participants_names = [p.participant_name for p in participants if p.winner_id != winner.id and p.winner_id is not None]

        # 예상 분배 포인트를 계산합니다.
        total_sharers = 1 + len(win_participants_names)
        total_points = betting.point * (2 + len(participants))
        share = total_points // total_sharers if total_sharers > 0 else 0
        
        db.session.commit()

        return jsonify({
            "message": "베팅 결과가 성공적으로 처리되었습니다!",
            "results": {
                "winnerName": winner.name,
                "loserName": loser.name, # 정확한 패배자 이름
                "winParticipants": win_participants_names,
                "loseParticipants": lose_participants_names,
                "distributedPoints": share
            }
        }), 200
        
    @app.route('/approve_bettings', methods=['POST'])
    def approve_bettings():
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'success': False, 'message': '승인할 베팅이 선택되지 않았습니다.'}), 400
        
        bettings = Betting.query.filter(Betting.id.in_(ids), Betting.approved == False).all()

        for betting in bettings:
            match = Match.query.get(betting.result)
            if not match: continue

            # ▼▼▼ 경기 결과에서 실제 승리한 선수의 'ID'를 명확하게 가져옵니다. ▼▼▼
            actual_winner_id = match.winner
            
            winner_player = Player.query.get(actual_winner_id)
            loser_player = Player.query.get(match.loser)
            if not winner_player or not loser_player: continue
            
            betting_reason = f"{winner_player.name} vs {loser_player.name} 베팅"
            
            # 주최자 및 참가자 포인트 차감 로직 (기존과 동일)
            winner_player.betting_count -= betting.point
            add_point_log(winner_player.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 주최")
            loser_player.betting_count -= betting.point
            add_point_log(loser_player.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 주최")
            
            participants = betting.participants
            for p in participants:
                participant_player = Player.query.get(p.participant_id)
                if participant_player:
                    participant_player.betting_count -= betting.point
                    add_point_log(participant_player.id, betting_change=-1 * betting.point, reason=f"{betting_reason} 참여")

            # ▼▼▼ 베팅 성공자를 판별하는 핵심 로직 ▼▼▼
            correct_bettors = [p for p in participants if p.winner_id == actual_winner_id]
            
            total_pot = betting.point * (2 + len(participants))
            total_sharers = 1 + len(correct_bettors)
            share = total_pot // total_sharers if total_sharers > 0 else 0
            
            # 포인트 분배 로직 (기존과 동일)
            for p in correct_bettors:
                bettor_player = Player.query.get(p.participant_id)
                if bettor_player:
                    bettor_player.betting_count += share
                    add_point_log(bettor_player.id, betting_change=share, reason=f"{betting_reason} 성공")

            winner_player.betting_count += share
            add_point_log(winner_player.id, betting_change=share, reason=f"{betting_reason} 경기 승리")
            
            betting.approved = True

        db.session.commit()
        update_player_orders_by_point()
      
        return jsonify({"success": True, "message": "선택한 베팅이 승인되었습니다."})
    
    @app.route('/betting/<int:betting_id>/delete', methods=['DELETE'])
    def delete_betting(betting_id):
        ids = request.json.get('ids', [])
        if not ids:
            return jsonify({'error': '삭제할 베팅이 선택되지 않았습니다.'}), 400

        bettings_to_delete = Betting.query.filter(Betting.id.in_(ids)).all()
        approved_count = 0
        pending_count = 0

        for betting in bettings_to_delete:
            if not betting.approved:
                pending_count += 1
                continue

            approved_count += 1
            match = Match.query.get(betting.result)
            if not match: continue
            winner = Player.query.get(match.winner)
            loser = Player.query.get(match.loser)
            if not winner or not loser: continue

            betting_reason = f"{winner.name} vs {loser.name} 베팅"
            
            participants = betting.participants
            correct_bettors = [p for p in participants if p.winner_id == winner.id]
            total_sharers = 1 + len(correct_bettors)
            total_pot = betting.point * (2 + len(participants))
            share = total_pot // total_sharers if total_sharers > 0 else 0

            winner.betting_count -= share
            add_point_log(winner.id, betting_change=-share, reason=f"{betting_reason} 삭제 (상금 회수)")

            for p in correct_bettors:
                bettor_player = Player.query.get(p.participant_id)
                if bettor_player:
                    bettor_player.betting_count -= share
                    add_point_log(bettor_player.id, betting_change=-share, reason=f"{betting_reason} 삭제 (상금 회수)")

            winner.betting_count += betting.point
            add_point_log(winner.id, betting_change=betting.point, reason=f"{betting_reason} 삭제 (참가비 환불)")
            loser.betting_count += betting.point
            add_point_log(loser.id, betting_change=betting.point, reason=f"{betting_reason} 삭제 (참가비 환불)")

            for p in participants:
                participant_player = Player.query.get(p.participant_id)
                if participant_player:
                    participant_player.betting_count += betting.point
                    add_point_log(participant_player.id, betting_change=betting.point, reason=f"{betting_reason} 삭제 (참가비 환불)")

        if bettings_to_delete:
            BettingParticipant.query.filter(BettingParticipant.betting_id.in_(ids)).delete(synchronize_session=False)
            Betting.query.filter(Betting.id.in_(ids)).delete(synchronize_session=False)

        db.session.commit()
        update_player_orders_by_point()

        return jsonify({'success': True, 'message': f'{approved_count}개의 승인된 베팅과 {pending_count}개의 미승인된 베팅이 삭제되었습니다.'})

    @app.route('/remove_participants', methods=['POST'])
    def remove_participants():
        data = request.get_json()
        player_ids = data.get('playerIds', [])
        betting_id = data.get('bettingId')

        if not player_ids:
            return jsonify({'success': False, 'error': '제거할 참가자를 찾을 수 없습니다.'}), 400
        if not betting_id:
            return jsonify({'success': False, 'error': '해당 베팅을 찾을 수 없습니다.'}), 400

        betting = Betting.query.get(betting_id)
        if not betting:
            return jsonify({'success': False, 'error': '해당 베팅을 찾을 수 없습니다.'}), 404

        removed_participants = []

        for player_id in player_ids:
            participant = BettingParticipant.query.filter_by(
                betting_id=betting_id, participant_id=player_id
            ).first()

            if participant:
                removed_participants.append(participant.participant_name)
                db.session.delete(participant)

        db.session.commit()
        
        participant_names_str = ', '.join(removed_participants) if removed_participants else '0명'
        
        return jsonify({'success': True, 'message': f'참가자 {participant_names_str} (이)가 제거되었습니다.'})

    @app.route('/betting/<int:betting_id>/update', methods=['POST'])
    def update_betting(betting_id):
        data = request.get_json()
        participants = data.get('participants', [])

        if not participants:
            return jsonify({'error': '참가자 데이터가 제공되지 않았습니다.'}), 400

        try:
            participants = sorted(participants, key=lambda x: x.get('id'))
            
            for participant_data in participants:
                participant_id = participant_data.get('id')
                winner_id = participant_data.get('winner')

                betting_participant = BettingParticipant.query.filter_by(
                    betting_id=betting_id, participant_id=participant_id
                ).first()

                if betting_participant:
                    betting_participant.winner_id = winner_id
            
            db.session.commit()
            return jsonify({'success': True, 'message': '베팅 데이터가 성공적으로 저장되었습니다!'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'서버 오류가 발생했습니다: {str(e)}'}), 500
        
    
    def submit_match_internal(match_data):
        winner_name = match_data.get("winner")
        loser_name = match_data.get("loser")
        score_value = match_data.get("score")

        if not winner_name or not loser_name or not score_value:
            return {"error": "잘못된 데이터"}

        winner = Player.query.filter_by(name=winner_name).first()
        if not winner:
            winner = Player(name=winner_name)
            db.session.add(winner)

        loser = Player.query.filter_by(name=loser_name).first()
        if not loser:
            loser = Player(name=loser_name)
            db.session.add(loser)

        db.session.flush()

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
        db.session.commit()

        return {"match_id": new_match.id}

    