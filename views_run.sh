#! /bin/bash
set -eo pipefail
python - <<'END_SCRIPT'
import views_bot

views_bot.main()
END_SCRIPT
echo "$(date): posted"
