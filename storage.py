import json
import os
import random
import datetime
import uuid
from config import TASKS_FILE, DATA_DIR, ADMIN_IDS

USERS_DIR = os.path.join(DATA_DIR, "users")

def init_storage():
    """Ensures data directories exist."""
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)

    if not os.path.exists(TASKS_FILE):
        # Initial sample tasks
        initial_tasks = [
            "Сделать 50 отжиманий",
            "Прочитать 20 страниц книги",
            "Выучить 10 новых слов на английском",
            "Написать план на неделю",
            "Создать мини-проект за 2 часа"
        ]
        save_tasks(initial_tasks)

def load_json(filepath, default=None):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_tasks():
    return load_json(TASKS_FILE, [])

def save_tasks(tasks):
    save_json(TASKS_FILE, tasks)

# --- User Specific Helpers ---

def get_user_dir(user_id):
    path = os.path.join(USERS_DIR, str(user_id))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def get_user_profile_file(user_id):
    return os.path.join(get_user_dir(user_id), "profile.json")

def get_user_assignments_file(user_id):
    return os.path.join(get_user_dir(user_id), "assignments.json")

def get_user_confirmations_file(user_id):
    return os.path.join(get_user_dir(user_id), "confirmations.json")

# --- User Management ---

def add_user(user_data):
    user_id = user_data['id']
    profile_file = get_user_profile_file(user_id)
    
    if os.path.exists(profile_file):
        return False # Already exists
        
    # Auto-admin check
    if user_id in ADMIN_IDS:
        user_data['is_admin'] = True
    
    save_json(profile_file, user_data)
    
    # Init other files
    save_json(get_user_assignments_file(user_id), [])
    save_json(get_user_confirmations_file(user_id), [])
    
    return True

def get_user_profile(user_id):
    return load_json(get_user_profile_file(user_id), {})

def get_all_user_ids():
    """Returns a list of all registered user IDs."""
    if not os.path.exists(USERS_DIR):
        return []
    
    user_ids = []
    for item in os.listdir(USERS_DIR):
        if os.path.isdir(os.path.join(USERS_DIR, item)):
            try:
                user_ids.append(int(item))
            except ValueError:
                pass
    return user_ids

# --- Assignments ---

def assign_next_task(user_id):
    """Assigns the next sequential task to the user if eligible."""
    tasks = get_tasks()
    if not tasks:
        return None

    assignments_file = get_user_assignments_file(user_id)
    assignments = load_json(assignments_file, [])
    
    # 1. Check if user has ANY pending assignment
    pending_assignment = next((a for a in assignments if a['status'] == 'pending'), None)
    
    if pending_assignment:
        return pending_assignment

    # 2. If no pending assignment, find next task
    completed_count = sum(1 for a in assignments if a['status'] == 'completed')
    
    if completed_count >= len(tasks):
        # All tasks completed
        return {"task": "Ты прошел все испытания. Жди новых.", "status": "completed", "date": datetime.date.today().isoformat()}
    
    next_task_text = tasks[completed_count]
    
    new_assignment = {
        "user_id": user_id,
        "task": next_task_text,
        "date": datetime.date.today().isoformat(),
        "status": "pending"
    }
    
    assignments.append(new_assignment)
    save_json(assignments_file, assignments)
    return new_assignment

def get_user_task(user_id):
    """Returns the current active assignment for the user."""
    assignments = load_json(get_user_assignments_file(user_id), [])
    if not assignments:
        return None
    return assignments[-1]

def update_assignment_status(user_id, task_text, status):
    assignments_file = get_user_assignments_file(user_id)
    assignments = load_json(assignments_file, [])
    
    for assignment in reversed(assignments):
        if assignment['task'] == task_text:
            assignment['status'] = status
            save_json(assignments_file, assignments)
            return True
    return False

# --- Confirmations ---

def create_confirmation(user_id, task_text, proof_type, proof_data):
    confirmations_file = get_user_confirmations_file(user_id)
    confirmations = load_json(confirmations_file, [])
    
    confirmation_id = str(uuid.uuid4())[:8] # Short ID for callbacks
    
    new_conf = {
        "id": confirmation_id,
        "user_id": user_id,
        "task": task_text,
        "proof_type": proof_type,
        "proof_data": proof_data,
        "status": "pending",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    confirmations.append(new_conf)
    save_json(confirmations_file, confirmations)
    return confirmation_id

def get_confirmation(user_id, confirmation_id):
    confirmations = load_json(get_user_confirmations_file(user_id), [])
    for conf in confirmations:
        if conf['id'] == confirmation_id:
            return conf
    return None

def update_confirmation_status(user_id, confirmation_id, status, admin_id):
    confirmations_file = get_user_confirmations_file(user_id)
    confirmations = load_json(confirmations_file, [])
    
    for conf in confirmations:
        if conf['id'] == confirmation_id:
            conf['status'] = status
            conf['admin_id'] = admin_id
            conf['processed_at'] = datetime.datetime.now().isoformat()
            save_json(confirmations_file, confirmations)
            return conf
    return None

def has_pending_confirmation(user_id, task_text):
    confirmations = load_json(get_user_confirmations_file(user_id), [])
    for conf in confirmations:
        if conf['task'] == task_text and conf['status'] == 'pending':
            return True
    return False
