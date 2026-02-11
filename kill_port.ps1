# PowerShell script to kill process using a specific port
param(
    [int]$Port = 8030
)

Write-Host "Checking for processes using port $Port..." -ForegroundColor Yellow

# Find process using the port
$connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

if ($connection) {
    $processId = $connection.OwningProcess
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    
    if ($process) {
        Write-Host "Found process: $($process.ProcessName) (PID: $processId)" -ForegroundColor Red
        Write-Host "Killing process..." -ForegroundColor Yellow
        
        try {
            Stop-Process -Id $processId -Force
            Write-Host "Process killed successfully!" -ForegroundColor Green
        } catch {
            Write-Host "Error killing process: $_" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Process with PID $processId not found." -ForegroundColor Yellow
    }
} else {
    Write-Host "No process found using port $Port" -ForegroundColor Green
}

