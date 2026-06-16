# LaunchPad

Windows connection dashboard for SSH, RDP, and web links with encrypted credential storage.

## Install on this PC

1. Open the LaunchPad project folder
2. Double-click **`build.bat`** (first time only, or after code changes)
3. Double-click **`install.bat`**
4. Launch **LaunchPad** from your Desktop shortcut

## Install on another computer

You do **not** need Python on the other PC. Copy the packaged app:

1. On your dev PC, run **`package.bat`**
2. Copy the **`LaunchPad-Install`** folder to the other PC (USB, OneDrive, zip file, etc.)
3. On the other PC, open that folder and double-click **`install.bat`**
4. Use the Desktop shortcut to launch

**Required files (must stay together):**

| File | Purpose |
|------|---------|
| `LaunchPad.exe` | Main app |
| `ssh_askpass.exe` | Silent SSH passphrase helper (stats + connect) |

**Other PC requirements:**

- Windows 10 or 11 (64-bit)
- **OpenSSH Client** (Settings → Apps → Optional features → OpenSSH Client) for SSH cards
- Optional: **Windows Terminal** for SSH windows

**Moving your cards to the new PC:**

1. Old PC: Admin → **Export Backup** (`.lpb` file)
2. New PC: first-run setup (new master password), then Admin → **Import Backup**
3. Use the **same master password** as when you exported, or import will fail

Your vault database lives at `%APPDATA%\LaunchPad\` — only copy that folder if you want to move the exact same vault **and** you know what you are doing. Export/import backup is safer.

## Install (Desktop) — quick path

1. Open `C:\Users\BrianColley\LaunchPad`
2. Run **`build.bat`** then **`install.bat`**
3. Launch **LaunchPad** from your Desktop shortcut

## First run

1. Create a **master password** (unlocks the vault)
2. Create an **admin password** (add/edit/delete cards)
3. Open **Admin** and add your SSH, RDP, or Web cards

## Features

- Dashboard cards with orange glow on hover
- **20 selectable icons** per card (terminal, server, globe, cloud, etc.)
- **Drag ⋮⋮ handle** to reorder cards on the dashboard
- **Export / Import** encrypted `.lpb` backups from Admin
- Dark / light mode toggle
- SSH via Windows Terminal or `ssh.exe`
- RDP via `mstsc.exe` with stored credentials
- Web links with optional HTTP basic auth
- Encrypted SQLite database at `%APPDATA%\LaunchPad\launchpad.db`

## Rebuild

```bat
build.bat
install.bat
```

## Package for another PC

```bat
package.bat
```

Then copy the `LaunchPad-Install` folder to the other computer and run `install.bat` there.

## Card types

| Type | Fields |
|------|--------|
| SSH | Host, port, username, password or private key |
| RDP | Host, port, username, password |
| Web | URL, optional username/password for basic auth |

**Icons:** Choose from 20 icons in Admin when editing a card.

**Reorder:** Drag the ⋮⋮ handle on a card (visible when viewing All categories with no search filter).

**Backup:** Admin → Export Backup saves an encrypted `.lpb` file. Import requires the same master password used when exporting.

**Note:** SSH passwords are copied to clipboard when launching (Windows limitation). Use SSH keys for one-click login.
