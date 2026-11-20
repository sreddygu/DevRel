# IQ8 SSH Runbook

This project uses an interactive-first SSH workflow for the IQ8 board. Keep
the board address, passwords, private keys, and key passphrases outside this
repository.

## Why this workflow exists

The device can accept an interactive SSH login while direct non-interactive
automation is unreliable. The proven workaround is to open one authenticated
ControlMaster connection, then reuse its socket for subsequent commands and
file transfers.

## Windows host with WSL procedure

On this Windows host, OpenSSH cannot create the Unix-domain socket required by
`ControlMaster` (`getsockname failed: Not a socket`). Use the installed Ubuntu
WSL distribution for the persistent connection instead.

Set the host and local private-key path only in the current PowerShell shell:

```powershell
$iq8Host = '<IQ8 host or address>'
$iq8Key = "$HOME\.ssh\iq8_ed25519"
```

Copy the local key into WSL with owner-only permissions. This does not copy it
into the project or a note:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc `
  "install -d -m 700 ~/.ssh && install -m 600 /mnt/c/Users/$env:USERNAME/.ssh/iq8_ed25519 ~/.ssh/iq8_ed25519"
```

First establish the WSL master session interactively. Enter the board password
if prompted; do not place it in a command, note, or script:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc `
  "ssh -M -S ~/.ssh/cm-iq8 -o ControlPersist=30m -i ~/.ssh/iq8_ed25519 root@$iq8Host"
```

After reaching the board shell, type `exit`. The master remains available for
its configured persistence interval. Reuse it through WSL for safe
non-interactive checks:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc `
  "ssh -S ~/.ssh/cm-iq8 root@$iq8Host 'hostname; uname -sm'"
```

The automation agent can use this same WSL socket for board commands and file
transfers. Close it when the task is complete:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc `
  "ssh -S ~/.ssh/cm-iq8 -O exit root@$iq8Host"
```

## Board-side key verification

When logged in interactively, verify the key file and SSH daemon policy before
changing any permissions or configuration:

```sh
namei -l /root/.ssh/authorized_keys
sshd -T | grep -E 'authorizedkeysfile|pubkeyauthentication|authenticationmethods|permitrootlogin'
```

The expected modes are directory `0700` and `authorized_keys` `0600`. Do not
store the public key itself in this repository; compare fingerprints locally
with `ssh-keygen -lf` instead.

## ACE-Step board gate

For the current range-preserving candidate, stage only the candidate DLC and
reuse the board's already verified raw inputs. Run HTP with native float32 I/O
and `--set_output_tensors` for these tensors before judging the final output:

- `/block/attn/MatMul_output_0`
- `/block/attn/MatMul_1_output_0`

Compare them with the paired host QAIRT CPU dumps in
`data/iq8/block0_10s_fp32_attn_scaled_16_rewrite/host_qairt_cpu_intermediates/`.
