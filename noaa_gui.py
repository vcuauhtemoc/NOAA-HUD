from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import *
from noaa_gui_screen1 import Ui_MainWindow
import noaa
import sys

# TODO:
#   1. Create exceptions for badly formatted zipcode.
#   1. Display loading message as db is built.
#   2. Hide loading message, display graph with all weather attributes graphed.
#   3. link checkboxes to each weather attribute, so unchecking hides the attribute from the graph.
#   4. Add a comfirm button, which replaces checkbox with a current conditions display.

class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.stacked_widget = self.ui.stackedWidget
        self.line_edit = self.ui.lineEdit

        #changes to the next page in the HUD after entering a zipcode.
        self.line_edit.returnPressed.connect(lambda: self.next_page())
    def next_page(self):

        self.stacked_widget.setCurrentIndex(1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())