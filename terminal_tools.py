import subprocess

def run_terminal_command(command: str) -> str:
    print(f"[TOOL] Executing: {command}")
    
    forbidden = ["rm -rf", "format", "del /f", "mkfs", "shutdown"]
    if any(word in command.lower() for word in forbidden):
        return "Error: Command blocked for safety reasons."

    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=180  # 3 minutes for slow scans like Nikto
        )
        
        output = result.stdout if result.stdout else result.stderr
        if not output:
            return "Command executed successfully, but returned no output."
            
        if len(output) > 6000:
            output = output[:6000] + "\n...[Output truncated]"
            
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 3 minutes."
    except Exception as e:
        return f"Error: {str(e)}"