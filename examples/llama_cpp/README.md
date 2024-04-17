# Llama.cpp Example
This example uses the official OpenAI client, but connects to local models served by `llama-cpp-python`.

## Installation (Dependencies)
> [!NOTE]
> You must first install `grimoire-ls` first before attempting to install this example

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

## Installation (Models)
First download the models used in this example:
1. [DeepSeek Coder Base 1.3B](https://huggingface.co/TheBloke/deepseek-coder-1.3b-base-GGUF/resolve/main/deepseek-coder-1.3b-base.Q4_K_M.gguf?download=true) (for code completion)
2. [DeepSeek Coder Instruct 6.7B](https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf?download=true) (for `Simplify this code` code action)
3. [Hermes Pro 2 Mistral 7B](https://huggingface.co/NousResearch/Hermes-2-Pro-Mistral-7B-GGUF/resolve/main/Hermes-2-Pro-Mistral-7B.Q4_K_M.gguf?download=true) (for style suggestion diagnostics)

Then edit the paths in `llama-ccp-server-config.json` file in this directory to match wherever you have stored the models.


## Usage
Run the model server, passing the configuration file in this directory as an argument:
```sh
python -m llama_cpp.server --config llama-ccp-server-config.json
```

With the model server running, make the LSP use the `init.py` in this directory.
You have two options to accomplish this:

1. Set an environment variable: `export GRIMOIRE_LS_HOME="path/to/this/directory"`
2. Copy the `init.py` from this directory into `$XDG_CONFIG_HOME/grimoire-ls`

If using the environment variable, make sure that is it set in your editor: terminal-based
editors should inherit the variables of the shell they are launched from, but GUI editors
might require additional configuration.
