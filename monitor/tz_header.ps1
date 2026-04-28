# tz_header.ps1 — Compute and print the [tz] timezone status line for monitoring output
# Outputs one line: UTC | Moscow | Broker | last MT5 signal timing
#
# Usage: powershell -ExecutionPolicy Bypass -File monitor\tz_header.ps1 [-LastSigBrokerTime "10:03:00"]
#
# Broker: Blueberry Markets uses EET (Eastern European Time)
#   Summer (last Sun Mar - last Sun Oct): UTC+3
#   Winter:                               UTC+2
# Moscow: always UTC+3 (no DST since 2011)
#
# The broker UTC offset is computed from Windows DST rules for EET.

param(
    [string]$LastSigBrokerTime = ""
)

$now = [System.DateTime]::UtcNow

# Moscow is always UTC+3
$moscowOffset = 3
$moscow = $now.AddHours($moscowOffset)

# Blueberry broker time: EET = UTC+2 winter, UTC+3 summer (CET+1 DST rule)
# Approximate: DST in effect if month is Apr-Oct (Europe/Nicosia zone)
$month = $now.Month
$brokerOffset = if ($month -ge 4 -and $month -le 10) { 3 } else { 2 }
$broker = $now.AddHours($brokerOffset)

$utcStr    = $now.ToString("HH:mm")
$mosStr    = $moscow.ToString("HH:mm")
$brkStr    = $broker.ToString("HH:mm")

if ($LastSigBrokerTime -ne "") {
    # Parse broker time and compute elapsed
    try {
        $sigParts = $LastSigBrokerTime -split ":"
        $sigBroker = [System.DateTime]::Today.AddHours([int]$sigParts[0]).AddMinutes([int]$sigParts[1]).AddSeconds([int]$sigParts[2])
        # If signal appears to be in the future (clock wrap), subtract a day
        if ($sigBroker -gt $broker) { $sigBroker = $sigBroker.AddDays(-1) }
        $elapsed = [int]($broker - $sigBroker).TotalMinutes
        $sigUtc = $sigBroker.AddHours(-$brokerOffset).ToString("HH:mm")
        $sigMos = $sigBroker.AddHours($moscowOffset - $brokerOffset).ToString("HH:mm")
        $sigInfo = " | Last sig: broker $($LastSigBrokerTime.Substring(0,5)) = UTC $sigUtc = Moscow $sigMos (${elapsed}m ago)"
    } catch {
        $sigInfo = " | Last sig: broker $LastSigBrokerTime"
    }
} else {
    $sigInfo = ""
}

Write-Host "[tz] UTC $utcStr | Moscow $mosStr | Broker $brkStr (UTC+${brokerOffset})$sigInfo"
