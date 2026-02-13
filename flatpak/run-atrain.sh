#!/bin/bash
set -eo pipefail

required_models_present() {
    if [[ -n "${REQUIRED_MODEL_1:-}" && -n "${REQUIRED_MODEL_2:-}" ]]; then
        [[ -d "${REQUIRED_MODEL_1}" && -d "${REQUIRED_MODEL_2}" ]]
        return
    fi

    python3 - <<'PY'
from aTrain_core.globals import REQUIRED_MODELS, REQUIRED_MODELS_DIR

missing = [name for name in REQUIRED_MODELS if not (REQUIRED_MODELS_DIR / name).is_dir()]
raise SystemExit(1 if missing else 0)
PY
}

for dir in \
    /app/lib/python*/site-packages/nvidia/*/lib \
    /usr/lib/*/GL/default/lib \
    /usr/lib/extensions/nvidia/lib \
    /usr/lib/extensions/nvidia-*/lib
do
    [[ -d "$dir" ]] || continue
    case ":${LD_LIBRARY_PATH-}:" in
        *":${dir}:"*) ;;
        *)
            LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+${LD_LIBRARY_PATH}:}${dir}"
            ;;
    esac
done
export LD_LIBRARY_PATH

if ! required_models_present; then
    echo "Models not found. Running aTrain init..."
    aTrain init
fi

exec aTrain start "$@"
