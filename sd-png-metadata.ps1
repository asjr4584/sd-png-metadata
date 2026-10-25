#!/usr/bin/env pwsh
& python "$PSScriptRoot\sd_png_metadata.py" @args
exit $LASTEXITCODE
