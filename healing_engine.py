import subprocess
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class HealingEngine:
    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def _execute_command(self, cmd: str) -> tuple[bool, str]:
        """Executes a shell command and returns (success, output)."""
        logger.info(f"Executing command: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                logger.info(f"Command succeeded.")
                return True, output
            else:
                logger.error(f"Command failed with code {result.returncode}. Output:\n{output}")
                return False, output
        except subprocess.TimeoutExpired:
            logger.error("Command timed out.")
            return False, "Timeout expired."
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False, str(e)

    def _rollback(self) -> None:
        """Rolls back the workspace using Git."""
        logger.warning("Initiating Git rollback...")
        self._execute_command("git reset --hard")
        self._execute_command("git clean -fd")
        logger.info("Rollback complete.")

    def run_healing_cycle(self, fix_cmd: str, probe_cmd: Optional[str], trust_tier: str) -> Dict[str, Any]:
        """
        Executes the healing cycle based on the trust tier.
        Returns a dictionary with status and output logs.
        """
        if trust_tier == "Suggest-Only":
            logger.info("Trust Tier is 'Suggest-Only'. Blocking execution.")
            return {
                "status": "suggested",
                "fix_cmd": fix_cmd,
                "probe_cmd": probe_cmd,
                "message": "Fix command suggested but not executed due to Trust Tier."
            }

        logger.info(f"Trust Tier is '{trust_tier}'. Proceeding with Auto-Heal.")
        
        # 1. Execute Fix
        fix_success, fix_output = self._execute_command(fix_cmd)
        
        if not fix_success:
            logger.error("Fix failed. Rolling back.")
            self._rollback()
            return {
                "status": "failed",
                "fix_cmd": fix_cmd,
                "fix_output": fix_output,
                "message": "Fix command failed to execute. Rolled back."
            }
            
        # 2. Execute Probe (if any)
        if probe_cmd:
            logger.info(f"Running verification probe: {probe_cmd}")
            probe_success, probe_output = self._execute_command(probe_cmd)
            
            if not probe_success:
                logger.error("Probe failed. Rolling back.")
                self._rollback()
                return {
                    "status": "failed_probe",
                    "fix_cmd": fix_cmd,
                    "fix_output": fix_output,
                    "probe_cmd": probe_cmd,
                    "probe_output": probe_output,
                    "message": "Verification probe failed. Rolled back."
                }
            else:
                logger.info("Probe succeeded!")
                return {
                    "status": "success",
                    "fix_cmd": fix_cmd,
                    "fix_output": fix_output,
                    "probe_cmd": probe_cmd,
                    "probe_output": probe_output,
                    "message": "Fix applied and verified successfully!"
                }
        else:
            logger.info("No probe provided. Assuming fix success.")
            return {
                "status": "success_no_probe",
                "fix_cmd": fix_cmd,
                "fix_output": fix_output,
                "message": "Fix applied successfully (no verification probe provided)."
            }
