import sys
import os

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models import User, Player
from flask import template_rendered
from contextlib import contextmanager
import unittest

@contextmanager
def captured_templates(app):
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)

class TestRanking(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
            # Create test player 1
            p1 = Player(name='Player1', win_count=10, rate_count=50.0, is_valid=True)
            db.session.add(p1)
            db.session.commit()
            
            # Create test user for p1
            u1 = User(username='user1', player_id=p1.id, is_admin=False)
            u1.set_password('password')
            db.session.add(u1)
            
            # Create test player 2
            p2 = Player(name='Player2', win_count=20, rate_count=60.0, is_valid=True)
            db.session.add(p2)
            
            # Create test player 3 (admin, should be excluded if we filtered admins, 
            # but current logic filters User.is_admin. If player has no user or user is admin)
            # Route logic: Player.query.join(Player.user).filter(Player.is_valid == True, User.is_admin == False).all()
            # So a player MUST have a user to be shown? 
            # Original code: Player.query.join(Player.user).filter(...)
            # This means players WITHOUT users will NOT be shown. 
            # Let's verify if this is intended. 
            # The prompt said "User visibility". 
            # If regular players don't have users, they won't show. 
            # Assuming all active players have users.
            
            p3 = Player(name='AdminPlayer', is_valid=True)
            db.session.add(p3)
            db.session.commit()
            
            u3 = User(username='admin', player_id=p3.id, is_admin=True)
            u3.set_password('adminpass')
            db.session.add(u3)
            
            # Create player 2 user
            u2 = User(username='user2', player_id=p2.id, is_admin=False)
            u2.set_password('password')
            db.session.add(u2)
            
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_ranking_page_content(self):
        # Login
        self.client.post('/login', data={'username': 'user1', 'password': 'password'})
        
        with self.app.app_context():
            with captured_templates(self.app) as templates:
                response = self.client.get('/rankings_page')
                self.assertEqual(response.status_code, 200)
                
                template, context = templates[0]
                self.assertEqual(template.name, 'rankings.html')
                
                players = context.get('players')
                self.assertIsNotNone(players)
                
                player_names = [p.name for p in players]
                self.assertIn('Player1', player_names)
                self.assertIn('Player2', player_names)
                self.assertNotIn('AdminPlayer', player_names) # Admin should be excluded
                
                print("Ranking page verification successful!")
                print(f"Players found: {player_names}")

if __name__ == '__main__':
    unittest.main()
