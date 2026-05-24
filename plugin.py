from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from io import UnsupportedOperation
from pathlib import Path
from typing import Any

import sublime
from LSP.plugin import (
    LspPlugin,
    OnPreStartContext,
    PluginStartError,
    Promise,
    command_handler,
)
from typing_extensions import override

GITHUB_RELEASES_API_URL = "https://api.github.com/repos/ltex-plus/ltex-ls-plus/releases/latest"
GITHUB_REPOSITORY_URL = "https://github.com/ltex-plus/ltex-ls-plus"
LATEST_TESTED_RELEASE = "18.6.1"
SETTINGS_FILENAME = "LSP-ltex-ls-plus.sublime-settings"

def code_action_insert_settings(server_setting_key: str, value: dict[str, Any]):
    """
    Adds a server setting initiated via custom ltex-la codeAction.
    Merges the settings if already present.
    This function is used for the addToDictionary,... custom commands
    :param      server_setting_key:    The key of the server setting
                                       (in "settings" block)
    :type       server_setting_key:    str
    :param      value:  A dict of "language": [settings] pairs
    :type       value:  dict
    """
    settings = sublime.load_settings(SETTINGS_FILENAME)
    server_settings: Any = settings.get("settings")
    exception_dict = server_settings.get(server_setting_key, {})

    for k, val in value.items():
        language_setting = exception_dict.get(k, [])
        # Remove duplicates
        new_language_setting = list(set(language_setting + val))
        exception_dict[k] = new_language_setting

    server_settings[server_setting_key] = exception_dict
    settings.set("settings", server_settings)
    sublime.save_settings(SETTINGS_FILENAME)


class LTeXLsPlus(LspPlugin):
    latest_github_release = None

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        server_script_name = "ltex-ls-plus"
        server_version = cls.serverversion(context)
        server_folder_name = f"{server_script_name}-{server_version}"
        # The directory of the server. In here are the "bin" and "lib" folders.
        server_directory = cls.plugin_storage_path / server_folder_name
        if not server_directory.is_dir() or not server_version:
            target_directory = cls.plugin_storage_path
            if target_directory.is_dir():
                shutil.rmtree(target_directory)
            target_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tempdir:
                archive_path = Path(tempdir, "server.tar.gz")

                suffix = ".tar.gz"  # platform-independent release
                if os.getenv("JAVA_HOME") is None:
                    platform = sublime.platform()
                    if platform == "osx":
                        suffix = "-mac-x64.tar.gz"
                    elif platform == "linux":
                        suffix = "-linux-x64.tar.gz"
                    elif platform == "windows":
                        suffix = "-windows-x64.zip"

                github_dl_url = f"{GITHUB_REPOSITORY_URL}/releases/download/{server_version}/ltex-ls-plus-{server_version}{suffix}"
                urllib.request.urlretrieve(github_dl_url, archive_path)

                sublime.status_message("ltex-ls: extracting")
                if suffix.endswith("tar.gz"):
                    archive = tarfile.open(archive_path, "r:gz")
                elif suffix.endswith(".zip"):
                    archive = zipfile.ZipFile(archive_path)
                else:
                    raise UnsupportedOperation()
                archive.extractall(tempdir)
                archive.close()
                shutil.move(Path(tempdir, server_folder_name), target_directory)
                if not server_directory.exists():
                    raise PluginStartError("Download failed or version could not be determined")
        context.variables.update({
            "script": server_script_name + (".bat" if sublime.platform() == 'windows' else ""),
            "serverdir": str(server_directory),
        })

    @classmethod
    def serverversion(cls, context: OnPreStartContext) -> str:
        """
        Returns the version of ltex-ls to use. Can be None if
        no version is set in settings and no connection is available and
        and no server is available offline.

        :returns:   The version of ltex-ls to use. Can be None.
        :rtype:     str
        """
        if version := context.configuration.root_settings.get("version"):
            return version
        # Use latest tested release by default but allow overwriting the behavior.
        if context.configuration.root_settings.get("allow_untested") and (latest_release := cls.fetch_latest_release()):
            return latest_release
        return LATEST_TESTED_RELEASE

    @classmethod
    def fetch_latest_release(cls) -> str | None:
        """Fetches a the latest release via GitHub API."""
        if not cls.latest_github_release:
            try:
                with urllib.request.urlopen(GITHUB_RELEASES_API_URL) as f:
                    data: dict[str, str] = json.loads(f.read().decode("utf-8"))
                    cls.latest_github_release = data["tag_name"]
            except urllib.error.URLError:
                pass
        return cls.latest_github_release

    @command_handler('_ltex.addToDictionary')
    def on_add_to_dictionary_command(self, arguments: list[Any] | None) -> Promise[None]:
        if isinstance(arguments, list):
            code_action_insert_settings("ltex.dictionary", arguments[0]["words"])
        return Promise.resolve(None)

    @command_handler('_ltex.hideFalsePositives')
    def on_hide_false_positives_command(self, arguments: list[Any] | None) -> Promise[None]:
        if isinstance(arguments, list):
            code_action_insert_settings("ltex.hiddenFalsePositives", arguments[0]["falsePositives"])
        return Promise.resolve(None)

    @command_handler('_ltex.disableRules')
    def on_disable_rules_command(self, arguments: list[Any] | None) -> Promise[None]:
        if isinstance(arguments, list):
            code_action_insert_settings("ltex.disabledRules", arguments[0]["ruleIds"])
        return Promise.resolve(None)


def plugin_loaded() -> None:
    LTeXLsPlus.register()


def plugin_unloaded() -> None:
    LTeXLsPlus.unregister()
