Param()

$root = git rev-parse --show-toplevel 2>$null
if (-not $root) {
  $root = (Get-Location).Path
}

$bashCommand = "cd `"$root`" && ./scripts/diagnose.sh"

try {
  & wsl bash -lc $bashCommand
} catch {
  Write-Warning "Failed to execute diagnose script via WSL: $($_.Exception.Message)"
}
