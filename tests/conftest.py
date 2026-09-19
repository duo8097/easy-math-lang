"""Shared Qt application for editor tests (single instance per session)."""

import os

import pytest


@pytest.fixture(scope='session')
def qapp():
    pytest.importorskip('PySide6')
    if not os.environ.get('DISPLAY'):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app
