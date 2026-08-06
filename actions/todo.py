import os
import json
import logging
import config

logger = logging.getLogger("VoiceAssistant.Todo")

TODO_FILE_PATH = os.path.join(config.BASE_DIR, "todo_list.json")

def _load_todo_list() -> list:
    if os.path.exists(TODO_FILE_PATH):
        try:
            with open(TODO_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading todo list: {e}")
    return []

def _save_todo_list(todo_list: list) -> bool:
    try:
        with open(TODO_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(todo_list, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving todo list: {e}")
        return False

def add_todo_task(task: str) -> str:
    task = task.strip()
    if not task:
        return "Task description cannot be empty."
    
    todo_list = _load_todo_list()
    todo_list.append({"task": task, "completed": False})
    if _save_todo_list(todo_list):
        return f"Added '{task}' to your to-do list."
    else:
        return "Failed to save the task to your to-do list."

def list_todo_tasks() -> str:
    todo_list = _load_todo_list()
    active_tasks = [item for item in todo_list if not item.get("completed")]
    
    if not active_tasks:
        return "You have no active tasks on your to-do list."
    
    msg = "Here is your to-do list:\n"
    for i, item in enumerate(active_tasks, start=1):
        msg += f"{i}. {item['task']}\n"
    return msg.strip()

def complete_todo_task(target) -> str:
    target_str = str(target).strip().lower()
    if not target_str:
        return "Please specify a task index or description to complete."
        
    todo_list = _load_todo_list()
    active_indices = [i for i, item in enumerate(todo_list) if not item.get("completed")]
    
    if not active_indices:
        return "You have no active tasks to complete."
        
    # Check if target is a number (1-based index of active tasks)
    selected_idx = None
    try:
        idx_val = int(target_str)
        if 1 <= idx_val <= len(active_indices):
            selected_idx = active_indices[idx_val - 1]
    except ValueError:
        pass
        
    # If not a valid index, search by substring match
    if selected_idx is None:
        for idx in active_indices:
            if target_str in todo_list[idx]["task"].lower():
                selected_idx = idx
                break
                
    if selected_idx is not None:
        task_name = todo_list[selected_idx]["task"]
        todo_list[selected_idx]["completed"] = True
        if _save_todo_list(todo_list):
            return f"Marked task '{task_name}' as completed."
        else:
            return "Failed to save the updated to-do list."
            
    return f"Could not find an active task matching '{target}'."

def clear_todo_list() -> str:
    if _save_todo_list([]):
        return "Your to-do list has been cleared."
    else:
        return "Failed to clear the to-do list."
