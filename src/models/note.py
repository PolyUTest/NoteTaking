from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db, note_shares

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True, default='General')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for backward compatibility
    is_public = db.Column(db.Boolean, default=False)  # For public sharing via link
    public_id = db.Column(db.String(50), unique=True, nullable=True)  # Public sharing identifier
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Many-to-many relationship for sharing with specific users
    shared_with = db.relationship('User', secondary=note_shares, backref='shared_notes')
    
    def __repr__(self):
        return f'<Note {self.title}>'
    
    def to_dict(self, include_sharing=False):
        result = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'user_id': self.user_id,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sharing:
            result['shared_with'] = [user.to_dict() for user in self.shared_with]
            result['public_id'] = self.public_id
            result['owner'] = self.owner.to_dict() if self.owner else None
            
        return result

