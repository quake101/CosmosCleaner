import sys
import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLineEdit, QTableWidget,
                               QTableWidgetItem, QFileDialog, QLabel, QHeaderView,
                               QMessageBox, QCheckBox, QDialog, QListWidget,
                               QInputDialog, QMenu, QTextEdit)
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QAction, QIcon


class NumericTableWidgetItem(QTableWidgetItem):
    """Custom table item that sorts numerically based on stored data"""
    def __lt__(self, other):
        """Compare items numerically using stored UserRole data"""
        try:
            # Get the numeric values stored in UserRole
            self_value = self.data(Qt.UserRole)
            other_value = other.data(Qt.UserRole)

            # If both have numeric data, compare those
            if self_value is not None and other_value is not None:
                return self_value < other_value
        except (TypeError, AttributeError):
            pass

        # Fallback to string comparison
        return super().__lt__(other)


class FolderScanner(QThread):
    """Thread to scan folders without blocking the UI using multiple worker threads"""
    progress = Signal(str, object)  # folder_path, size_in_bytes (as Python int, can be > 32-bit)
    finished = Signal()

    def __init__(self, root_path, target_folders, max_workers=8):
        super().__init__()
        self.root_path = root_path
        self.target_folders = target_folders
        self.max_workers = max_workers
        self.should_stop = False
        self._lock = threading.Lock()
        self._pending_tasks = 0

    def run(self):
        """Scan the root path for target folders using thread pool"""
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._executor = executor
                self._scan_directory_parallel(self.root_path)

                # Wait for all tasks to complete
                while True:
                    with self._lock:
                        if self._pending_tasks == 0:
                            break
                    self.msleep(50)  # Sleep 50ms between checks

        except Exception as e:
            print(f"Error during scan: {e}")
        finally:
            self._executor = None
            self.finished.emit()

    def _scan_directory_parallel(self, directory):
        """Submit directory for scanning"""
        if self.should_stop:
            return

        with self._lock:
            self._pending_tasks += 1

        try:
            self._executor.submit(self._scan_directory_worker, directory)
        except Exception as e:
            with self._lock:
                self._pending_tasks -= 1
            print(f"Error submitting task: {e}")

    def _scan_directory_worker(self, directory):
        """Worker function to scan a single directory"""
        try:
            if self.should_stop:
                return

            path = Path(directory)
            subdirs = []

            # Check all items in directory
            for item in path.iterdir():
                if self.should_stop:
                    return

                if item.is_dir():
                    # Check if this folder name matches our targets
                    if item.name.lower() in self.target_folders:
                        size = self._get_folder_size(item)
                        self.progress.emit(str(item), size)

                    # Collect subdirectories for parallel processing
                    subdirs.append(item)

            # Submit subdirectories for parallel scanning
            for subdir in subdirs:
                if not self.should_stop:
                    self._scan_directory_parallel(subdir)

        except PermissionError:
            # Skip folders we don't have permission to access
            pass
        except Exception as e:
            print(f"Error scanning {directory}: {e}")
        finally:
            with self._lock:
                self._pending_tasks -= 1

    def _get_folder_size(self, folder_path):
        """Calculate total size of folder in bytes"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                if self.should_stop:
                    break
                for filename in filenames:
                    if self.should_stop:
                        break
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        # Skip files we can't access
                        pass
        except Exception as e:
            print(f"Error calculating size for {folder_path}: {e}")

        return total_size

    def stop(self):
        """Stop the scanning process"""
        self.should_stop = True


class FolderDeleter(QThread):
    """Thread to delete folders without blocking the UI"""
    progress = Signal(str, bool, str)  # folder_path, success, error_message
    finished = Signal(list, list)  # deleted_rows, failed_deletions [(path, error), ...]

    def __init__(self, folders_to_delete):
        super().__init__()
        self.folders_to_delete = folders_to_delete  # List of (row, folder_path) tuples
        self.deleted_rows = []
        self.failed_deletions = []

    def run(self):
        """Delete folders and track results"""
        for row, folder_path in self.folders_to_delete:
            try:
                shutil.rmtree(folder_path)
                self.deleted_rows.append(row)
                self.progress.emit(folder_path, True, "")
            except Exception as e:
                error_msg = str(e)
                self.failed_deletions.append((folder_path, error_msg))
                self.progress.emit(folder_path, False, error_msg)

        self.finished.emit(self.deleted_rows, self.failed_deletions)


class CleanupProgressDialog(QDialog):
    """Dialog to show cleanup progress"""
    def __init__(self, total_folders, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cleaning Folders")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(200)
        self.total_folders = total_folders
        self.completed = 0
        self.init_ui()

    def init_ui(self):
        """Initialize the progress dialog UI"""
        layout = QVBoxLayout(self)

        # Progress label
        self.progress_label = QLabel(f"Deleting folders: 0 / {self.total_folders}")
        layout.addWidget(self.progress_label)

        # Current folder label
        self.current_label = QLabel("Preparing...")
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)

        # Status text area
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

    def update_progress(self, folder_path, success, error_message):
        """Update progress with folder deletion result"""
        self.completed += 1
        self.progress_label.setText(f"Deleting folders: {self.completed} / {self.total_folders}")

        if success:
            self.status_text.append(f"Deleted: {folder_path}")
            self.current_label.setText(f"Successfully deleted: {folder_path}")
        else:
            self.status_text.append(f"Failed: {folder_path}\n  Error: {error_message}")
            self.current_label.setText(f"Failed to delete: {folder_path}")

    def cleanup_complete(self):
        """Mark cleanup as complete"""
        self.current_label.setText("Cleanup complete!")
        self.progress_label.setText(f"Completed: {self.completed} / {self.total_folders}")


class OptionsDialog(QDialog):
    """Dialog for managing target folder names"""
    def __init__(self, current_folders, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options - Target Folders")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        self.folder_list = list(current_folders)
        self.init_ui()

    def init_ui(self):
        """Initialize the options dialog UI"""
        layout = QVBoxLayout(self)

        # Instructions
        label = QLabel("Manage the list of folder names to scan for:")
        layout.addWidget(label)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.folder_list)
        layout.addWidget(self.list_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_folder)
        button_layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self.edit_folder)
        button_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_folder)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)

        # OK/Cancel buttons
        ok_cancel_layout = QHBoxLayout()
        ok_cancel_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        ok_cancel_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        ok_cancel_layout.addWidget(self.cancel_button)

        layout.addLayout(ok_cancel_layout)

    def add_folder(self):
        """Add a new folder name to the list"""
        text, ok = QInputDialog.getText(self, "Add Folder Name", "Enter folder name:")
        if ok and text.strip():
            folder_name = text.strip().lower()
            if folder_name not in self.folder_list:
                self.folder_list.append(folder_name)
                self.list_widget.addItem(folder_name)
            else:
                QMessageBox.warning(self, "Duplicate", "This folder name already exists in the list.")

    def edit_folder(self):
        """Edit the selected folder name"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a folder name to edit.")
            return

        current_text = current_item.text()
        text, ok = QInputDialog.getText(self, "Edit Folder Name", "Enter folder name:", text=current_text)
        if ok and text.strip():
            folder_name = text.strip().lower()
            if folder_name != current_text and folder_name in self.folder_list:
                QMessageBox.warning(self, "Duplicate", "This folder name already exists in the list.")
                return

            # Update the list
            row = self.list_widget.currentRow()
            self.folder_list[row] = folder_name
            current_item.setText(folder_name)

    def delete_folder(self):
        """Delete the selected folder name"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a folder name to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to remove '{current_item.text()}' from the list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            row = self.list_widget.currentRow()
            self.folder_list.pop(row)
            self.list_widget.takeItem(row)

    def get_folders(self):
        """Return the updated folder list"""
        return self.folder_list


class MainUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scanner_thread = None
        self.deleter_thread = None
        self.settings = QSettings('CosmosCleaner', 'CosmosCleaner')
        self.scan_dot_count = 0  # For animated scanning dots
        self.scan_folder_count = 0  # Track number of folders found

        # Timer for animating scanning dots
        self.scan_animation_timer = QTimer(self)
        self.scan_animation_timer.timeout.connect(self.update_scan_animation)

        # Load target folders from settings or use defaults
        default_folders = ['calibrated', 'debayered', 'logs', 'registered', 'fastIntegration', 'process']
        saved_folders = self.settings.value('target_folders', default_folders)
        self.target_folders = saved_folders if isinstance(saved_folders, list) else default_folders

        self.init_ui()

        # Load previously saved folder path
        saved_folder = self.settings.value('last_root_folder', '')
        if saved_folder and os.path.exists(saved_folder):
            self.folder_input.setText(saved_folder)

    @staticmethod
    def format_size(size_bytes):
        """Format bytes into human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Cosmos Cleaner")
        self.setGeometry(100, 100, 900, 600)

        # Set application icon
        icon_path = os.path.join(os.path.dirname(__file__), 'images', 'CosmosCleaner.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Create menu bar
        menubar = self.menuBar()

        # Options menu
        options_action = QAction("Options", self)
        options_action.triggered.connect(self.open_options)
        menubar.addAction(options_action)

        # About menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.open_about)
        menubar.addAction(about_action)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Folder selection section
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Root Folder:")
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select a folder to scan...")
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_folder)

        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.browse_button)

        # Scan button
        self.scan_button = QPushButton("Start Scan")
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setEnabled(False)

        # Status label
        self.status_label = QLabel("Select a folder to begin")

        # Clean controls section
        clean_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.toggled.connect(self.on_select_all_changed)
        self.select_all_checkbox.setEnabled(False)
        self.clean_button = QPushButton("Clean Selected Folders")
        self.clean_button.clicked.connect(self.clean_selected_folders)
        self.clean_button.setEnabled(False)
        self.clean_button.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }")

        clean_layout.addWidget(self.select_all_checkbox)
        clean_layout.addStretch()
        clean_layout.addWidget(self.clean_button)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Select", "Folder Path", "Size"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)

        # Add widgets to main layout
        main_layout.addLayout(folder_layout)
        main_layout.addWidget(self.scan_button)
        main_layout.addWidget(self.status_label)
        main_layout.addLayout(clean_layout)
        main_layout.addWidget(self.results_table)

        # Connect folder input changes
        self.folder_input.textChanged.connect(self.on_folder_changed)

    def browse_folder(self):
        """Open folder selection dialog"""
        # Start from last saved folder if available
        start_dir = self.settings.value('last_root_folder', '')
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Root Folder to Scan",
            start_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder:
            self.folder_input.setText(folder)
            # Save the selected folder
            self.settings.setValue('last_root_folder', folder)

    def on_folder_changed(self, text):
        """Enable/disable scan button based on folder input"""
        self.scan_button.setEnabled(bool(text.strip()))

    def start_scan(self):
        """Start the folder scanning process"""
        root_path = self.folder_input.text().strip()

        if not root_path:
            QMessageBox.warning(self, "No Folder", "Please select a folder to scan.")
            return

        if not os.path.exists(root_path):
            QMessageBox.warning(self, "Invalid Folder", "The selected folder does not exist.")
            return

        if not os.path.isdir(root_path):
            QMessageBox.warning(self, "Invalid Folder", "The selected path is not a folder.")
            return

        # Clear previous results
        self.results_table.setRowCount(0)
        self.results_table.setSortingEnabled(False)

        # Reset scan animation counter and folder count
        self.scan_dot_count = 0
        self.scan_folder_count = 0

        # Update UI state
        self.scan_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.folder_input.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.select_all_checkbox.setChecked(False)
        self.clean_button.setEnabled(False)
        self.status_label.setText("Scanning. Please wait.")

        # Start animation timer (update every 500ms)
        self.scan_animation_timer.start(500)

        # Start scanner thread
        self.scanner_thread = FolderScanner(root_path, self.target_folders)
        self.scanner_thread.progress.connect(self.on_scan_progress)
        self.scanner_thread.finished.connect(self.on_scan_finished)
        self.scanner_thread.start()

    def on_scan_progress(self, folder_path, size_bytes):
        """Handle progress updates from scanner thread"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # Checkbox
        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox { margin-left: 5px; }")
        self.results_table.setCellWidget(row, 0, checkbox)

        # Folder path
        path_item = QTableWidgetItem(folder_path)
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
        self.results_table.setItem(row, 1, path_item)

        # Size (human readable)
        size_item = NumericTableWidgetItem(self.format_size(size_bytes))
        size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
        # Store the bytes value as user data for sorting
        size_item.setData(Qt.UserRole, size_bytes)
        self.results_table.setItem(row, 2, size_item)

        # Update folder count (the timer will update the status label)
        self.scan_folder_count = row + 1

    def update_scan_animation(self):
        """Update the scanning status label with animated dots"""
        self.scan_dot_count = (self.scan_dot_count + 1) % 3
        dots = "." * (self.scan_dot_count + 1)
        if self.scan_folder_count > 0:
            self.status_label.setText(f"Scanning{dots} Found {self.scan_folder_count} folder(s)")
        else:
            self.status_label.setText(f"Scanning{dots} Please wait.")

    def on_scan_finished(self):
        """Handle scan completion"""
        # Stop animation timer
        self.scan_animation_timer.stop()

        # Re-enable UI elements
        self.scan_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.folder_input.setEnabled(True)

        # Update status
        row_count = self.results_table.rowCount()
        if row_count == 0:
            self.status_label.setText("Scan complete. No matching folders found.")
            self.select_all_checkbox.setEnabled(False)
            self.clean_button.setEnabled(False)
        else:
            # Calculate total size from stored user data
            total_bytes = 0
            for row in range(row_count):
                size_item = self.results_table.item(row, 2)  # Column 2 is size
                total_bytes += size_item.data(Qt.UserRole)

            total_size_formatted = self.format_size(total_bytes)
            self.status_label.setText(
                f"Scan complete. Found {row_count} folder(s) - Total size: {total_size_formatted}"
            )
            self.select_all_checkbox.setEnabled(True)
            self.clean_button.setEnabled(True)

        # Enable sorting after scan is complete
        self.results_table.setSortingEnabled(True)
        # Set default sort by folder path (column 1)
        self.results_table.sortItems(1, Qt.AscendingOrder)

        # Clean up thread
        if self.scanner_thread:
            self.scanner_thread.wait()
            self.scanner_thread = None

    def on_select_all_changed(self, checked):
        """Handle select all checkbox state change"""
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and isinstance(checkbox, QCheckBox):
                checkbox.setChecked(checked)

    def clean_selected_folders(self):
        """Delete selected folders using a background thread"""
        # Collect selected folders
        selected_folders = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                folder_path = self.results_table.item(row, 1).text()
                selected_folders.append((row, folder_path))

        if not selected_folders:
            QMessageBox.information(self, "No Selection", "Please select at least one folder to clean.")
            return

        # Confirm deletion
        folder_count = len(selected_folders)
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete {folder_count} folder(s)?\n\nThis action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Disable UI during cleanup
        self.clean_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)

        # Create and show progress dialog
        self.progress_dialog = CleanupProgressDialog(folder_count, self)
        self.progress_dialog.show()

        # Start deletion thread
        self.deleter_thread = FolderDeleter(selected_folders)
        self.deleter_thread.progress.connect(self.on_delete_progress)
        self.deleter_thread.finished.connect(self.on_delete_finished)
        self.deleter_thread.start()

    def on_delete_progress(self, folder_path, success, error_message):
        """Handle progress updates from deletion thread"""
        self.progress_dialog.update_progress(folder_path, success, error_message)

    def on_delete_finished(self, deleted_rows, failed_deletions):
        """Handle deletion completion"""
        # Mark progress dialog as complete
        self.progress_dialog.cleanup_complete()

        # Remove deleted folders from table (in reverse order to maintain indices)
        for row in sorted(deleted_rows, reverse=True):
            self.results_table.removeRow(row)

        # Update select all checkbox state
        self.select_all_checkbox.setChecked(False)

        # Re-enable UI elements
        self.scan_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)

        # Update status and show results
        remaining_count = self.results_table.rowCount()
        if remaining_count == 0:
            self.status_label.setText("All folders cleaned.")
            self.clean_button.setEnabled(False)
        else:
            # Recalculate total size
            total_bytes = 0
            for row in range(remaining_count):
                size_item = self.results_table.item(row, 2)
                total_bytes += size_item.data(Qt.UserRole)

            total_size_formatted = self.format_size(total_bytes)
            self.status_label.setText(
                f"Cleaned {len(deleted_rows)} folder(s). Remaining: {remaining_count} folder(s) - Total size: {total_size_formatted}"
            )
            self.clean_button.setEnabled(True)

        # Clean up thread
        if self.deleter_thread:
            self.deleter_thread.wait()
            self.deleter_thread = None

        # Show error summary if any deletions failed
        if failed_deletions:
            error_msg = "Some folders could not be deleted:\n\n"
            for folder_path, error in failed_deletions[:5]:  # Show first 5 errors
                error_msg += f"{folder_path}\n  Error: {error}\n\n"
            if len(failed_deletions) > 5:
                error_msg += f"...and {len(failed_deletions) - 5} more"

            QMessageBox.warning(self, "Deletion Errors", error_msg)
        elif deleted_rows:
            QMessageBox.information(
                self,
                "Success",
                f"Successfully deleted {len(deleted_rows)} folder(s)."
            )

    def closeEvent(self, event):
        """Handle window close event"""
        if self.scanner_thread and self.scanner_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Scan in Progress",
                "A scan is currently running. Do you want to stop it and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.scanner_thread.stop()
                self.scanner_thread.wait()
                event.accept()
            else:
                event.ignore()
        elif self.deleter_thread and self.deleter_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Cleanup in Progress",
                "A cleanup operation is currently running. Do you want to wait for it to finish before exiting?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.deleter_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def open_options(self):
        """Open the options dialog"""
        dialog = OptionsDialog(self.target_folders, self)
        if dialog.exec() == QDialog.Accepted:
            # Update target folders
            new_folders = dialog.get_folders()
            if new_folders:
                self.target_folders = new_folders
                # Save to settings
                self.settings.setValue('target_folders', self.target_folders)
                QMessageBox.information(
                    self,
                    "Options Saved",
                    "Target folder list has been updated. Changes will apply to the next scan."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Empty List",
                    "The target folder list cannot be empty. Changes were not saved."
                )

    def open_about(self):
        """Open the about dialog"""
        about_box = QMessageBox(self)
        about_box.setWindowTitle("About Cosmos Cleaner")
        about_box.setTextFormat(Qt.RichText)
        about_box.setText("<h2>Cosmos Cleaner</h2>"
                          "<p>A simple tool for scanning and cleaning up processing data folders.</p>"
                          "<p><a href='https://github.com/quake101/CosmosCleaner'>github.com/quake101/CosmosCleaner</a></p>")

        # Set icon for the about dialog
        icon_path = os.path.join(os.path.dirname(__file__), 'images', 'CosmosCleaner.png')
        if os.path.exists(icon_path):
            about_box.setWindowIcon(QIcon(icon_path))

        about_box.exec()


def main():
    app = QApplication(sys.argv)

    # Set application icon
    icon_path = os.path.join(os.path.dirname(__file__), 'images', 'CosmosCleaner.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
