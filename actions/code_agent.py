import os
import sys
import subprocess
import logging
import re
from google import genai
import config

logger = logging.getLogger("VoiceAssistant.CodeAgent")

# Path to the generated script in the project root
GENERATED_CODE_PATH = os.path.join(config.BASE_DIR, "generated_code.py")

# Risky imports or execution patterns to screen for
RISKY_PATTERNS = [
    r"os\.remove", r"os\.rmdir", r"os\.unlink", r"os\.system",
    r"shutil\.rmtree", r"pathlib.*\.unlink",
    r"socket", r"requests\b", r"urllib", r"http\.client", r"aiohttp",
    r"subprocess", r"winreg", r"ctypes", r"del\b.*file"
]

def generate_code(user_prompt: str) -> tuple[bool, str]:
    """
    Sends the user prompt to Gemini to generate Python code.
    Extracts the python script and writes it to generated_code.py.
    Returns (success, code_string).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        msg = "GEMINI_API_KEY is not configured. Cannot perform code generation."
        logger.error(msg)
        return False, msg

    try:
        client = genai.Client(api_key=api_key)
        
        system_prompt = (
            "You are a helpful Python code generator. Generate a clean, complete, and correct Python script based on the following user request.\n"
            "Your output must follow these rules strictly:\n"
            "1. Output ONLY the raw Python code block enclosed within ```python and ```.\n"
            "2. Do not include any introductory or concluding text, explanations, or remarks outside of the code block.\n"
            "3. Make sure the code runs independently and prints its outputs clearly.\n\n"
            f"User request: \"{user_prompt}\""
        )
        
        logger.info(f"Calling Gemini to generate code for prompt: '{user_prompt}'")
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=system_prompt
        )
        
        response_text = response.text.strip()
        
        # Extract content between ```python and ```
        code_match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
        
        if code_match:
            code_content = code_match.group(1).strip()
        else:
            # Fallback if the model didn't format it as a markdown code block but sent code directly
            code_content = response_text
            
        # Save to file
        with open(GENERATED_CODE_PATH, "w", encoding="utf-8") as f:
            f.write(code_content)
            
        logger.info(f"Generated code written to {GENERATED_CODE_PATH}")
        return True, code_content

    except Exception as e:
        msg = f"Failed to generate code: {e}"
        logger.error(msg)
        return False, msg

import ast

DANGEROUS_MODULES = {
    "os", "sys", "subprocess", "shutil", "ctypes", "winreg",
    "socket", "urllib", "requests", "aiohttp", "http", "builtins"
}

DANGEROUS_FUNCTIONS = {
    "eval", "exec", "__import__", "compile", "open", "getattr", "setattr", "delattr"
}

def inspect_code_safety(code_str: str) -> bool:
    """
    Parses and scans generated Python code using AST to detect unsafe modules,
    builtin overrides, dangerous function calls, or filesystem mutation attempts.
    Returns True if the code appears safe, and False if potential risks exist.
    """
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        logger.warning(f"Generated code failed AST syntax parsing: {e}")
        return False

    for node in ast.walk(tree):
        # 1. Inspect imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_root = alias.name.split('.')[0].lower()
                if mod_root in DANGEROUS_MODULES:
                    logger.warning(f"AST Safety Violation: Disallowed module import '{alias.name}'")
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_root = node.module.split('.')[0].lower()
                if mod_root in DANGEROUS_MODULES:
                    logger.warning(f"AST Safety Violation: Disallowed module import from '{node.module}'")
                    return False

        # 2. Inspect dangerous builtin/function calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_FUNCTIONS:
                    logger.warning(f"AST Safety Violation: Disallowed function call '{node.func.id}'")
                    return False
            elif isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr.lower()
                if attr_name in {"remove", "rmtree", "unlink", "system", "popen", "spawn", "exec", "__subclasses__"}:
                    logger.warning(f"AST Safety Violation: Disallowed attribute invocation '{attr_name}'")
                    return False

    logger.info("Code passed AST risk inspection. No security violations detected.")
    return True

def execute_generated_code() -> tuple[bool, str]:
    """
    Executes the generated python file in a subprocess.
    Returns (success, console_output).
    """
    if not os.path.exists(GENERATED_CODE_PATH):
        return False, "No generated code file found to execute."

    logger.info(f"Executing generated script: {GENERATED_CODE_PATH}")
    try:
        # Run subprocess with a 30 second timeout to prevent infinite loops
        result = subprocess.run(
            [sys.executable, GENERATED_CODE_PATH],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        stdout_output = result.stdout or ""
        stderr_output = result.stderr or ""
        
        combined_output = stdout_output
        if stderr_output:
            combined_output += f"\nErrors:\n{stderr_output}"
            
        success = result.returncode == 0
        logger.info(f"Subprocess completed with returncode: {result.returncode}")
        
        return success, combined_output.strip()

    except subprocess.TimeoutExpired:
        logger.error("Subprocess execution timed out (limit: 30s).")
        return False, "Execution failed: The code execution timed out after 30 seconds."
    except Exception as e:
        logger.error(f"Error running subprocess: {e}")
        return False, f"Execution failed: {e}"

def fix_code_with_ai(user_prompt: str, failed_code: str, error_message: str) -> tuple[bool, str]:
    """
    Sends the failed code, original user prompt, and the error traceback to Gemini
    to request a corrected version.
    Returns (success, fixed_code_string).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        msg = "GEMINI_API_KEY is not configured. Cannot perform self-fixing."
        logger.error(msg)
        return False, msg

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = (
            "You are a helpful Python code debugger and generator.\n"
            "The Python code you previously generated failed to run correctly.\n\n"
            f"Original User Request: \"{user_prompt}\"\n\n"
            f"Failed Code:\n```python\n{failed_code}\n```\n\n"
            f"Execution Error Output:\n```\n{error_message}\n```\n\n"
            "Analyze the error, fix the bug, and provide a corrected version of the script.\n"
            "Your output must follow these rules strictly:\n"
            "1. Output ONLY the raw Python code block enclosed within ```python and ```.\n"
            "2. Do not include any introductory or concluding text, explanations, or remarks outside of the code block.\n"
            "3. Make sure the code runs independently, handles exceptions where necessary, and prints its outputs clearly."
        )
        
        logger.info("Calling Gemini to fix code error...")
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt
        )
        
        response_text = response.text.strip()
        
        # Extract content between ```python and ```
        code_match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
        
        if code_match:
            code_content = code_match.group(1).strip()
        else:
            code_content = response_text
            
        logger.info("Successfully received fixed code from Gemini.")
        return True, code_content

    except Exception as e:
        msg = f"Failed to generate fix: {e}"
        logger.error(msg)
        return False, msg
