# Kali APT repair playbook

This is a review-first playbook. Hermes must not run it without explicit approval on
the `hermes-kali` host. It does not change Proxmox, VM 100, disks, SSH, or networking.

## 1. Inspect (safe)

```bash
cat /etc/os-release
grep -R --line-number --no-messages '^deb ' /etc/apt/sources.list /etc/apt/sources.list.d
apt-cache policy
df -h / /var
```

Expected rolling repository line:

```text
deb http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware
```

## 2. Repair (caution; approval required)

Back up the current file, then replace only `/etc/apt/sources.list`:

```bash
sudo cp --preserve=all /etc/apt/sources.list /etc/apt/sources.list.hermes-backup
printf '%s\n' 'deb http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware' | sudo tee /etc/apt/sources.list
sudo apt update
```

Do not use `apt-key`, disable signature checks, remove unrelated source files, or run
`apt full-upgrade` as part of repository repair.

## 3. Verify (safe)

```bash
apt-cache policy
grep -R --line-number --no-messages '^deb ' /etc/apt/sources.list /etc/apt/sources.list.d
```

Rollback, with approval, is:

```bash
sudo cp --preserve=all /etc/apt/sources.list.hermes-backup /etc/apt/sources.list
sudo apt update
```
