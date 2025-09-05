#!/usr/bin/env python3

"""
Migration script to add is_admin field to user table
"""

import os
import sys
import sqlite3

def migrate_add_admin():
    """Add is_admin column to user table"""
    
    # Database path
    db_path = os.path.join(os.path.dirname(__file__), 'src', 'database', 'app.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if is_admin column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_admin' in columns:
            print("is_admin column already exists!")
            return True
        
        # Add is_admin column with default value False
        print("Adding is_admin column to user table...")
        cursor.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
        
        # Create first admin user if no users exist with admin privileges
        cursor.execute("SELECT COUNT(*) FROM user WHERE is_admin = 1")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            # Make the first user an admin, or create a default admin
            cursor.execute("SELECT id, username FROM user ORDER BY id LIMIT 1")
            first_user = cursor.fetchone()
            
            if first_user:
                cursor.execute("UPDATE user SET is_admin = 1 WHERE id = ?", (first_user[0],))
                print(f"Made user '{first_user[1]}' (ID: {first_user[0]}) an admin")
            else:
                # No users exist, create default admin
                from werkzeug.security import generate_password_hash
                password_hash = generate_password_hash('admin123')
                cursor.execute(
                    "INSERT INTO user (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                    ('admin', 'admin@example.com', password_hash, True)
                )
                print("Created default admin user (username: admin, password: admin123)")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_add_admin()
    sys.exit(0 if success else 1)