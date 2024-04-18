# Grimoire Language Server
Grimoire Language Server is a scaffold for building your own grimoire: 
a personalized AI-powered language server. Your grimoire can integrate
with your editor via the [language server protocol](https://microsoft.github.io/language-server-protocol/),
and can be used alongside your existing language servers and tooling, 
or on its own for languages that do not have a language server.

Grimoire Language Server is built on top of [`pygls`](https://github.com/openlawlibrary/pygls),
a python library that greatly simplifies the implementation of language servers.
`grimoire_ls` provides scaffolding around `pygls` and extra helper functions to
make your grimoire more tinker-friendly, and to support its two use-cases that are
unique among language servers: integration with generative AI, and re-use of the
same language server with many different programming languages.


# Installation
> [!WARNING]  
> This project is in early stages of development.
> I welcome any early adopters who would like to test it and I value your feedback!
> However, please be advised that the APIs may change as the project develops. 

First install the server:
1. [Install `uv`](https://github.com/astral-sh/uv?tab=readme-ov-file#getting-started)
2. Clone this repository and enter it in a terminal
3. Create a virtual environment: ```uv venv```
3. Install the this project into the env ```uv pip install .```

Then configure your editor to use the server:

## Neovim
```lua
nvim_create_augroup("grimoire-ls", { clear = true })
nvim_create_autocmd("BufEnter", {
  group = "grimoire-ls",
  pattern = ""
  callback = function()
	vim.lsp.start({
		name = "grimoire-ls",
		cmd = {"/absolute/path/to/cloned/grimoire-ls/.venv/bin/python", "-m", "grimoire_ls.run"},
		capabilities = vim.lsp.protocol.make_client_capabilities(),
        root_dir = vim.fn.getcwd(),
	})
  end,
})
```

## VSCode
(Coming soon)

## Emacs
(Coming soon)

# Upgrading to the latest version
In your cloned repository:
1. `git pull`
2. `uv pip install --upgrade .`

# Usage
The simplest grimoire is a single python file called `init.py`. You can
indicate where your `init.py` is saved in the following ways (in order
of precedence):

1. Set the environment variable `GRIMOIRE_LS_HOME` to the path of the directory containing the file.
2. If your system defines the environment variable `XDG_CONFIG_HOME`, put the file at `$XDG_CONFIG_HOME/grimoire-ls/init.py`
3. Put the file at `$HOME/.config/grimoire-ls/init.py`

To get started, check out the [`examples`](examples/) folder for some example configurations.

In addition, `pygls` provides a full implementation of the language server protocol and
`GrimoireServer` inherits from `pygls.LanguageServer`, so you can also consult the
[`pygls` documentation](https://pygls.readthedocs.io/en/latest/) if you would like to use
any of its features directly.

If you would like to install additional python dependencies for your grimoire, make sure you
install them into the virtual environment that you created during installation. An easy way
to do this is to use `uv` to install them:

1. `cd` into the cloned `grimoire-ls` repository
2. Install your dependencies with `uv`: ```uv pip install <some package>```


# FAQ
## Can my grimoire use locally-hosted AI models?
Absolutely! Check out [`examples/llama_cpp`](examples/llama_cpp) for an example.

## Can my grimoire use proprietary models like GPT or Claude?
Sure! As long as you have an API key, anything shown in their API
tutorials can be done in your grimoire.

## Can my grimoire use `${any_python_library_here}`?
Yes! Your grimoire configuration is just regular python code.
Any library you can install on your machine can be used in your grimoire.

## Why Python?
**Ecosystem**

Python has the earliest adoption and most support for generative AI tools.
In fact, many implementations of new ideas are available in python first 
because most cutting-edge research in this area uses python. I feel that 
having early access to the latest tools and ideas fits grimoire's intended 
purpose: allowing users to tinker and create their own creative and wonderful 
tools.

**Scripting is not the bottleneck**

In the majority of cases, the performance bottleneck of your grimoire
will be the models themselves, not the glue code around them. As such,
python's relative lack of performance is not likely to affect your
experience much.
