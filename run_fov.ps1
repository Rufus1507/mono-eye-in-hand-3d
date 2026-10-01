param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $FovArguments
)

# Uu tien uv (moi truong trong pyproject.toml). Neu may khong co uv thi quay ve
# cach cu: py -3.14 voi cac goi trong requirements.txt.
# KHONG dat PYTHONPATH: thu muc chua do_fov.py tu vao sys.path[0] khi goi thang file.
# File nay viet TIENG VIET KHONG DAU: Windows PowerShell 5.1 doc script .ps1
# khong co BOM bang codepage ANSI, chu co dau se lam vo chuoi -> ParserError.

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $scriptRoot "do_fov.py"

if (-not (Test-Path -LiteralPath $script)) {
    Write-Error "Khong tim thay $script"
    exit 127
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run --project $scriptRoot python $script @FovArguments
} else {
    & py -3.14 $script @FovArguments
}
exit $LASTEXITCODE
