import sys

from PySide6.QtWidgets import QApplication

import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow.MainWindow()
    window.show()
    sys.exit(app.exec())