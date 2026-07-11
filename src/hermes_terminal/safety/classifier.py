"""
Command safety classification and approval system
"""

import re
from ..models import CommandRisk, Command


class SafetyClassifier:
    """Classifies commands by risk level"""
    
    # Safe commands - read-only, informational only
    SAFE_PATTERNS = [
        r"^pwd$",
        r"^ls(\s|$)",
        r"^cat(\s|$)",
        r"^head(\s|$)",
        r"^tail(\s|$)",
        r"^grep(\s|$)",
        r"^find(\s|$)",
        r"^df(\s|$)",
        r"^free(\s|$)",
        r"^uname(\s|$)",
        r"^ip\s+addr",
        r"^systemctl\s+status",
        r"^journalctl",
        r"^apt-cache",
        r"^pvesm\s+status",
        r"^qm\s+config",
        r"^qm\s+status",
        r"^lvs(\s|$)",
        r"^vgs(\s|$)",
        r"^pvs(\s|$)",
        r"^lsblk(\s|$)",
        r"^whoami(\s|$)",
        r"^id(\s|$)",
        r"^date(\s|$)",
        r"^uptime(\s|$)",
        r"^ps(\s|$)",
        r"^top(\s|$)",
        r"^htop(\s|$)",
        r"^netstat(\s|$)",
        r"^ss(\s|$)",
        r"^dig(\s|$)",
        r"^nslookup(\s|$)",
        r"^ping(\s|$)",
        r"^traceroute(\s|$)",
        r"^stat(\s|$)",
        r"^file(\s|$)",
        r"^wc(\s|$)",
    ]
    
    # Caution commands - modify system but reversible
    CAUTION_PATTERNS = [
        r"^apt\s+update",
        r"^apt\s+install",
        r"^apt\s+remove",
        r"^apt\s+upgrade",
        r"^apt-get\s+(update|install|remove|upgrade)",
        r"^systemctl\s+(start|stop|restart|enable|disable|daemon-reload)",
        r"^chmod(\s|$)",
        r"^chown(\s|$)",
        r"^firewall-cmd",
        r"^ufw(\s|$)",
        r"^useradd(\s|$)",
        r"^userdel(\s|$)",
        r"^usermod(\s|$)",
        r"^groupadd(\s|$)",
        r"^groupdel(\s|$)",
        r"^sshd(\s|$)",
        r"^qm\s+set",
        r"^qm\s+start",
        r"^qm\s+stop",
        r"^qm\s+reboot",
        r"^mkdir(\s|$)",
        r"^touch(\s|$)",
        r"^cp(\s|$)",
        r"^mv(\s|$)",
        r"^sed(\s|$)",
        r"^awk(\s|$)",
        r"^nano(\s|$)",
        r"^vi(\s|$)",
        r"^vim(\s|$)",
        r"^scp(\s|$)",
    ]
    
    # Dangerous commands - destructive or critical
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf",
        r"^dd(\s|$)",
        r"^mkfs",
        r"^wipefs",
        r"^fdisk",
        r"^parted",
        r"^lvremove",
        r"^vgremove",
        r"^pvremove",
        r"^qm\s+destroy",
        r"^qm\s+delete",
        r"^pvesm\s+remove",
        r"^userdel\s+-r",
        r"^shutdown",
        r"^reboot",
        r"^halt",
        r"^iptables\s+-P",
        r"^firewall-cmd\s+-P",
        r"^format\s+",
        r"^repartition",
    ]
    
    # Completely blocked patterns
    BLOCKED_PATTERNS = [
        r"base64\s+-d",
        r"\|.*base64\s+-d",
        r"eval\s+",
        r"exec\s+",
        r"source\s+",
        r"\|\s*sh\s*$",
        r"\|\s*bash\s*$",
        r"\|\s*python",
        r"\|\s*perl",
        r";\s*rm\s+",
        r"&&\s*rm\s+",
        r"\|\|\s*rm\s+",
        r";\s*mkfs",
        r";\s*dd",
        r">\s*/dev/sda",
        r">\s*/dev/hda",
    ]
    
    @staticmethod
    def classify(command: str) -> tuple[CommandRisk, str]:
        """
        Classify a command by risk level.
        
        Returns:
            Tuple of (CommandRisk, explanation)
        """
        # Clean up the command
        cmd = command.strip()

        for pattern in SafetyClassifier.BLOCKED_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return CommandRisk.BLOCKED, f"Command contains blocked pattern: {pattern}"

        # Classify each shell-chain segment independently so a harmless first
        # command cannot hide a later mutation (for example, ``ls && reboot``).
        if re.search(r"(?:&&|\|\||[;|])", cmd):
            segments = [part.strip() for part in re.split(r"&&|\|\||[;|]", cmd) if part.strip()]
            results = [SafetyClassifier.classify(part) for part in segments]
            priority = {
                CommandRisk.SAFE: 0,
                CommandRisk.CAUTION: 1,
                CommandRisk.DANGER: 2,
                CommandRisk.BLOCKED: 3,
            }
            return max(results, key=lambda item: priority[item[0]])

        # sudo changes identity, not the underlying command risk.
        cmd = re.sub(r"^sudo(?:\s+-\S+)*\s+", "", cmd, flags=re.IGNORECASE)
        
        # Check for blocked patterns first
        for pattern in SafetyClassifier.BLOCKED_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return CommandRisk.BLOCKED, f"Command contains blocked pattern: {pattern}"
        
        # Check for dangerous commands
        for pattern in SafetyClassifier.DANGEROUS_PATTERNS:
            if re.match(pattern, cmd, re.IGNORECASE):
                return CommandRisk.DANGER, f"Dangerous command: {pattern}"
        
        # Check for caution commands
        for pattern in SafetyClassifier.CAUTION_PATTERNS:
            if re.match(pattern, cmd, re.IGNORECASE):
                return CommandRisk.CAUTION, f"Caution command: {pattern}"
        
        # Check for safe commands
        for pattern in SafetyClassifier.SAFE_PATTERNS:
            if re.match(pattern, cmd, re.IGNORECASE):
                return CommandRisk.SAFE, "Safe read-only command"
        
        # Default to caution for unknown commands
        return CommandRisk.CAUTION, "Unknown command - requires approval"
    
    @staticmethod
    def requires_approval(risk: CommandRisk) -> bool:
        """Check if a command requires approval"""
        return risk in [CommandRisk.CAUTION, CommandRisk.DANGER]
    
    @staticmethod
    def is_blocked(risk: CommandRisk) -> bool:
        """Check if a command is completely blocked"""
        return risk == CommandRisk.BLOCKED
    
    @staticmethod
    def requires_confirmation_prefix(risk: CommandRisk, confirmation_prefix: str = "CONFIRM") -> bool:
        """Check if a command requires explicit confirmation text"""
        return risk == CommandRisk.DANGER


