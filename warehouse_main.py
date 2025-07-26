import sys
import matplotlib

matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QLineEdit,
    QFormLayout, QMessageBox, QHBoxLayout, QGridLayout, QPushButton,
    QScrollArea, QFrame, QDialog, QComboBox, QGroupBox, QCheckBox
)
from PyQt6.QtGui import QDoubleValidator, QIntValidator, QFont
from PyQt6.QtCore import Qt

# 添加字体配置
matplotlib.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题
# 全局配置
DEFAULT_THRESHOLD = 2.0
WARNING_COLOR = "red"
WARNING_TEXT = "⚠️ 低库存"


# 自定义图表画布
class MplCanvas(FigureCanvas):
    def __init__(self, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['bottom'].set_visible(True)
        self.axes.spines['left'].set_visible(True)
        self.axes.spines['right'].set_visible(True)


# 工具函数
def shorten_spec(spec):
    parts = spec.split('×')
    if len(parts) == 3:
        return f"{float(parts[0]):.3f}×{float(parts[1]):.3f}×{float(parts[2]):.3f}"  # 改为三位小数
    return spec


def sort_by_thickness(data):
    def get_thickness(spec):
        parts = spec.split('×')
        return float(parts[2]) * 100 if len(parts) == 3 else 0

    return sorted(data, key=lambda x: get_thickness(x[0]))


# 预警设置对话框
class SettingsDialog(QDialog):
    def __init__(self, current_threshold, current_enabled, parent=None):
        super().__init__(parent)
        self.setWindowTitle("库存预警设置")
        self.threshold = current_threshold
        self.enabled = current_enabled

        self.threshold_input = QLineEdit(str(current_threshold))
        self.threshold_input.setValidator(QDoubleValidator(0.001, 100.0, 3))
        self.enable_checkbox = QCheckBox("启用库存预警功能")
        self.enable_checkbox.setChecked(current_enabled)

        self.ok_btn = QPushButton("确认")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        form_layout = QFormLayout()
        form_layout.addRow("预警阈值（方）：", self.threshold_input)
        form_layout.addRow(self.enable_checkbox)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def accept(self):
        try:
            self.threshold = float(self.threshold_input.text())
            self.enabled = self.enable_checkbox.isChecked()
            super().accept()
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的阈值数值")


# 添加仓位对话框
class AddWarehouseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加新仓位")
        self.warehouse_name = ""

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("请输入仓位名称，如：仓位 F")

        self.ok_btn = QPushButton("确认")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        form_layout = QFormLayout()
        form_layout.addRow("仓位名称：", self.name_input)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "输入错误", "请输入仓位名称")
            return
        self.warehouse_name = name
        super().accept()


