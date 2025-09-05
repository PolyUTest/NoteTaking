from flask import Blueprint, jsonify, request, session
from src.models.note import Note, db
from src.models.user import User
from src.routes.user import login_required, get_current_user, can_access_note, can_modify_note
import uuid

note_bp = Blueprint('note', __name__)

@note_bp.route('/notes', methods=['GET'])
@login_required
def get_notes():
    """Get user's notes (own notes + shared notes)"""
    current_user = get_current_user()
    
    # Get user's own notes and notes shared with them
    own_notes = Note.query.filter_by(user_id=current_user.id).all()
    shared_notes = current_user.shared_notes
    
    # Combine and deduplicate
    all_notes = {note.id: note for note in own_notes + shared_notes}.values()
    notes = sorted(all_notes, key=lambda x: x.updated_at, reverse=True)
    
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
@login_required
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
            user_id=current_user.id
        )
        db.session.add(note)
        db.session.commit()
        return jsonify(note.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
@login_required
def get_note(note_id):
    """Get a specific note by ID"""
    current_user = get_current_user()
    note = Note.query.get_or_404(note_id)
    
    if not can_access_note(current_user, note):
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    """Update a specific note"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        if not can_modify_note(current_user, note):
            return jsonify({'error': 'Permission denied'}), 403
        
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
@login_required
def delete_note(note_id):
    """Delete a specific note"""
    try:
        current_user = get_current_user()
        note = Note.query.get_or_404(note_id)
        
        if not can_modify_note(current_user, note):
            return jsonify({'error': 'Permission denied'}), 403
        
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
@login_required
def search_notes():
    """Search notes by title or content (user's accessible notes only)"""
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    
    if not query and not category:
        return jsonify([])
    
    current_user = get_current_user()
    
    # Get user's own notes and notes shared with them
    own_notes = Note.query.filter_by(user_id=current_user.id)
    shared_note_ids = [note.id for note in current_user.shared_notes]
    shared_notes = Note.query.filter(Note.id.in_(shared_note_ids)) if shared_note_ids else Note.query.filter(False)
    
    # Combine queries
    notes_query = own_notes.union(shared_notes)
    
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
@login_required
def get_categories():
    """Get all unique categories from user's accessible notes"""
    try:
        current_user = get_current_user()
        
        # Get categories from user's own notes
        own_categories = db.session.query(Note.category).filter_by(user_id=current_user.id).distinct()
        
        # Get categories from shared notes
        shared_note_ids = [note.id for note in current_user.shared_notes]
        shared_categories = db.session.query(Note.category).filter(Note.id.in_(shared_note_ids)).distinct() if shared_note_ids else db.session.query(Note.category).filter(False).distinct()
        
        # Combine and get unique categories
        all_categories = set()
        for cat in own_categories.all():
            if cat[0]:
                all_categories.add(cat[0])
        for cat in shared_categories.all():
            if cat[0]:
                all_categories.add(cat[0])
        
        category_list = sorted(list(all_categories))
        return jsonify(category_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/by-category/<category>', methods=['GET'])
@login_required
def get_notes_by_category(category):
    """Get notes by category (user's accessible notes only)"""
    try:
        current_user = get_current_user()
        
        # Get user's own notes and notes shared with them
        own_notes = Note.query.filter_by(category=category, user_id=current_user.id).all()
        shared_notes = [note for note in current_user.shared_notes if note.category == category]
        
        # Combine and deduplicate
        all_notes = {note.id: note for note in own_notes + shared_notes}.values()
        notes = sorted(all_notes, key=lambda x: x.updated_at, reverse=True)
            
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

