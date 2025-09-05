from flask import Blueprint, jsonify, request, session
from src.models.user import User, db
from functools import wraps

user_bp = Blueprint('user', __name__)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = get_current_user()
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def can_access_note(user, note):
    """Check if user can access a note"""
    if not user:
        return False
    
    # User owns the note
    if note.user_id == user.id:
        return True
    
    # Note is shared with the user
    if user in note.shared_with:
        return True
    
    # Admin can access all notes
    if user.is_admin:
        return True
    
    return False

def can_modify_note(user, note):
    """Check if user can modify (edit/delete) a note"""
    if not user:
        return False
    
    # User owns the note
    if note.user_id == user.id:
        return True
    
    # Admin can modify all notes
    if user.is_admin:
        return True
    
    return False

@user_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        if not data or 'username' not in data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Username, email, and password are required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        user = User(username=data['username'], email=data['email'])
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()
        
        # Log in the user
        session['user_id'] = user.id
        
        return jsonify(user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Username and password are required'}), 400
        
        user = User.query.filter_by(username=data['username']).first()
        
        if user and user.check_password(data['password']):
            session['user_id'] = user.id
            return jsonify(user.to_dict()), 200
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@user_bp.route('/me', methods=['GET'])
@login_required
def get_current_user_info():
    """Get current user info"""
    user = get_current_user()
    return jsonify(user.to_dict())

@user_bp.route('/users/search', methods=['GET'])
@login_required
def search_users():
    """Search users by username for sharing"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        User.username.contains(query)
    ).limit(10).all()
    
    return jsonify([user.to_dict() for user in users])

# Keep original endpoints for backward compatibility
@user_bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@user_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    user = User(username=data['username'], email=data['email'])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    db.session.commit()
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204

# Admin-only endpoints for user management
@user_bp.route('/admin/users', methods=['GET'])
@admin_required
def admin_get_all_users():
    """Admin endpoint to get all users with full details"""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([user.to_dict() for user in users])

@user_bp.route('/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    """Admin endpoint to update any user"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update user fields
        if 'username' in data:
            # Check if username is already taken by another user
            existing_user = User.query.filter_by(username=data['username']).first()
            if existing_user and existing_user.id != user_id:
                return jsonify({'error': 'Username already exists'}), 400
            user.username = data['username']
        
        if 'email' in data:
            # Check if email is already taken by another user
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user and existing_user.id != user_id:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        if 'is_admin' in data:
            user.is_admin = bool(data['is_admin'])
        
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        db.session.commit()
        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """Admin endpoint to delete any user"""
    try:
        current_user = get_current_user()
        
        # Prevent admin from deleting themselves
        if user_id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': f'User {user.username} deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/admin/users/<int:user_id>/make-admin', methods=['POST'])
@admin_required
def admin_make_user_admin(user_id):
    """Admin endpoint to grant admin privileges to a user"""
    try:
        user = User.query.get_or_404(user_id)
        user.is_admin = True
        db.session.commit()
        return jsonify({'message': f'User {user.username} is now an admin', 'user': user.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/admin/users/<int:user_id>/remove-admin', methods=['POST'])
@admin_required
def admin_remove_user_admin(user_id):
    """Admin endpoint to remove admin privileges from a user"""
    try:
        current_user = get_current_user()
        
        # Prevent admin from removing their own admin privileges
        if user_id == current_user.id:
            return jsonify({'error': 'Cannot remove admin privileges from your own account'}), 400
        
        user = User.query.get_or_404(user_id)
        user.is_admin = False
        db.session.commit()
        return jsonify({'message': f'Admin privileges removed from {user.username}', 'user': user.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/admin/users/<int:user_id>/notes', methods=['GET'])
@admin_required
def admin_get_user_notes(user_id):
    """Admin endpoint to view all notes owned by a specific user"""
    try:
        from src.models.note import Note  # Import here to avoid circular import
        user = User.query.get_or_404(user_id)
        notes = Note.query.filter_by(user_id=user_id).order_by(Note.updated_at.desc()).all()
        return jsonify({
            'user': user.to_dict(),
            'notes': [note.to_dict() for note in notes]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
