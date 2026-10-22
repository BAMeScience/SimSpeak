"""Generate opt-in argon reference files from an explicit JSON configuration.

Usage: python generate_argon_reference.py config/argon_lj_example.json output.zip
"""
import json
import sys
from pathlib import Path
from simspeak.argon_reference import ArgonLJConfig, generate_argon_lj_bundle


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python generate_argon_reference.py CONFIG.json OUTPUT.zip')
    values = json.loads(Path(sys.argv[1]).read_text())
    config = ArgonLJConfig(**values)
    Path(sys.argv[2]).write_bytes(generate_argon_lj_bundle(config))
    print('Generated candidate LAMMPS reference input (NOT engine-executed).')

if __name__ == '__main__':
    main()
