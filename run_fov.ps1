param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $FovArguments
)

# Chay bang py -3.14 theo quy uoc du an (python 3.12 mac dinh thieu cv2/numpy/yaml).
# KHONG dat PYTHONPATH: thu muc chua do_fov.py tu vao sys.path[0] khi goi thang file.
# File nay viet TIENG VIET KHONG DAU: Windows PowerShell 5.1 doc script .ps1
# khong co BOM bang codepage ANSI, chu co dau se lam vo chuoi -> ParserError.

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $scriptRoot "do_fov.py"

if (-not (Test-Path -LiteralPath $script)) {
    Write-Error "Khong tim thay $script"
    exit 127
}

& py -3.14 $script @FovArguments
exit $LASTEXITCODE
