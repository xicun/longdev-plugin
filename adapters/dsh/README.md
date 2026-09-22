# dsh adapter

Use [INSTALL.md](../../INSTALL.md). This wrapper delegates to the shared installer, preserves the complete bundle and creates thin discovery entries.

```powershell
./adapters/dsh/install-dsh.ps1 -Project D:/path/to/project
./adapters/dsh/install-dsh.ps1 -Project D:/path/to/project -Check
```

Requires Python 3.9+. Existing unknown or edited skills are preserved. Profiles must enable the filesystem skill provider.
