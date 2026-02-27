#!/usr/bin/env python3
"""
Build script to download required models during snap build process.
This script modifies the model directory paths to use snap-appropriate locations.
"""

import os
import sys
from pathlib import Path


def download_models(install_dir: str):
    """Download required models to the snap install directory."""

    # Add the installed package to Python path
    site_packages = f"{install_dir}/lib/python3.12/site-packages"
    sys.path.insert(0, site_packages)

    try:
        # Import after adding to path
        from aTrain_core import globals
        from aTrain_core.load_resources import get_model

        # Override the required models directory to point to our snap location
        snap_models_dir = Path(site_packages) / "aTrain" / "required_models"
        snap_models_dir.mkdir(parents=True, exist_ok=True)

        # Monkey patch the globals to use our directory
        globals.REQUIRED_MODELS_DIR = snap_models_dir

        print(f"Downloading models to: {snap_models_dir}")

        # Download each required model
        for model in globals.REQUIRED_MODELS:
            print(f"Downloading model: {model}")
            try:
                model_path = get_model(model)
                print(f"Successfully downloaded {model} to {model_path}")
            except Exception as e:
                print(f"Error downloading {model}: {e}")
                raise

        print("All required models downloaded successfully!")

    except ImportError as e:
        print(f"Import error: {e}")
        print("Available packages:")
        import pkgutil

        for pkg in pkgutil.iter_modules([site_packages]):
            print(f"  - {pkg.name}")
        raise
    except Exception as e:
        print(f"Error during model download: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 snapcraft_download_models.py <install_dir>")
        sys.exit(1)

    install_dir = sys.argv[1]
    if not os.path.exists(install_dir):
        print(f"Install directory does not exist: {install_dir}")
        sys.exit(1)

    download_models(install_dir)
