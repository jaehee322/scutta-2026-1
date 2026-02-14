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


def add_point_log(player_id, achieve_change=0, betting_change=0, reason=""):
    """플레이어 포인트 변동 로그 기록"""
    if achieve_change == 0 and betting_change == 0:
        return

    log = PlayerPointLog(
        player_id=player_id,
        achieve_change=achieve_change,
        betting_change=betting_change,
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
    """업적/베팅 포인트 기반 순위를 재계산합니다."""
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
