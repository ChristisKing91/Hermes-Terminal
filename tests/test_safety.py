"""
Tests for safety classifier and approval gate
"""

from hermes_terminal.safety.classifier import SafetyClassifier, ApprovalGate
from hermes_terminal.models import CommandRisk, Command


class TestSafetyClassifier:
    """Test command safety classification"""

    def test_safe_commands(self):
        """Test safe command classification"""
        safe_commands = [
            "ls -la",
            "pwd",
            "cat /etc/os-release",
            "grep -r pattern .",
            "df -h",
            "ps aux",
        ]

        for cmd in safe_commands:
            risk, _ = SafetyClassifier.classify(cmd)
            assert risk == CommandRisk.SAFE, f"Command {cmd} should be SAFE"

    def test_caution_commands(self):
        """Test caution command classification"""
        caution_commands = [
            "apt update",
            "chmod 755 file.txt",
            "systemctl start nginx",
            "useradd newuser",
        ]

        for cmd in caution_commands:
            risk, _ = SafetyClassifier.classify(cmd)
            assert risk == CommandRisk.CAUTION, f"Command {cmd} should be CAUTION"

    def test_danger_commands(self):
        """Test dangerous command classification"""
        danger_commands = [
            "rm -rf /var",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "sudo rm -rf /var",
            "ls && reboot",
        ]

        for cmd in danger_commands:
            risk, _ = SafetyClassifier.classify(cmd)
            assert risk == CommandRisk.DANGER, f"Command {cmd} should be DANGER"

    def test_blocked_commands(self):
        """Test blocked command classification"""
        blocked_commands = [
            "echo secret | base64 -d",
            "eval user_input",
            "cat file | sh",
        ]

        for cmd in blocked_commands:
            risk, _ = SafetyClassifier.classify(cmd)
            assert risk == CommandRisk.BLOCKED, f"Command {cmd} should be BLOCKED"

    def test_requires_approval(self):
        """Test approval requirement logic"""
        assert not SafetyClassifier.requires_approval(CommandRisk.SAFE)
        assert SafetyClassifier.requires_approval(CommandRisk.CAUTION)
        assert SafetyClassifier.requires_approval(CommandRisk.DANGER)
        assert not SafetyClassifier.requires_approval(CommandRisk.BLOCKED)

    def test_is_blocked(self):
        """Test blocked command detection"""
        assert not SafetyClassifier.is_blocked(CommandRisk.SAFE)
        assert not SafetyClassifier.is_blocked(CommandRisk.CAUTION)
        assert not SafetyClassifier.is_blocked(CommandRisk.DANGER)
        assert SafetyClassifier.is_blocked(CommandRisk.BLOCKED)


class TestApprovalGate:
    """Test approval gate workflow"""

    def test_approval_gate_safe_command(self):
        """Test approval gate for safe commands"""
        gate = ApprovalGate()
        cmd = Command(
            command="ls",
            risk_level=CommandRisk.SAFE,
            host="localhost",
        )

        # Safe commands should be immediately approved
        approved = gate.request_approval("cmd1", cmd)
        assert approved is True

    def test_approval_gate_caution_command(self):
        """Test approval gate for caution commands"""
        gate = ApprovalGate()
        cmd = Command(
            command="apt update",
            risk_level=CommandRisk.CAUTION,
            host="localhost",
        )

        # Caution commands should require approval
        approved = gate.request_approval("cmd1", cmd)
        assert approved is False
        assert "cmd1" in gate.pending_approvals

    def test_approval_gate_dangerous_confirmation(self):
        """Test dangerous command confirmation format"""
        gate = ApprovalGate()
        cmd = Command(
            command="rm -rf /var",
            risk_level=CommandRisk.DANGER,
            host="core",
        )

        # Valid confirmation
        valid = gate.validate_dangerous_confirmation(cmd, "core", "CONFIRM core delete-var")
        assert valid is True

        # Invalid confirmation - wrong prefix
        invalid = gate.validate_dangerous_confirmation(cmd, "core", "YES core delete-var")
        assert invalid is False

        # Invalid confirmation - wrong host
        invalid = gate.validate_dangerous_confirmation(cmd, "core", "CONFIRM kali delete-var")
        assert invalid is False
