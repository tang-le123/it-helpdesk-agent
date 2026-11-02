param(
  [int]$ApiPort = 8002,
  [int]$WebPort = 5173
)

$ErrorActionPreference = "SilentlyContinue"

foreach ($port in @($ApiPort, $WebPort)) {
  $connections = Get-NetTCPConnection -LocalPort $port -State Listen
  foreach ($connection in $connections) {
    $process = Get-Process -Id $connection.OwningProcess
    if ($process) {
      Write-Host ("Stopping " + $process.ProcessName + " (PID " + $process.Id + ", port " + $port + ")")
      Stop-Process -Id $process.Id -Force
    }
  }
}

Write-Host "Stopped."
