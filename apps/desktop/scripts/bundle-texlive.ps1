# Builds the TeX distribution the Windows desktop app ships with.
#
#   apps/desktop/scripts/bundle-texlive.ps1 [-Destination <path>]
#
# The Windows half of scripts/bundle-texlive.sh, and the two have to stay in
# step: same TinyTeX, same package list, same reasons. See that script for why
# the engine must be pdfTeX and why the platform directory under bin/ is left
# exactly where it is.
#
# NOTE: written against TinyTeX's documented Windows installer but never run —
# there is no Windows machine in this project's history. The first CI run on a
# windows runner is the first time this executes.

[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $PSScriptRoot "..\resources\texlive")
)

$ErrorActionPreference = "Stop"

# Exactly the list apps/api/Dockerfile installs, and the same list the unix
# script uses. They typeset the same document with the same preamble.
$Packages = @(
    "tools"
    "preprint"
    "titlesec"
    "marvosym"
    "enumitem"
    "fancyhdr"
    "babel-english"
    "fontawesome5"
    "xcolor"
)

if (Test-Path (Join-Path $Destination "bin")) {
    $existing = Get-ChildItem -Path (Join-Path $Destination "bin") -Recurse -Filter "pdflatex.exe" -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "TeX already bundled at $Destination"
        exit 0
    }
}

$workspace = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $workspace | Out-Null

try {
    Write-Host "Installing TinyTeX into a scratch directory..."
    # TINYTEX_DIR keeps the install out of the user profile, the same as
    # TINYTEX_DIR does on unix. Without it the installer picks %APPDATA%.
    $env:TINYTEX_DIR = $workspace

    # The PowerShell installer directly, rather than the .bat wrapper around
    # it. The wrapper fetches this same script with
    #   curl.exe -fsSLO 'https://...'
    # and cmd.exe does not strip single quotes, so curl is handed a literal
    # quoted string, downloads nothing, and the failure surfaces one step later
    # as PowerShell being unable to find a file it was never given. We are
    # already in PowerShell, so the detour buys nothing anyway.
    $installer = Join-Path $workspace "install-bin-windows.ps1"
    Invoke-WebRequest -Uri "https://tinytex.yihui.org/install-bin-windows.ps1" -OutFile $installer
    & powershell.exe -ExecutionPolicy Bypass -File $installer
    if ($LASTEXITCODE -ne 0) { throw "the TinyTeX installer exited with $LASTEXITCODE" }

    $installed = Join-Path $workspace "TinyTeX"
    if (-not (Test-Path $installed)) {
        throw "TinyTeX did not install where expected ($installed)"
    }

    # The binaries sit under a platform-named directory. Left where they are:
    # TeX resolves its own files by walking up from the running binary, and
    # moving them puts every one of those lookups a directory too high.
    $binDir = (Get-ChildItem -Path (Join-Path $installed "bin") -Directory | Select-Object -First 1).FullName
    $env:PATH = "$binDir;$env:PATH"

    Write-Host "Installing the packages the template needs..."
    & tlmgr install @Packages
    if ($LASTEXITCODE -ne 0) { throw "tlmgr exited with $LASTEXITCODE" }

    # None of this is read by pdfTeX, and it is most of the size.
    foreach ($path in @("texmf-dist\doc", "texmf-dist\source", "tlpkg\tlpobj")) {
        $full = Join-Path $installed $path
        if (Test-Path $full) { Remove-Item -Recurse -Force $full }
    }

    $parent = Split-Path -Parent $Destination
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    if (Test-Path $Destination) { Remove-Item -Recurse -Force $Destination }
    Move-Item -Path $installed -Destination $Destination

    $pdflatex = (Get-ChildItem -Path (Join-Path $Destination "bin") -Recurse -Filter "pdflatex.exe" | Select-Object -First 1).FullName
    $size = "{0:N0} MB" -f ((Get-ChildItem -Path $Destination -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB)
    Write-Host "Bundled TeX at $Destination ($size)"
    & $pdflatex --version | Select-Object -First 1
}
finally {
    Remove-Item -Recurse -Force $workspace -ErrorAction SilentlyContinue
}