# 存入对话框
class StoreDialog(QDialog):
    def __init__(self, mode="存入"):
        super().__init__()
        self.setWindowTitle(f"{mode}板材")
        self.spec = ""
        self.volume = 0.0

        self.length_input = QLineEdit()
        self.width_input = QLineEdit()
        self.height_input = QLineEdit()
        self.length_input.setValidator(QDoubleValidator(0.001, 100.0, 3))
        self.width_input.setValidator(QDoubleValidator(0.001, 100.0, 3))
        self.height_input.setValidator(QDoubleValidator(0.001, 100.0, 3))

        self.dong_input = QLineEdit("0")
        self.bao_input = QLineEdit("0")
        self.zhang_input = QLineEdit("0")
        self.dong_input.setValidator(QIntValidator(0, 10000))
        self.bao_input.setValidator(QIntValidator(0, 10000))
        self.zhang_input.setValidator(QIntValidator(0, 10000))

        form_layout = QFormLayout()
        form_layout.addRow("长度 (m):", self.length_input)
        form_layout.addRow("宽度 (m):", self.width_input)
        form_layout.addRow("厚度 (m):", self.height_input)
        form_layout.addRow("栋:", self.dong_input)
        form_layout.addRow("包:", self.bao_input)
        form_layout.addRow("张:", self.zhang_input)

        self.result_label = QLabel("方数: 0.000")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.calc_button = QPushButton("计算")
        self.calc_button.clicked.connect(self.calculate_volume)

        self.ok_button = QPushButton("确认")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.calc_button)
        btn_layout.addWidget(self.ok_button)
        btn_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.result_label)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def calculate_volume(self):
        try:
            length = float(self.length_input.text()) if self.length_input.text() else 0
            width = float(self.width_input.text()) if self.width_input.text() else 0
            height = float(self.height_input.text()) if self.height_input.text() else 0
            dong = int(self.dong_input.text()) if self.dong_input.text() else 0
            bao = int(self.bao_input.text()) if self.bao_input.text() else 0
            zhang = int(self.zhang_input.text()) if self.zhang_input.text() else 0

            if length <= 0 or width <= 0 or height <= 0:
                QMessageBox.warning(self, "错误", "长、宽、高必须大于0")
                return

            if dong == 0 and bao == 0 and zhang == 0:
                QMessageBox.warning(self, "错误", "至少需要输入一个数量")
                return

            spec = f"{length:.3f}×{width:.3f}×{height:.3f}"
            quantity = dong * bao * zhang
            volume = round(length * width * height * quantity, 3)
            self.spec = spec
            self.volume = volume
            self.result_label.setText(f"规格: {spec}\n总方数: {volume:.3f} 方")
        except ValueError:
            QMessageBox.warning(self, "错误", "请正确填写所有数值")


# 取用对话框
class TakeDialog(QDialog):
    def __init__(self, available_specs, mode="取用"):
        super().__init__()
        self.setWindowTitle(f"{mode}板材")
        self.spec = ""
        self.volume = 0.0
        self.available_specs = available_specs
        self.spec_details = {}

        for spec in available_specs:
            parts = spec.split('×')
            if len(parts) == 3:
                self.spec_details[spec] = (float(parts[0]), float(parts[1]), float(parts[2]))

        self.spec_combo = QComboBox()
        self.spec_combo.addItems(available_specs)
        self.spec_combo.currentTextChanged.connect(self.on_spec_changed)

        self.dong_input = QLineEdit("0")
        self.bao_input = QLineEdit("0")
        self.zhang_input = QLineEdit("0")
        self.dong_input.setValidator(QIntValidator(0, 10000))
        self.bao_input.setValidator(QIntValidator(0, 10000))
        self.zhang_input.setValidator(QIntValidator(0, 10000))

        form_layout = QFormLayout()
        form_layout.addRow("选择规格:", self.spec_combo)
        form_layout.addRow("栋:", self.dong_input)
        form_layout.addRow("包:", self.bao_input)
        form_layout.addRow("张:", self.zhang_input)

        self.result_label = QLabel("方数: 0.000")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.calc_button = QPushButton("计算")
        self.calc_button.clicked.connect(self.calculate_volume)

        self.ok_button = QPushButton("确认")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.calc_button)
        btn_layout.addWidget(self.ok_button)
        btn_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.result_label)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        if available_specs:
            self.on_spec_changed(available_specs[0])

    def on_spec_changed(self, spec):
        if spec in self.spec_details:
            length, width, height = self.spec_details[spec]
            self.result_label.setText(f"规格: {spec}\n尺寸: {length}×{width}×{height}m")
            self.spec = spec
            self.calculate_volume()

    def calculate_volume(self):
        try:
            spec = self.spec_combo.currentText()
            if not spec or spec not in self.spec_details:
                return

            length, width, height = self.spec_details[spec]
            dong = int(self.dong_input.text()) if self.dong_input.text() else 0
            bao = int(self.bao_input.text()) if self.bao_input.text() else 0
            zhang = int(self.zhang_input.text()) if self.zhang_input.text() else 0

            if dong == 0 and bao == 0 and zhang == 0:
                QMessageBox.warning(self, "错误", "至少需要输入一个数量")
                return

            quantity = dong * bao * zhang
            volume = round(length * width * height * quantity, 3)
            self.spec = spec
            self.volume = volume
            self.result_label.setText(f"规格: {spec}\n总方数: {volume:.3f} 方")
        except ValueError:
            QMessageBox.warning(self, "错误", "请正确填写所有数值")


