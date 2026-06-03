# pre_compact.ps1
# Injects project memory into Claude's context before auto-compaction.
# Ensures key project state survives context resets without requiring manual re-briefing.
# Called by the PreCompact hook in .claude/settings.local.json

$MEMORY_DIR  = "C:\Users\zeesh\.claude\projects\c--Users-zeesh-Documents-GitHub-turtle\memory"
$PROJECT_DIR = "C:\Users\zeesh\Documents\GitHub\turtle"

$ctx = [System.Collections.Generic.List[string]]::new()
$ctx.Add("============================================================")
$ctx.Add("TURTLE PROJECT STATE -- PRESERVED ACROSS COMPACTION")
$ctx.Add("Captured: $(Get-Date -Format 'yyyy-MM-dd HH:mm') (local)")
$ctx.Add("============================================================")
$ctx.Add("")

# Read all memory files (skip MEMORY.md index itself)
if (Test-Path $MEMORY_DIR) {
    $files = Get-ChildItem $MEMORY_DIR -Filter "*.md" |
             Where-Object { $_.Name -ne "MEMORY.md" } |
             Sort-Object Name
    foreach ($f in $files) {
        $content = Get-Content $f.FullName -Raw -Encoding UTF8
        if ($content) {
            $ctx.Add("--- $($f.Name) ---")
            $ctx.Add($content.Trim())
            $ctx.Add("")
        }
    }
}

# Recent Claude Trader signals (last 10)
$sigsPath = "$PROJECT_DIR\monitor\claude_signals.csv"
if (Test-Path $sigsPath) {
    $ctx.Add("--- Recent Claude Trader signals (last 10) ---")
    $rows = Get-Content $sigsPath -Tail 10 -Encoding UTF8
    $ctx.Add(($rows -join "`n"))
    $ctx.Add("")
}

# Cron manifest quick summary
$manifestPath = "$PROJECT_DIR\crons\manifest.json"
if (Test-Path $manifestPath) {
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $ctx.Add("--- Active crons ---")
    foreach ($c in $manifest.crons) {
        if ($c.enabled) {
            $ctx.Add("  $($c.id): $($c.name) [$($c.schedule)]")
        }
    }
    $ctx.Add("")
}

$combined = $ctx -join "`n"

# Output JSON that Claude's PreCompact hook injects as additional context
$result = @{
    hookSpecificOutput = @{
        hookEventName   = "PreCompact"
        additionalContext = $combined
    }
}

$result | ConvertTo-Json -Depth 5 -Compress
