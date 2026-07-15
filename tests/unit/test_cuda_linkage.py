"""Lockfile guard for the torch / ctranslate2 CUDA-runtime coupling.

ctranslate2 (via faster-whisper) dynamically links against the CUDA 12
runtime (cublas64_12.dll / libcublas.so.12). The GPU-flavored torch wheels
bundle the runtime their `+cuXYZ` tag names - and nothing else. If torch is
pinned to a CUDA major that ctranslate2 is not linked against, GPU
transcription crashes at model load with "Library cublas64_12.dll is not
found" while CPU transcription keeps working, so CPU-only CI stays green
(the exact regression shipped in #205 and fixed in #215).

A real runtime check needs an NVIDIA driver, which CI runners don't have.
These tests instead pin the coupling at the resolver level by parsing
uv.lock - deterministic, milliseconds, torch- and NiceGUI-free.
"""

import tomllib
from pathlib import Path

import pytest

UV_LOCK = Path(__file__).parents[2] / "uv.lock"

# CUDA major that ctranslate2 links against, per released major version.
# ctranslate2 4.x has no CUDA 13 support (and faster-whisper caps
# ctranslate2<5). When a ctranslate2 release adds CUDA 13, extend this map -
# the KeyError below is the reminder to make that a conscious decision.
CTRANSLATE2_CUDA_MAJOR = {4: 12}


def _locked_versions(name: str) -> list[str]:
    with UV_LOCK.open("rb") as f:
        lock = tomllib.load(f)
    return [p["version"] for p in lock["package"] if p["name"] == name]


def _cuda_major(version: str) -> int | None:
    """Extract the CUDA major from a `+cuXYZ` local version tag.

    The tag encodes the CUDA version without the dot and the minor is the
    last digit: cu128 -> 12.8 -> 12, cu130 -> 13.0 -> 13."""
    _, _, local = version.partition("+")
    if not local.startswith("cu"):
        return None
    return int(local[2:-1])


def test_torch_cuda_major_matches_ctranslate2_linkage():
    ctranslate2_versions = _locked_versions("ctranslate2")
    assert ctranslate2_versions, "ctranslate2 disappeared from uv.lock - update this guard"
    ctranslate2_major = int(ctranslate2_versions[0].split(".")[0])
    required_cuda_major = CTRANSLATE2_CUDA_MAJOR[ctranslate2_major]

    cuda_tagged = [v for v in _locked_versions("torch") if _cuda_major(v) is not None]
    assert cuda_tagged, "no GPU-flavored torch in uv.lock - update this guard"
    for version in cuda_tagged:
        assert _cuda_major(version) == required_cuda_major, (
            f"torch {version} bundles the CUDA {_cuda_major(version)} runtime, but "
            f"ctranslate2 {ctranslate2_versions[0]} links against CUDA "
            f"{required_cuda_major}. GPU transcription would crash at model load "
            f"(see #215). Pin torch to a +cu{required_cuda_major}x build or update "
            f"CTRANSLATE2_CUDA_MAJOR if ctranslate2 gained support."
        )


def test_torchaudio_locked_in_lockstep_with_torch():
    # torchaudio is ABI-coupled to torch: versions and +cuXYZ tags must match
    # exactly, or import fails at runtime.
    torch_versions = sorted(_locked_versions("torch"))
    torchaudio_versions = sorted(_locked_versions("torchaudio"))
    torch_tags = sorted({v.partition("+")[2] for v in torch_versions})
    torchaudio_tags = sorted({v.partition("+")[2] for v in torchaudio_versions})
    assert torch_tags == torchaudio_tags, (
        f"torch {torch_versions} and torchaudio {torchaudio_versions} are not in "
        f"lockstep - their local version tags must match (ABI coupling)."
    )


@pytest.mark.parametrize(
    ("version", "major"),
    [("2.9.1+cu128", 12), ("2.9.1+cu130", 13), ("2.9.1+cu118", 11), ("2.9.1", None)],
)
def test_cuda_major_parsing(version, major):
    assert _cuda_major(version) == major
