#! /bin/bash
set -eo pipefail
python - <<'END_SCRIPT'
import featarticle_bot

featarticle_bot.main()
END_SCRIPT
echo "$(date): posted"