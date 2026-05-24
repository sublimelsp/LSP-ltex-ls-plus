# LSP-ltex-ls-plus

Latex/Markdown grammar check support for Sublime's LSP plugin provided through [ltex-plus/ltex-ls-plus](https://github.com/ltex-plus/ltex-ls-plus).

## Installation

1. Install [LSP](https://packagecontrol.io/packages/LSP) via Package Control.
2. Install this package.
3. Restart Sublime.

Note: Currently LSP ignores non-workspace files. Add the folder to Sublime Text to enable the Server.

## Configuration

Here are some ways to configure the package and the language server.

- From `Preferences > Package Settings > LSP > Servers > LSP-ltex-ls-plus`
- Project-specific configuration.
  From the command palette run `Project: Edit Project` and add your settings in:

  ```js
  {
     "settings": {
        "LSP": {
           "LSP-ltex-ls-plus": {
              "settings": {
                 // Put your settings here
              }
           }
        }
     }
  }
  ```

### Language Configuration
- Set the language string in the server settings
- Use magic comments in code, see https://ltex-plus.github.io/ltex-plus/advanced-usage.html

### Limitations

This version lacks in comparison to [vscode-ltex](https://github.com/ltex-plus/vscode-ltex-plus) the possibility to add exceptions (rules, words, …) on a per-project basis. (Maybe added in the future.)
