"""CLI wrapper for training the SoundPulse advanced prediction engine.

Run from the project root:
    python -m scripts.train_model
    python -m scripts.train_model --basic   # Use basic trainer (GBM only)
"""

import sys


def main():
    use_basic = "--basic" in sys.argv

    if use_basic:
        from ml.train import main as basic_main

        basic_main()
    else:
        from ml.trainer import main as advanced_main

        advanced_main()


if __name__ == "__main__":
    main()
