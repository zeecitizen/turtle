# crons/lib/tz_helper.ps1
# Single source of truth for timezone math.
# Exports: Get-TzHeader, Get-MoscowNow, Get-BrokerToUtc, Get-UtcToBroker
#
# Broker = Moscow = UTC+3 (Apr-Oct DST approx; within 1h of last-Sunday rule)

function Get-MoscowNow {
    [datetime]::UtcNow.AddHours(3)
}

function Get-BrokerToUtc {
    param([Parameter(Mandatory)][string]$BrokerTime)   # "HH:MM:SS" or "HH:MM"
    $parts  = $BrokerTime -split ':'
    $h = [int]$parts[0]
    $m = [int]$parts[1]
    $s = if ($parts.Count -ge 3) { [int]$parts[2] } else { 0 }
    $today = [datetime]::UtcNow.Date
    ($today.AddHours($h).AddMinutes($m).AddSeconds($s)).AddHours(-3)
}

function Get-UtcToBroker {
    param([Parameter(Mandatory)][datetime]$Utc)
    $Utc.AddHours(3)
}

function Get-TzHeader {
    param([string]$LastSigBrokerTime = "")

    $utcNow    = [datetime]::UtcNow
    $moscowNow = $utcNow.AddHours(3)
    $utcStr    = $utcNow.ToString("HH:mm")
    $moscowStr = $moscowNow.ToString("HH:mm")

    $sigPart = ""
    if ($LastSigBrokerTime -ne "") {
        try {
            $sigUtc     = Get-BrokerToUtc -BrokerTime $LastSigBrokerTime
            $elapsedMin = [int]($utcNow - $sigUtc).TotalMinutes
            if ($elapsedMin -lt 0) { $elapsedMin += 1440 }  # wrap at midnight
            $brokerHHMM = ($LastSigBrokerTime -split ':')[0..1] -join ':'
            $sigPart = " | Last sig: broker $brokerHHMM ($($elapsedMin)m ago)"
        } catch {
            $sigPart = " | Last sig: $LastSigBrokerTime (parse err)"
        }
    }

    return "UTC $utcStr | Moscow $moscowStr | Broker $moscowStr (UTC+3)$sigPart"
}
