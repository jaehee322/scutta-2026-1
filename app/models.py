import enum
from .extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

def get_seoul_time():
    return datetime.now(ZoneInfo("Asia/Seoul"))

class GenderEnum(enum.Enum):
    MALE='M'
    FEMALE='F'

class FreshmanEnum(enum.Enum):
    YES='Y'
    No='N'

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_valid = db.Column(db.Boolean, default=True)
    gender=db.Column(db.Enum(GenderEnum), nullable=True)
    previous_rank = db.Column(db.Integer, default=None)
    rank_change = db.Column(db.String(10), default=None)
    rank = db.Column(db.Integer, default=None)
    match_count = db.Column(db.Integer, default=0)
    win_count = db.Column(db.Integer, default=0)
    loss_count = db.Column(db.Integer, default=0)
    rate_count = db.Column(db.Float, default=0.0)
    opponent_count = db.Column(db.Integer, default=0)
    achieve_count = db.Column(db.Integer, default=0)
    betting_count = db.Column(db.Integer, default=100)
    win_order = db.Column(db.Integer, default=None)
    loss_order = db.Column(db.Integer, default=None)
    match_order = db.Column(db.Integer, default=None)
    rate_order = db.Column(db.Integer, default=None)
    opponent_order = db.Column(db.Integer, default=None)
    achieve_order = db.Column(db.Integer, default=None)
    betting_order = db.Column(db.Integer, default=None)
    is_she_or_he_freshman = db.Column(db.Enum(FreshmanEnum), nullable=True)

    def __repr__(self):
        return f"<Player {self.name}>"

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    winner = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    winner_name = db.Column(db.String(100), nullable=False)
    loser = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    loser_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_seoul_time)
    approved = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Match {self.winner_name} vs {self.loser_name}>"

class UpdateLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=get_seoul_time)

class League(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=True)
    p1 = db.Column(db.String(100), nullable=False)
    p2 = db.Column(db.String(100), nullable=False)
    p3 = db.Column(db.String(100), nullable=False)
    p4 = db.Column(db.String(100), nullable=False)
    p5 = db.Column(db.String(100), nullable=False)
    p1p2 = db.Column(db.Integer, default=None)
    p1p3 = db.Column(db.Integer, default=None)
    p1p4 = db.Column(db.Integer, default=None)
    p1p5 = db.Column(db.Integer, default=None)
    p2p1 = db.Column(db.Integer, default=None)
    p2p3 = db.Column(db.Integer, default=None)
    p2p4 = db.Column(db.Integer, default=None)
    p2p5 = db.Column(db.Integer, default=None)
    p3p1 = db.Column(db.Integer, default=None)
    p3p2 = db.Column(db.Integer, default=None)
    p3p4 = db.Column(db.Integer, default=None)
    p3p5 = db.Column(db.Integer, default=None)
    p4p1 = db.Column(db.Integer, default=None)
    p4p2 = db.Column(db.Integer, default=None)
    p4p3 = db.Column(db.Integer, default=None)
    p4p5 = db.Column(db.Integer, default=None)
    p5p1 = db.Column(db.Integer, default=None)
    p5p2 = db.Column(db.Integer, default=None)
    p5p3 = db.Column(db.Integer, default=None)
    p5p4 = db.Column(db.Integer, default=None)

class Betting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    p1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    p1_name = db.Column(db.String(100), nullable=False)
    p2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    p2_name = db.Column(db.String(100), nullable=False)
    point = db.Column(db.Integer, nullable=False)
    approved = db.Column(db.Boolean, default=False)
    submitted = db.Column(db.Boolean, default=False)
    result = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=True)
    is_closed = db.Column(db.Boolean, default=False, nullable=True)
    participants = db.relationship('BettingParticipant', backref='betting', cascade='all, delete-orphan')

class BettingParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    betting_id = db.Column(db.Integer, db.ForeignKey('betting.id'), nullable=False)
    participant_name = db.Column(db.String(100), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=True)

class TodayPartner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    p1_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    p1_name = db.Column(db.String(100), nullable=False)
    p2_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    p2_name = db.Column(db.String(100), nullable=False)
    submitted = db.Column(db.Boolean, default=False)
    

class PlayerPointLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    achieve_change = db.Column(db.Integer, default=0)
    betting_change = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Seoul")))
    player = db.relationship('Player', backref=db.backref('point_logs', lazy=True))

    def __repr__(self):
        return f"<PlayerPointLog {self.player.name} {self.reason}>"
    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)

    player_id = db.Column(db.Integer, db.ForeignKey('player.id'))
    # User 객체에서 player 정보에 접근하기 위한 관계 설정
    player = db.relationship('Player', backref=db.backref('user', uselist=False))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'
    

class Tournament(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default='대기중', nullable=False) # 대기중, 진행중, 완료
    created_at = db.Column(db.DateTime(timezone=True), default=get_seoul_time)
    bracket_data = db.Column(db.JSON, nullable=True)