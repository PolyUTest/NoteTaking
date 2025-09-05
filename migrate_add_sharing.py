#!/usr/bin/env python3
"""
Migration script to add sharing fields and user authentication
"""
import os
import sys
import sqlite3

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), 'src', 'database', 'app.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database...")
        return
    
    print(f"Migrating database at {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current table structure
        cursor.execute("PRAGMA table_info(note)")
        note_columns = [column[1] for column in cursor.fetchall()]
        
        # Add sharing fields to note table if they don't exist
        if 'user_id' not in note_columns:
            print("Adding user_id column to note table...")
            cursor.execute("ALTER TABLE note ADD COLUMN user_id INTEGER")
        
        if 'is_public' not in note_columns:
            print("Adding is_public column to note table...")
            cursor.execute("ALTER TABLE note ADD COLUMN is_public BOOLEAN DEFAULT 0")
        
        if 'public_id' not in note_columns:
            print("Adding public_id column to note table...")
            cursor.execute("ALTER TABLE note ADD COLUMN public_id VARCHAR(50)")
        
        # Check if user table exists and update it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        user_table_exists = cursor.fetchone() is not None
        
        if user_table_exists:
            cursor.execute("PRAGMA table_info(user)")
            user_columns = [column[1] for column in cursor.fetchall()]
            
            if 'password_hash' not in user_columns:
                print("Adding password_hash column to user table...")
                cursor.execute("ALTER TABLE user ADD COLUMN password_hash VARCHAR(120)")
            
            if 'created_at' not in user_columns:
                print("Adding created_at column to user table...")
                cursor.execute("ALTER TABLE user ADD COLUMN created_at DATETIME")
                cursor.execute("UPDATE user SET created_at = datetime('now') WHERE created_at IS NULL")
        else:
            print("Creating user table...")
            cursor.execute('''
                CREATE TABLE user (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(120),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Create note_shares table for many-to-many relationship
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='note_shares'")
        note_shares_exists = cursor.fetchone() is not None
        
        if not note_shares_exists:
            print("Creating note_shares table...")
            cursor.execute('''
                CREATE TABLE note_shares (
                    note_id INTEGER,
                    user_id INTEGER,
                    permission VARCHAR(20) DEFAULT 'read',
                    shared_at DATETIME,
                    PRIMARY KEY (note_id, user_id),
                    FOREIGN KEY (note_id) REFERENCES note (id),
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            ''')
        
        conn.commit()
        print("Migration completed successfully!")
        
        conn.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("Database migration completed.")
    else:
        print("Database migration failed.")
        sys.exit(1)