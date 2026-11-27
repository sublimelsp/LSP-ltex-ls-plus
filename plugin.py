from __future__ import annotations

import os
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
from lsp_utils import (
    InstallDirectory,
    PlatformAssets,
    UnsupportedPlatformError,
    download_and_extract_github_asset,
    fetch_latest_github_release_tag,
    select_platform_asset,
)
from typing_extensions import override

GITHUB_REPOSITORY = "ltex-plus/ltex-ls-plus"
LATEST_TESTED_RELEASE = "19.0.0"
SETTINGS_FILENAME = "LSP-ltex-ls-plus.sublime-settings"
SERVER_NAME = "ltex-ls-plus"
# Suffixes of the release assets that bundle a Java runtime, by platform.
BUNDLED_JAVA_ASSET_SUFFIXES: PlatformAssets = {
    "linux-arm64": "-linux-aarch64.tar.gz",
    "linux-x64": "-linux-x64.tar.gz",
    "osx-arm64": "-mac-aarch64.tar.gz",
    "osx-x64": "-mac-x64.tar.gz",
    "windows-arm64": "-windows-aarch64.zip",
    "windows-x64": "-windows-x64.zip",
}
# Suffix of the platform-independent release asset that runs with the Java installation set in JAVA_HOME.
PLATFORM_INDEPENDENT_ASSET_SUFFIX = ".tar.gz"


def read_user_server_settings() -> dict[str, Any]:
    """
    Returns the "settings" object from the user's settings file only.

    `sublime.load_settings()` returns the default "settings" object when the user's file doesn't define one, so
    saving that back would copy all default settings to the user's file.
    """
    user_settings_path = Path(sublime.packages_path(), "User", SETTINGS_FILENAME)
    try:
        user_settings = sublime.decode_value(user_settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    server_settings = user_settings.get("settings") if isinstance(user_settings, dict) else None
    return server_settings if isinstance(server_settings, dict) else {}


def code_action_insert_settings(server_setting_key: str, value: dict[str, list[str]]) -> None:
    """
    Adds entries from the ltex-ls-plus quick fixes ("Add to dictionary", "Disable rule", "Hide false positive") to the
    user's settings, merging them with entries already set there.

    :param      server_setting_key:    The key of the server setting (in the "settings" object)
    :param      value:                 A dict of "language": [entries] pairs
    """
    server_settings = read_user_server_settings()
    entries: dict[str, list[str]] = server_settings.get(server_setting_key) or {}
    for language, new_entries in value.items():
        # Remove duplicates while preserving order.
        entries[language] = list(dict.fromkeys(entries.get(language, []) + new_entries))
    server_settings[server_setting_key] = entries
    settings = sublime.load_settings(SETTINGS_FILENAME)
    settings.set("settings", server_settings)
    sublime.save_settings(SETTINGS_FILENAME)


class LTeXLsPlus(LspPlugin):
    latest_github_release = None

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        server_path = context.configuration.root_settings.get('server_path', 'auto')
        if server_path == 'auto':
            cls.setup_managed_server(context)
        else:
            context.variables.update({
                "server_path": server_path,
            })

    @classmethod
    def setup_managed_server(cls, context: OnPreStartContext) -> None:
        server_version = cls.server_version(context)
        asset = f"{SERVER_NAME}-{server_version}{cls.asset_suffix()}"
        storage_path = cls.plugin_storage_path
        script_path = f"bin/{SERVER_NAME}" + (".bat" if sublime.platform() == "windows" else "")
        install_dir = InstallDirectory(
            storage_path,
            "server",
            server_version,
            asset,
            # unversioned directories (named "ltex-ls-plus-{version}") used by previous releases
            legacy_dirs=list(storage_path.glob(f"{SERVER_NAME}-*")),
        )
        install_path = install_dir.install(
            lambda path: download_and_extract_github_asset(GITHUB_REPOSITORY, server_version, asset, path)
        )
        # Archives of some platforms have their files in "./ltex-ls-plus-{version}/", which isn't recognized as a
        # single root directory to extract the contents of, unlike "ltex-ls-plus-{version}/" in the other archives.
        # The archives preserve the executable permission of the script.
        server_path = install_path / script_path
        if not server_path.is_file():
            server_path = install_path / f"{SERVER_NAME}-{server_version}" / script_path
        if not server_path.is_file():
            raise PluginStartError(f"Server script not found in {install_path}")
        context.variables.update({
            "server_path": str(server_path),
        })

    @staticmethod
    def asset_suffix() -> str:
        """
        Returns the suffix of the release asset to download: one that bundles a Java runtime, unless JAVA_HOME is set
        or there is none for the current platform.
        """
        if os.getenv("JAVA_HOME") is None:
            try:
                return select_platform_asset(BUNDLED_JAVA_ASSET_SUFFIXES)
            except UnsupportedPlatformError:
                pass
        return PLATFORM_INDEPENDENT_ASSET_SUFFIX

    @classmethod
    def server_version(cls, context: OnPreStartContext) -> str:
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
        """Fetches the tag of the latest release from GitHub."""
        if not cls.latest_github_release:
            try:
                cls.latest_github_release = fetch_latest_github_release_tag(GITHUB_REPOSITORY)
            except Exception as ex:
                print(f"LSP-ltex-ls-plus: Failed fetching the latest release: {ex}")
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
