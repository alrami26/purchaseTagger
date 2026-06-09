from pathlib import Path
from unittest.mock import Mock, patch

from purchase_tagger_app import (
    APP_ICON_PATH,
    APP_ICON_PNG_PATH,
    WINDOWS_APP_ID,
    PurchaseTaggerUI,
    main,
    resource_path,
    set_windows_app_user_model_id,
)
from version import APP_DISPLAY_NAME, APP_TITLE, APP_VERSION, RELEASE_DATE, __version__


ROOT = Path(__file__).resolve().parent


def test_resource_path_resolves_assets_in_project_root():
    assert resource_path("assets/app_icon.ico") == str(ROOT / "assets" / "app_icon.ico")


def test_release_metadata_marks_version_1_0_1():
    assert APP_DISPLAY_NAME == "Etiquetador de compras PDF"
    assert APP_VERSION == "1.0.1"
    assert __version__ == APP_VERSION
    assert APP_TITLE == "Etiquetador de compras PDF v1.0.1"
    assert RELEASE_DATE == "2026-06-09"


def test_apply_app_icon_uses_icon_and_photo_when_available():
    app = object.__new__(PurchaseTaggerUI)
    app.iconbitmap = Mock()
    app.iconphoto = Mock()
    photo = Mock()

    with patch("purchase_tagger_app.os.path.exists", return_value=True), \
            patch("purchase_tagger_app.tk.PhotoImage", return_value=photo):
        app._apply_app_icon()

    app.iconbitmap.assert_called_once_with(APP_ICON_PATH)
    app.iconphoto.assert_called_once_with(True, photo)
    assert app._app_icon_photo is photo


def test_sets_windows_app_user_model_id_on_windows():
    shell32 = Mock()

    with patch("purchase_tagger_app.sys.platform", "win32"), \
            patch("purchase_tagger_app.ctypes.windll.shell32", shell32, create=True):
        assert set_windows_app_user_model_id() is True

    shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(WINDOWS_APP_ID)


def test_main_sets_windows_identity_before_creating_window():
    events = []
    app = Mock()

    with patch("purchase_tagger_app.set_windows_app_user_model_id", side_effect=lambda: events.append("identity")), \
            patch("purchase_tagger_app.PurchaseTaggerUI", side_effect=lambda: events.append("ui") or app):
        main()

    app.mainloop.assert_called_once_with()
    assert events == ["identity", "ui"]


def test_pyinstaller_spec_uses_app_icon():
    spec_path = ROOT / "purchase_tagger_app.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "icon='assets/app_icon.ico'" in spec_text


def test_pyinstaller_spec_includes_version_module():
    spec_path = ROOT / "purchase_tagger_app.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "'version'" in spec_text
