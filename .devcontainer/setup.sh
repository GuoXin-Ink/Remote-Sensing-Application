#!/usr/bin/env bash
set -euo pipefail

eval "$(/opt/conda/bin/conda shell.bash hook)"

echo "Creating/updating conda environment: rsa-lab"
if conda env list | awk '{print $1}' | grep -qx "rsa-lab"; then
  conda env update -n rsa-lab -f .devcontainer/environment.yml --prune
else
  conda env create -f .devcontainer/environment.yml
fi

echo "Registering Jupyter kernel: Python (rsa-lab)"
conda run -n rsa-lab python -m ipykernel install \
  --user \
  --name rsa-lab \
  --display-name "Python (rsa-lab)"

echo "Activating rsa-lab automatically in new terminals"
if ! grep -q "conda activate rsa-lab" "${HOME}/.bashrc"; then
  {
    echo ""
    echo "# Remote Sensing Application lab environment"
    echo "conda activate rsa-lab"
  } >> "${HOME}/.bashrc"
fi

echo "Codespaces setup complete. Select the Jupyter kernel: Python (rsa-lab)."
