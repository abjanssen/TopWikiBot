#! /bin/bash
set -eo pipefail
python - <<'END_SCRIPT'
import potd_bot

potd_bot.main()
END_SCRIPT
echo "$(date): posted"
