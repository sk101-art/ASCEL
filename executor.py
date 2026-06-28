import os
import shlex
import subprocess
import sqlite3
import git
import sys
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "ascel.db")
REPO_PATH = os.path.dirname(__file__)

class HealingEngine:
    def __init__(self):
        self.repo = git.Repo(REPO_PATH, search_parent_directories=True)
        
    def evaluate_permission(self, cmd_str: str, trust_tier: str) -> bool:
        """
        Evaluate if a command is allowed based on the trust tier.
        """
        read_only_cmds = ['cat', 'ls', 'echo', 'pwd']
        parsed = shlex.split(cmd_str)
        if not parsed:
            return False
            
        base_cmd = parsed[0]
        
        if base_cmd in read_only_cmds:
            return True
            
        if trust_tier == 'Silent Auto-Heal':
            return True
            
        if trust_tier in ['Suggest-Only', 'Auto-Apply w/ Notify']:
            # Block and prompt
            while True:
                sys.stdout.write(f"\n[PERMISSION GATE] Execute this fix? (`{cmd_str}`) [Y/N]: ")
                sys.stdout.flush()
                resp = input().strip().upper()
                if resp == 'Y':
                    return True
                elif resp == 'N':
                    return False
        
        return False

    def run_command(self, cmd_str: str, timeout: int = 15) -> Optional[int]:
        """
        Run command safely using subprocess with a hard timeout.
        """
        parsed_cmd = shlex.split(cmd_str)
        try:
            print(f"Executing: {cmd_str}")
            result = subprocess.run(
                parsed_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=True if os.name == 'nt' else False
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            print(f"Timeout expired ({timeout}s) for command: {cmd_str}")
            return -1
        except Exception as e:
            print(f"Execution error: {e}")
            return -1

    def verify_fix(self, probe_command: str, expected_exit_code: int = 0) -> bool:
        """
        Run verification probe immediately after remediation.
        """
        print(f"Running verification probe: {probe_command}")
        returncode = self.run_command(probe_command)
        return returncode == expected_exit_code

    def rollback(self, skill_id: str):
        """
        Perform a git rollback and penalize skill in database.
        """
        print("\n=== CAUSAL FAILURE AUDIT LOG ===")
        print("Failure detected during verification probe.")
        print("Initiating rollback workflow...")
        
        # Git Rollback
        try:
            self.repo.git.reset('--hard')
            print("Action: `git reset --hard` executed successfully.")
        except Exception as e:
            print(f"Action Failed: Could not execute git reset. Error: {e}")
        
        # Database Penalty
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE skills SET confidence = confidence * 0.5 WHERE id = ?",
                (skill_id,)
            )
            conn.commit()
            conn.close()
            print(f"Action: Demoted confidence score for skill {skill_id} in database (multiplied by 0.5).")
        except Exception as e:
            print(f"Action Failed: Database update failed. Error: {e}")
            
        print("================================\n")

    def execute_skill(self, skill_id: str, remediation_cmd: str, probe_cmd: str, trust_tier: str):
        """
        End-to-end execution of a skill payload.
        """
        allowed = self.evaluate_permission(remediation_cmd, trust_tier)
        if not allowed:
            print("Execution aborted by user.")
            return False
            
        # Execute remediation
        self.run_command(remediation_cmd)
        
        # Verify
        is_fixed = self.verify_fix(probe_cmd)
        
        if not is_fixed:
            self.rollback(skill_id)
            return False
            
        print("Verification successful! Fix applied permanently.")
        return True

if __name__ == '__main__':
    from unittest.mock import patch
    
    print("Initializing Healing Engine test...")
    engine = HealingEngine()
    
    test_skill_id = 'test_skill_123'
    try:
        c = sqlite3.connect(DB_PATH)
        c.execute("INSERT OR IGNORE INTO skills (id, title, confidence) VALUES (?, ?, ?)", (test_skill_id, "Test Skill", 1.0))
        c.commit()
        c.close()
    except Exception as e:
        print(f"Setup error: {e}")
    
    with patch('builtins.input', return_value='Y'):
        engine.execute_skill(
            skill_id=test_skill_id,
            remediation_cmd="echo '#include <stdbool.h>' >> main.c",
            probe_cmd="cat missing_file.txt",
            trust_tier='Auto-Apply w/ Notify'
        )