# 仓位详情弹窗
class WarehouseDetailDialog(QDialog):
    def __init__(self, name, board_data, warehouse_widget, parent=None):
        super().__init__(parent)
        self.name = name
        self.board_data = board_data
        self.warehouse_widget = warehouse_widget
        self.parent_window = parent
        self.setWindowTitle(f"{name}-仓位详情")
        self.resize(900, 550)

        self.warning_threshold = parent.warning_threshold if parent else DEFAULT_THRESHOLD
        self.warning_enabled = parent.warning_enabled if parent else True

        main_layout = QVBoxLayout(self)

        self.warning_group = QGroupBox(f"库存预警（低于 {self.warning_threshold} 方）")
        self.warning_layout = QVBoxLayout()
        self.warning_group.setLayout(self.warning_layout)
        main_layout.addWidget(self.warning_group)
        self.update_warning_visibility()

        data_chart_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        title_label = QLabel(f"{name}的详细库存")
        title_label.setFont(QFont("Arial", 13, weight=QFont.Weight.Bold))
        left_layout.addWidget(title_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        left_layout.addWidget(line)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        left_layout.addWidget(self.scroll_area)

        left_layout.addStretch()

        right_layout = QVBoxLayout()
        chart_title = QLabel("本仓位储量分布")
        chart_title.setFont(QFont("Arial", 12, weight=QFont.Weight.Bold))
        right_layout.addWidget(chart_title)

        self.canvas = MplCanvas(width=5, height=3.5, dpi=100)
        self.update_chart()
        right_layout.addWidget(self.canvas)

        data_chart_layout.addLayout(left_layout, stretch=1)
        data_chart_layout.addLayout(right_layout, stretch=2)
        main_layout.addLayout(data_chart_layout)

        button_layout = QHBoxLayout()
        store_btn = QPushButton("存入")
        take_btn = QPushButton("取用")
        close_btn = QPushButton("关闭")
        store_btn.clicked.connect(self.handle_store)
        take_btn.clicked.connect(self.handle_take)
        close_btn.clicked.connect(self.close)

        store_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        take_btn.setStyleSheet("background-color: #f44336; color: white;")

        button_layout.addWidget(store_btn)
        button_layout.addWidget(take_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.update_data_labels()
        self.update_warning_display()

    def update_warning_visibility(self):
        self.warning_group.setVisible(self.warning_enabled)

    def update_warning_display(self):
        if not self.warning_enabled:
            return

        while self.warning_layout.count():
            item = self.warning_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        low_stock_items = [(spec, vol) for spec, vol in self.board_data
                           if vol < self.warning_threshold]

        if not low_stock_items:
            self.warning_layout.addWidget(QLabel("当前无低库存项目"))
        else:
            for spec, vol in low_stock_items:
                self.warning_layout.addWidget(QLabel(f"⚠️ {spec}: {vol:.3f}方（低于预警值）"))

    def update_chart(self):
        self.canvas.axes.clear()
        self.canvas.axes.spines['top'].set_visible(False)

        sorted_boards = sort_by_thickness(self.board_data)
        specs = [shorten_spec(spec) for spec, _ in sorted_boards]
        volumes = [volume for _, volume in sorted_boards]

        # 修复：确保规格标签不为空
        specs = [s if s else "未知规格" for s in specs]

        colors = []
        for spec, volume in sorted_boards:
            if self.warning_enabled and volume < self.warning_threshold:
                colors.append('red')
            else:
                colors.append(plt.cm.Pastel1.colors[0])

        x_pos = range(len(specs))
        self.canvas.axes.bar(x_pos, volumes, width=0.6, color=colors)
        self.canvas.axes.set_xticks(x_pos)
        self.canvas.axes.set_xticklabels(
            specs,
            rotation=45,
            ha='right',
            fontsize=7,
            fontproperties = "SimHei"  # 强制指定字体
        )

        self.canvas.axes.set_ylabel('储量（方）', fontsize=9, fontweight='bold')
        self.canvas.axes.tick_params(axis='y', labelsize=8)

        if self.warning_enabled:
            self.canvas.axes.axhline(
                y=self.warning_threshold,
                color='r',
                linestyle='--',
                alpha=0.5,
                label=f'预警线 ({self.warning_threshold}方)'
            )
            self.canvas.axes.legend(fontsize=7)

        # 修复1：数字精确到三位小数
        for i, v in enumerate(volumes):
            self.canvas.axes.text(
                i, v + 0.1,
                f'{v:.3f}',  # 改为三位小数
                ha='center',
                fontsize=8
            )

        # 调整底部边距，防止标签被截断
        self.canvas.fig.subplots_adjust(bottom=0.45)
        self.canvas.fig.suptitle("各规格储量对比", y=0.95, fontsize=10)
        self.canvas.fig.tight_layout()
        self.canvas.draw()

    def update_data_labels(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sorted_boards = sort_by_thickness(self.board_data)
        for spec, volume in sorted_boards:
            label = QLabel(f"规格：{spec}  数量：{volume:.3f}方")
            if self.warning_enabled and volume < self.warning_threshold:
                label.setStyleSheet(f"color: {WARNING_COLOR}; font-weight: bold;")
            else:
                label.setStyleSheet("border: none;")
            self.scroll_layout.addWidget(label)

        self.scroll_layout.addStretch()

    def handle_store(self):
        try:
            dialog = StoreDialog("存入")
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.volume > 0:
                found = False
                for i, (spec, volume) in enumerate(self.board_data):
                    if spec == dialog.spec:
                        self.board_data[i] = (spec, volume + dialog.volume)
                        found = True
                        break
                if not found:
                    self.board_data.append((dialog.spec, dialog.volume))

                self.update_data_labels()
                self.update_chart()
                self.update_warning_display()
                if self.warehouse_widget:
                    self.warehouse_widget.update_display()
                if self.parent_window:
                    self.parent_window.update_total_stats()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"存入操作失败: {str(e)}")

    def handle_take(self):
        try:
            available_specs = [spec for spec, _ in self.board_data]
            if not available_specs:
                QMessageBox.information(self, "提示", "该仓位没有可取用的板材")
                return

            dialog = TakeDialog(available_specs, "取用")
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.volume > 0:
                for i, (spec, volume) in enumerate(self.board_data):
                    if spec == dialog.spec:
                        if volume >= dialog.volume:
                            new_volume = volume - dialog.volume
                            if new_volume <= 0:
                                del self.board_data[i]
                            else:
                                self.board_data[i] = (spec, new_volume)
                            break
                        else:
                            QMessageBox.warning(self, "错误", "库存不足，无法完成取用操作")
                            return

            self.update_data_labels()
            self.update_chart()
            self.update_warning_display()
            if self.warehouse_widget:
                self.warehouse_widget.update_display()
            if self.parent_window:
                self.parent_window.update_total_stats()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"取用操作失败: {str(e)}")


# 仓位模块组件
class WarehouseWidget(QFrame):
    def __init__(self, name, board_data, parent=None):
        super().__init__(parent)
        self.name = name
        self.board_data = board_data
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #888888;
                border-radius: 10px;
                padding: 10px;
                margin: 6px;
            }
            QFrame:hover {
                border-color: #555555;
            }
            QFrame#low_stock {
                border-color: red;
                border-width: 2px;
            }
        """)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(8)

        self.name_label = QLabel(self.name)
        self.name_label.setFont(QFont("Arial", 14, weight=QFont.Weight.Bold))
        self.name_label.setStyleSheet("border: none;")
        self.main_layout.addWidget(self.name_label)

        self.update_display()

    def update_display(self):
        while self.main_layout.count() > 1:
            item = self.main_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        warning_enabled = self.parent_window.warning_enabled if self.parent_window else True
        warning_threshold = self.parent_window.warning_threshold if self.parent_window else DEFAULT_THRESHOLD

        has_low_stock = warning_enabled and any(
            vol < warning_threshold for _, vol in self.board_data
        )

        if has_low_stock:
            self.setObjectName("low_stock")
            self.name_label.setText(f"{self.name} {WARNING_TEXT}")
            self.name_label.setStyleSheet("border: none; color: red;")
        else:
            self.setObjectName("")
            self.name_label.setText(self.name)
            self.name_label.setStyleSheet("border: none;")

        sorted_boards = sort_by_thickness(self.board_data)
        for spec, volume in sorted_boards:
            label = QLabel(f"{spec}: {volume:.3f}方")  # 三位小数
            label.setFont(QFont("Arial", 10))
            if warning_enabled and volume < warning_threshold:
                label.setStyleSheet(f"color: {WARNING_COLOR};")
            else:
                label.setStyleSheet("border: none;")
            self.main_layout.addWidget(label)

        self.main_layout.addStretch()

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                dialog = WarehouseDetailDialog(
                    self.name,
                    self.board_data,
                    self,
                    self.parent_window
                )
                dialog.exec()
            super().mousePressEvent(event)
        except Exception as e:
            print(f"点击事件错误: {str(e)}")


# 总统计图表组件
class StatsChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.canvas = MplCanvas(width=6, height=3, dpi=100)
        self.layout.addWidget(self.canvas)

    def update_chart(self, data):
        self.canvas.axes.clear()
        self.canvas.axes.spines['top'].set_visible(False)

        warning_enabled = self.parent_window.warning_enabled if self.parent_window else True
        warning_threshold = self.parent_window.warning_threshold if self.parent_window else DEFAULT_THRESHOLD

        sorted_items = sort_by_thickness(list(data.items()))
        specs = [shorten_spec(spec) for spec, _ in sorted_items]
        volumes = [volume for _, volume in sorted_items]

        # 修复：确保规格标签不为空
        specs = [s if s else "未知规格" for s in specs]

        colors = []
        for spec, vol in sorted_items:
            if warning_enabled and vol < warning_threshold:
                colors.append('red')
            else:
                colors.append(plt.cm.Set2.colors[0])

        x_pos = range(len(specs))
        self.canvas.axes.bar(x_pos, volumes, width=0.5, color=colors)
        self.canvas.axes.set_xticks(x_pos)
        self.canvas.axes.set_xticklabels(
            specs,
            rotation=30,
            ha='right',
            fontsize=7,
            fontproperties = "SimHei"  # 强制指定字体
        )

        self.canvas.axes.set_ylabel('总储量（方）', fontsize=9, fontweight='bold')
        self.canvas.axes.set_title('各规格板材总储量对比', pad=10, fontsize=10)
        self.canvas.axes.tick_params(axis='both', labelsize=8)

        if warning_enabled:
            self.canvas.axes.axhline(
                y=warning_threshold,
                color='r',
                linestyle='--',
                alpha=0.5,
                label=f'预警线 ({warning_threshold}方)'
            )
            self.canvas.axes.legend(fontsize=7)

        # 修复1：数字精确到三位小数
        for i, v in enumerate(volumes):
            self.canvas.axes.text(
                i, v + 0.1,
                f'{v:.3f}',  # 改为三位小数
                ha='center',
                fontsize=8
            )

        # 调整底部边距，防止标签被截断
        self.canvas.fig.subplots_adjust(bottom=0.45)
        self.canvas.draw()


# 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("仓位管理系统")
        self.resize(1200, 750)

        self.warning_threshold = DEFAULT_THRESHOLD
        self.warning_enabled = True

        self.warehouse_data = [
            ("仓位 A", [("1.220×2.440×0.018", 3.216), ("1.830×0.915×0.009", 1.235)]),
            ("仓位 B", [("1.220×2.440×0.015", 5.781)]),
            ("仓位 C", [("1.220×2.440×0.025", 2.120), ("1.830×0.915×0.012", 0.938)]),
            ("仓位 D", [("1.220×2.440×0.030", 4.520), ("1.830×0.915×0.018", 1.562)]),
            ("仓位 E", [("1.220×2.440×0.020", 2.890), ("1.830×0.915×0.025", 2.305)])
        ]

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        top_btn_layout = QHBoxLayout()
        self.add_warehouse_btn = QPushButton("添加新仓位")
        self.add_warehouse_btn.clicked.connect(self.add_warehouse)
        self.settings_btn = QPushButton("预警设置")
        self.settings_btn.clicked.connect(self.open_settings)
        top_btn_layout.addWidget(self.add_warehouse_btn)
        top_btn_layout.addWidget(self.settings_btn)
        top_btn_layout.addStretch()
        main_layout.addLayout(top_btn_layout)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("QScrollArea {border: none;}")
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area, stretch=2)

        stats_layout = QHBoxLayout()

        self.total_label = QLabel("总统计：")
        self.total_label.setFont(QFont("Arial", 11))
        self.total_label.setStyleSheet("""
            QLabel {
                border: 1px solid #888888;
                border-radius: 5px;
                padding: 8px;
                margin: 10px;
            }
        """)
        stats_layout.addWidget(self.total_label, stretch=1)

        self.stats_chart = StatsChartWidget(self)
        stats_layout.addWidget(self.stats_chart, stretch=4)

        main_layout.addLayout(stats_layout, stretch=1)

        self.load_warehouses()
        self.update_total_stats()
        self.setCentralWidget(main_widget)

    def load_warehouses(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (name, boards) in enumerate(self.warehouse_data):
            widget = WarehouseWidget(name, boards, self)
            self.grid.addWidget(widget, i // 3, i % 3)

    def add_warehouse(self):
        dialog = AddWarehouseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.warehouse_name:
            self.warehouse_data.append((dialog.warehouse_name, []))
            self.load_warehouses()
            QMessageBox.information(self, "成功", f"已添加新仓位：{dialog.warehouse_name}")

    def open_settings(self):
        dialog = SettingsDialog(self.warning_threshold, self.warning_enabled, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.warning_threshold = dialog.threshold
            self.warning_enabled = dialog.enabled
            self.refresh_all_displays()

    def refresh_all_displays(self):
        for i in range(self.grid.count()):
            item = self.grid.itemAt(i)
            if item and item.widget():
                item.widget().update_display()

        self.update_total_stats()

    def update_total_stats(self):
        total_stats = {}

        for name, boards in self.warehouse_data:
            for spec, volume in boards:
                total_stats[spec] = total_stats.get(spec, 0) + volume

        sorted_total = sort_by_thickness(list(total_stats.items()))
        total_text = "总统计（按厚度排序）：\n"
        for spec, total in sorted_total:
            if self.warning_enabled and total < self.warning_threshold:
                total_text += f"  {spec}: {total:.3f} 方（低库存）\n"  # 三位小数
            else:
                total_text += f"  {spec}: {total:.3f} 方\n"  # 三位小数
        self.total_label.setText(total_text)

        self.stats_chart.update_chart(total_stats)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            #low_stock {
                border-color: red;
                border-width: 2px;
            }
        """)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"程序错误: {str(e)}")
        sys.exit(1)