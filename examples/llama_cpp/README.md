# Llama.cpp Example
This example uses the official OpenAI client, but connects to local models served by `llama-cpp-python`.

## Installation
*Note: you must first install `grimoire-ls` first before attempting to install this example*
Enter this directory and then follow the instructions depending on how you want to run the models.

### CPU
Run:
```sh
uv pip install -r requirements.txt
```

### GPU with CUDA
Run:
```sh
CMAKE_ARGS="-DLLAMA_CUDA=on" FORCE_CMAKE=1 uv pip install -r requirements.txt
```

### GPU with Apple Silicon
First ensure `XCode` is installed:
```sh
xcode-select --install
```

Then run:
```sh
CMAKE_ARGS="-DLLAMA_METAL=on" uv pip install -r requirements.txt
```

## Usage
Run the model server
```sh
python -m --config examples/llama_cpp/llama-ccp-server-config.json
```

With the model server running, make the LSP use the `init.py` in this directory.
You have two options to accomplish this:

1. Set an environment variable: `export GRIMOIRE_LS_HOME="path/to/this/directory"`
2. Copy the `init.py` from this directory into `$XDG_CONFIG_HOME/grimoire-ls`

If using the environment variable, make sure that is it set in your editor: terminal-based
editors should inherit the variables of the shell they are launched from, but GUI editors
might require additional configuration.
