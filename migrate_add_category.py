#!/usr/bin/env python3
"""
Migration script to add category column to existing notes table
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
        
        # Check if category column already exists
        cursor.execute("PRAGMA table_info(note)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'category' not in columns:
            print("Adding category column to note table...")
            cursor.execute("ALTER TABLE note ADD COLUMN category VARCHAR(100) DEFAULT 'General'")
            
            # Update existing notes to have 'General' category
            cursor.execute("UPDATE note SET category = 'General' WHERE category IS NULL")
            
            conn.commit()
            print("Migration completed successfully!")
        else:
            print("Category column already exists. No migration needed.")
        
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