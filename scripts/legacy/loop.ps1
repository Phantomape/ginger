[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$maxIterations = 20
$iteration = 0

while ($iteration -lt $maxIterations) {

    Write-Host "Iteration $iteration"

    $prompt = Get-Content CLAUDE3.md -Raw
    Write-Host "Prompt loaded"

    Write-Host "Running Claude..."
    claude `
        --dangerously-skip-permissions `
        --print `
        $prompt `
        2>&1 | Out-Host

    Write-Host "Iteration finished"

    Start-Sleep 2

    $iteration++
}
