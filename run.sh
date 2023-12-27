#! /bin/bash
set -eo pipefail
python - <<'END_SCRIPT'
import bot

bot.main()
END_SCRIPT
echo "$(date): posted"
