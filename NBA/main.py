import sys
from PyQt5.QtWidgets import QApplication
from draft_gui import DraftSimulator


def main():
    app = QApplication(sys.argv)
    # Apply a stylesheet for better aesthetics
    app.setStyle("Fusion")
    stylesheet = """
        QMainWindow {
            background-color: #2E2E2E;
            color: #FFFFFF;
        }
        QLabel {
            color: #FFFFFF;
        }
        QListWidget {
            background-color: #3C3C3C;
            color: #FFFFFF;
            border: 1px solid #555555;
            padding: 5px;
        }
        QTableWidget {
            background-color: #3C3C3C;
            color: #FFFFFF;
            gridline-color: #555555;
        }
        QHeaderView::section {
            background-color: #555555;
            color: #FFFFFF;
            padding: 6px;
            border: 1px solid #2E2E2E;
            font-size: 14px;
        }
        QPushButton {
            font-size: 16px;
        }
        QComboBox {
            background-color: #555555;
            color: #FFFFFF;
            padding: 5px;
            border-radius: 3px;
        }
        QLineEdit {
            background-color: #555555;
            color: #FFFFFF;
            padding: 5px;
            border-radius: 3px;
        }
    """
    app.setStyleSheet(stylesheet)
    simulator = DraftSimulator()
    simulator.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
