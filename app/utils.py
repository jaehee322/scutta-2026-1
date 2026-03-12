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
    """모든 순위(경기+포인트)를 한 번에 재계산합니다."""
    players = Player.query.filter(Player.is_valid == True).all()

    categories = [
        ('win_order', 'win_count'),
        ('loss_order', 'loss_count'),
        ('match_order', 'match_count'),
        ('rate_order', 'rate_count'),
        ('opponent_order', 'opponent_count'),
        ('achieve_order', 'achieve_count'),
        ('betting_order', 'betting_count'),
        ('scutta_order', 'scutta_count'),
    ]

    for order_field, value_field in categories:
        sorted_players = sorted(players, key=lambda p: getattr(p, value_field) or 0, reverse=True)
        current_rank = 0
        previous_value = None
        for i, player in enumerate(sorted_players, start=1):
            value = getattr(player, value_field) or 0
            if value != previous_value:
                current_rank = i
                previous_value = value
            setattr(player, order_field, current_rank)

    db.session.commit()


def update_player_orders_by_point():
    """update_player_orders_by_match에 통합됨. 호환성을 위해 유지."""
    pass


def get_player_ranks(player):
    """특정 선수의 순위 정보를 반환합니다. DB에 저장된 순위를 직접 사용합니다."""
    return {
        'win_order': player.win_order,
        'loss_order': player.loss_order,
        'rate_order': player.rate_order,
        'match_order': player.match_order,
        'opponent_order': player.opponent_order,
        'achieve_order': player.achieve_order,
        'betting_order': player.betting_order,
        'scutta_order': player.scutta_order
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
