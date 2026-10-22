# Run from an extracted source folder without installing dependencies.
$taskSource = Join-Path $PSScriptRoot 'src'
$taskPreviousPythonPath = $env:PYTHONPATH
$taskExitCode = 1
try {
    $env:PYTHONPATH = $taskSource
    python -X utf8 -m repo_weekly @args
    $taskExitCode = $LASTEXITCODE
}
finally {
    $env:PYTHONPATH = $taskPreviousPythonPath
}
exit $taskExitCode
