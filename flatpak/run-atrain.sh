#!/bin/bash
set -

# Force Qt to use XDG Desktop Portal for file dialogs in Flatpak
export QT_QPA_PLATFORMTHEME=xdgdesktopportal

#check if required models are there. otherwise run atrain init to get them
if [ ! -d "$REQUIRED_MODEL_1" ] || [ ! -d "$REQUIRED_MODEL_2" ]; then
    echo "Models not found. Running aTrain init..."
    aTrain init
fi

exec aTrain start "$@"