class ApprovalGate:
    """Manages command approval workflow"""
    
    def __init__(self, dangerous_confirmation_prefix: str = "CONFIRM"):
        self.dangerous_confirmation_prefix = dangerous_confirmation_prefix
        self.pending_approvals: dict[str, Command] = {}
    
    def request_approval(self, command_id: str, command: Command) -> bool:
        """
        Register a command for approval.
        
        Returns: True if immediate approval granted, False if manual approval needed
        """
        if not SafetyClassifier.requires_approval(command.risk_level):
            return True
        
        self.pending_approvals[command_id] = command
        return False
    
    def get_approval_prompt(self, command: Command, target_host: str) -> str:
        """Generate an approval prompt for the user"""
        prompt = f"""
[{command.risk_level.value.upper()}] Approval Required

Target Host: {target_host}
Command: {command.command}

{command.explanation}

Approve? (yes/no): """
        return prompt
    
    def validate_dangerous_confirmation(
        self, command: Command, target_host: str, user_input: str
    ) -> bool:
        """
        Validate dangerous command confirmation format.
        
        Format: CONFIRM <host> <short-action>
        Examples: CONFIRM core reboot, CONFIRM kali delete-directory
        """
        if command.risk_level != CommandRisk.DANGER:
            return True
        
        parts = user_input.strip().split()
        if len(parts) < 3:
            return False
        
        if parts[0] != self.dangerous_confirmation_prefix:
            return False
        
        if parts[1] != target_host:
            return False
        
        return True
