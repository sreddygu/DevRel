$roboAgentModelProfiles = @{
    gemma4 = [pscustomobject]@{
        PiModelId = "gemma4"
        DisplayName = "Gemma 4 (RoboAgent QNN)"
        ModelDirectory = "models\gemma4_e2b_sc8380xp_ctxt_4000_ar_l-128"
        ModelFile = "gemma4_e2b_sc8380xp_ctxt_4000-001.pte"
        TokenizerFile = "tokenizer.json"
        DecoderModelVersion = "gemma4"
        PipeName = "gemma4"
        ContextTokens = 3800
        PiContextTokens = 100000
        DefaultSeqLen = 3800
        MaxTokens = 512
    }
}

function Get-RoboAgentModelProfile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $profile = $roboAgentModelProfiles[$Name]
    if (-not $profile) {
        throw "Unknown RoboAgent model profile '$Name'. Available profiles: $($roboAgentModelProfiles.Keys -join ', ')."
    }

    $modelDirectory = Join-Path $Root $profile.ModelDirectory
    $modelPath = Join-Path $modelDirectory $profile.ModelFile
    $tokenizerPath = Join-Path $modelDirectory $profile.TokenizerFile
    if (-not (Test-Path $modelPath)) { throw "Model file not found for profile '$Name': $modelPath" }
    if (-not (Test-Path $tokenizerPath)) { throw "Tokenizer file not found for profile '$Name': $tokenizerPath" }

    return [pscustomobject]@{
        Name = $Name
        PiModelId = $profile.PiModelId
        DisplayName = $profile.DisplayName
        ModelPath = $modelPath
        TokenizerPath = $tokenizerPath
        DecoderModelVersion = $profile.DecoderModelVersion
        PipeName = $profile.PipeName
        ContextTokens = $profile.ContextTokens
        PiContextTokens = $profile.PiContextTokens
        DefaultSeqLen = $profile.DefaultSeqLen
        MaxTokens = $profile.MaxTokens
    }
}
