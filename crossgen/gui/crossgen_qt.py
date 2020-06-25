from PyQt5.QtCore import (
	QSize,
	QObject,
	QThread,
	pyqtSignal,
)
from PyQt5.QtWidgets import (
	QFrame,
	QMainWindow,
	QApplication,
	QWidget,
	QPushButton,
	QBoxLayout,
	QVBoxLayout,
	QTextEdit,
	QPlainTextEdit,
	QLabel,
	QDesktopWidget,
	QMenuBar,
	QAction,
	QMessageBox,
	QFileDialog,
	QSizePolicy,
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from io import StringIO
import sys
import logging

import crossgen.command
import crossgen.grid
import crossgen.pretty
from crossgen.gui.debug_window import DebugWindow

class CrossgenQt(QMainWindow):
	def __init__(self, app):
		# Setup

		QMainWindow.__init__(self)
		self.app = app
		dim = app.primaryScreen().availableGeometry()
		self.sizeHint = lambda : QSize(dim.width(), dim.height())

		# Attributes

		self.save_path = ""
		self.is_dirty = False
		self.confirm_generate = False # if generated crosswords aren't saved, prompt user
		self.max = 10
		self.batch = 5
		self.words = []
		self.crosswords = []
		self.gen_worker = None
		self.save_worker = None
		self.html = ""
		self.debug_window = None
		self.qt_log_handler = None

		# Build UI

		self._build_main_menu()

		self.layout = QBoxLayout(QBoxLayout.LeftToRight)
		margins = self.layout.contentsMargins()
		margins.setBottom(2)
		self.layout.setContentsMargins(margins)
		self.pane = QWidget()
		self.pane.setLayout(self.layout)

		self.input_pane = self._build_input_pane()
		self.layout.addWidget(self.input_pane)

		self.btn_generate = QPushButton('Generate')
		self.btn_generate.clicked.connect(self.on_generate_pressed)
		self.layout.addWidget(self.btn_generate)

		self.output_pane = self._build_output_pane()
		self.layout.addWidget(self.output_pane)
		
		self.setCentralWidget(self.pane)

		# Post-setup

		self._refresh_window_title()
		self.on_input_changed() # populate status bar with initial status
		self.on_output_changed()

	def _refresh_window_title(self):
		title = "Crossgen "
		if self.save_path != "":
			title += " - " + self.save_path + " "
		if self.is_dirty:
			title += "(*)"
		self.setWindowTitle(title)

	def _build_main_menu(self):
		menubar = self.menuBar()
		file_menu = menubar.addMenu('&File')
		tools_menu = menubar.addMenu('&Tools')

		act_save = QAction('&Save', self) # http://zetcode.com/gui/pyqt5/menustoolbars/
		act_save.setShortcut('Ctrl+S')
		act_save.setStatusTip('Save the generated crosswords')
		act_save.triggered.connect(self.save)
		file_menu.addAction(act_save)

		act_save_as = QAction('&Save As...', self)
		act_save_as.setStatusTip('Save a copy of the generated crosswords')
		act_save_as.triggered.connect(self.save_as)
		file_menu.addAction(act_save_as)

		act_exit = QAction('&Exit', self)
		act_exit.setShortcut('Alt+F4')
		act_exit.setStatusTip('Exit application')
		act_exit.triggered.connect(self.close)
		file_menu.addAction(act_exit)

		act_debug = QAction('&Debug logging', self)
		act_debug.setStatusTip('Show debug output for crossword generation')
		act_debug.triggered.connect(self.show_debug)
		tools_menu.addAction(act_debug)

	def _build_input_pane(self):
		input_layout = QBoxLayout(QBoxLayout.TopToBottom)
		input_pane = QWidget()
		input_pane.setLayout(input_layout)

		input_label = QLabel("Input (list of words, separated by newlines):")
		input_label.setStyleSheet("""font-size: 10pt""")
		input_layout.addWidget(input_label)

		self.text_input = QPlainTextEdit()
		doc = self.text_input.document()
		font = doc.defaultFont()
		font.setFamily("Consolas")
		font.setPointSize(13)
		doc.setDefaultFont(font)
		self.text_input.textChanged.connect(self.on_input_changed)
		input_layout.addWidget(self.text_input)

		self.word_count_label = QLabel("0 words")
		input_layout.addWidget(self.word_count_label)

		return input_pane

	def _build_output_pane(self):
		output_pane = QWidget()
		output_layout = QBoxLayout(QBoxLayout.TopToBottom)
		output_pane.setLayout(output_layout)

		output_label = QLabel("Output:")
		output_label.setStyleSheet("""font-size: 10pt""")
		output_layout.addWidget(output_label)

		#self.output_view = QTextEdit()
		self.output_view = QWebEngineView()
		self.output_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		#self.output_view.setReadOnly(True)
		web_frame = QFrame()
		web_frame.setStyleSheet("""border:1px solid #B9B9B9""") # hack to back output pane have some border colour as input pane
		web_frame_layout = QVBoxLayout()
		web_frame_layout.setSpacing(0)
		web_frame_layout.setContentsMargins(0, 0, 0, 0)
		web_frame.setLayout(web_frame_layout)
		web_frame_layout.addWidget(self.output_view)
		output_layout.addWidget(web_frame)

		self.output_label = QLabel("")
		output_layout.addWidget(self.output_label)

		return output_pane

	def on_input_changed(self):
		text = self.text_input.document().toPlainText()
		lines = text.split("\n")
		self.words = [line.strip() for line in lines if len(line.strip()) > 0]
		word_count = len(self.words)
		label_text = f"{word_count} "
		if word_count == 1:
			label_text += "word"
		else:
			label_text += "words"
		self.word_count_label.setText(label_text)

		if word_count > 0:
			self.statusBar().showMessage("Ready")
		else:
			self.statusBar().showMessage("Enter some words!")

	class GenerateCrosswordsWorker(QThread):
		num_done_updated = pyqtSignal(int)
		finished = pyqtSignal()

		def __init__(self, words, max, batch):
			super().__init__()
			self.words = words
			self.max = max
			self.batch = batch
			self.crosswords = []

		def run(self):
			def progress_callback(num_done):
				self.num_done_updated.emit(num_done)

			self.crosswords = crossgen.command.create_crosswords(words=self.words, max=self.max, batch=self.batch,
					progress_callback=progress_callback)

			self.finished.emit()

	def on_generate_pressed(self):
		if not self.can_generate(): # avoid generating while already generating, and prompt if previous crosswords are unsaved
			return

		self.btn_generate.setEnabled(False)
		words = self.words
		max_crosswords = self.max # it shouldn't be possible for this to change while generating, but just in case

		def update_progress(num_done):
			if num_done == 0:
				self.statusBar().showMessage(f"Could not generate any crosswords with the words given.")
				return

			self.statusBar().showMessage(f"Generated {num_done}/{max_crosswords} crosswords...")

		def on_done_generating():
			self.crosswords = self.gen_worker.crosswords
			self.on_output_changed(self.crosswords, words)
			self.gen_worker = None
			self.btn_generate.setEnabled(True)

		self.gen_worker = CrossgenQt.GenerateCrosswordsWorker(words, max_crosswords, self.batch)
		self.gen_worker.num_done_updated.connect(update_progress)
		self.gen_worker.finished.connect(on_done_generating)
		self.gen_worker.start()

	def on_output_changed(self, crosswords=[], words=[]):
		if len(crosswords) > 0:
			strbuf = StringIO()
			pretty_printer = crossgen.pretty.HtmlGridPrinter(outstream=strbuf)
			pretty_printer.print_crosswords(crosswords, words)
			self.html = strbuf.getvalue()
			self.output_view.setHtml(self.html)
			self.set_dirty(True)

	def set_dirty(self, is_dirty):
		"""Dirty = if the file has been changed since it was last saved"""
		self.is_dirty = is_dirty
		self._refresh_window_title()			

	class SaveCrosswordsWorker(QThread):
		done = pyqtSignal(bool) # bool is_success

		def __init__(self, save_path, html):
			super().__init__()
			self.save_path = save_path
			self.html = html

		def run(self):
			try:
				with open(self.save_path, "w", encoding="utf-8") as f:
					f.write(self.html)
				self.done.emit(True)
			except IOError as err:
				print("Save error:", err, file=sys.stderr)
				self.done.emit(False)

	def can_save(self):
		if self.save_worker is not None:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setWindowTitle("Save Crosswords")
			msg.setText("Not done previous save yet!")			
			msg.setStandardButtons(QMessageBox.Ok)
			msg.exec_()
			return False
		return True

	def save(self):
		if not self.can_save():
			return

		if self.save_path == "":
			self.save_as()
			return

		save_path = self.save_path
		html = self.html

		def done_save(is_success):
			if is_success:
				self.statusBar().showMessage(f"Saved to {save_path}")
				self.set_dirty(False)
			else:
				self.statusBar().showMessage(f"Error: Failed to save to {save_path}")
			self.save_worker = None

		self.save_worker = CrossgenQt.SaveCrosswordsWorker(save_path, html)
		self.save_worker.done.connect(done_save)
		self.save_worker.start()
		self.statusBar().showMessage(f"Saving...")

	def save_as(self):
		if not self.can_save():
			return

		dialog = QFileDialog(self, caption="Save Crosswords", directory="./crosswords.html", filter="HTML files (*.html)")
		dialog.setDefaultSuffix(".html")
		dialog.setFileMode(QFileDialog.AnyFile) # including files that don't exist
		dialog.setAcceptMode(QFileDialog.AcceptSave)

		result = dialog.exec_()
		if not result: # user rejected the save
			return

		file_names = dialog.selectedFiles()
			# output looks something like ("C:/Users/Person/Documents/crosswords.html", 'HTML files (*.html)')
		if len(file_names) == 0:
			return
		self.save_path = file_names[0]
		self.save()

	def closeEvent(self, event):
		"""@Override"""
		if self.can_exit():
			event.accept()
		else:
			event.ignore()

	def can_generate(self):
		if len(self.words) == 0:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setWindowTitle("Generate Crosswords")
			msg.setText("Enter some words first!")			
			msg.setStandardButtons(QMessageBox.Ok)
			msg.exec_()
			return False
		if self.gen_worker is not None:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setWindowTitle("Generate Crosswords")
			msg.setText("Already generating!")			
			msg.setStandardButtons(QMessageBox.Ok)
			msg.exec_()
			return False
		if self.confirm_generate and self.is_dirty:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Information)
			msg.setWindowTitle("Generate Crosswords")
			msg.setText("Current crosswords aren't saved. Generate new crosswords?")			
			msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			retval = msg.exec_()
			if retval == QMessageBox.No:
				return False
		return True

	def can_exit(self):
		if self.is_dirty:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Warning)
			msg.setWindowTitle("Exit Application")
			msg.setText("You have unsaved changes. Are you sure you want to exit?")			
			msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
			retval = msg.exec_()
			if retval == QMessageBox.No:
				return False
		return True

	# https://stackoverflow.com/questions/24469662/how-to-redirect-logger-output-into-pyqt-text-widget
	# https://stackoverflow.com/questions/28655198/best-way-to-display-logs-in-pyqt

	class QtLogHandler(logging.Handler, QObject): # multiple inheritance hack
		logged_msg = pyqtSignal(str)

		def __init__(self):
			logging.Handler.__init__(self)
			QObject.__init__(self)

		def emit(self, record):
			msg = self.format(record) + "\n"
			self.logged_msg.emit(msg)

		def write(self, text):
			self.logged_msg.emit(text)

		def flush(self):
			pass			

	def show_debug(self):
		if self.debug_window is None:
			self.debug_window = DebugWindow(parent=self)
			self.qt_log_handler = self.QtLogHandler()
			formatter = logging.Formatter(fmt=self.debug_window.FORMAT, datefmt=self.debug_window.DATE_FORMAT)
			self.qt_log_handler.setFormatter(formatter)
			self.qt_log_handler.logged_msg.connect(self.debug_window.append_text)

			logging.basicConfig(format=self.debug_window.FORMAT, datefmt=self.debug_window.DATE_FORMAT, level=logging.INFO)
			logging.getLogger().addHandler(self.qt_log_handler)
			logging.getLogger().setLevel(logging.INFO)
			logging.info("Set up logging")

			old_stderr = sys.stderr

			def on_debug_closed():
				sys.stderr = old_stderr
				logging.info("sys.stderr restored back to original value")

			self.debug_window.closed.connect(on_debug_closed)

		if not self.debug_window.isVisible():
			sys.stderr = self.qt_log_handler
			
			logging.info("sys.stderr now prints to the debug window")

			self.debug_window.show()
