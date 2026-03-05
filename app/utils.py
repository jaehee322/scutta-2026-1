from sqlalchemy import distinct, case, func
from .extensions import db
from .models import Match, Player, PlayerPointLog, User


def _get_summary_rankings_data(current_player):
    """ranking_page 전용: 카테고리별 상위 5명 + 현재 유저 정보를 반환합니다."""
    categories = [
        ('승리', Player.win_order.asc(), 'win_count', 'win_order'),
        ('승률', Player.rate_order.asc(), 'rate_count', 'rate_order'),
        ('경기', Player.match_order.asc(), 'match_count', 'match_order'),
        ('베팅', Player.betting_order.asc(), 'betting_count', 'betting_order'),
    ]
    rankings_data = {}

    for title, order_criteria, value_attr, rank_attr in categories:
        top_5_players = Player.query.join(Player.user).filter(
            Player.is_valid == True,
            User.is_admin == False
        ).order_by(order_criteria, Player.name).limit(5).all()

        final_player_list = []
        is_user_in_top_5 = False

        for p in top_5_players:
            final_player_list.append({
                'id': p.id,
                'name': p.name,
                'rank': p.rank,
                'value': getattr(p, value_attr),
                'actual_rank': getattr(p, rank_attr)
            })
            if current_player and p.id == current_player.id:
                is_user_in_top_5 = True

        if current_player and not is_user_in_top_5:
            if len(final_player_list) >= 5:
                final_player_list.pop()

            final_player_list.append({
                'id': current_player.id,
                'name': current_player.name,
                'rank': current_player.rank,
                'value': getattr(current_player, value_attr),
                'actual_rank': getattr(current_player, rank_attr)
            })

        rankings_data[title] = final_player_list

    return rankings_data


def add_point_log(player_id, achieve_change=0, betting_change=0, scutta_change=0, reason=""):
    """플레이어 포인트 변동 로그 기록"""
    if achieve_change == 0 and betting_change == 0 and scutta_change == 0:
        return

    log = PlayerPointLog(
        player_id=player_id,
        achieve_change=achieve_change,
        betting_change=betting_change,
        scutta_change=scutta_change,
        reason=reason
    )
    db.session.add(log)


def calculate_opponent_count(player_id):
    """해당 선수의 고유 상대 수를 계산합니다."""
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
    """승리/패배/경기 수 기반 순위를 재계산합니다."""
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


def update_player_orders_by_point():
    """업적/베팅/스쿠타 포인트 기반 순위를 재계산합니다."""
    categories = [
        ('achieve_order', Player.achieve_count.desc()),
        ('betting_order', Player.betting_count.desc()),
        ('scutta_order', Player.scutta_count.desc()),
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


def get_player_ranks(player):
    """특정 선수의 실시간 순위 정보를 계산하여 반환합니다."""
    # 1. 승리 순위
    win_rank = Player.query.filter(Player.win_count > player.win_count, Player.is_valid == True).count() + 1
    
    # 2. 패배 순위 (많이 진 순서)
    loss_rank = Player.query.filter(Player.loss_count > player.loss_count, Player.is_valid == True).count() + 1
    
    # 3. 승률 순위
    rate_rank = Player.query.filter(Player.rate_count > player.rate_count, Player.is_valid == True).count() + 1
    
    # 4. 경기수 순위
    match_rank = Player.query.filter(Player.match_count > player.match_count, Player.is_valid == True).count() + 1
    
    # 5. 상대수 순위
    opponent_rank = Player.query.filter(Player.opponent_count > player.opponent_count, Player.is_valid == True).count() + 1
    
    # 6. 업적 순위
    achieve_rank = Player.query.filter(Player.achieve_count > player.achieve_count, Player.is_valid == True).count() + 1
    
    # 7. 베팅 순위
    betting_rank = Player.query.filter(Player.betting_count > player.betting_count, Player.is_valid == True).count() + 1

    # 8. 스쿠타 순위
    scutta_rank = Player.query.filter(Player.scutta_count > player.scutta_count, Player.is_valid == True).count() + 1
    
    return {
        'win_order': win_rank,
        'loss_order': loss_rank,
        'rate_order': rate_rank,
        'match_order': match_rank,
        'opponent_order': opponent_rank,
        'achieve_order': achieve_rank,
        'betting_order': betting_rank,
        'scutta_order': scutta_rank
    }


def attach_rank(players, attribute, rank_attr_name):
    """
    리스트에 있는 선수들에게 특정 속성(attribute)을 기준으로 순위(rank_attr_name)를 매깁니다.
    동점자가 있을 경우 공동 순위를 부여합니다 (예: 1위, 1위, 3위).
    """
    # 점수 기준 내림차순 정렬
    sorted_players = sorted(players, key=lambda p: getattr(p, attribute) or 0, reverse=True)

    previous_val = None
    current_rank = 1
    
    for i, player in enumerate(sorted_players):
        val = getattr(player, attribute) or 0
        
        if i > 0 and val == previous_val:
            # 이전 선수와 점수가 같으면 같은 순위 유지 (current_rank 변하지 않음)
            pass 
        else:
            # 다르면 현재 인덱스+1 이 순위가 됨
            current_rank = i + 1
        
        setattr(player, rank_attr_name, current_rank)
        previous_val = val
