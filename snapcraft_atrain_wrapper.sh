#!/bin/sh

# Wrapper script for aTrain to properly set up the environment when running inside a snap.
# This ensures that models are found in the correct snap-specific locations.

# Get snap directory
SNAP_DIR="${SNAP:-/snap/atrain/current}"
SNAP_USER_DATA="${SNAP_USER_DATA:-$HOME/snap/atrain/current}"
REAL_HOME="${SNAP_REAL_HOME:-$HOME}"

# Set up model directories
SNAP_MODELS_DIR="$SNAP_DIR/lib/python3.12/site-packages/aTrain/required_models"
export ATRAIN_USER_DIR="${ATRAIN_USER_DIR:-$REAL_HOME/Documents/atrain}"
USER_MODELS_DIR="$ATRAIN_USER_DIR/models"

# Set up temporary and runtime directories for multiprocessing
SNAP_USER_COMMON="${SNAP_USER_COMMON:-$HOME/snap/atrain/common}"
export TMPDIR="$SNAP_USER_COMMON/tmp"
export XDG_RUNTIME_DIR="$SNAP_USER_COMMON/runtime"

# Ensure user directories exist
mkdir -p "$USER_MODELS_DIR"
mkdir -p "$ATRAIN_USER_DIR/transcriptions"
mkdir -p "$ATRAIN_USER_DIR/settings"
mkdir -p "$TMPDIR"
mkdir -p "$XDG_RUNTIME_DIR"

# Set proper permissions for runtime directory
chmod 700 "$XDG_RUNTIME_DIR"

# Set environment variables for aTrain
if [ -d "$SNAP_MODELS_DIR" ]; then
    export ATRAIN_REQUIRED_MODELS_DIR="$SNAP_MODELS_DIR"
fi

# Add snap's python packages to PYTHONPATH
export PYTHONPATH="$SNAP/lib/python3.12/site-packages:$PYTHONPATH"
# Force Qt backend for native windowing and make it snap-safe.
export PYWEBVIEW_GUI=qt
export QT_API=pyqt5
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu"
export LIBGL_ALWAYS_SOFTWARE=1
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
# Reduce ONNX Runtime console noise (keep errors, hide warnings).
export ORT_LOG_SEVERITY_LEVEL="${ORT_LOG_SEVERITY_LEVEL:-3}"
export ORT_LOG_VERBOSITY_LEVEL="${ORT_LOG_VERBOSITY_LEVEL:-0}"
# Ensure a valid arrow cursor theme is available inside the snap runtime.
export XCURSOR_PATH="$SNAP/usr/share/icons:${XCURSOR_PATH:-}"
export XCURSOR_THEME="${XCURSOR_THEME:-DMZ-White}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-24}"

# Expose CUDA/NVIDIA shared libraries bundled in Python wheels.
CUDA_LIB_BASE="$SNAP/lib/python3.12/site-packages/nvidia"
for subdir in npp/lib cublas/lib cuda_runtime/lib cudnn/lib cufft/lib curand/lib cusolver/lib cusparse/lib nvjitlink/lib nvtx/lib; do
    if [ -d "$CUDA_LIB_BASE/$subdir" ]; then
        LD_LIBRARY_PATH="$CUDA_LIB_BASE/$subdir:$LD_LIBRARY_PATH"
    fi
done
LD_LIBRARY_PATH="$SNAP/lib/python3.12/site-packages/torch/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH

echo "aTrain snap environment configured:"
echo "  Required models: $ATRAIN_REQUIRED_MODELS_DIR"
echo "  User models: $USER_MODELS_DIR"
echo "  User data: $ATRAIN_USER_DIR"

# Execute aTrain as a Python module so that multiprocessing can correctly
# re-import __main__ when using spawn/forkserver start methods.
# Using "python3 -c ..." previously broke this because worker processes
# cannot reconstruct an inline -c script as their __main__ module.
exec python3 -m aTrain "$@"
