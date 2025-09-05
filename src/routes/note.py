from flask import Blueprint, jsonify, request, session
from src.models.note import Note, db
from src.models.user import User
from src.routes.user import login_required, get_current_user
import uuid

note_bp = Blueprint('note', __name__)

@note_bp.route('/notes', methods=['GET'])
def get_notes():
    """Get all notes (user's own notes + shared notes if logged in, or all notes if not logged in)"""
    current_user = get_current_user()
    
    if current_user:
        # Get user's own notes and notes shared with them
        own_notes = Note.query.filter_by(user_id=current_user.id).all()
        shared_notes = current_user.shared_notes
        
        # Combine and deduplicate
        all_notes = {note.id: note for note in own_notes + shared_notes}.values()
        notes = sorted(all_notes, key=lambda x: x.updated_at, reverse=True)
    else:
        # For backward compatibility, show all notes if not logged in
        notes = Note.query.order_by(Note.updated_at.desc()).all()
    
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
def create_note():
    """Create a new note"""
    try:
        data = request.json
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Title and content are required'}), 400
        
        current_user = get_current_user()
        note = Note(
            title=data['title'], 
            content=data['content'],
            category=data.get('category', 'General'),
            user_id=current_user.id if current_user else None
        )
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Get a specific note by ID"""
    note = Note.query.get_or_404(note_id)
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Update a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        note.title = data.get('title', note.title)
        note.content = data.get('content', note.content)
        note.category = data.get('category', note.category)
        db.session.commit()
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
def search_notes():
    """Search notes by title or content"""
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    if not query and not category:
        return jsonify([])
    
    # Start with base query
    notes_query = Note.query
    
    # Add text search filter if provided
    if query:
        notes_query = notes_query.filter(
            (Note.title.contains(query)) | (Note.content.contains(query))
        )
    
    # Add category filter if provided
    if category:
        notes_query = notes_query.filter(Note.category == category)
    
    notes = notes_query.order_by(Note.updated_at.desc()).all()
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes/categories', methods=['GET'])
def get_categories():
    """Get all unique categories"""
    try:
        categories = db.session.query(Note.category).distinct().all()
        category_list = [cat[0] for cat in categories if cat[0]]
        return jsonify(category_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/by-category/<category>', methods=['GET'])
def get_notes_by_category(category):
    """Get notes by category"""
    try:
        current_user = get_current_user()
        
        if current_user:
            # Get user's own notes and notes shared with them
            own_notes = Note.query.filter_by(category=category, user_id=current_user.id).all()
            shared_notes = [note for note in current_user.shared_notes if note.category == category]
            
            # Combine and deduplicate
            all_notes = {note.id: note for note in own_notes + shared_notes}.values()
            notes = sorted(all_notes, key=lambda x: x.updated_at, reverse=True)
        else:
            # For backward compatibility
            notes = Note.query.filter_by(category=category).order_by(Note.updated_at.desc()).all()
            
        return jsonify([note.to_dict() for note in notes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Sharing endpoints
@note_bp.route('/notes/<int:note_id>/share', methods=['POST'])
@login_required
def share_note(note_id):
    """Share a note with specific users"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        # Check if user owns the note
        if note.user_id != current_user.id:
            return jsonify({'error': 'You can only share your own notes'}), 403
        
        data = request.json
        if not data or 'usernames' not in data:
            return jsonify({'error': 'List of usernames is required'}), 400
        
        shared_users = []
        for username in data['usernames']:
            user = User.query.filter_by(username=username).first()
            if user and user.id != current_user.id:
                if user not in note.shared_with:
                    note.shared_with.append(user)
                    shared_users.append(user.to_dict())
        
        db.session.commit()
        return jsonify({
            'message': f'Note shared with {len(shared_users)} users',
            'shared_with': shared_users
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>/unshare', methods=['POST'])
@login_required
def unshare_note(note_id):
    """Unshare a note from specific users"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        # Check if user owns the note
        if note.user_id != current_user.id:
            return jsonify({'error': 'You can only unshare your own notes'}), 403
        
        data = request.json
        if not data or 'usernames' not in data:
            return jsonify({'error': 'List of usernames is required'}), 400
        
        removed_users = []
        for username in data['usernames']:
            user = User.query.filter_by(username=username).first()
            if user and user in note.shared_with:
                note.shared_with.remove(user)
                removed_users.append(user.to_dict())
        
        db.session.commit()
        return jsonify({
            'message': f'Note unshared from {len(removed_users)} users',
            'removed_from': removed_users
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>/public', methods=['POST'])
@login_required
def make_note_public(note_id):
    """Make a note publicly shareable via link"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        # Check if user owns the note
        if note.user_id != current_user.id:
            return jsonify({'error': 'You can only make your own notes public'}), 403
        
        if not note.public_id:
            note.public_id = str(uuid.uuid4())
        note.is_public = True
        
        db.session.commit()
        return jsonify({
            'message': 'Note is now publicly accessible',
            'public_id': note.public_id,
            'public_url': f'/public/{note.public_id}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>/unpublic', methods=['POST'])
@login_required
def make_note_private(note_id):
    """Make a public note private again"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        # Check if user owns the note
        if note.user_id != current_user.id:
            return jsonify({'error': 'You can only modify your own notes'}), 403
        
        note.is_public = False
        db.session.commit()
        
        return jsonify({'message': 'Note is now private'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/public/<public_id>', methods=['GET'])
def get_public_note(public_id):
    """Get a publicly shared note by its public ID"""
    note = Note.query.filter_by(public_id=public_id, is_public=True).first_or_404()
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>/sharing', methods=['GET'])
@login_required
def get_note_sharing_info(note_id):
    """Get sharing information for a note"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        # Check if user owns the note
        if note.user_id != current_user.id:
            return jsonify({'error': 'You can only view sharing info for your own notes'}), 403
        
        return jsonify(note.to_dict(include_sharing=True))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

